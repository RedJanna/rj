from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.services.metrics_service import list_events


SUCCESS_TARGETS: Dict[str, Dict[str, Any]] = {
    "containment_rate": {
        "label": "Containment Rate",
        "description": "Insana devretmeden tamamlanan konusma orani.",
        "target": 0.75,
        "direction": "gte",
    },
    "clarification_loop_rate": {
        "label": "Clarification Loop Rate",
        "description": "Arka arkaya netlestirme dongusune dusen oran.",
        "target": 0.10,
        "direction": "lte",
    },
    "false_handoff_rate": {
        "label": "False Handoff Rate",
        "description": "Gereksiz handoff (yanlis pozitif) orani.",
        "target": 0.05,
        "direction": "lte",
    },
    "false_auto_rate": {
        "label": "False Auto Rate",
        "description": "Yanlis otomatik cevap orani.",
        "target": 0.03,
        "direction": "lte",
    },
    "p95_response_time_seconds": {
        "label": "P95 Response Time (s)",
        "description": "95. yuzdelik cevap suresi.",
        "target": 6.0,
        "direction": "lte",
    },
}


AUTO_EVENTS = {"local", "openai", "local_faq", "first_message", "greeting", "menu"}
HANDOFF_EVENTS = {"handoff", "handoff.packet", "handoff.packet_reject"}


def _safe_rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def _percentile(values: List[float], q: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    idx = int((len(s) - 1) * q)
    return float(s[idx])


def _status(metric_key: str, actual: float | None) -> str:
    if actual is None:
        return "no_data"
    target = float(SUCCESS_TARGETS[metric_key]["target"])
    direction = str(SUCCESS_TARGETS[metric_key]["direction"])
    if direction == "gte":
        return "pass" if actual >= target else "fail"
    return "pass" if actual <= target else "fail"


def evaluate_success_scorecard(days: int = 7) -> Dict[str, Any]:
    items, total = list_events(days=days, limit=10_000, offset=0)

    auto_count = 0
    handoff_count = 0
    clarify_loop_count = 0
    false_handoff_count = 0
    false_auto_count = 0
    response_times: List[float] = []

    for row in items:
        event = str(row.get("event") or "").strip()
        if event in AUTO_EVENTS:
            auto_count += 1
        if event in HANDOFF_EVENTS or event.startswith("handoff."):
            handoff_count += 1
        if event == "clarify_loop":
            clarify_loop_count += 1
        if event == "handoff.false_positive":
            false_handoff_count += 1
        if event == "auto.false_positive":
            false_auto_count += 1

        rt = row.get("response_time")
        if isinstance(rt, (int, float)):
            response_times.append(float(rt))

    resolution_base = auto_count + handoff_count
    containment_rate = _safe_rate(auto_count, resolution_base)
    clarification_loop_rate = _safe_rate(clarify_loop_count, total)
    false_handoff_rate = _safe_rate(false_handoff_count, handoff_count)
    false_auto_rate = _safe_rate(false_auto_count, auto_count)
    p95_response_time = _percentile(response_times, 0.95)

    metrics = {
        "containment_rate": {
            **SUCCESS_TARGETS["containment_rate"],
            "actual": containment_rate,
            "status": _status("containment_rate", containment_rate),
            "numerator": auto_count,
            "denominator": resolution_base,
        },
        "clarification_loop_rate": {
            **SUCCESS_TARGETS["clarification_loop_rate"],
            "actual": clarification_loop_rate,
            "status": _status("clarification_loop_rate", clarification_loop_rate),
            "numerator": clarify_loop_count,
            "denominator": total,
        },
        "false_handoff_rate": {
            **SUCCESS_TARGETS["false_handoff_rate"],
            "actual": false_handoff_rate,
            "status": _status("false_handoff_rate", false_handoff_rate),
            "numerator": false_handoff_count,
            "denominator": handoff_count,
        },
        "false_auto_rate": {
            **SUCCESS_TARGETS["false_auto_rate"],
            "actual": false_auto_rate,
            "status": _status("false_auto_rate", false_auto_rate),
            "numerator": false_auto_count,
            "denominator": auto_count,
        },
        "p95_response_time_seconds": {
            **SUCCESS_TARGETS["p95_response_time_seconds"],
            "actual": p95_response_time,
            "status": _status("p95_response_time_seconds", p95_response_time),
            "sample_size": len(response_times),
        },
    }

    return {
        "days": int(days),
        "event_total": int(total),
        "counts": {
            "auto": int(auto_count),
            "handoff": int(handoff_count),
            "clarify_loop": int(clarify_loop_count),
            "false_handoff": int(false_handoff_count),
            "false_auto": int(false_auto_count),
        },
        "metrics": metrics,
    }
