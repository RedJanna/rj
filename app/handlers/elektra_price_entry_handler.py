from __future__ import annotations

import os
import re

LANG_MESSAGES = {
    "tr": {
        "handoff": "Talebinizi aldik, ekibimiz en kisa surede sizinle iletisime gececektir.",
        "config_error": "Şu anda fiyat/ücret sistemine bağlanamıyorum (eksik ayar). Lütfen biraz sonra tekrar deneyin.",
        "runtime_error": "Şu anda fiyat/ücret bilgisine erişemedim. Lütfen tekrar deneyin.",
        "price_prefix": "Fiyat bilgisi için yardımcı olabilirim. ",
        "guest_count_prompts": ("kisilik konaklama", "kac kisilik"),
    },
    "en": {
        "handoff": "We received your request, our team will contact you shortly.",
        "config_error": "I cannot connect to the pricing system at the moment (missing configuration). Please try again shortly.",
        "runtime_error": "I couldn't access pricing information right now. Please try again.",
        "price_prefix": "I can help with pricing information. ",
        "guest_count_prompts": ("how many guests", "number of guests"),
    },
    "ru": {
        "handoff": "Мы получили ваш запрос, наша команда свяжется с вами в ближайшее время.",
        "config_error": "Сейчас не удаётся подключиться к системе цен (неполная настройка). Пожалуйста, попробуйте позже.",
        "runtime_error": "Сейчас не удалось получить информацию о ценах. Пожалуйста, попробуйте снова.",
        "price_prefix": "Я могу помочь с информацией по ценам. ",
        "guest_count_prompts": ("сколько гостей", "количество гостей"),
    },
}


async def try_handle_elektra_price_entry(
    *,
    phone: str,
    user_message: str,
    history: list,
    detect_price_request_fn,
    is_price_flow_active_fn,
    detect_language_fn,
    handle_elektra_price_request_fn,
    notify_admin_handoff_fn,
    add_to_history_fn,
    save_message_fn,
    schedule_followup_fn,
    response_factory,
    notify_admin_error_fn,
    eleltra_config_error_cls,
    natural_date_keywords: list,
    price_inquiry_keywords: list,
    guest_keywords: list,
):
    def _lang_pack(lang_code: str) -> dict:
        return LANG_MESSAGES.get((lang_code or "tr").lower(), LANG_MESSAGES["tr"])

    iso_dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", user_message or "")
    low_um = (user_message or "").lower()
    has_natural_date = any(kw in low_um for kw in natural_date_keywords)
    is_price_inquiry = any(kw in low_um for kw in price_inquiry_keywords)
    has_guest_info = any(kw in low_um for kw in guest_keywords)

    user_message_with_dates = user_message
    # Mesajda tarih var ama misafir bilgisi yoksa, son mesajlardan misafir bilgisini ekle.
    if has_natural_date and not has_guest_info:
        for msg in reversed(history[-10:]):
            msg_content = (msg.get("content") or "").lower()
            if any(kw in msg_content for kw in guest_keywords):
                user_message_with_dates = msg.get("content", "") + " " + user_message
                has_guest_info = True
                print(f"👥 History'den misafir bilgisi bulundu: {msg.get('content', '')[:50]}...")
                break

    if has_guest_info and not has_natural_date and len(iso_dates) < 2:
        for msg in reversed(history[-10:]):
            msg_content = (msg.get("content") or "").lower()
            for kw in natural_date_keywords:
                if kw in msg_content:
                    user_message_with_dates = msg.get("content", "") + " " + user_message
                    has_natural_date = True
                    print(f"📅 History'den tarih bulundu: {msg.get('content', '')[:50]}...")
                    break
            if has_natural_date:
                break

    looks_like_price_payload = ((len(iso_dates) >= 2 or has_natural_date) and (has_guest_info or is_price_inquiry))
    natural_price_request = has_natural_date and is_price_inquiry

    if is_price_flow_active_fn(phone):
        return None

    if not (detect_price_request_fn(user_message, history) or looks_like_price_payload or natural_price_request):
        return None

    print(f"💰 ELEKTRA PRICE FLOW TRIGGERED | looks_like_payload={looks_like_price_payload} | has_natural_date={has_natural_date}")
    customer_lang = detect_language_fn(user_message) or "tr"
    msg = _lang_pack(customer_lang)
    hotel_id = (os.getenv("ELEKTRA_HOTEL_ID") or "21966").strip()

    try:
        message_for_price = user_message_with_dates if user_message_with_dates != user_message else user_message
        reply, log, _raw_offers = await handle_elektra_price_request_fn(
            message_for_price,
            hotel_id=hotel_id,
            lang=customer_lang,
        )
        if reply.startswith("HANDOFF:"):
            error_type = reply.replace("HANDOFF:", "")
            await notify_admin_handoff_fn(
                "fiyat_sistemi_hatasi",
                "high",
                phone,
                f"Fiyat sistemi hatasi: {error_type}\nMesaj: {user_message[:200]}",
            )
            reply = msg["handoff"]
            add_to_history_fn(phone, "user", user_message)
            add_to_history_fn(phone, "assistant", reply)
            save_message_fn(phone, user_message, reply)
            return response_factory(reply=reply, status="handoff")
    except eleltra_config_error_cls as e:
        reply = msg["config_error"]
        log = f"Elektra config error: {str(e)[:2000]}"
        await notify_admin_error_fn(
            error_type="ELEKTRA_CONFIG",
            customer_phone=phone,
            customer_message=user_message,
            error_details=log,
        )
    except Exception as e:
        reply = msg["runtime_error"]
        log = f"Elektra runtime error: {type(e).__name__}: {str(e)[:2000]}"
        await notify_admin_error_fn(
            error_type="ELEKTRA_RUNTIME",
            customer_phone=phone,
            customer_message=user_message,
            error_details=log,
        )

    low_reply = (reply or "").lower()
    guest_count_prompts = msg.get("guest_count_prompts", ())
    if not any(prompt in low_reply for prompt in guest_count_prompts):
        if msg["price_prefix"].lower() not in low_reply:
            reply = msg["price_prefix"] + (reply or "")
    add_to_history_fn(phone, "user", user_message)
    add_to_history_fn(phone, "assistant", reply)
    save_message_fn(phone, user_message, reply, is_price_template=True)
    schedule_followup_fn(phone)
    return response_factory(reply=reply, reservation_log=log, is_price_template=True, status="ok")
