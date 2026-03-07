"""Admin monitoring and test routes extracted from legacy monolith."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Dict, List

import platform
import psutil
from fastapi import APIRouter


def build_admin_monitoring_router(
    bot_start_time: datetime,
    openai_client: Any,
    get_openai_model_fn: Callable[[], str],
    whatsapp_phone_id: str,
    whatsapp_token: str,
    error_logs: List[Dict[str, Any]],
    detect_language_fn: Callable[[str], str],
    get_openai_response_fn: Callable[[str, str], Awaitable[str]],
) -> APIRouter:
    router = APIRouter(tags=["admin-monitoring"])

    @router.get("/admin/health")
    async def get_system_health():
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            ram_percent = memory.percent
            ram_used_gb = round(memory.used / (1024**3), 2)
            ram_total_gb = round(memory.total / (1024**3), 2)
            disk = psutil.disk_usage("/")
            disk_percent = disk.percent
            disk_used_gb = round(disk.used / (1024**3), 2)
            disk_total_gb = round(disk.total / (1024**3), 2)
            uptime_seconds = (datetime.now() - bot_start_time).total_seconds()
            uptime_days = int(uptime_seconds // 86400)
            uptime_hours = int((uptime_seconds % 86400) // 3600)
            uptime_minutes = int((uptime_seconds % 3600) // 60)
            system_info = {"os": platform.system(), "python_version": platform.python_version()}
            return {
                "status": "ok",
                "timestamp": datetime.now().isoformat(),
                "cpu": {
                    "percent": cpu_percent,
                    "status": "critical" if cpu_percent > 90 else "warning" if cpu_percent > 80 else "normal",
                },
                "ram": {
                    "percent": ram_percent,
                    "used_gb": ram_used_gb,
                    "total_gb": ram_total_gb,
                    "status": "critical" if ram_percent > 90 else "warning" if ram_percent > 80 else "normal",
                },
                "disk": {
                    "percent": disk_percent,
                    "used_gb": disk_used_gb,
                    "total_gb": disk_total_gb,
                    "status": "critical" if disk_percent > 90 else "warning" if disk_percent > 85 else "normal",
                },
                "uptime": {
                    "days": uptime_days,
                    "hours": uptime_hours,
                    "minutes": uptime_minutes,
                    "formatted": f"{uptime_days}g {uptime_hours}s {uptime_minutes}dk",
                },
                "system": system_info,
            }
        except Exception as e:
            return {"status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}

    @router.get("/admin/api-status")
    async def get_api_status():
        results = {"timestamp": datetime.now().isoformat(), "apis": {}}
        try:
            start_time = datetime.now()
            openai_client.chat.completions.create(
                model=get_openai_model_fn(),
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5,
            )
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            results["apis"]["openai"] = {
                "status": "ok",
                "response_time_ms": round(elapsed, 2),
                "model": get_openai_model_fn(),
            }
        except Exception as e:
            results["apis"]["openai"] = {"status": "error", "error": str(e)}

        try:
            if whatsapp_phone_id and whatsapp_token:
                results["apis"]["whatsapp"] = {
                    "status": "ok",
                    "phone_id": whatsapp_phone_id[:10] + "...",
                    "token_present": True,
                }
            else:
                results["apis"]["whatsapp"] = {"status": "error", "error": "Token veya Phone ID eksik"}
        except Exception as e:
            results["apis"]["whatsapp"] = {"status": "error", "error": str(e)}

        all_ok = all(api["status"] == "ok" for api in results["apis"].values())
        results["overall_status"] = "ok" if all_ok else "degraded"
        return results

    @router.get("/admin/error-logs")
    async def get_error_logs(hours: int = 24, error_type: str | None = None):
        cutoff_time = datetime.now() - timedelta(hours=hours)
        filtered_logs = []
        for log in error_logs:
            log_time = datetime.fromisoformat(log["timestamp"])
            if log_time >= cutoff_time:
                if error_type is None or log["type"] == error_type:
                    filtered_logs.append(log)
        error_counts: Dict[str, int] = {}
        for log in filtered_logs:
            error_counts[log["type"]] = error_counts.get(log["type"], 0) + 1
        return {
            "period_hours": hours,
            "total_errors": len(filtered_logs),
            "error_counts": error_counts,
            "logs": filtered_logs[-50:],
            "timestamp": datetime.now().isoformat(),
        }

    @router.post("/admin/test-chat")
    async def test_chat_endpoint(phone: str = "TEST_BOT_001", message: str = "Merhaba"):
        start_time = datetime.now()
        try:
            _ = detect_language_fn(message)
            response_text = await get_openai_response_fn(phone, message)
            response_source = "OPENAI"
            elapsed = (datetime.now() - start_time).total_seconds()
            return {
                "status": "ok",
                "test_phone": phone,
                "input_message": message,
                "response": response_text,
                "response_source": response_source,
                "response_time_seconds": round(elapsed, 3),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds()
            return {
                "status": "error",
                "test_phone": phone,
                "input_message": message,
                "error": str(e),
                "response_time_seconds": round(elapsed, 3),
                "timestamp": datetime.now().isoformat(),
            }

    @router.get("/admin/elektraweb/raw-price")
    async def elektraweb_raw_price_test(
        from_date: str = "2025-06-05",
        to_date: str = "2025-06-10",
        adult: int = 2,
        currency: str = "EUR",
    ):
        from app.services.elektraweb_booking_service import fetch_price

        hotel_id = (os.getenv("ELEKTRA_HOTEL_ID") or "21966").strip()
        try:
            raw = await fetch_price(
                hotel_id=hotel_id,
                from_date=from_date,
                to_date=to_date,
                adult=adult,
                currency=currency,
                nationality="TR",
                language="tr",
            )

            all_keys: set = set()
            offers = []
            if isinstance(raw, list):
                offers = raw
            elif isinstance(raw, dict):
                for k in ("data", "result", "offers", "prices"):
                    if k in raw and isinstance(raw[k], list):
                        offers = raw[k]
                        break

            for offer in offers:
                if isinstance(offer, dict):
                    all_keys.update(offer.keys())
                    for val in offer.values():
                        if isinstance(val, dict):
                            all_keys.update(f"  └─{sub_k}" for sub_k in val.keys())

            needed_ids = [
                "rate-type-id",
                "board-type-id",
                "rate-code-id",
                "room-type-id",
                "price-agency-id",
                "room-id",
            ]
            found_ids = {nid: (nid in all_keys) for nid in needed_ids}
            return {
                "success": True,
                "hotel_id": hotel_id,
                "query": {
                    "from_date": from_date,
                    "to_date": to_date,
                    "adult": adult,
                    "currency": currency,
                },
                "offer_count": len(offers),
                "all_response_keys": sorted(all_keys),
                "needed_ids_for_booking": found_ids,
                "all_ids_present": all(found_ids.values()),
                "first_offer_sample": offers[0] if offers else None,
                "raw_response_type": type(raw).__name__,
            }
        except Exception as e:
            return {"success": False, "error": str(e), "hotel_id": hotel_id}

    return router
