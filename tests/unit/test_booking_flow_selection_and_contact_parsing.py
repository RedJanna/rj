from __future__ import annotations

import pytest

from app.handlers import booking_flow_handler as h
from app.services.booking_flow_service import BookingFlowState


@pytest.mark.unit
@pytest.mark.asyncio
async def test_select_room_numeric_choice_does_not_reask_price_type(monkeypatch):
    selected = {
        "room_key": "exclusivePool",
        "is_refundable": True,
        "room_display": "Exclusive Havuz Manzaralı (40m2)",
        "price": 508.2,
        "currency": "EUR",
        "offer": {},
    }
    alt = {
        "room_key": "exclusivePool",
        "is_refundable": False,
        "room_display": "Exclusive Havuz Manzaralı (40m2)",
        "price": 462.0,
        "currency": "EUR",
        "offer": {},
    }
    saved_states: list[str] = []

    monkeypatch.setattr(h, "get_price_offers", lambda _phone: {"offers": [{}], "query_params": {}})
    monkeypatch.setattr(h, "get_available_rooms_from_offers", lambda _offers, _lang: [selected, alt])
    monkeypatch.setattr(h, "_parse_room_selection", lambda _msg, _rooms: selected)
    monkeypatch.setattr(h, "_build_flow_data_from_selection", lambda _selected, _query, _phone="": {})
    monkeypatch.setattr(h, "save_booking_flow", lambda _phone, state, _data: saved_states.append(state))

    result = await h._handle_select_room("905551112233", "8", {}, "tr")

    assert result is not None
    assert result["status"] == "booking_flow"
    assert "İki fiyat seçeneği mevcuttur" not in result["reply"]
    assert "Lütfen aşağıdaki bilgileri yazın" in result["reply"]
    assert saved_states and saved_states[-1] == BookingFlowState.ASK_NAME


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ask_name_accepts_natural_contact_sentence_and_current_phone(monkeypatch):
    saved_states: list[str] = []
    data = {}

    monkeypatch.setattr(h, "save_booking_flow", lambda _phone, state, _data: saved_states.append(state))

    result = await h._handle_ask_name(
        phone="905304498453",
        message="Ömer alperen gönen, gsdfkmsd@gmail.com ve bu telefon numarasını kayıt edebilirsiniz sisteme",
        data=data,
        lang="tr",
    )

    assert result is not None
    assert result["status"] == "booking_flow"
    assert "Teşekkürler!" in result["reply"]
    assert data["guest_first_name"] == "Ömer"
    assert data["guest_last_name"] == "Alperen Gönen"
    assert data.get("guest_email", "") == ""
    assert data.get("guest_phone", "") == ""
    assert saved_states and saved_states[-1] == BookingFlowState.ASK_PHONE


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ask_name_accepts_unicode_name_variants(monkeypatch):
    saved_states: list[str] = []
    data = {}

    monkeypatch.setattr(h, "save_booking_flow", lambda _phone, state, _data: saved_states.append(state))

    # "ö" combining formu ile gelirken de parse basarili olmali.
    result = await h._handle_ask_name(
        phone="905304498453",
        message="oomer oome\u0308r",
        data=data,
        lang="tr",
    )

    assert result is not None
    assert result["status"] == "booking_flow"
    assert data["guest_first_name"] == "Oomer"
    assert data["guest_last_name"] == "Oomër"
    assert saved_states and saved_states[-1] == BookingFlowState.ASK_PHONE


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ask_phone_normalizes_to_e164_and_moves_next(monkeypatch):
    saved_states: list[str] = []
    data = {"guest_first_name": "Omer", "guest_last_name": "Gonen"}

    monkeypatch.setattr(h, "save_booking_flow", lambda _phone, state, _data: saved_states.append(state))

    result = await h._handle_ask_phone(
        phone="905304498453",
        message="0530 449 84 53",
        data=data,
        lang="tr",
    )

    assert result is not None
    assert result["status"] == "booking_flow"
    assert data["guest_phone"] == "+905304498453"
    assert saved_states and saved_states[-1] == BookingFlowState.ASK_EMAIL


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ask_phone_rejects_invalid_short_number(monkeypatch):
    data = {"guest_first_name": "Omer", "guest_last_name": "Gonen"}
    called = {"save": False}

    monkeypatch.setattr(h, "save_booking_flow", lambda *_args, **_kwargs: called.update({"save": True}))

    result = await h._handle_ask_phone(
        phone="905304498453",
        message="+7 2565 025",
        data=data,
        lang="tr",
    )

    assert result is not None
    assert result["status"] == "booking_flow"
    assert "ülke koduyla geçerli" in result["reply"].lower()
    assert data.get("guest_phone", "") == ""
    assert called["save"] is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ask_name_does_not_treat_change_message_as_name(monkeypatch):
    saved_states: list[str] = []
    data = {}

    monkeypatch.setattr(h, "save_booking_flow", lambda _phone, state, _data: saved_states.append(state))

    result = await h._handle_ask_name(
        phone="905304498453",
        message="Pardon saati 19:00 olarak değiştirebilir miyiz?",
        data=data,
        lang="tr",
    )

    assert result is not None
    assert result["status"] == "booking_flow"
    assert "ad soyad" in result["reply"].lower()
    assert "guest_first_name" not in data
    assert saved_states == []
