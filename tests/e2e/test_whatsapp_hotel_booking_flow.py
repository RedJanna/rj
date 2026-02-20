import os
from unittest.mock import AsyncMock

import pytest


os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("WHATSAPP_PHONE_ID", "test-phone")
os.environ.setdefault("WHATSAPP_TOKEN", "test-token")


def _build_offer(*, is_refundable: bool, price: float, rate_type_id: int, rate_code_id: int) -> dict:
    return {
        "room-type": "PREMIUM",
        "room-type-id": 66,
        "board-type-id": 2,
        "rate-type-id": rate_type_id,
        "rate-code-id": rate_code_id,
        "price-agency-id": 777,
        "currency-id": 44,
        "currency-code": "EUR",
        "price": price,
        "discounted-price": price,
        "cancellation-penalty": {"is-refundable": is_refundable},
    }


@pytest.fixture
def hotel_booking_client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import app.services.booking_flow_service as booking_flow_service

    monkeypatch.setattr(booking_flow_service, "BOOKING_FLOW_FILE", tmp_path / "booking_flows.json")

    import kassandra_openai_bot as bot

    bot.send_whatsapp_message = AsyncMock(return_value=True)
    if hasattr(bot, "QA_ENABLED"):
        bot.QA_ENABLED = False

    return TestClient(bot.app)


def _send(client, phone: str, message: str) -> dict:
    response = client.post("/chat", json={"phone": phone, "message": message})
    assert response.status_code == 200
    return response.json()


@pytest.mark.e2e
def test_whatsapp_hotel_booking_requires_name_and_contact(hotel_booking_client):
    from app.services.booking_flow_service import clear_booking_flow, save_price_offers

    phone = "905550009999"
    clear_booking_flow(phone)
    save_price_offers(
        phone,
        offers=[
            _build_offer(is_refundable=True, price=1045.0, rate_type_id=10, rate_code_id=101),
            _build_offer(is_refundable=False, price=950.0, rate_type_id=11, rate_code_id=102),
        ],
        query_params={
            "from_date": "2026-09-01",
            "to_date": "2026-09-05",
            "adult_count": 2,
            "child_ages": [5],
            "hotel_id": "21966",
            "currency": "EUR",
            "lang": "tr",
        },
    )

    r1 = _send(hotel_booking_client, phone, "premium oda için rezervasyon oluştur")
    assert "iki fiyat secenegi" in r1["reply"].lower()

    r2 = _send(hotel_booking_client, phone, "2")
    r2_low = r2["reply"].lower()
    assert "ad soyad" in r2_low
    assert "telefon" in r2_low
    assert "e-posta" in r2_low or "e posta" in r2_low

    r3 = _send(hotel_booking_client, phone, "Ahmet Yilmaz")
    r3_low = r3["reply"].lower()
    assert "iletisim" in r3_low
    assert "telefon" in r3_low or "e-posta" in r3_low

    r4 = _send(hotel_booking_client, phone, "Ahmet Yilmaz +905301112233")
    assert "ozel bir isteginiz var mi" in r4["reply"].lower()
