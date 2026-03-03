from __future__ import annotations

from app.services.language_policy_service import (
    extract_language_switch_request,
    normalize_language_code,
    resolve_language_lock,
)


def test_normalize_language_code():
    assert normalize_language_code("tr") == "tr"
    assert normalize_language_code("xx") == "en"


def test_extract_language_switch_request_supported():
    lang, supported = extract_language_switch_request("can you speak portuguese?")
    assert lang == "pt"
    assert supported is True


def test_resolve_language_lock_keeps_seed_language_for_ambiguous_followup():
    def _load(_phone: str):
        return {"messages": [{"user_message": "Olá, quero saber o preço."}]}

    lang = resolve_language_lock(
        phone="+905551112233",
        user_message="1",
        load_conversation_fn=_load,
        detect_language_fn=lambda _t: "pt",
    )
    assert lang == "pt"
