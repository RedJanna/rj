from __future__ import annotations

from app.services.routing_state_service import resolve_flow_order_for_context


def test_registry_prefers_active_price_flow():
    order = resolve_flow_order_for_context(
        message="Merhaba",
        state={
            "price": {"state": "ask_dates"},
            "booking": {"state": ""},
            "restaurant": {"state": ""},
            "_routing": {"active_flow": "price", "domain_lock": ""},
        },
        available_flow_names=["restaurant", "price", "booking"],
    )
    assert order[0] == "price"


def test_registry_prefers_restaurant_lock():
    order = resolve_flow_order_for_context(
        message="rezervasyon için yardımcı olur musunuz",
        state={
            "price": {"state": ""},
            "booking": {"state": ""},
            "restaurant": {"state": ""},
            "_routing": {"active_flow": "", "domain_lock": "restaurant"},
        },
        available_flow_names=["restaurant", "price", "booking"],
    )
    assert order[0] == "restaurant"


def test_registry_keeps_default_order_without_signal():
    default_order = ["restaurant", "price", "booking"]
    order = resolve_flow_order_for_context(
        message="selam",
        state={"price": {"state": ""}, "booking": {"state": ""}, "restaurant": {"state": ""}},
        available_flow_names=default_order,
    )
    assert order == default_order

