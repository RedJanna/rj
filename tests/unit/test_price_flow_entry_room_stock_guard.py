from __future__ import annotations

import pytest

from app.handlers.price_flow_entry_handler import try_handle_price_flow_entry


@pytest.mark.asyncio
async def test_price_template_room_stock_question_does_not_auto_start_booking():
    booking_called = {"value": False}
    saved = []

    async def _handle_price_flow_fn(*_args, **_kwargs):
        return {
            "reply": "2026-08-10 - 2026-08-13 tarihleri arasında Premium için 2 adet müsait oda görünmektedir.",
            "status": "price_room_stock_result",
            "log": "room_stock_ok",
            "is_price_template": True,
        }

    async def _handle_booking_flow_fn(*_args, **_kwargs):
        booking_called["value"] = True
        return {"reply": "Harika seçim!", "status": "booking_flow", "log": None}

    def _response_factory(**kwargs):
        return kwargs

    result = await try_handle_price_flow_entry(
        phone="+905551112233",
        user_message="Kaç adet Premium oda müsaittir?",
        history=[],
        lang="tr",
        start_time=0.0,
        handle_price_flow_fn=_handle_price_flow_fn,
        notify_admin_handoff_fn=lambda **_kwargs: None,
        notify_admin_error_fn=lambda **_kwargs: None,
        add_to_history_fn=lambda *_args, **_kwargs: None,
        save_message_fn=lambda *_args, **_kwargs: saved.append(_args),
        schedule_followup_fn=lambda *_args, **_kwargs: None,
        record_metric_fn=lambda *_args, **_kwargs: None,
        response_factory=_response_factory,
        handle_booking_flow_fn=_handle_booking_flow_fn,
        detect_language_fn=lambda _msg: "tr",
    )

    assert result is not None
    assert result["status"] == "price_room_stock_result"
    assert "Harika seçim" not in result["reply"]
    assert booking_called["value"] is False
