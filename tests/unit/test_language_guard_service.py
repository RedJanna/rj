from __future__ import annotations

from app.services.language_guard_service import (
    is_script_compatible,
    needs_hard_language_guard,
    normalize_guard_language,
)


def test_normalize_guard_language_forces_unknown_to_en():
    assert normalize_guard_language("tr") == "tr"
    assert normalize_guard_language("jp") == "en"
    assert normalize_guard_language("") == "en"


def test_script_compatibility_detects_english_text_for_tr():
    assert is_script_compatible("Teşekkürler, rezervasyonunuz alınmıştır.", "tr") is True
    assert is_script_compatible("Thank you for your reservation details.", "tr") is True


def test_script_compatibility_detects_cyrillic_for_ru():
    assert is_script_compatible("Спасибо, ваше бронирование получено.", "ru") is True
    assert is_script_compatible("Thank you for reservation.", "ru") is False


def test_needs_hard_language_guard_on_detected_mismatch():
    msg = "Thank you, please share your phone number."
    assert needs_hard_language_guard(msg, "tr", detect_language_fn=lambda _t: "en") is True

