from __future__ import annotations

import os
import re
import time as time_module
import inspect
import httpx
import unicodedata
from difflib import SequenceMatcher
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Request, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from app.content.intent_taxonomy import INTENT_AUTO_CONFIDENCE_THRESHOLD
from app.flows.flow_context import FlowContext as RequestFlowContext
from app.services.correlation_service import CORRELATION_HEADER, resolve_correlation_id
from app.services.flow_fsm_service import decide_execution_order
from app.services.intent_policy_service import infer_primary_intent
from app.services.intent_router_service import infer_domain_hint, route_intent
from app.services.intent_normalizer_service import (
    force_primary_intent_from_explicit_message as force_primary_intent_from_explicit_message_svc,
    looks_like_booking_payment_followup as looks_like_booking_payment_followup_svc,
    looks_like_explicit_booking_create_signal as looks_like_explicit_booking_create_signal_svc,
    looks_like_explicit_room_price_or_availability_query as looks_like_explicit_room_price_or_availability_query_svc,
    looks_like_general_price_query_with_slots as looks_like_general_price_query_with_slots_svc,
    looks_like_generic_price_or_availability_signal as looks_like_generic_price_or_availability_signal_svc,
)
from app.services.language_policy_service import (
    contains_turkish_chars as contains_turkish_chars_svc,
    extract_language_from_switch_confirmation as extract_language_from_switch_confirmation_svc,
    extract_language_switch_request as extract_language_switch_request_svc,
    looks_like_turkish_ascii_message as looks_like_turkish_ascii_message_svc,
    normalize_language_code as normalize_language_code_svc,
    resolve_language_lock as resolve_language_lock_svc,
)
from app.services.language_guard_service import (
    needs_hard_language_guard,
    normalize_guard_language,
)
from app.services.policy_guard_service import evaluate_policy_guard, is_new_pipeline_enabled
from app.services.slot_contract_service import (
    evaluate_slot_coverage,
    get_missing_slot_prompt,
    should_request_slot_clarification,
)
from app.services.structured_log_service import log_event
from app.services.booking_flow_service import get_payment_context
from app.services.handoff_critical_registry import KNOWN_AUTO_INTENTS


class ChatRequest(BaseModel):
    phone: str
    message: str
    message_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    reservation_log: Optional[str] = None
    is_price_template: bool = False
    status: str = "ok"
    reason_code: Optional[str] = None
    next_expected_input: Optional[str] = None


def _clean_phone_digits(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


def _extract_whatsapp_text(message_obj: Dict[str, Any]) -> str:
    text_obj = message_obj.get("text")
    if isinstance(text_obj, dict):
        body = str(text_obj.get("body") or "").strip()
        if body:
            return body

    interactive = message_obj.get("interactive")
    if isinstance(interactive, dict):
        button_reply = interactive.get("button_reply")
        if isinstance(button_reply, dict):
            title = str(button_reply.get("title") or "").strip()
            if title:
                return title
            selected_id = str(button_reply.get("id") or "").strip()
            if selected_id:
                return selected_id

        list_reply = interactive.get("list_reply")
        if isinstance(list_reply, dict):
            title = str(list_reply.get("title") or "").strip()
            if title:
                return title
            selected_id = str(list_reply.get("id") or "").strip()
            if selected_id:
                return selected_id

    button = message_obj.get("button")
    if isinstance(button, dict):
        text = str(button.get("text") or "").strip()
        if text:
            return text
        payload = str(button.get("payload") or "").strip()
        if payload:
            return payload

    return ""


def _extract_whatsapp_inbound_messages(payload: Dict[str, Any]) -> list[Dict[str, str]]:
    out: list[Dict[str, str]] = []
    entries = payload.get("entry")
    if not isinstance(entries, list):
        return out

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        changes = entry.get("changes")
        if not isinstance(changes, list):
            continue
        for change in changes:
            if not isinstance(change, dict):
                continue
            value = change.get("value")
            if not isinstance(value, dict):
                continue
            messages = value.get("messages")
            if not isinstance(messages, list):
                continue
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                text = _extract_whatsapp_text(msg)
                phone = _clean_phone_digits(str(msg.get("from") or ""))
                message_id = str(msg.get("id") or "").strip()
                if not phone or not text:
                    continue
                out.append(
                    {
                        "phone": phone,
                        "message": text,
                        "message_id": message_id,
                    }
                )
    return out


def _should_forward_reply(status: str, reply: str) -> bool:
    low = str(status or "").strip().lower()
    if not str(reply or "").strip():
        return False
    return low not in {"empty", "duplicate", "duplicate_message_id"}


_TR_SPELLING_MAP = {
    "yas": "yaş",
    "cocuk": "çocuk",
    "secim": "seçim",
    "secenek": "seçenek",
    "secenegi": "seçeneği",
    "ozel": "özel",
    "isteginiz": "isteğiniz",
    "numarasi": "numarası",
    "musait": "müsait",
    "farkli": "farklı",
    "bulunamadi": "bulunamadı",
    "yetiskin": "yetişkin",
    "tesekkur": "teşekkür",
    "kahvalti": "kahvaltı",
    "odeme": "ödeme",
    "guncel": "güncel",
    "musteri": "müşteri",
    "ucretsiz": "ücretsiz",
    "cikis": "çıkış",
    "giris": "giriş",
    "degisiklik": "değişiklik",
    "iletisim": "iletişim",
    "hizli": "hızlı",
    "sifre": "şifre",
    "konusma": "konuşma",
    "kisa": "kısa",
}

_TR_ASCII_SIGNAL_WORDS = {
    "kahvalti",
    "dahil",
    "degilse",
    "kisi",
    "yetiskin",
    "cocuk",
    "giris",
    "cikis",
    "havalimani",
    "rezervasyon",
    "fiyat",
    "ucret",
    "musait",
    "kapora",
    "odeme",
    "tesekkur",
    "yardimci",
    "balayi",
    "surpriz",
    "saatleriniz",
    "nedir",
}


LANGUAGE_PRIORITY = ["en", "tr", "ru", "de", "ar", "es", "fr", "zh", "hi", "pt"]
TRANSLATION_ONLY_LANGS = set(LANGUAGE_PRIORITY)
LANGUAGE_NAME_ALIASES = {
    "en": ["english", "ingilizce"],
    "tr": ["turkish", "türkçe", "turkce"],
    "ru": ["russian", "rusça", "rusca", "русский", "по-русски"],
    "de": ["german", "almanca", "deutsch"],
    "ar": ["arabic", "arapça", "arapca", "العربية", "عربي"],
    "es": ["spanish", "ispanyolca", "español", "espanol"],
    "fr": ["french", "fransızca", "fransizca", "français", "francais"],
    "zh": ["chinese", "çince", "cince", "中文", "汉语", "漢語"],
    "hi": ["hindi", "hintçe", "hintce", "हिंदी"],
    "pt": ["portuguese", "portekizce", "português", "portugues"],
}
LANGUAGE_SWITCH_MARKERS = [
    "speak",
    "talk",
    "continue in",
    "write in",
    "konuş",
    "konusalim",
    "konuşalım",
    "devam edelim",
    "yaz",
]
UNSUPPORTED_LANGUAGE_HINTS = [
    "japanese",
    "japonca",
    "日本語",
    "italian",
    "italyanca",
    "italiano",
    "korean",
    "korece",
    "한국어",
]


def _normalize_turkish_reply_text(text: str) -> str:
    if not text:
        return text
    out = text
    for src, dst in _TR_SPELLING_MAP.items():
        out = re.sub(rf"\b{re.escape(src)}\b", dst, out, flags=re.IGNORECASE)
        out = re.sub(rf"\b{re.escape(src.capitalize())}\b", dst.capitalize(), out)
        out = re.sub(rf"\b{re.escape(src.upper())}\b", dst.upper(), out)
    return out


def _normalize_language_code(lang: str) -> str:
    # Supported languages outside this list are forced to English.
    return normalize_guard_language(normalize_language_code_svc(lang))


def _extract_language_switch_request(text: str) -> tuple[str, bool]:
    return extract_language_switch_request_svc(text)


def _language_switch_confirmation(target_lang: str, supported: bool) -> str:
    if not supported:
        return "I can continue in English. Supported languages: English, Turkish, Russian, German, Arabic, Spanish, French, Chinese, Hindi, Portuguese."
    if target_lang == "tr":
        return "Elbette, Türkçe devam edebiliriz. Size nasıl yardımcı olabilirim?"
    if target_lang == "ru":
        return "Конечно, можем продолжить на русском. Чем могу помочь?"
    if target_lang == "en":
        return "Yes, of course. We can continue in English. How can I help you?"
    return "Sure. We can continue in this language. How can I help you?"


def _extract_language_from_switch_confirmation(text: str) -> str:
    return extract_language_from_switch_confirmation_svc(text)


def _looks_like_turkish_ascii_message(text: str) -> bool:
    return looks_like_turkish_ascii_message_svc(text)


def _contains_turkish_chars(text: str) -> bool:
    return contains_turkish_chars_svc(text)


def _count_mojibake_markers(text: str) -> int:
    if not text:
        return 0
    markers = ("Ğ", "Ã", "â", "Â", "Ñ", "Ð", "Ä", "Å", "�")
    return sum(text.count(marker) for marker in markers)


def _repair_mojibake_text(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return raw
    # Normal metinleri asla zorlamayalım.
    if _count_mojibake_markers(raw) < 3:
        return raw

    best = raw
    best_bad = _count_mojibake_markers(raw)
    for source_encoding in ("cp1254", "cp1252", "latin1"):
        try:
            candidate = raw.encode(source_encoding, errors="ignore").decode("utf-8", errors="ignore").strip()
        except Exception:
            continue
        if not candidate:
            continue
        # CJK/AR/HI/RU script geri geldiyse doğrudan kullan.
        if re.search(r"[а-яёА-ЯЁ\u0600-\u06FF\u0900-\u097F\u4e00-\u9fff]", candidate):
            return candidate
        cand_bad = _count_mojibake_markers(candidate)
        if cand_bad < best_bad and len(candidate) >= max(4, len(raw) // 3):
            best = candidate
            best_bad = cand_bad
    return best


def _resolve_language_lock(phone: str, user_message: str, load_conversation_fn, detect_language_fn) -> str:
    return resolve_language_lock_svc(
        phone=phone,
        user_message=user_message,
        load_conversation_fn=load_conversation_fn,
        detect_language_fn=detect_language_fn,
    )


def _translate_reply_if_needed(reply: str, target_lang: str, openai_client, openai_model: str, detect_language_fn) -> str:
    text = (reply or "").strip()
    lang = _normalize_language_code(target_lang)
    if not text or lang not in TRANSLATION_ONLY_LANGS:
        return text

    detected_lang = ""
    try:
        if callable(detect_language_fn):
            detected_lang = _normalize_language_code(detect_language_fn(text))
    except Exception:
        detected_lang = ""

    alpha_chars = re.findall(r"[A-Za-z\u00C0-\u024F\u0400-\u04FF\u0600-\u06FF\u0900-\u097F\u4e00-\u9fff]", text)
    alpha_count = len(alpha_chars) or 1

    def _ratio(pattern: str) -> float:
        return len(re.findall(pattern, text)) / float(alpha_count)

    latin_ratio = _ratio(r"[A-Za-z\u00C0-\u024F]")
    script_ratio = {
        "ru": _ratio(r"[а-яёА-ЯЁ]"),
        "ar": _ratio(r"[\u0600-\u06FF]"),
        "zh": _ratio(r"[\u4e00-\u9fff]"),
        "hi": _ratio(r"[\u0900-\u097F]"),
    }.get(lang, 0.0)
    has_untranslated_room_markers = bool(
        re.search(
            r"\b(deluxe|superior|exclusive|street\s*view|pool\s*view|penthouse|premium|jacuzzi)\b",
            text,
            flags=re.IGNORECASE,
        )
    )
    if lang in {"ru", "ar", "zh", "hi"}:
        # Hedef script neredeyse tüm metni kapsıyorsa ve Latin içerik yoksa çeviri atlanır.
        # Aksi durumda karışık cevapları tamamen hedef dile çevirmek için LLM'e düşer.
        if script_ratio >= 0.9 and latin_ratio == 0.0 and not has_untranslated_room_markers:
            return text
    elif detected_lang and detected_lang == lang:
        return text

    if not openai_client or os.getenv("OPENAI_API_KEY", "").strip().lower().startswith("test-"):
        return text
    try:
        non_latin_script_constraint = ""
        if lang in {"ru", "ar", "zh", "hi"}:
            non_latin_script_constraint = (
                "Use only the target language/script for all translatable text, including room type names. "
                "Do not keep English room labels. "
                "Avoid Latin letters unless strictly required for URLs, phone numbers, or hotel brand 'Kassandra'. "
            )
        translated = openai_client.chat.completions.create(
            model=openai_model,
            temperature=0,
            max_tokens=700,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"Translate the assistant message to {lang.upper()}. "
                        f"{non_latin_script_constraint}"
                        "Keep meaning exactly, preserve URLs/phone numbers, output only translation."
                    ),
                },
                {"role": "user", "content": text},
            ],
        )
        content = (translated.choices[0].message.content or "").strip()
        return content or text
    except Exception:
        return text


def _enforce_language_lock(reply: str, target_lang: str, detect_language_fn, openai_client, openai_model: str) -> str:
    """
    Final guard: if model drifts to a different language, force one more translation pass.
    Runtime drift in mixed flows can still happen; this keeps customer-visible language stable.
    """
    text = (reply or "").strip()
    lang = _normalize_language_code(target_lang)
    if not text or lang not in TRANSLATION_ONLY_LANGS:
        return text
    try:
        detected = _normalize_language_code(detect_language_fn(text))
    except Exception:
        detected = ""
    if detected == lang:
        return text
    # One retry (idempotent if already in target language).
    retried = _translate_reply_if_needed(
        text,
        lang,
        openai_client=openai_client,
        openai_model=openai_model,
        detect_language_fn=detect_language_fn,
    )
    try:
        retried_detected = _normalize_language_code(detect_language_fn(retried))
    except Exception:
        retried_detected = ""
    if retried_detected == lang:
        return retried

    # Final strict rewrite pass for rare drift cases (e.g. PT response staying EN).
    if not openai_client or os.getenv("OPENAI_API_KEY", "").strip().lower().startswith("test-"):
        return retried
    try:
        forced = openai_client.chat.completions.create(
            model=openai_model,
            temperature=0,
            max_tokens=700,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"Rewrite the text fully in {lang.upper()}. "
                        "Do not use any other language except URLs/phone numbers/proper brand names. "
                        "Preserve meaning and structure."
                    ),
                },
                {"role": "user", "content": retried},
            ],
        )
        forced_text = (forced.choices[0].message.content or "").strip()
        return forced_text or retried
    except Exception:
        return retried


def _merge_slot_context_from_history(current_message: str, history: list[dict], max_user_turns: int = 4) -> str:
    """
    Slot clarifier için mevcut mesaja yakın kullanıcı geçmişini ekleyerek
    tarih/kişi gibi bilgilerin ikinci kez istenmesini azaltır.
    """
    parts: list[str] = []
    user_turns: list[str] = []
    for item in reversed(history or []):
        if item.get("role") != "user":
            continue
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        user_turns.append(content)
        if len(user_turns) >= max_user_turns:
            break
    for turn in reversed(user_turns):
        parts.append(turn)
    parts.append(str(current_message or "").strip())
    return "\n".join([p for p in parts if p])


def _looks_like_price_slot_followup_with_history(message: str, history: list[dict]) -> bool:
    """
    Kullanıcı slot tamamlama cevabı verdiğinde (örn: "2 yetişkin 2 çocuk"),
    strict-ai-first kapısında fallback'e düşmesini engeller.
    """
    if not (message or "").strip() or not history:
        return False
    current_coverage = evaluate_slot_coverage("PRICE_QUERY", message)
    current_missing = set(current_coverage.get("missing_required_slots") or [])
    merged_text = _merge_slot_context_from_history(message, history)
    merged_coverage = evaluate_slot_coverage("PRICE_QUERY", merged_text)
    merged_missing = set(merged_coverage.get("missing_required_slots") or [])
    if len(merged_missing) >= len(current_missing):
        return False
    low = (message or "").lower()
    slot_markers = (
        "yetişkin",
        "yetiskin",
        "adult",
        "çocuk",
        "cocuk",
        "child",
        "gece",
        "night",
        "ekim",
        "agustos",
        "ağustos",
        "eylül",
        "eylul",
        "kasım",
        "kasim",
        "aralık",
        "aralik",
    )
    return any(marker in low for marker in slot_markers) or bool(re.search(r"\d", low))


def _compute_sentiment_and_frustration(user_message: str, history: list[dict]) -> dict[str, Any]:
    text = (user_message or "").lower()
    negative_words = [
        "saçma", "berbat", "kötü", "rezalet", "şikayet", "sinir", "angry", "bad", "terrible", "useless",
    ]
    positive_words = ["teşekkür", "harika", "iyi", "thanks", "great", "perfect"]

    neg = sum(1 for w in negative_words if w in text)
    pos = sum(1 for w in positive_words if w in text)

    if neg > pos:
        sentiment = "neg"
    elif pos > neg:
        sentiment = "pos"
    else:
        sentiment = "neu"

    intensity = min(1.0, 0.25 + (abs(neg - pos) * 0.2)) if (neg or pos) else 0.2
    confidence = min(1.0, 0.4 + ((neg + pos) * 0.1))

    recent_user_messages: list[str] = []
    for item in history[-8:]:
        if item.get("role") == "user":
            recent_user_messages.append((item.get("content") or "").strip().lower())

    current = (user_message or "").strip().lower()
    repeat_count = 0
    for prev in recent_user_messages[-4:]:
        if not prev or not current:
            continue
        ratio = SequenceMatcher(None, prev, current).ratio()
        if ratio >= 0.82:
            repeat_count += 1
    frustration_loop = repeat_count >= 2

    return {
        "sentiment": sentiment,
        "intensity": round(float(intensity), 3),
        "confidence": round(float(confidence), 3),
        "frustration_loop": frustration_loop,
    }


def _domain_hint_from_message(message: str) -> str:
    m = (message or "").lower()
    if any(k in m for k in ["restaurant", "restoran", "masa"]):
        return "restaurant"
    if any(k in m for k in ["ödeme", "odeme", "payment", "link"]):
        return "payment"
    if any(k in m for k in ["fiyat", "price", "oda", "rezervasyon", "booking"]):
        return "hotel"
    return "unknown"


def _should_bypass_strict_ai_first(message: str) -> bool:
    """
    Fiyat/müsaitlik/rezervasyon niyeti varsa deterministic flow'lara öncelik ver.
    Bu sayede LLM'in teknik placeholder veya erken bilgi isteme üretmesi engellenir.
    """
    if _looks_like_explicit_room_price_or_availability_query(message):
        return True
    if _looks_like_general_price_query_with_slots(message):
        return True
    if _looks_like_generic_price_or_availability_signal(message):
        return True
    if _looks_like_explicit_booking_create_signal(message):
        return True
    if _looks_like_room_booking_create_request(message):
        return True
    if _looks_like_direct_room_booking_create_request(message):
        return True
    if _looks_like_booking_payment_followup(message):
        return True
    domain_hint = infer_domain_hint(message)
    intent = infer_primary_intent(message, domain_hint)
    return intent in {"PRICE_QUERY", "AVAILABILITY_QUERY", "HOTEL_BOOKING_CREATE"}


def _looks_like_booking_payment_followup(message: str) -> bool:
    return looks_like_booking_payment_followup_svc(message)


def _is_price_flow_intent(primary_intent: str) -> bool:
    return str(primary_intent or "").upper() in {"PRICE_QUERY", "AVAILABILITY_QUERY"}


def _is_booking_flow_intent(primary_intent: str) -> bool:
    return str(primary_intent or "").upper() in {
        "HOTEL_BOOKING_CREATE",
        "HOTEL_BOOKING_MODIFY",
        "HOTEL_BOOKING_CANCEL",
        "PAYMENT_METHOD_QUERY",
        "PAYMENT_LINK_REQUEST",
    }


def _is_restaurant_flow_intent(primary_intent: str) -> bool:
    return str(primary_intent or "").upper() in {
        "RESTAURANT_BOOKING_CREATE",
        "RESTAURANT_BOOKING_MODIFY",
        "RESTAURANT_BOOKING_CANCEL",
    }


def _has_non_idle_state(flow_obj: Any) -> bool:
    if not flow_obj:
        return False
    if not isinstance(flow_obj, dict):
        return bool(flow_obj)
    state = str(flow_obj.get("state") or "").strip().lower()
    return bool(state) and state != "idle"


def _extract_locked_lang_from_flow(flow_obj: Any) -> str:
    if not isinstance(flow_obj, dict):
        return ""
    candidates = []
    data = flow_obj.get("data")
    if isinstance(data, dict):
        candidates.extend([data.get("lang"), data.get("language")])
    candidates.extend([flow_obj.get("lang"), flow_obj.get("language")])
    for candidate in candidates:
        if not str(candidate or "").strip():
            continue
        code = _normalize_language_code(str(candidate or ""))
        if code:
            return code
    return ""


def _get_unknown_handoff_reply(lang: str) -> str:
    code = _normalize_language_code(lang)
    if code == "tr":
        return "Bu konuda net ve doğru bilgi verebilmek için sizi canlı destek ekibimize bağlıyorum."
    if code == "ru":
        return "Чтобы предоставить точную информацию по этому вопросу, я подключаю вас к нашей службе поддержки."
    return "To provide accurate information on this topic, I am connecting you to our live support team."


def _looks_like_price_slot_payload(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    coverage = evaluate_slot_coverage("PRICE_QUERY", text)
    required = set(coverage.get("required_slots") or [])
    missing = set(coverage.get("missing_required_slots") or [])
    present = required - missing
    if {"check_in_date", "check_out_date", "adult_count"}.issubset(present):
        return True
    # Tarih + yetişkin bilgisi olan kısa follow-up payload'ları da kabul et.
    has_date_pair = {"check_in_date", "check_out_date"}.issubset(present)
    return has_date_pair and "adult_count" in present


def _looks_like_explicit_room_price_or_availability_query(message: str) -> bool:
    return looks_like_explicit_room_price_or_availability_query_svc(message)


def _looks_like_general_price_query_with_slots(message: str) -> bool:
    return looks_like_general_price_query_with_slots_svc(
        message,
        _looks_like_price_slot_payload,
    )


def _looks_like_explicit_booking_create_signal(message: str) -> bool:
    return looks_like_explicit_booking_create_signal_svc(message)


def _looks_like_room_booking_create_request(message: str) -> bool:
    low = (message or "").lower()
    if not low:
        return False
    has_booking = any(k in low for k in ("rezervasyon", "booking", "book", "reserve"))
    has_room = any(k in low for k in ("oda", "room", "premium", "superior", "deluxe", "exclusive", "penthouse"))
    has_price = _looks_like_generic_price_or_availability_signal(message)
    return has_booking and has_room and not has_price


_CONFUSABLE_CHAR_MAP = str.maketrans(
    {
        "а": "a",  # Cyrillic
        "е": "e",
        "о": "o",
        "р": "p",
        "с": "c",
        "у": "y",
        "х": "x",
        "к": "k",
        "м": "m",
        "т": "t",
        "в": "b",
        "н": "h",
        "і": "i",
        "ї": "i",
        "ӏ": "l",
        "ş": "s",
        "ğ": "g",
        "ı": "i",
        "ö": "o",
        "ü": "u",
        "ç": "c",
    }
)


def _normalize_for_keyword_match(message: str) -> str:
    raw = (message or "").strip().lower()
    if not raw:
        return ""
    folded = unicodedata.normalize("NFKD", raw)
    stripped = "".join(ch for ch in folded if not unicodedata.combining(ch))
    mapped = stripped.translate(_CONFUSABLE_CHAR_MAP)
    mapped = re.sub(r"[^a-z0-9\s]", " ", mapped)
    return re.sub(r"\s+", " ", mapped).strip()


def _looks_like_direct_room_booking_create_request(message: str) -> bool:
    """
    Fail-safe guard for direct booking-create turns.
    Handles short typos/variants like "rezervasyon olustur musunz" even if
    upstream explicit intent helpers misclassify the turn as PRICE_QUERY.
    """
    low = _normalize_for_keyword_match(message)
    if not low:
        return False
    has_booking = any(
        marker in low
        for marker in (
            "rezervasyon",
            "booking",
            "book",
            "reserve",
            "reservation",
        )
    )
    has_create = any(
        marker in low
        for marker in (
            "olustur",
            "yap",
            "baslat",
            "start",
            "create",
            "make",
        )
    )
    has_room = any(
        marker in low
        for marker in (
            "oda",
            "room",
            "premium",
            "superior",
            "deluxe",
            "exclusive",
            "penthouse",
        )
    )
    has_strong_price_marker = any(
        marker in low
        for marker in (
            "fiyat",
            "ücret",
            "ucret",
            "ne kadar",
            "müsait",
            "musait",
            "price",
            "rate",
            "cost",
            "availability",
            "available",
            "how much",
        )
    )
    return has_booking and has_create and has_room and not has_strong_price_marker


def _looks_like_generic_price_or_availability_signal(message: str) -> bool:
    return looks_like_generic_price_or_availability_signal_svc(message)


def _force_primary_intent_from_explicit_message(message: str, current_intent: str) -> str:
    return force_primary_intent_from_explicit_message_svc(
        message,
        current_intent,
        looks_like_price_slot_payload_fn=_looks_like_price_slot_payload,
    )


def _is_price_flow_pivot_message(message: str) -> bool:
    low = (message or "").lower()
    if not low:
        return False
    markers = (
        "ödeme",
        "odeme",
        "payment",
        "kredi kart",
        "credit card",
        "link gönder",
        "link gonder",
        "payment link",
        "otopark",
        "parking",
        "wifi",
        "wi-fi",
        "check-in",
        "check in",
        "check-out",
        "check out",
        "gece geç",
        "gece gec",
        "rezervasyonu başlatalım",
        "rezervasyonu baslatalim",
        "start reservation",
        "start booking",
        "book now",
    )
    return any(m in low for m in markers)


def _looks_like_room_feature_price_comparison(message: str) -> bool:
    low = (message or "").lower()
    if not low:
        return False
    has_feature = any(
        k in low
        for k in (
            "deniz manzara", "sea view", "havuz manzara", "pool view",
            "standart", "standard", "balkon", "balcony",
        )
    )
    has_compare_or_fee = any(
        k in low
        for k in ("fark", "değiş", "degis", "difference", "change", "ek ücret", "ek ucret", "extra fee", "surcharge")
    )
    has_price = any(k in low for k in ("fiyat", "price", "rate", "cost", "ücret", "ucret", "fee"))
    return has_feature and has_compare_or_fee and has_price


def _looks_like_late_checkin_info_query(message: str) -> bool:
    low = (message or "").lower()
    if not low:
        return False
    has_late_checkin_signal = any(
        k in low
        for k in ("gece geç", "gece gec", "geç saatte", "late check-in", "late check in", "night check-in", "night check in")
    )
    has_question = ("?" in (message or "")) or any(
        k in low for k in ("sorun olur mu", "olur mu", "mümkün mü", "mumkun mu", "possible", "is it ok", "can we")
    )
    return has_late_checkin_signal and has_question


def _should_skip_local_faq_for_booking(user_message: str) -> bool:
    """
    Rezervasyon baslatma/devam mesajlarinda local FAQ kisa devresini atla.
    Ornek: "telefonumu gondereyim mi?" ifadesinin iletisim FAQ'ina dusmesini engeller.
    """
    if (
        _looks_like_explicit_booking_create_signal(user_message)
        or _looks_like_room_booking_create_request(user_message)
        or _looks_like_direct_room_booking_create_request(user_message)
    ):
        return True
    low = _normalize_for_keyword_match(user_message)
    has_booking = any(marker in low for marker in ("rezerv", "booking", "reservation", "book"))
    has_identity_or_contact = any(marker in low for marker in ("isim", "name", "telefon", "phone", "numara"))
    has_share_or_start = any(marker in low for marker in ("gonder", "paylas", "send", "share", "baslat", "start"))
    has_booking_progress = any(
        marker in low
        for marker in (
            "rezervasyona gec",
            "rezervasyona devam",
            "rezervasyonu baslat",
            "rezervasyonu baslatalim",
            "book now",
            "continue booking",
            "proceed with booking",
        )
    )
    if has_booking and has_booking_progress:
        return True
    return has_booking and has_identity_or_contact and has_share_or_start


def _looks_like_phone_number_payload(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    if any(ch in text for ch in ("/", ".", ",")):
        # Tarih/fiyat benzeri payloadlari telefon sanma.
        return False
    if not re.fullmatch(r"[\d\+\-\s\(\)]+", text):
        return False
    digits = re.sub(r"\D", "", text)
    return 10 <= len(digits) <= 15


def _recent_reservation_prompt_domain(history: list[Dict[str, Any]]) -> str:
    for item in reversed((history or [])[-8:]):
        if item.get("role") != "assistant":
            continue
        content = (item.get("content") or "").lower()
        if any(k in content for k in ("restoran", "restaurant", "table reservation", "masa rezervasyonu")):
            return "restaurant"
        if any(k in content for k in ("transfer", "flight", "uçuş", "havaliman", "airport")):
            return "transfer"
        if any(k in content for k in ("rezervasyon", "booking", "room", "oda", "ad soyad", "full name")):
            return "hotel"
    return "unknown"


def _has_recent_reservation_contact_prompt(history: list[Dict[str, Any]]) -> bool:
    for item in reversed((history or [])[-8:]):
        if item.get("role") != "assistant":
            continue
        content = (item.get("content") or "").lower()
        if any(
            k in content
            for k in (
                "adım adım",
                "step by step",
                "ilk adım",
                "first step",
                "ad soyad",
                "full name",
                "telefon numaran",
                "phone number",
                "how many guests",
                "kaç kişilik rezervasyon",
                "transfer tarih",
            )
        ):
            return True
    return False


def _should_send_first_message_welcome(message: str) -> bool:
    low = _normalize_for_keyword_match(message)
    if not low:
        return True
    # İlk mesaj açık bir işlem talebiyse (fiyat/rezervasyon/transfer/restoran) doğrudan akışa gir.
    transactional_markers = (
        "rezerv",
        "booking",
        "book",
        "reserve",
        "fiyat",
        "price",
        "musait",
        "müsait",
        "availability",
        "transfer",
        "havaliman",
        "airport",
        "restoran",
        "restaurant",
        "oda",
        "room",
    )
    if any(marker in low for marker in transactional_markers):
        return False
    return True


def _price_engine_unavailable_reply(lang: str) -> str:
    code = _normalize_language_code(lang)
    if code == "en":
        return "I have forwarded your request to our team. We will contact you shortly with price and availability details."
    if code == "ru":
        return "Я передал(а) ваш запрос нашей команде. Мы свяжемся с вами в ближайшее время с информацией о цене и наличии."
    return "Talebinizi ekibimize ilettim. Fiyat ve müsaitlik detayları için en kısa sürede sizinle iletişime geçeceğiz."


def build_chat_router(**deps):
    router = APIRouter()
    new_pipeline_enabled = is_new_pipeline_enabled(os.getenv("NEW_PIPELINE_ENABLED"))
    strict_ai_first = str(os.getenv("STRICT_AI_FIRST", "true")).strip().lower() in {"1", "true", "yes", "on"}
    webhook_path = (os.getenv("WHATSAPP_WEBHOOK_PATH", "/webhook/kassandra-bot-v2").strip() or "/webhook/kassandra-bot-v2")
    if not webhook_path.startswith("/"):
        webhook_path = f"/{webhook_path}"
    webhook_verify_token = (
        os.getenv("WHATSAPP_WEBHOOK_VERIFY_TOKEN", "").strip()
        or os.getenv("WHATSAPP_VERIFY_TOKEN", "").strip()
        or "Mimar1453"
    )
    internal_chat_base_url = (os.getenv("KASSANDRA_INTERNAL_BASE_URL", "http://127.0.0.1:8000").strip() or "http://127.0.0.1:8000").rstrip("/")

    async def _handle_whatsapp_inbound_message(message_data: Dict[str, str], correlation_id: str) -> None:
        phone = _clean_phone_digits(message_data.get("phone", ""))
        user_message = str(message_data.get("message") or "").strip()
        message_id = str(message_data.get("message_id") or "").strip()
        if not phone or not user_message:
            return

        payload = {
            "phone": phone,
            "message": user_message,
            "message_id": message_id,
        }
        try:
            async with httpx.AsyncClient(timeout=70.0) as client:
                chat_resp = await client.post(
                    f"{internal_chat_base_url}/chat",
                    json=payload,
                    headers={CORRELATION_HEADER: correlation_id},
                )
        except Exception as exc:
            log_event(
                "whatsapp.webhook.chat_call_failed",
                level="ERROR",
                correlation_id=correlation_id,
                phone=phone,
                message_id=message_id,
                error=str(exc),
            )
            return

        if chat_resp.status_code != 200:
            log_event(
                "whatsapp.webhook.chat_call_non200",
                level="ERROR",
                correlation_id=correlation_id,
                phone=phone,
                message_id=message_id,
                status_code=chat_resp.status_code,
                body=(chat_resp.text or "")[:500],
            )
            return

        try:
            chat_data = chat_resp.json()
        except Exception:
            log_event(
                "whatsapp.webhook.chat_json_invalid",
                level="ERROR",
                correlation_id=correlation_id,
                phone=phone,
                message_id=message_id,
            )
            return

        reply = str(chat_data.get("reply") or "").strip()
        status = str(chat_data.get("status") or "").strip()
        if not _should_forward_reply(status, reply):
            log_event(
                "whatsapp.webhook.reply_skipped",
                level="DEBUG",
                correlation_id=correlation_id,
                phone=phone,
                message_id=message_id,
                status=status,
            )
            return

        try:
            sent = await deps["send_whatsapp_message_fn"](phone, reply[:4096])
            if not sent:
                log_event(
                    "whatsapp.webhook.reply_send_failed",
                    level="ERROR",
                    correlation_id=correlation_id,
                    phone=phone,
                    message_id=message_id,
                    status=status,
                )
        except Exception as exc:
            log_event(
                "whatsapp.webhook.reply_send_exception",
                level="ERROR",
                correlation_id=correlation_id,
                phone=phone,
                message_id=message_id,
                status=status,
                error=str(exc),
            )

    @router.get(webhook_path)
    async def whatsapp_webhook_verify(request: Request):
        mode = str(request.query_params.get("hub.mode") or "").strip()
        token = str(request.query_params.get("hub.verify_token") or "").strip()
        challenge = str(request.query_params.get("hub.challenge") or "")
        correlation_id = (
            getattr(getattr(request, "state", object()), "correlation_id", None)
            or resolve_correlation_id(getattr(request, "headers", {}))
        )
        if mode == "subscribe" and token and token == webhook_verify_token:
            return PlainTextResponse(content=challenge, status_code=200, headers={CORRELATION_HEADER: correlation_id})
        log_event(
            "whatsapp.webhook.verify_failed",
            level="WARNING",
            correlation_id=correlation_id,
            mode=mode,
            token_provided=bool(token),
        )
        return PlainTextResponse(content="forbidden", status_code=403, headers={CORRELATION_HEADER: correlation_id})

    @router.post(webhook_path)
    async def whatsapp_webhook_ingress(request: Request, background_tasks: BackgroundTasks):
        correlation_id = (
            getattr(getattr(request, "state", object()), "correlation_id", None)
            or resolve_correlation_id(getattr(request, "headers", {}))
        )
        try:
            payload = await request.json()
        except Exception:
            log_event(
                "whatsapp.webhook.invalid_json",
                level="WARNING",
                correlation_id=correlation_id,
            )
            return PlainTextResponse(content="EVENT_RECEIVED", status_code=200, headers={CORRELATION_HEADER: correlation_id})

        inbound = _extract_whatsapp_inbound_messages(payload if isinstance(payload, dict) else {})
        for item in inbound:
            background_tasks.add_task(_handle_whatsapp_inbound_message, item, correlation_id)

        log_event(
            "whatsapp.webhook.accepted",
            correlation_id=correlation_id,
            inbound_count=len(inbound),
        )
        return PlainTextResponse(content="EVENT_RECEIVED", status_code=200, headers={CORRELATION_HEADER: correlation_id})

    @router.post("/chat", response_model=ChatResponse)
    async def chat_endpoint(payload: ChatRequest, request: Request, response: Response):
        start_time = time_module.time()
        user_message = _repair_mojibake_text((payload.message or "").strip())
        phone = (payload.phone or "").strip()
        message_id = (payload.message_id or "").strip()

        correlation_id = (
            getattr(getattr(request, "state", object()), "correlation_id", None)
            or resolve_correlation_id(getattr(request, "headers", {}))
        )
        response.headers[CORRELATION_HEADER] = correlation_id

        flow_context = RequestFlowContext(
            correlation_id=correlation_id,
            phone=phone,
            message_id=message_id or None,
            request_path=request.url.path,
            request_method=request.method,
        )

        detect_language_fn = deps["detect_language_fn"]
        load_conversation_fn = deps["load_conversation_fn"]
        initial_lang = _resolve_language_lock(phone, user_message, load_conversation_fn, detect_language_fn)

        def _locked_detect_language_fn(_: str) -> str:
            return initial_lang

        log_event(
            "chat.request.received",
            correlation_id=correlation_id,
            phone=phone,
            message_id=message_id,
            path=request.url.path,
            method=request.method,
            message_len=len(user_message),
        )
        chat_summary_ctx: Dict[str, Any] = {
            "intent": "UNRESOLVED",
            "confidence": None,
        }

        def trace_event(payload_dict):
            deps["trace_decision_fn"]({**flow_context.as_dict(), **(payload_dict or {})})

        def resp(
            reply: str,
            status: str = "ok",
            reservation_log=None,
            is_price_template: bool = False,
            reason_code: Optional[str] = None,
            next_expected_input: Optional[str] = None,
        ):
            normalized_reply = reply or ""
            if initial_lang == "tr":
                normalized_reply = _normalize_turkish_reply_text(normalized_reply)
            should_translate = not (is_price_template and initial_lang == "tr")
            if should_translate:
                normalized_reply = _translate_reply_if_needed(
                    normalized_reply,
                    initial_lang,
                    deps["openai_client"],
                    deps["openai_model"],
                    deps["detect_language_fn"],
                )
            normalized_reply = _enforce_language_lock(
                normalized_reply,
                initial_lang,
                deps["detect_language_fn"],
                deps["openai_client"],
                deps["openai_model"],
            )
            if needs_hard_language_guard(normalized_reply, initial_lang, deps["detect_language_fn"]):
                normalized_reply = _enforce_language_lock(
                    normalized_reply,
                    initial_lang,
                    deps["detect_language_fn"],
                    deps["openai_client"],
                    deps["openai_model"],
                )
            elapsed_ms = int((time_module.time() - start_time) * 1000)
            log_event(
                "chat.response",
                correlation_id=correlation_id,
                phone=phone,
                message_id=message_id,
                status=status,
                reason_code=reason_code,
                elapsed_ms=elapsed_ms,
            )
            log_event(
                "chat.summary",
                correlation_id=correlation_id,
                phone=phone,
                message_id=message_id,
                locked_lang=initial_lang,
                normalized_intent=chat_summary_ctx.get("intent") or "UNRESOLVED",
                intent=chat_summary_ctx.get("intent") or "UNRESOLVED",
                confidence=chat_summary_ctx.get("confidence"),
                status=status,
                reason_code=reason_code,
                handoff="yes" if str(status or "").strip().lower() == "handoff" else "no",
                elapsed_ms=elapsed_ms,
            )
            return ChatResponse(
                reply=normalized_reply,
                status=status,
                reservation_log=reservation_log,
                is_price_template=is_price_template,
                reason_code=reason_code,
                next_expected_input=next_expected_input,
            )

        # STAGE 1: Ingress
        if phone and message_id and deps["is_processed_message_id_fn"](phone, message_id):
            trace_event({"stage": "ingress", "event": "duplicate_message_id"})
            return resp(reply="", status="duplicate_message_id")
        if phone and message_id:
            deps["mark_message_id_processed_fn"](phone, message_id)

        # STAGE 2: Context/State Builder + STAGE 4: Gating/Moderation
        precheck = await deps["run_chat_prechecks_fn"](
            phone=phone,
            user_message=user_message,
            detect_language_fn=_locked_detect_language_fn,
            load_conversation_fn=deps["load_conversation_fn"],
            notify_admin_error_fn=deps["notify_admin_error_fn"],
            save_message_fn=deps["save_message_fn"],
            is_safe_mode_fn=deps["is_safe_mode_fn"],
            is_auto_safe_mode_fn=deps["is_auto_safe_mode_fn"],
            check_rate_limit_fn=deps["check_rate_limit_fn"],
            is_automation_enabled_fn=deps["is_automation_enabled_fn"],
            is_operational_rules_enabled_fn=deps.get("is_operational_rules_enabled_fn", lambda: True),
            is_blacklisted_fn=deps["is_blacklisted_fn"],
            is_paused_fn=deps["is_paused_fn"],
            cancel_followup_fn=deps["cancel_followup_fn"],
            get_conversation_history_fn=deps["get_conversation_history_fn"],
            handle_cancel_flow_v2_fn=deps["handle_cancel_flow_v2_fn"],
            detect_suspicious_message_fn=deps["detect_suspicious_message_fn"],
            notify_admin_suspicious_fn=deps["notify_admin_suspicious_fn"],
            ai_question_response=deps["ai_question_response"],
            suspicious_response=deps["suspicious_response"],
            add_to_history_fn=deps["add_to_history_fn"],
            detect_critical_issue_fn=deps["detect_critical_issue_fn"],
            send_critical_notification_fn=deps["send_critical_notification_fn"],
            response_factory=resp,
            notify_admin_handoff_fn=deps["notify_admin_handoff_fn"],
            activate_human_takeover_fn=deps.get("activate_human_takeover_fn", lambda *_a, **_k: None),
            flow_context=flow_context,
        )
        if precheck["response"] is not None:
            trace_event({"stage": "gating", "event": "blocked", "status": getattr(precheck["response"], "status", "")})
            return precheck["response"]

        lang = _normalize_language_code(precheck.get("lang") or initial_lang)
        history = precheck.get("history") or []
        pending_payment_ctx = get_payment_context(phone) or {}

        local_faq_match: Dict[str, Any] = {
            "found": False,
            "answer_tr": "",
            "answer_en": "",
            "answer_ru": "",
        }
        local_faq_fn = deps.get("check_local_faq_fn")
        if callable(local_faq_fn):
            try:
                found, answer_tr, answer_en, _category, answer_ru = local_faq_fn(user_message)
                local_faq_match = {
                    "found": bool(found),
                    "answer_tr": str(answer_tr or ""),
                    "answer_en": str(answer_en or ""),
                    "answer_ru": str(answer_ru or ""),
                }
            except Exception:
                local_faq_match = {
                    "found": False,
                    "answer_tr": "",
                    "answer_en": "",
                    "answer_ru": "",
                }

        def _resolve_local_faq_reply() -> str:
            if not local_faq_match.get("found"):
                return ""
            if lang == "en":
                return str(local_faq_match.get("answer_en") or local_faq_match.get("answer_tr") or "")
            if lang == "ru":
                return str(
                    local_faq_match.get("answer_ru")
                    or local_faq_match.get("answer_en")
                    or local_faq_match.get("answer_tr")
                    or ""
                )
            return str(local_faq_match.get("answer_tr") or local_faq_match.get("answer_en") or "")

        skip_local_faq_for_booking = _should_skip_local_faq_for_booking(user_message)

        # Konusma devam ederken yakalanan deterministic FAQ'lari strict-ai-first'ten once cevapla.
        if history and local_faq_match.get("found") and not skip_local_faq_for_booking:
            local_reply = _resolve_local_faq_reply()
            if local_reply:
                deps["add_to_history_fn"](phone, "user", user_message)
                deps["add_to_history_fn"](phone, "assistant", local_reply)
                deps["save_message_fn"](phone, user_message, local_reply)
                deps["schedule_followup_fn"](phone)
                deps["record_metric_fn"](
                    "local_faq",
                    response_time=time_module.time() - start_time,
                )
                return resp(reply=local_reply, status="local_faq")

        if (
            not history
            and _should_send_first_message_welcome(user_message)
            and not _looks_like_booking_payment_followup(user_message)
        ):
            welcome_reply = deps["get_welcome_message_fn"](lang)
            deps["add_to_history_fn"](phone, "user", user_message)
            deps["add_to_history_fn"](phone, "assistant", welcome_reply)
            deps["save_message_fn"](phone, user_message, welcome_reply)
            deps["schedule_followup_fn"](phone)
            deps["record_metric_fn"]("first_message", response_time=time_module.time() - start_time)
            trace_event({"stage": "response_generator", "event": "first_message_welcome"})
            return resp(reply=welcome_reply, status="first_message")

        reservation_flow_state = deps["get_reservation_flow_fn"](phone)
        price_flow_state = deps["get_price_flow_fn"](phone)
        booking_flow_state = deps["get_booking_flow_fn"](phone)
        active_domain_flow = deps["get_active_flow_fn"](phone)

        # Aktif flow varsa mesaj bazli dil algisini ez: flow'da kayitli dili kullan.
        # Bu, "geç"/telefon gibi kisa veya bozuk kodlamali girdilerde dil kaymasini engeller.
        for flow_candidate in (booking_flow_state, reservation_flow_state, price_flow_state):
            if _has_non_idle_state(flow_candidate):
                flow_lang = _extract_locked_lang_from_flow(flow_candidate)
                if flow_lang:
                    initial_lang = flow_lang
                    break

        has_active_domain_flow = bool(
            _has_non_idle_state(reservation_flow_state)
            or _has_non_idle_state(price_flow_state)
            or _has_non_idle_state(booking_flow_state)
            or bool(active_domain_flow)
        )

        has_price_slot_followup_with_history = _looks_like_price_slot_followup_with_history(user_message, history)
        if strict_ai_first and not (
            has_active_domain_flow
            or _should_bypass_strict_ai_first(user_message)
            or _has_recent_reservation_contact_prompt(history)
            or has_price_slot_followup_with_history
            or bool(local_faq_match.get("found"))
            or bool(pending_payment_ctx)
        ):
            chat_summary_ctx["intent"] = "AI_FALLBACK"
            chat_summary_ctx["confidence"] = None
            trace_event({"stage": "response_generator", "event": "strict_ai_first"})
            return await deps["handle_openai_fallback_fn"](
                client=deps["openai_client"],
                openai_model=deps["openai_model"],
                info_system_prompt=deps["info_system_prompt"],
                history=history,
                user_message=user_message,
                phone=phone,
                start_time=start_time,
                add_to_history_fn=deps["add_to_history_fn"],
                save_message_fn=deps["save_message_fn"],
                schedule_followup_fn=deps["schedule_followup_fn"],
                record_metric_fn=deps["record_metric_fn"],
                maybe_start_qa_background_fn=deps["maybe_start_qa_background_fn"],
                qa_enabled=deps["qa_enabled"],
                qa_agent=deps["qa_agent"],
                admin_phone=deps["admin_phone"],
                send_whatsapp_message_fn=deps["send_whatsapp_message_fn"],
                qa_fail_notifications=deps["qa_fail_notifications"],
                record_error_fn=deps["record_error_fn"],
                response_factory=resp,
                flow_context=flow_context,
                notify_admin_handoff_fn=deps.get("notify_admin_handoff_fn"),
                activate_human_takeover_fn=deps.get("activate_human_takeover_fn"),
                detected_intent="AI_FALLBACK",
                handoff_source="chat_pipeline.strict_ai_first",
            )
        if strict_ai_first:
            trace_event(
                {
                    "stage": "response_generator",
                    "event": "strict_ai_first_bypassed_for_domain_flow",
                    "has_active_domain_flow": has_active_domain_flow,
                }
            )

        # STAGE 3: Sentiment & Frustration
        sf = _compute_sentiment_and_frustration(user_message, history)
        trace_event({"stage": "sentiment", **sf})

        # Explicit language switch
        switch_target, switch_supported = _extract_language_switch_request(user_message)
        if switch_target:
            switch_reply = _language_switch_confirmation(switch_target, switch_supported)
            deps["add_to_history_fn"](phone, "user", user_message)
            deps["add_to_history_fn"](phone, "assistant", switch_reply)
            deps["save_message_fn"](phone, user_message, switch_reply)
            deps["schedule_followup_fn"](phone)
            deps["record_metric_fn"]("language_switch", category=switch_target, response_time=time_module.time() - start_time)
            trace_event({"stage": "context", "event": "language_switch", "target": switch_target, "supported": switch_supported})
            return resp(
                reply=switch_reply,
                status="language_switch",
                reason_code="language_switch_supported" if switch_supported else "language_switch_unsupported",
            )

        if new_pipeline_enabled:
            policy = evaluate_policy_guard(user_message, lang=initial_lang)
            trace_event({"stage": "policy_guard", "enabled": True, "handled": bool(policy.get("handled")), "meta": policy.get("meta")})
            if policy.get("handled"):
                deps["add_to_history_fn"](phone, "user", user_message)
                deps["add_to_history_fn"](phone, "assistant", policy.get("reply", ""))
                deps["save_message_fn"](phone, user_message, policy.get("reply", ""))
                deps["schedule_followup_fn"](phone)
                deps["record_metric_fn"]("policy_guard", category=policy.get("status", "policy_guard"), response_time=time_module.time() - start_time)
                return resp(
                    reply=policy.get("reply", ""),
                    status=policy.get("status", "policy_guard"),
                    reason_code=policy.get("reason_code"),
                )

        # STAGE 5: Intent + Routing
        domain_hint = infer_domain_hint(user_message) if new_pipeline_enabled else _domain_hint_from_message(user_message)
        if new_pipeline_enabled:
            routed = route_intent(user_message, domain_hint)
            primary_intent = routed["primary_intent"]
            if str(primary_intent or "").upper() == "OUT_OF_SCOPE_OTHER" and _looks_like_price_slot_payload(user_message):
                # "23-26 Ağustos, 4 yetişkin" gibi takip payload'larını yanlışlıkla
                # out-of-scope sınıfına düşürme; fiyat akışına geri yönlendir.
                primary_intent = "PRICE_QUERY"
                routed["primary_intent"] = "PRICE_QUERY"
                routed["semantic_intent"] = routed.get("semantic_intent") or "PRICE_QUERY"
            if str(primary_intent or "").upper() == "OUT_OF_SCOPE_OTHER" and history:
                merged_slot_text = _merge_slot_context_from_history(user_message, history)
                merged_price_coverage = evaluate_slot_coverage("PRICE_QUERY", merged_slot_text)
                merged_missing = merged_price_coverage.get("missing_required_slots", []) or []
                if not merged_missing:
                    # Kullanıcı ikinci mesajda eksik slotları tamamladıysa fiyat akışına dön.
                    primary_intent = "PRICE_QUERY"
                    routed["primary_intent"] = "PRICE_QUERY"
                    routed["semantic_intent"] = routed.get("semantic_intent") or "PRICE_QUERY"
            primary_intent = _force_primary_intent_from_explicit_message(user_message, str(primary_intent or ""))
            if (
                str(primary_intent or "").upper() not in {"PRICE_QUERY", "AVAILABILITY_QUERY"}
                and _looks_like_generic_price_or_availability_signal(user_message)
                and bool(re.search(r"[\u4e00-\u9fff]", str(user_message or "")))
            ):
                # CJK fiyat sinyallerinde semantic router bazen OUT_OF_SCOPE/GENERIC dönebiliyor.
                # Bu durumda fiyat akışını zorunlu başlat.
                primary_intent = "PRICE_QUERY"
                routed["primary_intent"] = "PRICE_QUERY"
                routed["semantic_intent"] = routed.get("semantic_intent") or "PRICE_QUERY"
            if (
                str(primary_intent or "").upper() in {"PRICE_QUERY", "AVAILABILITY_QUERY"}
                and _looks_like_explicit_booking_create_signal(user_message)
                and not _looks_like_generic_price_or_availability_signal(user_message)
            ):
                primary_intent = "HOTEL_BOOKING_CREATE"
            routed["primary_intent"] = primary_intent
            chat_summary_ctx["intent"] = primary_intent
            chat_summary_ctx["confidence"] = float(routed.get("semantic_confidence") or 0.0)
            trace_event({"stage": "intent_router", "enabled": True, **routed})
        else:
            primary_intent = infer_primary_intent(user_message, domain_hint)
            routed = {
                "primary_intent": primary_intent,
                "domain_hint": domain_hint,
                "semantic_intent": primary_intent,
                "semantic_confidence": 1.0,
                "router": "legacy_intent_policy",
            }
            chat_summary_ctx["intent"] = primary_intent
            chat_summary_ctx["confidence"] = 1.0
        primary_intent = _force_primary_intent_from_explicit_message(user_message, str(primary_intent or ""))
        if (
            str(primary_intent or "").upper() in {"PRICE_QUERY", "AVAILABILITY_QUERY"}
            and _looks_like_explicit_booking_create_signal(user_message)
            and not _looks_like_generic_price_or_availability_signal(user_message)
        ):
            primary_intent = "HOTEL_BOOKING_CREATE"
        if _looks_like_booking_payment_followup(user_message):
            # "kapora/odeme/link" takip sorularini fiyat slot-clarify dongusune dusurme.
            primary_intent = "PAYMENT_METHOD_QUERY"
        if (
            str(primary_intent or "").upper() in {"PRICE_QUERY", "AVAILABILITY_QUERY"}
            and _looks_like_phone_number_payload(user_message)
            and _has_recent_reservation_contact_prompt(history)
        ):
            # Rezervasyon bilgi toplama adiminda paylasilan telefon numarasini
            # fiyat payload'i gibi yorumlama.
            domain = _recent_reservation_prompt_domain(history)
            if domain == "restaurant":
                primary_intent = "RESTAURANT_BOOKING_CREATE"
            elif domain == "transfer":
                primary_intent = "TRANSFER_BOOKING_REQUEST"
            else:
                primary_intent = "HOTEL_BOOKING_CREATE"
        routed["primary_intent"] = primary_intent
        if _looks_like_late_checkin_info_query(user_message):
            primary_intent = "LOCAL_FAQ_INFO"
            routed["primary_intent"] = "LOCAL_FAQ_INFO"
            routed["semantic_intent"] = routed.get("semantic_intent") or "LOCAL_FAQ_INFO"
            chat_summary_ctx["intent"] = primary_intent
        slot_coverage = evaluate_slot_coverage(primary_intent, user_message)
        if _looks_like_room_booking_create_request(user_message) or _looks_like_direct_room_booking_create_request(user_message):
            primary_intent = "HOTEL_BOOKING_CREATE"
            routed["primary_intent"] = "HOTEL_BOOKING_CREATE"
            slot_coverage = evaluate_slot_coverage(primary_intent, user_message)
        if str(primary_intent or "").upper() in {"PRICE_QUERY", "AVAILABILITY_QUERY", "HOTEL_BOOKING_CREATE"}:
            missing_now = slot_coverage.get("missing_required_slots", []) or []
            if missing_now and history:
                merged_slot_text = _merge_slot_context_from_history(user_message, history)
                merged_coverage = evaluate_slot_coverage(primary_intent, merged_slot_text)
                merged_missing = merged_coverage.get("missing_required_slots", []) or []
                if len(merged_missing) < len(missing_now):
                    slot_coverage = merged_coverage
        trace_event(
            {
                "stage": "intent_routing",
                "primary_intent": primary_intent,
                "domain_hint": domain_hint,
                "slot_coverage": slot_coverage,
            }
        )
        capture_active_learning_fn = deps.get("capture_active_learning_fn")
        semantic_confidence = float(routed.get("semantic_confidence") or 0.0)
        is_novel_topic = primary_intent == "OUT_OF_SCOPE_OTHER"
        is_low_confidence = semantic_confidence < float(INTENT_AUTO_CONFIDENCE_THRESHOLD)
        if callable(capture_active_learning_fn):
            if is_novel_topic or is_low_confidence:
                reason = "novel_topic_out_of_scope" if is_novel_topic else "low_confidence_below_auto_threshold"
                capture_active_learning_fn(
                    phone=phone,
                    message=user_message,
                    stage="intent_router_v2",
                    lang=initial_lang,
                    predicted_intent=primary_intent,
                    confidence=semantic_confidence,
                    reason=reason,
                    metadata={
                        "domain_hint": domain_hint,
                        "slot_coverage": slot_coverage,
                        "semantic_intent": routed.get("semantic_intent"),
                        "router": routed.get("router"),
                    },
                )

        has_active_flow = bool(
            bool(active_domain_flow)
            or _has_non_idle_state(reservation_flow_state)
            or _has_non_idle_state(price_flow_state)
            or _has_non_idle_state(booking_flow_state)
        )

        # Kesin olarak yanıtlanamayan konularda müşteri doğrudan canlı ekibe aktarılır.
        unknown_guard_should_handoff = is_novel_topic or (
            is_low_confidence and str(primary_intent or "").upper() not in KNOWN_AUTO_INTENTS
        )
        if _looks_like_late_checkin_info_query(user_message):
            unknown_guard_should_handoff = False
        if unknown_guard_should_handoff and not has_active_flow and not bool(pending_payment_ctx):
            reason = "novel_topic_out_of_scope" if is_novel_topic else "low_confidence_below_auto_threshold"
            try:
                await deps["notify_admin_handoff_fn"](
                    category="canli_destek",
                    priority="high",
                    customer_phone=phone,
                    customer_message=user_message,
                    source="chat_pipeline.unknown_guard",
                    detected_intent=primary_intent,
                    confidence=semantic_confidence,
                    conversation_summary=reason,
                    attempted_actions=["intent_router_v2", "unknown_guard_handoff"],
                    suggested_reply="Net olmayan talep canlı desteğe aktarıldı.",
                    tags=["unknown_guard", reason],
                    correlation_id=correlation_id,
                )
            except Exception:
                pass
            try:
                deps.get("activate_human_takeover_fn", lambda *_a, **_k: None)(
                    phone, reason=f"unknown_guard:{reason}"
                )
            except Exception:
                pass
            handoff_reply = _get_unknown_handoff_reply(initial_lang)
            deps["add_to_history_fn"](phone, "user", user_message)
            deps["add_to_history_fn"](phone, "assistant", handoff_reply)
            deps["save_message_fn"](phone, user_message, handoff_reply)
            deps["schedule_followup_fn"](phone)
            deps["record_metric_fn"]("handoff", category="unknown_guard", response_time=time_module.time() - start_time)
            return resp(reply=handoff_reply, status="handoff", reason_code=reason)

        skip_slot_clarify_for_explicit_booking_start = (
            str(primary_intent or "").upper() == "HOTEL_BOOKING_CREATE"
            and _looks_like_explicit_booking_create_signal(user_message)
        )
        if (
            should_request_slot_clarification(primary_intent, slot_coverage, has_active_flow=has_active_flow)
            and not skip_slot_clarify_for_explicit_booking_start
        ):
            clarify_prompt = get_missing_slot_prompt(primary_intent) or "Lutfen eksik bilgileri tamamlayin."
            deps["add_to_history_fn"](phone, "user", user_message)
            deps["add_to_history_fn"](phone, "assistant", clarify_prompt)
            deps["save_message_fn"](phone, user_message, clarify_prompt)
            deps["record_metric_fn"]("clarify_loop", category=primary_intent, response_time=time_module.time() - start_time)
            return resp(reply=clarify_prompt, status="clarify_required", reason_code="missing_required_slots")

        # STAGE 6: Tool/Flow Executor
        needs_handoff, handoff_category, handoff_priority, handoff_msg_tr, handoff_msg_en, handoff_msg_ru = deps[
            "detect_handoff_required_fn"
        ](user_message)
        if pending_payment_ctx:
            # Payment continuation turns (e.g. "273 TRY") can look ambiguous in isolation;
            # keep flow continuity and avoid premature human handoff.
            needs_handoff = False

        reservation_flow_active = _has_non_idle_state(reservation_flow_state)
        if _is_restaurant_flow_intent(primary_intent) or reservation_flow_active:
            restaurant_response = await deps["try_start_restaurant_reservation_flow_fn"](
                needs_handoff=needs_handoff,
                handoff_category=handoff_category,
                user_message=user_message,
                phone=phone,
                start_time=start_time,
                history=history,
                restaurant_settings=deps["restaurant_settings"],
                clear_reservation_flow_fn=deps["clear_reservation_flow_fn"],
                notify_admin_handoff_fn=deps["notify_admin_handoff_fn"],
                detect_language_fn=_locked_detect_language_fn,
                add_to_history_fn=deps["add_to_history_fn"],
                save_message_fn=deps["save_message_fn"],
                response_factory=resp,
                extract_date_from_message_fn=deps["extract_date_from_message_fn"],
                parse_date_input_fn=deps["parse_date_input_fn"],
                extract_date_phrase_fn=deps["extract_date_phrase_fn"],
                is_within_season_fn=deps["is_within_season_fn"],
                extract_time_from_message_fn=deps["extract_time_from_message_fn"],
                get_meal_type_from_time_fn=deps["get_meal_type_from_time_fn"],
                update_reservation_flow_fn=deps["update_reservation_flow_fn"],
                reservation_state_cls=deps["reservation_state_cls"],
                record_metric_fn=deps["record_metric_fn"],
            )
            if restaurant_response is not None:
                return restaurant_response
        else:
            trace_event(
                {
                    "stage": "restaurant_flow_gate",
                    "event": "intent_blocked",
                    "primary_intent": primary_intent,
                }
            )

        handoff_or_reservation = await deps["try_handle_handoff_and_reservation_flow_fn"](
            needs_handoff=needs_handoff,
            handoff_category=handoff_category,
            handoff_priority=handoff_priority,
            handoff_msg_tr=handoff_msg_tr,
            handoff_msg_en=handoff_msg_en,
            handoff_msg_ru=handoff_msg_ru,
            user_message=user_message,
            phone=phone,
            start_time=start_time,
            notify_admin_handoff_fn=deps["notify_admin_handoff_fn"],
            detect_language_fn=_locked_detect_language_fn,
            add_to_history_fn=deps["add_to_history_fn"],
            save_message_fn=deps["save_message_fn"],
            record_metric_fn=deps["record_metric_fn"],
            get_reservation_flow_fn=deps["get_reservation_flow_fn"],
            reservation_state_cls=deps["reservation_state_cls"],
            handle_reservation_flow_fn=deps["handle_reservation_flow_fn"],
            response_factory=resp,
            flow_context=flow_context,
        )
        if handoff_or_reservation is not None:
            return handoff_or_reservation

        async def _run_booking_chain():
            booking_flow_active = _has_non_idle_state(booking_flow_state)
            booking_followup_hint = _looks_like_booking_payment_followup(user_message)
            has_payment_context = bool(pending_payment_ctx)
            explicit_booking_signal = (
                _looks_like_explicit_booking_create_signal(user_message)
                or _looks_like_direct_room_booking_create_request(user_message)
                or _looks_like_room_booking_create_request(user_message)
            )
            if not (
                _is_booking_flow_intent(primary_intent)
                or booking_flow_active
                or booking_followup_hint
                or has_payment_context
                or explicit_booking_signal
            ):
                trace_event(
                    {
                        "stage": "booking_flow_gate",
                        "event": "intent_blocked",
                        "primary_intent": primary_intent,
                        "booking_followup_hint": booking_followup_hint,
                        "has_payment_context": has_payment_context,
                        "explicit_booking_signal": explicit_booking_signal,
                    }
                )
                return None

            booking_entry = await deps["try_handle_booking_flow_entry_fn"](
                phone=phone,
                user_message=user_message,
                history=history,
                start_time=start_time,
                detect_language_fn=_locked_detect_language_fn,
                handle_booking_flow_fn=deps["handle_booking_flow_fn"],
                add_to_history_fn=deps["add_to_history_fn"],
                save_message_fn=deps["save_message_fn"],
                record_metric_fn=deps["record_metric_fn"],
                send_whatsapp_message_fn=deps["send_whatsapp_message_fn"],
                admin_phone=deps["admin_phone"],
                response_factory=resp,
            )
            if booking_entry is not None:
                return booking_entry

            booking_flow_result = await deps["handle_booking_flow_fn"](phone, user_message, history=history, lang=lang)
            if booking_flow_result is not None:
                if isinstance(booking_flow_result, dict):
                    return resp(
                        reply=booking_flow_result.get("reply", ""),
                        status=booking_flow_result.get("status", "booking_flow"),
                        reservation_log=booking_flow_result.get("log"),
                    )
                return booking_flow_result
            return None

        async def _run_price_chain():
            price_flow_active = _has_non_idle_state(price_flow_state)
            if _looks_like_phone_number_payload(user_message) and not _looks_like_generic_price_or_availability_signal(user_message):
                trace_event(
                    {
                        "stage": "price_flow_gate",
                        "event": "contact_payload_skip",
                        "primary_intent": primary_intent,
                    }
                )
                return None
            if price_flow_active and _is_price_flow_pivot_message(user_message):
                trace_event(
                    {
                        "stage": "price_flow_gate",
                        "event": "pivot_message_skip",
                        "primary_intent": primary_intent,
                    }
                )
                return None
            if not (_is_price_flow_intent(primary_intent) or price_flow_active):
                trace_event(
                    {
                        "stage": "price_flow_gate",
                        "event": "intent_blocked",
                        "primary_intent": primary_intent,
                    }
                )
                return None
            price_entry = await deps["try_handle_price_flow_entry_fn"](
                phone=phone,
                user_message=user_message,
                history=history,
                lang=lang,
                start_time=start_time,
                handle_price_flow_fn=deps["handle_price_flow_fn"],
                notify_admin_handoff_fn=deps["notify_admin_handoff_fn"],
                notify_admin_error_fn=deps["notify_admin_error_fn"],
                add_to_history_fn=deps["add_to_history_fn"],
                save_message_fn=deps["save_message_fn"],
                schedule_followup_fn=deps["schedule_followup_fn"],
                record_metric_fn=deps["record_metric_fn"],
                handle_booking_flow_fn=deps["handle_booking_flow_fn"],
                detect_language_fn=_locked_detect_language_fn,
                response_factory=resp,
            )
            if price_entry is not None:
                return price_entry

            price_flow_result = await deps["handle_price_flow_fn"](
                phone=phone,
                message=user_message,
                history=history,
                lang=lang,
            )
            if price_flow_result is not None:
                return price_flow_result
            return None

        if new_pipeline_enabled:
            fsm_decision = decide_execution_order(
                primary_intent=primary_intent,
                active_flow=active_domain_flow,
                booking_flow_active=_has_non_idle_state(booking_flow_state),
                price_flow_active=_has_non_idle_state(price_flow_state),
            )
            trace_event({"stage": "flow_fsm", "enabled": True, **fsm_decision})
            execution_order = fsm_decision.get("order") or ["booking", "price"]
        else:
            execution_order = ["booking", "price"]

        for chain in execution_order:
            if chain == "price":
                result = await _run_price_chain()
            else:
                result = await _run_booking_chain()
            if result is not None:
                return result

        if _is_price_flow_intent(primary_intent):
            elektra_entry = await deps["try_handle_elektra_price_entry_fn"](
                phone=phone,
                user_message=user_message,
                history=history,
                locked_lang=initial_lang,
                detect_price_request_fn=deps["detect_price_request_fn"],
                is_price_flow_active_fn=deps["is_price_flow_active_fn"],
                detect_language_fn=_locked_detect_language_fn,
                handle_elektra_price_request_fn=deps["handle_elektra_price_request_fn"],
                notify_admin_handoff_fn=deps["notify_admin_handoff_fn"],
                add_to_history_fn=deps["add_to_history_fn"],
                save_message_fn=deps["save_message_fn"],
                schedule_followup_fn=deps["schedule_followup_fn"],
                response_factory=resp,
                notify_admin_error_fn=deps["notify_admin_error_fn"],
                eleltra_config_error_cls=deps["elektra_config_error_cls"],
                natural_date_keywords=deps["price_natural_date_keywords"],
                price_inquiry_keywords=deps["price_inquiry_keywords"],
                guest_keywords=deps["price_guest_keywords"],
            )
            if elektra_entry is not None:
                return elektra_entry
        else:
            trace_event(
                {
                    "stage": "elektra_price_gate",
                    "event": "intent_blocked",
                    "primary_intent": primary_intent,
                }
            )

        # Fiyat/müsaitlik taleplerinde Elektra sonucu yoksa asla LLM fiyat cevabı üretme.
        direct_booking_create = _looks_like_direct_room_booking_create_request(user_message)
        explicit_booking_create = (
            _looks_like_explicit_booking_create_signal(user_message)
            or _looks_like_room_booking_create_request(user_message)
            or direct_booking_create
        )
        price_signal = (
            (_is_price_flow_intent(primary_intent) and not explicit_booking_create)
            or _looks_like_generic_price_or_availability_signal(user_message)
        ) and not direct_booking_create
        if price_signal:
            # Oda ozellik-fark karsilastirmalarinda teknik hata vermek yerine
            # slot tamamlatma sorusu ile akisi canli tut.
            if _looks_like_room_feature_price_comparison(user_message) and not _looks_like_price_slot_payload(user_message):
                clarify_prompt = get_missing_slot_prompt("PRICE_QUERY") or "Lutfen eksik bilgileri tamamlayin."
                deps["add_to_history_fn"](phone, "user", user_message)
                deps["add_to_history_fn"](phone, "assistant", clarify_prompt)
                deps["save_message_fn"](phone, user_message, clarify_prompt)
                deps["record_metric_fn"]("clarify_loop", category="PRICE_QUERY", response_time=time_module.time() - start_time)
                return resp(reply=clarify_prompt, status="clarify_required", reason_code="missing_required_slots")

            safe_reply = _price_engine_unavailable_reply(lang)
            try:
                notify_result = deps["notify_admin_handoff_fn"](
                    category="fiyat_sistemi_hatasi",
                    priority="high",
                    customer_phone=phone or "Bilinmiyor",
                    customer_message=user_message,
                    source="chat_pipeline.price_fallback_guard",
                    detected_intent="PRICE_QUERY",
                    confidence=0.90,
                    conversation_summary=f"price_chain_no_result intent={primary_intent}",
                    attempted_actions=["intent_router_v2", "price_chain_no_result_guard"],
                    suggested_reply=safe_reply[:240],
                    tags=["price_flow", "elektra_unavailable", "handoff"],
                )
                if inspect.isawaitable(notify_result):
                    await notify_result
            except Exception:
                pass
            try:
                deps.get("activate_human_takeover_fn", lambda *_a, **_k: None)(
                    phone, reason="price_flow:elektra_unavailable"
                )
            except Exception:
                pass
            deps["add_to_history_fn"](phone, "user", user_message)
            deps["add_to_history_fn"](phone, "assistant", safe_reply)
            deps["save_message_fn"](phone, user_message, f"[ELEKTRAWEB_PRICE_UNAVAILABLE] {safe_reply}")
            deps["schedule_followup_fn"](phone)
            deps["record_metric_fn"](
                "handoff",
                category="elektra_price_unavailable",
                response_time=time_module.time() - start_time,
            )
            return resp(reply=safe_reply, status="handoff", reason_code="elektra_price_unavailable")

        late_response = deps["try_handle_late_message_checks_fn"](
            phone=phone,
            user_message=user_message,
            history=history,
            start_time=start_time,
            is_conversation_ending_fn=deps["is_conversation_ending_fn"],
            get_closing_message_fn=deps["get_closing_message_fn"],
            parse_turkish_date_fn=deps["parse_turkish_date_fn"],
            is_hotel_open_fn=deps["is_hotel_open_fn"],
            format_date_turkish_fn=deps["format_date_turkish_fn"],
            get_welcome_message_fn=deps["get_welcome_message_fn"],
            is_greeting_fn=deps["is_greeting_fn"],
            is_menu_selection_fn=deps["is_menu_selection_fn"],
            get_menu_response_fn=deps["get_menu_response_fn"],
            add_to_history_fn=deps["add_to_history_fn"],
            save_message_fn=deps["save_message_fn"],
            schedule_followup_fn=deps["schedule_followup_fn"],
            record_metric_fn=deps["record_metric_fn"],
            detect_language_fn=_locked_detect_language_fn,
            response_factory=resp,
        )
        if late_response is not None:
            return late_response

        # STAGE 7: Deterministic local FAQ (canonical flow removed)
        local_reply = _resolve_local_faq_reply()
        if local_reply and not skip_local_faq_for_booking:
            deps["add_to_history_fn"](phone, "user", user_message)
            deps["add_to_history_fn"](phone, "assistant", local_reply)
            deps["save_message_fn"](phone, user_message, local_reply)
            deps["schedule_followup_fn"](phone)
            deps["record_metric_fn"](
                "local_faq",
                response_time=time_module.time() - start_time,
            )
            return resp(reply=local_reply, status="local_faq")

        # STAGE 8: Postcheck (basit kural: dusuk confidence + negatif duygu -> handoff)
        if sf["sentiment"] == "neg" and sf["intensity"] >= 0.75 and sf["frustration_loop"]:
            try:
                await deps["notify_admin_handoff_fn"](
                    category="canli_destek",
                    priority="high",
                    customer_phone=phone,
                    customer_message=user_message,
                    source="chat_pipeline.postcheck",
                    detected_intent=primary_intent,
                    confidence=0.4,
                    conversation_summary="negative sentiment + frustration loop",
                    attempted_actions=["postcheck_sentiment_guard"],
                    suggested_reply="Musteriye insan destegi sunuldu.",
                    tags=["postcheck", "sentiment_guard"],
                    correlation_id=correlation_id,
                )
            except Exception:
                pass
            handoff_reply = "I am connecting you to our live support team."
            deps["add_to_history_fn"](phone, "user", user_message)
            deps["add_to_history_fn"](phone, "assistant", handoff_reply)
            deps["save_message_fn"](phone, user_message, handoff_reply)
            return resp(reply=handoff_reply, status="handoff", reason_code="postcheck_sentiment_guard")

        # STAGE 9: Auto reply via LLM fallback
        return await deps["handle_openai_fallback_fn"](
            client=deps["openai_client"],
            openai_model=deps["openai_model"],
            info_system_prompt=deps["info_system_prompt"],
            history=history,
            user_message=user_message,
            phone=phone,
            start_time=start_time,
            add_to_history_fn=deps["add_to_history_fn"],
            save_message_fn=deps["save_message_fn"],
            schedule_followup_fn=deps["schedule_followup_fn"],
            record_metric_fn=deps["record_metric_fn"],
            maybe_start_qa_background_fn=deps["maybe_start_qa_background_fn"],
            qa_enabled=deps["qa_enabled"],
            qa_agent=deps["qa_agent"],
            admin_phone=deps["admin_phone"],
            send_whatsapp_message_fn=deps["send_whatsapp_message_fn"],
            qa_fail_notifications=deps["qa_fail_notifications"],
            record_error_fn=deps["record_error_fn"],
            response_factory=resp,
            flow_context=flow_context,
            notify_admin_handoff_fn=deps.get("notify_admin_handoff_fn"),
            activate_human_takeover_fn=deps.get("activate_human_takeover_fn"),
            detected_intent=primary_intent,
            handoff_source="chat_pipeline.stage9_fallback",
        )

    return router
