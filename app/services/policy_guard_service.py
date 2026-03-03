from __future__ import annotations

import re
from typing import Any, Dict, Optional


TR_CANCELLATION_POLICY_REPLY = (
    "İptal/iade koşulları tarife göre değişir:\n"
    "- İade yapılmaz (non-refundable): daha avantajlı fiyattır, iptal/iade yoktur.\n"
    "- Ücretsiz iptal tarifesi: fiyatı daha yüksektir; girişten 5 gün öncesine kadar iptalde %100 geri ödeme yapılır.\n"
    "- Girişten sonra iptal/iade seçeneği bulunmamaktadır."
)
EN_CANCELLATION_POLICY_REPLY = (
    "Our cancellation policy depends on rate type:\n"
    "- Non-refundable: lower price, no cancellation/refund.\n"
    "- Free Cancellation: higher price, 100% refund up to 5 days before check-in.\n"
    "- After check-in: no cancellation/refund is available."
)
RU_CANCELLATION_POLICY_REPLY = (
    "Условия отмены зависят от типа тарифа:\n"
    "- Невозвратный тариф: цена ниже, отмена/возврат не предусмотрены.\n"
    "- Тариф с бесплатной отменой: цена выше, 100% возврат при отмене не позднее чем за 5 дней до заезда.\n"
    "- После заезда отмена/возврат не предусмотрены."
)

DE_CANCELLATION_POLICY_REPLY = (
    "Unsere Stornierungsbedingungen hängen vom Tariftyp ab:\n"
    "- Nicht erstattungsfähig: günstigerer Preis, keine Stornierung/Erstattung.\n"
    "- Kostenlose Stornierung: höherer Preis, 100% Erstattung bis 5 Tage vor Check-in.\n"
    "- Nach dem Check-in ist keine Stornierung/Erstattung möglich."
)
ES_CANCELLATION_POLICY_REPLY = (
    "La política de cancelación depende del tipo de tarifa:\n"
    "- No reembolsable: precio más bajo, sin cancelación/reembolso.\n"
    "- Cancelación gratuita: precio más alto, reembolso del 100% hasta 5 días antes del check-in.\n"
    "- Después del check-in no hay cancelación/reembolso."
)
FR_CANCELLATION_POLICY_REPLY = (
    "Notre politique d'annulation dépend du type de tarif:\n"
    "- Non remboursable: prix plus bas, sans annulation/remboursement.\n"
    "- Annulation gratuite: prix plus élevé, remboursement à 100% jusqu'à 5 jours avant l'arrivée.\n"
    "- Après l'arrivée, aucune annulation/remboursement n'est possible."
)
PT_CANCELLATION_POLICY_REPLY = (
    "Nossa política de cancelamento depende do tipo de tarifa:\n"
    "- Não reembolsável: preço mais baixo, sem cancelamento/reembolso.\n"
    "- Cancelamento gratuito: preço mais alto, reembolso de 100% até 5 dias antes do check-in.\n"
    "- Após o check-in, não há cancelamento/reembolso."
)
AR_CANCELLATION_POLICY_REPLY = (
    "تعتمد سياسة الإلغاء على نوع السعر:\n"
    "- غير قابل للاسترداد: سعر أقل، بدون إلغاء/استرداد.\n"
    "- إلغاء مجاني: سعر أعلى، استرداد 100% حتى 5 أيام قبل تسجيل الدخول.\n"
    "- بعد تسجيل الدخول لا يوجد إلغاء/استرداد."
)
ZH_CANCELLATION_POLICY_REPLY = (
    "取消政策取决于房价类型：\n"
    "- 不可退款：价格更低，不可取消/退款。\n"
    "- 免费取消：价格更高，入住前5天可100%退款。\n"
    "- 入住后不可取消/退款。"
)
HI_CANCELLATION_POLICY_REPLY = (
    "रद्दीकरण नीति चुनी गई दर पर निर्भर करती है:\n"
    "- नॉन-रिफंडेबल: कम कीमत, कोई कैंसलेशन/रिफंड नहीं।\n"
    "- फ्री कैंसलेशन: अधिक कीमत, चेक-इन से 5 दिन पहले तक 100% रिफंड।\n"
    "- चेक-इन के बाद कैंसलेशन/रिफंड उपलब्ध नहीं है।"
)

LANG_REPLIES = {
    "tr": TR_CANCELLATION_POLICY_REPLY,
    "en": EN_CANCELLATION_POLICY_REPLY,
    "ru": RU_CANCELLATION_POLICY_REPLY,
    "de": DE_CANCELLATION_POLICY_REPLY,
    "es": ES_CANCELLATION_POLICY_REPLY,
    "fr": FR_CANCELLATION_POLICY_REPLY,
    "pt": PT_CANCELLATION_POLICY_REPLY,
    "ar": AR_CANCELLATION_POLICY_REPLY,
    "zh": ZH_CANCELLATION_POLICY_REPLY,
    "hi": HI_CANCELLATION_POLICY_REPLY,
}

DIRECT_CANCEL_PATTERNS = (
    r"\brezervasyonumu iptal\b",
    r"\biptal etmek istiyorum\b",
    r"\bcancel my reservation\b",
    r"\bcancel reservation\b",
    r"\bquiero cancelar\b",
    r"\bannuler\b",
    r"\bstornier(?:en|ung)?\b",
    r"\bcancelar\b",
    r"\bотменить\b",
    r"\bإلغاء\b",
    r"\b取消\b",
    r"\bरद्द\b",
)


def _looks_like_direct_cancel_request(raw_msg: str) -> bool:
    if not raw_msg:
        return False
    return any(re.search(pattern, raw_msg, flags=re.IGNORECASE) for pattern in DIRECT_CANCEL_PATTERNS)


def _looks_like_mixed_stay_or_booking_intent(message: str) -> bool:
    if not message:
        return False

    raw_msg = message or ""
    low_msg = _normalize(raw_msg)

    # Primary signal: if message already looks like a pricing request, do not short-circuit
    # into a standalone cancellation-policy reply.
    try:
        from app.utils.message_utils import detect_price_request

        if detect_price_request(raw_msg, history=None):
            return True
    except Exception:
        # Guard should be resilient; fallback to marker-based detection below.
        pass

    booking_action_markers = (
        "book",
        "booking",
        "reservation",
        "reserve",
        "rezervasyon",
        "rezerv",
        "broniro",
        "брони",
        "бронь",
        "оформить",
    )
    if any(marker in low_msg for marker in booking_action_markers):
        return True

    # Non-policy operational questions usually indicate mixed intent and should continue
    # to the main flow instead of being answered with policy-only shortcut.
    mixed_context_markers = (
        "availability",
        "available",
        "müsait",
        "musait",
        "oda",
        "room",
        "sea view",
        "deniz manzar",
        "breakfast",
        "kahvalti",
        "kahvaltı",
        "check-in",
        "check in",
        "check-out",
        "check out",
        "late check",
        "geç çıkış",
        "gec cikis",
        "transfer",
        "airport",
        "havalimani",
        "havalimanı",
        "payment",
        "ödeme",
        "odeme",
        "deposit",
        "depozit",
        "kapora",
        "паспорт",
        "whatsapp",
        "стоимость",
        "свободн",
        "заезд",
        "выезд",
        "трансфер",
        "предоплат",
        "завтрак",
    )
    return any(marker in low_msg for marker in mixed_context_markers)


def _looks_like_cancellation_policy_question(low_msg: str, raw_msg: str) -> bool:
    if not low_msg and not raw_msg:
        return False
    if _looks_like_direct_cancel_request(raw_msg):
        return False

    cancel_markers = [
        "iptal", "cancellation", "cancelation", "cancelación", "annulation",
        "storno", "stornierung", "отмена", "отмен", "возврат", "إلغاء", "取消", "रद्द",
        "refund", "iade", "reembolso", "remboursement", "rueckerstattung",
        "rückerstattung", "استرداد", "退款", "रिफंड",
        "cancelamento", "cancelar",
    ]
    if not any(marker in low_msg or marker in raw_msg for marker in cancel_markers):
        return False

    if _looks_like_mixed_stay_or_booking_intent(raw_msg):
        return False

    inquiry_markers = [
        "kosul",
        "kural",
        "sart",
        "rule",
        "rules",
        "condition",
        "conditions",
        "term",
        "terms",
        "politika",
        "policy",
        "tarife",
        "tarif",
        "rate type",
        "refundable",
        "reembolsavel",
        "reembolsável",
        "non-refundable",
        "non refundable",
        "nao reembolsavel",
        "não reembolsável",
        "free cancellation",
        "cancelamento",
        "tarifa",
        "tarifas",
        "nedir",
        "nasil",
        "detay",
        "bilgi",
        "var mi",
        "geri odeme",
        "reembolso",
        "remboursement",
        "erstattung",
        "услов",
        "политик",
        "правил",
        "条件",
        "规则",
        "قواعد",
        "سياسة",
        "الإلغاء",
        "الالغاء",
        "استرداد",
        "शर्त",
        "नीति",
        "?",
    ]
    return any(marker in low_msg or marker in raw_msg for marker in inquiry_markers)


def _normalize(text: str) -> str:
    return (
        (text or "")
        .lower()
        .replace("\u0131", "i")
        .replace("\u011f", "g")
        .replace("\u00fc", "u")
        .replace("\u015f", "s")
        .replace("\u00f6", "o")
        .replace("\u00e7", "c")
        .replace("ğ", "g")
        .replace("ş", "s")
        .replace("ö", "o")
        .replace("ü", "u")
        .replace("ç", "c")
        .replace("á", "a")
        .replace("à", "a")
        .replace("â", "a")
        .replace("ã", "a")
        .replace("é", "e")
        .replace("è", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ì", "i")
        .replace("î", "i")
        .replace("ó", "o")
        .replace("ò", "o")
        .replace("ô", "o")
        .replace("õ", "o")
        .replace("ú", "u")
        .replace("ù", "u")
        .replace("û", "u")
        .replace("ñ", "n")
        .replace("ç", "c")
    )


def evaluate_policy_guard(message: str, lang: str = "tr") -> Dict[str, Any]:
    low_msg = _normalize(message)
    raw_msg = (message or "").lower()
    lang_norm = (lang or "en").strip().lower()
    if lang_norm not in LANG_REPLIES:
        lang_norm = "en"

    if _looks_like_cancellation_policy_question(low_msg, raw_msg):
        reply = LANG_REPLIES.get(lang_norm, EN_CANCELLATION_POLICY_REPLY)
        return {
            "handled": True,
            "status": "policy_guard_cancellation_policy",
            "reply": reply,
            "reason_code": "policy_guard.cancellation_policy",
            "meta": {"policy_id": "cancellation_policy.v1", "lang": lang_norm},
        }

    return {"handled": False, "status": None, "reply": None, "reason_code": None, "meta": {}}


def is_new_pipeline_enabled(env_value: Optional[str]) -> bool:
    value = (env_value or "").strip().lower()
    return value in {"1", "true", "yes", "on", "enabled"}
