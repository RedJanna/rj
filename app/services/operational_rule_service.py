from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.content.automation_info import AUTOMATION_RUNTIME_RULES, get_runtime_text

_OPERATIONAL_LANG_TEXTS: Dict[str, Dict[str, str]] = {
    "rez_id_info": {
        "tr": "Rezervasyon numarası, konfirmasyon formunda yer alan kimlik bilgisidir. Elektra ekranında bu bilgi Voucher No olarak da görünebilir.",
        "en": "Your reservation number is shown on the confirmation form. In Elektra, the same reference may also appear as Voucher No.",
        "ru": "Номер бронирования указан в форме подтверждения. В системе Elektra этот же номер может отображаться как Voucher No.",
        "de": "Ihre Reservierungsnummer steht auf dem Bestätigungsformular. In Elektra kann diese Referenz auch als Voucher-Nummer erscheinen.",
        "es": "Su número de reserva aparece en el formulario de confirmación. En Elektra, esta referencia también puede verse como Voucher No.",
        "fr": "Votre numéro de réservation figure sur le formulaire de confirmation. Dans Elektra, cette référence peut aussi apparaître comme Voucher No.",
        "pt": "O número da sua reserva aparece no formulário de confirmação. No Elektra, essa referência também pode aparecer como Voucher No.",
        "ar": "رقم الحجز يظهر في نموذج التأكيد. وفي نظام Elektra قد يظهر المرجع نفسه باسم Voucher No.",
        "zh": "您的预订编号会显示在确认单中。在 Elektra 系统里，同一编号也可能显示为 Voucher No。",
        "hi": "आपका reservation number कन्फर्मेशन फॉर्म पर लिखा होता है। Elektra में यही संदर्भ Voucher No के रूप में भी दिख सकता है।",
    },
    "booking_confirmation_info": {
        "tr": "Rezervasyon kesinleştikten sonra sizlere rezervasyon kodu ve teyit mesajı paylaşılacaktır.",
        "en": "After your reservation is finalized, we will share your booking code and confirmation message.",
        "ru": "После подтверждения бронирования мы отправим вам код бронирования и сообщение-подтверждение.",
        "de": "Nach der finalen Bestätigung Ihrer Reservierung senden wir Ihnen den Buchungscode und die Bestätigungsnachricht.",
        "es": "Una vez confirmada su reserva, le compartiremos el código de reserva y el mensaje de confirmación.",
        "fr": "Une fois votre réservation confirmée, nous vous enverrons le code de réservation et le message de confirmation.",
        "pt": "Após a confirmação final da reserva, compartilharemos com você o código da reserva e a mensagem de confirmação.",
        "ar": "بعد تأكيد الحجز بشكل نهائي، سنشارك معكم رمز الحجز ورسالة التأكيد.",
        "zh": "预订确认后，我们会向您发送预订编号和确认信息。",
        "hi": "आपकी बुकिंग कन्फर्म होने के बाद हम आपके साथ बुकिंग कोड और कन्फर्मेशन संदेश साझा करेंगे।",
    },
}


def _tr_lower(text: str) -> str:
    return (text or "").replace("İ", "i").replace("I", "ı").lower()


def _lang_text(key: str, lang: str) -> str:
    lang_norm = (lang or "en").strip().lower()
    bucket = _OPERATIONAL_LANG_TEXTS.get(key, {})
    return bucket.get(lang_norm) or bucket.get("en") or ""


def _iter_messages(history: List[Dict[str, Any]]) -> List[tuple[str, str]]:
    """
    Normalize message rows from both formats:
    1) {"role": "...", "content": "..."}
    2) {"user_message": "...", "bot_reply": "..."}
    """
    out: List[tuple[str, str]] = []
    for item in history or []:
        row = item or {}
        role = str(row.get("role") or "").strip().lower()
        if role in {"user", "assistant"}:
            content = str(row.get("content") or "").strip()
            if content:
                out.append((role, content))
            continue
        user_msg = str(row.get("user_message") or "").strip()
        bot_msg = str(row.get("bot_reply") or "").strip()
        if user_msg:
            out.append(("user", user_msg))
        if bot_msg:
            out.append(("assistant", bot_msg))
    return out


def _last_assistant(history: List[Dict[str, Any]]) -> str:
    for role, content in reversed(_iter_messages(history)):
        if role == "assistant":
            return content
    return ""


def _is_yes(text: str) -> bool:
    t = _tr_lower(text).strip()
    return t in {"evet", "tamam", "onay", "onaylıyorum", "onayliyorum", "ok", "yes"}


def _extract_rez_id_token(msg: str) -> str:
    """
    Mesajdan Rez ID benzeri kimligi yakala.
    Destek:
    - "rez id 12345"
    - "rezervasyon id: 12345"
    - "#12345"
    - "CTX-ABCDEFG"
    """
    patterns = [
        r"\brez(?:ervasyon)?\s*id\s*[:#]?\s*([a-z0-9\-.]{4,})\b",
        r"\brez(?:ervasyon)?\s*no\s*[:#]?\s*([a-z0-9\-.]{4,})\b",
        r"\bvoucher\s*no\s*[:#]?\s*([a-z0-9\-.]{4,})\b",
        r"\bvoucher\s*number\s*[:#]?\s*([a-z0-9\-.]{4,})\b",
        r"\b(ctx-[a-z0-9]{6,})\b",
        r"#\s*([0-9][0-9\.]{3,})\b",
    ]
    for pat in patterns:
        m = re.search(pat, msg, flags=re.IGNORECASE)
        if m:
            return (m.group(1) or "").strip()
    return ""


def _extract_rate_type(msg: str) -> str:
    text = _tr_lower(msg)
    stripped = text.strip()
    if stripped in {"1", "1.", "1-", "1)"}:
        return "iptal_edilemez"
    if stripped in {"2", "2.", "2-", "2)"}:
        return "ucretsiz_iptal"

    if any(
        phrase in text
        for phrase in (
            "iptal edilemez",
            "non-refundable",
            "non refundable",
            "iade edilmez",
        )
    ):
        return "iptal_edilemez"
    if any(
        phrase in text
        for phrase in (
            "ücretsiz iptal",
            "ucretsiz iptal",
            "free cancellation",
            "free cancel",
            "refundable",
        )
    ):
        return "ucretsiz_iptal"

    if re.search(r"\b(fiyat tipi|kosul|koşul|rate type)\s*[:\-]?\s*1\b", text):
        return "iptal_edilemez"
    if re.search(r"\b(fiyat tipi|kosul|koşul|rate type)\s*[:\-]?\s*2\b", text):
        return "ucretsiz_iptal"
    # "Rez ID 12345, 1" gibi kısa seçim cevapları.
    short_token = re.search(r"(?:^|[,;:\-\s])([12])(?:\s*$|\s*(?:\)|\.|,|;))", text)
    if short_token:
        return "iptal_edilemez" if short_token.group(1) == "1" else "ucretsiz_iptal"
    return ""


def _extract_full_name(msg: str) -> str:
    text = (msg or "").strip()
    if not text:
        return ""
    patterns = [
        r"\b(?:ad[\s\-]*soyad(?:[ıi]n?[ıi]z)?|isim(?:\s*soyisim)?)\s*[:\-]?\s*([a-zA-ZçğıöşüÇĞİÖŞÜ'\.\-\s]{3,60})",
        r"\b(?:name|full name)\s*[:\-]?\s*([a-zA-Z'\.\-\s]{3,60})",
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            candidate = re.sub(r"\s+", " ", (m.group(1) or "").strip())
            if len(candidate.split()) >= 2:
                return candidate
    return ""


def _extract_latest_user_slot(history: List[Dict[str, Any]], extractor) -> str:
    for role, content in reversed(_iter_messages(history)):
        if role != "user":
            continue
        value = extractor(content)
        if value:
            return value
    return ""


def _is_cancel_policy_question(msg_ascii: str) -> bool:
    has_cancel_term = any(k in msg_ascii for k in ["iptal", "cancellation", "refund", "iade"])
    if not has_cancel_term:
        return False
    info_markers = [
        "kosul",
        "koşul",
        "kural",
        "politika",
        "policy",
        "nedir",
        "nasil",
        "nasil",
        "detay",
        "bilgi",
        "var mi",
        "var mı",
    ]
    return any(marker in msg_ascii for marker in info_markers)


def _is_hotel_cancel_request(msg_ascii: str) -> bool:
    if _is_cancel_policy_question(msg_ascii):
        return False
    if any(k in msg_ascii for k in ["restoran", "restaurant", "transfer", "tur ", "tour", "masa"]):
        return False
    triggers = AUTOMATION_RUNTIME_RULES.get("hotel_cancel_v1", {}).get("trigger_keywords", [])
    return any(str(trigger).lower() in msg_ascii for trigger in triggers)


def _is_waiting_hotel_cancel_slots(last_bot: str) -> bool:
    text = _tr_lower(last_bot)
    has_reference = (
        ("rezervasyon / voucher" in text)
        or ("rezervasyon/voucher" in text)
        or ("reservation / voucher" in text)
        or ("reservation/voucher" in text)
        or ("voucher number" in text)
    )
    has_rate_options = ("1-" in text and "2-" in text) and (
        ("iptal" in text) or ("non-refundable" in text) or ("free cancellation" in text)
    )
    return has_reference and has_rate_options


def _missing_cancel_fields_message(lang: str, missing_fields: List[str]) -> str:
    base = get_runtime_text(("hotel_cancel_v1", "messages", "missing_slots"), lang=lang)
    if not missing_fields:
        return base
    if lang == "en":
        labels = {
            "reservation_id_or_voucher_no": "Reservation/Voucher No",
            "rate_type": "Rate type (1/2)",
        }
        return f"{base}\nMissing: {', '.join(labels.get(m, m) for m in missing_fields)}."
    if lang == "ru":
        labels = {
            "reservation_id_or_voucher_no": "Номер бронирования/ваучера",
            "rate_type": "Тип тарифа (1/2)",
        }
        return f"{base}\nНе хватает: {', '.join(labels.get(m, m) for m in missing_fields)}."

    labels = {
        "reservation_id_or_voucher_no": "Rezervasyon/Voucher No",
        "rate_type": "Fiyat tipi (1/2)",
    }
    return f"{base}\nEksik: {', '.join(labels.get(m, m) for m in missing_fields)}."


def _is_price_availability_followup_query(msg_ascii: str) -> bool:
    """
    Fiyat/müsaitlik takip sorularını operasyonel RezID kuralından ayır.
    Amaç: "aynı tarihlerde deniz manzaralı oda müsait mi, fiyat farkı?"
    gibi sorguların yanlışlıkla rezervasyon operasyonu olarak etiketlenmesini engellemek.
    """
    text = (msg_ascii or "").strip()
    if not text:
        return False

    price_markers = [
        "fiyat", "ücret", "ucret", "fark",
        "müsait", "musait", "availability", "available",
        "oda", "room", "manzara", "view",
        "tl", "₺", "eur", "usd", "euro", "dolar",
    ]
    intent_anchors = [
        "aynı tarihlerde", "ayni tarihlerde", "bu tarihlerde", "o tarihlerde",
        "same dates", "varsa", "ne kadar", "kaç", "kac",
    ]
    hard_operation_markers = [
        "rezervasyonumu", "rezervasyonum", "bookingimi",
        "iptal", "iade", "değiş", "degis", "güncelle", "guncelle",
        "update", "cancel", "modify",
        "voucher", "rez id", "rez no", "rezervasyon no", "rezervasyon id",
    ]

    has_price_signal = any(k in text for k in price_markers)
    has_question_signal = ("?" in text) or any(k in text for k in ["ne kadar", "kaç", "kac", "müsait mi", "musait mi"])
    has_anchor = any(k in text for k in intent_anchors)
    has_hard_operation = any(k in text for k in hard_operation_markers)

    if has_hard_operation:
        return False
    return has_price_signal and has_question_signal and has_anchor


def _is_booking_confirmation_code_question(msg_ascii: str) -> bool:
    text = (msg_ascii or "").strip()
    if not text:
        return False
    confirmation_markers = [
        "kesinles", "kesinleş", "teyit", "onay", "confirm", "confirmation", "подтвержд",
    ]
    code_markers = [
        "rezervasyon kod", "rez kod", "rez id", "voucher", "kodu paylaş",
        "teyit mesaj", "whatsapp", "booking code", "booking number", "confirmation number",
        "код", "номер бронир",
    ]
    has_booking = any(k in text for k in ["rezervasyon", "booking", "reservation", "брони", "бронь"])
    has_confirmation = any(k in text for k in confirmation_markers)
    has_code = any(k in text for k in code_markers)
    return has_booking and has_confirmation and has_code


def _is_rez_id_info_question(msg_ascii: str) -> bool:
    text = (msg_ascii or "").strip()
    if not text:
        return False
    token = _extract_rez_id_token(text)
    if token and token.lower() not in {"nedir", "ne", "what", "whats", "info", "это", "такое"}:
        return False

    id_markers = [
        "rez id",
        "reservation id",
        "voucher no",
        "voucher number",
    ]
    info_markers = [
        "nedir",
        "ne",
        "what is",
        "what's",
        "info",
        "что такое",
        "что это",
        "?",
    ]
    has_id_ref = any(marker in text for marker in id_markers)
    has_info = any(marker in text for marker in info_markers)
    return has_id_ref and has_info


def _is_date_change_request(msg_ascii: str) -> bool:
    text = (msg_ascii or "").strip()
    if not text:
        return False
    if "iptal" in text:
        return False
    if not any(k in text for k in ["rezerv", "booking", "reservation"]):
        return False
    date_change_signals = [
        "tarih değiş", "tarih degis", "tarihini değiş", "tarihini degis",
        "tarihe almak", "tarihe al", "date change", "change date",
    ]
    if any(s in text for s in date_change_signals):
        return True
    # "15 Temmuz rezervasyonumu 22 Temmuz tarihine almak istiyorum" benzeri.
    if re.search(r"tarihi?ne?\s+al", text):
        return True
    return False


def evaluate_operational_reservation_rule(
    user_message: str,
    history: List[Dict[str, Any]],
    lang: str = "tr",
) -> Optional[Dict[str, Any]]:
    """
    Konuşmada netleştirilen operasyon kurallarını deterministik uygular.
    Bu katman LLM'e gitmeden önce çalışır.
    """
    msg = _tr_lower(user_message)
    msg_ascii = msg.replace("ıd", "id")
    last_bot = _tr_lower(_last_assistant(history))
    rez_id_token = _extract_rez_id_token(msg_ascii)
    previous_rez_id_token = _extract_latest_user_slot(history, _extract_rez_id_token)
    rate_type = _extract_rate_type(msg_ascii)
    previous_rate_type = _extract_latest_user_slot(history, _extract_rate_type)
    full_name = _extract_full_name(user_message) or _extract_latest_user_slot(history, _extract_full_name)
    effective_rez_id = rez_id_token or previous_rez_id_token
    effective_rate_type = rate_type or previous_rate_type

    # Rez ID açıklaması
    if _is_rez_id_info_question(msg_ascii):
        return {
            "reply": _lang_text("rez_id_info", lang),
            "status": "operational_rez_id_info",
            "notify_admin_handoff": False,
            "activate_human_takeover": False,
        }

    # Rezervasyon onayından sonra teyit mesajı + rezervasyon kodu paylaşımı
    if _is_booking_confirmation_code_question(msg_ascii):
        return {
            "reply": _lang_text("booking_confirmation_info", lang),
            "status": "operational_booking_confirmation_info",
            "notify_admin_handoff": False,
            "activate_human_takeover": False,
        }

    # Fiyat/müsaitlik takip sorularını operasyonel RezID kurallarından çıkar.
    if _is_price_availability_followup_query(msg_ascii):
        return None

    # Çoklu oda + kısmi iptal (önce oda netleştir) - genel iptal akışından önce.
    partial_multi_room_cancel = (
        ("oda" in msg and "iptal" in msg)
        and any(k in msg for k in ["sadece 1", "bir oday", "kalan 2", "2 oda", "3 oda"])
    )
    if partial_multi_room_cancel:
        if not rez_id_token:
            return {
                "reply": (
                    "Rezervasyonunuzla ilgili sorgulama, değişiklik veya iptal işlemi başlatabilmemiz için "
                    "lütfen önce rezervasyon numarası / Voucher No bilginizi paylaşın.\n"
                    "Rezervasyon numarası veya Voucher No paylaşılmadan rezervasyon üzerinde değişiklik yapılamaz."
                ),
                "status": "operational_rezid_required",
                "notify_admin_handoff": False,
                "activate_human_takeover": False,
            }
        return {
            "reply": (
                "Elbette, kısmi iptal talebinizi birlikte düzenleyebiliriz.\n"
                "Lütfen iptal edilecek odayı (misafir adı/oda bilgisi) teyit edin; "
                "kalan odalarınız aynı şekilde korunacaktır.\n"
                "Teyit sonrası sizi canlı müşteri temsilcimize bağlıyorum."
            ),
            "status": "operational_partial_cancel_identify_room",
            "notify_admin_handoff": False,
            "activate_human_takeover": False,
        }

    # Hotel cancellation v1:
    # Hard handoff only after Reservation/Voucher No + rate type (1/2) are collected.
    waiting_cancel_slots = _is_waiting_hotel_cancel_slots(last_bot)
    is_cancel_request = _is_hotel_cancel_request(msg_ascii)
    if waiting_cancel_slots or is_cancel_request:
        missing_fields: List[str] = []
        if not effective_rez_id:
            missing_fields.append("reservation_id_or_voucher_no")
        if not effective_rate_type:
            missing_fields.append("rate_type")

        if not missing_fields:
            handoff_reply = get_runtime_text(("hotel_cancel_v1", "messages", "handoff"), lang=lang)
            handoff_category = str(
                AUTOMATION_RUNTIME_RULES.get("hotel_cancel_v1", {}).get("handoff_category", "iptal_iade")
            )
            handoff_priority = str(
                AUTOMATION_RUNTIME_RULES.get("hotel_cancel_v1", {}).get("handoff_priority", "high")
            )
            return {
                "reply": handoff_reply,
                "status": "operational_cancel_handoff",
                "notify_admin_handoff": True,
                "handoff_category": handoff_category,
                "handoff_priority": handoff_priority,
                "activate_human_takeover": True,
                "handoff_reason": (
                    f"hotel_cancel_v1 rez_id={effective_rez_id} "
                    f"rate_type={effective_rate_type} full_name={full_name or '-'}"
                ),
                "meta": {
                    "rez_id": effective_rez_id,
                    "rate_type": effective_rate_type,
                    "full_name": full_name,
                },
            }

        if is_cancel_request and not waiting_cancel_slots:
            return {
                "reply": get_runtime_text(("hotel_cancel_v1", "messages", "start"), lang=lang),
                "status": "operational_cancel_collect_required",
                "notify_admin_handoff": False,
                "activate_human_takeover": False,
            }

        return {
            "reply": _missing_cancel_fields_message(lang=lang, missing_fields=missing_fields),
            "status": "operational_cancel_collect_missing",
            "notify_admin_handoff": False,
            "activate_human_takeover": False,
        }

    # Rezervasyon sorgu/degisiklik/iptal isteklerinde Rez ID zorunlu
    # ÖNEMLİ: "aynı tarihlerde oda müsait mi, fiyat farkı ne kadar?" gibi fiyat/müsaitlik
    # soruları rezervasyon operasyonu değildir; Rez ID kuralına düşmemeli.
    operation_action_markers = [
        "sorgu", "sorgulama", "durum", "kontrol",
        "degis", "değiş", "tarih", "iptal", "iade",
        "update", "change", "cancel", "status", "modify",
    ]
    reservation_context_markers = [
        "rezervasyon", "rez id", "voucher", "booking", "reservation",
    ]
    price_availability_markers = [
        "fiyat", "ücret", "ucret", "fark", "müsait", "musait",
        "availability", "available", "oda", "room", "manzara", "view",
    ]
    booking_create_markers = [
        "rezervasyon yapmak", "rezervasyon yaptirmak", "oda ayirtmak",
        "i want to book", "book this room", "make a reservation",
    ]
    price_comparison_markers = [
        "fiyat", "ücret", "ucret", "fark", "ne kadar", "price", "rate",
    ]
    has_reservation_context = any(k in msg_ascii for k in reservation_context_markers)
    has_operation_action = any(k in msg_ascii for k in operation_action_markers)
    has_price_comparison_signal = any(k in msg_ascii for k in price_comparison_markers)
    is_room_level_operation = (
        ("oda" in msg_ascii)
        and any(k in msg_ascii for k in ["iptal", "degis", "değiş", "change", "cancel", "update"])
        and not has_price_comparison_signal
    )
    is_reservation_operation = (has_reservation_context and has_operation_action) or is_room_level_operation
    is_new_booking_request = any(k in msg_ascii for k in booking_create_markers)
    is_price_availability_inquiry = any(k in msg_ascii for k in price_availability_markers) and not any(
        k in msg_ascii for k in ["iptal", "degis", "değiş", "change", "cancel", "update", "iade"]
    )
    if is_reservation_operation and not is_new_booking_request and not rez_id_token and not is_price_availability_inquiry:
        return {
            "reply": (
                "Rezervasyonunuzla ilgili sorgulama, değişiklik veya iptal işlemi başlatabilmemiz için "
                "lütfen önce rezervasyon numarası / Voucher No bilginizi paylaşın.\n"
                "Rezervasyon numarası veya Voucher No paylaşılmadan rezervasyon üzerinde değişiklik yapılamaz."
            ),
            "status": "operational_rezid_required",
            "notify_admin_handoff": False,
            "activate_human_takeover": False,
        }

    # Çoklu oda + farklı tarih (Rez ID iste)
    multi_room_date_change = (
        "oda" in msg
        and any(k in msg for k in ["tarih", "almak", "degist", "değiş"])
        and any(k in msg for k in ["2 oda", "3 oda", "bir oday", "sadece bir oda"])
    )
    if multi_room_date_change:
        return {
            "reply": (
                "Elbette, çoklu oda rezervasyonlarında farklı tarih taleplerini birlikte yönetebiliriz.\n"
                "Hangi odanın değişeceğini netleştirebilmemiz için rezervasyon numaranızı ve ilgili oda bilgisini paylaşır mısınız?\n"
                "Teyit sonrası işlemi canlı müşteri temsilcimizle ilerleteceğiz."
            ),
            "status": "operational_multiroom_date_change_rezid",
            "notify_admin_handoff": False,
            "activate_human_takeover": False,
        }

    # Genel tarih değişikliği akışı
    if _is_date_change_request(msg_ascii):
        return {
            "reply": (
                "Talebinizi aldım.\n"
                "Öncelikle yeni tarihte aynı oda tipinin müsaitliğini kontrol edeceğim.\n"
                "- Aynı oda tipi müsaitse yeni toplam fiyatı sizinle paylaşacağım.\n"
                "- Müsait değilse, aynı giriş/çıkış tarihleri için müsait tüm oda tiplerini ve fiyatlarını ileteceğim.\n"
                "İşlemi başlatmam için rezervasyon numaranızı paylaşır mısınız?"
            ),
            "status": "operational_date_change_flow",
            "notify_admin_handoff": False,
            "activate_human_takeover": False,
        }

    # Oda değişikliği onayı sonrası admin/canlı temsilci aktarımı
    waiting_room_change_approval = "müsait tüm oda tiplerini" in last_bot and "fiyatlarını ileteceğim" in last_bot
    if waiting_room_change_approval and _is_yes(msg):
        return {
            "reply": (
                "Onayınızı aldım, teşekkür ederim. "
                "Oda değişikliği talebinizi şimdi canlı müşteri temsilcimize ve operasyon ekibimize iletiyorum."
            ),
            "status": "operational_room_change_handoff",
            "notify_admin_handoff": True,
            "handoff_category": "canli_destek",
            "handoff_priority": "medium",
            "activate_human_takeover": True,
            "handoff_reason": "room_change_confirmed",
        }

    return None
