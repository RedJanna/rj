from __future__ import annotations

import re


async def run_chat_prechecks(
    *,
    phone: str,
    user_message: str,
    detect_language_fn,
    load_conversation_fn,
    notify_admin_error_fn,
    save_message_fn,
    is_safe_mode_fn,
    is_auto_safe_mode_fn,
    check_rate_limit_fn,
    is_automation_enabled_fn,
    is_blacklisted_fn,
    is_paused_fn,
    cancel_followup_fn,
    get_conversation_history_fn,
    handle_cancel_flow_v2_fn,
    detect_suspicious_message_fn,
    notify_admin_suspicious_fn,
    ai_question_response: str,
    suspicious_response: str,
    add_to_history_fn,
    detect_critical_issue_fn,
    send_critical_notification_fn,
    response_factory,
):
    persisted_conversation = load_conversation_fn(phone) if phone else {"messages": []}
    persisted_messages = persisted_conversation.get("messages", []) if isinstance(persisted_conversation, dict) else []

    # Konusma dosyasi bos/temiz ise stale RAM+flow state'lerini sifirla.
    # Boylece dosya silindikten sonra eski mesaj/rezervasyon baglami kullanilmaz.
    if phone and not persisted_messages:
        try:
            from app.services.conversation_store import conversation_history, last_activity
            from app.services.price_flow_service import clear_price_flow
            from app.services.restaurant_reservation_flow_service import clear_reservation_flow
            from app.services.booking_flow_service import purge_booking_flow_data

            clean_phone = re.sub(r"[^\d]", "", phone or "")
            conversation_history.pop(phone, None)
            last_activity.pop(phone, None)
            if clean_phone:
                conversation_history.pop(clean_phone, None)
                last_activity.pop(clean_phone, None)

            clear_price_flow(phone)
            clear_reservation_flow(phone)
            purge_booking_flow_data(phone)
        except Exception:
            pass

    if phone:
        history = persisted_messages
        if history:
            user_messages = [m for m in history[-10:] if m.get("role") == "user"]
            recent_user_msg = user_messages[-1].get("content", "").strip().lower() if user_messages else ""
            if recent_user_msg == user_message.lower():
                print(f"🔄 Duplicate mesaj atlandı: {phone} - '{user_message[:30]}...'")
                return {"response": response_factory(reply="", status="duplicate_skipped"), "lang": None, "history": None}

            bot_messages = [m for m in history[-6:] if m.get("role") == "assistant"]
            if bot_messages:
                last_bot_msg = bot_messages[-1].get("content", "").lower()
                greetings = ["hello", "hi", "hey", "merhaba", "selam", "привет", "здравствуйте"]
                if any(g in last_bot_msg for g in greetings):
                    if user_message.lower().strip() in greetings:
                        print(f"🔄 Tekrarlanan selamlama atlandı: {phone} - '{user_message}'")
                        return {"response": response_factory(reply="", status="greeting_duplicate_skipped"), "lang": None, "history": None}

    lang = detect_language_fn(user_message) if user_message else "tr"

    if is_safe_mode_fn() or is_auto_safe_mode_fn():
        await notify_admin_error_fn(
            error_type="Güvenli Mod Aktif",
            customer_phone=phone or "Bilinmiyor",
            customer_message=user_message,
            error_details="Sistem güvenli modda. Müşteriye cevap verilmedi.",
        )
        save_message_fn(phone, user_message, "[GÜVENLİ MOD - MÜŞTERİYE CEVAP VERİLMEDİ]")
        return {"response": response_factory(reply="", status="safe_mode_silent"), "lang": lang, "history": None}

    is_allowed, rate_reason = check_rate_limit_fn(phone)
    if not is_allowed:
        save_message_fn(phone, user_message, "[RATE LIMIT - MÜŞTERİYE CEVAP VERİLMEDİ]")
        return {"response": response_factory(reply="", status=rate_reason), "lang": lang, "history": None}

    if not user_message:
        return {"response": response_factory(reply="", status="empty"), "lang": lang, "history": None}

    if not is_automation_enabled_fn():
        await notify_admin_error_fn(
            error_type="Otomasyon Kapalı",
            customer_phone=phone or "Bilinmiyor",
            customer_message=user_message,
            error_details="Otomasyon kapalı. Müşteriye cevap verilmedi.",
        )
        save_message_fn(phone, user_message, "[OTOMASYON KAPALI - MÜŞTERİYE CEVAP VERİLMEDİ]")
        return {"response": response_factory(reply="", status="automation_disabled"), "lang": lang, "history": None}

    if is_blacklisted_fn(phone):
        save_message_fn(phone, user_message, "[BLACKLIST]")
        return {"response": response_factory(reply="", status="blacklisted"), "lang": lang, "history": None}

    if is_paused_fn(phone):
        save_message_fn(phone, user_message, "[PAUSED]")
        return {"response": response_factory(reply="", status="paused"), "lang": lang, "history": None}

    cancel_followup_fn(phone)
    history = get_conversation_history_fn(phone)

    try:
        cancel_reply = await handle_cancel_flow_v2_fn(phone, user_message)
        if cancel_reply:
            return {"response": response_factory(reply=cancel_reply, status="cancel_flow_v2"), "lang": lang, "history": history}
    except Exception:
        pass

    is_suspicious, suspicion_reason, severity = detect_suspicious_message_fn(user_message)
    if is_suspicious:
        await notify_admin_suspicious_fn(
            severity=severity,
            reason=suspicion_reason,
            customer_phone=phone or "Bilinmiyor",
            customer_message=user_message,
        )
        if "yapay zeka" in suspicion_reason.lower() or (severity == "high" and "yapay zeka" in user_message.lower()):
            reply = ai_question_response
            add_to_history_fn(phone, "user", user_message)
            add_to_history_fn(phone, "assistant", reply)
            save_message_fn(phone, user_message, reply)
            return {"response": response_factory(reply=reply, status="ai_question_handled"), "lang": lang, "history": history}
        if severity == "critical":
            reply = suspicious_response
            add_to_history_fn(phone, "user", user_message)
            add_to_history_fn(phone, "assistant", reply)
            save_message_fn(phone, user_message, f"[ŞÜPHELİ-KRİTİK: {suspicion_reason}] {reply}")
            return {"response": response_factory(reply=reply, status="suspicious_critical"), "lang": lang, "history": history}
        if severity == "high":
            reply = suspicious_response
            add_to_history_fn(phone, "user", user_message)
            add_to_history_fn(phone, "assistant", reply)
            save_message_fn(phone, user_message, f"[ŞÜPHELİ-YÜKSEK: {suspicion_reason}] {reply}")
            return {"response": response_factory(reply=reply, status="suspicious_high"), "lang": lang, "history": history}
        save_message_fn(phone, user_message, f"[ŞÜPHELİ-{severity.upper()}: {suspicion_reason}] - Normal işleme devam")

    is_critical, critical_category, critical_priority, critical_info = detect_critical_issue_fn(user_message)
    if is_critical and critical_priority >= 5:
        await send_critical_notification_fn(
            category=critical_category,
            priority=critical_priority,
            customer_phone=phone or "Bilinmiyor",
            customer_message=user_message,
        )
        auto_lang = detect_language_fn(user_message)
        auto_response = critical_info.get(f"auto_response_{auto_lang}") or critical_info.get("auto_response_tr")
        if auto_response:
            reply = auto_response
            add_to_history_fn(phone, "user", user_message)
            add_to_history_fn(phone, "assistant", reply)
            save_message_fn(phone, user_message, f"[KRİTİK-{critical_category.upper()}] {reply}")
            return {"response": response_factory(reply=reply, status=f"critical_{critical_category}"), "lang": lang, "history": history}
    elif is_critical:
        save_message_fn(phone, user_message, f"[KRİTİK-{critical_category.upper()}-P{critical_priority}] Normal işleme devam")

    return {"response": None, "lang": lang, "history": history}
