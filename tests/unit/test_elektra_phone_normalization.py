from __future__ import annotations

from app.services.elektraweb_booking_service import _normalize_phone_e164


def test_normalize_phone_e164_accepts_plus_format():
    assert _normalize_phone_e164("+90 530 449 84 53") == "+905304498453"


def test_normalize_phone_e164_converts_local_tr_mobile():
    assert _normalize_phone_e164("05304498453") == "+905304498453"
    assert _normalize_phone_e164("5304498453") == "+905304498453"


def test_normalize_phone_e164_rejects_too_short():
    assert _normalize_phone_e164("+7 2565 025") == ""

