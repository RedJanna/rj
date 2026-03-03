from __future__ import annotations

from app.handlers.booking_flow_handler import _build_booking_pending_reply


def test_booking_pending_reply_tr_contains_reservation_number_and_rule():
    reply = _build_booking_pending_reply(
        lang="tr",
        booking_id=12345,
        booking_ctx="CTX-AB12CD34",
        room_display="Superior (30m2)",
        check_in="2026-07-15",
        check_out="2026-07-22",
        price=1400,
        currency="EUR",
    )
    assert "Talep No: #12345" in reply
    assert "resmi rezervasyon numarası / Voucher No" in reply


def test_booking_pending_reply_en_contains_reservation_number_and_rule():
    reply = _build_booking_pending_reply(
        lang="en",
        booking_id=98765,
        booking_ctx="CTX-XYZ98765",
        room_display="Deluxe (25m2)",
        check_in="2026-08-01",
        check_out="2026-08-05",
        price=999,
        currency="EUR",
    )
    assert "Request No: #98765" in reply
    assert "official reservation number / Voucher No" in reply
