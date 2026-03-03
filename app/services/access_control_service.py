# Dosya Adı: app/services/access_control_service.py
from __future__ import annotations

import re
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from app.services.state_store_service import JsonStateRepository

# app/services/... -> parents[2] = proje root (C:\KassandraOpenAI)
BASE_DIR = Path(__file__).resolve().parents[2]

BLACKLIST_FILE = BASE_DIR / "blacklist.json"
PAUSED_FILE = BASE_DIR / "paused_conversations.json"
_BLACKLIST_STORE = JsonStateRepository(BLACKLIST_FILE)
_PAUSED_STORE = JsonStateRepository(PAUSED_FILE)


def _clean_phone(phone: str) -> str:
    """Telefonu sadece rakamlara indirger."""
    if not phone:
        return ""
    return re.sub(r"[^\d]", "", phone)


# ======================================================
# BLACKLIST
# ======================================================

def load_blacklist() -> List[str]:
    """blacklist.json -> {"blacklist":[...]} okur."""
    data = _BLACKLIST_STORE.load_dict()
    out = data.get("blacklist", [])
    if isinstance(out, list):
        return out
    return []


def save_blacklist(numbers: List[str]) -> None:
    """blacklist.json yazar (updated_at dahil)."""
    cleaned: List[str] = []
    for n in numbers or []:
        cn = _clean_phone(str(n))
        if cn:
            cleaned.append(cn)

    _BLACKLIST_STORE.save_dict(
        {"blacklist": cleaned, "updated_at": datetime.now().isoformat()}
    )


def is_blacklisted(phone: str) -> bool:
    """Mevcut davranışı korur: eşitlik + endswith/startswith benzeri karşılaştırma."""
    if not phone:
        return False

    clean_phone = _clean_phone(phone)
    if not clean_phone:
        return False

    blacklist = load_blacklist()
    for bl_number in blacklist:
        clean_bl = _clean_phone(str(bl_number))
        if not clean_bl:
            continue
        if clean_phone == clean_bl or clean_phone.endswith(clean_bl) or clean_bl.endswith(clean_phone):
            return True

    return False


def add_to_blacklist(phone: str) -> bool:
    clean_phone = _clean_phone(phone)
    if not clean_phone:
        return False

    blacklist = load_blacklist()
    if clean_phone not in blacklist:
        blacklist.append(clean_phone)
        save_blacklist(blacklist)
        return True

    return False


def remove_from_blacklist(phone: str) -> bool:
    clean_phone = _clean_phone(phone)
    if not clean_phone:
        return False

    blacklist = load_blacklist()
    if clean_phone in blacklist:
        blacklist.remove(clean_phone)
        save_blacklist(blacklist)
        return True

    return False


# ======================================================
# PAUSED CONVERSATIONS
# ======================================================

def load_paused() -> Dict:
    """paused_conversations.json -> {"paused": {...}} okur."""
    data = _PAUSED_STORE.load_dict()
    if isinstance(data, dict):
        data.setdefault("paused", {})
        if not isinstance(data.get("paused"), dict):
            data["paused"] = {}
        return data
    return {"paused": {}}


def save_paused(data: Dict) -> None:
    """paused_conversations.json yazar."""
    if not isinstance(data, dict):
        data = {"paused": {}}
    data.setdefault("paused", {})
    if not isinstance(data.get("paused"), dict):
        data["paused"] = {}
    _PAUSED_STORE.save_dict(data)


def is_paused(phone: str) -> bool:
    if not phone:
        return False
    clean_phone = _clean_phone(phone)
    if not clean_phone:
        return False
    data = load_paused()
    return clean_phone in data.get("paused", {})


def pause_conversation(phone: str, reason: str = "manual") -> None:
    clean_phone = _clean_phone(phone)
    if not clean_phone:
        return

    data = load_paused()
    data.setdefault("paused", {})
    data["paused"][clean_phone] = {
        "paused_at": datetime.now().isoformat(),
        "reason": reason or "manual",
    }
    save_paused(data)


def resume_conversation(phone: str) -> None:
    clean_phone = _clean_phone(phone)
    if not clean_phone:
        return

    data = load_paused()
    paused_map = data.get("paused", {})
    if isinstance(paused_map, dict) and clean_phone in paused_map:
        del paused_map[clean_phone]
        data["paused"] = paused_map
        save_paused(data)


def activate_human_takeover(phone: str, reason: str = "handoff") -> bool:
    """
    İnsan devri gerektiren durumlarda müşteri konuşmasını bot akışından pause eder.
    Opsiyonel: AUTO_BLACKLIST_ON_HANDOFF=true ise blacklist'e de ekler.
    """
    clean_phone = _clean_phone(phone)
    if not clean_phone:
        return False
    auto_blacklist = str(os.getenv("AUTO_BLACKLIST_ON_HANDOFF", "false")).strip().lower() in {"1", "true", "yes", "on"}
    if auto_blacklist:
        add_to_blacklist(clean_phone)
    pause_conversation(clean_phone, reason=f"human_takeover:{(reason or 'handoff')[:80]}")
    return True
