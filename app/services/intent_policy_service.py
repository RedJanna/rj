from __future__ import annotations

import re
from typing import Any, Dict

from app.services.intent_semantic_service import infer_intent_semantic


INTENT_SLOT_TOOL_MATRIX: Dict[str, Dict[str, Any]] = {
    "GREETING": {"allowed_tools": ["local_response_template"], "required_slots": []},
    "SMALLTALK_CLOSING": {"allowed_tools": ["local_response_template"], "required_slots": []},
    "HOTEL_BOOKING_CREATE": {"allowed_tools": ["booking_api", "availability_api", "price_api"], "required_slots": ["check_in_date", "check_out_date", "adult_count"]},
    "HOTEL_BOOKING_MODIFY": {"allowed_tools": ["booking_lookup_api", "booking_update_api"], "required_slots": ["booking_ref_or_match_key", "change_fields"]},
    "HOTEL_BOOKING_CANCEL": {"allowed_tools": ["booking_lookup_api", "booking_cancel_api"], "required_slots": ["booking_ref_or_match_key"]},
    "PRICE_QUERY": {"allowed_tools": ["price_api", "availability_api"], "required_slots": ["check_in_date", "check_out_date", "adult_count"]},
    "AVAILABILITY_QUERY": {"allowed_tools": ["availability_api"], "required_slots": ["check_in_date", "check_out_date", "adult_count"]},
    "RESTAURANT_BOOKING_CREATE": {"allowed_tools": ["restaurant_booking_create_api"], "required_slots": ["reservation_date", "reservation_time", "guest_count", "reservation_name"]},
    "RESTAURANT_BOOKING_MODIFY": {"allowed_tools": ["restaurant_booking_lookup_api", "restaurant_booking_update_api"], "required_slots": ["restaurant_booking_ref_or_match_key", "change_fields"]},
    "RESTAURANT_BOOKING_CANCEL": {"allowed_tools": ["restaurant_booking_lookup_api", "restaurant_booking_cancel_api"], "required_slots": ["restaurant_booking_ref_or_match_key"]},
    "TRANSFER_INFO": {"allowed_tools": ["local_transfer_info_template"], "required_slots": []},
    "TRANSFER_BOOKING_REQUEST": {"allowed_tools": ["transfer_booking_api"], "required_slots": ["transfer_date", "transfer_time", "flight_no", "guest_count", "route"]},
    "PAYMENT_METHOD_QUERY": {"allowed_tools": ["payment_method_info_template"], "required_slots": []},
    "PAYMENT_LINK_REQUEST": {"allowed_tools": ["booking_lookup_api", "payment_link_api"], "required_slots": ["booking_ref"]},
    "LOCAL_FAQ_INFO": {"allowed_tools": ["local_faq_kb"], "required_slots": ["faq_topic"]},
    "COMPLAINT": {"allowed_tools": ["handoff_ticket_api"], "required_slots": ["complaint_text"]},
    "DISCOUNT_NEGOTIATION": {"allowed_tools": ["handoff_ticket_api"], "required_slots": ["target_product_or_booking_context"]},
    "HUMAN_AGENT_REQUEST": {"allowed_tools": ["handoff_ticket_api"], "required_slots": []},
    "SPECIAL_REQUEST_EVENT": {"allowed_tools": ["handoff_ticket_api"], "required_slots": ["event_type"]},
    "URGENT_CASE": {"allowed_tools": ["handoff_ticket_api", "critical_notify_api"], "required_slots": ["urgent_reason"]},
    "RISK_ABUSE": {"allowed_tools": ["safety_guard", "suspicious_notify_api"], "required_slots": ["risk_text"]},
    "AI_IDENTITY_QUESTION": {"allowed_tools": ["fixed_identity_template"], "required_slots": []},
    "OUT_OF_SCOPE_OTHER": {"allowed_tools": ["clarification_template"], "required_slots": []},
}


def _norm(text: str) -> str:
    return (text or "").strip().lower()


def has_booking_reference(text: str) -> bool:
    return bool(re.search(r"\b(CTX-[A-Z0-9]{6,}|A\d{1,2})\b", (text or "").upper()))


def infer_primary_intent(message: str, route_domain: str | None = None) -> str:
    intent_name, score = infer_intent_semantic(message, route_domain=route_domain)
    if intent_name != "OUT_OF_SCOPE_OTHER":
        return intent_name
    if score >= 0.18 and route_domain == "restaurant":
        return "RESTAURANT_BOOKING_CREATE"
    if score >= 0.18 and route_domain == "payment":
        return "PAYMENT_METHOD_QUERY"
    if score >= 0.18 and route_domain == "hotel":
        return "PRICE_QUERY"
    return "OUT_OF_SCOPE_OTHER"


def get_intent_policy(intent_name: str) -> Dict[str, Any]:
    return INTENT_SLOT_TOOL_MATRIX.get(intent_name, INTENT_SLOT_TOOL_MATRIX["OUT_OF_SCOPE_OTHER"])


def intent_allows_tool(intent_name: str, tool_name: str) -> bool:
    policy = get_intent_policy(intent_name)
    return tool_name in (policy.get("allowed_tools") or [])


def intent_allows_any_tool(intent_name: str, tool_names: list[str]) -> bool:
    allowed = set((get_intent_policy(intent_name).get("allowed_tools") or []))
    return any(t in allowed for t in tool_names)
