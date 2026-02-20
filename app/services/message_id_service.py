from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict


MESSAGE_ID_STORE_FILE = Path("data/message_ids.json")
MESSAGE_ID_TTL_HOURS = 24


def _load_store() -> Dict[str, Any]:
    if not MESSAGE_ID_STORE_FILE.exists():
        return {}
    try:
        with open(MESSAGE_ID_STORE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_store(data: Dict[str, Any]) -> None:
    MESSAGE_ID_STORE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(MESSAGE_ID_STORE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _clean_phone(phone: str) -> str:
    return "".join(ch for ch in (phone or "") if ch.isdigit())


def _prune_expired(store: Dict[str, Any]) -> bool:
    now = datetime.now()
    changed = False
    for phone in list(store.keys()):
        raw_items = store.get(phone, {})
        if not isinstance(raw_items, dict):
            store.pop(phone, None)
            changed = True
            continue
        kept: Dict[str, str] = {}
        for msg_id, ts in raw_items.items():
            try:
                dt = datetime.fromisoformat(ts)
                if now - dt <= timedelta(hours=MESSAGE_ID_TTL_HOURS):
                    kept[msg_id] = ts
            except Exception:
                continue
        if kept:
            store[phone] = kept
        else:
            store.pop(phone, None)
        if kept != raw_items:
            changed = True
    return changed


def is_processed_message_id(phone: str, message_id: str) -> bool:
    clean = _clean_phone(phone)
    if not clean or not message_id:
        return False
    store = _load_store()
    changed = _prune_expired(store)
    found = message_id in store.get(clean, {})
    if changed:
        _save_store(store)
    return found


def mark_message_id_processed(phone: str, message_id: str) -> None:
    clean = _clean_phone(phone)
    if not clean or not message_id:
        return
    store = _load_store()
    _prune_expired(store)
    phone_map = store.get(clean, {})
    if not isinstance(phone_map, dict):
        phone_map = {}
    phone_map[message_id] = datetime.now().isoformat()
    store[clean] = phone_map
    _save_store(store)


def clear_message_ids(phone: str) -> None:
    clean = _clean_phone(phone)
    if not clean:
        return
    store = _load_store()
    if clean in store:
        store.pop(clean, None)
        _save_store(store)

