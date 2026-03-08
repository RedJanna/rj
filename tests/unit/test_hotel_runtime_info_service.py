from __future__ import annotations

import json

import pytest

from app.services.hotel_runtime_info_service import (
    build_runtime_hard_override_block,
    normalize_hotel_runtime_info,
)


@pytest.mark.unit
def test_normalize_hotel_runtime_info_preserves_unknown_keys():
    payload = {
        "hotel_opening_mmdd": "04-20",
        "hotel_closing_mmdd": "11-10",
        "new_runtime_field": "dynamic-value",
        "restaurant_last_order_time": "21:30",
    }
    normalized = normalize_hotel_runtime_info(payload)
    assert normalized["hotel_opening_mmdd"] == "04-20"
    assert normalized["new_runtime_field"] == "dynamic-value"
    assert normalized["restaurant_last_order_time"] == "21:30"


@pytest.mark.unit
def test_runtime_override_block_contains_full_runtime_payload():
    info = normalize_hotel_runtime_info(
        {
            "hotel_opening_mmdd": "04-20",
            "hotel_closing_mmdd": "11-10",
            "new_runtime_field": "dynamic-value",
        }
    )
    block = build_runtime_hard_override_block(info)
    assert "Season open/close (MM-DD): 04-20 - 11-10" in block
    assert "Full runtime payload (JSON):" in block
    assert "new_runtime_field" in block

    json_str = block.split("Full runtime payload (JSON): ", 1)[1].split("\n", 1)[0]
    parsed = json.loads(json_str)
    assert parsed["new_runtime_field"] == "dynamic-value"

