from __future__ import annotations

from app.routes.chat_routes import _extract_language_switch_request
from app.routes.chat_routes import _normalize_language_code
from app.routes.chat_routes import _resolve_language_lock


def test_normalize_language_code_fallbacks_to_en():
    assert _normalize_language_code("tr") == "tr"
    assert _normalize_language_code("xx") == "en"
    assert _normalize_language_code("") == "en"


def test_resolve_language_lock_prefers_latest_non_ambiguous_user_message():
    def _load_conv(_phone: str):
        return {
            "messages": [
                {"user_message": "Merhaba"},
                {"user_message": "Hello again"},
            ]
        }

    def _detect(text: str) -> str:
        low = (text or "").lower()
        if "merhaba" in low:
            return "tr"
        if "hello" in low:
            return "en"
        return "en"

    lang = _resolve_language_lock(
        phone="+905551112233",
        user_message="1",
        load_conversation_fn=_load_conv,
        detect_language_fn=_detect,
    )
    assert lang == "en"


def test_resolve_language_lock_defaults_to_current_message_when_no_history():
    def _load_conv(_phone: str):
        return {"messages": []}

    lang = _resolve_language_lock(
        phone="+905551112233",
        user_message="Bonjour",
        load_conversation_fn=_load_conv,
        detect_language_fn=lambda _text: "fr",
    )
    assert lang == "fr"


def test_extract_language_switch_request_supported():
    target, supported = _extract_language_switch_request("Can you speak English?")
    assert target == "en"
    assert supported is True


def test_extract_language_switch_request_unsupported_falls_back_to_en():
    target, supported = _extract_language_switch_request("Can you speak Japanese?")
    assert target == "en"
    assert supported is False


def test_resolve_language_lock_skips_ambiguous_history_messages():
    def _load_conv(_phone: str):
        return {
            "messages": [
                {"user_message": "1", "bot_reply": "Merhaba"},
                {"user_message": "1", "bot_reply": "Nasıl yardımcı olabilirim?"},
            ]
        }

    def _detect(text: str) -> str:
        low = (text or "").lower()
        if "merhaba" in low or "yardımcı" in low:
            return "tr"
        return "en"

    lang = _resolve_language_lock(
        phone="+905551112233",
        user_message="A1 payment link",
        load_conversation_fn=_load_conv,
        detect_language_fn=_detect,
    )
    assert lang == "tr"


def test_resolve_language_lock_uses_last_bot_reply_when_user_history_ambiguous():
    def _load_conv(_phone: str):
        return {
            "messages": [
                {"user_message": "1", "bot_reply": "Merhaba"},
                {"user_message": "2", "bot_reply": "Ödemeyi hangi para birimi ile yapmak istersiniz?"},
            ]
        }

    def _detect(text: str) -> str:
        low = (text or "").lower()
        if "merhaba" in low or "para birimi" in low:
            return "tr"
        return "en"

    lang = _resolve_language_lock(
        phone="+905551112233",
        user_message="USD",
        load_conversation_fn=_load_conv,
        detect_language_fn=_detect,
    )
    assert lang == "tr"


def test_resolve_language_lock_prioritizes_explicit_language_switch():
    def _load_conv(_phone: str):
        return {
            "messages": [
                {"user_message": "Mherba"},
                {"user_message": "türkçeye geçiş yapar mısın ?"},
                {"user_message": "Hello again"},
            ]
        }

    def _detect(_text: str) -> str:
        return "en"

    lang = _resolve_language_lock(
        phone="+905551112233",
        user_message="10-13 Ağustos için standart oda fiyatı kaç TL?",
        load_conversation_fn=_load_conv,
        detect_language_fn=_detect,
    )
    assert lang == "tr"


def test_resolve_language_lock_uses_current_long_message_language_over_history():
    def _load_conv(_phone: str):
        return {
            "messages": [
                {"user_message": "Do you have availability?"},
                {"bot_reply": "Yes, please share your dates."},
            ]
        }

    def _detect(text: str) -> str:
        low = (text or "").lower()
        if "kahvalti" in low or "kahvaltı" in low:
            return "tr"
        return "en"

    lang = _resolve_language_lock(
        phone="+905551112233",
        user_message="Kahvalti dahil mi, degilse ne kadar ekleniyor?",
        load_conversation_fn=_load_conv,
        detect_language_fn=_detect,
    )
    assert lang == "tr"


def test_resolve_language_lock_detects_turkish_ascii_even_if_detector_returns_en():
    lang = _resolve_language_lock(
        phone="",
        user_message="Odeme ve kapora bilgilerini yazabilir misiniz?",
        load_conversation_fn=lambda _phone: {"messages": []},
        detect_language_fn=lambda _text: "en",
    )
    assert lang == "tr"


def test_resolve_language_lock_skips_rezid_slot_message_for_language_inference():
    def _load_conv(_phone: str):
        return {
            "messages": [
                {"user_message": "Rezervasyonumu iptal etmek istiyorum."},
                {"user_message": "Rez ID: 81.943.761"},
            ]
        }

    def _detect(text: str) -> str:
        low = (text or "").lower()
        if "rezervasyonumu iptal etmek istiyorum" in low:
            return "tr"
        return "en"

    lang = _resolve_language_lock(
        phone="+905551112233",
        user_message="2",
        load_conversation_fn=_load_conv,
        detect_language_fn=_detect,
    )
    assert lang == "tr"


def test_resolve_language_lock_skips_composite_cancel_slot_payload():
    def _load_conv(_phone: str):
        return {
            "messages": [
                {"user_message": "Rezervasyonumu iptal etmek istiyorum."},
                {
                    "bot_reply": (
                        "Iptal isleminiz icin size yardimci olayim. Islemi baslatabilmemiz icin "
                        "lutfen Rezervasyon / Voucher Numaranizi ve Ad-Soyad bilginizi paylasir misiniz? "
                        "(1- Iptal Edilemez, 2- Ucretsiz Iptal)"
                    )
                },
            ]
        }

    def _detect(text: str) -> str:
        low = (text or "").lower()
        if "rezervasyonumu iptal etmek istiyorum" in low:
            return "tr"
        return "en"

    lang = _resolve_language_lock(
        phone="+905551112233",
        user_message="Rez ID: TEST-12345, Ad Soyad: Test Kullanici, 2",
        load_conversation_fn=_load_conv,
        detect_language_fn=_detect,
    )
    assert lang == "tr"
