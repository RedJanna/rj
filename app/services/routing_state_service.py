from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.services.state_store_service import JsonStateRepository, resolve_data_file

ROUTING_STATE_FILE = resolve_data_file("routing_states.json", env_var="KASSANDRA_ROUTING_STATE_FILE")
_ROUTING_STATE_STORE = JsonStateRepository(ROUTING_STATE_FILE)
ROUTING_STATE_TTL_MINUTES = 60
DOMAIN_LOCK_TTL_MINUTES = 15
AWAITING_CHOICE_LOCK = "awaiting_choice"


@dataclass(frozen=True)
class FlowRegistryRule:
    name: str
    base_priority: int
    keywords: tuple[str, ...]
    state_key: str


FLOW_REGISTRY: tuple[FlowRegistryRule, ...] = (
    FlowRegistryRule(
        name="booking",
        base_priority=30,
        keywords=("rezervasyon", "reservation", "book", "booking", "oda", "room"),
        state_key="booking",
    ),
    FlowRegistryRule(
        name="price",
        base_priority=20,
        keywords=("fiyat", "price", "ucret", "ücret", "gecelik", "nightly"),
        state_key="price",
    ),
    FlowRegistryRule(
        name="restaurant",
        base_priority=10,
        keywords=("restoran", "restaurant", "masa", "kahvalti", "kahvaltı", "aksam yemegi", "yemek"),
        state_key="restaurant",
    ),
)


def _load_states() -> Dict[str, Any]:
    return _ROUTING_STATE_STORE.load_dict()


def _save_states(data: Dict[str, Any]) -> None:
    _ROUTING_STATE_STORE.save_dict(data)


def _clean_phone(phone: str) -> str:
    return "".join(ch for ch in (phone or "") if ch.isdigit())


def get_active_flow(phone: str) -> Optional[str]:
    clean = _clean_phone(phone)
    if not clean:
        return None
    data = _load_states()
    item = data.get(clean)
    if not item:
        return None
    flow = item.get("active_flow")
    updated_at = item.get("updated_at")
    try:
        if updated_at:
            ts = datetime.fromisoformat(updated_at)
            if datetime.now() - ts > timedelta(minutes=ROUTING_STATE_TTL_MINUTES):
                # Active flow TTL dolunca sadece flow alanlarini temizle;
                # domain lock gibi diger routing state alanlarini koru.
                for key in ("active_flow", "reason", "updated_at"):
                    item.pop(key, None)
                if item:
                    data[clean] = item
                else:
                    data.pop(clean, None)
                _save_states(data)
                return None
    except Exception:
        for key in ("active_flow", "reason", "updated_at"):
            item.pop(key, None)
        if item:
            data[clean] = item
        else:
            data.pop(clean, None)
        _save_states(data)
        return None
    return flow if isinstance(flow, str) and flow else None


def set_active_flow(phone: str, flow: str, *, reason: str = "") -> None:
    clean = _clean_phone(phone)
    if not clean:
        return
    data = _load_states()
    now = datetime.now().isoformat()
    item = data.get(clean) or {}
    item["active_flow"] = flow
    item["reason"] = reason or ""
    item["updated_at"] = now
    data[clean] = item
    _save_states(data)


def clear_active_flow(phone: str) -> None:
    clean = _clean_phone(phone)
    if not clean:
        return
    data = _load_states()
    item = data.get(clean)
    if not item:
        return
    changed = False
    for key in ("active_flow", "reason", "updated_at"):
        if key in item:
            item.pop(key, None)
            changed = True
    if changed:
        if item:
            data[clean] = item
        else:
            data.pop(clean, None)
        _save_states(data)


def get_domain_lock(phone: str) -> Optional[str]:
    clean = _clean_phone(phone)
    if not clean:
        return None
    data = _load_states()
    item = data.get(clean) or {}
    lock = item.get("domain_lock")
    updated_at = item.get("domain_lock_updated_at")
    if not lock:
        return None
    try:
        if updated_at:
            ts = datetime.fromisoformat(updated_at)
            if datetime.now() - ts > timedelta(minutes=DOMAIN_LOCK_TTL_MINUTES):
                item.pop("domain_lock", None)
                item.pop("domain_lock_reason", None)
                item.pop("domain_lock_updated_at", None)
                if item:
                    data[clean] = item
                else:
                    data.pop(clean, None)
                _save_states(data)
                return None
    except Exception:
        item.pop("domain_lock", None)
        item.pop("domain_lock_reason", None)
        item.pop("domain_lock_updated_at", None)
        if item:
            data[clean] = item
        else:
            data.pop(clean, None)
        _save_states(data)
        return None
    return lock if isinstance(lock, str) and lock else None


def set_domain_lock(phone: str, domain: str, *, reason: str = "") -> None:
    clean = _clean_phone(phone)
    if not clean:
        return
    data = _load_states()
    now = datetime.now().isoformat()
    item = data.get(clean) or {}
    item["domain_lock"] = domain
    item["domain_lock_reason"] = reason or ""
    item["domain_lock_updated_at"] = now
    data[clean] = item
    _save_states(data)


def clear_domain_lock(phone: str) -> None:
    clean = _clean_phone(phone)
    if not clean:
        return
    data = _load_states()
    item = data.get(clean)
    if not item:
        return
    changed = False
    for key in ("domain_lock", "domain_lock_reason", "domain_lock_updated_at"):
        if key in item:
            item.pop(key, None)
            changed = True
    if changed:
        if item:
            data[clean] = item
        else:
            data.pop(clean, None)
        _save_states(data)


def _normalize_message(message: str) -> str:
    low = (message or "").lower()
    return re.sub(r"\s+", " ", low).strip()


def _flow_state_active(state_obj: Dict[str, Any]) -> bool:
    if not isinstance(state_obj, dict):
        return False
    current_state = (state_obj.get("state") or "").strip().lower()
    return bool(current_state and current_state not in {"idle"})


def resolve_flow_order_for_context(
    *,
    message: str,
    state: Dict[str, Any],
    available_flow_names: List[str],
) -> List[str]:
    """
    Merkezi flow registry sirasi:
    - Aktif flow state'leri en yuksek oncelik.
    - Domain lock ve mesaj anahtar kelimeleri ile skor artirimi.
    - Hic sinyal yoksa verilen default sirayi koru (geriye donuk uyumluluk).
    """
    if not available_flow_names:
        return []

    default_order = [name for name in available_flow_names if name]
    normalized = _normalize_message(message)
    routing_meta = (state or {}).get("_routing") or {}
    active_flow = (routing_meta.get("active_flow") or "").strip().lower()
    domain_lock = (routing_meta.get("domain_lock") or "").strip().lower()

    score_by_flow: Dict[str, int] = {name: 0 for name in default_order}
    saw_signal = False

    for rule in FLOW_REGISTRY:
        if rule.name not in score_by_flow:
            continue
        score_by_flow[rule.name] += rule.base_priority

        flow_state = (state or {}).get(rule.state_key) or {}
        if _flow_state_active(flow_state):
            score_by_flow[rule.name] += 100
            saw_signal = True

        if normalized and any(keyword in normalized for keyword in rule.keywords):
            score_by_flow[rule.name] += 20
            saw_signal = True

    if active_flow in score_by_flow:
        score_by_flow[active_flow] += 90
        saw_signal = True

    if domain_lock == "restaurant" and "restaurant" in score_by_flow:
        score_by_flow["restaurant"] += 80
        saw_signal = True
    elif domain_lock == "hotel":
        for name in ("booking", "price"):
            if name in score_by_flow:
                score_by_flow[name] += 70
                saw_signal = True

    if not saw_signal:
        return default_order

    indexed = {name: idx for idx, name in enumerate(default_order)}
    return sorted(
        default_order,
        key=lambda name: (-score_by_flow.get(name, 0), indexed.get(name, 9999)),
    )
