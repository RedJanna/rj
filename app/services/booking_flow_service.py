"""app/services/booking_flow_service.py

Otel rezervasyon (booking) akis yonetimi.
- Flow state: JSON dosyasi (data/booking_flows.json)
- Offer cache: Fiyat sorgusu sonrasi ham offer'lari saklar
- SQLite CRUD: Onay bekleyen / onaylanan / reddedilen otel rezervasyonlari

v1 - 2026-02-15
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.flows.flow_contract import FlowContext, FlowResult
from app.services.state_store_service import JsonStateRepository, resolve_data_file


# ============================
# Config
# ============================

BOOKING_FLOW_FILE = resolve_data_file("booking_flows.json", env_var="KASSANDRA_BOOKING_FLOW_FILE")
_BOOKING_FLOW_STORE = JsonStateRepository(BOOKING_FLOW_FILE)
BOOKING_FLOW_TIMEOUT_MINUTES = 30
OFFER_CACHE_TIMEOUT_MINUTES = 60
HOTEL_BOOKINGS_DB = resolve_data_file("hotel_bookings.db", env_var="KASSANDRA_HOTEL_BOOKINGS_DB")


# ============================
# States & Status
# ============================

class BookingFlowState:
    IDLE = "idle"
    SELECT_ROOM = "select_room"
    ASK_PRICE_TYPE = "ask_price_type"      # Fiyat tipi: Ücretsiz İptal / İptal Edilemez
    ASK_NAME = "ask_name"
    ASK_PHONE = "ask_phone"
    ASK_EMAIL = "ask_email"
    ASK_SPECIAL = "ask_special"
    CONFIRM = "confirm"
    PENDING_APPROVAL = "pending_approval"
    GROUP_COLLECT_TEMPLATE = "group_collect_template"
    GROUP_SELECT_TEMPLATE = "group_select_template"


class BookingStatus:
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    ELEKTRA_CREATED = "elektra_created"
    ELEKTRA_FAILED = "elektra_failed"
    CANCELLED = "cancelled"


# ============================
# Flow Persistence (JSON)
# ============================

def _load_booking_flows() -> Dict[str, Any]:
    return _BOOKING_FLOW_STORE.load_dict()


def _save_booking_flows(data: Dict[str, Any]) -> None:
    _BOOKING_FLOW_STORE.save_dict(data)


def get_booking_flow(phone: str) -> Optional[Dict[str, Any]]:
    """Musterinin aktif booking flow'unu getir. Timeout olmussa None dondur."""
    if not phone:
        return None
    data = _load_booking_flows()
    clean = phone.replace("+", "").replace(" ", "")
    flow = data.get(clean)
    if not flow:
        return None

    # cached_offers-only entry ise flow olarak donme
    if not flow.get("state") and not flow.get("data"):
        return None

    # Timeout kontrolu
    try:
        updated = flow.get("updated_at") or flow.get("created_at")
        if updated:
            ts = datetime.fromisoformat(updated)
            if datetime.now() - ts > timedelta(minutes=BOOKING_FLOW_TIMEOUT_MINUTES):
                # Offer cache'i koru
                cached = flow.get("cached_offers")
                del data[clean]
                if cached:
                    data[clean] = {"cached_offers": cached}
                _save_booking_flows(data)
                print(f"[BOOKING] Flow timeout: {clean}")
                return None
    except Exception:
        return None

    return flow


def save_booking_flow(phone: str, state: str, flow_data: Dict[str, Any]) -> None:
    """Booking flow state'ini kaydet / guncelle."""
    if not phone:
        return
    data = _load_booking_flows()
    clean = phone.replace("+", "").replace(" ", "")
    now = datetime.now().isoformat()

    existing = data.get(clean, {})
    cached = existing.get("cached_offers")

    data[clean] = {
        "state": state,
        "data": flow_data,
        "created_at": existing.get("created_at", now),
        "updated_at": now,
    }
    if cached:
        data[clean]["cached_offers"] = cached

    _save_booking_flows(data)


def clear_booking_flow(phone: str) -> None:
    """Booking flow'u temizle. Offer cache'i koru."""
    if not phone:
        return
    data = _load_booking_flows()
    clean = phone.replace("+", "").replace(" ", "")
    existing = data.get(clean)
    if existing:
        cached = existing.get("cached_offers")
        del data[clean]
        if cached:
            data[clean] = {"cached_offers": cached}
        _save_booking_flows(data)


def purge_booking_flow_data(phone: str) -> bool:
    """Telefon icin booking flow kaydini (state + cache + payment context) tamamen sil."""
    if not phone:
        return False
    data = _load_booking_flows()
    clean = phone.replace("+", "").replace(" ", "")
    if clean not in data:
        return False
    del data[clean]
    _save_booking_flows(data)
    return True


def save_payment_context(phone: str, context: Dict[str, Any]) -> None:
    """Odeme para birimi/tutar secimi icin kisa sureli context sakla."""
    if not phone:
        return
    data = _load_booking_flows()
    clean = phone.replace("+", "").replace(" ", "")
    existing = data.get(clean, {})
    existing["payment_context"] = {
        **(context or {}),
        "updated_at": datetime.now().isoformat(),
    }
    data[clean] = existing
    _save_booking_flows(data)


def get_payment_context(phone: str) -> Optional[Dict[str, Any]]:
    """Odeme context'ini getir (suresi dolmussa temizler)."""
    if not phone:
        return None
    data = _load_booking_flows()
    clean = phone.replace("+", "").replace(" ", "")
    existing = data.get(clean, {})
    ctx = existing.get("payment_context")
    if not ctx:
        return None
    try:
        updated = datetime.fromisoformat(ctx.get("updated_at", ""))
        if datetime.now() - updated > timedelta(minutes=10):
            existing.pop("payment_context", None)
            data[clean] = existing
            _save_booking_flows(data)
            return None
    except Exception:
        return None
    return ctx


def clear_payment_context(phone: str) -> None:
    if not phone:
        return
    data = _load_booking_flows()
    clean = phone.replace("+", "").replace(" ", "")
    existing = data.get(clean)
    if not existing:
        return
    if "payment_context" in existing:
        existing.pop("payment_context", None)
        data[clean] = existing
        _save_booking_flows(data)


def is_booking_flow_active(phone: str) -> bool:
    """Aktif booking flow var mi?"""
    flow = get_booking_flow(phone)
    return flow is not None and flow.get("state") not in (None, BookingFlowState.IDLE)


# ============================
# Offer Cache
# ============================

def save_price_offers(phone: str, offers: List[Dict[str, Any]], query_params: Dict[str, Any]) -> None:
    """Fiyat sorgusu sonrasi ham offer'lari cache'le."""
    if not phone or not offers:
        return
    data = _load_booking_flows()
    clean = phone.replace("+", "").replace(" ", "")

    existing = data.get(clean, {})
    existing["cached_offers"] = {
        "saved_at": datetime.now().isoformat(),
        "query_params": query_params,
        "offers": offers,
    }
    data[clean] = existing
    _save_booking_flows(data)
    print(f"[BOOKING] {len(offers)} offer cached for {clean}")


def get_price_offers(phone: str) -> Optional[Dict[str, Any]]:
    """Cache'deki offer'lari getir. Expired ise None dondur."""
    if not phone:
        return None
    data = _load_booking_flows()
    clean = phone.replace("+", "").replace(" ", "")
    entry = data.get(clean, {})
    cached = entry.get("cached_offers")
    if not cached:
        return None

    # Timeout kontrolu
    try:
        saved_at = datetime.fromisoformat(cached["saved_at"])
        if datetime.now() - saved_at > timedelta(minutes=OFFER_CACHE_TIMEOUT_MINUTES):
            return None
    except Exception:
        return None

    return cached


# ============================
# Room Selection Helpers
# ============================

# Oda isim haritasi (API -> goruntu)
ROOM_TYPE_MAP = {
    "DELUXE": {"tr": "Deluxe (25m2)", "en": "Deluxe (25m2)", "key": "deluxe"},
    "SUPERIOR": {"tr": "Superior (30m2)", "en": "Superior (30m2)", "key": "superior"},
    "EXCLUSIVE LAND": {"tr": "Exclusive Sokak Manzarali (40m2)", "en": "Exclusive Street View (40m2)", "key": "exclusiveLand"},
    "EXCLUSIVE LAND VIEW": {"tr": "Exclusive Sokak Manzarali (40m2)", "en": "Exclusive Street View (40m2)", "key": "exclusiveLand"},
    "EXCLUSIVE STREET": {"tr": "Exclusive Sokak Manzarali (40m2)", "en": "Exclusive Street View (40m2)", "key": "exclusiveLand"},
    "EXCLUSIVE POOL": {"tr": "Exclusive Havuz Manzarali (40m2)", "en": "Exclusive Pool View (40m2)", "key": "exclusivePool"},
    "EXCLUSIVE POOL VIEW": {"tr": "Exclusive Havuz Manzarali (40m2)", "en": "Exclusive Pool View (40m2)", "key": "exclusivePool"},
    # Daha spesifik oda adlarini genel "PENTHOUSE"tan once koy.
    "PENTHOUSE LAND JAKUZILI": {"tr": "Penthouse Land - Jakuzili (25m2)", "en": "Penthouse Land with Jacuzzi (25m2)", "key": "penthouseLand"},
    "PENTHOUSE LAND JACUZZI": {"tr": "Penthouse Land - Jakuzili (25m2)", "en": "Penthouse Land with Jacuzzi (25m2)", "key": "penthouseLand"},
    "PENTHOUSE LAND": {"tr": "Penthouse Land - Jakuzili (25m2)", "en": "Penthouse Land with Jacuzzi (25m2)", "key": "penthouseLand"},
    "PENTHOUSE": {"tr": "Penthouse - Jakuzili (45m2)", "en": "Penthouse with Jacuzzi (45m2)", "key": "penthouse"},
    "PREMIUM": {"tr": "Premium - Jakuzili (45m2)", "en": "Premium (45m2)", "key": "premium"},
}

ROOM_ORDER = ["deluxe", "superior", "exclusiveLand", "exclusivePool", "penthouseLand", "penthouse", "premium"]


def _normalize_price_value(value: float) -> float:
    """Musteriye gosterilen fiyatla rezervasyon fiyatinin birebir tutarli kalmasi icin yuvarlama yapma."""
    return float(value)


def _normalize_room_type(api_room_type: str) -> Optional[Dict[str, str]]:
    """API'den gelen oda tipini toleransli sekilde map et."""
    if not api_room_type:
        return None
    upper = api_room_type.strip().upper()
    if upper in ROOM_TYPE_MAP:
        return ROOM_TYPE_MAP[upper]
    for key, val in ROOM_TYPE_MAP.items():
        if key in upper or upper in key:
            return val
    return None


# Musteriye sunulacak rate-type'lar.
# "Kontrat", "Balayi", "SPA Paket", "Yasli Paketi" gibi ozel rate-type'lar
# musteri seciminde GOSTERILMEZ; sadece standart fiyat kanallarini sunuyoruz.
# ENV ile override edilebilir: ELEKTRA_ALLOWED_RATE_TYPES="İptal Edilemez,Ücretsiz İptal,Esnek Fiyat"
import os as _os
_ALLOWED_RATE_TYPES_RAW = _os.getenv("ELEKTRA_ALLOWED_RATE_TYPES", "").strip()
ALLOWED_RATE_TYPES: Optional[set] = None
if _ALLOWED_RATE_TYPES_RAW:
    ALLOWED_RATE_TYPES = {x.strip().lower() for x in _ALLOWED_RATE_TYPES_RAW.split(",") if x.strip()}
else:
    # Varsayilan: sadece standart musteri rate-type'lari
    ALLOWED_RATE_TYPES = {
        "iptal edilemez", "İptal edilemez",
        "ucretsiz iptal", "ücretsiz iptal", "ücretsiz İptal",
    }
# Case-insensitive set
ALLOWED_RATE_TYPES = {x.lower() for x in ALLOWED_RATE_TYPES} if ALLOWED_RATE_TYPES else None


def _is_allowed_rate_type(offer: Dict) -> bool:
    """Offer'in rate-type'i musteriye sunulabilir mi?"""
    if ALLOWED_RATE_TYPES is None:
        return True  # Filtre yoksa hepsini goster
    rate_type = (offer.get("rate-type") or "").strip().lower()
    if not rate_type:
        return True  # rate-type bilgisi yoksa goster (guvenli varsayim)
    return rate_type in ALLOWED_RATE_TYPES


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
    """Offer rezervasyona/müşteriye sunuma uygun mu?"""
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
        "availability", "quota", "remaining",
    )
    for key in count_keys:
        iv = _to_int_or_none(offer.get(key))
        if iv is not None and iv <= 0:
            return False

    status = str(offer.get("status") or offer.get("availability-status") or "").strip().lower()
    if status in {"soldout", "sold_out", "full", "closed", "unavailable", "not_available", "pasif"}:
        return False

    return True


def get_available_rooms_from_offers(offers: List[Dict], lang: str = "tr") -> List[Dict]:
    """Offer listesinden secim yapilabilir oda listesi cikar.
    Her oda tipi x iade durumu icin bir secenek olusturur.

    ONEMLI: Sadece musteriye sunulabilir rate-type'lar dahil edilir.
    "Kontrat", "Balayi", "SPA Paket", "Yasli Paketi" gibi ozel rate-type'lar filtrelenir.
    """
    room_map: Dict[str, Dict[str, Any]] = {}

    for offer in offers:
        room_type_raw = offer.get("room-type", "")
        room_info = _normalize_room_type(room_type_raw)
        if not room_info:
            continue

        # Müsait olmayan/satışa kapalı offer'ları dahil etme
        if not _is_offer_bookable(offer):
            continue

        # Rate-type filtresi: sadece izin verilen rate-type'lari dahil et
        if not _is_allowed_rate_type(offer):
            continue

        room_key = room_info["key"]
        cancel_info = offer.get("cancellation-penalty", {})
        is_refundable = cancel_info.get("is-refundable", False)
        refund_key = "refundable" if is_refundable else "non_refundable"
        combo_key = f"{room_key}_{refund_key}"

        raw_price = offer.get("discounted-price") or offer.get("price") or 0
        price = _normalize_price_value(float(raw_price))
        currency = offer.get("currency", "EUR")

        if combo_key not in room_map or price < room_map[combo_key]["price"]:
            room_map[combo_key] = {
                "combo_key": combo_key,
                "room_key": room_key,
                "room_type": room_type_raw,
                "room_display": room_info.get(lang, room_info.get("tr", room_type_raw)),
                "is_refundable": is_refundable,
                "price": price,
                "currency": currency,
                "offer": offer,  # tam offer objesi (ID'ler dahil)
            }

    # Sirala: room_order'a gore, sonra refundable durumuna gore
    result = []
    for room_key in ROOM_ORDER:
        for refund_key in ["non_refundable", "refundable"]:
            combo = f"{room_key}_{refund_key}"
            if combo in room_map:
                result.append(room_map[combo])

    return result


def find_offer_by_selection(rooms: List[Dict], selection_index: int) -> Optional[Dict]:
    """Numara ile secim."""
    if 1 <= selection_index <= len(rooms):
        return rooms[selection_index - 1]
    return None


# ============================
# SQLite CRUD
# ============================

def init_hotel_bookings_db() -> None:
    """Hotel bookings DB'yi olustur."""
    HOTEL_BOOKINGS_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(HOTEL_BOOKINGS_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hotel_bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_phone TEXT NOT NULL,
            guest_first_name TEXT NOT NULL,
            guest_last_name TEXT NOT NULL,
            guest_title_id INTEGER DEFAULT 1,
            hotel_id INTEGER NOT NULL,
            check_in TEXT NOT NULL,
            check_out TEXT NOT NULL,
            nights INTEGER NOT NULL,
            adult_count INTEGER NOT NULL,
            child_ages TEXT,
            room_type TEXT NOT NULL,
            room_type_display TEXT,
            room_type_id INTEGER NOT NULL,
            board_type_id INTEGER NOT NULL,
            rate_type_id INTEGER NOT NULL,
            rate_code_id INTEGER NOT NULL,
            price_agency_id INTEGER NOT NULL,
            currency_id INTEGER NOT NULL,
            currency TEXT NOT NULL,
            total_price REAL NOT NULL,
            discounted_price REAL,
            is_refundable INTEGER NOT NULL DEFAULT 0,
            special_requests TEXT,
            guest_phone TEXT,
            guest_email TEXT,
            status TEXT NOT NULL DEFAULT 'pending_approval',
            elektra_reservation_id TEXT,
            elektra_response TEXT,
            admin_notes TEXT,
            approved_by TEXT,
            approved_at TEXT,
            rejected_by TEXT,
            rejected_at TEXT,
            rejection_reason TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT,
            lang TEXT DEFAULT 'tr',
            booking_context_id TEXT,
            is_test INTEGER DEFAULT 0
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hb_phone ON hotel_bookings(customer_phone)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hb_status ON hotel_bookings(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hb_checkin ON hotel_bookings(check_in)")

    # Migration: guest_phone ve guest_email kolonlarini ekle (mevcut DB'ler icin)
    try:
        conn.execute("ALTER TABLE hotel_bookings ADD COLUMN guest_phone TEXT")
    except Exception:
        pass  # Kolon zaten varsa hata verir, ignore et
    try:
        conn.execute("ALTER TABLE hotel_bookings ADD COLUMN guest_email TEXT")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE hotel_bookings ADD COLUMN booking_context_id TEXT")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE hotel_bookings ADD COLUMN is_test INTEGER DEFAULT 0")
    except Exception:
        pass

    # Kolon migration'lari tamamlandiktan sonra context index'i olustur.
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hb_context ON hotel_bookings(booking_context_id)")

    conn.commit()
    conn.close()
    print("[BOOKING] hotel_bookings DB initialized")


def create_hotel_booking(booking_data: Dict[str, Any]) -> Dict[str, Any]:
    """Yeni hotel booking olustur. Returns dict with ID."""
    now = datetime.now().isoformat()
    conn = sqlite3.connect(str(HOTEL_BOOKINGS_DB))
    cursor = conn.cursor()
    context_id = str(booking_data.get("booking_context_id") or "").strip()
    if not context_id:
        seed = f"{booking_data.get('customer_phone','')}|{booking_data.get('check_in','')}|{booking_data.get('check_out','')}|{now}"
        context_id = f"CTX-{hashlib.sha1(seed.encode('utf-8')).hexdigest()[:8].upper()}"
    cursor.execute("""
        INSERT INTO hotel_bookings (
            customer_phone, guest_first_name, guest_last_name, guest_title_id,
            hotel_id, check_in, check_out, nights,
            adult_count, child_ages,
            room_type, room_type_display,
            room_type_id, board_type_id, rate_type_id, rate_code_id,
            price_agency_id, currency_id, currency,
            total_price, discounted_price, is_refundable,
            special_requests, guest_phone, guest_email,
            status, created_at, lang, booking_context_id, is_test
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        booking_data.get("customer_phone", ""),
        booking_data.get("guest_first_name", ""),
        booking_data.get("guest_last_name", ""),
        booking_data.get("guest_title_id", 1),
        booking_data.get("hotel_id", 0),
        booking_data.get("check_in", ""),
        booking_data.get("check_out", ""),
        booking_data.get("nights", 0),
        booking_data.get("adult_count", 0),
        json.dumps(booking_data.get("child_ages", []), ensure_ascii=False),
        booking_data.get("room_type", ""),
        booking_data.get("room_type_display", ""),
        booking_data.get("room_type_id", 0),
        booking_data.get("board_type_id", 0),
        booking_data.get("rate_type_id", 0),
        booking_data.get("rate_code_id", 0),
        booking_data.get("price_agency_id", 0),
        booking_data.get("currency_id", 0),
        booking_data.get("currency", "EUR"),
        booking_data.get("total_price", 0),
        booking_data.get("discounted_price"),
        1 if booking_data.get("is_refundable") else 0,
        booking_data.get("special_requests", ""),
        booking_data.get("guest_phone", ""),
        booking_data.get("guest_email", ""),
        BookingStatus.PENDING_APPROVAL,
        now,
        booking_data.get("lang", "tr"),
        context_id,
        1 if booking_data.get("is_test") else 0,
    ))
    booking_id = cursor.lastrowid
    conn.commit()
    conn.close()

    result = dict(booking_data)
    result["id"] = booking_id
    result["status"] = BookingStatus.PENDING_APPROVAL
    result["created_at"] = now
    result["booking_context_id"] = context_id
    return result


def get_hotel_booking(booking_id: int) -> Optional[Dict[str, Any]]:
    """Tek bir booking getir."""
    conn = sqlite3.connect(str(HOTEL_BOOKINGS_DB))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hotel_bookings WHERE id = ?", (booking_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def _table_has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    try:
        cursor = conn.execute(f"PRAGMA table_info({table})")
        for row in cursor.fetchall():
            # row: cid, name, type, notnull, dflt_value, pk
            if str(row[1]).strip().lower() == str(column).strip().lower():
                return True
    except Exception:
        return False
    return False


def get_latest_booking_by_phone(phone: str, *, include_test: bool = False) -> Optional[Dict[str, Any]]:
    """Telefonla en son olusturulan booking'i getir (elektra_created status'u oncelikli)."""
    clean = re.sub(r'\D', '', phone or "")
    if not clean:
        return None
    conn = sqlite3.connect(str(HOTEL_BOOKINGS_DB))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    has_is_test = _table_has_column(conn, "hotel_bookings", "is_test")
    # Oncelik: elektra_created > pending_approval > diger
    sql = """
        SELECT * FROM hotel_bookings
        WHERE customer_phone LIKE ?
    """
    if (not include_test) and has_is_test:
        sql += " AND COALESCE(is_test, 0) = 0 "
    sql += """
        ORDER BY
            CASE status
                WHEN 'elektra_created' THEN 1
                WHEN 'pending_approval' THEN 2
                ELSE 3
            END,
            id DESC
        LIMIT 1
    """
    cursor.execute(sql, (f"%{clean[-10:]}%",))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_booking_by_context_id(context_id: str) -> Optional[Dict[str, Any]]:
    ctx = (context_id or "").strip()
    if not ctx:
        return None
    conn = sqlite3.connect(str(HOTEL_BOOKINGS_DB))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM hotel_bookings WHERE booking_context_id = ? ORDER BY id DESC LIMIT 1",
        (ctx,),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_active_bookings_by_phone(
    phone: str,
    *,
    max_hours: int = 48,
    include_test: bool = False,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    clean = re.sub(r"\D", "", phone or "")
    if not clean:
        return []
    conn = sqlite3.connect(str(HOTEL_BOOKINGS_DB))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    has_is_test = _table_has_column(conn, "hotel_bookings", "is_test")
    sql = """
        SELECT * FROM hotel_bookings
        WHERE customer_phone LIKE ?
          AND status IN ('pending_approval', 'elektra_created')
    """
    if (not include_test) and has_is_test:
        sql += " AND COALESCE(is_test, 0) = 0 "
    sql += " ORDER BY COALESCE(updated_at, created_at) DESC LIMIT ? "
    cursor.execute(sql, (f"%{clean[-10:]}%", int(limit)))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    now = datetime.now()
    today = now.date()
    out: List[Dict[str, Any]] = []
    for row in rows:
        ts_raw = row.get("updated_at") or row.get("created_at")
        try:
            ts = datetime.fromisoformat(str(ts_raw))
        except Exception:
            continue
        if now - ts > timedelta(hours=max_hours):
            continue
        check_in_raw = str(row.get("check_in") or "").strip()
        check_out_raw = str(row.get("check_out") or "").strip()
        try:
            check_in_date = datetime.fromisoformat(check_in_raw).date()
            check_out_date = datetime.fromisoformat(check_out_raw).date()
        except Exception:
            continue
        # "Aktif rezervasyon": misafir halen konaklamada (check-in yapilmis, check-out olmamis).
        if check_in_date <= today <= check_out_date:
            out.append(row)
    return out


def archive_and_delete_bookings_by_phone(phone: str) -> int:
    clean = re.sub(r"\D", "", phone or "")
    if not clean:
        return 0
    conn = sqlite3.connect(str(HOTEL_BOOKINGS_DB))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hotel_bookings_archive AS
        SELECT * FROM hotel_bookings WHERE 1=0
    """)
    cursor.execute(
        "INSERT INTO hotel_bookings_archive SELECT * FROM hotel_bookings WHERE customer_phone LIKE ?",
        (f"%{clean[-10:]}%",),
    )
    cursor.execute(
        "DELETE FROM hotel_bookings WHERE customer_phone LIKE ?",
        (f"%{clean[-10:]}%",),
    )
    deleted = cursor.rowcount if cursor.rowcount is not None else 0
    conn.commit()
    conn.close()
    return max(int(deleted), 0)


def update_hotel_booking_status(booking_id: int, status: str, **kwargs) -> None:
    """Booking status guncelle + ekstra alanlar."""
    now = datetime.now().isoformat()
    conn = sqlite3.connect(str(HOTEL_BOOKINGS_DB))

    sets = ["status = ?", "updated_at = ?"]
    vals: list = [status, now]

    for key, val in kwargs.items():
        sets.append(f"{key} = ?")
        vals.append(val)

    vals.append(booking_id)
    sql = f"UPDATE hotel_bookings SET {', '.join(sets)} WHERE id = ?"
    conn.execute(sql, vals)
    conn.commit()
    conn.close()


def get_pending_hotel_bookings() -> List[Dict[str, Any]]:
    """Onay bekleyen tum bookingleri getir."""
    conn = sqlite3.connect(str(HOTEL_BOOKINGS_DB))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM hotel_bookings WHERE status = ? ORDER BY created_at DESC",
        (BookingStatus.PENDING_APPROVAL,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_hotel_bookings(limit: int = 50) -> List[Dict[str, Any]]:
    """Tum bookingleri getir (son limit kadar)."""
    conn = sqlite3.connect(str(HOTEL_BOOKINGS_DB))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM hotel_bookings ORDER BY created_at DESC LIMIT ?",
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_hotel_booking_stats() -> Dict[str, int]:
    """Booking istatistikleri."""
    conn = sqlite3.connect(str(HOTEL_BOOKINGS_DB))
    cursor = conn.cursor()
    cursor.execute("SELECT status, COUNT(*) FROM hotel_bookings GROUP BY status")
    rows = cursor.fetchall()
    conn.close()
    stats = {row[0]: row[1] for row in rows}
    stats["total"] = sum(stats.values())
    return stats


# ============================
# Cleanup
# ============================

def cleanup_stale_booking_flows(max_age_minutes: int = 30) -> int:
    """Eski booking flow'lari temizle."""
    data = _load_booking_flows()
    now = datetime.now()
    to_delete = []

    for phone, flow in data.items():
        if not flow.get("state"):
            # cached_offers-only, buna dokunma (kendi timeout'u var)
            continue
        updated = flow.get("updated_at") or flow.get("created_at")
        if not updated:
            to_delete.append(phone)
            continue
        try:
            ts = datetime.fromisoformat(updated)
            if now - ts > timedelta(minutes=max_age_minutes):
                to_delete.append(phone)
        except Exception:
            to_delete.append(phone)

    for phone in to_delete:
        cached = data[phone].get("cached_offers")
        del data[phone]
        if cached:
            data[phone] = {"cached_offers": cached}

    if to_delete:
        _save_booking_flows(data)
        print(f"[BOOKING] Cleaned {len(to_delete)} stale flows")

    return len(to_delete)


class BookingFlowAdapter:
    """Minimal orchestrator adapter for booking flow contract."""

    flow_name = "booking"

    def can_handle(self, context: FlowContext) -> bool:
        flow_state = (context.state or {}).get(self.flow_name) or {}
        current_state = flow_state.get("state")
        if current_state and current_state != BookingFlowState.IDLE:
            return True
        msg = (context.message or "").lower()
        keywords = ("rezervasyon", "reservation", "book", "booking", "oda", "room")
        return any(k in msg for k in keywords)

    def handle(self, context: FlowContext) -> FlowResult:
        user_id = (context.user_id or "").strip()
        if not user_id:
            return FlowResult(
                reply_messages=[],
                next_state=context.state or {},
                side_effects=[],
                handoff={"reason": "missing_user_id", "target": "human"},
            )

        flow = get_booking_flow(user_id) or {}
        state_name = flow.get("state") or BookingFlowState.SELECT_ROOM
        data = flow.get("data") or {}
        if not flow:
            save_booking_flow(user_id, state_name, data)

        next_state = dict(context.state or {})
        next_state[self.flow_name] = {"state": state_name, "data": data}
        return FlowResult(
            reply_messages=[],
            next_state=next_state,
            side_effects=[{"type": "state_update", "flow": self.flow_name}],
            handoff=None,
        )
