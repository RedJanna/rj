"""app/services/elektraweb_booking_service.py

ElektraWeb BookingAPI entegrasyonu (otel fiyat cekimi).
- APIKEY: env Elektra_Booking (orn: booking#....)
- Hotel ID: param olarak gelir (kassandra_openai_bot.py icinden)
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple, Union

import httpx
from app.core.settings_service import get_quiet_room_policy


# =========================
# Exceptions
# =========================

class ElektrawebConfigError(RuntimeError):
    pass


class ElektrawebAuthError(RuntimeError):
    pass


# =========================
# Config
# =========================

ELEKTRA_API_BASE_URL = (os.getenv("ELEKTRA_API_BASE_URL") or "https://bookingapi.elektraweb.com").rstrip("/")
DEFAULT_CURRENCY = (os.getenv("ELEKTRA_DEFAULT_CURRENCY") or "EUR").strip().upper()
DEFAULT_NATIONALITY = (os.getenv("ELEKTRA_DEFAULT_NATIONALITY") or "TR").strip().upper()
USER_AGENT = os.getenv("ELEKTRA_USER_AGENT") or "KassandraBot/1.0"

ELEKTRA_ENDPOINT_DEFAULTS: Dict[str, List[str]] = {
    "create_reservation": [
        "/hotel/{hotel_id}/createReservation",
        "/hotel/{hotel_id}/reservation/create",
        "/hotel/{hotel_id}/reservations/create",
    ],
    "get_reservation": [
        "/hotel/{hotel_id}/reservation",
        "/hotel/{hotel_id}/getReservation",
        "/hotel/{hotel_id}/reservation/detail",
        "/hotel/{hotel_id}/reservation/get",
        "/hotel/{hotel_id}/reservations/get",
    ],
    "list_reservations": [
        "/hotel/{hotel_id}/reservationList",
        "/hotel/{hotel_id}/reservations",
        "/hotel/{hotel_id}/reservation/list",
    ],
    "update_reservation": [
        "/hotel/{hotel_id}/updateReservation",
        "/hotel/{hotel_id}/reservation/update",
    ],
    "cancel_reservation": [
        "/hotel/{hotel_id}/cancelReservation",
        "/hotel/{hotel_id}/reservation/cancel",
    ],
}

ELEKTRA_ENDPOINT_ENV_MAP: Dict[str, str] = {
    "create_reservation": "ELEKTRA_CREATE_RESERVATION_PATHS",
    "get_reservation": "ELEKTRA_GET_RESERVATION_PATHS",
    "list_reservations": "ELEKTRA_LIST_RESERVATIONS_PATHS",
    "update_reservation": "ELEKTRA_UPDATE_RESERVATION_PATHS",
    "cancel_reservation": "ELEKTRA_CANCEL_RESERVATION_PATHS",
}


# =========================
# Ay Isimleri (TR/EN)
# =========================

MONTHS_TR = {
    "ocak": 1, "subat": 2, "mart": 3, "nisan": 4,
    "mayis": 5, "haziran": 6, "temmuz": 7,
    "agustos": 8, "eylul": 9,
    "ekim": 10, "kasim": 11, "aralik": 12
}

MONTHS_EN = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
}

MONTHS_RU = {
    # Nominative
    "январь": 1, "февраль": 2, "март": 3, "апрель": 4,
    "май": 5, "июнь": 6, "июль": 7, "август": 8,
    "сентябрь": 9, "октябрь": 10, "ноябрь": 11, "декабрь": 12,
    # Genitive (common in date expressions: 10 августа)
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
    "мая": 5, "июня": 6, "июля": 7, "августа": 8,
    "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}

MONTHS_DE = {
    "januar": 1, "februar": 2, "marz": 3, "märz": 3, "april": 4,
    "mai": 5, "juni": 6, "juli": 7, "august": 8,
    "september": 9, "oktober": 10, "november": 11, "dezember": 12,
}

MONTHS_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}

MONTHS_FR = {
    "janvier": 1, "fevrier": 2, "février": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "aout": 8, "août": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12, "décembre": 12,
}

MONTHS_PT = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "março": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
    "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}

MONTHS_AR = {
    "يناير": 1, "فبراير": 2, "مارس": 3,
    "أبريل": 4, "ابريل": 4,
    "مايو": 5, "يونيو": 6, "يوليو": 7,
    "أغسطس": 8, "اغسطس": 8,
    "سبتمبر": 9,
    "أكتوبر": 10, "اكتوبر": 10,
    "نوفمبر": 11, "ديسمبر": 12,
}

MONTHS_HI = {
    "जनवरी": 1, "फ़रवरी": 2, "फरवरी": 2, "मार्च": 3, "अप्रैल": 4,
    "मई": 5, "जून": 6, "जुलाई": 7, "अगस्त": 8,
    "सितंबर": 9, "अक्टूबर": 10, "नवंबर": 11, "दिसंबर": 12,
}

MONTHS_TR_REVERSE = {
    1: 'Ocak', 2: 'Subat', 3: 'Mart', 4: 'Nisan',
    5: 'Mayis', 6: 'Haziran', 7: 'Temmuz', 8: 'Agustos',
    9: 'Eylul', 10: 'Ekim', 11: 'Kasim', 12: 'Aralik'
}

MONTHS_EN_REVERSE = {
    1: 'January', 2: 'February', 3: 'March', 4: 'April',
    5: 'May', 6: 'June', 7: 'July', 8: 'August',
    9: 'September', 10: 'October', 11: 'November', 12: 'December'
}


# =========================
# Oda Isim Mapping (API -> Sablon)
# =========================

ROOM_TYPE_MAP = {
    "DELUXE": {
        "tr": "Deluxe (25m2)",
        "en": "Deluxe (25m2)",
        "ru": "Делюкс (25 м²)",
        "key": "deluxe",
    },
    "SUPERIOR": {
        "tr": "Superior (30m2)",
        "en": "Superior (30 m2)",
        "ru": "Супериор (30 м²)",
        "key": "superior",
    },
    "EXCLUSIVE LAND": {
        "tr": "Exclusive Sokak Manzarali (40m2)",
        "en": "Exclusive Street View (40 m2)",
        "ru": "Эксклюзив с видом на улицу (40 м²)",
        "key": "exclusiveLand",
    },
    "EXCLUSIVE LAND VIEW": {
        "tr": "Exclusive Sokak Manzarali (40m2)",
        "en": "Exclusive Street View (40 m2)",
        "ru": "Эксклюзив с видом на улицу (40 м²)",
        "key": "exclusiveLand",
    },
    "EXCLUSIVE STREET": {
        "tr": "Exclusive Sokak Manzarali (40m2)",
        "en": "Exclusive Street View (40 m2)",
        "ru": "Эксклюзив с видом на улицу (40 м²)",
        "key": "exclusiveLand",
    },
    "EXCLUSIVE POOL": {
        "tr": "Exclusive Havuz Manzarali (40m2)",
        "en": "Exclusive Pool View (40m2)",
        "ru": "Эксклюзив с видом на бассейн (40 м²)",
        "key": "exclusivePool",
    },
    "EXCLUSIVE POOL VIEW": {
        "tr": "Exclusive Havuz Manzarali (40m2)",
        "en": "Exclusive Pool View (40m2)",
        "ru": "Эксклюзив с видом на бассейн (40 м²)",
        "key": "exclusivePool",
    },
    # Daha spesifik oda adlarini genel "PENTHOUSE"tan once koy.
    "PENTHOUSE LAND JAKUZILI": {
        "tr": "Penthouse Land - Jakuzili (25m2)",
        "en": "Penthouse Land with Jacuzzi (25m2)",
        "ru": "Пентхаус с джакузи (вид на сушу, 25 м²)",
        "key": "penthouseLand",
    },
    "PENTHOUSE LAND JACUZZI": {
        "tr": "Penthouse Land - Jakuzili (25m2)",
        "en": "Penthouse Land with Jacuzzi (25m2)",
        "ru": "Пентхаус с джакузи (вид на сушу, 25 м²)",
        "key": "penthouseLand",
    },
    "PENTHOUSE LAND": {
        "tr": "Penthouse Land - Jakuzili (25m2)",
        "en": "Penthouse Land with Jacuzzi (25m2)",
        "ru": "Пентхаус с джакузи (вид на сушу, 25 м²)",
        "key": "penthouseLand",
    },
    "PENTHOUSE": {
        "tr": "Penthouse - Jakuzili (45m2)",
        "en": "Penthouse with Jacuzzi (45m2)",
        "ru": "Пентхаус с джакузи (45 м²)",
        "key": "penthouse",
    },
    "PREMIUM": {
        "tr": "Premium - Jakuzili (45m2)",
        "en": "Premium (45m2)",
        "ru": "Премиум с джакузи (45 м²)",
        "key": "premium",
    },
}

MONTHS_RU_REVERSE = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
}

ROOM_ORDER = ["deluxe", "superior", "exclusiveLand", "exclusivePool", "penthouseLand", "penthouse", "premium"]


# =========================
# Helpers
# =========================

def _normalize_token(raw: str) -> str:
    return (raw or "").strip().strip('"').strip("'").strip()


def _safe_snippet(text: str, limit: int = 800) -> str:
    t = (text or "").replace("\r", "").replace("\n", " ")
    return t[:limit]


def _build_elektra_url(path: str) -> str:
    cleaned = (path or "").strip()
    if cleaned.startswith("http://") or cleaned.startswith("https://"):
        return cleaned
    if not cleaned.startswith("/"):
        cleaned = f"/{cleaned}"
    return f"{ELEKTRA_API_BASE_URL}{cleaned}"


def _resolve_endpoint_candidates(operation: str, hotel_id: Union[int, str]) -> List[str]:
    env_key = ELEKTRA_ENDPOINT_ENV_MAP.get(operation, "")
    env_raw = os.getenv(env_key, "") if env_key else ""
    configured: List[str] = []
    if env_raw.strip():
        configured = [x.strip() for x in env_raw.split(",") if x.strip()]
    else:
        configured = list(ELEKTRA_ENDPOINT_DEFAULTS.get(operation, []))

    resolved: List[str] = []
    seen: set[str] = set()
    for tpl in configured:
        try:
            path = tpl.format(hotel_id=hotel_id)
        except Exception:
            path = tpl.replace("{hotel_id}", str(hotel_id))
        if path not in seen:
            seen.add(path)
            resolved.append(path)
    return resolved


def _elektra_auth_headers(jwt: str, *, include_json: bool = False) -> Dict[str, str]:
    headers = {
        "Authorization": f"Bearer {jwt}",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    if include_json:
        headers["Content-Type"] = "application/json"
    captcha = _normalize_token(os.getenv("ELEKTRA_X_CAPTCHA", ""))
    if captcha:
        headers["x-captcha"] = captcha
    return headers


async def _request_json_with_fallback(
    *,
    method: str,
    operation: str,
    endpoint_candidates: List[str],
    headers: Dict[str, str],
    timeout_sec: int,
    params: Optional[Dict[str, Any]] = None,
    json_payload: Optional[Dict[str, Any]] = None,
    retry_on_statuses: Optional[set[int]] = None,
    continue_on_error_substrings: Optional[set[str]] = None,
) -> Dict[str, Any]:
    if not endpoint_candidates:
        raise ElektrawebConfigError(f"Endpoint listesi bos: operation={operation}")

    retry_status = retry_on_statuses or {404, 405}
    continue_on_substrings = {s.lower() for s in (continue_on_error_substrings or set()) if s}
    attempts: List[str] = []
    method_u = (method or "GET").upper()

    async with httpx.AsyncClient(timeout=timeout_sec, follow_redirects=True) as client:
        for endpoint in endpoint_candidates:
            url = _build_elektra_url(endpoint)
            try:
                resp = await client.request(
                    method_u,
                    url,
                    headers=headers,
                    params=params,
                    json=json_payload,
                )
            except Exception as exc:
                attempts.append(f"{url} -> transport_error:{exc.__class__.__name__}")
                continue

            body = _safe_snippet(resp.text, 800)
            if resp.status_code >= 400:
                attempts.append(f"{url} -> HTTP {resp.status_code}")
                body_low = body.lower()
                if continue_on_substrings and any(s in body_low for s in continue_on_substrings):
                    continue
                if resp.status_code in retry_status:
                    continue
                raise ElektrawebAuthError(
                    f"{operation} failed: endpoint={url} HTTP {resp.status_code} | body={body}"
                )

            try:
                data = resp.json()
            except Exception:
                attempts.append(f"{url} -> bad_json")
                raise ElektrawebAuthError(
                    f"{operation} bad json: endpoint={url} | body={body}"
                )

            if isinstance(data, dict) and data.get("success") is False:
                snippet = json.dumps(data, ensure_ascii=False)[:800]
                snippet_low = snippet.lower()
                if continue_on_substrings and any(s in snippet_low for s in continue_on_substrings):
                    attempts.append(f"{url} -> success:false(continued)")
                    continue
                raise ElektrawebAuthError(
                    f"{operation} returned success:false: endpoint={url} | response={snippet}"
                )
            return data

    raise ElektrawebAuthError(
        f"{operation} failed for all endpoint candidates: {' | '.join(attempts)[:2000]}"
    )


def _api_language(lang: str) -> str:
    l = (lang or "").strip().lower()
    if l.startswith("tr"):
        return "TR"
    return "en"


def _normalize_price_value(value: float) -> float:
    """Fiyatlari Elektra'dan geldigi sekliyle koru; yapay yuvarlama yapma."""
    return float(value)


def _format_price(value: Optional[float]) -> str:
    if value is None:
        return "-"
    if abs(value - int(value)) < 1e-9:
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _extract_required_quote_amount(error_text: str) -> Optional[float]:
    """
    Elektra createReservation hatasindan beklenen dogru quote tutarini cikarir.
    Ornek: "You price quote 2016 EUR is wrong, it must be 1575 EUR"
    """
    txt = (error_text or "").strip()
    if not txt:
        return None

    patterns = [
        r"must be\s+([0-9]+(?:[.,][0-9]+)?)",
        r"it must be\s+([0-9]+(?:[.,][0-9]+)?)",
        r"olmal[ıi]\s*:?\s*([0-9]+(?:[.,][0-9]+)?)",
    ]
    for p in patterns:
        m = re.search(p, txt, flags=re.IGNORECASE)
        if not m:
            continue
        raw = (m.group(1) or "").replace(",", ".")
        try:
            return float(raw)
        except Exception:
            continue
    return None


def _extract_price_data_pax_counts(error_text: str) -> Optional[Dict[str, int]]:
    """
    Elektra createReservation hatasindan price data'daki pax dagilimini cikarir.
    Ornek:
    "adult-count and children counts ... as found adult: 2, and elder-child-count: 0younger-child-count: 0baby-count: 0"
    """
    txt = (error_text or "").strip()
    if not txt:
        return None
    def _pick(patterns: List[str]) -> Optional[int]:
        for p in patterns:
            m = re.search(p, txt, flags=re.IGNORECASE)
            if m:
                try:
                    return int(m.group(1))
                except Exception:
                    continue
        return None

    try:
        adult_v = _pick(
            [
                r"adult-count:\s*(\d+)",
                r"adult:\s*(\d+)",
            ]
        )
        elder_v = _pick([r"elder-child-count:\s*(\d+)"])
        younger_v = _pick([r"younger-child-count:\s*(\d+)"])
        baby_v = _pick([r"baby-count:\s*(\d+)"])
        if None in (adult_v, elder_v, younger_v, baby_v):
            return None
        return {
            "adult": int(adult_v),
            "elder-child-count": int(elder_v),
            "younger-child-count": int(younger_v),
            "baby-count": int(baby_v),
        }
    except Exception:
        return None


def _normalize_phone_e164(raw_phone: str, default_country_code: str = "+90") -> str:
    raw = str(raw_phone or "").strip()
    if not raw:
        return ""
    txt = raw.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if txt.startswith("00"):
        txt = "+" + txt[2:]
    if txt.startswith("+"):
        digits = re.sub(r"\D", "", txt)
        candidate = f"+{digits}"
        if re.fullmatch(r"\+[1-9]\d{9,14}", candidate):
            return candidate
        return ""

    digits = re.sub(r"\D", "", txt)
    if not digits:
        return ""

    if digits.startswith("90") and len(digits) == 12:
        candidate = "+" + digits
        if re.fullmatch(r"\+[1-9]\d{9,14}", candidate):
            return candidate
    if digits.startswith("0") and len(digits) == 11:
        candidate = f"{default_country_code}{digits[1:]}"
        if re.fullmatch(r"\+[1-9]\d{9,14}", candidate):
            return candidate
    if len(digits) == 10:
        candidate = f"{default_country_code}{digits}"
        if re.fullmatch(r"\+[1-9]\d{9,14}", candidate):
            return candidate
    if 10 <= len(digits) <= 15 and not digits.startswith("0"):
        candidate = "+" + digits
        if re.fullmatch(r"\+[1-9]\d{9,14}", candidate):
            return candidate
    return ""


def _is_no_rooms_available_error(error_text: str) -> bool:
    txt = (error_text or "").lower()
    return (
        "offer has no rooms available to be sold" in txt
        or "no rooms available to be sold" in txt
    )


def _child_pax_buckets(child_ages: List[int]) -> Dict[str, int]:
    """
    Child age bucket mapping:
    - elder-child-count: 6-16 (provider UI'da 11-6 olarak gorunen alan)
    - younger-child-count: 1-5
    - baby-count: 0
    """
    ages = [int(a) for a in (child_ages or []) if 0 <= int(a) <= 16]
    return {
        "elder-child-count": len([a for a in ages if 6 <= a <= 16]),
        "younger-child-count": len([a for a in ages if 1 <= a <= 5]),
        "baby-count": len([a for a in ages if a == 0]),
    }


def _clear_child_age_payload_fields(payload: Dict[str, Any]) -> None:
    """Payload icindeki child age alanlarini temizler; count alanlarini korur."""
    if not isinstance(payload, dict):
        return

    for key in (
        "childage",
        "child-age",
        "child-ages",
        "child-age-list",
        "child-age-arr",
        "children-ages",
    ):
        payload.pop(key, None)

    for key in list(payload.keys()):
        k = str(key).strip().lower()
        if re.fullmatch(r"child-\d+-age", k) or re.fullmatch(r"child-age-\d+", k):
            payload.pop(key, None)


def _normalize_room_type(api_room_type: str) -> Optional[Dict[str, str]]:
    """API'den gelen oda ismini sablon formatina cevir"""
    if not api_room_type:
        return None
    upper = api_room_type.strip().upper()
    if upper in ROOM_TYPE_MAP:
        return ROOM_TYPE_MAP[upper]
    for key, val in ROOM_TYPE_MAP.items():
        if key in upper or upper in key:
            return val
    return None


def _format_date_range_tr(from_date: str, to_date: str) -> str:
    """Tarih araligini Turkce formatla"""
    try:
        d1 = datetime.strptime(from_date, "%Y-%m-%d")
        d2 = datetime.strptime(to_date, "%Y-%m-%d")
        return f"{d1.day} {MONTHS_TR_REVERSE[d1.month]} - {d2.day} {MONTHS_TR_REVERSE[d2.month]} {d2.year}"
    except:
        return f"{from_date} - {to_date}"


def _format_date_range_en(from_date: str, to_date: str) -> str:
    """Tarih araligini Ingilizce formatla"""
    try:
        d1 = datetime.strptime(from_date, "%Y-%m-%d")
        d2 = datetime.strptime(to_date, "%Y-%m-%d")
        return f"{MONTHS_EN_REVERSE[d1.month]} {d1.day} - {MONTHS_EN_REVERSE[d2.month]} {d2.day}, {d2.year}"
    except:
        return f"{from_date} - {to_date}"

def _format_date_range_ru(from_date: str, to_date: str) -> str:
    """Tarih araligini Rusca formatla"""
    try:
        d1 = datetime.strptime(from_date, "%Y-%m-%d")
        d2 = datetime.strptime(to_date, "%Y-%m-%d")
        return f"{d1.day} {MONTHS_RU_REVERSE[d1.month]} - {d2.day} {MONTHS_RU_REVERSE[d2.month]} {d2.year}"
    except:
        return f"{from_date} - {to_date}"


def _calculate_nights(from_date: str, to_date: str) -> int:
    """Gece sayisini hesapla"""
    try:
        d1 = datetime.strptime(from_date, "%Y-%m-%d")
        d2 = datetime.strptime(to_date, "%Y-%m-%d")
        return (d2 - d1).days
    except:
        return 1


def _normalize_turkish_chars(text: str) -> str:
    """Turkce karakterleri normalize et"""
    if not text:
        return ""
    # Bazi kanallarda UTF-8 metin mojibake olarak gelebiliyor
    # (örn: "AÄŸustos", "â€“"). Tarih parse kaçırmamak için önce onar.
    mojibake_replacements = {
        "Ã§": "ç",
        "Ã‡": "Ç",
        "ã§": "ç",
        "ÄŸ": "ğ",
        "Äž": "Ğ",
        "äÿ": "ğ",
        "Ä±": "ı",
        "Ä°": "İ",
        "ä±": "ı",
        "Ã¶": "ö",
        "Ã–": "Ö",
        "ã¶": "ö",
        "Ã¼": "ü",
        "Ãœ": "Ü",
        "ã¼": "ü",
        "ÅŸ": "ş",
        "Åž": "Ş",
        "åÿ": "ş",
        "â€“": "-",
        "â€”": "-",
        "â€‘": "-",
        "â€™": "'",
        "â€˜": "'",
        "â€œ": '"',
        "â€": '"',
        "Â": "",
    }
    replacements = {
        'ş': 's', 'Ş': 'S',
        'ğ': 'g', 'Ğ': 'G',
        'ü': 'u', 'Ü': 'U',
        'ö': 'o', 'Ö': 'O',
        'ı': 'i', 'İ': 'I',
        'ç': 'c', 'Ç': 'C'
    }
    result = text
    # "EKİM" lower() sonrasi "eki̇m" (i + combining dot) olabilir.
    # Bu form regex eslesmesini bozdugu icin yalnizca bu isareti temizle.
    result = result.replace("i\u0307", "i").replace("I\u0307", "I")
    for bad, good in mojibake_replacements.items():
        result = result.replace(bad, good)
    # Arabic/Persian digits -> ASCII digits
    result = result.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    result = result.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
    # Tarih araligi separator'larini normalize et (23–26 gibi)
    result = re.sub(r"[–—−]", "-", result)
    for tr_char, en_char in replacements.items():
        result = result.replace(tr_char, en_char)
    return result


# =========================
# Dogal Dil Tarih Parse
# =========================

def _get_all_months() -> Dict[str, int]:
    """Tum ay isimlerini birlestir (TR + EN + RU + DE + ES + FR + PT + AR + HI + normalize edilmis)"""
    all_months = {}
    all_months.update(MONTHS_TR)
    all_months.update(MONTHS_EN)
    all_months.update(MONTHS_RU)
    all_months.update(MONTHS_DE)
    all_months.update(MONTHS_ES)
    all_months.update(MONTHS_FR)
    all_months.update(MONTHS_PT)
    all_months.update(MONTHS_AR)
    all_months.update(MONTHS_HI)
    # Turkce karakterli versiyonlari da ekle
    all_months["şubat"] = 2
    all_months["mayıs"] = 5
    all_months["ağustos"] = 8
    all_months["eylül"] = 9
    all_months["kasım"] = 11
    all_months["aralık"] = 12
    return all_months


def _extract_date_range_natural(text: str) -> List[str]:
    """
    Dogal dildeki tarih araligini cikar.
    Desteklenen formatlar:
    - "4 haziran ile 9 haziran"
    - "4-9 haziran"
    - "4 ile 9 haziran arasi"
    - "4 haziran giris, 9 haziran cikis"
    - "June 4 to June 9"
    - "4 haziran - 9 haziran tarihleri"
    """
    if not text:
        return []
    
    # Turkce karakterleri normalize et
    text_normalized = _normalize_turkish_chars(text.lower())
    text_lower = text.lower()
    
    today = datetime.now()
    year = today.year
    
    all_months = _get_all_months()
    range_connectors = "ile|to|ve|and|arasi|arasında|between|tarihleri|al|a|au|bis|hasta|ate|até|à|الى|إلى|من|حتى|से|तक"
    
    # Pattern 1: "4 haziran giris, 9 haziran cikis" veya "4 haziran giris 9 haziran cikis"
    for month_name, month_num in all_months.items():
        month_normalized = _normalize_turkish_chars(month_name)
        # Giris/cikis formati
        pattern = rf'(\d{{1,2}})\s*{month_normalized}\s*(?:giris|giriş|check.?in)[\s,]*(\d{{1,2}})\s*(\w+)\s*(?:cikis|çıkış|check.?out)'
        match = re.search(pattern, text_normalized)
        if match:
            day1 = int(match.group(1))
            day2 = int(match.group(2))
            month2_name = match.group(3)
            month2_num = all_months.get(_normalize_turkish_chars(month2_name), month_num)
            
            if 1 <= day1 <= 31 and 1 <= day2 <= 31:
                try:
                    date1 = datetime(year, month_num, day1)
                    date2 = datetime(year, month2_num, day2)
                    if date1 < today:
                        date1 = datetime(year + 1, month_num, day1)
                        date2 = datetime(year + 1, month2_num, day2)
                    return [date1.strftime("%Y-%m-%d"), date2.strftime("%Y-%m-%d")]
                except:
                    pass
    
    # Pattern 2: "4 haziran ile 9 haziran", "4 haziran - 9 haziran"
    for month_name, month_num in all_months.items():
        month_normalized = _normalize_turkish_chars(month_name)
        pattern = rf'(\d{{1,2}})\.?\s*{month_normalized}\s*(?:{range_connectors}|[-–—])\s*(\d{{1,2}})\.?\s*(?:de\s+)?(\w+)?'
        match = re.search(pattern, text_normalized)
        if match:
            day1 = int(match.group(1))
            day2 = int(match.group(2))
            month2_name = match.group(3)
            
            month2_num = month_num
            if month2_name:
                month2_num = all_months.get(_normalize_turkish_chars(month2_name.strip()), month_num)
            
            if 1 <= day1 <= 31 and 1 <= day2 <= 31:
                try:
                    date1 = datetime(year, month_num, day1)
                    date2 = datetime(year, month2_num, day2)
                    if date1 < today:
                        date1 = datetime(year + 1, month_num, day1)
                        date2 = datetime(year + 1, month2_num, day2)
                    return [date1.strftime("%Y-%m-%d"), date2.strftime("%Y-%m-%d")]
                except:
                    pass
    
    # Pattern 3: "4-9 haziran", "4 - 9 haziran"
    for month_name, month_num in all_months.items():
        month_normalized = _normalize_turkish_chars(month_name)
        pattern = rf'(\d{{1,2}})\.?\s*[-–—]\s*(\d{{1,2}})\.?\s*(?:de\s+)?{month_normalized}'
        match = re.search(pattern, text_normalized)
        if match:
            day1 = int(match.group(1))
            day2 = int(match.group(2))
            if 1 <= day1 <= 31 and 1 <= day2 <= 31:
                try:
                    date1 = datetime(year, month_num, day1)
                    date2 = datetime(year, month_num, day2)
                    if date1 < today:
                        date1 = datetime(year + 1, month_num, day1)
                        date2 = datetime(year + 1, month_num, day2)
                    return [date1.strftime("%Y-%m-%d"), date2.strftime("%Y-%m-%d")]
                except:
                    pass
    
    # Pattern 4: "4 ile 9 haziran arasi"
    for month_name, month_num in all_months.items():
        month_normalized = _normalize_turkish_chars(month_name)
        pattern = rf'(\d{{1,2}})\.?\s*(?:{range_connectors}|[-–—])\s*(\d{{1,2}})\.?\s*(?:de\s+)?{month_normalized}'
        match = re.search(pattern, text_normalized)
        if match:
            day1 = int(match.group(1))
            day2 = int(match.group(2))
            if 1 <= day1 <= 31 and 1 <= day2 <= 31:
                try:
                    date1 = datetime(year, month_num, day1)
                    date2 = datetime(year, month_num, day2)
                    if date1 < today:
                        date1 = datetime(year + 1, month_num, day1)
                        date2 = datetime(year + 1, month_num, day2)
                    return [date1.strftime("%Y-%m-%d"), date2.strftime("%Y-%m-%d")]
                except:
                    pass
    
    # Pattern 5: Tek tek tarihleri bul (son care)
    found_dates = []
    for month_name, month_num in all_months.items():
        month_normalized = _normalize_turkish_chars(month_name)
        for pattern in [rf'(\d{{1,2}})\s*{month_normalized}', rf'{month_normalized}\s*(\d{{1,2}})']:
            for match in re.finditer(pattern, text_normalized):
                day = int(match.group(1))
                if 1 <= day <= 31:
                    try:
                        date_obj = datetime(year, month_num, day)
                        if date_obj < today:
                            date_obj = datetime(year + 1, month_num, day)
                        found_dates.append((match.start(), date_obj.strftime("%Y-%m-%d")))
                    except:
                        pass
    
    if found_dates:
        # Pozisyona gore sirala ve unique yap
        found_dates.sort(key=lambda x: x[0])
        unique_dates = []
        seen = set()
        for pos, date in found_dates:
            if date not in seen:
                unique_dates.append(date)
                seen.add(date)
        if len(unique_dates) >= 2:
            return unique_dates[:2]
    
    return []


def _extract_date_range_chinese(text: str) -> List[str]:
    """
    Çince tarih aralığı desteği.
    Örnek:
    - 2026年8月14日至18日
    - 2026年8月14日到2026年8月18日
    - 2026年8月14日-8月18日
    """
    if not text:
        return []
    low = (text or "").strip()
    patterns = [
        # 2026年8月14日到2026年8月18日
        r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?\s*(?:到|至|-|—|–)\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?",
        # 2026年8月14日到8月18日
        r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?\s*(?:到|至|-|—|–)\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?",
        # 2026年8月14日至18日
        r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?\s*(?:到|至|-|—|–)\s*(\d{1,2})\s*日?",
    ]
    for idx, pattern in enumerate(patterns):
        m = re.search(pattern, low)
        if not m:
            continue
        try:
            if idx == 0:
                y1, mo1, d1, y2, mo2, d2 = [int(x) for x in m.groups()]
            elif idx == 1:
                y1, mo1, d1, mo2, d2 = [int(x) for x in m.groups()]
                y2 = y1
            else:
                y1, mo1, d1, d2 = [int(x) for x in m.groups()]
                y2, mo2 = y1, mo1

            date1 = datetime(y1, mo1, d1)
            date2 = datetime(y2, mo2, d2)
            if date2 <= date1:
                return []
            return [date1.strftime("%Y-%m-%d"), date2.strftime("%Y-%m-%d")]
        except Exception:
            continue
    return []


def _extract_all_dates(text: str) -> List[str]:
    """
    Hem ISO formati hem dogal dili destekleyen tarih cikarici.
    Once ISO formati dene, sonra dogal dil.
    """
    if not text:
        return []
    
    # Once ISO formati kontrol et (YYYY-MM-DD)
    iso_dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text)
    if len(iso_dates) >= 2:
        return iso_dates[:2]

    # Çince tarih aralığı
    chinese_dates = _extract_date_range_chinese(text)
    if len(chinese_dates) >= 2:
        return chinese_dates[:2]
    
    # Dogal dil tarih araligi dene
    natural_dates = _extract_date_range_natural(text)
    if len(natural_dates) >= 2:
        return natural_dates[:2]
    
    # Tek ISO + tek dogal tarih kombinasyonu
    if len(iso_dates) == 1 and len(natural_dates) == 1:
        all_dates = list(set(iso_dates + natural_dates))
        all_dates.sort()
        if len(all_dates) >= 2:
            return all_dates[:2]
    
    return natural_dates if natural_dates else iso_dates


# =========================
# Elektra API calls
# =========================

async def _login_get_jwt(api_key: str, *, timeout_sec: int = 15) -> str:
    api_key = _normalize_token(api_key)
    if not api_key:
        raise ElektrawebConfigError("Eksik config: Elektra_Booking ortam degiskeni bos.")

    url = f"{ELEKTRA_API_BASE_URL}/login"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }

    async with httpx.AsyncClient(timeout=timeout_sec, follow_redirects=True) as client:
        resp = await client.post(url, headers=headers)

    if resp.status_code >= 400:
        ctype = resp.headers.get("content-type", "")
        body = _safe_snippet(resp.text, 800)
        raise ElektrawebAuthError(f"/login failed: HTTP {resp.status_code} | content-type={ctype} | body={body}")

    try:
        data = resp.json()
    except Exception:
        body = _safe_snippet(resp.text, 800)
        raise ElektrawebAuthError(f"/login bad json: body={body}")

    if isinstance(data, dict) and data.get("success") is False:
        snippet = json.dumps(data, ensure_ascii=False)[:800]
        raise ElektrawebAuthError(f"/login returned success:false | response={snippet}")

    jwt = data.get("jwt") if isinstance(data, dict) else None
    if not jwt or not isinstance(jwt, str):
        snippet = json.dumps(data, ensure_ascii=False)[:800] if isinstance(data, (dict, list)) else str(data)[:800]
        raise ElektrawebAuthError(f"/login succeeded but jwt missing | response={snippet}")

    return jwt


async def fetch_price(
    *,
    hotel_id: str,
    from_date: str,
    to_date: str,
    adult: int,
    child_ages: Optional[List[int]] = None,
    currency: Optional[str] = None,
    nationality: Optional[str] = None,
    only_best_offer: bool = False,
    language: str = "tr",
    timeout_sec: int = 15,
) -> Union[Dict[str, Any], List[Any]]:
    api_key = _normalize_token(os.getenv("Elektra_Booking", ""))
    if not api_key:
        raise ElektrawebConfigError("Eksik config: Elektra_Booking ortam degiskeni bos.")

    if not hotel_id:
        raise ElektrawebConfigError("Eksik config: hotel_id bos.")

    jwt = await _login_get_jwt(api_key, timeout_sec=timeout_sec)

    url = f"{ELEKTRA_API_BASE_URL}/hotel/{hotel_id}/price/"

    cur = (currency or DEFAULT_CURRENCY).strip().upper()
    nat = (nationality or DEFAULT_NATIONALITY).strip().upper()

    params: Dict[str, Any] = {
        "fromdate": from_date,
        "todate": to_date,
        "adult": int(adult),
        "onlybestoffer": str(bool(only_best_offer)).lower(),
        "language": _api_language(language),
        "currency": cur,
        "nationality": nat,
    }

    if child_ages:
        normalized_child_ages = [
            int(a)
            for a in child_ages
            if str(a).strip().isdigit() and 0 <= int(a) <= 16
        ]
        child_age_csv = ",".join(str(a) for a in normalized_child_ages)
        pax_buckets = _child_pax_buckets(normalized_child_ages)
        total_children = len(normalized_child_ages)

        # Tenant uyumlulugu: price endpoint'i child age alanini farkli isimlerle bekleyebiliyor.
        params["childage"] = child_age_csv
        params["child-age"] = child_age_csv
        params["child-ages"] = child_age_csv
        params["child"] = total_children
        params["child-count"] = total_children
        params["children-count"] = total_children
        params["elder-child-count"] = pax_buckets["elder-child-count"]
        params["younger-child-count"] = pax_buckets["younger-child-count"]
        params["baby-count"] = pax_buckets["baby-count"]

    headers = _elektra_auth_headers(jwt)

    async with httpx.AsyncClient(timeout=timeout_sec, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers, params=params)

    if resp.status_code >= 400:
        ctype = resp.headers.get("content-type", "")
        body = _safe_snippet(resp.text, 800)
        raise ElektrawebAuthError(
            f"/price failed: HTTP {resp.status_code} | content-type={ctype} | params={json.dumps(params, ensure_ascii=False)} | body={body}"
        )

    try:
        data = resp.json()
    except Exception:
        body = _safe_snippet(resp.text, 800)
        raise ElektrawebAuthError(
            f"/price bad json | params={json.dumps(params, ensure_ascii=False)} | body={body}"
        )

    if isinstance(data, dict) and data.get("success") is False:
        snippet = json.dumps(data, ensure_ascii=False)[:800]
        raise ElektrawebAuthError(
            f"/price returned success:false | params={json.dumps(params, ensure_ascii=False)} | response={snippet}"
        )

    return data


async def fetch_availability(
    *,
    hotel_id: str,
    from_date: str,
    to_date: str,
    adult: int,
    currency: Optional[str] = None,
    child_ages: Optional[List[int]] = None,
    timeout_sec: int = 15,
) -> Union[Dict[str, Any], List[Any]]:
    """
    GET /hotel/{hotel_id}/availability
    Booking API availability data.
    """
    api_key = _normalize_token(os.getenv("Elektra_Booking", ""))
    if not api_key:
        raise ElektrawebConfigError("Eksik config: Elektra_Booking ortam degiskeni bos.")
    if not hotel_id:
        raise ElektrawebConfigError("Eksik config: hotel_id bos.")

    jwt = await _login_get_jwt(api_key, timeout_sec=timeout_sec)
    url = f"{ELEKTRA_API_BASE_URL}/hotel/{hotel_id}/availability"
    cur = (currency or DEFAULT_CURRENCY).strip().upper()
    params: Dict[str, Any] = {
        "fromdate": from_date,
        "todate": to_date,
        "adult": int(adult),
        "currency": cur,
    }
    if child_ages:
        normalized_child_ages = [
            int(a)
            for a in child_ages
            if str(a).strip().isdigit() and 0 <= int(a) <= 16
        ]
        if normalized_child_ages:
            child_age_csv = ",".join(str(a) for a in normalized_child_ages)
            params["childage"] = child_age_csv
            params["child-age"] = child_age_csv
            params["child-ages"] = child_age_csv
            params["child"] = len(normalized_child_ages)
    headers = _elektra_auth_headers(jwt)

    async with httpx.AsyncClient(timeout=timeout_sec, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers, params=params)

    if resp.status_code >= 400:
        ctype = resp.headers.get("content-type", "")
        body = _safe_snippet(resp.text, 800)
        raise ElektrawebAuthError(
            f"/availability failed: HTTP {resp.status_code} | content-type={ctype} | params={json.dumps(params, ensure_ascii=False)} | body={body}"
        )

    try:
        data = resp.json()
    except Exception:
        body = _safe_snippet(resp.text, 800)
        raise ElektrawebAuthError(
            f"/availability bad json | params={json.dumps(params, ensure_ascii=False)} | body={body}"
        )
    if isinstance(data, dict) and data.get("success") is False:
        snippet = json.dumps(data, ensure_ascii=False)[:800]
        raise ElektrawebAuthError(
            f"/availability returned success:false | params={json.dumps(params, ensure_ascii=False)} | response={snippet}"
        )
    return data


# =========================
# Create Reservation (ElektraWeb)
# =========================

async def create_elektraweb_reservation(
    *,
    hotel_id: int,
    from_date: str,
    to_date: str,
    room_type_id: int,
    board_type_id: int,
    rate_type_id: int,
    rate_code_id: int,
    price_agency_id: int,
    currency_id: int = 0,
    currency_code: str = "",
    total_price: float = 0,
    adult_count: int,
    child_ages: Optional[List[int]] = None,
    guest_first_name: str,
    guest_last_name: str,
    guest_title_id: int = 0,  # 0=MR (default), 1=MS, 2=CHILD, 3=BABY
    guest_birth_date: Optional[str] = None,
    guest_phone: str = "",
    guest_email: str = "",
    special_requests: str = "",
    nationality: str = "",
    voucher_no: str = "",
    room_count: int = 1,
    is_refundable: Optional[bool] = None,
    timeout_sec: int = 20,
) -> Dict[str, Any]:
    """
    POST /hotel/{hotel-id}/createReservation

    ElektraWeb'de yeni otel rezervasyonu olusturur.
    Returns: ElektraWeb response dict
    Raises: ElektrawebAuthError on failure
    """
    api_key = _normalize_token(os.getenv("Elektra_Booking", ""))
    if not api_key:
        raise ElektrawebConfigError("Eksik config: Elektra_Booking ortam degiskeni bos.")

    jwt = await _login_get_jwt(api_key, timeout_sec=timeout_sec)
    phone_cc = (os.getenv("ELEKTRA_DEFAULT_PHONE_COUNTRY_CODE") or "+90").strip() or "+90"
    normalized_guest_phone = _normalize_phone_e164(guest_phone, default_country_code=phone_cc)
    if guest_phone and not normalized_guest_phone:
        raise ElektrawebAuthError(
            "invalid guest phone format: please use E.164 with country code (e.g. +905555555555)"
        )

    endpoint_candidates = _resolve_endpoint_candidates("create_reservation", hotel_id)

    # Misafir bilgisi
    # NOT: API "name" / "surname" bekler, "first-name" / "last-name" DEĞİL!
    # NOT: guest-list'teki kişi sayısı adult-count ile eşleşmeli!
    #      Her yetişkin için bir guest objesi olmalı.
    effective_nationality = (nationality or DEFAULT_NATIONALITY).strip().upper() or "TR"

    primary_guest: Dict[str, Any] = {
        "title-id": guest_title_id,
        "gender": 0,
        "country": effective_nationality,
        "name": str(guest_first_name or ""),
        "surname": str(guest_last_name or ""),
    }
    if guest_birth_date:
        primary_guest["birthday"] = guest_birth_date
        primary_guest["birth-date"] = guest_birth_date
    if normalized_guest_phone:
        primary_guest["phone"] = str(normalized_guest_phone)
    if guest_email:
        primary_guest["email"] = str(guest_email)

    normalized_child_ages: List[int] = []
    for a in (child_ages or []):
        try:
            ia = int(a)
        except Exception:
            continue
        if 0 <= ia <= 16:
            normalized_child_ages.append(ia)

    # Is kurali:
    # - 0-16 yas cocuk olarak gonderilir
    # - 17+ yas cocuk alanina yazilmaz, yetiskin sayisina eklenir
    effective_adult_count = int(adult_count or 0)
    overage_count = 0
    for a in (child_ages or []):
        try:
            ia = int(a)
        except Exception:
            continue
        if ia >= 17:
            overage_count += 1
    effective_adult_count += overage_count
    effective_billable_child_ages = list(normalized_child_ages)

    def _build_guest_list_for_adults(adults: int) -> List[Dict[str, Any]]:
        gl: List[Dict[str, Any]] = [dict(primary_guest)]
        # Ek yetişkinler için boş guest objesi ekle (API adult-count kadar guest bekler)
        for _ in range(max(0, int(adults) - 1)):
            gl.append({
                "title-id": 1,
                "gender": 0,
                "country": effective_nationality,
                "name": "",
                "surname": "",
            })
        return gl

    def _child_birthdate_from_age(age: int, check_in_date: str) -> Optional[str]:
        try:
            ci = datetime.strptime(check_in_date, "%Y-%m-%d")
            y = ci.year - int(age)
            # Gun/ay bilinmediginden stabil bir tarih kullan.
            return f"{y:04d}-01-01"
        except Exception:
            return None

    guest_list: List[Dict[str, Any]] = _build_guest_list_for_adults(effective_adult_count)
    for idx, age in enumerate(normalized_child_ages, start=1):
        child_title_id = 3 if int(age) == 0 else 2  # 2=CHILD, 3=BABY
        child_guest: Dict[str, Any] = {
            "title-id": child_title_id,
            "gender": 0,
            "country": effective_nationality,
            "name": f"CHILD{idx}",
            "surname": "",
        }
        bday = _child_birthdate_from_age(int(age), from_date)
        if bday:
            child_guest["birthday"] = bday
            child_guest["birth-date"] = bday
        guest_list.append(child_guest)

    # Currency: API "currency-code" (str) bekler, "currency-id" (int) degil!
    # Eger currency_code bossa ve currency_id varsa, bilinen ID-code eslesmesini kullan
    _CURRENCY_ID_TO_CODE = {
        44: "EUR", 1: "TRY", 21: "USD", 47: "GBP",
    }
    effective_currency_code = currency_code or _CURRENCY_ID_TO_CODE.get(currency_id, "EUR")

    # Tarih formatı: API "yyyy-MM-dd" bekler (orn: "2026-09-01")
    # from_date/to_date zaten bu formatta gelmeli ama garanti edelim
    def _ensure_date_fmt(d: str) -> str:
        d = (d or "").strip()
        if not d:
            return ""
        # Zaten yyyy-MM-dd formatindaysa doğrudan dön
        if re.match(r"^\d{4}-\d{2}-\d{2}$", d):
            return d
        # Baska formatlari dene
        for fmt in ("%d/%m/%Y", "%d.%m.%Y", "%Y/%m/%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(d, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return d  # fallback: olduğu gibi gönder

    safe_from = _ensure_date_fmt(from_date)
    safe_to = _ensure_date_fmt(to_date)

    # WALKIN agency: env varsa onu kullan, yoksa offer'dan gelen agency id ile devam et
    walkin_agency_id = os.getenv("ELEKTRA_WALKIN_AGENCY_ID", "").strip()
    if walkin_agency_id.isdigit():
        effective_agency_id = int(walkin_agency_id)
    else:
        if int(price_agency_id or 0) <= 0:
            raise ElektrawebConfigError(
                "Eksik/hatali config: ELEKTRA_WALKIN_AGENCY_ID yok ve gecerli price_agency_id bulunamadi."
            )
        effective_agency_id = int(price_agency_id)
        print(
            "[ELEKTRA] WARN: ELEKTRA_WALKIN_AGENCY_ID yok. "
            f"Offer agency id kullaniliyor: {effective_agency_id}"
        )

    # Board type override: env'den BB board-type-id alınabilir
    bb_board_type_id = os.getenv("ELEKTRA_BB_BOARD_TYPE_ID", "").strip()
    effective_board_type_id = int(bb_board_type_id) if bb_board_type_id.isdigit() else board_type_id

    # Kalici cozum:
    # create oncesi, cocuk yaslari varsa fiyat/offer'i ayni pax ile yeniden cekip
    # ID + fiyat alanlarini bu quote ile senkronla.
    effective_room_type_id = int(room_type_id or 0)
    effective_rate_type_id = int(rate_type_id or 0)
    effective_rate_code_id = int(rate_code_id or 0)
    effective_total_price = float(total_price) if total_price else 0.0
    effective_offer_id = ""

    if effective_billable_child_ages or (effective_adult_count != int(adult_count or 0)):
        try:
            quote_data = await fetch_price(
                hotel_id=str(hotel_id),
                from_date=safe_from,
                to_date=safe_to,
                adult=int(effective_adult_count),
                child_ages=effective_billable_child_ages or None,
                currency=effective_currency_code,
                language="tr",
                timeout_sec=timeout_sec,
            )

            offers: List[Dict[str, Any]] = []
            if isinstance(quote_data, list):
                offers = [x for x in quote_data if isinstance(x, dict)]
            elif isinstance(quote_data, dict):
                for key in ("data", "result", "offers", "items", "rows"):
                    val = quote_data.get(key)
                    if isinstance(val, list):
                        offers = [x for x in val if isinstance(x, dict)]
                        break

            def _refund_ok(of: Dict[str, Any]) -> bool:
                if is_refundable is None:
                    return True
                cancel = of.get("cancellation-penalty") or {}
                ref = cancel.get("is-refundable")
                if ref is None:
                    return True
                return bool(ref) == bool(is_refundable)

            def _expected_pax_counts() -> Dict[str, int]:
                pax_buckets = _child_pax_buckets(normalized_child_ages)
                return {
                    "adult": int(effective_adult_count),
                    "elder-child-count": pax_buckets["elder-child-count"],
                    "younger-child-count": pax_buckets["younger-child-count"],
                    "baby-count": pax_buckets["baby-count"],
                }

            expected_pax = _expected_pax_counts()

            best_offer: Optional[Dict[str, Any]] = None
            best_offer_pax_exact: Optional[Dict[str, Any]] = None
            best_score = -1
            best_score_pax_exact = -10_000
            for of in offers:
                score = 0
                if int(of.get("room-type-id") or 0) == int(room_type_id or 0):
                    score += 8
                if int(of.get("board-type-id") or 0) == int(effective_board_type_id or 0):
                    score += 4
                if int(of.get("rate-type-id") or 0) == int(rate_type_id or 0):
                    score += 3
                if int(of.get("rate-code-id") or 0) == int(rate_code_id or 0):
                    score += 3
                if int(of.get("price-agency-id") or 0) == int(effective_agency_id or 0):
                    score += 2
                if _refund_ok(of):
                    score += 1
                # Cocuklu rezervasyonlarda pax uyumu en kritik kriterdir.
                pax = of.get("pax-count") if isinstance(of.get("pax-count"), dict) else {}
                pax_adult = int((pax or {}).get("adult") or 0)
                pax_elder = int((pax or {}).get("elder-child-count") or 0)
                pax_younger = int((pax or {}).get("younger-child-count") or 0)
                pax_baby = int((pax or {}).get("baby-count") or 0)
                pax_exact = False
                if normalized_child_ages:
                    if (
                        pax_adult == expected_pax["adult"]
                        and pax_elder == expected_pax["elder-child-count"]
                        and pax_younger == expected_pax["younger-child-count"]
                        and pax_baby == expected_pax["baby-count"]
                    ):
                        pax_exact = True
                        score += 50
                    else:
                        score -= 100
                if pax_exact and score > best_score_pax_exact:
                    best_offer_pax_exact = of
                    best_score_pax_exact = score
                if score > best_score:
                    best_score = score
                    best_offer = of

            # Cocuklu rezervasyonlarda sadece birebir pax eslesen quote'u kullan.
            if normalized_child_ages:
                best_offer = best_offer_pax_exact

            if best_offer:
                effective_room_type_id = int(best_offer.get("room-type-id") or effective_room_type_id)
                effective_board_type_id = int(best_offer.get("board-type-id") or effective_board_type_id)
                effective_rate_type_id = int(best_offer.get("rate-type-id") or effective_rate_type_id)
                effective_rate_code_id = int(best_offer.get("rate-code-id") or effective_rate_code_id)
                quoted_agency = int(best_offer.get("price-agency-id") or 0)
                if quoted_agency > 0 and not walkin_agency_id.isdigit():
                    effective_agency_id = quoted_agency
                quote_price = best_offer.get("discounted-price")
                if quote_price is None:
                    quote_price = best_offer.get("price")
                if quote_price is not None:
                    try:
                        effective_total_price = float(quote_price)
                    except Exception:
                        pass
                effective_offer_id = str(best_offer.get("id") or "").strip()
                print(
                    "[ELEKTRA] createReservation repriced with child pax. "
                    f"offer(room={effective_room_type_id}, board={effective_board_type_id}, "
                    f"rateType={effective_rate_type_id}, rateCode={effective_rate_code_id}, "
                    f"agency={effective_agency_id}, total={_format_price(effective_total_price)}, "
                    f"offerId={effective_offer_id or '-'})"
                )
            elif normalized_child_ages:
                print(
                    "[ELEKTRA] WARN: child pax reprice found no exact pax offer. "
                    "Keeping stored ids/price."
                )
        except Exception as e:
            print(f"[ELEKTRA] WARN: child pax reprice failed, fallback to stored ids/price: {e}")

    # Rezervasyon payload
    # NOT: API alan adlari:
    #   "check-in" / "check-out" (from-date / to-date DEĞİL!)
    #   "adult-count" (adult DEĞİL!)
    payload: Dict[str, Any] = {
        "hotel-id": hotel_id,
        "room-type-id": effective_room_type_id,
        "board-type-id": effective_board_type_id,
        "rate-type-id": effective_rate_type_id,
        "rate-code-id": effective_rate_code_id,
        "price-agency-id": effective_agency_id,
        "currency-code": effective_currency_code,
        "total-price": float(effective_total_price) if effective_total_price else 0.0,
        "check-in": safe_from,
        "check-out": safe_to,
        "adult-count": int(effective_adult_count),
        "nationality": effective_nationality,
        "room-count": max(1, int(room_count or 1)),
        "guest-list": guest_list,
        # Ödeyen kısmı: misafir (guest-list'teki ilk kişi)
        "payer-info": {
            "name": str(guest_first_name or ""),
            "surname": str(guest_last_name or ""),
        },
        "contact-first-name": str(guest_first_name or ""),
        "contact-last-name": str(guest_last_name or ""),
        # Kullanici talebi: rezervasyon olusurken depozito yuzdesi mutlaka 0 gitsin.
        "DEPOSITPERCENT": 0,
        "deposit-percent": 0,
    }
    # Online odeme sayfasinda "Depozito bulunamadi/0" durumunu azaltmak icin
    # bir gecelik on odeme tutarini farkli tenant anahtar isimleriyle gonder.
    deposit_amount = 0.0
    try:
        d1 = datetime.strptime(safe_from, "%Y-%m-%d")
        d2 = datetime.strptime(safe_to, "%Y-%m-%d")
        nights = max(1, (d2 - d1).days)
        deposit_amount = round(float(payload.get("total-price") or 0.0) / nights, 2)
    except Exception:
        deposit_amount = 0.0
    if deposit_amount > 0:
        payload["deposit-amount"] = deposit_amount
        payload["deposit-currency"] = str(effective_currency_code or "EUR")
        payload["prepayment-amount"] = deposit_amount
        payload["prepayment-currency"] = str(effective_currency_code or "EUR")
        payload["payment-amount"] = deposit_amount
        payload["pre-payment-amount"] = deposit_amount
        payload["advance-payment-amount"] = deposit_amount
        payload["on-payment-amount"] = deposit_amount
    if currency_id:
        payload["currency-id"] = int(currency_id)
    if normalized_guest_phone:
        payload["payer-info"]["phone"] = str(normalized_guest_phone)
    if guest_email:
        payload["payer-info"]["email"] = str(guest_email)
        payload["contact-email"] = str(guest_email)
    if normalized_guest_phone:
        payload["contact-phone"] = str(normalized_guest_phone)
    if voucher_no:
        payload["voucher-no"] = str(voucher_no)
    if effective_offer_id:
        # Farkli tenantlar farkli anahtar isimleri bekleyebiliyor.
        payload["offer-id"] = effective_offer_id
        payload["price-data-id"] = effective_offer_id
        payload["price-id"] = effective_offer_id
        payload["quote-id"] = effective_offer_id

    if normalized_child_ages:
        ordered_child_ages = sorted(list(normalized_child_ages))
        child_age_csv = ",".join(str(a) for a in ordered_child_ages)
        pax_buckets = _child_pax_buckets(ordered_child_ages)
        elder_child_count = pax_buckets["elder-child-count"]
        younger_child_count = pax_buckets["younger-child-count"]
        baby_count = pax_buckets["baby-count"]

        # Tenant uyumlulugu: farkli Elektra kurulumlari child yas alanini
        # farkli isimlerle bekleyebiliyor.
        payload["childage"] = child_age_csv
        payload["child-age"] = child_age_csv
        payload["child-ages"] = child_age_csv
        payload["child-age-list"] = list(ordered_child_ages)
        payload["child-age-arr"] = list(ordered_child_ages)
        payload["children-ages"] = list(ordered_child_ages)
        payload["child"] = len(ordered_child_ages)
        payload["child-count"] = len(ordered_child_ages)
        payload["children-count"] = len(ordered_child_ages)
        payload["elder-child-count"] = elder_child_count
        payload["younger-child-count"] = younger_child_count
        payload["baby-count"] = baby_count
        for idx, age in enumerate(ordered_child_ages[:4], start=1):
            payload[f"child-{idx}-age"] = int(age)
            payload[f"child-age-{idx}"] = int(age)
        # HotelAdvisor/HAR uyumlu alan isimleri
        payload["CHD1"] = elder_child_count
        payload["CHD2"] = younger_child_count
        payload["BABY"] = baby_count
        payload["CHD1AGE"] = int(ordered_child_ages[0]) if len(ordered_child_ages) > 0 else 0
        payload["CHD2AGE"] = int(ordered_child_ages[1]) if len(ordered_child_ages) > 1 else 0
        payload["CHD3AGE"] = int(ordered_child_ages[2]) if len(ordered_child_ages) > 2 else 0
        payload["CHD4AGE"] = int(ordered_child_ages[3]) if len(ordered_child_ages) > 3 else 0
        payload["pax-count"] = {
            "adult": int(effective_adult_count),
            "elder-child-count": elder_child_count,
            "younger-child-count": younger_child_count,
            "baby-count": baby_count,
        }

    note_parts: List[str] = []
    if special_requests:
        note_parts.append(str(special_requests).strip())

    if note_parts:
        special_note = " | ".join([p for p in note_parts if p])
        payload["note"] = special_note
        payload["notes"] = special_note
        payload["special-note"] = special_note
        payload["res-notes"] = special_note

    headers = _elektra_auth_headers(jwt, include_json=True)

    if is_refundable is not None:
        rate_label = "free_cancellation" if is_refundable else "non_refundable"
        print(f"[ELEKTRA] selected price type: {rate_label}")
    print(f"[ELEKTRA] createReservation candidates -> {endpoint_candidates}")
    print(f"[ELEKTRA] payload: {json.dumps(payload, ensure_ascii=False)[:3000]}")
    # Bazi tenantlarda createReservation ardışık birden fazla validasyon hatası dönebiliyor:
    # 1) pax mismatch (adult differs), 2) pax mismatch (child counts), 3) quote mismatch.
    # Son patch'in de yeni bir request ile denenebilmesi icin deneme sayisini bir adim yuksek tut.
    max_adaptive_attempts = 5
    data: Optional[Dict[str, Any]] = None
    last_exc: Optional[ElektrawebAuthError] = None
    no_rooms_refreshed = False
    for attempt in range(1, max_adaptive_attempts + 1):
        try:
            data = await _request_json_with_fallback(
                method="POST",
                operation="createReservation",
                endpoint_candidates=endpoint_candidates,
                headers=headers,
                timeout_sec=timeout_sec,
                json_payload=payload,
                retry_on_statuses={404, 405},
            )
            break
        except ElektrawebAuthError as exc:
            last_exc = exc
            err_text = str(exc)
            err_low = err_text.lower()
            patched = False

            pax_counts = _extract_price_data_pax_counts(err_text)
            if pax_counts and "doesn't match with price data" in err_low:
                requested_adult = int(payload.get("adult-count") or 0)
                requested_elder = int(payload.get("elder-child-count") or 0)
                requested_younger = int(payload.get("younger-child-count") or 0)
                requested_baby = int(payload.get("baby-count") or 0)
                price_adult = int(pax_counts["adult"])
                price_elder = int(pax_counts["elder-child-count"])
                price_younger = int(pax_counts["younger-child-count"])
                price_baby = int(pax_counts["baby-count"])
                requested_total = requested_adult + requested_elder + requested_younger + requested_baby
                price_total = price_adult + price_elder + price_younger + price_baby
                if requested_total == price_total:
                    # Supplier ayni toplam kisiyi farkli pax dagilimiyla fiyatliyor olabilir
                    # (orn: 2+2 yerine 3+1). Ic kaydi bozmadan, sadece create payload'ini
                    # price-data pax dagilimina hizalayip tekrar dene.
                    payload["adult-count"] = price_adult
                    payload["elder-child-count"] = price_elder
                    payload["younger-child-count"] = price_younger
                    payload["baby-count"] = price_baby
                    payload["pax-count"] = {
                        "adult": price_adult,
                        "elder-child-count": price_elder,
                        "younger-child-count": price_younger,
                        "baby-count": price_baby,
                    }
                    price_child_total = max(0, price_elder + price_younger + price_baby)
                    # Cocuk yaslari ic kayitta korunur. Supplier tarafinda child count daha azsa
                    # en kucuk yaslari child olarak birak (buyuk yaslar supplier'a gore adult sayilmis olabilir).
                    supplier_child_ages = sorted(list(normalized_child_ages))[:price_child_total]
                    child_age_csv = ",".join(str(a) for a in supplier_child_ages)
                    payload["child"] = price_child_total
                    payload["child-count"] = price_child_total
                    payload["children-count"] = price_child_total
                    payload["childage"] = child_age_csv
                    payload["child-age"] = child_age_csv
                    payload["child-ages"] = child_age_csv
                    payload["child-age-list"] = list(supplier_child_ages)
                    payload["child-age-arr"] = list(supplier_child_ages)
                    payload["children-ages"] = list(supplier_child_ages)
                    # child-age-N alanlarini supplier child listesine gore yeniden yaz.
                    for idx in range(1, 5):
                        payload.pop(f"child-{idx}-age", None)
                        payload.pop(f"child-age-{idx}", None)
                    for idx, age in enumerate(supplier_child_ages[:4], start=1):
                        payload[f"child-{idx}-age"] = int(age)
                        payload[f"child-age-{idx}"] = int(age)
                    payload["CHD1"] = price_elder
                    payload["CHD2"] = price_younger
                    payload["BABY"] = price_baby
                    payload["CHD1AGE"] = int(supplier_child_ages[0]) if len(supplier_child_ages) > 0 else 0
                    payload["CHD2AGE"] = int(supplier_child_ages[1]) if len(supplier_child_ages) > 1 else 0
                    payload["CHD3AGE"] = int(supplier_child_ages[2]) if len(supplier_child_ages) > 2 else 0
                    payload["CHD4AGE"] = int(supplier_child_ages[3]) if len(supplier_child_ages) > 3 else 0
                    # guest-list'i de supplier pax beklentisine gore hizala.
                    payload["guest-list"] = _build_guest_list_for_adults(price_adult)
                    for idx, age in enumerate(supplier_child_ages, start=1):
                        child_title_id = 3 if int(age) == 0 else 2
                        child_guest: Dict[str, Any] = {
                            "title-id": child_title_id,
                            "gender": 0,
                            "country": effective_nationality,
                            "name": f"CHILD{idx}",
                            "surname": "",
                        }
                        bday = _child_birthdate_from_age(int(age), from_date)
                        if bday:
                            child_guest["birthday"] = bday
                            child_guest["birth-date"] = bday
                        payload["guest-list"].append(child_guest)
                    patched = True
                    print(
                        "[ELEKTRA] createReservation pax mismatch detected. "
                        "same total pax; retrying with supplier pax mapping "
                        f"(requested a/e/y/b={requested_adult}/{requested_elder}/{requested_younger}/{requested_baby} "
                        f"-> supplier a/e/y/b={price_adult}/{price_elder}/{price_younger}/{price_baby})"
                    )
                else:
                    raise ElektrawebAuthError(
                        "createReservation blocked due to pax mismatch: "
                        f"requested(adult={requested_adult},elder={requested_elder},"
                        f"younger={requested_younger},baby={requested_baby}) vs "
                        f"price_data(adult={price_adult},elder={price_elder},"
                        f"younger={price_younger},baby={price_baby}). "
                        "Please reprice and recreate reservation with exact pax."
                    )

            required_amount = _extract_required_quote_amount(err_text)
            current_amount = float(payload.get("total-price") or 0.0)
            if required_amount and required_amount > 0 and abs(required_amount - current_amount) > 1e-6:
                payload["total-price"] = float(required_amount)
                patched = True
                print(
                    "[ELEKTRA] createReservation quote mismatch detected. "
                    f"retrying with total-price={_format_price(required_amount)} "
                    f"(was {_format_price(current_amount)})"
                )

            if _is_no_rooms_available_error(err_text) and not no_rooms_refreshed:
                no_rooms_refreshed = True
                try:
                    req_adult = max(1, int(payload.get("adult-count") or effective_adult_count or 1))
                    req_child_ages = payload.get("child-age-list")
                    if not isinstance(req_child_ages, list):
                        req_child_ages = list(normalized_child_ages)

                    quote_data = await fetch_price(
                        hotel_id=str(hotel_id),
                        from_date=safe_from,
                        to_date=safe_to,
                        adult=req_adult,
                        child_ages=req_child_ages or None,
                        currency=effective_currency_code,
                        language="tr",
                        timeout_sec=timeout_sec,
                    )

                    offers: List[Dict[str, Any]] = []
                    if isinstance(quote_data, list):
                        offers = [x for x in quote_data if isinstance(x, dict)]
                    elif isinstance(quote_data, dict):
                        for key in ("data", "result", "offers", "items", "rows"):
                            val = quote_data.get(key)
                            if isinstance(val, list):
                                offers = [x for x in val if isinstance(x, dict)]
                                break

                    def _is_offer_sellable(of: Dict[str, Any]) -> bool:
                        stock_keys = (
                            "available-room-count",
                            "available-room",
                            "available",
                            "availability",
                            "quota",
                            "room-count",
                            "stock",
                        )
                        for k in stock_keys:
                            if k not in of:
                                continue
                            raw = of.get(k)
                            if isinstance(raw, bool):
                                return bool(raw)
                            try:
                                return float(raw or 0) > 0
                            except Exception:
                                continue
                        return True

                    best_offer: Optional[Dict[str, Any]] = None
                    best_score = -10_000
                    for of in offers:
                        if not _is_offer_sellable(of):
                            continue
                        score = 0
                        if int(of.get("room-type-id") or 0) == int(payload.get("room-type-id") or 0):
                            score += 8
                        if int(of.get("board-type-id") or 0) == int(payload.get("board-type-id") or 0):
                            score += 4
                        if int(of.get("rate-type-id") or 0) == int(payload.get("rate-type-id") or 0):
                            score += 3
                        if int(of.get("rate-code-id") or 0) == int(payload.get("rate-code-id") or 0):
                            score += 3
                        if int(of.get("price-agency-id") or 0) == int(payload.get("price-agency-id") or 0):
                            score += 2
                        if score > best_score:
                            best_score = score
                            best_offer = of

                    if best_offer:
                        payload["room-type-id"] = int(best_offer.get("room-type-id") or payload.get("room-type-id") or 0)
                        payload["board-type-id"] = int(best_offer.get("board-type-id") or payload.get("board-type-id") or 0)
                        payload["rate-type-id"] = int(best_offer.get("rate-type-id") or payload.get("rate-type-id") or 0)
                        payload["rate-code-id"] = int(best_offer.get("rate-code-id") or payload.get("rate-code-id") or 0)
                        quoted_agency = int(best_offer.get("price-agency-id") or payload.get("price-agency-id") or 0)
                        if quoted_agency > 0:
                            payload["price-agency-id"] = quoted_agency
                        quote_price = best_offer.get("discounted-price")
                        if quote_price is None:
                            quote_price = best_offer.get("price")
                        if quote_price is not None:
                            try:
                                payload["total-price"] = float(quote_price)
                            except Exception:
                                pass
                        refreshed_offer_id = str(best_offer.get("id") or "").strip()
                        if refreshed_offer_id:
                            payload["offer-id"] = refreshed_offer_id
                            payload["price-data-id"] = refreshed_offer_id
                            payload["price-id"] = refreshed_offer_id
                            payload["quote-id"] = refreshed_offer_id
                        patched = True
                        print(
                            "[ELEKTRA] createReservation no-room offer detected. "
                            "retrying with refreshed live quote "
                            f"(room={payload.get('room-type-id')}, board={payload.get('board-type-id')}, "
                            f"rateType={payload.get('rate-type-id')}, rateCode={payload.get('rate-code-id')}, "
                            f"agency={payload.get('price-agency-id')}, total={_format_price(float(payload.get('total-price') or 0.0))}, "
                            f"offerId={refreshed_offer_id or '-'})"
                        )
                except Exception as refresh_exc:
                    print(f"[ELEKTRA] WARN: no-room refresh failed: {refresh_exc}")

            if patched and attempt < max_adaptive_attempts:
                continue
            raise

    if data is None:
        if last_exc:
            raise last_exc
        raise ElektrawebAuthError("createReservation failed: unknown error")

    if isinstance(data, dict):
        data.setdefault("_final-request-total-price", float(payload.get("total-price") or 0.0))
        data.setdefault("_final-request-child-ages", list(normalized_child_ages))

    print(f"[ELEKTRA] createReservation OK: {json.dumps(data, ensure_ascii=False)[:300]}")
    return data


async def list_elektraweb_reservations(
    *,
    hotel_id: int,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    status: Optional[str] = None,
    timeout_sec: int = 20,
) -> Dict[str, Any]:
    api_key = _normalize_token(os.getenv("Elektra_Booking", ""))
    if not api_key:
        raise ElektrawebConfigError("Eksik config: Elektra_Booking ortam degiskeni bos.")
    jwt = await _login_get_jwt(api_key, timeout_sec=timeout_sec)

    payload: Dict[str, Any] = {"hotel-id": int(hotel_id)}
    if from_date:
        payload["from-date"] = from_date
    if to_date:
        payload["to-date"] = to_date
    if status:
        payload["status"] = status

    return await _request_json_with_fallback(
        method="POST",
        operation="listReservations",
        endpoint_candidates=_resolve_endpoint_candidates("list_reservations", hotel_id),
        headers=_elektra_auth_headers(jwt, include_json=True),
        timeout_sec=timeout_sec,
        json_payload=payload,
        retry_on_statuses={404, 405},
    )


async def get_elektraweb_reservation(
    *,
    hotel_id: int,
    reservation_id: Optional[Union[int, str]] = None,
    voucher_no: Optional[str] = None,
    timeout_sec: int = 20,
) -> Dict[str, Any]:
    if not reservation_id and not voucher_no:
        raise ElektrawebConfigError("reservation_id veya voucher_no zorunlu.")

    api_key = _normalize_token(os.getenv("Elektra_Booking", ""))
    if not api_key:
        raise ElektrawebConfigError("Eksik config: Elektra_Booking ortam degiskeni bos.")
    jwt = await _login_get_jwt(api_key, timeout_sec=timeout_sec)

    payload: Dict[str, Any] = {"hotel-id": int(hotel_id)}
    if reservation_id:
        payload["reservation-id"] = str(reservation_id)
    if voucher_no:
        payload["voucher-no"] = str(voucher_no)
    get_candidates_post = _resolve_endpoint_candidates("get_reservation", hotel_id)
    last_errors: List[str] = []

    # 1) Primary: POST + payload
    try:
        return await _request_json_with_fallback(
            method="POST",
            operation="getReservation",
            endpoint_candidates=get_candidates_post,
            headers=_elektra_auth_headers(jwt, include_json=True),
            timeout_sec=timeout_sec,
            json_payload=payload,
            retry_on_statuses={404, 405},
        )
    except Exception as exc:
        last_errors.append(str(exc))

    # 2) Secondary: GET path/query varyantlari
    rid = str(reservation_id or "").strip()
    get_candidates_get: List[str] = []
    if rid:
        get_candidates_get.extend(
            [
                f"/hotel/{hotel_id}/reservation/{rid}",
                f"/hotel/{hotel_id}/reservations/{rid}",
                f"/reservation/{rid}",
                f"/reservations/{rid}",
                f"/hotel/{hotel_id}/booking/{rid}",
            ]
        )
    get_candidates_get.extend(get_candidates_post)

    params: Dict[str, Any] = {"hotel-id": int(hotel_id)}
    if rid:
        params["reservation-id"] = rid
        params["id"] = rid
    if voucher_no:
        params["voucher-no"] = str(voucher_no)
        params["voucherno"] = str(voucher_no)

    try:
        return await _request_json_with_fallback(
            method="GET",
            operation="getReservation(GET)",
            endpoint_candidates=get_candidates_get,
            headers=_elektra_auth_headers(jwt, include_json=False),
            timeout_sec=timeout_sec,
            params=params,
            retry_on_statuses={404, 405},
        )
    except Exception as exc:
        last_errors.append(str(exc))

    # 3) Last fallback: listReservations ve local filtreleme
    try:
        list_data = await list_elektraweb_reservations(
            hotel_id=int(hotel_id),
            timeout_sec=timeout_sec,
        )
        items: List[Dict[str, Any]] = []
        if isinstance(list_data, list):
            items = [x for x in list_data if isinstance(x, dict)]
        elif isinstance(list_data, dict):
            for key in ("data", "result", "reservations", "items", "rows"):
                val = list_data.get(key)
                if isinstance(val, list):
                    items = [x for x in val if isinstance(x, dict)]
                    break

        if items:
            rid_norm = rid
            voucher_norm = str(voucher_no or "").strip()
            for it in items:
                it_rid = str(it.get("reservation-id") or it.get("id") or "").strip()
                it_vno = str(it.get("voucher-no") or it.get("voucherno") or "").strip()
                if rid_norm and it_rid and it_rid == rid_norm:
                    return it
                if voucher_norm and it_vno and it_vno == voucher_norm:
                    return it

        last_errors.append("listReservations fallback: matching reservation bulunamadi")
    except Exception as exc:
        last_errors.append(f"listReservations fallback failed: {exc}")

    raise ElektrawebAuthError(
        "getReservation tum stratejilerde basarisiz. "
        "Gerekirse ELEKTRA_GET_RESERVATION_PATHS env'i ile tenant path'i override edin. "
        f"Detay: {' | '.join(last_errors)[:2500]}"
    )


async def update_elektraweb_reservation(
    *,
    hotel_id: int,
    reservation_id: Union[int, str],
    updates: Dict[str, Any],
    timeout_sec: int = 20,
) -> Dict[str, Any]:
    api_key = _normalize_token(os.getenv("Elektra_Booking", ""))
    if not api_key:
        raise ElektrawebConfigError("Eksik config: Elektra_Booking ortam degiskeni bos.")
    payload: Dict[str, Any] = {"hotel-id": int(hotel_id), "reservation-id": str(reservation_id)}
    payload.update(updates or {})
    endpoint_candidates = _resolve_endpoint_candidates("update_reservation", hotel_id)

    max_attempts = 2  # verification/rate-limit hatasi icin 1 otomatik retry
    retry_delay_raw = os.getenv("ELEKTRA_UPDATE_RETRY_DELAY_SEC", "2").strip()
    try:
        retry_delay_sec = max(1, int(retry_delay_raw))
    except Exception:
        retry_delay_sec = 2

    last_exc: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        jwt = await _login_get_jwt(api_key, timeout_sec=timeout_sec)
        try:
            return await _request_json_with_fallback(
                method="POST",
                operation="updateReservation",
                endpoint_candidates=endpoint_candidates,
                headers=_elektra_auth_headers(jwt, include_json=True),
                timeout_sec=timeout_sec,
                json_payload=payload,
                retry_on_statuses={404, 405},
                continue_on_error_substrings={"verification_exception", "query or rate limit error"},
            )
        except ElektrawebAuthError as exc:
            last_exc = exc
            err_low = str(exc).lower()
            is_verification_or_rate = (
                "verification_exception" in err_low
                or "query or rate limit error" in err_low
                or "rate limit" in err_low
            )
            if attempt < max_attempts and is_verification_or_rate:
                print(
                    "[ELEKTRA] updateReservation verification/rate-limit alindi. "
                    f"{retry_delay_sec}s sonra yeniden denenecek (attempt {attempt + 1}/{max_attempts})."
                )
                await asyncio.sleep(retry_delay_sec)
                continue
            raise

    if last_exc:
        raise last_exc
    raise ElektrawebAuthError("updateReservation failed: unknown error")


async def cancel_elektraweb_reservation(
    *,
    hotel_id: int,
    reservation_id: Union[int, str],
    reason: str = "",
    timeout_sec: int = 20,
) -> Dict[str, Any]:
    api_key = _normalize_token(os.getenv("Elektra_Booking", ""))
    if not api_key:
        raise ElektrawebConfigError("Eksik config: Elektra_Booking ortam degiskeni bos.")
    jwt = await _login_get_jwt(api_key, timeout_sec=timeout_sec)

    payload: Dict[str, Any] = {
        "hotel-id": int(hotel_id),
        "reservation-id": str(reservation_id),
    }
    if reason:
        payload["reason"] = reason

    return await _request_json_with_fallback(
        method="POST",
        operation="cancelReservation",
        endpoint_candidates=_resolve_endpoint_candidates("cancel_reservation", hotel_id),
        headers=_elektra_auth_headers(jwt, include_json=True),
        timeout_sec=timeout_sec,
        json_payload=payload,
        retry_on_statuses={404, 405},
    )


# =========================
# User message parsing
# =========================

def _extract_iso_dates(text: str) -> List[str]:
    """Geriye uyumluluk icin"""
    return re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text or "")


def _strip_dates(text: str, dates: List[str]) -> str:
    out = text or ""
    for d in dates:
        out = out.replace(d, " ")
    return out


def _parse_simple_chinese_number(token: str) -> Optional[int]:
    if not token:
        return None
    if token.isdigit():
        try:
            return int(token)
        except Exception:
            return None

    mapping = {
        "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
        "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    }
    s = token.strip()
    if s in mapping:
        return mapping[s]
    # 十一 / 二十 / 二十三
    if "十" in s:
        parts = s.split("十")
        left = parts[0]
        right = parts[1] if len(parts) > 1 else ""
        tens = mapping.get(left, 1) if left else 1
        ones = mapping.get(right, 0) if right else 0
        return tens * 10 + ones
    return mapping.get(s)


def _extract_adult_count(text: str) -> Optional[int]:
    """Yetiskin sayisini cikar"""
    low = _normalize_turkish_chars((text or "").lower())
    # Rusca sayi kelimelerini rakama cevir (iki/uc vb. benzeri)
    ru_number_words = {
        "один": "1", "одна": "1", "одного": "1", "одну": "1",
        "два": "2", "две": "2", "двух": "2",
        "три": "3", "трех": "3", "трёх": "3",
        "четыре": "4", "четырех": "4", "четырёх": "4",
        "пять": "5", "пяти": "5",
        "шесть": "6", "шести": "6",
        "семь": "7", "семи": "7",
        "восемь": "8", "восьми": "8",
        "девять": "9", "девяти": "9",
        "десять": "10", "десяти": "10",
    }
    for word, num in ru_number_words.items():
        low = re.sub(rf"\b{word}\b", num, low)

    # Arapça sayi kelimelerini rakama çevir
    ar_number_words = {
        "واحد": "1", "واحدة": "1",
        "اثنين": "2", "إثنين": "2", "اثنان": "2", "اتنين": "2",
        "ثلاثة": "3", "ثلاث": "3",
        "أربعة": "4", "اربعة": "4", "أربع": "4", "اربع": "4",
        "خمسة": "5", "خمس": "5",
        "ستة": "6", "ست": "6",
        "سبعة": "7", "سبع": "7",
        "ثمانية": "8", "ثمان": "8",
        "تسعة": "9", "تسع": "9",
        "عشرة": "10", "عشر": "10",
    }
    for word, num in ar_number_words.items():
        low = re.sub(rf"\b{word}\b", num, low)

    # Hintçe sayi kelimelerini rakama çevir
    hi_number_words = {
        "एक": "1",
        "दो": "2",
        "तीन": "3",
        "चार": "4",
        "पांच": "5",
        "पाँच": "5",
        "छह": "6",
        "सात": "7",
        "आठ": "8",
        "नौ": "9",
        "दस": "10",
    }
    for word, num in hi_number_words.items():
        low = re.sub(rf"\b{word}\b", num, low)
    
    # Pattern 0: Çince (2位成人 / 两位成人)
    raw = (text or "").lower()
    cn_match = re.search(r"([0-9一二两三四五六七八九十]+)\s*(?:位|名)?\s*(?:成人|大人|成年人)", raw)
    if cn_match:
        cn_value = _parse_simple_chinese_number(cn_match.group(1))
        if cn_value is not None:
            return int(cn_value)

    # Pattern 1: "3 yetiskin", "2 kisi", "2 adults", "2 erwachsene"
    m = re.search(
        r"(\d+)\s*(yetiskin|kisi|adults?|people|guests?|kisilik|взросл\w*|человек|гост\w*|erwachsene\w*)",
        low,
    )
    if m:
        try:
            return int(m.group(1))
        except:
            pass

    # Pattern 1.5: Arapça (2 بالغين / 2 أشخاص / ٢ شخص)
    m = re.search(
        r"([0-9]+)\s*(بالغ(?:ين)?|شخص(?:ين)?|اشخاص|أشخاص|ضيف(?:ين|ان)?|ضيوف)",
        low,
    )
    if m:
        try:
            return int(m.group(1))
        except Exception:
            pass

    # Pattern 1.6: İkili Arapça biçimler (sayı yazılmadan)
    if re.search(r"(شخصين|بالغين|ضيفين|زوجين)", low):
        return 2

    # Pattern 1.7: Hintçe (2 वयस्क / 2 वयस्कों / 2 मेहमान)
    m = re.search(
        r"(\d+)\s*(वयस्क(?:ों)?|मेहमान(?:ों)?|अतिथि(?:यों)?|व्यक्ति(?:यों)?)",
        low,
    )
    if m:
        try:
            return int(m.group(1))
        except Exception:
            pass
    
    return None


def _extract_child_ages(text: str) -> List[int]:
    """
    Cocuk yaslarini cikar.

    Destek:
    - "1 5 yas cocuk"
    - "2 cocuk 10 yas" / "2 cocuk cocuklarin ikiside 10 yasinda"  => [10, 10]
    - "2 cocuk 10 ve 3 yas" => [10, 3]
    - "5 yasinda cocuk"
    - "9 aylik bebek" => [0]
    - Genel fallback: "10 yas" gibi yaslari topla
    """
    ages: List[int] = []
    low = _normalize_turkish_chars((text or "").lower())

    child_keywords = [
        "cocuk", "child", "children", "kid", "kids", "bebek", "baby", "infant",
        "बच्चा", "बच्चों", "शिशु",
    ]
    has_child_context = any(k in low for k in child_keywords)
    has_month_age = bool(re.search(r"\b\d{1,2}\s*ay\w*\b", low))

    # Cocuk baglami yoksa yaslari cocuk diye varsayma
    if not has_child_context and not has_month_age:
        return ages

    # Mesajdan çocuk sayısı (örn: "2 cocuk")
    child_count: Optional[int] = None
    m_cnt = re.search(r"(\d+)\s*(?:cocuk|child|children|kid|kids|bebek|baby|infant|बच्चा|बच्चों|शिशु)", low)
    if m_cnt:
        try:
            child_count = int(m_cnt.group(1))
        except:
            child_count = None

    # Pattern A: "2 cocuk 10 yas ve 8 yas" / "2 children 10 years and 8 years"
    m_multi_with_age_words = re.search(
        r"(?:cocuk|child|children|kid|kids|bebek|baby|infant)\w*"
        r"(?:\s+\w+){0,8}\s+((?:\d{1,2}\s*yas\w*\s*(?:,|ve|and)\s*)+\d{1,2}\s*yas\w*)",
        low,
    )
    if m_multi_with_age_words:
        seq = m_multi_with_age_words.group(1)
        seq_ages = [int(n) for n in re.findall(r"\d{1,2}", seq)]
        ages.extend([a for a in seq_ages if 0 <= a <= 16])
        if child_count and len(ages) >= child_count:
            return ages[: min(child_count, 4)]
        return ages[:4]

    # Pattern 0: "2 cocuk 10 ve 3 yas" gibi birden cok yas
    m_multi = re.search(
        r"(?:cocuk|child|children|kid|kids|bebek|baby|infant)\w*"
        r"(?:\s+\w+){0,8}\s+((?:\d{1,2}\s*(?:,|ve|and)\s*)+\d{1,2})\s*yas",
        low,
    )
    if m_multi:
        seq = m_multi.group(1)
        seq_ages = [int(n) for n in re.findall(r"\d{1,2}", seq)]
        ages.extend([a for a in seq_ages if 0 <= a <= 16])
        return ages[:4]

    # Pattern 1: "2 10 yas cocuk" (sayi + yas + cocuk)
    m = re.search(r"(\d+)\s+(\d+)\s*yas\w*\s*(?:cocuk|child|children|kid|kids|bebek|baby|infant)", low)
    if m:
        count = int(m.group(1))
        age = int(m.group(2))
        if 0 <= age <= 16:
            ages.extend([age] * min(count, 4))
            return ages[:4]

    # Pattern 2 (GELİŞTİRİLDİ): "2 cocuk ... 10 yas" (arada birkaç kelime olabilir, rakam olmasın)
    # Örn: "2 cocuk cocuklarin ikiside 10 yasinda"
    m = re.search(
        r"(\d+)\s*(?:cocuk|child|children|kid|kids|bebek|baby|infant)\w*(?:\s+[a-z_]+){0,8}\s+(\d+)\s*yas",
        low,
    )
    if m:
        count = int(m.group(1))
        age = int(m.group(2))
        if 0 <= age <= 16:
            # Mesajda birden fazla yas ifadesi varsa tek yasi cogaltma.
            mentioned_ages = [int(n) for n in re.findall(r"(\d{1,2})\s*yas", low) if 0 <= int(n) <= 16]
            if len(mentioned_ages) >= 2:
                if child_count and len(mentioned_ages) >= child_count:
                    return mentioned_ages[: min(child_count, 4)]
                return mentioned_ages[:4]
            ages.extend([age] * min(count, 4))
            return ages[:4]

    # Pattern 2.5: "cocuk yasi 7" / "child age 7" / "children ages 7 and 10"
    m_age_label = re.search(
        r"(?:cocuk|child|children|kid|kids|bebek|baby|infant)\w*"
        r"(?:\s+\w+){0,3}\s*(?:yasi|yaslari|age|ages)\s*[:=\-]?\s*"
        r"((?:\d{1,2}\s*(?:,|ve|and)\s*)*\d{1,2})",
        low,
    )
    if m_age_label:
        seq = m_age_label.group(1)
        seq_ages = [int(n) for n in re.findall(r"\d{1,2}", seq)]
        seq_ages = [a for a in seq_ages if 0 <= a <= 16]
        if seq_ages:
            if child_count and len(seq_ages) == 1 and child_count > 1:
                return [seq_ages[0]] * min(child_count, 4)
            if child_count and len(seq_ages) >= child_count:
                return seq_ages[: min(child_count, 4)]
            return seq_ages[:4]

    # Pattern 3: "5 yasinda cocuk" veya "5 yas cocuk"
    m = re.search(r"(\d+)\s*yas\w*\s*(?:cocuk|child|children|kid|kids|bebek|baby|infant)", low)
    if m:
        age = int(m.group(1))
        if 0 <= age <= 16:
            ages.append(age)

    # Pattern 3.5: "9 aylik bebek", "6 ay", "12 aylık" -> 0 yas.
    # NOT: "2 ayrı oda ayarlayabilir..." gibi metinlerdeki "ay..." kelimelerine
    # yanlis pozitif dusmemesi icin sadece ay birimi sekillerini kabul et.
    month_matches = list(
        re.finditer(r"\b(\d{1,2})\s*(?:ay|aylik|aylık|aylik\b|aylık\b)\b", low)
    )
    if month_matches:
        month_zero_count = len(month_matches)
        if child_count and child_count > month_zero_count:
            month_zero_count = child_count
        ages.extend([0] * month_zero_count)

    # Pattern 4: Genel yas arama (son care)
    if not ages:
        for mm in re.finditer(r"(\d{1,2})\s*yas", low):
            try:
                a = int(mm.group(1))
                if 0 <= a <= 16:
                    ages.append(a)
            except:
                pass
        # EN: "7 years old", "8 yr old", "6 y/o"
        if not ages:
            for mm in re.finditer(r"\b(\d{1,2})\s*(?:years?\s*old|yrs?\s*old|y\/o)\b", low):
                try:
                    a = int(mm.group(1))
                    if 0 <= a <= 16:
                        ages.append(a)
                except Exception:
                    pass
        if child_count and len(ages) >= child_count:
            return ages[: min(child_count, 4)]

    ages = ages[:4]

    # Eğer mesaj "2 cocuk" diyorsa ama sadece 1 yaş yakaladıysak:
    # - Bu fonksiyon, Pattern 2 ile "2 cocuk ... 10 yas" durumunu zaten [10,10] yapar.
    # - Hala tek yaş kaldıysa (örn: arada rakam/karmaşa), yanlış varsayım yapmayalım: boş dön → flow yaşları tek tek ister.
    if child_count and child_count > 1 and len(ages) == 1:
        return []

    return ages


def _apply_child_policy_to_pricing(adult_count: int, child_ages: Optional[List[int]]) -> Tuple[int, List[int]]:
    """
    Is kurali:
    - 0-16 yas cocuk olarak fiyat sorgusuna gonderilir
    - 17+ yas yetiskin sayisina eklenir
    """
    normalized_children: List[int] = []
    effective_adult = int(adult_count or 0)
    for a in (child_ages or []):
        try:
            ia = int(a)
        except Exception:
            continue
        if 0 <= ia <= 16:
            normalized_children.append(ia)
        elif ia >= 17:
            effective_adult += 1

    return effective_adult, normalized_children


def _infer_currency(text: str) -> Optional[str]:
    """Kullanici mesajindan para birimi cikar - sadece acikca belirtilmisse"""
    low = (text or "").lower()
    # TL kontrolu - word boundary ile (musaitlik gibi kelimeleri yakalamasin)
    if re.search(r'\btl\b', low) or re.search(r'\btry\b', low) or "turk lirasi" in low or "₺" in low:
        return "TRY"
    if any(k in low for k in ["usd", "dolar", "dollar", "$"]):
        return "USD"
    if any(k in low for k in ["gbp", "pound", "sterlin"]):
        return "GBP"
    if any(k in low for k in ["eur", "euro", "€"]):
        return "EUR"
    return None

def _infer_nationality(text: str) -> Optional[str]:
    m = re.search(r"\b(tr|de|gb|us|ru)\b", (text or "").lower())
    return m.group(1).upper() if m else None


def _collect_exchange_rows(node: Any, out: List[Dict[str, Any]]) -> None:
    if isinstance(node, dict):
        has_rate_key = any(k in node for k in ("RATE", "rate"))
        has_currency_key = any(
            k in node for k in ("CURRENCY", "currency", "CURCODE", "curcode", "CURRENCYCODE", "currencycode")
        )
        if has_rate_key and has_currency_key:
            out.append(node)
        for v in node.values():
            if isinstance(v, (dict, list)):
                _collect_exchange_rows(v, out)
    elif isinstance(node, list):
        for item in node:
            if isinstance(item, (dict, list)):
                _collect_exchange_rows(item, out)


async def _fetch_exchange_rates_map(hotel_id: int, rate_date: str) -> Dict[str, float]:
    from app.services.elektra_hoteladvisor_service import hoteladvisor_function

    payload = {"DATE": rate_date, "HOTELID": int(hotel_id)}
    raw = await hoteladvisor_function("FN_HOTEL_EXCHANGERATES_ALL", payload=payload, timeout_sec=15)
    rows: List[Dict[str, Any]] = []
    _collect_exchange_rows(raw, rows)
    rates: Dict[str, float] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = str(
            row.get("CURRENCY")
            or row.get("currency")
            or row.get("CURCODE")
            or row.get("curcode")
            or row.get("CURRENCYCODE")
            or row.get("currencycode")
            or ""
        ).strip().upper()
        try:
            rate = float(row.get("RATE") if row.get("RATE") is not None else row.get("rate"))
        except Exception:
            continue
        if code and rate > 0:
            rates[code] = rate
    return rates


def _convert_amount_with_rates(amount: float, from_currency: str, to_currency: str, rates: Dict[str, float]) -> Optional[float]:
    from_cur = (from_currency or "").strip().upper()
    to_cur = (to_currency or "").strip().upper()
    if amount <= 0:
        return amount
    if not from_cur or not to_cur:
        return None
    if from_cur == to_cur:
        return amount
    if from_cur not in rates or to_cur not in rates:
        return None
    amount_try = float(amount) * float(rates[from_cur])
    return amount_try / float(rates[to_cur])


async def _coerce_offer_currency(
    offers: List[Dict[str, Any]],
    *,
    requested_currency: str,
    hotel_id: str,
    rate_date: str,
) -> List[Dict[str, Any]]:
    target = (requested_currency or "").strip().upper()
    if not offers or not target:
        return offers

    # TRY/EUR/USD/GBP disinda bir hedefte otomatik donusum yapma.
    if target not in {"TRY", "EUR", "USD", "GBP"}:
        return offers

    rates = await _fetch_exchange_rates_map(int(hotel_id or 0), rate_date)
    if not rates:
        return offers

    converted: List[Dict[str, Any]] = []
    for offer in offers:
        if not isinstance(offer, dict):
            converted.append(offer)
            continue
        row = dict(offer)
        src = str(row.get("currency") or row.get("currency-code") or DEFAULT_CURRENCY).strip().upper() or DEFAULT_CURRENCY
        for key in ("discounted-price", "price", "total-price"):
            if row.get(key) is None:
                continue
            try:
                original = float(row.get(key))
            except Exception:
                continue
            conv = _convert_amount_with_rates(original, src, target, rates)
            if conv is not None:
                row[key] = _normalize_price_value(conv)
        row["currency"] = target
        row["currency-code"] = target
        converted.append(row)
    return converted


def _is_price_inquiry(text: str) -> bool:
    """Mesajin fiyat/musaitlik sorgusu olup olmadigini kontrol et"""
    low = _normalize_turkish_chars((text or "").lower())
    price_keywords = [
        "fiyat", "ucret", "price", "cost", "rate",
        "musait", "uygun", "available", "availability",
        "bos", "vacancy", "kac para", "ne kadar",
        "giris", "cikis", "check", "konaklama"
    ]
    return any(kw in low for kw in price_keywords)


def _to_int_or_none(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        if isinstance(value, bool):
            return int(value)
        return int(str(value).strip())
    except Exception:
        return None


def _is_offer_bookable(offer: Dict[str, Any]) -> bool:
    """Offer rezervasyona uygun mu? (müsaitlik/satış durumu)"""
    if not isinstance(offer, dict):
        return False

    falsey_availability_keys = (
        "is-available", "is_available", "available", "bookable", "is-saleable", "is_saleable",
    )
    for key in falsey_availability_keys:
        if key in offer:
            val = offer.get(key)
            if isinstance(val, bool) and not val:
                return False
            sval = str(val).strip().lower()
            if sval in {"false", "0", "no", "none", "yok"}:
                return False

    count_keys = (
        "room-count", "room_count", "available-room-count", "available_room_count",
        "availability", "quota", "remaining", "room-to-sell", "room_to_sell",
    )
    for key in count_keys:
        iv = _to_int_or_none(offer.get(key))
        if iv is not None and iv <= 0:
            return False

    # Elektra /price yanitinda gece bazli stok listesi gelebilir.
    arr = offer.get("availability-arr")
    if isinstance(arr, list) and arr:
        for v in arr:
            iv = _to_int_or_none(v)
            if iv is not None and iv <= 0:
                return False

    # Bazi tenantlarda stop-sell nested rate-rules altinda tutulur.
    rr = offer.get("rate-rules")
    if isinstance(rr, dict):
        if _to_bool(rr.get("stop-sell")):
            return False

    status = str(offer.get("status") or offer.get("availability-status") or "").strip().lower()
    if status in {"soldout", "sold_out", "full", "closed", "unavailable", "not_available", "pasif"}:
        return False

    return True


BASE_ROOM_REQUEST_TAGS: Dict[str, set] = {
    "deluxe": set(),
    "superior": set(),
    "exclusiveLand": {"street_view", "noisy"},
    "exclusivePool": {"pool_view", "noisy"},
    "penthouseLand": {"jacuzzi"},
    "penthouse": {"jacuzzi"},
    "premium": {"jacuzzi"},
}


def _resolve_room_key_from_label(label: str) -> Optional[str]:
    normalized = _normalize_turkish_chars(str(label or "")).strip()
    if not normalized:
        return None

    # First try canonical room normalization used by API room-type mapping.
    room_info = _normalize_room_type(normalized)
    if room_info and room_info.get("key"):
        return str(room_info["key"])

    low = normalized.lower()
    mapping = (
        ("exclusive pool", "exclusivePool"),
        ("exclusive havuz", "exclusivePool"),
        ("exclusive land", "exclusiveLand"),
        ("exclusive sokak", "exclusiveLand"),
        ("exclusive cadde", "exclusiveLand"),
        ("exclusive street", "exclusiveLand"),
        ("penthouse land", "penthouseLand"),
        ("penthouse", "penthouse"),
        ("superior", "superior"),
        ("deluxe", "deluxe"),
        ("premium", "premium"),
    )
    for hint, room_key in mapping:
        if hint in low:
            return room_key
    return None


@lru_cache(maxsize=1)
def _automation_room_view_tags() -> Dict[str, set]:
    """
    Oda manzara etiketlerini otel veri dosyasindan (automation_info) turetir.
    Bu sayede sabit hardcode yerine otel bilgisindeki gercek manzara tanimi kullanilir.
    """
    try:
        from app.content.automation_info import OTOMASYON_INFO_TEXT_V2
    except Exception:
        return {}

    text = str(OTOMASYON_INFO_TEXT_V2 or "")
    if not text:
        return {}

    tags: Dict[str, set] = {}
    blocks = re.split(r"\[ODA T[İI]P[İI]\s*#\d+\]", text, flags=re.IGNORECASE)
    for block in blocks:
        room_m = re.search(
            r"Oda\s*ad[ıi]\s*\(TR\s*/\s*EN\)\s*:\s*([^\n\r]+)",
            block,
            flags=re.IGNORECASE,
        )
        view_m = re.search(
            r"Manzara\s*/\s*konum\s*:\s*([^\n\r]+)",
            block,
            flags=re.IGNORECASE,
        )
        if not room_m or not view_m:
            continue
        room_key = _resolve_room_key_from_label(room_m.group(1))
        if not room_key:
            continue

        view_low = _normalize_turkish_chars(view_m.group(1).lower())
        room_tags: set = set()
        if any(k in view_low for k in ("havuz manzara", "havuz taraf", "pool view", "poolside", "pool-side")):
            room_tags.add("pool_view")
        if any(k in view_low for k in ("cadde manzara", "sokak manzara", "street view", "city view")):
            room_tags.add("street_view")
        if any(k in view_low for k in ("deniz manzara", "sea view", "ocean view")):
            room_tags.add("sea_view")
        if room_tags:
            tags.setdefault(room_key, set()).update(room_tags)

    return tags


def _room_request_tags() -> Dict[str, set]:
    tags: Dict[str, set] = {k: set(v) for k, v in BASE_ROOM_REQUEST_TAGS.items()}
    for room_key, dynamic_tags in _automation_room_view_tags().items():
        tags.setdefault(room_key, set()).update(dynamic_tags)
    policy = get_quiet_room_policy()
    for key in policy.get("quiet_auto_room_keys", []):
        tags.setdefault(key, set()).add("quiet_preferred")
    for key in policy.get("quiet_handoff_room_keys", []):
        tags.setdefault(key, set()).add("quiet_human_only")
    for key in policy.get("standard_room_keys", []):
        tags.setdefault(key, set()).add("standard_preferred")
    return tags


def _extract_room_request_filters(text: str) -> Dict[str, set]:
    low = _normalize_turkish_chars((text or "").lower())
    required: set = set()
    forbidden: set = set()

    if any(k in low for k in ("sessiz", "sakin", "quiet", "no noise", "less noise")):
        required.add("quiet_preferred")
        forbidden.add("noisy")
    if any(k in low for k in ("deniz manzara", "sea view", "ocean view")):
        required.add("sea_view")
    if any(k in low for k in ("havuz manzara", "pool view")):
        required.add("pool_view")
    if any(k in low for k in ("sokak manzara", "street view", "city view")):
        required.add("street_view")
    if any(k in low for k in ("jakuz", "jakuzi", "jacuzzi")):
        required.add("jacuzzi")
    if (
        "standart oda" in low
        or "standard room" in low
        or "standart room" in low
        or ("standart" in low and "oda" in low)
    ):
        required.add("standard_preferred")

    return {"required": required, "forbidden": forbidden}


def _room_tag_supported_globally(tag: str) -> bool:
    if not tag:
        return False
    room_tags = _room_request_tags()
    return any(tag in tags for tags in room_tags.values())


def _offer_matches_room_request(offer: Dict[str, Any], filters: Dict[str, set]) -> bool:
    room_tags = _room_request_tags()
    room_info = _normalize_room_type(offer.get("room-type", ""))
    if not room_info:
        return False
    tags = room_tags.get(room_info["key"], set())
    required = filters.get("required", set())
    forbidden = filters.get("forbidden", set())
    if required and not required.issubset(tags):
        return False
    if forbidden and tags.intersection(forbidden):
        return False
    return True


def _extract_offers_from_api_json(api_json: Union[Dict[str, Any], List[Any]]) -> Tuple[List[Dict[str, Any]], bool]:
    offers: List[Dict[str, Any]] = []
    explicit_list_seen = False
    if isinstance(api_json, list):
        explicit_list_seen = True
        offers = [x for x in api_json if isinstance(x, dict)]
    elif isinstance(api_json, dict):
        for key in ("data", "result", "offers", "prices"):
            if key in api_json and isinstance(api_json.get(key), list):
                explicit_list_seen = True
                offers = [x for x in api_json.get(key) if isinstance(x, dict)]
                break
    return offers, explicit_list_seen


def _normalize_roomtype_code(raw: str) -> str:
    return re.sub(r"\s+", " ", str(raw or "").strip()).upper()


def _normalize_row_date(raw: Any) -> str:
    txt = str(raw or "").strip()
    if len(txt) >= 10:
        return txt[:10]
    return txt


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    sval = str(value).strip().lower()
    return sval in {"1", "true", "yes", "y", "evet"}


def _stay_night_dates(from_date: str, to_date: str) -> List[str]:
    try:
        start = datetime.strptime(from_date, "%Y-%m-%d")
        end = datetime.strptime(to_date, "%Y-%m-%d")
    except Exception:
        return []
    if end <= start:
        return []
    out: List[str] = []
    cur = start
    while cur < end:
        out.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)
    return out


def _extract_hoteladvisor_rows(raw: Any) -> List[Dict[str, Any]]:
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if not isinstance(raw, dict):
        return []

    rows: List[Dict[str, Any]] = []
    result_sets = raw.get("ResultSets")
    if isinstance(result_sets, list):
        for rs in result_sets:
            if isinstance(rs, list):
                rows.extend(x for x in rs if isinstance(x, dict))

    data = raw.get("data")
    if isinstance(data, list):
        rows.extend(x for x in data if isinstance(x, dict))

    result = raw.get("result")
    if isinstance(result, list):
        rows.extend(x for x in result if isinstance(x, dict))

    return rows


def _extract_booking_availability_rows(raw: Any) -> List[Dict[str, Any]]:
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if not isinstance(raw, dict):
        return []
    rows: List[Dict[str, Any]] = []
    for key in ("data", "result", "items", "rows", "availability"):
        val = raw.get(key)
        if isinstance(val, list):
            rows.extend(x for x in val if isinstance(x, dict))
    return rows

def _extract_room_stock_from_availability_rows(
    rows: List[Dict[str, Any]],
    *,
    from_date: str,
    to_date: str,
    room_type_id_to_key: Optional[Dict[int, str]] = None,
) -> Dict[str, int]:
    """
    Her oda tipi icin tum gece araliginda satilabilir adet (minimum ROOMTOSELL) hesaplar.
    - stop-sell olan gece varsa o gece adet 0 kabul edilir.
    - Bir oda tipinin tum gecelerde kaydi yoksa sonuca dahil edilmez.
    """
    nights = _stay_night_dates(from_date, to_date)
    if not nights:
        return {}
    required_dates = set(nights)
    id_to_key = room_type_id_to_key or {}

    per_key_per_date: Dict[str, Dict[str, int]] = {}

    for row in rows:
        date_key = _normalize_row_date(row.get("date") if "date" in row else row.get("DATE"))
        if date_key not in required_dates:
            continue

        room_key = ""
        room_type_raw = (
            row.get("room-type")
            or row.get("room_type")
            or row.get("ROOMTYPE")
            or row.get("ROOMTYPECODE")
            or row.get("room-type-code")
            or ""
        )
        room_info = _normalize_room_type(str(room_type_raw))
        if room_info:
            room_key = room_info["key"]
        if not room_key:
            rid = _to_int_or_none(row.get("room-type-id") if "room-type-id" in row else row.get("room_type_id"))
            if rid is not None and rid in id_to_key:
                room_key = id_to_key[rid]
        if not room_key:
            continue

        room_to_sell = _to_int_or_none(
            row.get("ROOMTOSELL")
            if "ROOMTOSELL" in row
            else row.get("room-to-sell")
        )
        stop_sell = _to_bool(row.get("STOPSELL") if "STOPSELL" in row else row.get("stop-sell"))
        current = 0 if stop_sell else max(int(room_to_sell or 0), 0)

        day_map = per_key_per_date.setdefault(room_key, {})
        prev = day_map.get(date_key)
        # Ayni gun/oda icin birden fazla satir varsa en yuksek satilabilir adedi kullan.
        day_map[date_key] = current if prev is None else max(prev, current)

    out: Dict[str, int] = {}
    for room_key, day_map in per_key_per_date.items():
        if set(day_map.keys()) != required_dates:
            continue
        out[room_key] = min(day_map[d] for d in nights)
    return out


def _derive_stay_eligible_room_keys(
    rows: List[Dict[str, Any]],
    *,
    from_date: str,
    to_date: str,
) -> set[str]:
    """
    Rule:
    - Her gece (check-in dahil, check-out haric) icin ROOMTOSELL > 0 olmali
    - Her gece icin STOPSELL true olmamali
    """
    nights = _stay_night_dates(from_date, to_date)
    if not nights:
        return set()
    required_dates = set(nights)

    seen_dates_by_key: Dict[str, set[str]] = {}
    good_dates_by_key: Dict[str, set[str]] = {}

    for row in rows:
        date_key = _normalize_row_date(row.get("DATE") or row.get("date"))
        if date_key not in required_dates:
            continue

        room_code = _normalize_roomtype_code(row.get("ROOMTYPECODE") or row.get("room-type-code"))
        room_info = _normalize_room_type(room_code)
        if not room_info:
            continue
        room_key = room_info["key"]

        seen_dates_by_key.setdefault(room_key, set()).add(date_key)

        room_to_sell = _to_int_or_none(
            row.get("ROOMTOSELL")
            if "ROOMTOSELL" in row
            else row.get("room-to-sell")
        )
        stop_sell = _to_bool(row.get("STOPSELL") if "STOPSELL" in row else row.get("stop-sell"))

        if (room_to_sell is not None and room_to_sell > 0) and not stop_sell:
            good_dates_by_key.setdefault(room_key, set()).add(date_key)

    eligible: set[str] = set()
    for room_key, seen_dates in seen_dates_by_key.items():
        if seen_dates == required_dates and good_dates_by_key.get(room_key, set()) == required_dates:
            eligible.add(room_key)
    return eligible


def _derive_stay_eligible_room_type_ids_from_availability(
    rows: List[Dict[str, Any]],
    *,
    from_date: str,
    to_date: str,
) -> set[int]:
    """
    Booking API /availability fallback:
    Bir room-type-id'nin tum gece araliginda (check-in dahil, check-out haric)
    her gece ROOMTOSELL > 0 ve STOPSELL != true olmasi gerekir.
    """
    nights = _stay_night_dates(from_date, to_date)
    if not nights:
        return set()
    required_dates = set(nights)
    seen_by_room_id: Dict[int, set[str]] = {}
    good_by_room_id: Dict[int, set[str]] = {}

    for row in rows:
        rid = _to_int_or_none(row.get("room-type-id") if "room-type-id" in row else row.get("room_type_id"))
        if rid is None or rid <= 0:
            continue
        date_key = _normalize_row_date(row.get("date") if "date" in row else row.get("DATE"))
        if date_key not in required_dates:
            continue
        rid_i = int(rid)
        seen_by_room_id.setdefault(rid_i, set()).add(date_key)

        has_capacity_signal = ("ROOMTOSELL" in row) or ("room-to-sell" in row) or ("STOPSELL" in row) or ("stop-sell" in row)
        room_to_sell = _to_int_or_none(
            row.get("ROOMTOSELL")
            if "ROOMTOSELL" in row
            else row.get("room-to-sell")
        )
        stop_sell = _to_bool(row.get("STOPSELL") if "STOPSELL" in row else row.get("stop-sell"))
        if not has_capacity_signal:
            # Bazi payload'larda room-to-sell/stop-sell alanlari olmayabiliyor.
            # Bu durumda "tum gecelerde satir var" kuralina geri don.
            good_by_room_id.setdefault(rid_i, set()).add(date_key)
        elif (room_to_sell is not None and room_to_sell > 0) and not stop_sell:
            good_by_room_id.setdefault(rid_i, set()).add(date_key)

    return {
        rid
        for rid, dates in seen_by_room_id.items()
        if dates == required_dates and good_by_room_id.get(rid, set()) == required_dates
    }


async def _fetch_stay_eligibility(
    *,
    hotel_id: str,
    from_date: str,
    to_date: str,
    adult: int,
    currency: Optional[str] = None,
    child_ages: Optional[List[int]] = None,
    timeout_sec: int = 20,
) -> Dict[str, Any]:
    """
    Returns:
    {
      "source": "hoteladvisor_vw" | "bookingapi_availability",
      "room_keys": set[str],
      "room_type_ids": set[int],
    }
    """
    # Kullanici talebi: 4001.hoteladvisor.net kullanma.
    # Musaitlik kontrolu yalnizca bookingapi.elektraweb.com /availability ile yapilir.
    print(
        f"[ELEKTRA][AVAILABILITY] source=bookingapi_only hotel_id={hotel_id} {from_date}->{to_date}"
    )

    nights = _stay_night_dates(from_date, to_date)
    if not nights:
        return {"source": "bookingapi_availability", "room_keys": set(), "room_type_ids": set()}

    raw = await fetch_availability(
        hotel_id=hotel_id,
        from_date=from_date,
        to_date=to_date,
        adult=int(adult),
        currency=(currency or DEFAULT_CURRENCY),
        child_ages=child_ages or None,
        timeout_sec=timeout_sec,
    )
    rows = _extract_booking_availability_rows(raw)
    room_type_ids = _derive_stay_eligible_room_type_ids_from_availability(
        rows,
        from_date=from_date,
        to_date=to_date,
    )
    return {"source": "bookingapi_availability", "room_keys": set(), "room_type_ids": room_type_ids}


async def _fetch_stay_eligible_room_keys_from_hoteladvisor(
    *,
    hotel_id: str,
    from_date: str,
    to_date: str,
    timeout_sec: int = 20,
) -> set[str]:
    nights = _stay_night_dates(from_date, to_date)
    if not nights:
        return set()
    last_night = nights[-1]

    # Local import to avoid import cycle at module import time.
    from app.services.elektra_hoteladvisor_service import hoteladvisor_select

    payload: Dict[str, Any] = {
        # HAR uyumlulugu: bu endpoint tenant bazli secili kolonlari reddedebilir.
        # Extranet ekraninda Select:["*"] ile cagriliyor.
        "Select": ["*"],
        "Where": [
            {"Column": "DATE", "Operator": ">=", "Value": from_date},
            {"Column": "DATE", "Operator": "<=", "Value": last_night},
            {"Column": "ROOMTYPECODE", "Operator": "IS NOT NULL", "Value": ""},
            {},
            {"Column": "HOTELID", "Operator": "=", "Value": int(hotel_id)},
        ],
        "Paging": {"Current": 1, "ItemsPerPage": 9999},
    }
    raw = await hoteladvisor_select("VW_EASYPMS_AVAILABILITY", payload=payload, timeout_sec=timeout_sec)
    rows = _extract_hoteladvisor_rows(raw)
    return _derive_stay_eligible_room_keys(rows, from_date=from_date, to_date=to_date)

async def fetch_room_stock_by_type_from_availability(
    *,
    hotel_id: str,
    from_date: str,
    to_date: str,
    adult: int,
    currency: Optional[str] = None,
    child_ages: Optional[List[int]] = None,
    room_type_id_to_key: Optional[Dict[int, str]] = None,
    timeout_sec: int = 20,
) -> Dict[str, int]:
    """
    Booking API /availability verisinden oda tipi bazinda satilabilir adet dondurur.
    Donen deger: {"premium": 2, "superior": 1, ...}
    """
    nights = _stay_night_dates(from_date, to_date)
    if not nights:
        return {}
    raw = await fetch_availability(
        hotel_id=hotel_id,
        from_date=from_date,
        to_date=to_date,
        adult=int(adult),
        currency=(currency or DEFAULT_CURRENCY),
        child_ages=child_ages or None,
        timeout_sec=timeout_sec,
    )
    rows = _extract_booking_availability_rows(raw)
    return _extract_room_stock_from_availability_rows(
        rows,
        from_date=from_date,
        to_date=to_date,
        room_type_id_to_key=room_type_id_to_key or {},
    )


def _filter_offers_for_customer_request(
    offers: List[Dict[str, Any]],
    request_text: str,
) -> Tuple[List[Dict[str, Any]], Dict[str, set], Dict[str, bool]]:
    filters = _extract_room_request_filters(request_text)
    filtered = [o for o in offers if _is_offer_bookable(o)]
    meta: Dict[str, bool] = {
        "quiet_human_only_found": False,
        "unsupported_sea_view_request": False,
    }

    # Otelde hiç bulunmayan oda özelliği istenirse bunu availability yokmuş gibi
    # göstermeyelim; deterministik olarak "özellik mevcut değil" cevabı üretelim.
    if "sea_view" in filters.get("required", set()) and not _room_tag_supported_globally("sea_view"):
        meta["unsupported_sea_view_request"] = True
        return [], filters, meta

    if "quiet_preferred" in filters.get("required", set()):
        room_tags = _room_request_tags()
        for offer in filtered:
            room_info = _normalize_room_type(offer.get("room-type", ""))
            if not room_info:
                continue
            tags = room_tags.get(room_info["key"], set())
            if "quiet_human_only" in tags:
                meta["quiet_human_only_found"] = True

    if filters.get("required") or filters.get("forbidden"):
        filtered = [o for o in filtered if _offer_matches_room_request(o, filters)]
    return filtered, filters, meta


# =========================
# Reply formatting (SABLONA UYGUN)
# =========================

def _format_price_reply(
    api_json: Union[Dict[str, Any], List[Any]],
    lang: str,
    from_date: str,
    to_date: str,
    adult: int,
    child_count: int = 0,
    child_ages: Optional[List[int]] = None,
    request_context_text: str = "",
) -> Tuple[str, bool]:
    """
    API response'unu sablona uygun formatta dondur.
    Returns: (reply_text, success)
    success=False ise handoff gerekli
    """
    
    offers, explicit_list_seen = _extract_offers_from_api_json(api_json)
    filtered_offers, request_filters, filter_meta = _filter_offers_for_customer_request(
        offers,
        request_context_text or "",
    )
    offers = filtered_offers

    # ✅ Boş liste geldiyse: handoff değil, "müsait yok" mesajı dön
    if not offers:
        if explicit_list_seen:
            had_request_filter = bool(request_filters.get("required") or request_filters.get("forbidden"))
            if had_request_filter:
                if filter_meta.get("unsupported_sea_view_request"):
                    if lang == "en":
                        return (
                            "Hello, thank you for your interest.\n\n"
                            "Our hotel does not have sea-view rooms. "
                            "However, we do have pool-view and street-view room options.\n\n"
                            "Would you like me to share suitable alternative room types?\n\n"
                            "I will be happy to assist."
                        , True)
                    if lang == "ru":
                        return (
                            "Здравствуйте, спасибо за ваш интерес.\n\n"
                            "В нашем отеле нет номеров с видом на море. "
                            "Однако у нас есть варианты с видом на бассейн и на улицу.\n\n"
                            "Хотите, я подберу для вас подходящие альтернативные типы номеров?\n\n"
                            "С радостью помогу."
                        , True)
                    return (
                        "Merhaba, ilginiz için teşekkür ederim.\n\n"
                        "Otelimizde deniz manzaralı oda bulunmamaktadır. Ancak havuz manzaralı ve cadde manzaralı odalarımız mevcuttur.\n\n"
                        "Size uygun alternatif oda tipleri hakkında bilgi vermemi ister misiniz?\n\n"
                        "Nazikçe cevabınızı bekliyorum."
                    , True)
                if lang == "en":
                    date_range = _format_date_range_en(from_date, to_date)
                    return (
                        f"For {date_range}, I couldn't find rooms that match your requested room preference. "
                        f"If you share an alternative preference, I can check again.",
                        True
                    )
                if lang == "ru":
                    date_range = _format_date_range_ru(from_date, to_date)
                    return (
                        f"На даты {date_range} не нашлось номеров, соответствующих вашему запросу по типу/расположению комнаты. "
                        f"Если укажете альтернативу, проверю снова.",
                        True
                    )
                date_range = _format_date_range_tr(from_date, to_date)
                return (
                    f"{date_range} tarihleri için talep ettiğiniz oda özelliğine uygun müsait oda bulunamadı. "
                    f"Alternatif tercih paylaşırsanız tekrar kontrol edebilirim.",
                    True
                )
            if lang == "en":
                date_range = _format_date_range_en(from_date, to_date)
                return (
                    f"Unfortunately, we don't have availability for {date_range} right now. "
                    f"If you share alternative dates, I can check again.",
                    True
                )
            if lang == "ru":
                date_range = _format_date_range_ru(from_date, to_date)
                return (
                    f"К сожалению, на даты {date_range} сейчас нет доступных номеров. "
                    f"Если предложите альтернативные даты, я проверю снова.",
                    True
                )
            date_range = _format_date_range_tr(from_date, to_date)
            return (
                f"Maalesef {date_range} tarihleri için şu an müsait oda görünmüyor. "
                f"Alternatif tarih paylaşırsanız tekrar kontrol edebilirim.",
                True
            )
        return ("", False)


    # Odalari grupla: room_key -> {refundable: price, non_refundable: price}
    # ONEMLI: Sadece musteriye sunulabilir rate-type'lar dahil edilir.
    # "Kontrat", "Balayi", "SPA Paket", "Yasli Paketi" gibi ozel rate-type'lar filtrelenir.
    _PRICE_ALLOWED_RATE_TYPES = {
        "iptal edilemez", "İptal edilemez",
        "ucretsiz iptal", "ücretsiz iptal", "ücretsiz İptal",
    }
    _PRICE_ALLOWED_RATE_TYPES_LOWER = {x.lower() for x in _PRICE_ALLOWED_RATE_TYPES}

    def _build_room_prices(source_offers: List[Dict[str, Any]], *, strict_rate_type: bool) -> Tuple[Dict[str, Dict[str, Optional[float]]], str]:
        out: Dict[str, Dict[str, Optional[float]]] = {}
        cur = "EUR"
        for offer in source_offers:
            room_type_raw = offer.get("room-type", "")
            room_info = _normalize_room_type(room_type_raw)
            if not room_info:
                continue

            # Rate-type filtresi: Kontrat, Balayi, SPA vb. gosterme
            rate_type_name = (offer.get("rate-type") or "").strip().lower()
            if strict_rate_type and rate_type_name and rate_type_name not in _PRICE_ALLOWED_RATE_TYPES_LOWER:
                continue

            room_key = room_info["key"]
            if room_key not in out:
                out[room_key] = {"refundable": None, "non_refundable": None}

            raw_price = offer.get("discounted-price") or offer.get("price") or 0
            price = _normalize_price_value(float(raw_price))
            cur = offer.get("currency", "EUR")

            cancel_info = offer.get("cancellation-penalty", {})
            is_refundable = cancel_info.get("is-refundable", False)
            if is_refundable:
                if out[room_key]["refundable"] is None or price < out[room_key]["refundable"]:
                    out[room_key]["refundable"] = price
            else:
                if out[room_key]["non_refundable"] is None or price < out[room_key]["non_refundable"]:
                    out[room_key]["non_refundable"] = price
        return out, cur

    room_prices, currency = _build_room_prices(offers, strict_rate_type=True)
    if not room_prices:
        # Fallback: Bazi acentalarda sadece "Kontrat" rate-type donuyor.
        # Musaitlik dogruyken "müsait yok" dememek icin bookable odalardan fiyat olustur.
        room_prices, currency = _build_room_prices(offers, strict_rate_type=False)

    # Hic oda bulunamadi - HANDOFF
    if not room_prices:
        return ("", False)

    lang_norm = (lang or "en").lower()
    if lang_norm not in {"tr", "en", "ru", "de", "ar", "es", "fr", "zh", "hi", "pt"}:
        lang_norm = "en"

    currency_upper = (currency or "").strip().upper()
    if lang_norm == "tr" and currency_upper == "TRY":
        display_currency = "₺"
    elif lang_norm == "ru":
        display_currency = {
            "EUR": "евро",
            "USD": "долл. США",
            "TRY": "тур. лир",
        }.get(currency_upper, currency)
    else:
        display_currency = currency

    # Tarihleri formatla
    nights = _calculate_nights(from_date, to_date)
    
    # Cocuk metni
    child_text_tr = ""
    child_text_en = ""
    child_text_zh = ""
    if child_count > 0:
        ages_txt_tr = " ve ".join(f"{a} yaş" for a in (child_ages or []))
        ages_txt_en = ", ".join(f"age {a}" for a in (child_ages or []))
        ages_txt_zh = "、".join(f"{a}岁" for a in (child_ages or []))
        child_text_tr = f" + {child_count} çocuk ({ages_txt_tr})" if ages_txt_tr else f" + {child_count} çocuk"
        child_text_en = f" + {child_count} children ({ages_txt_en})" if ages_txt_en else f" + {child_count} children"
        child_text_zh = f" + {child_count}名儿童（{ages_txt_zh}）" if ages_txt_zh else f" + {child_count}名儿童"
    
    # Sablona gore mesaj olustur
    if lang_norm == "en":
        date_range = _format_date_range_en(from_date, to_date)
        lines = [
            f"Thank you very much for your interest in our hotel.",
            f"",
            f"Our prices between {date_range} for {adult} Adults{child_text_en} {nights} night -including breakfast- below;",
            f""
        ]
        
        for room_key in ROOM_ORDER:
            if room_key not in room_prices:
                continue
            
            prices = room_prices[room_key]
            room_map = None
            for k, v in ROOM_TYPE_MAP.items():
                if v["key"] == room_key:
                    room_map = v
                    break
            
            if not room_map:
                continue
            
            room_name = room_map["en"]
            lines.append(room_name)
            
            nr_price = prices.get("non_refundable")
            r_price = prices.get("refundable")
            
            lines.append(f"Non refundable: {_format_price(nr_price)} {display_currency}" if nr_price is not None else "Non refundable: -")
            lines.append(f"Free Cancellation: {_format_price(r_price)} {display_currency}" if r_price is not None else "Free Cancellation: -")
            lines.append("")
        
        lines.extend([
            'Our check-in and check-out times: "Check-in: 02.00 p.m. - Check-out: 12.00 p.m."',
            "",
            "Note: Due to cancellations 5 days before check-in we refund 100% with Free Cancellation reservations.",
            "",
            "There are no cancellation/refund after check in.",
            "",
            "For reservation confirmation we charge 1 night price."
        ])

        if filter_meta.get("quiet_human_only_found") and "quiet_preferred" in request_filters.get("required", set()):
            lines.extend([
                "",
                "Note: Superior rooms are also quiet, but booking for Superior is handled by our live representative."
            ])
    elif lang_norm == "ru":
        date_range = _format_date_range_ru(from_date, to_date)
        child_text_ru = ""
        if child_count > 0:
            ages_txt_ru = ", ".join(f"{a} лет" for a in (child_ages or []))
            child_text_ru = f" + {child_count} детей ({ages_txt_ru})" if ages_txt_ru else f" + {child_count} детей"

        lines = [
            "Благодарим вас за интерес к нашему отелю.",
            "",
            f"Наши цены на {nights} ночей в период {date_range}",
            f"с завтраком для {adult} взрослых{child_text_ru}:",
            ""
        ]

        for room_key in ROOM_ORDER:
            if room_key not in room_prices:
                continue

            prices = room_prices[room_key]
            room_map = None
            for k, v in ROOM_TYPE_MAP.items():
                if v["key"] == room_key:
                    room_map = v
                    break

            if not room_map:
                continue

            room_name = room_map.get("ru", room_map.get("en", ""))
            lines.append(room_name)

            nr_price = prices.get("non_refundable")
            r_price = prices.get("refundable")

            lines.append(f"Невозвратный тариф: {_format_price(nr_price)} {display_currency}" if nr_price is not None else "Невозвратный тариф: -")
            lines.append(f"Бесплатная отмена: {_format_price(r_price)} {display_currency}" if r_price is not None else "Бесплатная отмена: -")
            lines.append("")

        lines.extend([
            'Время заезда и выезда: "Заезд: 14:00 - Выезд: 12:00"',
            "",
            "Примечание: при тарифе с бесплатной отменой возврат 100% возможен при отмене не позднее чем за 5 дней до заезда.",
            "",
            "После заезда отмена и возврат не предусмотрены.",
            "",
            "Для подтверждения бронирования взимается стоимость 1 ночи."
        ])

        if filter_meta.get("quiet_human_only_found") and "quiet_preferred" in request_filters.get("required", set()):
            lines.extend([
                "",
                "Примечание: номера Superior тоже тихие, но бронирование Superior оформляется через живого менеджера."
            ])
    elif lang_norm == "zh":
        date_range = f"{from_date} 至 {to_date}"
        lines = [
            "感谢您对我们酒店的关注。",
            "",
            f"{date_range}（{nights}晚）{adult}位成人{child_text_zh}（含早餐）价格如下：",
            "",
        ]

        for room_key in ROOM_ORDER:
            if room_key not in room_prices:
                continue

            prices = room_prices[room_key]
            room_map = None
            for k, v in ROOM_TYPE_MAP.items():
                if v["key"] == room_key:
                    room_map = v
                    break
            if not room_map:
                continue

            room_name = room_map["en"]
            lines.append(room_name)
            nr_price = prices.get("non_refundable")
            r_price = prices.get("refundable")
            lines.append(f"不可退款: {_format_price(nr_price)} {display_currency}" if nr_price is not None else "不可退款: -")
            lines.append(f"免费取消: {_format_price(r_price)} {display_currency}" if r_price is not None else "免费取消: -")
            lines.append("")

        lines.extend([
            '入住/退房时间: "入住 14:00 - 退房 12:00"',
            "",
            "免费取消政策: 入住前5天及以上取消可100%退款。",
            "入住后不支持取消/退款。",
            "",
            "确认预订需支付1晚房费。",
        ])
    elif lang_norm in {"de", "ar", "es", "fr", "hi", "pt"}:
        date_range = f"{from_date} - {to_date}"
        generic_localized = {
            "de": {
                "intro_1": "Ich kann Ihnen bei der Preisermittlung helfen.",
                "intro_2": "Vielen Dank für Ihr Interesse an unserem Hotel.",
                "price_line": f"Unsere Preise zwischen {date_range} für {adult} Erwachsene{child_text_en} für {nights} Nächte (inklusive Frühstück):",
                "label_non_ref": "Nicht erstattbar",
                "label_free_cancel": "Kostenlose Stornierung",
                "check_line": 'Unsere Check-in/Check-out-Zeiten: "Check-in: 14:00 - Check-out: 12:00"',
                "refund_line": "Hinweis: Bei kostenloser Stornierung ist bis 5 Tage vor Check-in eine 100% Rückerstattung möglich.",
                "after_checkin_line": "Nach dem Check-in sind Stornierung und Rückerstattung nicht möglich.",
                "confirm_line": "Zur Buchungsbestätigung wird der Preis für 1 Nacht berechnet.",
                "quiet_note": "Hinweis: Superior-Zimmer sind ebenfalls ruhig, aber Superior-Buchungen werden von unserem Live-Team durchgeführt.",
            },
            "ar": {
                "intro_1": "يمكنني مساعدتك بمعلومات الأسعار.",
                "intro_2": "شكرًا جزيلاً لاهتمامك بفندقنا.",
                "price_line": f"أسعارنا بين {date_range} لعدد {adult} بالغين{child_text_en} لمدة {nights} ليالٍ (شاملة الإفطار):",
                "label_non_ref": "غير قابل للاسترداد",
                "label_free_cancel": "إلغاء مجاني",
                "check_line": 'أوقات تسجيل الدخول والمغادرة: "تسجيل الدخول: 14:00 - تسجيل المغادرة: 12:00"',
                "refund_line": "ملاحظة: في الحجوزات ذات الإلغاء المجاني، يتم رد 100% عند الإلغاء قبل 5 أيام من تسجيل الدخول.",
                "after_checkin_line": "بعد تسجيل الدخول لا يتوفر إلغاء أو استرداد.",
                "confirm_line": "لتأكيد الحجز، يتم تحصيل قيمة ليلة واحدة.",
                "quiet_note": "ملاحظة: غرف Superior هادئة أيضًا، لكن حجز Superior يتم عبر فريقنا البشري.",
            },
            "es": {
                "intro_1": "Puedo ayudarte con la información de precios.",
                "intro_2": "Muchas gracias por tu interés en nuestro hotel.",
                "price_line": f"Nuestros precios entre {date_range} para {adult} adultos{child_text_en} por {nights} noches (desayuno incluido):",
                "label_non_ref": "No reembolsable",
                "label_free_cancel": "Cancelación gratuita",
                "check_line": 'Nuestros horarios de check-in/check-out: "Check-in: 14:00 - Check-out: 12:00"',
                "refund_line": "Nota: en reservas con cancelación gratuita, cancelando hasta 5 días antes del check-in se reembolsa el 100%.",
                "after_checkin_line": "Después del check-in no hay cancelación ni reembolso.",
                "confirm_line": "Para confirmar la reserva, cobramos el precio de 1 noche.",
                "quiet_note": "Nota: las habitaciones Superior también son silenciosas, pero su reserva se gestiona con nuestro equipo en vivo.",
            },
            "fr": {
                "intro_1": "Je peux vous aider avec les informations tarifaires.",
                "intro_2": "Merci beaucoup pour votre intérêt pour notre hôtel.",
                "price_line": f"Nos tarifs entre {date_range} pour {adult} adultes{child_text_en} pendant {nights} nuits (petit déjeuner inclus) :",
                "label_non_ref": "Non remboursable",
                "label_free_cancel": "Annulation gratuite",
                "check_line": 'Nos horaires de check-in/check-out : "Check-in : 14:00 - Check-out : 12:00"',
                "refund_line": "Remarque : avec l'annulation gratuite, un remboursement à 100% est possible jusqu'à 5 jours avant le check-in.",
                "after_checkin_line": "Après le check-in, aucune annulation ni remboursement n'est possible.",
                "confirm_line": "Pour confirmer la réservation, nous facturons le prix d'1 nuit.",
                "quiet_note": "Remarque : les chambres Superior sont aussi calmes, mais leur réservation est traitée par notre équipe en direct.",
            },
            "hi": {
                "intro_1": "मैं मूल्य जानकारी में आपकी मदद कर सकता हूँ।",
                "intro_2": "हमारे होटल में आपकी रुचि के लिए बहुत धन्यवाद।",
                "price_line": f"{date_range} के बीच {adult} वयस्कों{child_text_en} के लिए {nights} रातों (नाश्ता शामिल) के हमारे मूल्य:",
                "label_non_ref": "नॉन-रिफंडेबल",
                "label_free_cancel": "फ्री कैंसलेशन",
                "check_line": 'हमारे check-in/check-out समय: "Check-in: 14:00 - Check-out: 12:00"',
                "refund_line": "नोट: फ्री कैंसलेशन बुकिंग में check-in से 5 दिन पहले तक कैंसल करने पर 100% रिफंड मिलता है।",
                "after_checkin_line": "check-in के बाद कैंसलेशन/रिफंड उपलब्ध नहीं है।",
                "confirm_line": "बुकिंग कन्फर्म करने के लिए 1 रात का शुल्क लिया जाता है।",
                "quiet_note": "नोट: Superior कमरे भी शांत हैं, लेकिन Superior बुकिंग हमारी लाइव टीम संभालती है।",
            },
            "pt": {
                "intro_1": "Posso ajudar com informações de preços.",
                "intro_2": "Muito obrigado pelo seu interesse em nosso hotel.",
                "price_line": f"Nossos preços entre {date_range} para {adult} adultos{child_text_en} por {nights} noites (café da manhã incluído):",
                "label_non_ref": "Não reembolsável",
                "label_free_cancel": "Cancelamento gratuito",
                "check_line": 'Nossos horários de check-in/check-out: "Check-in: 14:00 - Check-out: 12:00"',
                "refund_line": "Observação: em reservas com cancelamento gratuito, há reembolso de 100% para cancelamentos até 5 dias antes do check-in.",
                "after_checkin_line": "Após o check-in, não há cancelamento/reembolso.",
                "confirm_line": "Para confirmar a reserva, cobramos o valor de 1 noite.",
                "quiet_note": "Observação: quartos Superior também são silenciosos, mas a reserva de Superior é feita pelo nosso time de atendimento ao vivo.",
            },
        }
        labels = generic_localized.get(lang_norm, generic_localized["es"])
        lines = [
            labels["intro_1"],
            labels["intro_2"],
            "",
            labels["price_line"],
            "",
        ]

        for room_key in ROOM_ORDER:
            if room_key not in room_prices:
                continue

            prices = room_prices[room_key]
            room_map = None
            for k, v in ROOM_TYPE_MAP.items():
                if v["key"] == room_key:
                    room_map = v
                    break
            if not room_map:
                continue

            room_name = room_map.get("en", "")
            lines.append(room_name)
            nr_price = prices.get("non_refundable")
            r_price = prices.get("refundable")
            lines.append(f"{labels['label_non_ref']}: {_format_price(nr_price)} {display_currency}" if nr_price is not None else f"{labels['label_non_ref']}: -")
            lines.append(f"{labels['label_free_cancel']}: {_format_price(r_price)} {display_currency}" if r_price is not None else f"{labels['label_free_cancel']}: -")
            lines.append("")

        lines.extend([
            labels["check_line"],
            "",
            labels["refund_line"],
            "",
            labels["after_checkin_line"],
            "",
            labels["confirm_line"],
        ])

        if filter_meta.get("quiet_human_only_found") and "quiet_preferred" in request_filters.get("required", set()):
            lines.extend(["", labels["quiet_note"]])

    else:  # Turkish
        date_range = _format_date_range_tr(from_date, to_date)
        lines = [
            "Memnuniyetle yardımcı olurum.",
            f"",
            f"{date_range} tarihleri arasında {nights} gece",
            f"kahvaltı dahil {adult} yetişkin{child_text_tr} fiyatlarımız aşağıdaki gibidir;",
            f""
        ]
        
        for room_key in ROOM_ORDER:
            if room_key not in room_prices:
                continue
            
            prices = room_prices[room_key]
            room_map = None
            for k, v in ROOM_TYPE_MAP.items():
                if v["key"] == room_key:
                    room_map = v
                    break
            
            if not room_map:
                continue
            
            room_name = room_map["tr"]
            lines.append(room_name)
            
            nr_price = prices.get("non_refundable")
            r_price = prices.get("refundable")
            
            lines.append(f"İade yapılmaz: {_format_price(nr_price)} {display_currency}" if nr_price is not None else "İade yapılmaz: -")
            lines.append(f"Ücretsiz İptal: {_format_price(r_price)} {display_currency}" if r_price is not None else "Ücretsiz İptal: -")
            lines.append("")

        lines.extend([
            'Otelimize giriş ve çıkış saatlerimiz: "Giriş Saati: 14:00 - Çıkış Saati: 12:00"',
            "",
            "Not: Ücretsiz iptal seçeneği ile yapılan rezervasyonlarda girişten 5 gün öncesine kadar iptal olması halinde %100 geri ödeme alabilirsiniz.",
            "",
            "Girişten itibaren herhangi bir iptal/iade seçeneğimiz bulunmamaktadır.",
            "",
            "Rezervasyon onayı için 1 gecelik ödeme tahsil edilmektedir. Kalan ödemeyi giriş günündeki güncel döviz kuruna göre TL veya döviz olarak yapabilirsiniz.",
            "",
            "Dilerseniz uygun oda tipini seçtiğiniz anda rezervasyon adımına birlikte geçebiliriz."
        ])

        if filter_meta.get("quiet_human_only_found") and "quiet_preferred" in request_filters.get("required", set()):
            lines.extend([
                "",
                "Not: Superior odalar da sessizdir; ancak Superior rezervasyonları canlı müşteri temsilcisi üzerinden yapılmaktadır."
            ])

    return ("\n".join(lines), True)


def _build_missing_info_reply(missing: List[str], lang: str, dates_found: bool) -> str:
    """Eksik bilgi mesaji - sadece gercekten eksik olani sor"""
    missing_labels = {
        "tr": {
            "tarih_araligi": "tarih aralığı",
            "guest_count": "misafir sayısı",
            "child_ages": "çocuk yaşları",
        },
        "en": {
            "tarih_araligi": "date range",
            "guest_count": "guest count",
            "child_ages": "child ages",
        },
        "ru": {
            "tarih_araligi": "диапазон дат",
            "guest_count": "количество гостей",
            "child_ages": "возраст детей",
        },
        "de": {
            "tarih_araligi": "Datumsbereich",
            "guest_count": "Anzahl der Gäste",
            "child_ages": "Alter der Kinder",
        },
        "es": {
            "tarih_araligi": "rango de fechas",
            "guest_count": "número de huéspedes",
            "child_ages": "edades de niños",
        },
        "fr": {
            "tarih_araligi": "période de dates",
            "guest_count": "nombre de clients",
            "child_ages": "âges des enfants",
        },
        "pt": {
            "tarih_araligi": "intervalo de datas",
            "guest_count": "número de hóspedes",
            "child_ages": "idades das crianças",
        },
        "ar": {
            "tarih_araligi": "نطاق التواريخ",
            "guest_count": "عدد الضيوف",
            "child_ages": "أعمار الأطفال",
        },
        "zh": {
            "tarih_araligi": "日期范围",
            "guest_count": "入住人数",
            "child_ages": "儿童年龄",
        },
        "hi": {
            "tarih_araligi": "तारीख सीमा",
            "guest_count": "मेहमानों की संख्या",
            "child_ages": "बच्चों की उम्र",
        },
    }
    lang_norm = (lang or "en").lower()
    labels = missing_labels.get(lang_norm, missing_labels["en"])
    missing_text = ", ".join(labels.get(item, item) for item in missing)
    child_ages_only_missing = ("child_ages" in missing) and ("guest_count" not in missing) and ("tarih_araligi" not in missing)

    if lang_norm == "en":
        if child_ages_only_missing:
            return "Could you share the children's ages, please?"
        if dates_found and "guest_count" in missing:
            return "Thank you! For how many guests? (adults and children with ages if any)"
        return (
            "To check availability, please provide:\n"
            f"Missing: {missing_text}"
        )
    if lang_norm == "ru":
        if child_ages_only_missing:
            return "Пожалуйста, подскажите возраст детей."
        if dates_found and "guest_count" in missing:
            return "Спасибо! На сколько гостей планируется проживание? (взрослые и, если есть, дети с возрастами)"
        return (
            "Чтобы проверить наличие, пожалуйста, уточните:\n"
            f"Не хватает данных: {missing_text}"
        )
    if lang_norm == "tr":
        if child_ages_only_missing:
            return "Çocuk yaşları nelerdir?"
        if dates_found and "guest_count" in missing:
            return "Teşekkürler! Kaç kişilik konaklama olacak? (yetişkin ve varsa çocuk yaşları)"
        return (
            "Müsaitlik kontrolü için lütfen belirtin:\n"
            f"Eksik: {missing_text}"
        )
    if lang_norm == "zh":
        if child_ages_only_missing:
            return "请问儿童年龄分别是多少？"
        if dates_found and "guest_count" in missing:
            return "谢谢！请问入住人数是多少？（成人及儿童年龄）"
        return (
            "为了查询可订情况，请补充以下信息：\n"
            f"缺少: {missing_text}"
        )
    if lang_norm == "hi":
        if child_ages_only_missing:
            return "कृपया बच्चों की उम्र बताइए।"
        if dates_found and "guest_count" in missing:
            return "धन्यवाद! कुल कितने मेहमान होंगे? (वयस्क और यदि हों तो बच्चों की उम्र के साथ)"
        return (
            "उपलब्धता जांचने के लिए कृपया यह जानकारी साझा करें:\n"
            f"कमी: {missing_text}"
        )

    if dates_found and "guest_count" in missing:
        # Desteklenen diger dillerde de net/tekdüze bilgi isteme için EN fallback.
        return "Thank you! For how many guests? (adults and children with ages if any)"
    return (
        "To check availability, please provide:\n"
        f"Missing: {missing_text}"
    )


# =========================
# Main entry used by kassandra_openai_bot.py
# =========================

async def handle_elektra_price_request(
    user_message: str,
    *,
    hotel_id: str,
    lang: str = "tr",
) -> Tuple[str, str, Optional[List[Dict[str, Any]]]]:
    """
    Returns: (reply, log, raw_offers)
    - raw_offers: Basarili sorguda ham offer listesi (booking icin cache'lenir)
    - Eger reply "HANDOFF:" ile basliyorsa, insana devir gerekli
    """
    # Hem ISO hem dogal dil tarihleri cikar
    dates = _extract_all_dates(user_message)
    missing: List[str] = []
    dates_found = len(dates) >= 2

    if not dates_found:
        missing.append("tarih_araligi")

    # Yetiskin ve cocuk sayisi
    adult = _extract_adult_count(user_message)
    child_ages = _extract_child_ages(user_message)
    child_count = None
    m_child = re.search(
        r"(\d+)\s*(?:cocuk|child|children|kid|kids|bebek|baby|infant|बच्चा|बच्चों|शिशु|طفل|أطفال|اطفال|儿童|小孩|兒童)",
        _normalize_turkish_chars((user_message or "").lower()),
    )
    if m_child:
        try:
            child_count = int(m_child.group(1))
        except Exception:
            child_count = None
    
    if adult is None:
        missing.append("guest_count")

    # Cocuk kelimesi var ama yas yok
    low_msg = _normalize_turkish_chars((user_message or "").lower())
    if any(k in low_msg for k in ["cocuk", "child", "children", "kid", "kids", "bebek", "baby", "infant"]) and not child_ages:
        missing.append("child_ages")
    # Cocuk sayisi verildiyse, yas sayisi da ayni olmalı. Eşleşmiyorsa net yaş sor.
    if child_count is not None and child_count > 0 and len(child_ages) != child_count:
        if "child_ages" not in missing:
            missing.append("child_ages")

    if missing:
        reply = _build_missing_info_reply(missing, lang, dates_found)
        log = json.dumps({"missing": missing, "input": (user_message or "")[:300], "dates_found": dates_found}, ensure_ascii=False)
        return reply, log, None

    from_date, to_date = dates[0], dates[1]
    currency = _infer_currency(user_message) or DEFAULT_CURRENCY
    nationality = _infer_nationality(user_message) or DEFAULT_NATIONALITY
    pricing_adult, pricing_child_ages = _apply_child_policy_to_pricing(int(adult), child_ages)

    try:
        api_json = await fetch_price(
            hotel_id=hotel_id,
            from_date=from_date,
            to_date=to_date,
            adult=int(pricing_adult),
            child_ages=pricing_child_ages or None,
            currency=currency,
            nationality=nationality,
            language=(lang or "tr"),
        )
    except Exception as e:
        # API hatasi - HANDOFF
        log = json.dumps({"error": str(e)[:500], "from": from_date, "to": to_date}, ensure_ascii=False)
        return "HANDOFF:API_ERROR", log, None

    offers_for_cache, _ = _extract_offers_from_api_json(api_json)
    try:
        eligibility = await _fetch_stay_eligibility(
            hotel_id=hotel_id,
            from_date=from_date,
            to_date=to_date,
            adult=int(pricing_adult),
            currency=currency,
            child_ages=pricing_child_ages or None,
            timeout_sec=20,
        )
    except Exception as e:
        print(f"[ELEKTRA][AVAILABILITY] check failed hotel_id={hotel_id} {from_date}->{to_date} err={e}")
        log = json.dumps(
            {
                "error": f"availability_check_failed: {str(e)[:400]}",
                "from": from_date,
                "to": to_date,
                "hotel_id": hotel_id,
            },
            ensure_ascii=False,
        )
        return "HANDOFF:AVAILABILITY_ERROR", log, None

    eligible_room_keys: set[str] = set(eligibility.get("room_keys") or set())
    eligible_room_type_ids: set[int] = set(eligibility.get("room_type_ids") or set())
    eligibility_source = str(eligibility.get("source") or "-")

    if offers_for_cache:
        offers_for_cache = [
            o
            for o in offers_for_cache
            if (
                ((_normalize_room_type(o.get("room-type", "") or "") or {}).get("key") in eligible_room_keys)
                or (
                    _to_int_or_none(o.get("room-type-id")) in eligible_room_type_ids
                )
            )
        ]

    # Kullanici acikca para birimi istediyse, offer fiyatlarini o para birimine cevir.
    # Booking API bazen istenen currency'yi dikkate almayip EUR dondugu icin burada zorlariz.
    if offers_for_cache and currency:
        try:
            offers_for_cache = await _coerce_offer_currency(
                offers_for_cache,
                requested_currency=currency,
                hotel_id=hotel_id,
                rate_date=from_date,
            )
        except Exception as e:
            print(f"[ELEKTRA] WARN: currency coercion failed ({currency}): {e}")

    offers_for_cache, room_request_filters, _ = _filter_offers_for_customer_request(offers_for_cache, user_message)

    reply, success = _format_price_reply(
        offers_for_cache,
        lang,
        from_date,
        to_date,
        adult,
        child_count=len(child_ages),
        child_ages=child_ages,
        request_context_text=user_message,
    )

    if not success:
        # Format hatasi veya bos response - HANDOFF
        log = json.dumps({"error": "empty_or_invalid_response", "from": from_date, "to": to_date, "adult": adult}, ensure_ascii=False)
        return "HANDOFF:FORMAT_ERROR", log, None

    # Ham offer listesini cikar (booking cache icin)
    raw_offers: Optional[List[Dict[str, Any]]] = offers_for_cache or None

    log_obj = {
        "hotel_id": hotel_id,
        "from": from_date,
        "to": to_date,
        "adult": adult,
        "pricing_adult": pricing_adult,
        "child_ages": child_ages,
        "pricing_child_ages": pricing_child_ages,
        "currency": currency,
        "nationality": nationality,
        "availability_source": eligibility_source,
        "eligible_room_keys_count": len(eligible_room_keys),
        "eligible_room_type_ids_count": len(eligible_room_type_ids),
        "room_request_required": sorted(list(room_request_filters.get("required", set()))),
        "room_request_forbidden": sorted(list(room_request_filters.get("forbidden", set()))),
        "room_count": len(raw_offers or []),
    }
    log = json.dumps(log_obj, ensure_ascii=False)[:2000]
    return reply, log, raw_offers
