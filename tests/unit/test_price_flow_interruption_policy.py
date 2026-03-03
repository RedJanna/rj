from __future__ import annotations

from app.handlers.price_flow_handler import _is_policy_interruption_question


def test_policy_interruption_detects_late_checkin_question():
    assert _is_policy_interruption_question("Gece geç saatte (01:00 gibi) giriş yaparsak sorun olur mu?") is True


def test_policy_interruption_detects_parking_question():
    assert _is_policy_interruption_question("Otoparkınız var mı, ücretli mi?") is True


def test_policy_interruption_detects_start_reservation_message():
    assert _is_policy_interruption_question("Tamam, rezervasyonu başlatalım") is True

