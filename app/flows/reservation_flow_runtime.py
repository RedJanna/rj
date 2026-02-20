from __future__ import annotations

import asyncio
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
            data[correction["field"]] = correction["new_value"]
            update_reservation_flow_fn(phone, state, data)
            return (
                f"Kişi sayısını {correction['new_value']} olarak güncelledim."
                if lang == "tr"
                else f"Updated to {correction['new_value']}."
            )

        extracted = extract_all_reservation_info_fn(message)
        if extracted.get("guest_count"):
            data["guest_count"] = extracted["guest_count"]
        if extracted.get("date"):
            data["date"] = extracted["date"]
        if extracted.get("time"):
            data["time"] = extracted["time"]
            data["meal_type"] = get_meal_type_from_time_fn(extracted["time"])

        if data.get("guest_count") and data["guest_count"] > 8:
            clear_reservation_flow_fn(phone)
            await notify_admin_handoff_fn(
                "grup_rezervasyon", "medium", phone, f"Grup rezervasyon: {data['guest_count']} kişi"
            )
            msg = (
                f"{data['guest_count']} ve üzeri kişilik rezervasyonlar için ekibimiz size yardımcı olacaktır."
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
            if len(message.strip()) >= 2:
                data["customer_name"] = message.strip().title()
                update_reservation_flow_fn(phone, reservation_state_cls.ASK_SPECIAL.value, data)
                return (
                    f"Teşekkürler {data['customer_name']}! Özel bir isteğiniz var mı? (Yoksa 'yok' yazın)"
                    if lang == "tr"
                    else f"Thanks {data['customer_name']}! Any special requests? (Type 'none' if not)"
                )
            return "Lütfen geçerli bir isim girin." if lang == "tr" else "Please enter a valid name."

        if state == reservation_state_cls.ASK_SPECIAL.value:
            if msg_lower in ["yok", "hayır", "no", "none", "-"]:
                data["special_requests"] = None
            else:
                data["special_requests"] = message.strip()

            update_reservation_flow_fn(phone, reservation_state_cls.CONFIRM.value, data)
            formatted_date = format_date_turkish_fn(data["date"]) if lang == "tr" else format_date_english_fn(data["date"])
            meal_names = {"breakfast": "Kahvaltı", "Lunch": "Öğle Yemeği", "Dinner": "Akşam Yemeği"}
            meal_name = meal_names.get(data.get("meal_type", "Dinner"), "Akşam Yemeği")
            confirm_msg = f"""📋 REZERVASYON ÖZETİ:
━━━━━━━━━━━━━━━━━━━━
📅 Tarih: {formatted_date}
🕐 Saat: {data['time']}
👥 Kişi: {data['guest_count']}
👤 İsim: {data['customer_name']}
🍽️ Öğün: {meal_name}"""
            if data.get("special_requests"):
                confirm_msg += f"\n📝 Not: {data['special_requests']}"
            confirm_msg += "\n\n✅ Onaylamak için 'Evet', iptal için 'Hayır' yazın."
            return confirm_msg

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
                confirm_message = format_reservation_confirmation_fn(reservation, lang)
                asyncio.create_task(send_reservation_pdf_fn(phone, reservation))

                try:
                    reservation_datetime = datetime.strptime(f"{data['date']} {data['time']}", "%Y-%m-%d %H:%M")
                    schedule_restaurant_reminder_fn(
                        phone=phone,
                        reservation_id=reservation.get("id", str(int(datetime.now().timestamp()))),
                        reservation_datetime=reservation_datetime,
                        guest_name=data.get("customer_name", "Misafir"),
                        guest_count=data.get("guest_count", 2),
                        language=lang,
                    )
                except Exception as e:
                    print(f"⚠️ Hatırlatma planlanamadı: {e}")

                return confirm_message, "ok"

            if msg_lower in ["hayır", "no", "iptal", "vazgeç"]:
                clear_reservation_flow_fn(phone)
                msg = "Rezervasyon iptal edildi." if lang == "tr" else "Reservation cancelled."
                return msg, "ok"

            return "Lütfen 'Evet' veya 'Hayır' ile cevap verin." if lang == "tr" else "Please answer 'Yes' or 'No'."

        clear_reservation_flow_fn(phone)
        return None

    return handle_reservation_flow
