from __future__ import annotations

import asyncio
import re
from datetime import datetime


def build_reservation_flow_handler(
    *,
    get_conversation_history_fn,
    detect_language_fn,
    update_reservation_flow_fn,
    clear_reservation_flow_fn,
    should_break_reservation_flow_fn,
    detect_correction_in_message_fn,
    extract_all_reservation_info_fn,
    get_meal_type_from_time_fn,
    notify_admin_handoff_fn,
    is_within_season_fn,
    reservation_state_cls,
    format_date_turkish_fn,
    format_date_english_fn,
    create_reservation_fn,
    format_reservation_confirmation_fn,
    send_reservation_pdf_fn,
    schedule_restaurant_reminder_fn,
):
    def _is_likely_person_name(text: str) -> bool:
        raw = (text or "").strip()
        if not raw or len(raw) < 2 or len(raw) > 60:
            return False
        if any(ch.isdigit() for ch in raw):
            return False
        low = raw.lower()
        blocked = (
            "pardon", "değiş", "degis", "düzelt", "duzelt", "yanlış", "yanlis",
            "saat", "tarih", "kişi", "kisi", "rezervasyon", "olarak", "miyiz", "?",
        )
        if any(b in low for b in blocked):
            return False
        words = re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü'\-]+", raw)
        return 1 <= len(words) <= 4

    async def handle_reservation_flow(phone: str, message: str, flow: dict) -> str | tuple[str, str] | None:
        state = flow.get("state", "idle")
        data = flow.get("data", {})
        lang = data.get("lang")

        if lang not in ("tr", "en"):
            inferred = None
            try:
                history = get_conversation_history_fn(phone) if phone else []
                for item in reversed(history):
                    if item.get("role") == "assistant" and item.get("content"):
                        inferred = detect_language_fn(item["content"])
                        break
            except Exception:
                inferred = None

            lang = inferred if inferred in ("tr", "en") else detect_language_fn(message)
            data["lang"] = lang
            update_reservation_flow_fn(phone, state, data)

        msg_lower = message.lower().strip()

        def _build_confirmation_summary(payload: dict) -> str:
            formatted_date = (
                format_date_turkish_fn(payload["date"])
                if lang == "tr"
                else format_date_english_fn(payload["date"])
            )
            meal_names = {"breakfast": "Kahvaltı", "Lunch": "Öğle Yemeği", "Dinner": "Akşam Yemeği"}
            meal_name = meal_names.get(payload.get("meal_type", "Dinner"), "Akşam Yemeği")
            confirm_msg = f"""📋 REZERVASYON ÖZETİ:
━━━━━━━━━━━━━━━━━━━━
📅 Tarih: {formatted_date}
🕐 Saat: {payload['time']}
👥 Kişi: {payload['guest_count']}
👤 İsim: {payload['customer_name']}
🍽️ Öğün: {meal_name}"""
            if payload.get("special_requests"):
                confirm_msg += f"\n📝 Not: {payload['special_requests']}"
            confirm_msg += "\n\n✅ Onaylamak için 'Evet', iptal için 'Hayır' yazın."
            return confirm_msg

        def _next_prompt_and_state(payload: dict) -> tuple[str, str]:
            if not payload.get("guest_count"):
                return (
                    ("Kaç kişilik rezervasyon düşünüyorsunuz?" if lang == "tr" else "How many guests?"),
                    reservation_state_cls.ASK_GUESTS.value,
                )
            if not payload.get("date"):
                return (
                    (
                        "Hangi tarih için? (örn: yarın, 15 Temmuz)"
                        if lang == "tr"
                        else "Which date? (e.g., tomorrow, July 15)"
                    ),
                    reservation_state_cls.ASK_DATE.value,
                )
            if not payload.get("time"):
                return (
                    ("Saat kaçı tercih edersiniz? (örn: 19:00)" if lang == "tr" else "What time? (e.g., 7pm)"),
                    reservation_state_cls.ASK_TIME.value,
                )
            if not payload.get("customer_name"):
                return (
                    ("Rezervasyon hangi isim adına olsun?" if lang == "tr" else "What name for the reservation?"),
                    reservation_state_cls.ASK_NAME.value,
                )
            return (
                (
                    "Özel bir isteğiniz var mı? (Yoksa 'yok' yazın)"
                    if lang == "tr"
                    else "Any special requests? (Type 'none' if not)"
                ),
                reservation_state_cls.ASK_SPECIAL.value,
            )

        if any(kw in msg_lower for kw in ["iptal", "vazgeç", "cancel", "istemiyorum"]):
            clear_reservation_flow_fn(phone)
            msg = (
                "Rezervasyon iptal edildi. Size nasıl yardımcı olabilirim?"
                if lang == "tr"
                else "Reservation cancelled. How can I help you?"
            )
            return msg, "ok"

        if should_break_reservation_flow_fn(message, state):
            clear_reservation_flow_fn(phone)
            return None

        correction = detect_correction_in_message_fn(message, state)
        if correction["is_correction"]:
            field = str(correction.get("field") or "").strip()
            new_value = correction.get("new_value")
            if field == "time":
                data["meal_type"] = get_meal_type_from_time_fn(str(new_value))
            if field == "date":
                is_valid, error_msg = is_within_season_fn(str(new_value), lang)
                if not is_valid:
                    return error_msg, "season_blocked"
            data[field] = new_value
            update_reservation_flow_fn(phone, state, data)

            if state == reservation_state_cls.CONFIRM.value and data.get("customer_name"):
                if lang == "tr":
                    field_labels = {
                        "time": f"saati {new_value}",
                        "date": "tarihi",
                        "guest_count": f"kişi sayısını {new_value}",
                    }
                    prefix = f"Teşekkür ederim, {field_labels.get(field, 'bilgileri')} güncelledim.\n\n"
                else:
                    prefix = "Thanks, I updated your reservation details.\n\n"
                return prefix + _build_confirmation_summary(data)

            if state == reservation_state_cls.ASK_SPECIAL.value and data.get("customer_name"):
                if lang == "tr":
                    return "Güncellemeyi not aldım. Özel bir isteğiniz var mı? (Yoksa 'yok' yazın)"
                return "Update noted. Any special requests? (Type 'none' if not)"

            question, next_state = _next_prompt_and_state(data)
            update_reservation_flow_fn(phone, next_state, data)

            if lang == "tr":
                field_labels = {
                    "time": f"saati {new_value}",
                    "date": "tarihi",
                    "guest_count": f"kişi sayısını {new_value}",
                }
                prefix = f"Tamam, {field_labels.get(field, 'bilgileri')} güncelledim."
                return f"{prefix} {question}"
            return f"Updated your details. {question}"

        before_extract = dict(data)
        extracted_all = extract_all_reservation_info_fn(message)
        extracted = {"guest_count": None, "date": None, "time": None}
        if state in {reservation_state_cls.ASK_GUESTS.value, reservation_state_cls.IDLE.value}:
            extracted["guest_count"] = extracted_all.get("guest_count")
        elif state == reservation_state_cls.ASK_DATE.value:
            extracted["date"] = extracted_all.get("date")
        elif state == reservation_state_cls.ASK_TIME.value:
            extracted["time"] = extracted_all.get("time")
        else:
            extracted["guest_count"] = extracted_all.get("guest_count")
            extracted["date"] = extracted_all.get("date")
            extracted["time"] = extracted_all.get("time")

        if extracted.get("guest_count"):
            data["guest_count"] = extracted["guest_count"]
        if extracted.get("date"):
            data["date"] = extracted["date"]
        if extracted.get("time"):
            data["time"] = extracted["time"]
            data["meal_type"] = get_meal_type_from_time_fn(extracted["time"])

        if data.get("guest_count") and data["guest_count"] > 9:
            clear_reservation_flow_fn(phone)
            await notify_admin_handoff_fn(
                "grup_rezervasyon", "medium", phone, f"Grup rezervasyon: {data['guest_count']} kişi"
            )
            msg = (
                f"{data['guest_count']} kişilik rezervasyonlar için ekibimiz size yardımcı olacaktır."
                if lang == "tr"
                else f"For groups of {data['guest_count']}+, our team will assist you."
            )
            return msg, "handoff"

        if data.get("date"):
            is_valid, error_msg = is_within_season_fn(data["date"], lang)
            if not is_valid:
                data.pop("date", None)
                return error_msg, "season_blocked"

        if data.get("time") and not data.get("meal_type"):
            await notify_admin_handoff_fn("ozel_saat", "medium", phone, f"Özel saat: {data['time']}")
            return (
                f"{data['time']} saati standart servis saatlerimiz dışındadır. Ekibimiz sizinle iletişime geçecektir."
                if lang == "tr"
                else f"{data['time']} is outside our hours. Our team will contact you."
            )

        ack_parts = []
        if extracted.get("guest_count"):
            ack_parts.append(f"{extracted['guest_count']} kişi" if lang == "tr" else f"{extracted['guest_count']} guests")
        if extracted.get("date"):
            formatted = (
                format_date_turkish_fn(extracted["date"])
                if lang == "tr"
                else format_date_english_fn(extracted["date"])
            )
            ack_parts.append(formatted)
        if extracted.get("time"):
            ack_parts.append(extracted["time"])

        ack = ""
        if ack_parts:
            ack = f"Harika! {', '.join(ack_parts)} not ettim. " if lang == "tr" else f"Great! Noted: {', '.join(ack_parts)}. "

        if not data.get("guest_count"):
            update_reservation_flow_fn(phone, reservation_state_cls.ASK_GUESTS.value, data)
            question = "Kaç kişilik rezervasyon düşünüyorsunuz?" if lang == "tr" else "How many guests?"
            return ack + question

        if not data.get("date"):
            update_reservation_flow_fn(phone, reservation_state_cls.ASK_DATE.value, data)
            question = "Hangi tarih için? (örn: yarın, 15 Temmuz)" if lang == "tr" else "Which date? (e.g., tomorrow, July 15)"
            return ack + question

        if not data.get("time"):
            update_reservation_flow_fn(phone, reservation_state_cls.ASK_TIME.value, data)
            question = "Saat kaçı tercih edersiniz? (örn: 19:00)" if lang == "tr" else "What time? (e.g., 7pm)"
            return ack + question

        if not data.get("customer_name"):
            if state != reservation_state_cls.ASK_NAME.value:
                update_reservation_flow_fn(phone, reservation_state_cls.ASK_NAME.value, data)
                question = "Rezervasyon hangi isim adına olsun?" if lang == "tr" else "What name for the reservation?"
                return ack + question

            edit_markers = ("pardon", "değiş", "degis", "düzelt", "duzelt", "yanlış", "yanlis", "actually", "sorry")
            looks_like_edit = any(m in msg_lower for m in edit_markers) or bool(
                extracted.get("guest_count") or extracted.get("date") or extracted.get("time")
            )
            if looks_like_edit:
                changed_bits = []
                if data.get("time") and data.get("time") != before_extract.get("time"):
                    changed_bits.append(f"saati {data['time']}")
                if data.get("date") and data.get("date") != before_extract.get("date"):
                    changed_bits.append("tarihi")
                if data.get("guest_count") and data.get("guest_count") != before_extract.get("guest_count"):
                    changed_bits.append(f"kişi sayısını {data['guest_count']}")
                update_reservation_flow_fn(phone, reservation_state_cls.ASK_NAME.value, data)
                if lang == "tr":
                    prefix = "Not aldım, "
                    if changed_bits:
                        prefix = f"Tamam, {', '.join(changed_bits)} güncelledim. "
                    return prefix + "Şimdi rezervasyon hangi isim adına olsun?"
                return "Updated. What name should the reservation be under now?"

            if _is_likely_person_name(message):
                data["customer_name"] = message.strip().title()
                update_reservation_flow_fn(phone, reservation_state_cls.ASK_SPECIAL.value, data)
                return (
                    f"Teşekkürler {data['customer_name']}! Özel bir isteğiniz var mı? (Yoksa 'yok' yazın)"
                    if lang == "tr"
                    else f"Thanks {data['customer_name']}! Any special requests? (Type 'none' if not)"
                )
            return (
                "İsmi anlayamadım. Lütfen sadece ad-soyad yazın. (Örn: Ahmet Yılmaz)"
                if lang == "tr"
                else "I could not parse the name. Please share only first and last name."
            )

        if state == reservation_state_cls.ASK_SPECIAL.value:
            if msg_lower in ["yok", "hayır", "no", "none", "-"]:
                data["special_requests"] = None
            else:
                data["special_requests"] = message.strip()

            update_reservation_flow_fn(phone, reservation_state_cls.CONFIRM.value, data)
            return _build_confirmation_summary(data)

        if state == reservation_state_cls.CONFIRM.value:
            if msg_lower in ["evet", "yes", "onay", "tamam", "ok"]:
                reservation = create_reservation_fn(
                    phone=phone,
                    name=data["customer_name"],
                    meal_type=data.get("meal_type", "Dinner"),
                    date=data["date"],
                    time=data["time"],
                    guest_count=data["guest_count"],
                    special_requests=data.get("special_requests"),
                    lang=lang,
                )
                clear_reservation_flow_fn(phone)
                await notify_admin_handoff_fn(
                    "restoran_rezervasyon",
                    "medium",
                    phone,
                    (
                        f"Kesin onay bekleyen restoran rezervasyonu: "
                        f"#{reservation.get('id')} | {reservation.get('date')} {reservation.get('time')} | "
                        f"{reservation.get('guest_count')} kisi | {reservation.get('customer_name')}"
                    ),
                )
                if lang == "tr":
                    confirm_message = (
                        f"Talebinizi aldım ve ön rezervasyonunuzu oluşturdum (No: #{reservation.get('id')}).\n"
                        "Kesin onay için canlı müşteri temsilcimiz kısa süre içinde sizinle iletişime geçecek."
                    )
                else:
                    confirm_message = (
                        f"I've created your preliminary reservation request (No: #{reservation.get('id')}).\n"
                        "Our live representative will contact you shortly for final confirmation."
                    )
                return confirm_message, "handoff"

            if msg_lower in ["hayır", "no", "iptal", "vazgeç"]:
                clear_reservation_flow_fn(phone)
                msg = "Rezervasyon iptal edildi." if lang == "tr" else "Reservation cancelled."
                return msg, "ok"

            return "Lütfen 'Evet' veya 'Hayır' ile cevap verin." if lang == "tr" else "Please answer 'Yes' or 'No'."

        clear_reservation_flow_fn(phone)
        return None

    return handle_reservation_flow
