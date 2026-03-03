from __future__ import annotations

import re
from typing import Dict, List

from app.content.intent_slot_contract import INTENT_SLOT_CONTRACT
from app.services.intent_policy_service import has_booking_reference


def get_slot_contract(intent_name: str) -> Dict:
    return INTENT_SLOT_CONTRACT.get(intent_name, INTENT_SLOT_CONTRACT["OUT_OF_SCOPE_OTHER"])


def _has_date(text: str) -> bool:
    low = (text or "").lower()
    if re.search(r"\b\d{1,2}[./-]\d{1,2}([./-]\d{2,4})?\b", low):
        return True
    return any(
        m in low
        for m in [
            "ocak", "şubat", "subat", "mart", "nisan", "mayıs", "mayis", "haziran",
            "temmuz", "ağustos", "agustos", "eylül", "eylul", "ekim", "kasım", "kasim",
            "aralık", "aralik", "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december",
            "январ", "феврал", "март", "апрел", "май", "июн", "июл", "август", "сентябр", "октябр", "ноябр", "декабр",
            "januar", "februar", "märz", "marz", "april", "mai", "juni", "juli", "august", "september", "oktober", "november", "dezember",
            "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "setiembre", "octubre", "noviembre", "diciembre",
            "janvier", "février", "fevrier", "mars", "avril", "mai", "juin", "juillet", "août", "aout", "septembre", "octobre", "novembre", "décembre", "decembre",
            "janeiro", "fevereiro", "março", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
            "يناير", "فبراير", "مارس", "ابريل", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "اغسطس", "سبتمبر", "أكتوبر", "اكتوبر", "نوفمبر", "ديسمبر",
            "जनवरी", "फ़रवरी", "फरवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर",
            "月",
            "yarın", "yarin", "today", "tomorrow", "bugün", "bugun",
            "сегодня", "завтра", "heute", "morgen", "hoy", "mañana", "manana", "aujourd", "demain",
            "hoje", "amanhã", "amanha", "اليوم", "غد", "आज", "कल", "今天", "明天",
        ]
    )


def _has_time(text: str) -> bool:
    low = (text or "").lower()
    return bool(re.search(r"\b\d{1,2}[:.]\d{2}\b", low) or re.search(r"\bsaat\s*\d{1,2}\b", low))


def _has_guest_count(text: str) -> bool:
    low = (text or "").lower()
    return bool(
        re.search(r"\b\d+\s*(kişi|kisi|people|person|adult|yetişkin|yetiskin)\b", low)
        or re.search(r"\b\d+\s*(adults|guests|pax)\b", low)
        or re.search(r"\b\d+\s*(взрос\w*|гост\w*|человек\w*)\b", low)
        or re.search(r"\b\d+\s*(erwachsen\w*|gäst\w*|gast\w*|personen?)\b", low)
        or re.search(r"\b\d+\s*(adultos?|hu[eé]spedes|personas?)\b", low)
        or re.search(r"\b\d+\s*(adultes?|voyageurs?|personnes?)\b", low)
        or re.search(r"\b\d+\s*(adultos?|h[oó]spedes|pessoas?)\b", low)
        or re.search(r"\b\d+\s*(بالغ\w*|أشخاص|اشخاص|ضيوف)\b", low)
        or re.search(r"\b\d+\s*(वयस्क\w*|मेहमान\w*)\b", low)
        or re.search(r"\b\d+\s*(位|人)\b", low)
        or any(k in low for k in ("شخصين", "شخصان", "بالغين", "بالغان", "两位成人", "两名成人", "两人"))
        or re.search(r"\b(1|2|3|4|5|6|7|8|9|10)\s*(pax)\b", low)
    )


def _has_name_like(text: str) -> bool:
    low = (text or "").lower()
    return any(k in low for k in ("adım", "adim", "name", "isim", "reservation name"))


def _has_flight_no(text: str) -> bool:
    return bool(re.search(r"\b[a-zA-Z]{2}\s*\d{3,4}\b", text or ""))


def evaluate_slot_coverage(intent_name: str, message: str) -> Dict:
    contract = get_slot_contract(intent_name)
    required = contract.get("required_slots", []) or []
    text = message or ""

    present = set()
    if _has_date(text):
        present.update({"check_in_date", "check_out_date", "reservation_date", "transfer_date"})
    if _has_time(text):
        present.update({"reservation_time", "transfer_time"})
    if _has_guest_count(text):
        present.update({"adult_count", "guest_count"})
    if has_booking_reference(text):
        present.update({"booking_ref", "booking_ref_or_match_key", "restaurant_booking_ref_or_match_key"})
    if _has_name_like(text):
        present.update({"reservation_name"})
    if _has_flight_no(text):
        present.update({"flight_no"})
    low = text.lower()
    if any(k in low for k in ("değiş", "degis", "güncelle", "guncelle", "revize", "update", "modify")):
        present.add("change_fields")
    if any(k in low for k in ("route", "rota", "dalaman", "antalya", "airport", "havaliman", "havaalani")):
        present.add("route")
    if intent_name == "LOCAL_FAQ_INFO":
        if any(
            k in low
            for k in (
                "wifi", "kahvalt", "check", "konum", "adres", "sezon", "havuz", "spa",
                "giriş", "giris", "çıkış", "cikis", "gece geç", "gece gec", "late check",
            )
        ):
            present.add("faq_topic")
    if intent_name == "COMPLAINT" and text.strip():
        present.add("complaint_text")
    if intent_name == "DISCOUNT_NEGOTIATION" and any(k in low for k in ("indirim", "discount", "pazarlık", "pazarlik")):
        present.add("target_product_or_booking_context")
    if intent_name == "SPECIAL_REQUEST_EVENT" and any(k in low for k in ("balayı", "balayi", "sürpriz", "surpriz", "birthday", "proposal", "yıldönümü", "yildonumu")):
        present.add("event_type")
    if intent_name == "URGENT_CASE" and any(k in low for k in ("acil", "urgent", "hemen", "flight delay", "rötar", "rotar")):
        present.add("urgent_reason")
    if intent_name == "RISK_ABUSE" and text.strip():
        present.add("risk_text")

    missing = [slot for slot in required if slot not in present]
    return {
        "intent_name": intent_name,
        "required_slots": required,
        "missing_required_slots": missing,
        "has_minimum_required": len(missing) == 0,
    }


def get_missing_slot_prompt(intent_name: str) -> str:
    return str(get_slot_contract(intent_name).get("clarify_prompt_tr", "") or "")


def should_request_slot_clarification(
    intent_name: str,
    slot_coverage: Dict,
    *,
    has_active_flow: bool,
) -> bool:
    """Return True when we should ask exactly one intent-specific clarify question."""
    if has_active_flow:
        # Existing stateful flows already ask step-by-step prompts.
        return False
    missing = slot_coverage.get("missing_required_slots", []) or []
    if not missing:
        return False
    return bool(get_missing_slot_prompt(intent_name))
