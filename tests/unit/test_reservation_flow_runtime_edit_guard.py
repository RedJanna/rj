from __future__ import annotations

import pytest

from app.flows.reservation_flow_runtime import build_reservation_flow_handler


class _State:
    IDLE = type("S", (), {"value": "idle"})()
    ASK_GUESTS = type("S", (), {"value": "ask_guests"})()
    ASK_DATE = type("S", (), {"value": "ask_date"})()
    ASK_TIME = type("S", (), {"value": "ask_time"})()
    ASK_NAME = type("S", (), {"value": "ask_name"})()
    ASK_SPECIAL = type("S", (), {"value": "ask_special"})()
    CONFIRM = type("S", (), {"value": "confirm"})()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ask_name_correction_message_updates_time_not_name():
    updates = []

    handler = build_reservation_flow_handler(
        get_conversation_history_fn=lambda _p: [],
        detect_language_fn=lambda _m: "tr",
        update_reservation_flow_fn=lambda _p, s, d: updates.append((s, dict(d))),
        clear_reservation_flow_fn=lambda _p: None,
        should_break_reservation_flow_fn=lambda _m, _s: False,
        detect_correction_in_message_fn=lambda _m, _s: {"is_correction": True, "field": "time", "new_value": "19:00"},
        extract_all_reservation_info_fn=lambda _m: {"guest_count": None, "date": None, "time": None},
        get_meal_type_from_time_fn=lambda _t: "Dinner",
        notify_admin_handoff_fn=lambda *_a, **_kw: None,
        is_within_season_fn=lambda *_a, **_kw: (True, ""),
        reservation_state_cls=_State,
        format_date_turkish_fn=lambda d: d,
        format_date_english_fn=lambda d: d,
        create_reservation_fn=lambda **_kw: {"id": 1},
        format_reservation_confirmation_fn=lambda *_a, **_kw: "",
        send_reservation_pdf_fn=lambda *_a, **_kw: True,
        schedule_restaurant_reminder_fn=lambda *_a, **_kw: None,
    )

    flow = {
        "state": _State.ASK_NAME.value,
        "data": {"lang": "tr", "guest_count": 3, "date": "2026-06-11", "time": "18:00"},
    }
    reply = await handler("905551112233", "Pardon saati 19:00 olarak değiştirebilir miyiz?", flow)

    assert "saati 19:00 güncelledim" in str(reply)
    assert updates[-1][0] == _State.ASK_NAME.value
    assert updates[-1][1]["time"] == "19:00"
    assert "customer_name" not in updates[-1][1]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ask_time_guest_correction_keeps_time_prompt():
    updates = []

    handler = build_reservation_flow_handler(
        get_conversation_history_fn=lambda _p: [],
        detect_language_fn=lambda _m: "tr",
        update_reservation_flow_fn=lambda _p, s, d: updates.append((s, dict(d))),
        clear_reservation_flow_fn=lambda _p: None,
        should_break_reservation_flow_fn=lambda _m, _s: False,
        detect_correction_in_message_fn=lambda _m, _s: {"is_correction": True, "field": "guest_count", "new_value": 5},
        extract_all_reservation_info_fn=lambda _m: {"guest_count": None, "date": None, "time": None},
        get_meal_type_from_time_fn=lambda _t: "Dinner",
        notify_admin_handoff_fn=lambda *_a, **_kw: None,
        is_within_season_fn=lambda *_a, **_kw: (True, ""),
        reservation_state_cls=_State,
        format_date_turkish_fn=lambda d: d,
        format_date_english_fn=lambda d: d,
        create_reservation_fn=lambda **_kw: {"id": 1},
        format_reservation_confirmation_fn=lambda *_a, **_kw: "",
        send_reservation_pdf_fn=lambda *_a, **_kw: True,
        schedule_restaurant_reminder_fn=lambda *_a, **_kw: None,
    )

    flow = {
        "state": _State.ASK_TIME.value,
        "data": {"lang": "tr", "guest_count": 3, "date": "2026-06-11"},
    }
    reply = await handler("905551112233", "pardon kişi sayısı 5 olacak", flow)

    assert "kişi sayısını 5" in str(reply).lower()
    assert "Saat kaçı tercih edersiniz" in str(reply)
    assert "isim adına" not in str(reply).lower()
    assert updates[-1][0] == _State.ASK_TIME.value
    assert updates[-1][1]["guest_count"] == 5


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ask_time_time_correction_advances_to_ask_name():
    updates = []

    handler = build_reservation_flow_handler(
        get_conversation_history_fn=lambda _p: [],
        detect_language_fn=lambda _m: "tr",
        update_reservation_flow_fn=lambda _p, s, d: updates.append((s, dict(d))),
        clear_reservation_flow_fn=lambda _p: None,
        should_break_reservation_flow_fn=lambda _m, _s: False,
        detect_correction_in_message_fn=lambda _m, _s: {"is_correction": True, "field": "time", "new_value": "20:00"},
        extract_all_reservation_info_fn=lambda _m: {"guest_count": None, "date": None, "time": None},
        get_meal_type_from_time_fn=lambda _t: "Dinner",
        notify_admin_handoff_fn=lambda *_a, **_kw: None,
        is_within_season_fn=lambda *_a, **_kw: (True, ""),
        reservation_state_cls=_State,
        format_date_turkish_fn=lambda d: d,
        format_date_english_fn=lambda d: d,
        create_reservation_fn=lambda **_kw: {"id": 1},
        format_reservation_confirmation_fn=lambda *_a, **_kw: "",
        send_reservation_pdf_fn=lambda *_a, **_kw: True,
        schedule_restaurant_reminder_fn=lambda *_a, **_kw: None,
    )

    flow = {
        "state": _State.ASK_TIME.value,
        "data": {"lang": "tr", "guest_count": 3, "date": "2026-06-11"},
    }
    reply = await handler("905551112233", "saat 20:00 olsun", flow)

    assert "saati 20:00" in str(reply).lower()
    assert "Rezervasyon hangi isim adına olsun?" in str(reply)
    assert updates[-1][0] == _State.ASK_NAME.value
    assert updates[-1][1]["time"] == "20:00"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_confirm_state_correction_updates_summary_and_keeps_confirm():
    updates = []

    handler = build_reservation_flow_handler(
        get_conversation_history_fn=lambda _p: [],
        detect_language_fn=lambda _m: "tr",
        update_reservation_flow_fn=lambda _p, s, d: updates.append((s, dict(d))),
        clear_reservation_flow_fn=lambda _p: None,
        should_break_reservation_flow_fn=lambda _m, _s: False,
        detect_correction_in_message_fn=lambda _m, _s: {"is_correction": True, "field": "guest_count", "new_value": 4},
        extract_all_reservation_info_fn=lambda _m: {"guest_count": None, "date": None, "time": None},
        get_meal_type_from_time_fn=lambda _t: "Dinner",
        notify_admin_handoff_fn=lambda *_a, **_kw: None,
        is_within_season_fn=lambda *_a, **_kw: (True, ""),
        reservation_state_cls=_State,
        format_date_turkish_fn=lambda d: d,
        format_date_english_fn=lambda d: d,
        create_reservation_fn=lambda **_kw: {"id": 1},
        format_reservation_confirmation_fn=lambda *_a, **_kw: "",
        send_reservation_pdf_fn=lambda *_a, **_kw: True,
        schedule_restaurant_reminder_fn=lambda *_a, **_kw: None,
    )

    flow = {
        "state": _State.CONFIRM.value,
        "data": {
            "lang": "tr",
            "guest_count": 3,
            "date": "2026-06-11",
            "time": "19:00",
            "customer_name": "Deneme",
            "meal_type": "Dinner",
            "special_requests": None,
        },
    }
    reply = await handler("905551112233", "Kişi sayısı 4 olacak", flow)

    assert "kişi sayısını 4 güncelledim" in str(reply).lower()
    assert "👥 Kişi: 4" in str(reply)
    assert "Onaylamak için 'Evet'" in str(reply)
    assert updates[-1][0] == _State.CONFIRM.value
    assert updates[-1][1]["guest_count"] == 4
