from __future__ import annotations

import pytest

from app.routes.chat_routes import _extract_language_switch_request
from app.routes.chat_routes import _enforce_language_lock
from app.routes.chat_routes import _force_primary_intent_from_explicit_message
from app.routes.chat_routes import _normalize_language_code
from app.routes.chat_routes import _extract_locked_lang_from_flow
from app.routes.chat_routes import _repair_mojibake_text
from app.routes.chat_routes import _resolve_language_lock
from app.routes.chat_routes import _translate_reply_if_needed


def test_normalize_language_code_fallbacks_to_en():
    assert _normalize_language_code("tr") == "tr"
    assert _normalize_language_code("xx") == "en"
    assert _normalize_language_code("") == "en"


def test_extract_locked_lang_from_flow_prefers_data_lang():
    flow = {"state": "ask_email", "data": {"lang": "tr"}}
    assert _extract_locked_lang_from_flow(flow) == "tr"


def test_extract_locked_lang_from_flow_supports_language_key():
    flow = {"state": "ask_name", "data": {"language": "ru"}}
    assert _extract_locked_lang_from_flow(flow) == "ru"


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


def test_resolve_language_lock_treats_yes_as_ambiguous_to_prevent_language_drift():
    def _load_conv(_phone: str):
        return {
            "messages": [
                {"user_message": "1 ekim ile 6 ekim tarihleri arasında 2 yetişkin fiyatı nedir?"},
                {"user_message": "yes"},
            ]
        }

    def _detect(text: str) -> str:
        low = (text or "").lower()
        if "yes" in low:
            return "en"
        if "ekim" in low or "yetişkin" in low:
            return "tr"
        return "en"

    lang = _resolve_language_lock(
        phone="+905551112233",
        user_message="1",
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


def test_resolve_language_lock_ambiguous_numeric_prefers_last_bot_reply_over_name_like_user_text():
    def _load_conv(_phone: str):
        return {
            "messages": [
                {"user_message": "deneme deneme", "bot_reply": "Teşekkürler! Deneme, Lütfen telefon numaranızı paylaşır mısınız?"},
            ]
        }

    def _detect(text: str) -> str:
        low = (text or "").lower()
        if "telefon numaranızı" in low or "teşekkürler" in low:
            return "tr"
        if "deneme deneme" in low:
            return "en"
        return "en"

    lang = _resolve_language_lock(
        phone="+905551112233",
        user_message="5599594499",
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


def test_resolve_language_lock_forces_tr_for_turkish_booking_markers():
    lang = _resolve_language_lock(
        phone="",
        user_message="premium oda rezervasyon olusturalim",
        load_conversation_fn=lambda _phone: {"messages": []},
        detect_language_fn=lambda _text: "en",
    )
    assert lang == "tr"


def test_resolve_language_lock_prefers_turkish_chars_for_mixed_checkin_text():
    lang = _resolve_language_lock(
        phone="",
        user_message="Check-in/check-out saatleriniz nedir?",
        load_conversation_fn=lambda _phone: {"messages": []},
        detect_language_fn=lambda _text: "en",
    )
    assert lang == "tr"


def test_resolve_language_lock_history_prefers_turkish_chars_over_detector_en():
    def _load_conv(_phone: str):
        return {"messages": [{"user_message": "Check-in/check-out saatleriniz nedir?"}]}

    lang = _resolve_language_lock(
        phone="+905551112233",
        user_message="2",
        load_conversation_fn=_load_conv,
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


@pytest.mark.parametrize(
    "seed_message,detected_lang",
    [
        ("Hello, I need room prices.", "en"),
        ("Merhaba, fiyat alabilir miyim?", "tr"),
        ("Здравствуйте, подскажите цену.", "ru"),
        ("Hallo, ich brauche den Preis.", "de"),
        ("مرحبا، أريد معرفة السعر.", "ar"),
        ("Hola, quiero saber el precio.", "es"),
        ("Bonjour, je veux connaître le prix.", "fr"),
        ("你好，我想了解价格。", "zh"),
        ("नमस्ते, मुझे कीमत जाननी है।", "hi"),
        ("Olá, quero saber o preço.", "pt"),
    ],
)
def test_resolve_language_lock_keeps_seed_language_for_ambiguous_followup(seed_message, detected_lang):
    def _load_conv(_phone: str):
        return {"messages": [{"user_message": seed_message}]}

    lang = _resolve_language_lock(
        phone="+905551112233",
        user_message="1",
        load_conversation_fn=_load_conv,
        detect_language_fn=lambda _text: detected_lang,
    )
    assert lang == detected_lang


def test_resolve_language_lock_prefers_cjk_current_message_over_seed_history():
    def _load_conv(_phone: str):
        return {
            "messages": [
                {"user_message": "seed", "bot_reply": "ack"},
            ]
        }

    lang = _resolve_language_lock(
        phone="+905551112233",
        user_message="请提供2026年8月14日至18日两位成人的总价。",
        load_conversation_fn=_load_conv,
        detect_language_fn=lambda _text: "zh",
    )
    assert lang == "zh"


def test_repair_mojibake_text_recovers_russian():
    garbled = "Ğ—Ğ´Ñ€Ğ°Ğ²ÑÑ‚Ğ²ÑƒĞ¹Ñ‚Ğµ"
    repaired = _repair_mojibake_text(garbled)
    assert "Здрав" in repaired


def test_repair_mojibake_text_keeps_normal_turkish():
    original = "14 Ağustos için fiyat nedir?"
    assert _repair_mojibake_text(original) == original


class _DummyOpenAIClient:
    class _Completions:
        @staticmethod
        def create(**_kwargs):
            class _Msg:
                content = "Translated output"

            class _Choice:
                message = _Msg()

            class _Resp:
                choices = [_Choice()]

            return _Resp()

    class _Chat:
        def __init__(self):
            self.completions = _DummyOpenAIClient._Completions()

    def __init__(self):
        self.chat = _DummyOpenAIClient._Chat()


class _SequenceOpenAIClient:
    class _Completions:
        def __init__(self, outputs: list[str]):
            self._outputs = outputs
            self._idx = 0

        def create(self, **_kwargs):
            content = self._outputs[min(self._idx, len(self._outputs) - 1)]
            self._idx += 1

            class _Msg:
                pass

            _Msg.content = content

            class _Choice:
                message = _Msg()

            class _Resp:
                choices = [_Choice()]

            return _Resp()

    class _Chat:
        def __init__(self, outputs: list[str]):
            self.completions = _SequenceOpenAIClient._Completions(outputs)

    def __init__(self, outputs: list[str]):
        self.chat = _SequenceOpenAIClient._Chat(outputs)


def test_translate_reply_skips_when_target_script_already_matches():
    text = "Условия отмены зависят от тарифа."
    out = _translate_reply_if_needed(
        text,
        "ru",
        _DummyOpenAIClient(),
        "gpt-test",
        detect_language_fn=lambda _t: "ru",
    )
    assert out == text


def test_translate_reply_uses_llm_when_reply_language_mismatches_target(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "live-key")
    text = "Rezervasyon kesinleştikten sonra kod paylaşılır."
    out = _translate_reply_if_needed(
        text,
        "en",
        _DummyOpenAIClient(),
        "gpt-test",
        detect_language_fn=lambda _t: "tr",
    )
    assert out == "Translated output"


def test_translate_reply_uses_llm_for_mixed_arabic_content(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "live-key")
    text = "مرحبًا، sorunuz için teşekkür ederim."
    out = _translate_reply_if_needed(
        text,
        "ar",
        _DummyOpenAIClient(),
        "gpt-test",
        detect_language_fn=lambda _t: "ar",
    )
    assert out == "Translated output"


def test_translate_reply_uses_llm_when_russian_text_has_latin_room_labels(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "live-key")
    text = "Цены на даты 14-18 августа:\nDeluxe (25m2)\nНевозвратный тариф: 840 EUR"
    out = _translate_reply_if_needed(
        text,
        "ru",
        _DummyOpenAIClient(),
        "gpt-test",
        detect_language_fn=lambda _t: "ru",
    )
    assert out == "Translated output"


def test_enforce_language_lock_forces_second_pass_when_first_translation_still_wrong(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "live-key")
    client = _SequenceOpenAIClient(["Hello this stayed English", "Olá, resposta em português."])
    out = _enforce_language_lock(
        reply="Initial english reply",
        target_lang="pt",
        detect_language_fn=lambda txt: "pt" if "português" in (txt or "").lower() else "en",
        openai_client=client,
        openai_model="gpt-test",
    )
    assert "português" in out.lower()


def test_force_primary_intent_prefers_price_query_for_explicit_price_text():
    intent = _force_primary_intent_from_explicit_message(
        "fiyat bilgisi verir misiniz?",
        "PAYMENT_LINK_REQUEST",
    )
    assert intent == "PRICE_QUERY"
