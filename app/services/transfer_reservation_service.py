from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.services.state_store_service import JsonStateRepository, resolve_data_file


TRANSFER_RESERVATIONS_FILE = resolve_data_file(
    "transfer_reservations.json",
    env_var="KASSANDRA_TRANSFER_RESERVATIONS_FILE",
)

_repo = JsonStateRepository(TRANSFER_RESERVATIONS_FILE)

_MONTH_ALIASES = {
    "ocak": 1, "january": 1, "январь": 1, "января": 1,
    "subat": 2, "şubat": 2, "february": 2, "февраль": 2, "февраля": 2,
    "mart": 3, "march": 3, "март": 3, "марта": 3,
    "nisan": 4, "april": 4, "апрель": 4, "апреля": 4,
    "mayis": 5, "mayıs": 5, "may": 5, "май": 5, "мая": 5,
    "haziran": 6, "june": 6, "июнь": 6, "июня": 6,
    "temmuz": 7, "july": 7, "июль": 7, "июля": 7,
    "agustos": 8, "ağustos": 8, "august": 8, "август": 8, "августа": 8,
    "eylul": 9, "eylül": 9, "september": 9, "сентябрь": 9, "сентября": 9,
    "ekim": 10, "october": 10, "октябрь": 10, "октября": 10,
    "kasim": 11, "kasım": 11, "november": 11, "ноябрь": 11, "ноября": 11,
    "aralik": 12, "aralık": 12, "december": 12, "декабрь": 12, "декабря": 12,
}


def _normalize_for_match(text: str) -> str:
    t = (text or "").strip().lower()
    return (
        t.replace("ı", "i")
        .replace("ö", "o")
        .replace("ü", "u")
        .replace("ş", "s")
        .replace("ç", "c")
        .replace("ğ", "g")
    )


def _extract_date_parts(text: str) -> tuple[Optional[int], Optional[int], Optional[int]]:
    raw = (text or "").strip()
    if not raw:
        return None, None, None
    t = _normalize_for_match(raw)

    iso = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", t)
    if iso:
        return int(iso.group(1)), int(iso.group(2)), int(iso.group(3))

    dmy = re.search(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\b", t)
    if dmy:
        year = int(dmy.group(3))
        if year < 100:
            year += 2000
        return year, int(dmy.group(2)), int(dmy.group(1))

    day_month_name = re.search(r"\b(\d{1,2})\s+([a-zа-яё]+)(?:\s+(\d{4}))?\b", t)
    if day_month_name:
        day = int(day_month_name.group(1))
        month_name = day_month_name.group(2)
        month = _MONTH_ALIASES.get(month_name)
        year = int(day_month_name.group(3)) if day_month_name.group(3) else None
        if month:
            return year, month, day

    day_month_num = re.search(r"\b(\d{1,2})[./-](\d{1,2})\b", t)
    if day_month_num:
        return None, int(day_month_num.group(2)), int(day_month_num.group(1))

    return None, None, None


def _date_matches(query: str, value: str) -> bool:
    qy, qm, qd = _extract_date_parts(query)
    vy, vm, vd = _extract_date_parts(value)
    if qm and qd and vm and vd:
        if qm != vm or qd != vd:
            return False
        if qy and vy:
            return qy == vy
        return True
    return _normalize_for_match(query) in _normalize_for_match(value)


def _load_store() -> Dict[str, Any]:
    data = _repo.load_dict()
    if not data:
        return {"last_id": 0, "items": []}
    data.setdefault("last_id", 0)
    data.setdefault("items", [])
    if not isinstance(data["items"], list):
        data["items"] = []
    return data


def _save_store(data: Dict[str, Any]) -> None:
    _repo.save_dict(data)


def normalize_transfer_status(status: Optional[str]) -> str:
    raw = (status or "").strip().lower()
    raw = raw.replace("ı", "i")
    aliases = {
        "all": "all",
        "*": "all",
        "tumu": "all",
        "tum": "all",
        "pending": "pending",
        "bekleyen": "pending",
        "confirmed": "confirmed",
        "onayli": "confirmed",
        "cancelled": "cancelled",
        "iptal": "cancelled",
        "updated": "updated",
        "guncellenmis": "updated",
    }
    return aliases.get(raw, "all" if raw else "pending")


def list_transfer_reservations(
    status: Optional[str] = None,
    date_query: Optional[str] = None,
) -> List[Dict[str, Any]]:
    items = _load_store().get("items", [])
    norm_status = normalize_transfer_status(status)
    if norm_status != "all":
        items = [item for item in items if (item.get("status", "").lower() == norm_status)]

    date_q = (date_query or "").strip().lower()
    if date_q:
        items = [
            item for item in items
            if _date_matches(date_q, item.get("transfer_date", ""))
        ]
    return sorted(items, key=lambda x: x.get("created_at", ""), reverse=True)


def get_transfer_reservation(reservation_id: int) -> Optional[Dict[str, Any]]:
    for item in _load_store().get("items", []):
        if int(item.get("id", 0)) == int(reservation_id):
            return item
    return None


def _dedupe_key(phone: str, details: Dict[str, Any]) -> str:
    payload = "|".join(
        [
            re.sub(r"[^\d]", "", phone or ""),
            (details.get("transfer_date") or "").strip(),
            (details.get("transfer_time") or "").strip(),
            (details.get("flight_no") or "").strip().upper(),
            (details.get("guest_text") or "").strip().lower(),
            (details.get("luggage_text") or "").strip().lower(),
            (details.get("baby_seat") or "").strip().lower(),
        ]
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def create_transfer_reservation(
    *,
    customer_phone: str,
    details: Dict[str, Any],
    source: str = "chat_confirmation",
) -> Dict[str, Any]:
    now = datetime.now()
    store = _load_store()
    items = store["items"]
    key = _dedupe_key(customer_phone, details)

    for item in items:
        if item.get("dedupe_key") != key:
            continue
        created_at = item.get("created_at")
        if not created_at:
            return item
        try:
            created_dt = datetime.fromisoformat(created_at)
        except Exception:
            return item
        if now - created_dt <= timedelta(hours=48):
            return item

    new_id = int(store.get("last_id", 0)) + 1
    reservation = {
        "id": new_id,
        "type": "transfer",
        "status": "pending",
        "customer_phone": re.sub(r"[^\d]", "", customer_phone or ""),
        "customer_name": details.get("customer_name", ""),
        "transfer_route": details.get("transfer_route", "Dalaman Havalimani -> Kassandra Oludeniz"),
        "transfer_date": details.get("transfer_date", ""),
        "transfer_time": details.get("transfer_time", ""),
        "flight_no": details.get("flight_no", ""),
        "guest_text": details.get("guest_text", ""),
        "luggage_text": details.get("luggage_text", ""),
        "baby_seat": details.get("baby_seat", ""),
        "price_text": details.get("price_text", "75 EUR"),
        "raw_summary": details.get("raw_summary", ""),
        "source": source,
        "dedupe_key": key,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    items.append(reservation)
    store["last_id"] = new_id
    _save_store(store)
    return reservation


def update_transfer_reservation_status(
    reservation_id: int,
    *,
    status: str,
    admin_note: str = "",
) -> Optional[Dict[str, Any]]:
    store = _load_store()
    now_iso = datetime.now().isoformat()
    for item in store["items"]:
        if int(item.get("id", 0)) != int(reservation_id):
            continue
        item["status"] = (status or "").strip().lower() or item.get("status", "pending")
        item["updated_at"] = now_iso
        if admin_note:
            item["admin_note"] = admin_note
        _save_store(store)
        return item
    return None


def update_transfer_reservation_details(
    reservation_id: int,
    changes: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    allowed_fields = {
        "customer_name",
        "transfer_route",
        "transfer_date",
        "transfer_time",
        "flight_no",
        "guest_text",
        "luggage_text",
        "baby_seat",
        "price_text",
        "admin_note",
    }
    store = _load_store()
    now_iso = datetime.now().isoformat()
    for item in store["items"]:
        if int(item.get("id", 0)) != int(reservation_id):
            continue
        changed = False
        for key, value in (changes or {}).items():
            if key not in allowed_fields:
                continue
            if value is None:
                continue
            text = str(value).strip()
            if item.get(key, "") == text:
                continue
            item[key] = text
            changed = True
        if changed:
            item["status"] = "updated"
            item["updated_at"] = now_iso
            _save_store(store)
        return item
    return None


def _is_affirmative(text: str) -> bool:
    t = (text or "").strip().lower()
    yes_words = {
        "evet", "evt", "olur", "tamam", "onay", "onayliyorum", "onaylıyorum",
        "dogru", "doğru", "yes", "ok", "okay", "confirm", "confirmed",
        "да", "верно", "подтверждаю",
    }
    return t in yes_words


def _is_transfer_confirmation_reply(text: str) -> bool:
    low = (text or "").lower()
    markers = [
        "transfer talebinizi ald",
        "ekibimize ilett",
        "soforumuz havalimaninda",
        "şoförümüz havalimanında",
        "transfer request received",
        "we have forwarded your transfer",
    ]
    normalized = low.replace("ı", "i")
    return any(m in normalized for m in markers)


def _parse_transfer_summary(summary: str) -> Dict[str, str]:
    txt = summary or ""
    normalized = txt.replace("ı", "i")

    route_match = re.search(r"📍\s*(.+)", txt)
    name_match = re.search(r"👤\s*(?:İsim|Ad Soyad|Name)\s*:\s*(.+)", txt, flags=re.IGNORECASE)
    dt_match = re.search(
        r"📅\s*([0-9]{1,2}\s+[A-Za-zÇĞİÖŞÜçğıöşü]+)\s*(?:saat)?\s*([0-9]{1,2}[:.][0-9]{2})",
        txt,
        flags=re.IGNORECASE,
    )
    flight_match = re.search(r"✈️\s*(?:Uçuş|Flight)\s*:\s*([A-Za-z0-9]+)", txt, flags=re.IGNORECASE)
    guest_match = re.search(r"👥\s*(.+)", txt)
    luggage_match = re.search(r"🧳\s*(.+)", txt)
    baby_match = re.search(r"👶\s*(?:Bebek koltuğu|Baby seat)\s*:\s*(.+)", txt, flags=re.IGNORECASE)
    price_match = re.search(r"💰\s*(?:Ücret|Price)\s*:\s*(.+)", txt, flags=re.IGNORECASE)

    transfer_date = (dt_match.group(1) if dt_match else "").strip()
    transfer_time = (dt_match.group(2) if dt_match else "").strip().replace(".", ":")
    if not transfer_date and "haziran" in normalized:
        transfer_date = "Haziran"

    return {
        "transfer_route": (route_match.group(1) if route_match else "").strip(),
        "customer_name": (name_match.group(1) if name_match else "").strip(),
        "transfer_date": transfer_date,
        "transfer_time": transfer_time,
        "flight_no": (flight_match.group(1) if flight_match else "").strip().upper(),
        "guest_text": (guest_match.group(1) if guest_match else "").strip(),
        "luggage_text": (luggage_match.group(1) if luggage_match else "").strip(),
        "baby_seat": (baby_match.group(1) if baby_match else "").strip(),
        "price_text": (price_match.group(1) if price_match else "").strip(),
        "raw_summary": txt.strip(),
    }


def maybe_create_transfer_reservation_from_chat(
    *,
    phone: str,
    user_message: str,
    bot_reply: str,
    conversation_messages: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not _is_affirmative(user_message):
        return None
    if not _is_transfer_confirmation_reply(bot_reply):
        return None

    summary_text = ""
    for msg in reversed(conversation_messages[-6:]):
        candidate = (msg.get("bot_reply") or "")
        if "transfer özeti" in candidate.lower() or "transfer summary" in candidate.lower():
            summary_text = candidate
            break
    if not summary_text:
        return None

    details = _parse_transfer_summary(summary_text)
    if not details.get("transfer_date") and not details.get("transfer_time"):
        return None
    return create_transfer_reservation(customer_phone=phone, details=details, source="chat_confirmation")
