import pytest

from app.services.booking_flow_service import get_available_rooms_from_offers


@pytest.mark.unit
def test_room_type_mapping_tolerates_variations_for_exclusive_pool():
    offers = [
        {
            "room-type": "EXCLUSIVE POOL VIEW ROOM",
            "cancellation-penalty": {"is-refundable": False},
            "discounted-price": 1085.0,
            "currency": "EUR",
        },
        {
            "room-type": "EXCLUSIVE POOL VIEW ROOM",
            "cancellation-penalty": {"is-refundable": True},
            "discounted-price": 1195.0,
            "currency": "EUR",
        },
    ]

    rooms = get_available_rooms_from_offers(offers, "tr")
    keys = [r["room_key"] for r in rooms]
    assert "exclusivePool" in keys


@pytest.mark.unit
def test_room_mapping_excludes_unavailable_offers():
    offers = [
        {
            "room-type": "SUPERIOR ROOM",
            "cancellation-penalty": {"is-refundable": False},
            "discounted-price": 800.0,
            "currency": "EUR",
            "available": False,
        },
        {
            "room-type": "DELUXE ROOM",
            "cancellation-penalty": {"is-refundable": False},
            "discounted-price": 900.0,
            "currency": "EUR",
            "available": True,
        },
    ]
    rooms = get_available_rooms_from_offers(offers, "tr")
    keys = [r["room_key"] for r in rooms]
    assert "superior" not in keys
    assert "deluxe" in keys
