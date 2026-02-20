"""Admin safety and fallback routes extracted from the legacy monolith."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from fastapi import APIRouter


def build_admin_safety_router(
    enable_safe_mode_fn: Callable[[], Any],
    disable_safe_mode_fn: Callable[[], Any],
    get_system_status_fn: Callable[[], Dict[str, Any]],
    unblock_rate_limit_fn: Callable[[str], bool],
    get_error_stats_fn: Callable[[], Dict[str, Any]],
    clear_errors_fn: Callable[[], Any],
    notify_critical_action_fn: Callable[[str, str], Awaitable[Any]],
) -> APIRouter:
    router = APIRouter(tags=["admin-safety"])

    @router.post("/admin/safe-mode/enable")
    async def api_enable_safe_mode():
        enable_safe_mode_fn()
        await notify_critical_action_fn(
            "GUVENLI MOD ACILDI",
            "Bot tum musterilere cevap vermeyi DURDURDU!",
        )
        return {"status": "ok", "safe_mode": True}

    @router.post("/admin/safe-mode/disable")
    async def api_disable_safe_mode():
        disable_safe_mode_fn()
        await notify_critical_action_fn(
            "GUVENLI MOD KAPATILDI",
            "Bot normal calismaya devam ediyor.",
        )
        return {"status": "ok", "safe_mode": False}

    @router.get("/admin/safe-mode/status")
    async def api_safe_mode_status():
        return get_system_status_fn()

    @router.post("/admin/rate-limit/unblock/{phone}")
    async def api_unblock_rate_limit(phone: str):
        success = unblock_rate_limit_fn(phone)
        return {"status": "ok", "unblocked": success}

    @router.get("/admin/errors")
    async def api_get_errors():
        return get_error_stats_fn()

    @router.post("/admin/errors/clear")
    async def api_clear_errors():
        clear_errors_fn()
        return {"status": "ok"}

    return router
