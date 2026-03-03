from __future__ import annotations

from typing import Any, Dict

from app.services.intent_policy_service import infer_primary_intent
from app.services.intent_semantic_service import infer_domain_from_message, infer_intent_semantic

def infer_domain_hint(message: str) -> str:
    return infer_domain_from_message(message)


def route_intent(message: str, domain_hint: str = "unknown") -> Dict[str, Any]:
    semantic_intent, semantic_confidence = infer_intent_semantic(message, route_domain=domain_hint)
    intent = infer_primary_intent(message, domain_hint)
    return {
        "primary_intent": intent,
        "domain_hint": domain_hint,
        "semantic_intent": semantic_intent,
        "semantic_confidence": round(float(semantic_confidence), 4),
        "router": "intent_router_v1",
    }
