from __future__ import annotations

import time


def try_handle_late_message_checks(
    *,
    user_message: str,
    phone: str,
    history: list,
    start_time: float,
    is_conversation_ending_fn,
    get_closing_message_fn,
    detect_language_fn,
    add_to_history_fn,
    save_message_fn,
    parse_turkish_date_fn,
    is_hotel_open_fn,
    format_date_turkish_fn,
    get_welcome_message_fn,
    schedule_followup_fn,
    record_metric_fn,
    is_greeting_fn,
    is_menu_selection_fn,
    get_menu_response_fn,
    response_factory,
):
    msg_lower = (user_message or "").lower()
    has_active_intent = (
        ("?" in (user_message or ""))
        or any(
            k in msg_lower
            for k in [
                "rezerv",
                "oda",
                "fiyat",
                "ücret",
                "ucret",
                "kaç para",
                "transfer",
                "wifi",
                "internet",
                "kahvalt",
                "check",
                "konum",
                "nerede",
                "adres",
                "havuz",
                "müsait",
                "musait",
                "availability",
                "book",
                "reservation",
            ]
        )
    )
    if is_conversation_ending_fn(user_message) and not has_active_intent:
        reply = get_closing_message_fn(detect_language_fn(user_message))
        add_to_history_fn(phone, "user", user_message)
        add_to_history_fn(phone, "assistant", reply)
        save_message_fn(phone, user_message, reply)
        return response_factory(reply=reply, status="ok")

    transfer_words = [
        "transfer",
        "havalimanı",
        "havaalanı",
        "airport",
        "dalaman",
        "antalya",
        "uçuş",
        "ucus",
        "flight",
        "iniş",
        "inis",
    ]
    is_transfer_context = any(w in msg_lower for w in transfer_words)

    last_menu = None
    if history:
        for m in reversed(history[-12:]):
            role = (m.get("role") or m.get("sender") or "").lower()
            content = (m.get("content") or "").strip().lower()
            if role == "user" and content in {"1", "2", "3", "4"}:
                last_menu = content
                break
    if last_menu == "2":
        is_transfer_context = True

    if not is_transfer_context and history:
        recent_user_context = " ".join(
            [(m.get("content") or "") for m in history[-8:] if (m.get("role") or m.get("sender") or "").lower() == "user"]
        ).lower()
        if any(w in recent_user_context for w in transfer_words):
            is_transfer_context = True

    if is_transfer_context:
        parsed_date = parse_turkish_date_fn(user_message)
        if parsed_date and not is_hotel_open_fn(parsed_date):
            date_str = format_date_turkish_fn(parsed_date)
            reply = (
                f"Maalesef {date_str} tarihi için transfer hizmeti veremiyoruz. "
                "Otelimiz 10 Nisan - 10 Kasım tarihleri arasında açıktır ve transfer hizmeti sadece bu dönemde geçerlidir. "
                "Bu tarihlerde size yardımcı olmaktan mutluluk duyarız! 😊"
            )
            add_to_history_fn(phone, "user", user_message)
            add_to_history_fn(phone, "assistant", reply)
            save_message_fn(phone, user_message, reply)
            return response_factory(reply=reply, status="season_blocked")

    if not history or len(history) == 0:
        msg = (user_message or "").strip()
        msg_clean = msg.lower().strip("!?. ,\n\t")
        plain_greetings = {"merhaba", "selam", "hi", "hello", "hey"}
        if msg_clean in plain_greetings or len(msg_clean) <= 2:
            first_msg_lang = detect_language_fn(msg)
            welcome_message = get_welcome_message_fn(first_msg_lang)
            add_to_history_fn(phone, "user", user_message)
            add_to_history_fn(phone, "assistant", welcome_message)
            save_message_fn(phone, user_message, welcome_message)
            schedule_followup_fn(phone)
            elapsed = time.time() - start_time
            record_metric_fn("first_message", response_time=elapsed)
            return response_factory(reply=welcome_message, status="first_message")

    greeting_check, greeting_lang = is_greeting_fn(user_message)
    if greeting_check and (user_message or "").strip().lower() in {"merhaba", "selam", "hi", "hello", "hey"}:
        reply = get_welcome_message_fn(greeting_lang)
        add_to_history_fn(phone, "user", user_message)
        add_to_history_fn(phone, "assistant", reply)
        save_message_fn(phone, user_message, reply)
        schedule_followup_fn(phone)
        elapsed = time.time() - start_time
        record_metric_fn("greeting", response_time=elapsed)
        return response_factory(reply=reply, status="ok")

    is_menu, selection = is_menu_selection_fn(user_message)
    if is_menu:
        conversation_lang = "tr"
        if history:
            recent_text = " ".join([m.get("content", "") for m in history[-4:]])
            conversation_lang = detect_language_fn(recent_text)
        reply = get_menu_response_fn(selection, conversation_lang)
        add_to_history_fn(phone, "user", user_message)
        add_to_history_fn(phone, "assistant", reply)
        save_message_fn(phone, user_message, reply)
        schedule_followup_fn(phone)
        elapsed = time.time() - start_time
        record_metric_fn("menu", category=f"menu_{selection}", response_time=elapsed)
        return response_factory(reply=reply, status="ok")

    return None
