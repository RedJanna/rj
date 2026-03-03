from __future__ import annotations

import re
from typing import Callable

SUPPORTED_CUSTOMER_LANGS = ["en", "tr", "ru", "de", "ar", "es", "fr", "zh", "hi", "pt"]

_LATIN_LANGS = {"en", "tr", "de", "es", "fr", "pt"}
_SCRIPT_PATTERNS = {
    "ru": r"[А-Яа-яЁё]",
    "ar": r"[\u0600-\u06FF]",
    "zh": r"[\u4E00-\u9FFF]",
    "hi": r"[\u0900-\u097F]",
}

_EXEMPT_PATTERNS = [
    r"https?://\S+",
    r"\b[\w\.\-]+@[\w\.\-]+\.\w+\b",
    r"\+?\d[\d\s\-\(\)]{6,}\d",
    r"\b(?:Kassandra|EUR|USD|TRY|TL|GBP)\b",
]


def normalize_guard_language(lang: str) -> str:
    code = (lang or "").strip().lower()
    return code if code in SUPPORTED_CUSTOMER_LANGS else "en"


def _remove_exempt_segments(text: str) -> str:
    out = text or ""
    for pat in _EXEMPT_PATTERNS:
        out = re.sub(pat, " ", out, flags=re.IGNORECASE)
    return out


def is_script_compatible(text: str, lang: str) -> bool:
    target = normalize_guard_language(lang)
    source = _remove_exempt_segments(text or "")
    letters = re.findall(r"[A-Za-z\u00C0-\u024F\u0400-\u04FF\u0600-\u06FF\u0900-\u097F\u4E00-\u9FFF]", source)
    if not letters:
        return True

    if target in _LATIN_LANGS:
        latin = re.findall(r"[A-Za-z\u00C0-\u024F]", source)
        return (len(latin) / float(len(letters))) >= 0.80

    script_pat = _SCRIPT_PATTERNS.get(target)
    if not script_pat:
        return True
    matches = re.findall(script_pat, source)
    return (len(matches) / float(len(letters))) >= 0.75


def needs_hard_language_guard(
    reply: str,
    target_lang: str,
    detect_language_fn: Callable[[str], str] | None = None,
) -> bool:
    text = (reply or "").strip()
    if not text:
        return False

    target = normalize_guard_language(target_lang)
    if not is_script_compatible(text, target):
        return True

    if callable(detect_language_fn):
        try:
            detected = normalize_guard_language(detect_language_fn(text))
            if detected != target:
                return True
        except Exception:
            pass

    return False

