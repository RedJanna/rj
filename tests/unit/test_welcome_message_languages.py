from __future__ import annotations

from app.utils.message_utils import get_welcome_message


def test_get_welcome_message_supported_languages_return_non_empty():
    langs = ["en", "tr", "ru", "de", "ar", "es", "fr", "zh", "hi", "pt"]
    for lang in langs:
        msg = get_welcome_message(lang)
        assert isinstance(msg, str)
        assert msg.strip()


def test_get_welcome_message_unknown_language_falls_back_to_english():
    msg = get_welcome_message("jp")
    assert "Welcome to Kassandra Ölüdeniz" in msg

