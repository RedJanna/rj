# app/routes/metrics_routes.py
from __future__ import annotations

from fastapi import APIRouter, Body, Query
from typing import Any, Dict

from app.services.metrics_service import (
    record_metric,
    list_events,
    metrics_summary,
    reset_metrics,
)
from app.services.success_metrics_service import (
    SUCCESS_TARGETS,
    evaluate_success_scorecard,
)

router = APIRouter(prefix="/admin/metrics", tags=["metrics"])


# RAW EVENT LIST (asıl endpoint)
@router.get("/events")
def get_metrics_events(
    days: int = Query(7, ge=0, le=365),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    event_prefix: str = Query("", description="Event prefix filter, orn: security."),
) -> Dict[str, Any]:
    items, total = list_events(days=days, limit=limit, offset=offset, event_prefix=event_prefix)
    return {
        "items": items,
        "total": total,
        "days": int(days),
        "limit": int(limit),
        "event_prefix": (event_prefix or "").strip(),
    }


# Alias: /admin/metrics ve /admin/metrics/
@router.get("")
@router.get("/")
def get_metrics_events_alias(
    days: int = Query(7, ge=0, le=365),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    event_prefix: str = Query("", description="Event prefix filter, orn: security."),
) -> Dict[str, Any]:
    items, total = list_events(days=days, limit=limit, offset=offset, event_prefix=event_prefix)
    return {
        "items": items,
        "total": total,
        "days": int(days),
        "limit": int(limit),
        "event_prefix": (event_prefix or "").strip(),
    }


# RECORD
@router.post("/record")
def record_metrics_event(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    event = str(payload.get("event") or "").strip()
    category = str(payload.get("category") or "general").strip()
    response_time = payload.get("response_time", None)
    meta = payload.get("meta", None)

    try:
        rt_val = float(response_time) if response_time is not None else None
    except Exception:
        rt_val = None

    if meta is not None and not isinstance(meta, dict):
        meta = {"_raw": meta}

    inserted_id = record_metric(event=event, category=category, response_time=rt_val, meta=meta)
    return {"status": "ok", "id": inserted_id}


# (opsiyonel) özet
@router.get("/summary")
def get_metrics_summary(days: int = Query(7, ge=0, le=365)) -> Dict[str, Any]:
    return metrics_summary(days=days)


@router.post("/reset")
def reset_metrics_events(
    event_prefix: str = Query("", description="Optional event prefix filter."),
) -> Dict[str, Any]:
    deleted = reset_metrics(event_prefix=(event_prefix or "").strip())
    return {"status": "ok", "deleted": int(deleted), "event_prefix": (event_prefix or "").strip()}


@router.get("/success-targets")
def get_success_targets() -> Dict[str, Any]:
    return {"targets": SUCCESS_TARGETS}


@router.get("/success-scorecard")
def get_success_scorecard(days: int = Query(7, ge=1, le=365)) -> Dict[str, Any]:
    return evaluate_success_scorecard(days=days)
