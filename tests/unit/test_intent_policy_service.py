from __future__ import annotations

from app.services.intent_policy_service import (
    has_booking_reference,
    infer_primary_intent,
    intent_allows_any_tool,
    intent_allows_tool,
)


def test_infer_primary_intent_payment_link():
    assert infer_primary_intent("Ödeme linki gönderir misiniz?") == "PAYMENT_LINK_REQUEST"


def test_infer_primary_intent_price():
    assert infer_primary_intent("Temmuz için fiyat nedir?") == "PRICE_QUERY"


def test_has_booking_reference():
    assert has_booking_reference("CTX-AB12CD için link atar mısınız?")
    assert not has_booking_reference("ödeme linki atar mısın")


def test_intent_allows_tool():
    assert intent_allows_tool("PRICE_QUERY", "price_api")
    assert not intent_allows_tool("PRICE_QUERY", "payment_link_api")


def test_intent_allows_any_tool():
    assert intent_allows_any_tool("PAYMENT_LINK_REQUEST", ["payment_link_api", "booking_api"])
    assert not intent_allows_any_tool("GREETING", ["booking_api", "price_api"])


def test_infer_primary_intent_semantic_with_typo():
    assert infer_primary_intent("rezervsayon yapmak istiyroum, 2 yetiskin") == "HOTEL_BOOKING_CREATE"
