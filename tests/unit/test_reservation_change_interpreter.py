from __future__ import annotations

from app.services.reservation_change_interpreter import extract_slot_updates, is_change_request


def test_is_change_request_detects_edit_marker():
    assert is_change_request("Pardon saati 19:00 yapalım") is True


def test_is_change_request_detects_slot_payload():
    assert is_change_request("tarih 15 haziran 3 kişi") is True


def test_extract_slot_updates_maps_fields():
    updates = extract_slot_updates(
        "Pardon, 15 haziran saat 19:30, 3 kişi",
        date_parser=lambda _msg: "2026-06-15",
        time_parser=lambda _msg: "19:30",
        guest_count_parser=lambda _msg: 3,
    )
    assert updates["date"] == "2026-06-15"
    assert updates["time"] == "19:30"
    assert updates["guest_count"] == 3
