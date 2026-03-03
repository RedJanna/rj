from __future__ import annotations

from app.services.slot_contract_service import (
    evaluate_slot_coverage,
    should_request_slot_clarification,
)


def test_price_query_slot_coverage_missing_dates():
    result = evaluate_slot_coverage("PRICE_QUERY", "fiyat nedir?")
    assert result["has_minimum_required"] is False
    assert "check_in_date" in result["missing_required_slots"]
    assert "adult_count" in result["missing_required_slots"]


def test_payment_link_slot_coverage_with_reference():
    result = evaluate_slot_coverage("PAYMENT_LINK_REQUEST", "CTX-AB12CD için ödeme linki atar mısınız?")
    assert result["has_minimum_required"] is True
    assert result["missing_required_slots"] == []


def test_restaurant_booking_create_slot_coverage():
    result = evaluate_slot_coverage(
        "RESTAURANT_BOOKING_CREATE",
        "2 kişi yarın saat 20:00 için isim Ali",
    )
    assert result["has_minimum_required"] is True


def test_should_request_slot_clarification_when_missing_and_no_active_flow():
    coverage = evaluate_slot_coverage("PRICE_QUERY", "fiyat nedir?")
    assert should_request_slot_clarification("PRICE_QUERY", coverage, has_active_flow=False) is True


def test_should_not_request_slot_clarification_when_active_flow():
    coverage = evaluate_slot_coverage("PRICE_QUERY", "fiyat nedir?")
    assert should_request_slot_clarification("PRICE_QUERY", coverage, has_active_flow=True) is False
