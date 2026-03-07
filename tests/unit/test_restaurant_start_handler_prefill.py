from __future__ import annotations

import pytest

from app.handlers.restaurant_start_handler import try_start_restaurant_reservation_flow


class _ReservationState:
    ASK_GUESTS = type("S", (), {"value": "ask_guests"})()
    ASK_DATE = type("S", (), {"value": "ask_date"})()
    ASK_TIME = type("S", (), {"value": "ask_time"})()
    ASK_NAME = type("S", (), {"value": "ask_name"})()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_restaurant_start_does_not_reask_date_when_date_and_guest_already_given():
    updated = {}

    async def _notify(**_kwargs):
        return None

    result = await try_start_restaurant_reservation_flow(
        primary_intent="RESTAURANT_BOOKING_CREATE",
        needs_handoff=False,
        handoff_category="",
        user_message="Akşam yemeği için 10 haziran'da 3 kişilik rezervasyon",
        phone="905551112233",
        start_time=0.0,
        restaurant_settings={"max_auto_reservation": 9},
        clear_reservation_flow_fn=lambda _p: None,
        notify_admin_handoff_fn=_notify,
        detect_language_fn=lambda _m: "tr",
        add_to_history_fn=lambda *_a, **_kw: None,
        save_message_fn=lambda *_a, **_kw: None,
        response_factory=lambda **kw: kw,
        extract_date_from_message_fn=lambda _m: "2026-06-10",
        parse_date_input_fn=lambda _m: "2026-06-10",
        extract_date_phrase_fn=lambda _m: "",
        is_within_season_fn=lambda _d: (True, ""),
        extract_time_from_message_fn=lambda _m: None,
        get_meal_type_from_time_fn=lambda _t: None,
        update_reservation_flow_fn=lambda _p, state, data: updated.update({"state": state, "data": dict(data)}),
        reservation_state_cls=_ReservationState,
        record_metric_fn=lambda *_a, **_kw: None,
        history=[],
    )

    assert result["status"] == "reservation_flow_started"
    assert updated["state"] == "ask_time"
    assert updated["data"]["guest_count"] == 3
    assert updated["data"]["date"] == "2026-06-10"
    assert "Hangi saati tercih edersiniz" in result["reply"]
