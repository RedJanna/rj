from __future__ import annotations

from app.services.elektraweb_booking_service import _extract_room_stock_from_availability_rows


def test_extract_room_stock_from_availability_rows_returns_min_per_night():
    rows = [
        {"date": "2026-08-10", "room-type": "PREMIUM", "room-to-sell": 3, "stop-sell": False},
        {"date": "2026-08-11", "room-type": "PREMIUM", "room-to-sell": 2, "stop-sell": False},
        {"date": "2026-08-12", "room-type": "PREMIUM", "room-to-sell": 4, "stop-sell": False},
    ]
    out = _extract_room_stock_from_availability_rows(
        rows,
        from_date="2026-08-10",
        to_date="2026-08-13",
    )
    assert out.get("premium") == 2


def test_extract_room_stock_stop_sell_forces_zero():
    rows = [
        {"date": "2026-08-10", "room-type": "PREMIUM", "room-to-sell": 3, "stop-sell": False},
        {"date": "2026-08-11", "room-type": "PREMIUM", "room-to-sell": 5, "stop-sell": True},
        {"date": "2026-08-12", "room-type": "PREMIUM", "room-to-sell": 4, "stop-sell": False},
    ]
    out = _extract_room_stock_from_availability_rows(
        rows,
        from_date="2026-08-10",
        to_date="2026-08-13",
    )
    assert out.get("premium") == 0
