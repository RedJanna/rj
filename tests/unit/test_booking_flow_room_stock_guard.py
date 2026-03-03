from __future__ import annotations

import pytest

from app.handlers.booking_flow_handler import handle_booking_flow


@pytest.mark.asyncio
async def test_room_stock_question_does_not_enter_booking_flow():
    result = await handle_booking_flow(
        phone="905000000001",
        message="Kaç adet premium oda müsaittir?",
        history=[],
        lang="tr",
    )
    assert result is None
