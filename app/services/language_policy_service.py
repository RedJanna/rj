from __future__ import annotations

import re
from typing import Callable

LANGUAGE_PRIORITY = ["en", "tr", "ru", "de", "ar", "es", "fr", "zh", "hi", "pt"]

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

TR_ASCII_SIGNAL_WORDS = {
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


def normalize_language_code(lang: str) -> str:
    code = (lang or "").strip().lower()
    return code if code in LANGUAGE_PRIORITY else "en"


def extract_language_switch_request(text: str) -> tuple[str, bool]:
    low = (text or "").strip().lower()
    if not low:
        return "", False
    has_marker = any(marker in low for marker in LANGUAGE_SWITCH_MARKERS) or "?" in low
    for lang, aliases in LANGUAGE_NAME_ALIASES.items():
        if any(alias in low for alias in aliases) and has_marker:
            return lang, True
    if has_marker and any(hint in low for hint in UNSUPPORTED_LANGUAGE_HINTS):
        return "en", False
    return "", False


def extract_language_from_switch_confirmation(text: str) -> str:
    low = (text or "").strip().lower()
    if not low:
        return ""
    if "türkçe devam" in low or "turkce devam" in low:
        return "tr"
    if "continue in english" in low:
        return "en"
    if "продолжить на русском" in low:
        return "ru"
    return ""


def looks_like_turkish_ascii_message(text: str) -> bool:
    raw = (text or "").strip().lower()
    if not raw:
        return False
    if any(ch in raw for ch in ("ğ", "ı", "ş")):
        return True
    tokens = re.findall(r"[a-zA-Z]+", raw)
    if not tokens:
        return False
    hits = sum(1 for token in tokens if token in TR_ASCII_SIGNAL_WORDS)
    return hits >= 2


def contains_turkish_chars(text: str) -> bool:
    return bool(re.search(r"[ığşİĞŞ]", text or ""))


def is_ambiguous_lang_message(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    if re.fullmatch(r"[\d\W_]+", t):
        return True
    low = t.lower()
    token = re.sub(
        r"[^\w\u00C0-\u024F\u0400-\u04FF\u0600-\u06FF\u0900-\u097F\u4e00-\u9fff]+",
        "",
        low,
    )
    short_ack_tokens = {
        "yes",
        "no",
        "ok",
        "okay",
        "evet",
        "hayir",
        "hayır",
        "tamam",
        "olur",
        "yok",
        "sim",
        "si",
        "oui",
        "ja",
        "nein",
        "да",
        "нет",
    }
    if token in short_ack_tokens:
        return True
    if re.fullmatch(
        r"(?:rez(?:ervasyon)?|reservation|voucher)\s*(?:id|no|number)?[\s:#\-]*[a-z0-9\.\-]+",
        low,
    ):
        return True
    has_rez_slot = bool(
        re.search(
            r"(?:rez(?:ervasyon)?\s*(?:id|no)?|reservation\s*(?:id|no)?|voucher\s*(?:no|number)?)\s*[:#\-]?\s*[a-z0-9\.\-]{4,}",
            low,
        )
    )
    has_name_slot = any(marker in low for marker in ("ad soyad", "full name", "name"))
    has_rate_choice = bool(re.search(r"(?:^|[\s,;:\-])[12](?:$|[\s,;:\-])", low))
    if has_rez_slot and (has_name_slot or has_rate_choice):
        return True
    return len(t) <= 2


def resolve_language_lock(
    phone: str,
    user_message: str,
    load_conversation_fn: Callable[[str], dict],
    detect_language_fn: Callable[[str], str],
) -> str:
    raw_msg = (user_message or "").strip()

    direct_target, _ = extract_language_switch_request(user_message or "")
    if direct_target:
        return direct_target

    current = normalize_language_code(detect_language_fn(user_message or ""))
    if contains_turkish_chars(raw_msg) or (current == "en" and looks_like_turkish_ascii_message(raw_msg)):
        current = "tr"
    else:
        low = (raw_msg or "").lower()
        tr_booking_markers = (
            "rezervasyon",
            "oda",
            "fiyat",
            "müsait",
            "musait",
            "giris",
            "çıkış",
            "cikis",
            "yetişkin",
            "yetiskin",
            "çocuk",
            "cocuk",
            "ad soyad",
            "telefon",
            "eposta",
            "e-posta",
        )
        if any(m in low for m in tr_booking_markers):
            current = "tr"

    if not phone:
        return current

    try:
        conv = load_conversation_fn(phone) or {}
        messages = conv.get("messages") or []

        for msg in reversed(messages):
            txt = (msg.get("user_message") or "").strip()
            target, _ = extract_language_switch_request(txt)
            if target:
                return target
            bot_txt = (msg.get("bot_reply") or "").strip()
            bot_target, _ = extract_language_switch_request(bot_txt)
            if bot_target:
                return bot_target
            confirmed_target = extract_language_from_switch_confirmation(bot_txt)
            if confirmed_target:
                return confirmed_target

        raw_is_ambiguous = is_ambiguous_lang_message(raw_msg)
        if not raw_is_ambiguous:
            token_count = len(re.findall(r"\w+", raw_msg, flags=re.UNICODE))
            has_non_latin_script = bool(
                re.search(r"[\u4e00-\u9fff\u0600-\u06FF\u0900-\u097F]", raw_msg)
            )
            if token_count >= 4 or has_non_latin_script:
                return current

        # Kisa/ambiguous follow-up'larda (örn: sadece telefon numarasi, "1", "ok")
        # son bot cevabinin dilini onceleyerek dil kaymasini engelle.
        if raw_is_ambiguous and messages:
            for msg in reversed(messages):
                bot_txt = (msg.get("bot_reply") or "").strip()
                if not bot_txt:
                    continue
                if contains_turkish_chars(bot_txt) or looks_like_turkish_ascii_message(bot_txt):
                    return "tr"
                return normalize_language_code(detect_language_fn(bot_txt))

        for msg in reversed(messages):
            txt = (msg.get("user_message") or "").strip()
            if txt:
                if is_ambiguous_lang_message(txt):
                    continue
                if contains_turkish_chars(txt) or looks_like_turkish_ascii_message(txt):
                    return "tr"
                return normalize_language_code(detect_language_fn(txt))

        if messages:
            for msg in reversed(messages):
                bot_txt = (msg.get("bot_reply") or "").strip()
                if not bot_txt:
                    continue
                return normalize_language_code(detect_language_fn(bot_txt))
    except Exception:
        pass

    return current
