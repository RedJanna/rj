from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes.hotel_bookings_routes import build_hotel_bookings_router


class _BookingStatus:
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    ELEKTRA_CREATED = "elektra_created"
    ELEKTRA_FAILED = "elektra_failed"


class _FakeElektraConfigError(RuntimeError):
    pass


def _sample_booking() -> dict:
    return {
        "id": 1,
        "status": _BookingStatus.PENDING_APPROVAL,
        "hotel_id": 21966,
        "check_in": "2026-09-01",
        "check_out": "2026-09-05",
        "room_type_id": 66,
        "board_type_id": 2,
        "rate_type_id": 11,
        "rate_code_id": 102,
        "price_agency_id": 777,
        "currency_id": 44,
        "currency": "EUR",
        "adult_count": 2,
        "guest_first_name": "Ahmet",
        "guest_last_name": "Yilmaz",
        "guest_phone": "+905301112233",
        "guest_email": "ahmet@test.com",
        "special_requests": "",
        "is_refundable": False,
        "room_type_display": "Premium - Jakuzili (45m2)",
        "customer_phone": "905550001111",
        "lang": "tr",
        "total_price": 950.0,
        "discounted_price": 950.0,
    }


@pytest.mark.integration
def test_approve_booking_returns_walkin_config_error_code():
    booking_store = {1: _sample_booking()}

    def get_booking(booking_id: int):
        return booking_store.get(booking_id)

    def update_status(booking_id: int, status: str, **kwargs):
        booking = booking_store[booking_id]
        booking["status"] = status
        booking["updated_at"] = datetime.now().isoformat()
        booking.update(kwargs)

    async def create_elektraweb_reservation_fn(**kwargs):
        raise _FakeElektraConfigError(
            "Eksik/hatali config: ELEKTRA_WALKIN_AGENCY_ID sayisal ve zorunlu olmali."
        )

    async def send_whatsapp_message_fn(phone: str, message: str):
        return True

    app = FastAPI()
    app.include_router(
        build_hotel_bookings_router(
            get_pending_hotel_bookings_fn=lambda: [],
            get_all_hotel_bookings_fn=lambda limit: [],
            get_hotel_booking_stats_fn=lambda: {},
            get_hotel_booking_fn=get_booking,
            update_hotel_booking_status_fn=update_status,
            create_elektraweb_reservation_fn=create_elektraweb_reservation_fn,
            send_whatsapp_message_fn=send_whatsapp_message_fn,
            booking_status=_BookingStatus,
            admin_phone="905550000000",
            elektra_config_error_cls=_FakeElektraConfigError,
        )
    )

    client = TestClient(app)
    response = client.post("/admin/hotel-bookings/1/approve")
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is False
    assert data["error_code"] == "ELEKTRA_CONFIG_MISSING_WALKIN"
    assert "WALKIN" in data["error"]
    assert booking_store[1]["status"] == _BookingStatus.ELEKTRA_FAILED


@pytest.mark.integration
def test_sync_elektra_booking_works_when_service_is_wired():
    booking = _sample_booking()
    booking["status"] = _BookingStatus.ELEKTRA_CREATED
    booking["elektra_reservation_id"] = "88865728"
    booking["elektra_response"] = '{"reservation-id":"88865728","voucher-no":"V123"}'
    booking_store = {1: booking}

    def get_booking(booking_id: int):
        return booking_store.get(booking_id)

    def update_status(booking_id: int, status: str, **kwargs):
        booking_store[booking_id]["status"] = status
        booking_store[booking_id].update(kwargs)

    async def create_elektraweb_reservation_fn(**kwargs):
        return {"reservation-id": "88865728"}

    async def send_whatsapp_message_fn(phone: str, message: str):
        return True

    async def get_elektraweb_reservation_fn(**kwargs):
        return {"success": True, "reservation-id": "88865728", "voucher-no": "V123"}

    app = FastAPI()
    app.include_router(
        build_hotel_bookings_router(
            get_pending_hotel_bookings_fn=lambda: [],
            get_all_hotel_bookings_fn=lambda limit: [],
            get_hotel_booking_stats_fn=lambda: {},
            get_hotel_booking_fn=get_booking,
            update_hotel_booking_status_fn=update_status,
            create_elektraweb_reservation_fn=create_elektraweb_reservation_fn,
            get_elektraweb_reservation_fn=get_elektraweb_reservation_fn,
            send_whatsapp_message_fn=send_whatsapp_message_fn,
            booking_status=_BookingStatus,
            admin_phone="905550000000",
        )
    )

    client = TestClient(app)
    response = client.post("/admin/hotel-bookings/1/elektra/sync")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert booking_store[1]["elektra_reservation_id"] == "88865728"


@pytest.mark.integration
def test_approve_booking_uses_elektra_price_in_customer_message():
    booking_store = {1: _sample_booking()}
    sent_messages = []

    def get_booking(booking_id: int):
        return booking_store.get(booking_id)

    def update_status(booking_id: int, status: str, **kwargs):
        booking = booking_store[booking_id]
        booking["status"] = status
        booking["updated_at"] = datetime.now().isoformat()
        booking.update(kwargs)

    async def create_elektraweb_reservation_fn(**kwargs):
        return {"success": True, "reservation-id": "88907390", "voucher-no": "V001"}

    async def get_elektraweb_reservation_fn(**kwargs):
        return {"success": True, "reservation-id": "88907390", "total-price": 1029}

    async def send_whatsapp_message_fn(phone: str, message: str):
        sent_messages.append((phone, message))
        return True

    app = FastAPI()
    app.include_router(
        build_hotel_bookings_router(
            get_pending_hotel_bookings_fn=lambda: [],
            get_all_hotel_bookings_fn=lambda limit: [],
            get_hotel_booking_stats_fn=lambda: {},
            get_hotel_booking_fn=get_booking,
            update_hotel_booking_status_fn=update_status,
            create_elektraweb_reservation_fn=create_elektraweb_reservation_fn,
            get_elektraweb_reservation_fn=get_elektraweb_reservation_fn,
            send_whatsapp_message_fn=send_whatsapp_message_fn,
            booking_status=_BookingStatus,
            admin_phone="905550000000",
        )
    )

    client = TestClient(app)
    response = client.post("/admin/hotel-bookings/1/approve")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

    customer_msgs = [m for p, m in sent_messages if p == booking_store[1]["customer_phone"]]
    assert customer_msgs
    assert "Toplam Fiyat: 1029 EUR" in customer_msgs[0]
