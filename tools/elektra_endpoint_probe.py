#!/usr/bin/env python3
"""ElektraWeb endpoint probe utility.

Amaç:
- Rezervasyonla ilgili endpoint path adaylarini canli ortamda hizlica test etmek.
- 404/405 veren pathleri elemek.

Not:
- Bu script network erişimi gerektirir.
- Mutating endpointleri (create/update/cancel) varsayilan olarak test etmez.
"""

from __future__ import annotations

import argparse
import asyncio
import os
from typing import Any, Dict, List

import httpx

from app.services.elektraweb_booking_service import (
    ELEKTRA_API_BASE_URL,
    _login_get_jwt,
    _normalize_token,
    _resolve_endpoint_candidates,
)


def _headers(jwt: str) -> Dict[str, str]:
    headers = {
        "Authorization": f"Bearer {jwt}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    captcha = _normalize_token(os.getenv("ELEKTRA_X_CAPTCHA", ""))
    if captcha:
        headers["x-captcha"] = captcha
    return headers


def _url(path: str) -> str:
    return path if path.startswith("http") else f"{ELEKTRA_API_BASE_URL}{path}"


async def _probe_one(
    client: httpx.AsyncClient,
    *,
    method: str,
    endpoint: str,
    headers: Dict[str, str],
    params: Dict[str, Any] | None = None,
    json_payload: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    url = _url(endpoint)
    try:
        resp = await client.request(method.upper(), url, headers=headers, params=params, json=json_payload)
    except Exception as exc:
        return {"url": url, "status": None, "kind": "transport_error", "detail": f"{exc.__class__.__name__}: {exc}"}

    kind = "possible_match"
    if resp.status_code in (404, 405):
        kind = "not_found"
    elif resp.status_code in (401, 403):
        kind = "auth_error_or_waf"
    elif resp.status_code in (400, 422):
        kind = "validation_error_possible_match"
    elif resp.status_code >= 500:
        kind = "server_error_possible_match"
    return {"url": url, "status": resp.status_code, "kind": kind, "detail": (resp.text or "")[:220].replace("\n", " ")}


async def main() -> int:
    parser = argparse.ArgumentParser(description="Probe Elektra reservation endpoint candidates.")
    parser.add_argument("--hotel-id", default=os.getenv("ELEKTRA_HOTEL_ID", "21966"), help="Elektra hotel id")
    parser.add_argument("--timeout", type=float, default=12.0, help="HTTP timeout (sec)")
    parser.add_argument(
        "--include-mutating",
        action="store_true",
        help="create/update/cancel endpointlerini de probe et (invalid payload ile).",
    )
    args = parser.parse_args()

    api_key = _normalize_token(os.getenv("Elektra_Booking", ""))
    if not api_key:
        print("ERROR: Elektra_Booking env set degil.")
        return 2

    try:
        jwt = await _login_get_jwt(api_key, timeout_sec=max(5, int(args.timeout)))
    except Exception as exc:
        print(f"ERROR: login failed: {exc}")
        return 3

    hotel_id = str(args.hotel_id).strip()
    headers = _headers(jwt)

    operations: List[Dict[str, Any]] = [
        {
            "name": "list_reservations",
            "method": "POST",
            "endpoints": _resolve_endpoint_candidates("list_reservations", hotel_id),
            "json": {"hotel-id": int(hotel_id)},
        },
        {
            "name": "get_reservation",
            "method": "POST",
            "endpoints": _resolve_endpoint_candidates("get_reservation", hotel_id),
            "json": {"hotel-id": int(hotel_id), "reservation-id": "0"},
        },
    ]

    if args.include_mutating:
        operations.extend(
            [
                {
                    "name": "create_reservation",
                    "method": "POST",
                    "endpoints": _resolve_endpoint_candidates("create_reservation", hotel_id),
                    "json": {"hotel-id": int(hotel_id)},
                },
                {
                    "name": "update_reservation",
                    "method": "POST",
                    "endpoints": _resolve_endpoint_candidates("update_reservation", hotel_id),
                    "json": {"hotel-id": int(hotel_id), "reservation-id": "0"},
                },
                {
                    "name": "cancel_reservation",
                    "method": "POST",
                    "endpoints": _resolve_endpoint_candidates("cancel_reservation", hotel_id),
                    "json": {"hotel-id": int(hotel_id), "reservation-id": "0", "reason": "probe"},
                },
            ]
        )

    print(f"Base URL: {ELEKTRA_API_BASE_URL}")
    print(f"Hotel ID: {hotel_id}")
    print("")

    async with httpx.AsyncClient(timeout=args.timeout, follow_redirects=True) as client:
        for op in operations:
            print(f"== {op['name']} ==")
            for endpoint in op["endpoints"]:
                result = await _probe_one(
                    client,
                    method=op["method"],
                    endpoint=endpoint,
                    headers=headers,
                    json_payload=op["json"],
                )
                print(
                    f"{result['status']!s:>4} | {result['kind']:<30} | {result['url']}"
                )
            print("")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
