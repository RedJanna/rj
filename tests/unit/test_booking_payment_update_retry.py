import pytest

from app.handlers import booking_flow_handler as h


def _sample_booking() -> dict:
    return {
        "room_type_id": 438550,
        "board_type_id": 44512,
        "rate_type_id": 24171,
        "rate_code_id": 183666,
        "price_agency_id": 247664,
        "currency": "EUR",
        "discounted_price": 1365.0,
        "total_price": 1365.0,
        "adult_count": 2,
        "check_in": "2026-10-01",
        "check_out": "2026-10-06",
        "guest_first_name": "Deneme",
        "guest_last_name": "Deneme",
        "guest_phone": "+905304498453",
        "guest_email": "gonenomeralperen@gmail.com",
        "child_ages": "[11,12]",
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_prepare_try_payment_retries_with_supplier_pax(monkeypatch):
    calls = []
    metric_calls = []

    async def _fake_update(*, hotel_id, reservation_id, updates, timeout_sec=20):
        calls.append(dict(updates))
        if len(calls) == 1:
            raise Exception(
                "adult-count and children counts (elder/younger/baby) doesn't match with price data, "
                "as found adult: 3, and elder-child-count: 1younger-child-count: 0baby-count: 0"
            )
        return {"success": True}

    monkeypatch.setattr(h, "update_elektraweb_reservation", _fake_update)
    monkeypatch.setattr(h, "record_metric", lambda *args, **kwargs: metric_calls.append((args, kwargs)))

    ok = await h._prepare_try_payment_on_supplier(
        reservation_id="89227844",
        hotel_id=21966,
        try_amount=273,
        booking=_sample_booking(),
    )

    assert ok is True
    assert len(calls) >= 2
    assert calls[1]["adult-count"] == 3
    assert calls[1]["elder-child-count"] == 1
    assert calls[1]["younger-child-count"] == 0
    assert calls[1]["baby-count"] == 0
    assert calls[1]["ROOMID"] == 438550
    assert isinstance(calls[1].get("guest-list"), list)
    assert calls[1]["guest-list"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_prepare_try_payment_does_not_force_currency_code_try(monkeypatch):
    captured = {}
    metric_calls = []

    async def _fake_update(*, hotel_id, reservation_id, updates, timeout_sec=20):
        captured.update(updates)
        return {"success": True}

    monkeypatch.setattr(h, "update_elektraweb_reservation", _fake_update)
    monkeypatch.setattr(h, "record_metric", lambda *args, **kwargs: metric_calls.append((args, kwargs)))

    ok = await h._prepare_try_payment_on_supplier(
        reservation_id="89227844",
        hotel_id=21966,
        try_amount=273,
        booking=_sample_booking(),
    )

    assert ok is True
    # Quote mismatch hatasini tetiklememek icin baz currency korunmali.
    assert captured.get("currency-code") == "EUR"
    assert captured.get("DEPOSITCURRENCYCODE") == "TRY"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_payment_intent_handoffs_instead_of_sending_usd_link(monkeypatch):
    booking = {
        "id": 102,
        "status": "elektra_created",
        "hotel_id": 21966,
        "elektra_reservation_id": "89381895",
        "booking_context_id": "CTX-0D1E714F",
        "guest_first_name": "Omer",
        "guest_last_name": "Gonen",
        "guest_phone": "+905304498453",
        "guest_email": "omer@example.com",
        "check_in": "2026-10-29",
        "check_out": "2026-10-31",
        "room_type_id": 438550,
        "board_type_id": 44512,
        "rate_type_id": 24171,
        "rate_code_id": 183666,
        "price_agency_id": 247664,
        "adult_count": 2,
        "currency": "EUR",
        "nights": 2,
        "total_price": 315.0,
        "discounted_price": 315.0,
        "updated_at": "2026-02-27T00:30:00",
        "created_at": "2026-02-27T00:20:00",
    }

    saved_ctx = {}
    takeover_calls = []
    handoff_payload = {}

    monkeypatch.setattr(h, "get_payment_context", lambda _phone: {"method": "link", "booking_id": 102})
    monkeypatch.setattr(h, "_is_test_phone", lambda _phone: False)
    monkeypatch.setattr(h, "get_latest_booking_by_phone", lambda *_args, **_kwargs: booking)
    monkeypatch.setattr(h, "get_hotel_booking", lambda _booking_id: booking)
    monkeypatch.setattr(h, "get_booking_by_context_id", lambda _ctx: None)
    monkeypatch.setattr(h, "get_active_bookings_by_phone", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(h, "clear_payment_context", lambda _phone: None)
    monkeypatch.setattr(
        h,
        "save_payment_context",
        lambda phone, data: saved_ctx.update({"phone": phone, "data": dict(data or {})}),
    )
    monkeypatch.setattr(
        h,
        "activate_human_takeover",
        lambda phone, reason="handoff": takeover_calls.append((phone, reason)) or True,
    )

    async def _fake_notify_admin_handoff(*_args, **kwargs):
        handoff_payload.update(kwargs)
        return True

    monkeypatch.setattr(h, "notify_admin_handoff", _fake_notify_admin_handoff)

    result = await h._handle_payment_intent("905304498453", "USD", "tr")

    assert isinstance(result, dict)
    assert result.get("status") == "handoff"
    assert "canlı müşteri temsilcimiz" in (result.get("reply") or "").lower()
    assert takeover_calls == [("905304498453", "payment_link_request")]
    assert handoff_payload.get("category") == "canli_destek"
    assert "ön ödeme talebi" in str(handoff_payload.get("customer_message", "")).lower()
    assert saved_ctx.get("phone") != "905304498453"
