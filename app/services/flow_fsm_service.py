from __future__ import annotations

from typing import Any, Dict, Optional


PRICE_INTENTS = {"PRICE_QUERY", "AVAILABILITY_QUERY"}
BOOKING_INTENTS = {
    "HOTEL_BOOKING_CREATE",
    "HOTEL_BOOKING_MODIFY",
    "HOTEL_BOOKING_CANCEL",
    "PAYMENT_METHOD_QUERY",
    "PAYMENT_LINK_REQUEST",
}


def decide_execution_order(
    *,
    primary_intent: str,
    active_flow: Optional[str],
    booking_flow_active: bool = False,
    price_flow_active: bool = False,
) -> Dict[str, Any]:
    """Phase-2 FSM baglanti noktasi.

    Return value:
      - order: stage-6 icin calisma sirasi (booking/price)
      - reason: karar aciklamasi
      - active_flow: normalize edilmis aktif flow
    """
    normalized_active = (active_flow or "").strip().lower() or None
    intent = str(primary_intent or "").strip().upper()

    if booking_flow_active:
        return {
            "order": ["booking", "price"],
            "reason": "booking_state_priority",
            "active_flow": normalized_active,
            "booking_flow_active": True,
            "price_flow_active": bool(price_flow_active),
        }

    if price_flow_active:
        return {
            "order": ["price", "booking"],
            "reason": "price_state_priority",
            "active_flow": normalized_active,
            "booking_flow_active": bool(booking_flow_active),
            "price_flow_active": True,
        }

    if normalized_active == "price":
        return {
            "order": ["price", "booking"],
            "reason": "active_flow_price_priority",
            "active_flow": normalized_active,
            "booking_flow_active": bool(booking_flow_active),
            "price_flow_active": bool(price_flow_active),
        }

    if normalized_active == "booking":
        return {
            "order": ["booking", "price"],
            "reason": "active_flow_booking_priority",
            "active_flow": normalized_active,
            "booking_flow_active": bool(booking_flow_active),
            "price_flow_active": bool(price_flow_active),
        }

    if intent in PRICE_INTENTS:
        return {
            "order": ["price", "booking"],
            "reason": "intent_price_priority",
            "primary_intent": intent,
            "active_flow": normalized_active,
            "booking_flow_active": bool(booking_flow_active),
            "price_flow_active": bool(price_flow_active),
        }

    if intent in BOOKING_INTENTS:
        return {
            "order": ["booking", "price"],
            "reason": "intent_booking_priority",
            "primary_intent": intent,
            "active_flow": normalized_active,
            "booking_flow_active": bool(booking_flow_active),
            "price_flow_active": bool(price_flow_active),
        }

    return {
        "order": ["booking", "price"],
        "reason": "default_booking_priority",
        "primary_intent": intent,
        "active_flow": normalized_active,
        "booking_flow_active": bool(booking_flow_active),
        "price_flow_active": bool(price_flow_active),
    }
