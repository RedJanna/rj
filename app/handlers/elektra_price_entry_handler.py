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
    "de": {
        "handoff": "Wir haben Ihre Anfrage erhalten, unser Team meldet sich in Kürze bei Ihnen.",
        "config_error": "Ich kann das Preissystem derzeit nicht erreichen (fehlende Konfiguration). Bitte versuchen Sie es später erneut.",
        "runtime_error": "Ich konnte die Preisinformationen gerade nicht abrufen. Bitte versuchen Sie es erneut.",
        "price_prefix": "Ich kann Ihnen bei der Preisermittlung helfen. ",
        "guest_count_prompts": ("wie viele gäste", "anzahl der gäste"),
    },
    "es": {
        "handoff": "Hemos recibido su solicitud, nuestro equipo se pondrá en contacto con usted en breve.",
        "config_error": "No puedo conectarme al sistema de precios en este momento (configuración incompleta). Inténtelo de nuevo más tarde.",
        "runtime_error": "No pude acceder a la información de precios ahora mismo. Inténtelo de nuevo.",
        "price_prefix": "Puedo ayudarte con la información de precios. ",
        "guest_count_prompts": ("cuántos huéspedes", "numero de huéspedes", "cuantos huespedes"),
    },
    "fr": {
        "handoff": "Nous avons bien reçu votre demande, notre équipe vous contactera dans les plus brefs délais.",
        "config_error": "Je ne peux pas me connecter au système tarifaire pour le moment (configuration incomplète). Veuillez réessayer plus tard.",
        "runtime_error": "Je n'ai pas pu accéder aux tarifs pour le moment. Veuillez réessayer.",
        "price_prefix": "Je peux vous aider avec les informations tarifaires. ",
        "guest_count_prompts": ("combien de clients", "nombre de clients"),
    },
    "pt": {
        "handoff": "Recebemos sua solicitação, nossa equipe entrará em contato em breve.",
        "config_error": "Não consigo conectar ao sistema de preços no momento (configuração ausente). Tente novamente em breve.",
        "runtime_error": "Não consegui acessar as informações de preço agora. Tente novamente.",
        "price_prefix": "Posso ajudar com informações de preços. ",
        "guest_count_prompts": ("quantos hóspedes", "numero de hospedes"),
    },
    "ar": {
        "handoff": "تم استلام طلبك، وسيتواصل معك فريقنا قريبًا.",
        "config_error": "لا يمكنني الاتصال بنظام الأسعار حاليًا (إعدادات ناقصة). يرجى المحاولة لاحقًا.",
        "runtime_error": "تعذر الوصول إلى معلومات الأسعار الآن. يرجى المحاولة مرة أخرى.",
        "price_prefix": "يمكنني مساعدتك بمعلومات الأسعار. ",
        "guest_count_prompts": ("كم عدد الضيوف",),
    },
    "zh": {
        "handoff": "我们已收到您的请求，我们的团队将尽快与您联系。",
        "config_error": "目前无法连接到价格系统（配置缺失），请稍后重试。",
        "runtime_error": "暂时无法获取价格信息，请稍后再试。",
        "price_prefix": "我可以为您提供价格信息。 ",
        "guest_count_prompts": ("几位客人", "客人人数"),
    },
    "hi": {
        "handoff": "हमने आपका अनुरोध प्राप्त कर लिया है, हमारी टीम जल्द ही आपसे संपर्क करेगी।",
        "config_error": "मैं इस समय प्राइसिंग सिस्टम से कनेक्ट नहीं कर पा रहा हूँ (कॉन्फ़िगरेशन अधूरा है)। कृपया बाद में पुनः प्रयास करें।",
        "runtime_error": "मैं अभी मूल्य जानकारी प्राप्त नहीं कर पाया। कृपया फिर से कोशिश करें।",
        "price_prefix": "मैं मूल्य जानकारी में आपकी मदद कर सकता हूँ। ",
        "guest_count_prompts": ("कितने मेहमान",),
    },
}


def _resolve_customer_lang(user_message: str, detected_lang: str, locked_lang: str = "") -> str:
    forced = (locked_lang or "").strip().lower()
    if forced in LANG_MESSAGES:
        return forced

    text = (user_message or "").strip()
    low = text.lower()

    if re.search(r"[а-яёА-ЯЁ]", text):
        return "ru"
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh"
    if re.search(r"[\u0600-\u06FF]", text):
        return "ar"
    if re.search(r"[\u0900-\u097F]", text):
        return "hi"

    lang_signals = {
        "de": [" bitte ", " preis", " erwachsene", " storn", " rück", " rueck", " vom ", " bis "],
        "es": ["¿", "¡", " precio", " adultos", " cancelación", " cancelacion", " reembols", " agosto", " puede "],
        "fr": [" prix", " adultes", " annulation", " rembours", " août", " pouvez", " veuillez"],
        "pt": [" preço", " preco", " hóspedes", " hospedes", " cancelamento", " reembols", " agosto", " pode "],
        "tr": [" fiyat", " ücret", " ucret", " yetişkin", " yetiskin", " ağustos", " agustos", " rezervasyon"],
    }

    scores: dict[str, int] = {}
    padded = f" {low} "
    for code, markers in lang_signals.items():
        score = 0
        for marker in markers:
            if marker in padded:
                score += 1
        scores[code] = score

    best_lang = max(scores, key=scores.get)
    if scores.get(best_lang, 0) >= 2:
        return best_lang

    lang = (detected_lang or "en").lower()
    return lang if lang in LANG_MESSAGES else "en"


def _is_policy_or_info_question(text: str) -> bool:
    """
    Oda fiyat sorgusu olmayan politika/bilgi sorularinda Elektra girisini atla.
    Bu guard, tarih/kişi içeren eski history ile alakasız "Missing: ..." yanıtlarını önler.
    """
    low = (text or "").lower()
    if not low:
        return False

    breakfast_policy = (
        ("kahvaltı" in low or "kahvalti" in low or "breakfast" in low)
        and any(
            k in low
            for k in (
                "dahil mi", "dahil", "included",
                "ek ücret", "ek ucret", "extra charge", "additional charge",
                "kişi başı", "kisi basi", "per person",
            )
        )
    )
    if breakfast_policy:
        return True

    policy_markers = (
        # child policy / ek yatak / check-in-out / payment-policy
        "child policy", "kids policy", "infant policy",
        "çocuk politika", "cocuk politika", "çocuk kural", "cocuk kural",
        "does the child pay", "discounted rate", "full price",
        "extra bed", "ek yatak", "nightly fee", "gecelik ucret", "gecelik ücret",
        "check-in", "check in", "check-out", "check out",
        "erken giriş", "erken giris", "geç çıkış", "gec cikis",
        "payment method", "ödeme yöntemi", "odeme yontemi",
        "deposit", "depozito", "kapora",
        "reservation code", "rezervasyon kodu", "teyit mesaji", "teyit mesajı",
        # cancellation-policy / refundable-nonrefundable (fiyat sorgusu degil)
        "cancellation policy", "cancellation rule", "cancellation rules",
        "refund policy", "refund rule", "refund rules",
        "refundable", "non-refundable", "non refundable",
        "cancelacion", "cancelación", "reembolso", "reglas de cancel",
        "annulation", "remboursement",
        "stornierung", "ruckerstattung", "rückerstattung",
        "cancelamento", "reembolso",
        "отмена", "возврат", "правила отмены",
        "إلغاء", "استرداد",
        "取消", "退款",
        "रद्द", "रिफंड",
    )
    return any(k in low for k in policy_markers)


def _iter_user_history_texts(history: list) -> list[str]:
    out: list[str] = []
    for row in history[-10:]:
        item = row or {}
        role = str(item.get("role") or "").strip().lower()
        if role and role != "user":
            continue
        if role == "user":
            content = str(item.get("content") or "").strip()
            if content:
                out.append(content.lower())
            continue
        legacy_user = str(item.get("user_message") or "").strip()
        if legacy_user:
            out.append(legacy_user.lower())
    return out


def _is_room_suitability_query_without_explicit_date(text: str, natural_date_keywords: list) -> bool:
    low = (text or "").lower()
    if not low:
        return False
    has_room = any(k in low for k in ("room", "oda"))
    has_suitability = any(k in low for k in ("suitable", "uygun", "room for"))
    has_guest_mix = bool(
        re.search(r"\d+\s*(adult|adults|yeti[şs]kin|child|children|kids?|çocuk|cocuk|kişi|kisi)", low)
    )
    has_explicit_date = bool(re.search(r"\b\d{4}-\d{2}-\d{2}\b", low)) or any(
        kw in low for kw in (natural_date_keywords or [])
    )
    return has_room and has_suitability and has_guest_mix and not has_explicit_date


async def try_handle_elektra_price_entry(
    *,
    phone: str,
    user_message: str,
    history: list,
    locked_lang: str = "",
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
        return LANG_MESSAGES.get((lang_code or "en").lower(), LANG_MESSAGES["en"])

    # ÖNEMLİ: Aktif transfer konuşması varsa price flow tetiklenmemeli
    from app.utils.message_utils import _is_transfer_conversation_active, looks_like_transfer_message
    if _is_transfer_conversation_active(history):
        print("🚫 elektra_price_entry: Aktif transfer konuşması tespit edildi, price flow atlanıyor")
        return None
    if looks_like_transfer_message(user_message):
        print("🚫 elektra_price_entry: Transfer detay mesajı tespit edildi, price flow atlanıyor")
        return None

    iso_dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", user_message or "")
    low_um = (user_message or "").lower()

    if _is_policy_or_info_question(user_message):
        print("🚫 elektra_price_entry: politika/bilgi sorusu tespit edildi, Elektra sorgusu atlanıyor")
        return None

    has_natural_date = any(kw in low_um for kw in natural_date_keywords)
    is_price_inquiry = any(kw in low_um for kw in price_inquiry_keywords)
    has_guest_info = any(kw in low_um for kw in guest_keywords)

    user_message_with_dates = user_message
    # Mesajda tarih var ama misafir bilgisi yoksa, son mesajlardan misafir bilgisini ekle.
    if has_natural_date and not has_guest_info:
        for msg_content in reversed(_iter_user_history_texts(history)):
            if any(kw in msg_content for kw in guest_keywords):
                user_message_with_dates = msg_content + " " + user_message
                has_guest_info = True
                print(f"👥 History'den misafir bilgisi bulundu: {msg_content[:50]}...")
                break

    force_fresh_date_prompt = _is_room_suitability_query_without_explicit_date(user_message, natural_date_keywords)
    if has_guest_info and not has_natural_date and len(iso_dates) < 2:
        if force_fresh_date_prompt:
            print("ℹ️ Elektra price entry: suitability query detected, asking date explicitly.")
        else:
            for msg_content in reversed(_iter_user_history_texts(history)):
                for kw in natural_date_keywords:
                    if kw in msg_content:
                        user_message_with_dates = msg_content + " " + user_message
                        has_natural_date = True
                        print(f"📅 History'den tarih bulundu: {msg_content[:50]}...")
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
    customer_lang = _resolve_customer_lang(
        user_message,
        detect_language_fn(user_message),
        locked_lang=locked_lang,
    )
    msg = _lang_pack(customer_lang)
    hotel_id = (os.getenv("ELEKTRA_HOTEL_ID") or "21966").strip()

    is_price_result = False

    try:
        message_for_price = user_message_with_dates if user_message_with_dates != user_message else user_message
        reply, log, _raw_offers = await handle_elektra_price_request_fn(
            message_for_price,
            hotel_id=hotel_id,
            lang=customer_lang,
        )
        is_price_result = bool(_raw_offers)
        # Basarili fiyat sorgusunda ham offer'lari booking flow icin cache'le.
        if _raw_offers:
            try:
                from app.services.booking_flow_service import save_price_offers
                save_price_offers(phone, _raw_offers, {
                    "hotel_id": hotel_id,
                    "lang": customer_lang,
                })
            except Exception as cache_err:
                print(f"[BOOKING] Offer cache error (elektra entry): {cache_err}")
        if reply.startswith("HANDOFF:"):
            error_type = reply.replace("HANDOFF:", "")
            await notify_admin_handoff_fn(
                category="fiyat_sistemi_hatasi",
                priority="high",
                customer_phone=phone,
                customer_message=f"Fiyat sistemi hatasi: {error_type}\nMesaj: {user_message[:200]}",
                source="elektra_price_entry_handler",
                detected_intent="PRICE_QUERY",
                confidence=0.9,
                conversation_summary=f"Elektra HANDOFF error_type={error_type}",
                attempted_actions=["handle_elektra_price_request"],
                suggested_reply=msg["handoff"],
                tags=["price_flow", "elektra_error", "handoff"],
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
    normalized_prefix = (msg.get("price_prefix", "") or "").strip().lower()
    if not any(prompt in low_reply for prompt in guest_count_prompts):
        if normalized_prefix and normalized_prefix not in low_reply:
            reply = msg["price_prefix"] + (reply or "")
    add_to_history_fn(phone, "user", user_message)
    add_to_history_fn(phone, "assistant", reply)
    save_message_fn(phone, user_message, reply, is_price_template=is_price_result)
    schedule_followup_fn(phone)
    return response_factory(
        reply=reply,
        reservation_log=log,
        is_price_template=is_price_result,
        status="price_result" if is_price_result else "price_flow",
    )
