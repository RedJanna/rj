"""HotelAdvisor-style endpoint client for Elektra tenant APIs."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import httpx

from app.services.elektraweb_booking_service import (
    ElektrawebAuthError,
    ElektrawebConfigError,
    USER_AGENT,
    _normalize_token,
    _safe_snippet,
)

HOTELADVISOR_BASE_URL = (
    os.getenv("ELEKTRA_HOTELADVISOR_BASE_URL")
    or os.getenv("ELEKTRA_API_BASE_URL")
    or "https://bookingapi.elektraweb.com"
).rstrip("/")

HOTELADVISOR_LEGACY_BASE_URL = (
    os.getenv("ELEKTRA_HOTELADVISOR_LEGACY_BASE_URL")
    or "https://4001.hoteladvisor.net"
).rstrip("/")

_FORCE_LEGACY = str(os.getenv("ELEKTRA_HOTELADVISOR_FORCE_LEGACY", "")).strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

_LEGACY_ENDPOINTS = {
    ("update", "HOTEL_RES"),
    ("select", "QWEB_FOLYO_HESAP"),
    ("select", "QA_HOTEL_DEPARTMENT"),
    ("execute", "SP_WEB_PAYMENT"),
    ("function", "FN_HOTEL_EXCHANGERATES_ALL"),
}


# Endpoint catalog extracted from HAR (provided by user)
HOTELADVISOR_ENDPOINTS: Dict[str, List[str]] = {
    "select": [
        "AGENCY",
        "COUNTRY",
        "HELPDOC",
        "HOTEL",
        "HOTEL_BOARDTYPE",
        "HOTEL_FOLIOTRANS",
        "HOTEL_GUEST",
        "HOTEL_GUEST_VIP_TYPE",
        "HOTEL_RATECODE",
        "HOTEL_RATECODE_DISCOUNT",
        "HOTEL_RATETYPE",
        "HOTEL_RES",
        "HOTEL_RESMODE",
        "HOTEL_RES_ACTIONS",
        "HOTEL_ROOM",
        "HOTEL_ROOMTYPE",
        "NEWS_USER_NOTIFICATION",
        "QA_AGENCY_RESLOOKUP",
        "QA_COUNTRY_NAMECODE",
        "QA_EASYPMS_HOTELCURS",
        "QA_EASYPMS_RESDETAIL",
        "QA_HOTEL_DEPARTMENT",
        "QA_HOTEL_FOLIOROUTING",
        "QA_HOTEL_RESERVATION",
        "QA_HOTEL_RESERVATION_CHECKOUT",
        "QA_HOTEL_RESERVATION_RESERVATION",
        "QA_HOTEL_RES_GUEST",
        "QA_HOTEL_REVENUE",
        "QA_HOTEL_TASKS",
        "QA_RESDAY_RESFORM",
        "QA_ROOMCALENDAR_RES",
        "QWEB_FOLYO_HESAP",
        "QWEB_RES_CARI",
        "QWEB_RES_FAT_MISAFIR",
        "QA_ROOMTYPE_AVAILABILITY_LASTRATE",
        "VW_EASYPMS_AVAILABILITY",
        "RES",
        "RES_CCARD",
    ],
    "execute": [
        "SP_EASYPMS_FAVORITE_SCREENS",
        "SP_EASYPMS_TENANTCHANGED",
        "SP_FORECAST_DATE",
        "SP_GETROLES",
        "SP_HOTELGUEST_SENDWHATSAPPLINK",
        "SP_HOTELRESGUEST_SAVE",
        "SP_HOTEL_EVENT_CALENDAR",
        "SP_NEWS_USER_NOTIFICATION",
        "SP_PORTALV4_GETPORTAL_INSTALLMENT",
        "SP_PROFILE_SETTOKEN",
        "SP_SHOW_GRID_CUSTOM_DESIGN_FOR_USER",
        "SP_WEB_PAYMENT",
        "SP_WEB_POSTING",
    ],
    "function": [
        "FN_AGENCY_RATECODE_LOOKUP",
        "FN_EASYPMS_FOLIOBALANCE",
        "FN_HOTEL_EXCHANGERATES_ALL",
        "FN_HOTEL_RES_DYNAMICFOLIO",
        "FN_RESFIXNOTE",
        "FN_RES_NOTE",
    ],
    "insert": [
        "HOTEL_RES_ACTIONS",
        "WHATSAPP_SENT",
    ],
    "update": [
        "HOTEL_FOLIOTRANS",
        "HOTEL_RES",
        "RES_DAY",
    ],
    "delete": [
        "HOTEL_FOLIOTRANS",
    ],
    "get_config": [
        "grid.RoomFolioType.config",
        "grid.foliorouting.config",
        "grid.forecast-analysis-accomodation.config",
        "grid.forecast-analysis-arrival-departure.config",
        "grid.forecast-analysis-availability.config",
        "grid.forecast-analysis-occupancy.config",
        "grid.forecast-analysis-revenue2.config",
        "grid.forecast-substate.config",
        "grid.resccard.config",
        "grid.resnote.config",
        "log.HOTEL_RES.config",
        "record2.folio-delete-reason-entry.config",
        "record2.folio-routing.config",
        "record2.foliorouting.config",
        "record2.hotel-forecast.config",
        "record2.online-guest-application.config",
        "record2.res-card-credit-card.config",
        "record2.res-card-notes.config",
    ],
    "get_log": [
        "HOTEL_RES",
    ],
}

_KIND_TO_PREFIX = {
    "select": "/Select/{name}",
    "execute": "/Execute/{name}",
    "function": "/Function/{name}",
    "insert": "/Insert/{name}",
    "update": "/Update/{name}",
    "delete": "/Delete/{name}",
    "get_config": "/GetConfig/{name}",
    "get_log": "/GetLog/{name}",
}


def _resolve_base_url(kind: str, name: str) -> str:
    if _FORCE_LEGACY:
        return HOTELADVISOR_LEGACY_BASE_URL
    key = ((kind or "").strip().lower(), (name or "").strip())
    if key in _LEGACY_ENDPOINTS:
        return HOTELADVISOR_LEGACY_BASE_URL
    return HOTELADVISOR_BASE_URL


async def _login_get_jwt_hoteladvisor(*, base_url: str, timeout_sec: int = 15) -> str:
    api_key = _normalize_token(
        os.getenv("ELEKTRA_HOTELADVISOR_APIKEY", "") or os.getenv("Elektra_Booking", "")
    )
    if not api_key:
        raise ElektrawebConfigError(
            "Eksik config: ELEKTRA_HOTELADVISOR_APIKEY veya Elektra_Booking ortam degiskeni bos."
        )

    login_candidates = [
        f"{base_url}/Login",
        f"{base_url}/login",
    ]
    alt_base = (os.getenv("ELEKTRA_API_BASE_URL") or "").strip().rstrip("/")
    if alt_base and alt_base != base_url:
        login_candidates.extend([f"{alt_base}/Login", f"{alt_base}/login"])
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }
    last_err = ""
    async with httpx.AsyncClient(timeout=timeout_sec, follow_redirects=True) as client:
        for url in login_candidates:
            try:
                # HAR'da HotelAdvisor login akisi Action=Login semantigine gore calisiyor.
                resp = await client.post(url, headers=headers, json={"Action": "Login"})
            except Exception as exc:
                last_err = f"{url} transport error: {exc}"
                continue
            if resp.status_code >= 400:
                body = _safe_snippet(resp.text, 800)
                last_err = f"{url} HTTP {resp.status_code} | body={body}"
                continue
            try:
                data = resp.json()
            except Exception:
                body = _safe_snippet(resp.text, 800)
                last_err = f"{url} bad json | body={body}"
                continue

            if isinstance(data, dict):
                for key in ("jwt", "token", "loginToken", "LoginToken"):
                    tok = data.get(key)
                    if isinstance(tok, str) and tok.strip():
                        return tok.strip()
            last_err = f"{url} login token missing | response={json.dumps(data, ensure_ascii=False)[:800]}"

    raise ElektrawebAuthError(f"/login failed for all candidates: {last_err}")


def _build_url(path: str, *, base_url: str) -> str:
    cleaned = (path or "").strip()
    if cleaned.startswith("http://") or cleaned.startswith("https://"):
        return cleaned
    if not cleaned.startswith("/"):
        cleaned = f"/{cleaned}"
    return f"{base_url}{cleaned}"


def get_hoteladvisor_path(kind: str, name: str) -> str:
    k = (kind or "").strip().lower()
    n = (name or "").strip()
    if k not in _KIND_TO_PREFIX:
        raise ValueError(f"Unsupported endpoint kind: {kind}")
    if not n:
        raise ValueError("Endpoint name cannot be empty")
    if n not in HOTELADVISOR_ENDPOINTS.get(k, []):
        raise ValueError(f"Unknown endpoint name for kind={k}: {n}")
    return _KIND_TO_PREFIX[k].format(name=n)


def list_hoteladvisor_endpoints(kind: Optional[str] = None) -> Dict[str, List[str]]:
    if kind is None:
        return {k: list(v) for k, v in HOTELADVISOR_ENDPOINTS.items()}
    k = (kind or "").strip().lower()
    if k not in HOTELADVISOR_ENDPOINTS:
        raise ValueError(f"Unsupported endpoint kind: {kind}")
    return {k: list(HOTELADVISOR_ENDPOINTS[k])}


async def _post_hoteladvisor(
    *,
    kind: str,
    name: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout_sec: int = 20,
) -> Dict[str, Any]:
    resolved_base = _resolve_base_url(kind, name)
    jwt = await _login_get_jwt_hoteladvisor(base_url=resolved_base, timeout_sec=timeout_sec)
    path = get_hoteladvisor_path(kind, name)
    url = _build_url(path, base_url=resolved_base)

    action = (kind or "").strip().capitalize()
    request_body: Dict[str, Any] = {
        "Action": action,
        "Object": str(name),
        "LoginToken": jwt,
    }
    raw_payload = payload or {}
    if action in ("Function", "Execute"):
        if isinstance(raw_payload, dict) and "Parameters" in raw_payload:
            request_body.update(raw_payload)
        else:
            request_body["Parameters"] = raw_payload
    else:
        request_body.update(raw_payload)

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }

    async with httpx.AsyncClient(timeout=timeout_sec, follow_redirects=True) as client:
        resp = await client.post(url, headers=headers, json=request_body)

    body = _safe_snippet(resp.text, 800)
    if resp.status_code >= 400:
        raise ElektrawebAuthError(
            f"{kind}/{name} failed: endpoint={url} HTTP {resp.status_code} | body={body}"
        )

    try:
        data = resp.json()
    except Exception:
        raise ElektrawebAuthError(f"{kind}/{name} bad json: endpoint={url} | body={body}")

    if isinstance(data, dict) and data.get("success") is False:
        snippet = json.dumps(data, ensure_ascii=False)[:800]
        raise ElektrawebAuthError(
            f"{kind}/{name} returned success:false: endpoint={url} | response={snippet}"
        )

    return data if isinstance(data, dict) else {"data": data}


async def hoteladvisor_select(name: str, payload: Optional[Dict[str, Any]] = None, *, timeout_sec: int = 20) -> Dict[str, Any]:
    return await _post_hoteladvisor(kind="select", name=name, payload=payload, timeout_sec=timeout_sec)


async def hoteladvisor_execute(name: str, payload: Optional[Dict[str, Any]] = None, *, timeout_sec: int = 20) -> Dict[str, Any]:
    return await _post_hoteladvisor(kind="execute", name=name, payload=payload, timeout_sec=timeout_sec)


async def hoteladvisor_function(name: str, payload: Optional[Dict[str, Any]] = None, *, timeout_sec: int = 20) -> Dict[str, Any]:
    return await _post_hoteladvisor(kind="function", name=name, payload=payload, timeout_sec=timeout_sec)


async def hoteladvisor_update(name: str, payload: Optional[Dict[str, Any]] = None, *, timeout_sec: int = 20) -> Dict[str, Any]:
    return await _post_hoteladvisor(kind="update", name=name, payload=payload, timeout_sec=timeout_sec)


async def get_reservation_guests(payload: Dict[str, Any], *, timeout_sec: int = 20) -> Dict[str, Any]:
    """Read reservation guest records via Select/QA_HOTEL_RES_GUEST."""
    return await hoteladvisor_select("QA_HOTEL_RES_GUEST", payload=payload, timeout_sec=timeout_sec)


async def save_reservation_guest(payload: Dict[str, Any], *, timeout_sec: int = 20) -> Dict[str, Any]:
    """Persist guest records via Execute/SP_HOTELRESGUEST_SAVE."""
    return await hoteladvisor_execute("SP_HOTELRESGUEST_SAVE", payload=payload, timeout_sec=timeout_sec)


async def get_portal_installments(payload: Dict[str, Any], *, timeout_sec: int = 20) -> Dict[str, Any]:
    """Fetch installment options via Execute/SP_PORTALV4_GETPORTAL_INSTALLMENT."""
    return await hoteladvisor_execute(
        "SP_PORTALV4_GETPORTAL_INSTALLMENT",
        payload=payload,
        timeout_sec=timeout_sec,
    )
