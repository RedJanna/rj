from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.routes.admin_reservations_routes import build_admin_reservations_router


class _StatusItem:
    def __init__(self, value: str):
        self.value = value


class _ReservationStatus:
    PENDING = _StatusItem("pending")
    CONFIRMED = _StatusItem("confirmed")
    CANCELLED = _StatusItem("cancelled")
    COMPLETED = _StatusItem("completed")
    NO_SHOW = _StatusItem("no_show")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_confirm_reservation_sends_customer_message_and_pdf(tmp_path):
    calls = {"wa": 0, "pdf": 0}
    reservation = {
        "id": 7,
        "customer_phone": "905551112233",
        "customer_name": "Test User",
        "date": "2026-06-15",
        "time": "20:00",
        "guest_count": 2,
    }

    async def _send_whatsapp(_phone: str, _msg: str):
        calls["wa"] += 1
        return True

    async def _send_pdf(_phone: str, _reservation: dict):
        calls["pdf"] += 1
        return True

    router = build_admin_reservations_router(
        reservations_db=tmp_path / "reservations.db",
        reservation_status=_ReservationStatus,
        get_reservations_by_date_fn=lambda _d: [],
        get_upcoming_reservations_fn=lambda _d: [],
        get_todays_reservations_fn=lambda: [],
        get_reservation_fn=lambda _rid: dict(reservation),
        update_reservation_status_fn=lambda _rid, _status: True,
        cancel_reservation_fn=lambda *_a, **_kw: True,
        notify_admin_cancel_v2_fn=lambda *_a, **_kw: None,
        get_customer_reservations_fn=lambda _p: [],
        send_whatsapp_message_fn=_send_whatsapp,
        admin_phone="905000000000",
        format_reservation_confirmation_fn=lambda _r, _l: "onay mesaji",
        send_reservation_pdf_fn=_send_pdf,
    )

    app = FastAPI()
    app.include_router(router)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.post("/admin/reservations/7/confirm")
    payload = res.json()

    assert res.status_code == 200
    assert payload["status"] == "ok"
    assert payload["customer_notified"] is True
    assert payload["pdf_sent"] is True
    assert calls["wa"] == 1
    assert calls["pdf"] == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_send_pdf_endpoint_sends_document_for_existing_reservation(tmp_path):
    calls = {"pdf": 0}
    reservation = {
        "id": 11,
        "customer_phone": "905551112233",
        "customer_name": "Test User",
        "date": "2026-06-15",
        "time": "20:00",
        "guest_count": 2,
    }

    async def _send_whatsapp(_phone: str, _msg: str):
        return True

    async def _send_pdf(_phone: str, _reservation: dict):
        calls["pdf"] += 1
        return True

    router = build_admin_reservations_router(
        reservations_db=tmp_path / "reservations.db",
        reservation_status=_ReservationStatus,
        get_reservations_by_date_fn=lambda _d: [],
        get_upcoming_reservations_fn=lambda _d: [],
        get_todays_reservations_fn=lambda: [],
        get_reservation_fn=lambda _rid: dict(reservation),
        update_reservation_status_fn=lambda _rid, _status: True,
        cancel_reservation_fn=lambda *_a, **_kw: True,
        notify_admin_cancel_v2_fn=lambda *_a, **_kw: None,
        get_customer_reservations_fn=lambda _p: [],
        send_whatsapp_message_fn=_send_whatsapp,
        admin_phone="905000000000",
        format_reservation_confirmation_fn=lambda _r, _l: "onay mesaji",
        send_reservation_pdf_fn=_send_pdf,
    )

    app = FastAPI()
    app.include_router(router)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.post("/admin/reservations/11/send-pdf")
    payload = res.json()

    assert res.status_code == 200
    assert payload["status"] == "ok"
    assert payload["pdf_sent"] is True
    assert calls["pdf"] == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_send_pdf_endpoint_returns_error_when_reservation_missing(tmp_path):
    async def _send_whatsapp(_phone: str, _msg: str):
        return True

    async def _send_pdf(_phone: str, _reservation: dict):
        return True

    router = build_admin_reservations_router(
        reservations_db=tmp_path / "reservations.db",
        reservation_status=_ReservationStatus,
        get_reservations_by_date_fn=lambda _d: [],
        get_upcoming_reservations_fn=lambda _d: [],
        get_todays_reservations_fn=lambda: [],
        get_reservation_fn=lambda _rid: None,
        update_reservation_status_fn=lambda _rid, _status: True,
        cancel_reservation_fn=lambda *_a, **_kw: True,
        notify_admin_cancel_v2_fn=lambda *_a, **_kw: None,
        get_customer_reservations_fn=lambda _p: [],
        send_whatsapp_message_fn=_send_whatsapp,
        admin_phone="905000000000",
        format_reservation_confirmation_fn=lambda _r, _l: "onay mesaji",
        send_reservation_pdf_fn=_send_pdf,
    )

    app = FastAPI()
    app.include_router(router)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.post("/admin/reservations/999/send-pdf")
    payload = res.json()

    assert res.status_code == 200
    assert payload["status"] == "error"
