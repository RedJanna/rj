from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Dict, List, Tuple


ALLOWED_PRIORITIES = {"low", "medium", "high", "critical"}


def build_handoff_packet(
    *,
    category: str,
    priority: str,
    customer_phone: str,
    customer_message: str,
    source: str = "chat_runtime",
    detected_intent: str = "unknown",
    confidence: float | None = None,
    conversation_summary: str = "",
    attempted_actions: list[str] | None = None,
    suggested_reply: str = "",
    tags: list[str] | None = None,
    correlation_id: str = "",
    trigger_type: str = "soft",
    sla_target_minutes: int = 30,
    within_business_hours: bool = True,
    language_lock: str = "en",
) -> Dict[str, Any]:
    msg = (customer_message or "").strip()
    phone = (customer_phone or "").strip()
    raw_id = f"{category}|{priority}|{phone}|{msg}|{datetime.now().isoformat()}".encode("utf-8", errors="ignore")
    packet_id = hashlib.sha256(raw_id).hexdigest()[:16]
    return {
        "packet_id": packet_id,
        "timestamp": datetime.now().isoformat(),
        "source": source or "chat_runtime",
        "category": (category or "").strip(),
        "priority": (priority or "").strip().lower(),
        "customer_phone": phone,
        "customer_message": msg,
        "detected_intent": (detected_intent or "unknown").strip(),
        "confidence": confidence,
        "conversation_summary": (conversation_summary or "").strip(),
        "attempted_actions": attempted_actions or [],
        "suggested_reply": (suggested_reply or "").strip(),
        "tags": tags or [],
        "correlation_id": (correlation_id or "").strip(),
        "trigger_type": (trigger_type or "soft").strip().lower(),
        "sla_target_minutes": int(sla_target_minutes),
        "within_business_hours": bool(within_business_hours),
        "language_lock": (language_lock or "en").strip().lower(),
    }


def validate_handoff_packet(packet: Dict[str, Any]) -> Tuple[bool, List[str]]:
    missing: List[str] = []
    if not (packet.get("packet_id") or "").strip():
        missing.append("packet_id")
    if not (packet.get("source") or "").strip():
        missing.append("source")
    if not (packet.get("category") or "").strip():
        missing.append("category")
    if not (packet.get("customer_phone") or "").strip():
        missing.append("customer_phone")
    if not (packet.get("customer_message") or "").strip():
        missing.append("customer_message")
    if not (packet.get("detected_intent") or "").strip():
        missing.append("detected_intent")
    if packet.get("priority") not in ALLOWED_PRIORITIES:
        missing.append("priority")
    if packet.get("trigger_type") not in {"hard", "soft"}:
        missing.append("trigger_type")
    try:
        if int(packet.get("sla_target_minutes", 0)) <= 0:
            missing.append("sla_target_minutes")
    except Exception:
        missing.append("sla_target_minutes")
    if not isinstance(packet.get("within_business_hours"), bool):
        missing.append("within_business_hours")
    if not (packet.get("language_lock") or "").strip():
        missing.append("language_lock")
    # confidence is optional, but if present it must be in [0, 1]
    conf = packet.get("confidence")
    if conf is not None:
        try:
            c = float(conf)
            if c < 0.0 or c > 1.0:
                missing.append("confidence_range")
        except Exception:
            missing.append("confidence_type")
    return (len(missing) == 0), missing
