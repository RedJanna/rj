import pytest

from app.services import elektraweb_booking_service as ews
from app.services.elektraweb_booking_service import (
    _derive_stay_eligible_room_keys,
    _derive_stay_eligible_room_type_ids_from_availability,
    _is_offer_bookable,
)


@pytest.mark.unit
def test_derive_stay_eligible_room_keys_requires_all_nights_room_to_sell_positive():
    rows = [
        {"DATE": "2026-04-18 00:00:00.000", "ROOMTYPECODE": "EXCLUSIVE POOL ", "ROOMTOSELL": 0, "STOPSELL": False},
        {"DATE": "2026-04-19 00:00:00.000", "ROOMTYPECODE": "EXCLUSIVE POOL ", "ROOMTOSELL": 1, "STOPSELL": False},
        {"DATE": "2026-04-18 00:00:00.000", "ROOMTYPECODE": "DELUXE", "ROOMTOSELL": 2, "STOPSELL": False},
        {"DATE": "2026-04-19 00:00:00.000", "ROOMTYPECODE": "DELUXE", "ROOMTOSELL": 2, "STOPSELL": False},
    ]

    keys = _derive_stay_eligible_room_keys(rows, from_date="2026-04-18", to_date="2026-04-20")
    assert "deluxe" in keys
    assert "exclusivePool" not in keys


@pytest.mark.unit
def test_derive_stay_eligible_room_keys_excludes_stop_sell_true():
    rows = [
        {"DATE": "2026-04-18 00:00:00.000", "ROOMTYPECODE": "SUPERIOR", "ROOMTOSELL": 5, "STOPSELL": False},
        {"DATE": "2026-04-19 00:00:00.000", "ROOMTYPECODE": "SUPERIOR", "ROOMTOSELL": 5, "STOPSELL": True},
    ]

    keys = _derive_stay_eligible_room_keys(rows, from_date="2026-04-18", to_date="2026-04-20")
    assert "superior" not in keys


@pytest.mark.unit
def test_derive_room_type_ids_from_booking_availability_requires_all_nights():
    rows = [
        {"date": "2026-04-18", "room-type-id": 396095, "room-to-sell": 2, "stop-sell": False},
        {"date": "2026-04-19", "room-type-id": 396095, "room-to-sell": 1, "stop-sell": False},
        {"date": "2026-04-18", "room-type-id": 396094, "room-to-sell": 2, "stop-sell": False},
    ]
    ids = _derive_stay_eligible_room_type_ids_from_availability(
        rows,
        from_date="2026-04-18",
        to_date="2026-04-20",
    )
    assert 396095 in ids
    assert 396094 not in ids


@pytest.mark.unit
def test_derive_room_type_ids_from_booking_availability_excludes_zero_or_stop_sell_nights():
    rows = [
        {"date": "2026-04-18", "room-type-id": 396095, "room-to-sell": 2, "stop-sell": False},
        {"date": "2026-04-19", "room-type-id": 396095, "room-to-sell": 0, "stop-sell": False},
        {"date": "2026-04-18", "room-type-id": 396094, "room-to-sell": 2, "stop-sell": False},
        {"date": "2026-04-19", "room-type-id": 396094, "room-to-sell": 2, "stop-sell": True},
    ]
    ids = _derive_stay_eligible_room_type_ids_from_availability(
        rows,
        from_date="2026-04-18",
        to_date="2026-04-20",
    )
    assert 396095 not in ids
    assert 396094 not in ids


@pytest.mark.unit
def test_derive_room_type_ids_from_booking_availability_fallbacks_when_capacity_fields_missing():
    rows = [
        {"date": "2026-04-18", "room-type-id": 396095},
        {"date": "2026-04-19", "room-type-id": 396095},
    ]
    ids = _derive_stay_eligible_room_type_ids_from_availability(
        rows,
        from_date="2026-04-18",
        to_date="2026-04-20",
    )
    assert 396095 in ids


@pytest.mark.unit
def test_is_offer_bookable_rejects_room_to_sell_and_stop_sell_and_zero_availability_arr():
    assert _is_offer_bookable(
        {
            "room-type": "EXCLUSIVE POOL",
            "room-to-sell": 0,
            "rate-rules": {"stop-sell": False},
            "availability-arr": [1, 1],
        }
    ) is False

    assert _is_offer_bookable(
        {
            "room-type": "EXCLUSIVE POOL",
            "room-to-sell": 2,
            "rate-rules": {"stop-sell": True},
            "availability-arr": [2, 2],
        }
    ) is False

    assert _is_offer_bookable(
        {
            "room-type": "EXCLUSIVE POOL",
            "room-to-sell": 2,
            "rate-rules": {"stop-sell": False},
            "availability-arr": [2, 0],
        }
    ) is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_stay_eligibility_uses_checkout_date_for_availability(monkeypatch):
    seen = {}

    async def _fake_fetch_availability(**kwargs):
        seen.update(kwargs)
        return [{"date": "2026-09-03", "room-type-id": 396095}]

    monkeypatch.setattr(ews, "fetch_availability", _fake_fetch_availability)

    result = await ews._fetch_stay_eligibility(
        hotel_id="21966",
        from_date="2026-09-03",
        to_date="2026-09-04",
        adult=3,
        currency="EUR",
    )

    assert seen["from_date"] == "2026-09-03"
    assert seen["to_date"] == "2026-09-04"
    assert 396095 in result["room_type_ids"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_room_stock_uses_checkout_date_for_availability(monkeypatch):
    seen = {}

    async def _fake_fetch_availability(**kwargs):
        seen.update(kwargs)
        return [{"date": "2026-09-03", "room-type-id": 396095, "room-to-sell": 2, "stop-sell": False}]

    monkeypatch.setattr(ews, "fetch_availability", _fake_fetch_availability)

    stock = await ews.fetch_room_stock_by_type_from_availability(
        hotel_id="21966",
        from_date="2026-09-03",
        to_date="2026-09-04",
        adult=3,
        currency="EUR",
        room_type_id_to_key={396095: "superior"},
    )

    assert seen["from_date"] == "2026-09-03"
    assert seen["to_date"] == "2026-09-04"
    assert stock.get("superior") == 2
