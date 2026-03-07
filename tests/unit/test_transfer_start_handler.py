from __future__ import annotations

import pytest

from app.handlers.transfer_start_handler import try_start_transfer_booking_flow


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_flow_starts_with_date_prompt(monkeypatch):
    state = {}

    monkeypatch.setattr(
        "app.handlers.transfer_start_handler.get_transfer_booking_flow",
        lambda _phone: state.get("flow", {"state": "idle", "data": {}}),
    )
    monkeypatch.setattr(
        "app.handlers.transfer_start_handler.update_transfer_booking_flow",
        lambda _phone, s, d=None: state.update({"flow": {"state": s, "data": dict(d or {})}}),
    )
    monkeypatch.setattr("app.handlers.transfer_start_handler.clear_transfer_booking_flow", lambda _phone: state.pop("flow", None))

    history = []
    saved = []

    async def _notify(**_kwargs):
        return None

    def _add(_phone, role, content):
        history.append((role, content))

    def _save(_phone, _msg, reply):
        saved.append(reply)

    result = await try_start_transfer_booking_flow(
        primary_intent="TRANSFER_BOOKING_REQUEST",
        user_message="Transfer ayarlamak istiyorum",
        phone="905001112233",
        history=[],
        start_time=0.0,
        detect_language_fn=lambda _m: "tr",
        notify_admin_handoff_fn=_notify,
        add_to_history_fn=_add,
        save_message_fn=_save,
        response_factory=lambda **kw: kw,
        record_metric_fn=lambda *_a, **_kw: None,
    )

    assert result["status"] == "transfer_flow"
    assert "1/5" in result["reply"]
    assert state["flow"]["state"] == "ask_date"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_flow_can_complete_and_create_reservation(monkeypatch):
    state = {"flow": {"state": "confirm", "data": {
        "transfer_date": "2026-06-15",
        "transfer_time": "14:30",
        "flight_no": "TK1234",
        "guest_text": "2 kişi",
        "transfer_route": "Dalaman Havalimani -> Kassandra Oludeniz",
    }}}
    created = {}

    monkeypatch.setattr(
        "app.handlers.transfer_start_handler.get_transfer_booking_flow",
        lambda _phone: state.get("flow", {"state": "idle", "data": {}}),
    )
    monkeypatch.setattr(
        "app.handlers.transfer_start_handler.update_transfer_booking_flow",
        lambda _phone, s, d=None: state.update({"flow": {"state": s, "data": dict(d or {})}}),
    )
    monkeypatch.setattr("app.handlers.transfer_start_handler.clear_transfer_booking_flow", lambda _phone: state.pop("flow", None))
    monkeypatch.setattr(
        "app.handlers.transfer_start_handler.create_transfer_reservation",
        lambda **kwargs: created.setdefault("reservation", {"id": 77, **kwargs}),
    )

    async def _notify(**_kwargs):
        return None

    result = await try_start_transfer_booking_flow(
        primary_intent="TRANSFER_BOOKING_REQUEST",
        user_message="Evet",
        phone="905001112233",
        history=[],
        start_time=0.0,
        detect_language_fn=lambda _m: "tr",
        notify_admin_handoff_fn=_notify,
        add_to_history_fn=lambda *_a, **_kw: None,
        save_message_fn=lambda *_a, **_kw: None,
        response_factory=lambda **kw: kw,
        record_metric_fn=lambda *_a, **_kw: None,
    )

    assert result["status"] == "transfer_flow_completed"
    assert "#77" in result["reply"]
    assert "flow" not in state
    assert created["reservation"]["source"] == "transfer_flow_chat"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_flow_applies_midflow_time_change_without_handoff(monkeypatch):
    state = {"flow": {"state": "ask_guest_count", "data": {
        "transfer_date": "2026-06-15",
        "transfer_time": "18:00",
        "flight_no": "TK1234",
    }}}

    monkeypatch.setattr(
        "app.handlers.transfer_start_handler.get_transfer_booking_flow",
        lambda _phone: state.get("flow", {"state": "idle", "data": {}}),
    )
    monkeypatch.setattr(
        "app.handlers.transfer_start_handler.update_transfer_booking_flow",
        lambda _phone, s, d=None: state.update({"flow": {"state": s, "data": dict(d or {})}}),
    )
    monkeypatch.setattr("app.handlers.transfer_start_handler.clear_transfer_booking_flow", lambda _phone: state.pop("flow", None))

    async def _notify(**_kwargs):
        raise AssertionError("handoff should not be called")

    result = await try_start_transfer_booking_flow(
        primary_intent="OUT_OF_SCOPE_OTHER",
        user_message="Pardon saati 19:00 yapalım",
        phone="905001112233",
        history=[],
        start_time=0.0,
        detect_language_fn=lambda _m: "tr",
        notify_admin_handoff_fn=_notify,
        add_to_history_fn=lambda *_a, **_kw: None,
        save_message_fn=lambda *_a, **_kw: None,
        response_factory=lambda **kw: kw,
        record_metric_fn=lambda *_a, **_kw: None,
    )

    assert result["status"] == "transfer_flow"
    assert "güncelledim" in result["reply"].lower()
    assert "kişi sayısını" in result["reply"].lower()
    assert state["flow"]["state"] == "ask_guest_count"
    assert state["flow"]["data"]["transfer_time"] == "19:00"
