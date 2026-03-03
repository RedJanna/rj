from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict

from app.services.state_store_service import JsonStateRepository, resolve_data_file

MESSAGE_ID_STORE_FILE = resolve_data_file("message_ids.json", env_var="KASSANDRA_MESSAGE_ID_FILE")
_MESSAGE_ID_STORE = JsonStateRepository(MESSAGE_ID_STORE_FILE)
MESSAGE_ID_TTL_HOURS = 24


def _load_store() -> Dict[str, Any]:
    return _MESSAGE_ID_STORE.load_dict()


def _save_store(data: Dict[str, Any]) -> None:
    _MESSAGE_ID_STORE.save_dict(data)


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
