from __future__ import annotations

import re
from typing import Any, Callable, Dict, Optional


CHANGE_MARKERS = (
    "pardon",
    "duzelt",
    "düzelt",
    "degistir",
    "değiştir",
    "degis",
    "değiş",
    "guncelle",
    "güncelle",
    "yanlis",
    "yanlış",
    "aslinda",
    "aslında",
    "sorry",
    "actually",
    "change",
    "update",
)

SLOT_HINT_MARKERS = (
    "tarih",
    "date",
    "saat",
    "time",
    "kisi",
    "kişi",
    "guest",
    "route",
    "rota",
    "ucus",
    "uçuş",
    "flight",
    "check-in",
    "check out",
)


def is_change_request(text: str) -> bool:
    low = (text or "").lower().strip()
    if not low:
        return False
    if any(marker in low for marker in CHANGE_MARKERS):
        return True
    if any(marker in low for marker in SLOT_HINT_MARKERS) and bool(re.search(r"\d", low)):
        return True
    return False


def extract_slot_updates(
    text: str,
    *,
    date_parser: Optional[Callable[[str], Optional[str]]] = None,
    time_parser: Optional[Callable[[str], Optional[str]]] = None,
    guest_count_parser: Optional[Callable[[str], Optional[int]]] = None,
    flight_no_parser: Optional[Callable[[str], Optional[str]]] = None,
    route_parser: Optional[Callable[[str], Optional[str]]] = None,
) -> Dict[str, Any]:
    updates: Dict[str, Any] = {}
    msg = text or ""

    if date_parser:
        date_val = date_parser(msg)
        if date_val:
            updates["date"] = date_val

    if time_parser:
        time_val = time_parser(msg)
        if time_val:
            updates["time"] = time_val

    if guest_count_parser:
        guest_count = guest_count_parser(msg)
        if guest_count:
            updates["guest_count"] = int(guest_count)

    if flight_no_parser:
        flight_no = flight_no_parser(msg)
        if flight_no:
            updates["flight_no"] = flight_no

    if route_parser:
        route = route_parser(msg)
        if route:
            updates["route"] = route

    return updates
