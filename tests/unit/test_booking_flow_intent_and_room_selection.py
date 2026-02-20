import pytest

from app.handlers.booking_flow_handler import detect_booking_intent, _parse_room_selection


@pytest.mark.unit
def test_detect_booking_intent_with_turkish_chars():
    assert detect_booking_intent("exclusive pool oda için rezervasyon oluştur")


@pytest.mark.unit
def test_parse_room_selection_with_typo_exclusvie():
    rooms = [
        {"room_key": "exclusivePool", "is_refundable": False, "room_display": "Exclusive Pool"},
        {"room_key": "exclusivePool", "is_refundable": True, "room_display": "Exclusive Pool"},
    ]
    selected = _parse_room_selection("exclusvie pool oda için rezervasyon oluştur", rooms)
    assert selected is not None
    assert selected["room_key"] == "exclusivePool"
