from app.handlers.booking_flow_handler import (
    _extract_group_stage1_data,
    _extract_group_stage2_selections,
    _extract_booking_alias_index,
    _extract_context_id,
    _extract_multi_room_request,
    _is_generic_payment_method_question,
    _is_group_quote_request,
)
from app.handlers import booking_flow_handler as h

import pytest


def test_extract_context_id():
    assert _extract_context_id("CTX-AB12CD34 için ödeme linki gönder") == "CTX-AB12CD34"
    assert _extract_context_id("reference ctx-abcd1234") == "CTX-ABCD1234"
    assert _extract_context_id("referans yok") == ""


def test_extract_booking_alias_index():
    assert _extract_booking_alias_index("A1 için ödeme") == 1
    assert _extract_booking_alias_index("#A2 link gönder") == 2
    assert _extract_booking_alias_index("A10") == 10
    assert _extract_booking_alias_index("rezervasyon") == 0


def test_generic_payment_method_question_guard():
    assert _is_generic_payment_method_question("Ödeme yöntemleriniz neler?")
    assert _is_generic_payment_method_question("payment methods?")
    assert not _is_generic_payment_method_question("A1 için ödeme linki gönder")


def test_extract_multi_room_request():
    parsed = _extract_multi_room_request("13 kişi için 3 adet oda rezerve etmek istiyorum")
    assert parsed["guest_count"] == 13
    assert parsed["room_count"] == 3


def test_extract_multi_room_request_with_family_count():
    parsed = _extract_multi_room_request("3 adet aile için fiyat almak istiyorum")
    assert parsed["family_count"] == 3
    assert parsed["room_count"] == 0


def test_group_quote_detects_family_price_message():
    assert _is_group_quote_request("3 adet aile için fiyat almak istiyorum")


def test_extract_group_stage1_data():
    msg = """GRUP FİYAT TALEP FORMU
- Giriş: 2026-08-10
- Çıkış: 2026-08-13
A1 | Yetişkin: 2 | Çocuk: 5, 8 | Oda adedi: 1
A2 | Yetişkin: 3 | Çocuk:  | Oda adedi: 2
"""
    data = _extract_group_stage1_data(msg)
    assert data["check_in"] == "2026-08-10"
    assert data["check_out"] == "2026-08-13"
    assert len(data["families"]) == 2
    assert data["families"][0]["alias"] == "A1"
    assert data["families"][0]["child_ages"] == [5, 8]


def test_extract_group_stage2_selections():
    msg = """ODA SEÇİM FORMU
A1 -> Seçim: Superior / Ücretsiz İptal
A2 -> Seçim: Deluxe / İade Yapılmaz
"""
    selections = _extract_group_stage2_selections(msg)
    assert selections["A1"].startswith("Superior")
    assert selections["A2"].startswith("Deluxe")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_payment_link_handoff_sends_admin_notification(monkeypatch):
    captured = {}
    takeover_calls = []

    async def _fake_notify_admin_handoff(*args, **kwargs):
        captured.update(kwargs)
        return True

    monkeypatch.setattr(h, "notify_admin_handoff", _fake_notify_admin_handoff)
    monkeypatch.setattr(
        h,
        "activate_human_takeover",
        lambda phone, reason="handoff": takeover_calls.append((phone, reason)) or True,
    )
    monkeypatch.setattr(h, "record_metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(h, "get_payment_context", lambda _phone: {})
    monkeypatch.setattr(h, "get_latest_booking_by_phone", lambda _phone, include_test=False: None)
    monkeypatch.setattr(h, "clear_payment_context", lambda _phone: None)

    result = await h._handle_payment_intent("+905551112233", "Ödeme linki gönderir misiniz?", "tr")

    assert result is not None
    assert result["status"] == "handoff"
    assert takeover_calls == [("+905551112233", "payment_link_request")]
    assert captured["category"] == "canli_destek"
    assert captured["priority"] == "high"
    assert captured["customer_phone"] == "+905551112233"
    assert "ödeme linki" in captured["customer_message"].lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_quiet_room_handoff_activates_takeover_and_notifies_admin(monkeypatch):
    captured = {}
    takeover_calls = []
    cleared = []

    async def _fake_notify_admin_handoff(*args, **kwargs):
        captured.update(kwargs)
        return True

    monkeypatch.setattr(h, "notify_admin_handoff", _fake_notify_admin_handoff)
    monkeypatch.setattr(
        h,
        "activate_human_takeover",
        lambda phone, reason="handoff": takeover_calls.append((phone, reason)) or True,
    )
    monkeypatch.setattr(h, "clear_booking_flow", lambda phone: cleared.append(phone))

    result = await h._handle_quiet_room_handoff("+905551112233", "tr")

    assert result["status"] == "handoff"
    assert takeover_calls == [("+905551112233", "quiet_room_live_required")]
    assert cleared == ["+905551112233"]
    assert captured["category"] == "quiet_room_live_required"
    assert captured["priority"] == "medium"
    assert captured["customer_phone"] == "+905551112233"
    assert "sessiz oda talebinde" in captured["customer_message"].lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_payment_context_saved_when_multiple_booking_candidates_for_link(monkeypatch):
    saved = {}
    candidates = [
        {
            "id": 1,
            "status": "elektra_created",
            "booking_context_id": "CTX-A1B2C3D4",
            "check_in": "2026-02-26",
            "check_out": "2026-02-28",
            "adult_count": 2,
            "room_type_display": "Premium - Jakuzili (45m2)",
            "updated_at": "2026-02-27T00:50:00",
            "created_at": "2026-02-27T00:40:00",
        },
        {
            "id": 2,
            "status": "elektra_created",
            "booking_context_id": "CTX-E5F6G7H8",
            "check_in": "2026-02-26",
            "check_out": "2026-02-28",
            "adult_count": 2,
            "room_type_display": "Premium - Jakuzili (45m2)",
            "updated_at": "2026-02-27T00:49:00",
            "created_at": "2026-02-27T00:39:00",
        },
    ]

    monkeypatch.setattr(h, "get_payment_context", lambda _phone: {})
    monkeypatch.setattr(h, "_is_test_phone", lambda _phone: False)
    monkeypatch.setattr(h, "get_latest_booking_by_phone", lambda *_args, **_kwargs: candidates[0])
    monkeypatch.setattr(h, "get_hotel_booking", lambda _booking_id: None)
    monkeypatch.setattr(h, "get_booking_by_context_id", lambda _ctx: None)
    monkeypatch.setattr(h, "get_active_bookings_by_phone", lambda *_args, **_kwargs: candidates)
    monkeypatch.setattr(h, "clear_payment_context", lambda _phone: None)
    monkeypatch.setattr(
        h,
        "save_payment_context",
        lambda phone, data: saved.update({"phone": phone, "data": dict(data or {})}),
    )

    result = await h._handle_payment_intent("+905551112233", "1", "tr")

    assert result is not None
    assert result.get("status") == "booking_context_required"
    assert saved.get("phone") == "+905551112233"
    assert saved.get("data", {}).get("method") == "link"
