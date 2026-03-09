from __future__ import annotations

import time
from typing import Any, Dict

from app.services.reservation_change_interpreter import (
    extract_slot_updates,
    is_change_request,
)
from app.services.hotel_runtime_info_service import get_hotel_runtime_info
from app.services.transfer_reservation_service import (
    clear_transfer_booking_flow,
    create_transfer_reservation,
    extract_transfer_flight_no,
    extract_transfer_guest_count,
    extract_transfer_route,
    extract_transfer_time_input,
    get_transfer_booking_flow,
    is_affirmative_reply,
    parse_transfer_date_input,
    update_transfer_booking_flow,
)


_TRANSFER_FOLLOWUP_MARKERS = (
    "transfer talebi icin adim adim",
    "transfer talebi için adım adım",
    "transfer tarihinizi paylaşın",
    "transfer tarihinizi paylasin",
    "ucus numaranizi",
    "uçuş numaranızı",
)


def _runtime_transfer_price_text(route: str | None = None) -> str:
    info = get_hotel_runtime_info()
    normalized_route = (route or "").lower()
    if "antalya" in normalized_route:
        fee = int(info.get("antalya_transfer_fee_eur") or 140)
    else:
        fee = int(info.get("dalaman_transfer_fee_eur") or 75)
    return f"{fee} EUR"

def _build_step_prompt(state: str, lang: str) -> str:
    if state == "ask_date":
        return (
            "1/5 Lütfen transfer tarihini yazın. (Örn: 15 Haziran 2026)"
            if lang == "tr"
            else "1/5 Please share transfer date. (Example: June 15, 2026)"
        )
    if state == "ask_time":
        return (
            "2/5 Lütfen transfer saatini yazın. (Örn: 14:30)"
            if lang == "tr"
            else "2/5 Please share transfer time. (Example: 14:30)"
        )
    if state == "ask_flight_no":
        return (
            "3/5 Lütfen uçuş numarasını yazın. (Örn: TK1234)"
            if lang == "tr"
            else "3/5 Please share flight number. (Example: TK1234)"
        )
    if state == "ask_guest_count":
        return (
            "4/5 Lütfen kişi sayısını yazın. (Örn: 2 kişi)"
            if lang == "tr"
            else "4/5 Please share guest count. (Example: 2 guests)"
        )
    if state == "ask_route":
        return (
            "5/5 Lütfen transfer rotasını yazın. (Örn: Dalaman Havalimanı -> Kassandra Ölüdeniz)"
            if lang == "tr"
            else "5/5 Please share transfer route. (Example: Dalaman Airport -> Kassandra Oludeniz)"
        )
    return ""


def _next_transfer_state(data: Dict[str, Any]) -> str:
    if not data.get("transfer_date"):
        return "ask_date"
    if not data.get("transfer_time"):
        return "ask_time"
    if not data.get("flight_no"):
        return "ask_flight_no"
    if not data.get("guest_count"):
        return "ask_guest_count"
    if not data.get("transfer_route"):
        return "ask_route"
    return "confirm"


def _summarize_transfer(data: Dict[str, Any]) -> str:
    return (
        "Transfer özeti:\n"
        f"📍 {data.get('transfer_route', '-')}\n"
        f"📅 {data.get('transfer_date', '-')}\n"
        f"🕒 {data.get('transfer_time', '-')}\n"
        f"✈️ Uçuş: {data.get('flight_no', '-')}\n"
        f"👥 {data.get('guest_text', '-')}\n\n"
        "Onay için 'Evet', iptal için 'Hayır' yazabilirsiniz."
    )


def _extract_transfer_updates(msg: str) -> Dict[str, Any]:
    raw_updates = extract_slot_updates(
        msg,
        date_parser=lambda txt: parse_transfer_date_input(txt),
        time_parser=extract_transfer_time_input,
        guest_count_parser=extract_transfer_guest_count,
        flight_no_parser=extract_transfer_flight_no,
        route_parser=extract_transfer_route,
    )
    updates: Dict[str, Any] = {}
    if raw_updates.get("date"):
        updates["transfer_date"] = raw_updates["date"]
    if raw_updates.get("time"):
        updates["transfer_time"] = raw_updates["time"]
    if raw_updates.get("flight_no"):
        updates["flight_no"] = raw_updates["flight_no"]
    if raw_updates.get("guest_count"):
        updates["guest_count"] = raw_updates["guest_count"]
        updates["guest_text"] = f"{raw_updates['guest_count']} kişi"
    if raw_updates.get("route"):
        updates["transfer_route"] = raw_updates["route"]
    return updates


def _updated_fields_text(changed: list[str], lang: str) -> str:
    if not changed:
        return ""
    labels = {
        "transfer_date": ("tarih", "date"),
        "transfer_time": ("saat", "time"),
        "flight_no": ("uçuş", "flight"),
        "guest_count": ("kişi sayısı", "guest count"),
        "transfer_route": ("rota", "route"),
    }
    named = [labels.get(key, (key, key))[0 if lang == "tr" else 1] for key in changed]
    if lang == "tr":
        return f"Not aldım, şu alanları güncelledim: {', '.join(named)}.\n"
    return f"Noted, updated fields: {', '.join(named)}.\n"


def _has_recent_transfer_prompt(history: list[Dict[str, Any]]) -> bool:
    for item in reversed((history or [])[-8:]):
        if item.get("role") != "assistant":
            continue
        content = str(item.get("content") or "").lower()
        if any(marker in content for marker in _TRANSFER_FOLLOWUP_MARKERS):
            return True
    return False


async def try_start_transfer_booking_flow(
    *,
    primary_intent: str,
    user_message: str,
    phone: str,
    history: list[Dict[str, Any]],
    start_time: float,
    detect_language_fn,
    notify_admin_handoff_fn,
    add_to_history_fn,
    save_message_fn,
    response_factory,
    record_metric_fn,
):
    flow = get_transfer_booking_flow(phone)
    state = str(flow.get("state") or "idle").strip().lower()
    data = flow.get("data") if isinstance(flow.get("data"), dict) else {}
    intent = str(primary_intent or "").upper()
    is_active = state != "idle"
    should_start = intent == "TRANSFER_BOOKING_REQUEST" or _has_recent_transfer_prompt(history)
    if not (is_active or should_start):
        return None

    lang = detect_language_fn(user_message)
    msg = (user_message or "").strip()
    low = msg.lower()

    def _persist_and_reply(next_state: str, reply: str, extra: Dict[str, Any] | None = None):
        payload = dict(data)
        if extra:
            payload.update(extra)
        payload["lang"] = lang
        update_transfer_booking_flow(phone, next_state, payload)
        add_to_history_fn(phone, "user", user_message)
        add_to_history_fn(phone, "assistant", reply)
        save_message_fn(phone, user_message, reply)
        record_metric_fn("transfer_flow", category=next_state, response_time=time.time() - start_time)
        return response_factory(reply=reply, status="transfer_flow")

    if any(k in low for k in ("iptal", "vazgec", "vazgeç", "cancel")):
        clear_transfer_booking_flow(phone)
        reply = (
            "Transfer talebinizi iptal ettim. Dilerseniz yeniden başlatabiliriz."
            if lang == "tr"
            else "I cancelled your transfer request. We can start again if you want."
        )
        add_to_history_fn(phone, "user", user_message)
        add_to_history_fn(phone, "assistant", reply)
        save_message_fn(phone, user_message, reply)
        return response_factory(reply=reply, status="transfer_flow_cancelled")

    if state == "idle":
        reply = (
            "Transfer rezervasyonu için adım adım ilerleyelim.\n"
            "1/5 Lütfen transfer tarihini yazın. (Örn: 15 Haziran 2026)"
        )
        return _persist_and_reply("ask_date", reply)

    incoming_updates = _extract_transfer_updates(msg)
    if incoming_updates:
        changed_fields = [
            key for key, value in incoming_updates.items()
            if data.get(key) != value and key in {"transfer_date", "transfer_time", "flight_no", "guest_count", "transfer_route"}
        ]
        merged = dict(data)
        merged.update(incoming_updates)
        next_state = _next_transfer_state(merged)
        prefix = _updated_fields_text(changed_fields, lang)

        if next_state == "confirm":
            summary = _summarize_transfer(merged)
            return _persist_and_reply("confirm", f"{prefix}{summary}", merged)

        # Bilgi parse edildiğinde yanlış "anlayamadım" döngüsüne düşme.
        if is_change_request(msg) or state != next_state:
            prompt = _build_step_prompt(next_state, lang)
            if lang == "tr":
                return _persist_and_reply(next_state, f"{prefix}{prompt}", merged)
            return _persist_and_reply(next_state, f"{prefix}{prompt}", merged)

    if state == "ask_date":
        transfer_date = parse_transfer_date_input(msg)
        if not transfer_date:
            reply = "Tarihi anlayamadım. Lütfen gg/aa/yyyy veya '15 Haziran 2026' formatında yazın."
            return _persist_and_reply("ask_date", reply)
        reply = (
            f"Tarih tamam: {transfer_date}\n"
            "2/5 Lütfen transfer saatini yazın. (Örn: 14:30)"
        )
        return _persist_and_reply("ask_time", reply, {"transfer_date": transfer_date})

    if state == "ask_time":
        transfer_time = extract_transfer_time_input(msg)
        if not transfer_time:
            reply = "Saati anlayamadım. Lütfen HH:MM formatında yazın. (Örn: 14:30)"
            return _persist_and_reply("ask_time", reply)
        reply = "Saat tamam.\n3/5 Lütfen uçuş numarasını yazın. (Örn: TK1234)"
        return _persist_and_reply("ask_flight_no", reply, {"transfer_time": transfer_time})

    if state == "ask_flight_no":
        flight_no = extract_transfer_flight_no(msg)
        if not flight_no:
            reply = "Uçuş numarasını anlayamadım. Lütfen 'TK1234' benzeri formatta yazın."
            return _persist_and_reply("ask_flight_no", reply)
        reply = "Uçuş numarası tamam.\n4/5 Lütfen kişi sayısını yazın. (Örn: 2 kişi)"
        return _persist_and_reply("ask_guest_count", reply, {"flight_no": flight_no})

    if state == "ask_guest_count":
        guest_count = extract_transfer_guest_count(msg)
        if not guest_count:
            reply = "Kişi sayısını anlayamadım. Lütfen '2 kişi' şeklinde yazın."
            return _persist_and_reply("ask_guest_count", reply)
        reply = (
            "Kişi sayısı tamam.\n"
            "5/5 Lütfen transfer rotasını yazın. (Örn: Dalaman Havalimanı -> Kassandra Ölüdeniz)"
        )
        return _persist_and_reply("ask_route", reply, {"guest_count": guest_count, "guest_text": f"{guest_count} kişi"})

    if state == "ask_route":
        route = extract_transfer_route(msg)
        if not route:
            reply = "Rotayı anlayamadım. Lütfen 'Nereden -> Nereye' formatında yazın."
            return _persist_and_reply("ask_route", reply)
        merged = dict(data)
        merged["transfer_route"] = route
        summary = _summarize_transfer(merged)
        return _persist_and_reply("confirm", summary, {"transfer_route": route, "raw_summary": summary})

    if state == "confirm":
        if is_affirmative_reply(msg):
            details = {
                "customer_name": data.get("customer_name", ""),
                "transfer_route": data.get("transfer_route", "Dalaman Havalimani -> Kassandra Oludeniz"),
                "transfer_date": data.get("transfer_date", ""),
                "transfer_time": data.get("transfer_time", ""),
                "flight_no": data.get("flight_no", ""),
                "guest_text": data.get("guest_text", ""),
                "luggage_text": data.get("luggage_text", ""),
                "baby_seat": data.get("baby_seat", ""),
                "price_text": data.get("price_text", _runtime_transfer_price_text(data.get("transfer_route"))),
                "raw_summary": data.get("raw_summary", ""),
            }
            reservation = create_transfer_reservation(
                customer_phone=phone,
                details=details,
                source="transfer_flow_chat",
            )
            clear_transfer_booking_flow(phone)
            try:
                await notify_admin_handoff_fn(
                    category="antalya_transfer",
                    priority="medium",
                    customer_phone=phone,
                    customer_message=f"Yeni transfer rezervasyonu oluşturuldu: #{reservation.get('id')}",
                    source="transfer_start_handler.confirm",
                    detected_intent="TRANSFER_BOOKING_REQUEST",
                    confidence=0.95,
                    conversation_summary=f"transfer_created id={reservation.get('id')}",
                    attempted_actions=["transfer_step_flow", "create_transfer_reservation"],
                    suggested_reply="Transfer rezervasyonu oluşturuldu.",
                    tags=["transfer", "step_flow", "reservation_created"],
                )
            except Exception:
                pass

            reply = (
                f"Talebinizi aldım ve transfer rezervasyonunu oluşturdum. ✅ (ID: #{reservation.get('id')})\n"
                "Ekibimiz kısa süre içinde sizinle iletişime geçecek."
            )
            add_to_history_fn(phone, "user", user_message)
            add_to_history_fn(phone, "assistant", reply)
            save_message_fn(phone, user_message, reply)
            record_metric_fn("transfer_flow", category="completed", response_time=time.time() - start_time)
            return response_factory(reply=reply, status="transfer_flow_completed")

        if low in {"hayir", "hayır", "no"}:
            clear_transfer_booking_flow(phone)
            reply = "Transfer talebinizi iptal ettim. Dilerseniz yeniden başlayabiliriz."
            add_to_history_fn(phone, "user", user_message)
            add_to_history_fn(phone, "assistant", reply)
            save_message_fn(phone, user_message, reply)
            return response_factory(reply=reply, status="transfer_flow_cancelled")

        reply = "Onaylamak için 'Evet', iptal etmek için 'Hayır' yazın."
        return _persist_and_reply("confirm", reply)

    clear_transfer_booking_flow(phone)
    return None
