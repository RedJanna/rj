from __future__ import annotations

from datetime import datetime
import re
import time


async def try_start_restaurant_reservation_flow(
    *,
    primary_intent: str,
    needs_handoff: bool,
    handoff_category: str,
    user_message: str,
    phone: str,
    start_time: float,
    restaurant_settings: dict,
    clear_reservation_flow_fn,
    notify_admin_handoff_fn,
    detect_language_fn,
    add_to_history_fn,
    save_message_fn,
    response_factory,
    extract_date_from_message_fn,
    parse_date_input_fn,
    extract_date_phrase_fn,
    is_within_season_fn,
    extract_time_from_message_fn,
    get_meal_type_from_time_fn,
    update_reservation_flow_fn,
    reservation_state_cls,
    record_metric_fn,
    history: list | None = None,
):
    msg_lower = (user_message or "").lower()
    history = history or []

    def _has_recent_restaurant_prompt(hist: list) -> bool:
        for item in reversed(hist[-6:]):
            if item.get("role") != "assistant":
                continue
            content = (item.get("content") or "").lower()
            if any(
                k in content
                for k in [
                    "restoran rezervasyonunuz için yardımcı olurum",
                    "kaç kişi, tarih, saat ve isim",
                    "kaç kişilik rezervasyon yapmak istersiniz",
                    "restaurant reservation",
                    "how many people",
                    "what name should the reservation be under",
                ]
            ):
                return True
        return False

    has_restaurant_intent = str(primary_intent or "").upper() == "RESTAURANT_BOOKING_CREATE"
    has_restaurant_category = (handoff_category == "restoran_rezervasyon")
    # Kullanici ilk adimi kanonik cevapla almis olsa bile, devam mesajini restaurant flow'a sok.
    looks_like_restaurant_followup = _has_recent_restaurant_prompt(history) and any(
        k in msg_lower for k in ["kişi", "kisi", "person", "people", ":", "ağustos", "agustos", "temmuz", "haziran", "pm", "am"]
    )

    if not (has_restaurant_intent or has_restaurant_category or looks_like_restaurant_followup):
        return None

    customer_lang = detect_language_fn(user_message)
    extracted_data = {"language": customer_lang}

    guest_numbers = re.findall(r"(\d+)\s*(?:kişi|kisilik|person|people|guest|pax)", user_message.lower())
    if not guest_numbers:
        guest_numbers = re.findall(r"(?:for|table\s+for)\s+(\d+)", user_message.lower())
    if not guest_numbers:
        all_numbers = re.findall(r"\b(\d+)\b", user_message)
        guest_numbers = [n for n in all_numbers if 1 <= int(n) <= 20]

    max_auto_reservation = int(restaurant_settings.get("max_auto_reservation", 9) or 9)

    if guest_numbers:
        guest_count = int(guest_numbers[0])
        if guest_count <= max_auto_reservation:
            extracted_data["guest_count"] = guest_count
        else:
            clear_reservation_flow_fn(phone)
            try:
                from app.services.access_control_service import activate_human_takeover
                activate_human_takeover(phone, reason="restoran_grup_rezervasyon")
            except Exception:
                pass
            await notify_admin_handoff_fn(
                category="restoran_rezervasyon",
                priority="medium",
                customer_phone=phone,
                customer_message=f"GRUP REZERVASYONU: {guest_count} kişi",
                source="restaurant_start_handler.group_handoff",
                detected_intent="RESTAURANT_BOOKING_CREATE",
                confidence=0.95,
                conversation_summary=f"group_reservation guest_count={guest_count}",
                attempted_actions=["restaurant_group_limit_check"],
                suggested_reply=(
                    f"{guest_count} kişilik grup rezervasyonu (10+ kişi) için sizi müşteri temsilcimize bağlıyorum."
                ),
                tags=["restaurant", "group_handoff"],
            )
            if customer_lang == "en":
                reply = f"For a group reservation of {guest_count} people, I'm connecting you with our representative. Please wait a moment."
            else:
                reply = f"{guest_count} kişilik grup rezervasyonu için sizi müşteri temsilcimize bağlıyorum. Lütfen biraz bekleyiniz."
            add_to_history_fn(phone, "user", user_message)
            add_to_history_fn(phone, "assistant", reply)
            save_message_fn(phone, user_message, f"[GRUP REZERVASYONU] {reply}")
            return response_factory(reply=reply, status="handoff")
    parsed_date = extract_date_from_message_fn(user_message)
    if not parsed_date:
        parsed_date = parse_date_input_fn(user_message)
    if not parsed_date:
        date_phrase = extract_date_phrase_fn(user_message)
        if date_phrase:
            parsed_date = extract_date_from_message_fn(date_phrase) or parse_date_input_fn(date_phrase)
    if parsed_date and parsed_date >= datetime.now().strftime("%Y-%m-%d"):
        is_in_season, season_error = is_within_season_fn(parsed_date)
        if not is_in_season:
            clear_reservation_flow_fn(phone)
            reply = season_error
            add_to_history_fn(phone, "user", user_message)
            add_to_history_fn(phone, "assistant", reply)
            save_message_fn(phone, user_message, f"[SEZON DIŞI] {reply}")
            return response_factory(reply=reply, status="season_blocked")
        extracted_data["date"] = parsed_date

    extracted_time = extract_time_from_message_fn(user_message)
    if extracted_time:
        extracted_data["time"] = extracted_time
        meal_type = get_meal_type_from_time_fn(extracted_time)
        if meal_type:
            extracted_data["meal_type"] = meal_type

    if guest_numbers and extracted_data.get("date") and extracted_data.get("time"):
        update_reservation_flow_fn(phone, reservation_state_cls.ASK_NAME.value, extracted_data)
        if customer_lang == "en":
            reply = (
                f"Perfect! I noted {extracted_data['guest_count']} people, {extracted_data['date']} at {extracted_data['time']}.\n"
                "What name should the reservation be under?"
            )
        else:
            reply = (
                f"Harika! {extracted_data['guest_count']} kişi, {extracted_data['date']} tarihi ve {extracted_data['time']} saati için not ettim. 📝\n\n"
                "Rezervasyon hangi isim üzerine olacak?"
            )
    elif guest_numbers and extracted_data.get("date"):
        update_reservation_flow_fn(phone, reservation_state_cls.ASK_TIME.value, extracted_data)
        if customer_lang == "en":
            reply = (
                f"Great! Noted for {extracted_data['guest_count']} people on {extracted_data['date']}. 📝\n\n"
                "What time would you prefer? (Lunch: 12:00-15:00, Dinner: 18:00-22:00)"
            )
        else:
            reply = (
                f"Harika! {extracted_data['guest_count']} kişi, {extracted_data['date']} tarihi için not ettim. 📝\n\n"
                "Hangi saati tercih edersiniz? (Öğle: 12:00-15:00, Akşam: 18:00-22:00)"
            )
    elif guest_numbers:
        update_reservation_flow_fn(phone, reservation_state_cls.ASK_DATE.value, extracted_data)
        if customer_lang == "en":
            reply = f"Great! Noted for {extracted_data['guest_count']} people. 📝\n\nWhich date would you like? (e.g., tomorrow, July 15, 20/07)"
        else:
            reply = f"Harika! {extracted_data['guest_count']} kişi için not ettim. 📝\n\nHangi tarih için rezervasyon yapmak istersiniz? (Örn: yarın, 15 Temmuz, 20/07)"
    else:
        update_reservation_flow_fn(phone, reservation_state_cls.ASK_GUESTS.value, extracted_data)
        if customer_lang == "en":
            reply = "Of course! I'd be happy to help you make a restaurant reservation. 🍽️\n\nHow many people will the reservation be for?"
        else:
            reply = "Restoran rezervasyonunuz için yardımcı olurum. 🍽️\n\nKaç kişilik rezervasyon yapmak istersiniz?"

    add_to_history_fn(phone, "user", user_message)
    add_to_history_fn(phone, "assistant", reply)
    save_message_fn(phone, user_message, f"[REZERVASYON BAŞLADI - {customer_lang.upper()}] {reply}")
    elapsed = time.time() - start_time
    record_metric_fn("reservation_start", response_time=elapsed)
    return response_factory(reply=reply, status="reservation_flow_started")
