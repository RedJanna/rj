from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.booking_flow_service import get_booking_flow
from app.services.price_flow_service import get_price_flow
from app.services.restaurant_reservation_flow_service import get_reservation_flow
from app.services.routing_state_service import get_active_flow, get_domain_lock
from app.services.transfer_reservation_service import get_transfer_booking_flow
from app.utils.message_utils import detect_language


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DECISION_TRACE_FILE = PROJECT_ROOT / "logs" / "decision_trace.jsonl"
CHAT_LAB_EVENT_FILE = PROJECT_ROOT / "logs" / "admin_chat_lab_events.jsonl"
BACKEND_BOOT_LOG_FILE = PROJECT_ROOT / "backend_boot.log"

SUPPORTED_LANGS = {"en", "tr", "ru", "de", "ar", "es", "fr", "zh", "hi", "pt"}
LANGUAGE_NAME_ALIASES = {
    "en": ["english", "ingilizce"],
    "tr": ["turkish", "türkçe", "turkce"],
    "ru": ["russian", "rusça", "rusca", "русский", "по-русски"],
    "de": ["german", "almanca", "deutsch"],
    "ar": ["arabic", "arapça", "arapca", "العربية", "عربي"],
    "es": ["spanish", "ispanyolca", "español", "espanol"],
    "fr": ["french", "fransızca", "fransizca", "français", "francais"],
    "zh": ["chinese", "çince", "cince", "中文", "汉语", "漢語"],
    "hi": ["hindi", "hintçe", "hintce", "हिंदी"],
    "pt": ["portuguese", "portekizce", "português", "portugues"],
}
LANGUAGE_SWITCH_MARKERS = [
    "speak",
    "talk",
    "continue in",
    "write in",
    "konuş",
    "konusalim",
    "konuşalım",
    "devam edelim",
    "yaz",
]


def _clean_phone(phone: str) -> str:
    return re.sub(r"[^\d]", "", phone or "")


def _append_jsonl_row(path: Path, payload: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        return


def append_chat_lab_event(payload: Dict[str, Any]) -> None:
    row = {
        "ts": datetime.now().isoformat(),
        **(payload or {}),
    }
    _append_jsonl_row(CHAT_LAB_EVENT_FILE, row)


def _read_jsonl_filtered(
    path: Path,
    *,
    phone: str = "",
    correlation_id: str = "",
    limit: int = 50,
) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    clean_phone = _clean_phone(phone)
    matched: List[Dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []

    for line in reversed(lines):
        if len(matched) >= limit:
            break
        try:
            row = json.loads(line)
        except Exception:
            continue
        if correlation_id and str(row.get("correlation_id") or "").strip() != correlation_id:
            continue
        if clean_phone and _clean_phone(str(row.get("phone") or "")) != clean_phone:
            continue
        matched.append(row)
    matched.reverse()
    return matched


def read_decision_traces(*, phone: str = "", correlation_id: str = "", limit: int = 80) -> List[Dict[str, Any]]:
    return _read_jsonl_filtered(
        DECISION_TRACE_FILE,
        phone=phone,
        correlation_id=correlation_id,
        limit=limit,
    )


def read_chat_lab_events(*, phone: str = "", correlation_id: str = "", limit: int = 30) -> List[Dict[str, Any]]:
    return _read_jsonl_filtered(
        CHAT_LAB_EVENT_FILE,
        phone=phone,
        correlation_id=correlation_id,
        limit=limit,
    )


def read_backend_log_events(*, phone: str = "", correlation_id: str = "", limit: int = 30) -> List[Dict[str, Any]]:
    if not BACKEND_BOOT_LOG_FILE.exists():
        return []
    clean_phone = _clean_phone(phone)
    matched: List[Dict[str, Any]] = []
    try:
        lines = BACKEND_BOOT_LOG_FILE.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []

    for line in reversed(lines):
        if len(matched) >= limit:
            break
        line = line.strip()
        if not line:
            continue
        parsed: Dict[str, Any]
        try:
            parsed = json.loads(line)
            payload_phone = _clean_phone(str(parsed.get("phone") or ""))
            payload_correlation = str(parsed.get("correlation_id") or "")
            if correlation_id and payload_correlation != correlation_id:
                continue
            if clean_phone and payload_phone != clean_phone:
                continue
        except Exception:
            if correlation_id and correlation_id not in line:
                continue
            if clean_phone and clean_phone not in line:
                continue
            parsed = {"raw": line}
        matched.append(parsed)
    matched.reverse()
    return matched


def load_conversation_messages(conversations_dir: Path, phone: str, *, limit: int = 24) -> Dict[str, Any]:
    clean = _clean_phone(phone)
    if not clean:
        return {"phone": "", "exists": False, "messages": []}
    path = conversations_dir / f"{clean}.json"
    if not path.exists():
        return {"phone": clean, "exists": False, "messages": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"phone": clean, "exists": False, "messages": []}

    messages = payload.get("messages")
    if not isinstance(messages, list):
        messages = []
    return {
        "phone": clean,
        "exists": True,
        "updated_at": payload.get("updated_at"),
        "created_at": payload.get("created_at"),
        "message_count": len(messages),
        "messages": messages[-limit:],
    }


def _extract_language_switch_request(text: str) -> str:
    low = (text or "").strip().lower()
    if not low:
        return ""
    has_marker = any(marker in low for marker in LANGUAGE_SWITCH_MARKERS) or "?" in low
    if not has_marker:
        return ""
    for lang, aliases in LANGUAGE_NAME_ALIASES.items():
        if any(alias in low for alias in aliases):
            return lang
    return ""


def infer_language_lock(messages: List[Dict[str, Any]]) -> str:
    items = messages or []
    for item in reversed(items):
        user_text = str(item.get("user_message") or "").strip()
        target = _extract_language_switch_request(user_text)
        if target:
            return target if target in SUPPORTED_LANGS else "en"
    for item in items:
        user_text = str(item.get("user_message") or "").strip()
        if user_text:
            lang = str(detect_language(user_text) or "en").strip().lower()
            return lang if lang in SUPPORTED_LANGS else "en"
    return "en"


def _derive_active_flow_state(phone: str) -> Dict[str, Any]:
    reservation_flow = get_reservation_flow(phone) or {}
    transfer_flow = get_transfer_booking_flow(phone) or {}
    price_flow = get_price_flow(phone) or {}
    booking_flow = get_booking_flow(phone) or {}
    active_flow = get_active_flow(phone)
    domain_lock = get_domain_lock(phone)

    flow_bundle = {
        "routing": {
            "active_flow": active_flow,
            "domain_lock": domain_lock,
        },
        "reservation": reservation_flow,
        "transfer": transfer_flow,
        "price": price_flow,
        "booking": booking_flow,
    }

    if isinstance(booking_flow, dict) and str(booking_flow.get("state") or "").strip().lower() not in {"", "idle"}:
        return {
            "label": f"BOOKING_{str(booking_flow.get('state') or '').upper()}",
            "next_step": str(booking_flow.get("state") or "").strip().lower(),
            "flows": flow_bundle,
        }
    if isinstance(price_flow, dict) and str(price_flow.get("state") or "").strip().lower() not in {"", "idle"}:
        return {
            "label": f"PRICE_{str(price_flow.get('state') or '').upper()}",
            "next_step": str(price_flow.get("state") or "").strip().lower(),
            "flows": flow_bundle,
        }
    if isinstance(transfer_flow, dict) and str(transfer_flow.get("state") or "").strip().lower() not in {"", "idle"}:
        return {
            "label": f"TRANSFER_{str(transfer_flow.get('state') or '').upper()}",
            "next_step": str(transfer_flow.get("state") or "").strip().lower(),
            "flows": flow_bundle,
        }
    if isinstance(reservation_flow, dict) and str(reservation_flow.get("state") or "").strip().lower() not in {"", "idle"}:
        return {
            "label": f"RESTAURANT_{str(reservation_flow.get('state') or '').upper()}",
            "next_step": str(reservation_flow.get("state") or "").strip().lower(),
            "flows": flow_bundle,
        }
    if active_flow:
        return {
            "label": str(active_flow).strip().upper(),
            "next_step": str(active_flow).strip().lower(),
            "flows": flow_bundle,
        }
    return {
        "label": "GREETING",
        "next_step": "await_user_intent",
        "flows": flow_bundle,
    }


def _derive_intent_summary(traces: List[Dict[str, Any]]) -> Dict[str, Any]:
    primary_intent = "other"
    semantic_intent = ""
    semantic_confidence = None
    entities: Dict[str, Any] = {}
    risk_flags: List[str] = []

    for row in reversed(traces):
        if row.get("primary_intent"):
            primary_intent = str(row.get("primary_intent") or primary_intent)
            semantic_intent = str(row.get("semantic_intent") or semantic_intent)
            semantic_confidence = row.get("semantic_confidence")
            break

    for row in reversed(traces):
        if row.get("stage") == "intent_routing" and isinstance(row.get("slot_coverage"), dict):
            coverage = row["slot_coverage"]
            entities = {
                "required_slots": coverage.get("required_slots") or [],
                "missing_required_slots": coverage.get("missing_required_slots") or [],
                "has_minimum_required": bool(coverage.get("has_minimum_required")),
            }
            break

    for row in traces:
        if bool(row.get("frustration_loop")) and "frustration_loop" not in risk_flags:
            risk_flags.append("frustration_loop")
        if row.get("stage") == "policy_guard" and bool(row.get("handled")) and "policy_guard" not in risk_flags:
            risk_flags.append("policy_guard")

    return {
        "primary_intent": primary_intent,
        "semantic_intent": semantic_intent,
        "semantic_confidence": semantic_confidence,
        "entities": entities,
        "risk_flags": risk_flags,
    }


def build_chat_lab_snapshot(
    *,
    conversations_dir: Path,
    phone: str,
    correlation_id: str = "",
    trace_limit: int = 80,
    event_limit: int = 20,
) -> Dict[str, Any]:
    clean = _clean_phone(phone)
    conversation = load_conversation_messages(conversations_dir, clean)
    messages = conversation.get("messages") or []
    traces = read_decision_traces(phone=clean, correlation_id=correlation_id, limit=trace_limit)
    lab_events = read_chat_lab_events(phone=clean, correlation_id=correlation_id, limit=event_limit)
    backend_events = read_backend_log_events(phone=clean, correlation_id=correlation_id, limit=20)
    flow_state = _derive_active_flow_state(clean)
    intent_summary = _derive_intent_summary(traces)
    latest_event = lab_events[-1] if lab_events else {}
    handoff = str(latest_event.get("status") or "").strip().lower() == "handoff"
    risk_flags = intent_summary.get("risk_flags") or []

    debug_payload = {
        "language": infer_language_lock(messages),
        "intent": intent_summary.get("primary_intent") or "other",
        "semantic_intent": intent_summary.get("semantic_intent") or "",
        "semantic_confidence": intent_summary.get("semantic_confidence"),
        "conversation_state": flow_state.get("label") or "GREETING",
        "risk_flags": risk_flags,
        "escalation": {
            "level": "L1" if handoff else "L0",
            "role": "HUMAN" if handoff else "NONE",
        },
        "entities": intent_summary.get("entities") or {},
        "next_step": flow_state.get("next_step") or "await_user_intent",
        "routing": flow_state.get("flows", {}).get("routing", {}),
        "flow_states": flow_state.get("flows", {}),
    }

    return {
        "phone": clean,
        "correlation_id": correlation_id,
        "conversation": conversation,
        "debug": {
            **debug_payload,
            "full_internal_json": debug_payload,
        },
        "traces": traces,
        "lab_events": lab_events,
        "backend_events": backend_events,
    }
