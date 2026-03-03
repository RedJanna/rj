from __future__ import annotations

from app.flows.flow_contract import FlowContext, FlowResult
from app.services.booking_flow_service import BookingFlowAdapter
from app.services.price_flow_service import PriceFlowAdapter
from app.services.restaurant_reservation_flow_service import RestaurantReservationFlowAdapter


def _context(message: str, *, state=None) -> FlowContext:
    return FlowContext(
        user_id="905551110000",
        channel="whatsapp",
        message=message,
        locale="tr",
        correlation_id="test-cid-001",
        state=state or {},
    )


def test_restaurant_adapter_contract_roundtrip():
    adapter = RestaurantReservationFlowAdapter()
    ctx = _context("Restoran için 2 kişi yarın 19:00")
    assert adapter.can_handle(ctx) is True
    result = adapter.handle(ctx)
    assert isinstance(result, FlowResult)
    assert "restaurant" in result.next_state


def test_price_adapter_contract_roundtrip():
    adapter = PriceFlowAdapter()
    ctx = _context("Oda fiyatı alabilir miyim?")
    assert adapter.can_handle(ctx) is True
    result = adapter.handle(ctx)
    assert isinstance(result, FlowResult)
    assert "price" in result.next_state


def test_booking_adapter_contract_roundtrip():
    adapter = BookingFlowAdapter()
    ctx = _context("Otel rezervasyon yapmak istiyorum")
    assert adapter.can_handle(ctx) is True
    result = adapter.handle(ctx)
    assert isinstance(result, FlowResult)
    assert "booking" in result.next_state

