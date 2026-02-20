from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional


ROUTING_STATE_FILE = Path("data/routing_states.json")
ROUTING_STATE_TTL_MINUTES = 60
DOMAIN_LOCK_TTL_MINUTES = 15
AWAITING_CHOICE_LOCK = "awaiting_choice"


def _load_states() -> Dict[str, Any]:
    if not ROUTING_STATE_FILE.exists():
        return {}
    try:
        with open(ROUTING_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_states(data: Dict[str, Any]) -> None:
    ROUTING_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(ROUTING_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


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
                data.pop(clean, None)
                _save_states(data)
                return None
    except Exception:
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
    data[clean] = {
        "active_flow": flow,
        "reason": reason or "",
        "updated_at": now,
    }
    _save_states(data)


def clear_active_flow(phone: str) -> None:
    clean = _clean_phone(phone)
    if not clean:
        return
    data = _load_states()
    if clean in data:
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
