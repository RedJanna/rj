# Dosya Adı: app/routes/access_control_routes.py
from __future__ import annotations

from typing import Awaitable, Callable, Optional

from fastapi import APIRouter

from app.services.access_control_service import (
    add_to_blacklist,
    load_blacklist,
    pause_conversation,
    remove_from_blacklist,
    resume_conversation,
)
from app.services.conversation_store import preview_phone_data, purge_phone_data

NotifyFn = Callable[[str, str], Awaitable[None]]


def build_access_control_router(notify_critical_action: Optional[NotifyFn] = None) -> APIRouter:
    """
    Endpoint path'leri mevcut haliyle korunur:
    - GET  /blacklist
    - POST /blacklist/add/{phone}
    - POST /blacklist/remove/{phone}
    - POST /pause/{phone}
    - POST /resume/{phone}
    """
    router = APIRouter(tags=["access-control"])

    @router.get("/blacklist")
    async def get_blacklist_api():
        return {"blacklist": load_blacklist()}

    @router.post("/blacklist/add/{phone}")
    async def add_blacklist_api(phone: str):
        ok = add_to_blacklist(phone)
        # Eski davranış: başarılıysa admin'e kritik bildirim
        if ok and notify_critical_action:
            await notify_critical_action("KARA LİSTEYE EKLEME", f"Numara: {phone}")
        return {"success": ok}

    @router.post("/blacklist/remove/{phone}")
    async def remove_blacklist_api(phone: str):
        ok = remove_from_blacklist(phone)
        # Eski davranış: başarılıysa admin'e kritik bildirim
        if ok and notify_critical_action:
            await notify_critical_action("KARA LİSTEDEN ÇIKARMA", f"Numara: {phone}")
        return {"success": ok}

    @router.post("/pause/{phone}")
    async def pause_api(phone: str, reason: str = "manual"):
        pause_conversation(phone, reason=reason)
        return {"success": True}

    @router.post("/resume/{phone}")
    async def resume_api(phone: str):
        resume_conversation(phone)
        return {"success": True}

    # ======================================================
    # PURGE (Telefon Numarası Tam Temizleme)
    # ======================================================

    @router.get("/purge/preview/{phone}")
    async def purge_preview_api(phone: str):
        return preview_phone_data(phone)

    @router.post("/purge/{phone}")
    async def purge_api(phone: str, hard: bool = False):
        result = purge_phone_data(phone, hard_delete_bookings=bool(hard))
        if result.get("success") and notify_critical_action:
            cleared = ", ".join(result.get("cleared", []))
            await notify_critical_action(
                "KONUŞMA SIFIRLAMA",
                f"Numara: {phone}\nHard Purge: {bool(hard)}\nTemizlenen: {cleared}",
            )
        return result

    return router
