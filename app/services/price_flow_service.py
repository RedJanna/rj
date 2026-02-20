"""app/services/price_flow_service.py

Fiyat sorgusu icin konusma state yonetimi.
State-machine bazli: ask_dates / ask_guests / ask_child_ages / ready
+ Son basarili sorgu kaydi (para birimi degisikligi icin)

v2 — 2026-02-12: Tam state-machine; dogal dil destegi; cocuk yasi akisi
v2.1 — 2026-02-12: last_query kaydi eklendi (currency re-query)
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# ============================
# State & Config
# ============================

PRICE_FLOW_FILE = Path("data/price_flows.json")
PRICE_FLOW_TIMEOUT_MINUTES = 15  # 15 dk sonra state silinir
LAST_QUERY_TIMEOUT_MINUTES = 60  # Son sorgu 60 dk gecerli (currency degisikligi icin)
LAST_SEEN_TIMEOUT_MINUTES = 180  # Son gorulen tarih/konuk bilgisi (3 saat)

class PriceFlowState:
    """Fiyat akisi durumlari"""
    IDLE = "idle"
    ASK_DATES = "ask_dates"
    ASK_GUESTS = "ask_guests"
    ASK_CHILD_AGES = "ask_child_ages"
    READY = "ready"


# ============================
# Persistence
# ============================

def _load_flows() -> Dict[str, Any]:
    if not PRICE_FLOW_FILE.exists():
        return {}
    try:
        with open(PRICE_FLOW_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_flows(data: Dict[str, Any]) -> None:
    PRICE_FLOW_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PRICE_FLOW_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ============================
# CRUD — Aktif Flow
# ============================

def get_price_flow(phone: str) -> Optional[Dict[str, Any]]:
    """Musterinin aktif fiyat flow'unu getir. Timeout olmussa None dondur."""
    if not phone:
        return None
    data = _load_flows()
    clean = phone.replace("+", "").replace(" ", "")
    flow = data.get(clean)
    if not flow:
        return None

    # last_query-only entry ise flow olarak donme
    if not flow.get("state") and not flow.get("data"):
        return None

    # Timeout kontrolu
    try:
        created_at = datetime.fromisoformat(flow["created_at"])
        if datetime.now() - created_at > timedelta(minutes=PRICE_FLOW_TIMEOUT_MINUTES):
            # last_query'yi koru
            last_query = flow.get("last_query")
            del data[clean]
            if last_query:
                data[clean] = {"last_query": last_query}
            _save_flows(data)
            print(f"⏰ Price flow timeout: {clean}")
            return None
    except Exception:
        return None

    return flow


def save_price_flow(
    phone: str,
    state: str,
    flow_data: Dict[str, Any],
) -> None:
    """Fiyat flow state'ini kaydet / guncelle."""
    if not phone:
        return
    data = _load_flows()
    clean = phone.replace("+", "").replace(" ", "")
    now_iso = datetime.now().isoformat()

    existing = data.get(clean, {})
    created = existing.get("created_at", now_iso)

    # last_query'yi koru
    last_query = existing.get("last_query")

    data[clean] = {
        "state": state,
        "data": flow_data,
        "created_at": created,
        "updated_at": now_iso,
    }
    if last_query:
        data[clean]["last_query"] = last_query

    _save_flows(data)
    print(f"💾 Price flow kaydedildi: {clean} | state={state}")


def clear_price_flow(phone: str) -> None:
    """Fiyat flow'unu temizle. last_query KORUNUR."""
    if not phone:
        return
    data = _load_flows()
    clean = phone.replace("+", "").replace(" ", "")
    if clean in data:
        last_query = data[clean].get("last_query")
        del data[clean]
        if last_query:
            data[clean] = {"last_query": last_query}
        _save_flows(data)
        print(f"🗑️ Price flow temizlendi: {clean}")


def is_waiting_for_guest_count(phone: str) -> bool:
    """Geriye uyumluluk."""
    flow = get_price_flow(phone)
    return flow is not None and flow.get("state") == PriceFlowState.ASK_GUESTS


def is_price_flow_active(phone: str) -> bool:
    """Aktif bir fiyat akisi var mi?"""
    flow = get_price_flow(phone)
    if not flow:
        return False
    state = flow.get("state", PriceFlowState.IDLE)
    return state not in (PriceFlowState.IDLE, None, "")


# ============================
# Son Basarili Sorgu (Currency Re-Query)
# ============================

def save_last_query(phone: str, query_params: Dict[str, Any]) -> None:
    """
    Basarili fiyat sorgusu sonrasi parametreleri kaydet.
    Musteri 'dolara cevir' dediginde bu bilgiler kullanilir.
    """
    if not phone:
        return
    data = _load_flows()
    clean = phone.replace("+", "").replace(" ", "")

    if clean not in data:
        data[clean] = {}

    data[clean]["last_query"] = {
        **query_params,
        "saved_at": datetime.now().isoformat(),
    }
    _save_flows(data)
    print(f"💾 Last query kaydedildi: {clean} | {query_params.get('from_date')} - {query_params.get('to_date')}")


def get_last_query(phone: str) -> Optional[Dict[str, Any]]:
    """
    Son basarili fiyat sorgusunun parametrelerini getir.
    Timeout (60dk) olmussa None dondur.
    """
    if not phone:
        return None
    data = _load_flows()
    clean = phone.replace("+", "").replace(" ", "")

    entry = data.get(clean)
    if not entry:
        return None

    last_query = entry.get("last_query")
    if not last_query:
        return None

    # Timeout kontrolu
    try:
        saved_at = datetime.fromisoformat(last_query["saved_at"])
        if datetime.now() - saved_at > timedelta(minutes=LAST_QUERY_TIMEOUT_MINUTES):
            entry.pop("last_query", None)
            if not entry.get("state") and not entry.get("data"):
                data.pop(clean, None)
            _save_flows(data)
            return None
    except Exception:
        return None

    return last_query

# ============================
# Son Gorulen Baglam (Tarih/Konuk)
# ============================

def save_last_seen_context(phone: str, context: Dict[str, Any]) -> None:
    ...

def get_last_seen_context(phone: str) -> Optional[Dict[str, Any]]:
    ...
# ============================
# Cleanup
# ============================

def cleanup_stale_price_flows() -> int:
    """Suresi gecmis price flow'lari temizle."""
    data = _load_flows()
    now = datetime.now()
    to_delete = []
    for phone, flow in data.items():
        has_valid_lq = False
        lq = flow.get("last_query")
        if lq:
            try:
                lq_time = datetime.fromisoformat(lq["saved_at"])
                has_valid_lq = (now - lq_time) <= timedelta(minutes=LAST_QUERY_TIMEOUT_MINUTES)
            except Exception:
                pass
        has_valid_ctx = False
        ctx = flow.get("last_seen_context")
        if ctx:
            try:
                ctx_time = datetime.fromisoformat(ctx["saved_at"])
                has_valid_ctx = (now - ctx_time) <= timedelta(minutes=LAST_SEEN_TIMEOUT_MINUTES)
            except Exception:
                pass
        has_valid_flow = False
        if flow.get("created_at"):
            try:
                created_at = datetime.fromisoformat(flow["created_at"])
                has_valid_flow = (now - created_at) <= timedelta(minutes=PRICE_FLOW_TIMEOUT_MINUTES)
            except Exception:
                pass

        if not has_valid_lq and not has_valid_ctx and not has_valid_flow:
            to_delete.append(phone)

    for phone in to_delete:
        del data[phone]

    if to_delete:
        _save_flows(data)
        print(f"🧹 {len(to_delete)} stale price flow temizlendi")
    return len(to_delete)
