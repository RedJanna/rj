import sqlite3
from pathlib import Path

import pytest

from app.services import booking_flow_service


@pytest.mark.unit
def test_get_latest_booking_by_phone_prefers_elektra_created(tmp_path, monkeypatch):
    db_path = tmp_path / "hotel_bookings.db"
    monkeypatch.setattr(booking_flow_service, "HOTEL_BOOKINGS_DB", Path(db_path))

    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE hotel_bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_phone TEXT,
            status TEXT,
            elektra_reservation_id TEXT,
            created_at TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO hotel_bookings (customer_phone, status, elektra_reservation_id, created_at) VALUES (?, ?, ?, ?)",
        ("905304498453", "approved", None, "2026-02-16T10:00:00"),
    )
    conn.execute(
        "INSERT INTO hotel_bookings (customer_phone, status, elektra_reservation_id, created_at) VALUES (?, ?, ?, ?)",
        ("905304498453", "elektra_created", "88865728", "2026-02-16T10:01:00"),
    )
    conn.commit()
    conn.close()

    booking = booking_flow_service.get_latest_booking_by_phone("+90 530 449 84 53")
    assert booking is not None
    assert booking["status"] == "elektra_created"
    assert booking["elektra_reservation_id"] == "88865728"

