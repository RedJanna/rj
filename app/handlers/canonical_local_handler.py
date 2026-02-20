from __future__ import annotations

import time
from app.content.local_faq_data import CANONICAL_LOCAL_REPLIES_TR


def try_handle_canonical_and_local(
    *,
    user_message: str,
    phone: str,
    start_time: float,
    history: list,
    check_local_faq_fn,
    detect_language_fn,
    get_welcome_message_fn,
    add_to_history_fn,
    save_message_fn,
    schedule_followup_fn,
    record_metric_fn,
    response_factory,
    update_reservation_flow_fn,
    reservation_state_cls,
    canonical_greeting_keywords: list,
    kanonik_fiyat_exclusions: list,
    erken_giris_keywords: list,
    gec_cikis_keywords: list,
):
    low_msg = (user_message or "").strip().lower()

    greeting_keywords = canonical_greeting_keywords
    is_greeting_msg = any(low_msg.startswith(kw) or low_msg == kw for kw in greeting_keywords)
    if not is_greeting_msg:
        for kw in greeting_keywords:
            if kw in low_msg and len(low_msg) <= len(kw) + 3:
                is_greeting_msg = True
                break
    if is_greeting_msg:
        russian_greetings = ["привет", "здравствуйте", "здравствуй", "приветик", "доброе утро", "добрый день", "добрый вечер"]
        if any(kw in low_msg for kw in russian_greetings):
            lang = "ru"
        elif any(kw in low_msg for kw in ["hello", "hi", "hey", "hii", "hiii"]):
            lang = "en"
        else:
            lang = "tr"
        reply = get_welcome_message_fn(lang)
        add_to_history_fn(phone, "user", user_message)
        add_to_history_fn(phone, "assistant", reply)
        save_message_fn(phone, user_message, f"[KANONIK:selamlama] {reply}")
        schedule_followup_fn(phone)
        elapsed = time.time() - start_time
        record_metric_fn("local", category="kanonik_selamlama", response_time=elapsed)
        return response_factory(reply=reply, status="local_kanonik_selamlama")

    if ("rezerv" in low_msg) and any(k in low_msg for k in ["restoran", "yemek", "yemeği", "yemegi", "dinner", "akşam", "aksam"]):
        update_reservation_flow_fn(
            phone,
            reservation_state_cls.ASK_GUESTS.value,
            {"language": detect_language_fn(user_message)},
        )
        reply = "Restoran rezervasyonunuz için yardımcı olurum. 🍽️\n\nLütfen şu bilgileri yazın: kaç kişi, tarih, saat ve isim. (Örn: 2 kişi, 20 Ağustos, 20:00, Ali)"
        add_to_history_fn(phone, "user", user_message)
        add_to_history_fn(phone, "assistant", reply)
        save_message_fn(phone, user_message, f"[KANONIK:restoran_rezervasyon] {reply}")
        schedule_followup_fn(phone)
        elapsed = time.time() - start_time
        record_metric_fn("local", category="kanonik_restoran_rezervasyon", response_time=elapsed)
        return response_factory(reply=reply, status="local_kanonik_restoran_rezervasyon")

    payment_keywords = [
        "odeme yontem", "ödeme yöntem", "odeme", "ödeme",
        "kredi kart", "mail order", "havale", "eft", "payment method", "bank transfer",
    ]
    if any(k in low_msg for k in payment_keywords):
        lang = detect_language_fn(user_message)
        if lang == "en":
            reply = "You can pay via secure payment link (credit card), mail order form, or bank transfer."
        elif lang == "ru":
            reply = "Вы можете оплатить через безопасную ссылку (банковская карта), по форме mail order или банковским переводом."
        else:
            reply = "Ödeme için tercih edebileceğiniz yöntemler arasında kredi kartı ile ödeme linki, mail order formu veya havale/EFT bulunmaktadır."
        add_to_history_fn(phone, "user", user_message)
        add_to_history_fn(phone, "assistant", reply)
        save_message_fn(phone, user_message, f"[KANONIK:odeme_yontemi] {reply}")
        schedule_followup_fn(phone)
        elapsed = time.time() - start_time
        record_metric_fn("local", category="kanonik_odeme_yontemi", response_time=elapsed)
        return response_factory(reply=reply, status="local_kanonik_odeme_yontemi")

    _kanonik_fiyat_excluded = any(exc in low_msg for exc in kanonik_fiyat_exclusions)
    if not _kanonik_fiyat_excluded and ("fiyat" in low_msg or "ücret" in low_msg or "ucret" in low_msg) and ("oda" in low_msg or "room" in low_msg):
        reply = CANONICAL_LOCAL_REPLIES_TR["kanonik_fiyat"]
        add_to_history_fn(phone, "user", user_message)
        add_to_history_fn(phone, "assistant", reply)
        save_message_fn(phone, user_message, f"[KANONIK:fiyat_soru] {reply}")
        schedule_followup_fn(phone)
        elapsed = time.time() - start_time
        record_metric_fn("local", category="kanonik_fiyat", response_time=elapsed)
        return response_factory(reply=reply, status="local_kanonik_fiyat")

    if "kahvalt" in low_msg:
        reply = CANONICAL_LOCAL_REPLIES_TR["kanonik_kahvalti"]
        add_to_history_fn(phone, "user", user_message)
        add_to_history_fn(phone, "assistant", reply)
        save_message_fn(phone, user_message, f"[KANONIK:kahvalti] {reply}")
        schedule_followup_fn(phone)
        elapsed = time.time() - start_time
        record_metric_fn("local", category="kanonik_kahvalti", response_time=elapsed)
        return response_factory(reply=reply, status="local_kanonik_kahvalti")

    if ("wifi" in low_msg) or ("wi-fi" in low_msg) or ("internet" in low_msg):
        reply = CANONICAL_LOCAL_REPLIES_TR["kanonik_wifi"]
        add_to_history_fn(phone, "user", user_message)
        add_to_history_fn(phone, "assistant", reply)
        save_message_fn(phone, user_message, f"[KANONIK:wifi] {reply}")
        schedule_followup_fn(phone)
        elapsed = time.time() - start_time
        record_metric_fn("local", category="kanonik_wifi", response_time=elapsed)
        return response_factory(reply=reply, status="local_kanonik_wifi")

    if any(k in low_msg for k in erken_giris_keywords):
        reply = CANONICAL_LOCAL_REPLIES_TR["kanonik_erken_giris"]
        add_to_history_fn(phone, "user", user_message)
        add_to_history_fn(phone, "assistant", reply)
        save_message_fn(phone, user_message, f"[KANONIK:erken_giris] {reply}")
        schedule_followup_fn(phone)
        elapsed = time.time() - start_time
        record_metric_fn("local", category="kanonik_erken_giris", response_time=elapsed)
        return response_factory(reply=reply, status="local_kanonik_erken_giris")

    if any(k in low_msg for k in gec_cikis_keywords):
        reply = CANONICAL_LOCAL_REPLIES_TR["kanonik_gec_cikis"]
        add_to_history_fn(phone, "user", user_message)
        add_to_history_fn(phone, "assistant", reply)
        save_message_fn(phone, user_message, f"[KANONIK:gec_cikis] {reply}")
        schedule_followup_fn(phone)
        elapsed = time.time() - start_time
        record_metric_fn("local", category="kanonik_gec_cikis", response_time=elapsed)
        return response_factory(reply=reply, status="local_kanonik_gec_cikis")

    if "check" in low_msg:
        reply = CANONICAL_LOCAL_REPLIES_TR["kanonik_check"]
        add_to_history_fn(phone, "user", user_message)
        add_to_history_fn(phone, "assistant", reply)
        save_message_fn(phone, user_message, f"[KANONIK:check] {reply}")
        schedule_followup_fn(phone)
        elapsed = time.time() - start_time
        record_metric_fn("local", category="kanonik_check", response_time=elapsed)
        return response_factory(reply=reply, status="local_kanonik_check")

    if ("sezon" in low_msg) or (("otel" in low_msg) and ("ne zaman" in low_msg) and ("aç" in low_msg)):
        reply = CANONICAL_LOCAL_REPLIES_TR["kanonik_sezon"]
        add_to_history_fn(phone, "user", user_message)
        add_to_history_fn(phone, "assistant", reply)
        save_message_fn(phone, user_message, f"[KANONIK:sezon] {reply}")
        schedule_followup_fn(phone)
        elapsed = time.time() - start_time
        record_metric_fn("local", category="kanonik_sezon", response_time=elapsed)
        return response_factory(reply=reply, status="local_kanonik_sezon")

    if ("nerede" in low_msg) or ("adres" in low_msg) or ("konum" in low_msg) or ("location" in low_msg):
        reply = CANONICAL_LOCAL_REPLIES_TR["kanonik_konum"]
        add_to_history_fn(phone, "user", user_message)
        add_to_history_fn(phone, "assistant", reply)
        save_message_fn(phone, user_message, f"[KANONIK:konum] {reply}")
        schedule_followup_fn(phone)
        elapsed = time.time() - start_time
        record_metric_fn("local", category="kanonik_konum", response_time=elapsed)
        return response_factory(reply=reply, status="local_kanonik_konum")

    faq_found, faq_answer_tr, faq_answer_en, faq_category, faq_answer_ru = check_local_faq_fn(user_message)
    if faq_found:
        lang = detect_language_fn(user_message)
        if lang == "ru":
            reply = faq_answer_ru
        elif lang == "en":
            reply = faq_answer_en
        else:
            reply = faq_answer_tr
        if lang != "en" and lang != "ru":
            msgl = (user_message or "").lower()
            catl = (faq_category or "").lower()
            if ("kahvalt" in msgl) or ("kahvalt" in catl):
                reply = CANONICAL_LOCAL_REPLIES_TR["kanonik_kahvalti"]
            elif ("check" in msgl) or ("check" in catl):
                reply = CANONICAL_LOCAL_REPLIES_TR["kanonik_check"]
            elif ("wifi" in msgl) or ("wi-fi" in msgl) or ("internet" in msgl) or ("wifi" in catl):
                reply = CANONICAL_LOCAL_REPLIES_TR["kanonik_wifi"]
            elif ("otel" in msgl and "ne zaman" in msgl and "aç" in msgl) or ("sezon" in msgl) or ("sezon" in catl):
                reply = CANONICAL_LOCAL_REPLIES_TR["kanonik_sezon"]
            elif ("transfer" in msgl) or ("airport" in msgl) or ("havaliman" in msgl) or ("transfer" in catl):
                reply = CANONICAL_LOCAL_REPLIES_TR["kanonik_transfer"]
            elif ("havuz" in msgl) or ("havuz" in catl):
                reply = CANONICAL_LOCAL_REPLIES_TR["kanonik_havuz"]
            elif ("nerede" in msgl) or ("adres" in msgl) or ("konum" in catl):
                reply = CANONICAL_LOCAL_REPLIES_TR["kanonik_konum"]

        add_to_history_fn(phone, "user", user_message)
        add_to_history_fn(phone, "assistant", reply)
        save_message_fn(phone, user_message, f"[LOCAL-FAQ:{faq_category}] {reply}")
        schedule_followup_fn(phone)
        elapsed = time.time() - start_time
        record_metric_fn("local", category=faq_category, response_time=elapsed)
        print(f"✅ LOCAL FAQ cevaplandı: {faq_category} (API çağrısı YOK)")
        return response_factory(reply=reply, status=f"local_faq_{faq_category}")

    low_msg = (user_message or "").lower()
    if any(k in low_msg for k in [
        "oda ayırt", "oda ayirt", "müsait", "musait", "müsaitlik", "musaitlik",
        "konakla", "gece", "book", "booking", "room", "reservation",
    ]):
        reply = CANONICAL_LOCAL_REPLIES_TR["local_otel_rezervasyon"]
        add_to_history_fn(phone, "user", user_message)
        add_to_history_fn(phone, "assistant", reply)
        save_message_fn(phone, user_message, f"[LOCAL-REZERVASYON] {reply}")
        schedule_followup_fn(phone)
        elapsed = time.time() - start_time
        record_metric_fn("local", category="otel_rezervasyon", response_time=elapsed)
        return response_factory(reply=reply, status="local_otel_rezervasyon")

    if "kahvalt" in low_msg:
        reply = CANONICAL_LOCAL_REPLIES_TR["kanonik_kahvalti"]
        add_to_history_fn(phone, "user", user_message)
        add_to_history_fn(phone, "assistant", reply)
        save_message_fn(phone, user_message, f"[LOCAL-KANONIK:kahvalti] {reply}")
        schedule_followup_fn(phone)
        elapsed = time.time() - start_time
        record_metric_fn("local", category="kanonik_kahvalti", response_time=elapsed)
        return response_factory(reply=reply, status="local_kanonik_kahvalti")

    if ("wifi" in low_msg) or ("wi-fi" in low_msg) or ("internet" in low_msg):
        reply = CANONICAL_LOCAL_REPLIES_TR["kanonik_wifi"]
        add_to_history_fn(phone, "user", user_message)
        add_to_history_fn(phone, "assistant", reply)
        save_message_fn(phone, user_message, f"[LOCAL-KANONIK:wifi] {reply}")
        schedule_followup_fn(phone)
        elapsed = time.time() - start_time
        record_metric_fn("local", category="kanonik_wifi", response_time=elapsed)
        return response_factory(reply=reply, status="local_kanonik_wifi")

    if "check" in low_msg:
        reply = CANONICAL_LOCAL_REPLIES_TR["kanonik_check"]
        add_to_history_fn(phone, "user", user_message)
        add_to_history_fn(phone, "assistant", reply)
        save_message_fn(phone, user_message, f"[LOCAL-KANONIK:check] {reply}")
        schedule_followup_fn(phone)
        elapsed = time.time() - start_time
        record_metric_fn("local", category="kanonik_check", response_time=elapsed)
        return response_factory(reply=reply, status="local_kanonik_check")

    if ("sezon" in low_msg) or (("otel" in low_msg) and ("ne zaman" in low_msg) and ("aç" in low_msg)):
        reply = CANONICAL_LOCAL_REPLIES_TR["kanonik_sezon"]
        add_to_history_fn(phone, "user", user_message)
        add_to_history_fn(phone, "assistant", reply)
        save_message_fn(phone, user_message, f"[LOCAL-KANONIK:sezon] {reply}")
        schedule_followup_fn(phone)
        elapsed = time.time() - start_time
        record_metric_fn("local", category="kanonik_sezon", response_time=elapsed)
        return response_factory(reply=reply, status="local_kanonik_sezon")

    if ("nerede" in low_msg) or ("adres" in low_msg) or ("konum" in low_msg) or ("location" in low_msg):
        reply = CANONICAL_LOCAL_REPLIES_TR["kanonik_konum"]
        add_to_history_fn(phone, "user", user_message)
        add_to_history_fn(phone, "assistant", reply)
        save_message_fn(phone, user_message, f"[LOCAL-KANONIK:konum] {reply}")
        schedule_followup_fn(phone)
        elapsed = time.time() - start_time
        record_metric_fn("local", category="kanonik_konum", response_time=elapsed)
        return response_factory(reply=reply, status="local_kanonik_konum")

    if ("spa" in low_msg) or ("masaj" in low_msg) or ("massage" in low_msg):
        reply = CANONICAL_LOCAL_REPLIES_TR["local_olanak_spa"]
        add_to_history_fn(phone, "user", user_message)
        add_to_history_fn(phone, "assistant", reply)
        save_message_fn(phone, user_message, f"[LOCAL-OLANAK] {reply}")
        schedule_followup_fn(phone)
        elapsed = time.time() - start_time
        record_metric_fn("local", category="olanak_spa", response_time=elapsed)
        return response_factory(reply=reply, status="local_olanak_spa")

    return None
