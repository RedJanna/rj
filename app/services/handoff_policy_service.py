from __future__ import annotations

from datetime import datetime
from typing import Dict

from app.services.handoff_critical_registry import (
    DEFAULT_SLA_MINUTES,
    HANDOFF_BUSINESS_HOURS,
    HANDOFF_POLICY_BY_CATEGORY,
    PRIORITY_RANK,
    RANK_PRIORITY,
)


def is_within_handoff_business_hours(now: datetime | None = None) -> bool:
    t = now or datetime.now()
    current_hour = t.hour
    start = int(HANDOFF_BUSINESS_HOURS["start_hour"])
    end = int(HANDOFF_BUSINESS_HOURS["end_hour"])
    if end < start:
        return current_hour >= start or current_hour < end
    return start <= current_hour < end


def apply_handoff_policy(category: str, requested_priority: str) -> Dict[str, str | int | bool]:
    cat = (category or "").strip().lower()
    req = (requested_priority or "medium").strip().lower()
    if req not in PRIORITY_RANK:
        req = "medium"

    cfg = HANDOFF_POLICY_BY_CATEGORY.get(cat, {})
    trigger_type = str(cfg.get("trigger_type", "soft"))
    min_priority = str(cfg.get("min_priority", "medium"))
    if min_priority not in PRIORITY_RANK:
        min_priority = "medium"
    eff_rank = max(PRIORITY_RANK[req], PRIORITY_RANK[min_priority])
    effective_priority = RANK_PRIORITY[eff_rank]

    business_hours = is_within_handoff_business_hours()
    base_sla = int(cfg.get("sla_minutes", DEFAULT_SLA_MINUTES.get(trigger_type, 30)))
    if not business_hours and trigger_type == "hard":
        # Mesai dışı hard trigger: daha agresif SLA.
        base_sla = min(base_sla, 10)
        effective_priority = "critical"

    return {
        "category": cat,
        "trigger_type": trigger_type,
        "requested_priority": req,
        "effective_priority": effective_priority,
        "sla_target_minutes": base_sla,
        "within_business_hours": business_hours,
    }
