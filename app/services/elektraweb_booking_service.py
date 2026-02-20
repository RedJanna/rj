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
from typing import Any, Dict, List, Optional, Tuple, Union

import httpx


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
    "DELUXE": {"tr": "Deluxe (25m2)", "en": "Deluxe (25m2)", "key": "deluxe"},
    "SUPERIOR": {"tr": "Superior (30m2)", "en": "Superior (30 m2)", "key": "superior"},
    "EXCLUSIVE LAND": {"tr": "Exclusive Sokak Manzarali (40m2)", "en": "Exclusive Street View (40 m2)", "key": "exclusiveLand"},
    "EXCLUSIVE LAND VIEW": {"tr": "Exclusive Sokak Manzarali (40m2)", "en": "Exclusive Street View (40 m2)", "key": "exclusiveLand"},
    "EXCLUSIVE STREET": {"tr": "Exclusive Sokak Manzarali (40m2)", "en": "Exclusive Street View (40 m2)", "key": "exclusiveLand"},
    "EXCLUSIVE POOL": {"tr": "Exclusive Havuz Manzarali (40m2)", "en": "Exclusive Pool View (40m2)", "key": "exclusivePool"},
    "EXCLUSIVE POOL VIEW": {"tr": "Exclusive Havuz Manzarali (40m2)", "en": "Exclusive Pool View (40m2)", "key": "exclusivePool"},
    # Daha spesifik oda adlarini genel "PENTHOUSE"tan once koy.
    "PENTHOUSE LAND JAKUZILI": {"tr": "Penthouse Land - Jakuzili (25m2)", "en": "Penthouse Land with Jacuzzi (25m2)", "key": "penthouseLand"},
    "PENTHOUSE LAND JACUZZI": {"tr": "Penthouse Land - Jakuzili (25m2)", "en": "Penthouse Land with Jacuzzi (25m2)", "key": "penthouseLand"},
    "PENTHOUSE LAND": {"tr": "Penthouse Land - Jakuzili (25m2)", "en": "Penthouse Land with Jacuzzi (25m2)", "key": "penthouseLand"},
    "PENTHOUSE": {"tr": "Penthouse - Jakuzili (45m2)", "en": "Penthouse with Jacuzzi (45m2)", "key": "penthouse"},
    "PREMIUM": {"tr": "Premium - Jakuzili (45m2)", "en": "Premium (45m2)", "key": "premium"},
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
    replacements = {
        'ş': 's', 'Ş': 'S',
        'ğ': 'g', 'Ğ': 'G',
        'ü': 'u', 'Ü': 'U',
        'ö': 'o', 'Ö': 'O',
        'ı': 'i', 'İ': 'I',
        'ç': 'c', 'Ç': 'C'
    }
    result = text
    for tr_char, en_char in replacements.items():
        result = result.replace(tr_char, en_char)
    return result


# =========================
# Dogal Dil Tarih Parse
# =========================

def _get_all_months() -> Dict[str, int]:
    """Tum ay isimlerini birlestir (TR + EN + RU + normalize edilmis)"""
    all_months = {}
    all_months.update(MONTHS_TR)
    all_months.update(MONTHS_EN)
    all_months.update(MONTHS_RU)
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
        pattern = rf'(\d{{1,2}})\s*{month_normalized}\s*(?:ile|[-–—]|to|ve|and|arası|arasında|between|tarihleri)\s*(\d{{1,2}})\s*(\w+)?'
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
        pattern = rf'(\d{{1,2}})\s*[-–—]\s*(\d{{1,2}})\s*{month_normalized}'
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
        pattern = rf'(\d{{1,2}})\s*(?:ile|[-–—]|to|ve|and)\s*(\d{{1,2}})\s*{month_normalized}'
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
    if guest_phone:
        primary_guest["phone"] = str(guest_phone)
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
    if guest_phone:
        payload["payer-info"]["phone"] = str(guest_phone)
    if guest_email:
        payload["payer-info"]["email"] = str(guest_email)
        payload["contact-email"] = str(guest_email)
    if guest_phone:
        payload["contact-phone"] = str(guest_phone)
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
    
    # Pattern 1: "3 yetiskin", "2 kisi", "2 adults"
    m = re.search(r"(\d+)\s*(yetiskin|kisi|adult|people|guest|kisilik|взросл\w*|человек|гост\w*)", low)
    if m:
        try:
            return int(m.group(1))
        except:
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

    child_keywords = ["cocuk", "child", "children", "kid", "kids", "bebek", "baby", "infant"]
    has_child_context = any(k in low for k in child_keywords)
    has_month_age = bool(re.search(r"\b\d{1,2}\s*ay\w*\b", low))

    # Cocuk baglami yoksa yaslari cocuk diye varsayma
    if not has_child_context and not has_month_age:
        return ages

    # Mesajdan çocuk sayısı (örn: "2 cocuk")
    child_count: Optional[int] = None
    m_cnt = re.search(r"(\d+)\s*(?:cocuk|child|children|kid|kids|bebek|baby|infant)", low)
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

    # Pattern 3: "5 yasinda cocuk" veya "5 yas cocuk"
    m = re.search(r"(\d+)\s*yas\w*\s*(?:cocuk|child|children|kid|kids|bebek|baby|infant)", low)
    if m:
        age = int(m.group(1))
        if 0 <= age <= 16:
            ages.append(age)

    # Pattern 3.5: "9 aylik bebek" vb. -> 0 yas
    month_matches = list(re.finditer(r"(\d{1,2})\s*ay\w*", low))
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
) -> Tuple[str, bool]:
    """
    API response'unu sablona uygun formatta dondur.
    Returns: (reply_text, success)
    success=False ise handoff gerekli
    """
    
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

    # ✅ Boş liste geldiyse: handoff değil, "müsait yok" mesajı dön
    if not offers:
        if explicit_list_seen:
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

    room_prices: Dict[str, Dict[str, Optional[float]]] = {}
    currency = "EUR"

    for offer in offers:
        room_type_raw = offer.get("room-type", "")
        room_info = _normalize_room_type(room_type_raw)

        if not room_info:
            continue

        # Rate-type filtresi: Kontrat, Balayi, SPA vb. gosterme
        rate_type_name = (offer.get("rate-type") or "").strip().lower()
        if rate_type_name and rate_type_name not in _PRICE_ALLOWED_RATE_TYPES_LOWER:
            continue

        room_key = room_info["key"]
        if room_key not in room_prices:
            room_prices[room_key] = {"refundable": None, "non_refundable": None}

        # Fiyati oldugu gibi koru (musteri mesaji ile rezervasyon fiyat tutarli kalsin)
        raw_price = offer.get("discounted-price") or offer.get("price") or 0
        price = _normalize_price_value(float(raw_price))
        currency = offer.get("currency", "EUR")

        # Iade durumunu kontrol et
        cancel_info = offer.get("cancellation-penalty", {})
        is_refundable = cancel_info.get("is-refundable", False)

        if is_refundable:
            if room_prices[room_key]["refundable"] is None or price < room_prices[room_key]["refundable"]:
                room_prices[room_key]["refundable"] = price
        else:
            if room_prices[room_key]["non_refundable"] is None or price < room_prices[room_key]["non_refundable"]:
                room_prices[room_key]["non_refundable"] = price

    # Hic oda bulunamadi - HANDOFF
    if not room_prices:
        return ("", False)

    # Tarihleri formatla
    nights = _calculate_nights(from_date, to_date)
    
    # Cocuk metni
    child_text_tr = ""
    child_text_en = ""
    if child_count > 0:
        ages_txt_tr = " ve ".join(f"{a} yaş" for a in (child_ages or []))
        ages_txt_en = ", ".join(f"age {a}" for a in (child_ages or []))
        child_text_tr = f" + {child_count} çocuk ({ages_txt_tr})" if ages_txt_tr else f" + {child_count} çocuk"
        child_text_en = f" + {child_count} children ({ages_txt_en})" if ages_txt_en else f" + {child_count} children"
    
    # Sablona gore mesaj olustur
    if lang == "en":
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
            
            lines.append(f"Non refundable: {_format_price(nr_price)} {currency}" if nr_price is not None else "Non refundable: -")
            lines.append(f"Free Cancellation: {_format_price(r_price)} {currency}" if r_price is not None else "Free Cancellation: -")
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
    elif lang == "ru":
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

            room_name = room_map["en"]
            lines.append(room_name)

            nr_price = prices.get("non_refundable")
            r_price = prices.get("refundable")

            lines.append(f"Невозвратный тариф: {_format_price(nr_price)} {currency}" if nr_price is not None else "Невозвратный тариф: -")
            lines.append(f"Бесплатная отмена: {_format_price(r_price)} {currency}" if r_price is not None else "Бесплатная отмена: -")
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

    else:  # Turkish
        date_range = _format_date_range_tr(from_date, to_date)
        lines = [
            f"Otelimize göstermiş olduğunuz ilgi için teşekkür ederiz.",
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
            
            lines.append(f"İade yapılmaz: {_format_price(nr_price)} {currency}" if nr_price is not None else "İade yapılmaz: -")
            lines.append(f"Ücretsiz İptal: {_format_price(r_price)} {currency}" if r_price is not None else "Ücretsiz İptal: -")
            lines.append("")

        lines.extend([
            "Sizleri ağırlamak dileğiyle,",
            "İyi günler dileriz.",
            "",
            'Otelimize giriş ve çıkış saatlerimiz: "Giriş Saati: 14:00 - Çıkış Saati: 12:00"',
            "",
            "Not: Ücretsiz iptal seçeneği ile yapılan rezervasyonlarda girişten 5 gün öncesine kadar iptal olması halinde %100 geri ödeme alabilirsiniz.",
            "",
            "Girişten itibaren herhangi bir iptal/iade seçeneğimiz bulunmamaktadır.",
            "",
            "Rezervasyon onayı için 1 gecelik ödeme tahsil edilmektedir. Kalan ödemeyi giriş günündeki güncel döviz kuruna göre TL veya döviz olarak yapabilirsiniz."
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
    }
    lang_norm = (lang or "tr").lower()
    labels = missing_labels.get(lang_norm, missing_labels["tr"])
    missing_text = ", ".join(labels.get(item, item) for item in missing)

    if (lang or "").lower() == "en":
        if dates_found and "guest_count" in missing:
            return "Thank you! For how many guests? (adults and children with ages if any)"
        return (
            "To check availability, please provide:\n"
            f"Missing: {missing_text}"
        )
    if (lang or "").lower() == "ru":
        if dates_found and "guest_count" in missing:
            return "Спасибо! На сколько гостей планируется проживание? (взрослые и, если есть, дети с возрастами)"
        return (
            "Чтобы проверить наличие, пожалуйста, уточните:\n"
            f"Не хватает данных: {missing_text}"
        )

    if dates_found and "guest_count" in missing:
        return "Teşekkürler! Kaç kişilik konaklama olacak? (yetişkin ve varsa çocuk yaşları)"
    
    return (
        "Müsaitlik kontrolü için lütfen belirtin:\n"
        f"Eksik: {missing_text}"
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
    
    if adult is None:
        missing.append("guest_count")

    # Cocuk kelimesi var ama yas yok
    low_msg = _normalize_turkish_chars((user_message or "").lower())
    if any(k in low_msg for k in ["cocuk", "child", "children", "kid", "kids", "bebek", "baby", "infant"]) and not child_ages:
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

    reply, success = _format_price_reply(
        api_json,
        lang,
        from_date,
        to_date,
        adult,
        child_count=len(child_ages),
        child_ages=child_ages,
    )

    if not success:
        # Format hatasi veya bos response - HANDOFF
        log = json.dumps({"error": "empty_or_invalid_response", "from": from_date, "to": to_date, "adult": adult}, ensure_ascii=False)
        return "HANDOFF:FORMAT_ERROR", log, None

    # Ham offer listesini cikar (booking cache icin)
    raw_offers: Optional[List[Dict[str, Any]]] = None
    if isinstance(api_json, list):
        raw_offers = [x for x in api_json if isinstance(x, dict)]
    elif isinstance(api_json, dict):
        for key in ("data", "result", "offers", "prices"):
            if key in api_json and isinstance(api_json[key], list):
                raw_offers = [x for x in api_json[key] if isinstance(x, dict)]
                break

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
        "room_count": len(api_json) if isinstance(api_json, list) else 0,
    }
    log = json.dumps(log_obj, ensure_ascii=False)[:2000]
    return reply, log, raw_offers
