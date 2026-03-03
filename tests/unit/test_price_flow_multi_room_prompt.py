from __future__ import annotations

import uuid

import pytest

from app.handlers.price_flow_handler import (
    _extract_room_count_from_message,
    _ask_guests_message,
    _extract_child_count,
    _get_missing_fields,
    _looks_like_price_slot_followup,
    detect_price_intent,
)
from app.handlers import price_flow_handler as pfh
from app.services.price_flow_service import (
    PriceFlowState,
    clear_price_flow,
    get_last_query,
    get_price_flow,
    save_price_flow,
)


def test_extract_room_count_from_message_detects_two_rooms():
    assert _extract_room_count_from_message("10-13 Ağustos için 2 oda fiyat alabilir miyim?") == 2
    assert _extract_room_count_from_message("10-13 Ağustos için iki oda fiyat alabilir miyim?") == 2


def test_ask_guests_message_for_multi_room_is_room_based():
    msg = _ask_guests_message("tr", room_count=2)
    assert "2 oda" in msg
    assert "her oda/aile için" in msg


def test_extract_child_count_detects_explicit_child_count():
    assert _extract_child_count("2 yetişkin 1 çocuk", []) == 1
    assert _extract_child_count("2 adults 2 children", []) == 2


def test_missing_fields_require_child_count_and_ages_when_child_mentioned():
    flow_data = {
        "from_date": "2026-08-10",
        "to_date": "2026-08-13",
        "adult_count": 2,
        "room_count": 1,
        "child_mentioned": True,
        "child_count": 0,
        "child_ages": [],
    }
    missing = _get_missing_fields(flow_data)
    assert "child_count" in missing
    assert "child_ages" in missing


def test_detect_price_intent_accepts_same_date_room_comparison_query():
    msg = "Aynı tarihlerde deniz manzaralı oda müsait mi, varsa fiyat farkı ne kadar?"
    assert detect_price_intent(msg) is True


def test_detect_price_intent_accepts_pool_view_room_price_query():
    msg = "14-18 Ağustos, 2 yetişkin, havuz manzaralı oda fiyatı nedir?"
    assert detect_price_intent(msg) is True


def test_detect_price_intent_accepts_chinese_price_query():
    msg = "请提供2026年8月14日至18日两位成人的总价。"
    assert detect_price_intent(msg) is True


def test_looks_like_price_slot_followup_when_age_message_after_missing_slot_prompt():
    history = [
        {"role": "user", "content": "1 ekim ile 3 ekim tarihleri arasında fiyat nedir?"},
        {"role": "assistant", "content": "Net fiyat verebilmem için giriş-çıkış tarihi ve kişi sayısını paylaşır mısınız?"},
        {"role": "user", "content": "2 yetişkin 2 çocuk"},
        {"role": "assistant", "content": "Fiyat bilgisi için yardımcı olabilirim. Eksik: çocuk yaşları"},
    ]
    assert _looks_like_price_slot_followup("7 ve 8", history) is True


@pytest.mark.asyncio
async def test_multi_room_initial_request_asks_room_based_guest_details(monkeypatch):
    clear_price_flow("905000000000")

    async def _dummy_query(*args, **kwargs):
        return {"reply": "should-not-query", "status": "price_result", "log": "", "is_price_template": True}

    monkeypatch.setattr(pfh, "_query_elektraweb", _dummy_query)

    result = await pfh.handle_price_flow(
        phone="905000000000",
        message="10-13 Ağustos için iki oda fiyatı alabilir miyim?",
        history=[],
        lang="tr",
    )
    assert result is not None
    assert result["status"] == "price_flow"
    assert "her oda/aile için" in result["reply"]
    clear_price_flow("905000000000")


@pytest.mark.asyncio
async def test_query_elektraweb_technical_handoff_returns_handoff(monkeypatch):
    async def _handoff(*args, **kwargs):
        return "HANDOFF:API_ERROR", "api_down", None

    monkeypatch.setattr(pfh, "handle_elektra_price_request", _handoff)
    clear_price_flow("905000000002")
    flow_data = {
        "lang": "tr",
        "from_date": "2026-08-10",
        "to_date": "2026-08-13",
        "adult_count": 2,
        "child_ages": [],
        "child_mentioned": False,
    }
    result = await pfh._query_elektraweb("905000000002", flow_data, "21966")
    assert result["status"] == "handoff"
    assert "Talebinizi ekibimize ilettim" in result["reply"]


@pytest.mark.asyncio
async def test_room_stock_query_api_failure_returns_handoff(monkeypatch):
    async def _boom(*args, **kwargs):
        raise RuntimeError("availability down")

    monkeypatch.setattr(pfh, "fetch_room_stock_by_type_from_availability", _boom)
    monkeypatch.setattr(
        pfh,
        "get_last_query",
        lambda _phone: {"from_date": "2026-08-10", "to_date": "2026-08-13", "adult_count": 2, "currency": "EUR"},
    )
    result = await pfh._handle_room_stock_query(
        phone="905000000003",
        message="Kaç adet premium oda müsaittir?",
        lang="tr",
        hotel_id="21966",
    )
    assert result is not None
    assert result["status"] == "handoff"
    assert "Talebinizi ekibimize ilettim" in result["reply"]


@pytest.mark.asyncio
async def test_room_stock_query_uses_cached_offer_availability_first(monkeypatch):
    monkeypatch.setattr(
        pfh,
        "get_last_query",
        lambda _phone: {"from_date": "2026-08-10", "to_date": "2026-08-13", "adult_count": 2, "currency": "EUR"},
    )

    from app.services import booking_flow_service as bfs

    monkeypatch.setattr(
        bfs,
        "get_price_offers",
        lambda _phone: {
            "offers": [
                {
                    "room-type": "PREMIUM",
                    "availability-arr": [2, 2, 2],
                    "room-type-id": 396095,
                }
            ]
        },
    )

    async def _boom(**_kwargs):
        raise AssertionError("availability API should not be called when cached offer stock exists")

    monkeypatch.setattr(pfh, "fetch_room_stock_by_type_from_availability", _boom)

    result = await pfh._handle_room_stock_query(
        phone="905000000099",
        message="Kaç adet premium oda müsaittir?",
        lang="tr",
        hotel_id="21966",
    )
    assert result is not None
    assert result["status"] == "price_room_stock_result"
    assert "2 adet müsait oda" in result["reply"]


@pytest.mark.asyncio
async def test_breakfast_policy_question_returns_policy_reply_not_price_query():
    result = await pfh.handle_price_flow(
        phone="905000001111",
        message="Bu fiyata kahvaltı dahil mi, değilse kişi başı ek ücret nedir?",
        history=[],
        lang="tr",
    )
    assert result is not None
    assert result["status"] == "price_policy_info"
    assert "Konseptimiz kahvaltı dahildir" in result["reply"]


@pytest.mark.asyncio
async def test_dates_followup_carries_standard_room_and_tl_intent_to_query(monkeypatch):
    phone = f"9059{uuid.uuid4().int % 10**8:08d}"
    clear_price_flow(phone)
    captured: dict[str, str] = {}

    async def _fake_handle_elektra_price_request(message: str, hotel_id: str, lang: str):
        captured["message"] = message
        return "ok", "{}", []

    monkeypatch.setattr(pfh, "handle_elektra_price_request", _fake_handle_elektra_price_request)

    first = await pfh.handle_price_flow(
        phone=phone,
        message="Merhaba, 2 yetişkin olarak Ağustos'ta konaklama fiyatı öğrenebilir miyim?",
        history=[],
        lang="tr",
    )
    assert first is not None
    assert first["status"] == "price_flow"

    second = await pfh.handle_price_flow(
        phone=phone,
        message="10-13 Ağustos için standart oda toplam fiyat kaç TL?",
        history=[],
        lang="tr",
    )
    assert second is not None
    assert second["status"] == "price_result"
    assert "standart oda" in captured.get("message", "").lower()
    assert "TL" in captured.get("message", "")

    last_q = get_last_query(phone)
    assert last_q is not None
    assert last_q.get("currency") == "TRY"
    clear_price_flow(phone)


@pytest.mark.asyncio
async def test_generic_followup_keeps_previous_room_preference(monkeypatch):
    phone = f"9057{uuid.uuid4().int % 10**8:08d}"
    clear_price_flow(phone)
    captured_messages: list[str] = []

    async def _fake_handle_elektra_price_request(message: str, hotel_id: str, lang: str):
        captured_messages.append(message)
        return "ok", "{}", []

    monkeypatch.setattr(pfh, "handle_elektra_price_request", _fake_handle_elektra_price_request)

    first = await pfh.handle_price_flow(
        phone=phone,
        message="14-18 Ağustos, 2 yetişkin, havuz manzaralı oda fiyatı nedir?",
        history=[],
        lang="tr",
    )
    assert first is not None
    assert first["status"] == "price_result"

    second = await pfh.handle_price_flow(
        phone=phone,
        message="Fiyat bilgisini verir misiniz?",
        history=[],
        lang="tr",
    )
    assert second is not None
    assert second["status"] == "price_result"

    assert len(captured_messages) >= 2
    assert "havuz manzara" in pfh._normalize_turkish_chars(captured_messages[-1].lower())
    clear_price_flow(phone)


@pytest.mark.asyncio
async def test_age_only_followup_uses_price_context_and_queries_elektra(monkeypatch):
    phone = f"9059{uuid.uuid4().int % 10**8:08d}"
    clear_price_flow(phone)
    captured: dict[str, str] = {}

    async def _fake_handle_elektra_price_request(message: str, hotel_id: str, lang: str):
        captured["message"] = message
        return "ok", "{}", []

    monkeypatch.setattr(pfh, "handle_elektra_price_request", _fake_handle_elektra_price_request)

    history = [
        {"role": "user", "content": "1 ekim 2026 ile 3 ekim 2026 tarihleri arasında fiyat nedir ?"},
        {"role": "assistant", "content": "Net fiyat verebilmem için giriş-çıkış tarihi ve kişi sayısını paylaşır mısınız?"},
        {"role": "user", "content": "2 yetişkin 2 çocuk"},
        {"role": "assistant", "content": "Fiyat bilgisi için yardımcı olabilirim. Eksik: çocuk yaşları"},
    ]

    result = await pfh.handle_price_flow(
        phone=phone,
        message="7 ve 8",
        history=history,
        lang="tr",
    )

    assert result is not None
    assert result["status"] == "price_result"
    assert "2 yetişkin" in captured.get("message", "")
    assert "7 yaş 8 yaş" in captured.get("message", "")
    clear_price_flow(phone)


@pytest.mark.asyncio
async def test_start_flow_with_child_count_without_ages_must_ask_child_ages():
    phone = f"9059{uuid.uuid4().int % 10**8:08d}"
    clear_price_flow(phone)
    result = await pfh.handle_price_flow(
        phone=phone,
        message="1 ekim 2026 ile 3 ekim 2026 arası 2 yetişkin 2 çocuk fiyat nedir?",
        history=[],
        lang="tr",
    )
    assert result is not None
    assert result["status"] == "price_flow"
    assert "yaşlarını paylaşır" in result["reply"].lower()
    clear_price_flow(phone)


@pytest.mark.asyncio
async def test_full_slot_general_query_does_not_carry_previous_room_preference(monkeypatch):
    phone = f"9055{uuid.uuid4().int % 10**8:08d}"
    clear_price_flow(phone)
    captured_messages: list[str] = []

    async def _fake_handle_elektra_price_request(message: str, hotel_id: str, lang: str):
        captured_messages.append(message)
        return "ok", "{}", []

    monkeypatch.setattr(pfh, "handle_elektra_price_request", _fake_handle_elektra_price_request)

    first = await pfh.handle_price_flow(
        phone=phone,
        message="14-18 Ağustos, 2 yetişkin, havuz manzaralı oda fiyatı nedir?",
        history=[],
        lang="tr",
    )
    assert first is not None
    assert first["status"] == "price_result"

    second = await pfh.handle_price_flow(
        phone=phone,
        message="14 ağustos ile 18 ağustos tarihler arasında 2 yetişkin fiyatı nedir",
        history=[],
        lang="tr",
    )
    assert second is not None
    assert second["status"] == "price_result"

    latest = pfh._normalize_turkish_chars(captured_messages[-1].lower())
    assert "havuz manzara" not in latest
    clear_price_flow(phone)


@pytest.mark.asyncio
async def test_new_room_preference_overrides_previous_preference(monkeypatch):
    phone = f"9056{uuid.uuid4().int % 10**8:08d}"
    clear_price_flow(phone)
    captured_messages: list[str] = []

    async def _fake_handle_elektra_price_request(message: str, hotel_id: str, lang: str):
        captured_messages.append(message)
        return "ok", "{}", []

    monkeypatch.setattr(pfh, "handle_elektra_price_request", _fake_handle_elektra_price_request)

    first = await pfh.handle_price_flow(
        phone=phone,
        message="14-18 Ağustos, 2 yetişkin, havuz manzaralı oda fiyatı nedir?",
        history=[],
        lang="tr",
    )
    assert first is not None
    assert first["status"] == "price_result"

    second = await pfh.handle_price_flow(
        phone=phone,
        message="14-18 Ağustos, 2 yetişkin, standart oda fiyatı nedir?",
        history=[],
        lang="tr",
    )
    assert second is not None
    assert second["status"] == "price_result"

    assert len(captured_messages) >= 2
    latest = pfh._normalize_turkish_chars(captured_messages[-1].lower())
    assert "standart oda" in latest
    assert "havuz manzara" not in latest
    clear_price_flow(phone)


@pytest.mark.asyncio
async def test_active_price_flow_syncs_lang_with_current_language_lock():
    phone = f"9058{uuid.uuid4().int % 10**8:08d}"
    clear_price_flow(phone)

    save_price_flow(
        phone,
        PriceFlowState.ASK_DATES,
        {
            "lang": "en",
            "from_date": None,
            "to_date": None,
            "adult_count": None,
            "child_ages": [],
            "child_mentioned": False,
        },
    )

    result = await pfh.handle_price_flow(
        phone=phone,
        message="10-13 Ağustos",
        history=[],
        lang="tr",
    )
    assert result is not None
    assert result["status"] == "price_flow"
    assert "kaç kişi" in result["reply"].lower() or "yetişkin" in result["reply"].lower()

    flow = get_price_flow(phone)
    assert flow is not None
    assert (flow.get("data") or {}).get("lang") == "tr"
    clear_price_flow(phone)


@pytest.mark.asyncio
async def test_handle_guests_response_sets_child_count_without_nameerror(monkeypatch):
    flow_data = {
        "lang": "en",
        "from_date": "2026-08-18",
        "to_date": "2026-08-22",
        "adult_count": 2,
        "child_mentioned": False,
        "child_count": 0,
        "child_ages": [],
    }

    async def _fake_query(_phone, fd, _hotel_id):
        return {"reply": "ok", "status": "price_result", "log": "ok", "is_price_template": True}

    monkeypatch.setattr(pfh, "_query_elektraweb", _fake_query)

    result = await pfh._handle_guests_response(
        phone="905000009999",
        message="2 adults + 1 child (7 years old)",
        flow_data=flow_data,
        lang="en",
        hotel_id="21966",
    )

    assert result["status"] in {"price_flow", "price_result"}
    if result["status"] == "price_flow":
        assert "age" in result["reply"].lower() or "yaş" in result["reply"].lower()
    assert flow_data["child_count"] == 1


@pytest.mark.asyncio
async def test_active_price_flow_policy_interruption_returns_none():
    phone = f"9057{uuid.uuid4().int % 10**8:08d}"
    clear_price_flow(phone)
    save_price_flow(
        phone,
        PriceFlowState.ASK_CHILD_AGES,
        {
            "lang": "en",
            "from_date": "2026-08-18",
            "to_date": "2026-08-22",
            "adult_count": 2,
            "child_mentioned": True,
            "child_count": 1,
            "child_ages": [],
        },
    )

    result = await pfh.handle_price_flow(
        phone=phone,
        message="What's your child policy-does the child pay full price or a discounted rate?",
        history=[],
        lang="en",
    )
    assert result is None
    flow = get_price_flow(phone)
    assert flow is not None
    assert flow.get("state") == PriceFlowState.ASK_CHILD_AGES
    clear_price_flow(phone)


@pytest.mark.asyncio
async def test_active_price_flow_single_room_feature_query_bypasses_multi_room_loop(monkeypatch):
    phone = f"9058{uuid.uuid4().int % 10**8:08d}"
    clear_price_flow(phone)
    save_price_flow(
        phone,
        PriceFlowState.ASK_GUESTS,
        {
            "lang": "tr",
            "from_date": "2026-08-18",
            "to_date": "2026-08-22",
            "adult_count": 2,
            "room_count": 2,  # onceki mesajdan kalan multi-room baglami
            "room_groups": [],
            "child_mentioned": False,
            "child_count": 0,
            "child_ages": [],
            "context_hint": "10-13 Agustos icin 2 oda fiyat alabilir miyim?",
        },
    )

    async def _fake_query(_phone, flow_data, _hotel_id, currency_override=None):
        assert flow_data.get("room_count") == 1
        assert flow_data.get("room_groups") == []
        return {"reply": "filtered-price", "status": "price_result", "log": "ok", "is_price_template": True}

    monkeypatch.setattr(pfh, "_query_elektraweb", _fake_query)

    result = await pfh.handle_price_flow(
        phone=phone,
        message="Havuz manzaralı oda fiyatını paylaşır mısın?",
        history=[],
        lang="tr",
    )
    assert result is not None
    assert result["status"] == "price_result"
    assert result["reply"] == "filtered-price"
    clear_price_flow(phone)


@pytest.mark.asyncio
async def test_currency_change_request_returns_handoff_when_currency_disabled(monkeypatch):
    phone = f"9053{uuid.uuid4().int % 10**8:08d}"
    clear_price_flow(phone)
    monkeypatch.setattr(pfh, "get_currency_policy", lambda: {"EUR": True, "USD": False, "TRY": True, "GBP": True})

    result = await pfh.handle_price_flow(
        phone=phone,
        message="fiyatı usd olarak paylaşır mısın?",
        history=[],
        lang="tr",
    )

    assert result is not None
    assert result["status"] == "handoff"
    assert result["reply"] == pfh._DISABLED_CURRENCY_REPLY
    assert result.get("handoff_reason") == "price_currency_disabled"
    clear_price_flow(phone)


@pytest.mark.asyncio
async def test_new_price_query_returns_handoff_when_requested_currency_disabled(monkeypatch):
    phone = f"9054{uuid.uuid4().int % 10**8:08d}"
    clear_price_flow(phone)
    monkeypatch.setattr(pfh, "get_currency_policy", lambda: {"EUR": True, "USD": False, "TRY": True, "GBP": True})

    result = await pfh.handle_price_flow(
        phone=phone,
        message="14-18 Ağustos 2026, 2 yetişkin toplam fiyat kaç USD?",
        history=[],
        lang="tr",
    )

    assert result is not None
    assert result["status"] == "handoff"
    assert result["reply"] == pfh._DISABLED_CURRENCY_REPLY
    assert result.get("handoff_reason") == "price_currency_disabled"
    clear_price_flow(phone)
