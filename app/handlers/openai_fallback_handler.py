from __future__ import annotations

import time


async def handle_openai_fallback(
    *,
    client,
    openai_model: str,
    info_system_prompt: str,
    history: list,
    user_message: str,
    phone: str,
    start_time: float,
    add_to_history_fn,
    save_message_fn,
    schedule_followup_fn,
    record_metric_fn,
    maybe_start_qa_background_fn,
    qa_enabled: bool,
    qa_agent,
    admin_phone: str,
    send_whatsapp_message_fn,
    qa_fail_notifications: list,
    record_error_fn,
    response_factory,
):
    try:
        messages = [{"role": "system", "content": info_system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})
        completion = client.chat.completions.create(
            model=openai_model,
            messages=messages,
            temperature=0.3,
            max_tokens=500,
        )
        reply = completion.choices[0].message.content.strip()
        add_to_history_fn(phone, "user", user_message)
        add_to_history_fn(phone, "assistant", reply)
        save_message_fn(phone, user_message, reply)
        schedule_followup_fn(phone)
        elapsed = time.time() - start_time
        record_metric_fn("openai", category="general", response_time=elapsed)
        maybe_start_qa_background_fn(
            qa_enabled=qa_enabled,
            qa_agent=qa_agent,
            user_message=user_message,
            reply=reply,
            phone=phone,
            admin_phone=admin_phone,
            send_whatsapp_message_fn=send_whatsapp_message_fn,
            qa_fail_notifications=qa_fail_notifications,
        )
        return response_factory(reply=reply, status="ok")
    except Exception as e:
        error_msg = str(e)
        error_type = type(e).__name__
        print(f"❌ CHAT HATASI [{error_type}]: {error_msg}")
        record_error_fn("chat_error", f"{error_type}: {error_msg}")
        elapsed = time.time() - start_time
        record_metric_fn("error", category=f"chat_{error_type}", response_time=elapsed)
        try:
            admin_alert = f"""🔴 TEKNİK HATA
⏱️ Süre: {elapsed:.1f}s
📱 Telefon: {phone or 'Bilinmiyor'}
❌ Hata Tipi: {error_type}
❌ Hata: {error_msg[:300]}
💬 Mesaj:
{user_message[:150] if user_message else 'Bilinmiyor'}"""
            await send_whatsapp_message_fn(admin_phone, admin_alert)
        except Exception as notify_err:
            print(f"Admin bildirim hatası: {notify_err}")
        save_message_fn(phone, user_message, f"[HATA - {error_type}] {error_msg[:100]}")
        try:
            from app.utils.message_utils import detect_language as _detect_lang
            _err_lang = _detect_lang(user_message) if user_message else "tr"
            if _err_lang == "ru":
                apology_msg = "Произошла техническая ошибка. Пожалуйста, попробуйте позже или позвоните нам: +90 533 250 32 77"
            elif _err_lang == "en":
                apology_msg = "A technical error occurred. Please try again later or call us: +90 533 250 32 77"
            else:
                apology_msg = "Teknik bir sorun oluştu. Lütfen biraz sonra tekrar deneyin veya bizi arayın: +90 533 250 32 77"
            await send_whatsapp_message_fn(phone, apology_msg)
        except Exception:
            pass
        print(f"⚠️ Admin'e bildirim gönderildi: {error_type}")
        return response_factory(reply="", status="error")
