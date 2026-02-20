"""Operational admin routes extracted from legacy monolith."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict

from fastapi import APIRouter


def build_admin_ops_router(
    load_settings_fn: Callable[[], Dict[str, Any]],
    save_settings_fn: Callable[[Dict[str, Any]], Any],
    is_automation_enabled_fn: Callable[[], bool],
    is_followup_enabled_fn: Callable[[], bool],
    notify_critical_action_fn: Callable[[str, str], Awaitable[Any]],
    conversations_dir: Path,
    load_conversation_fn: Callable[[str], Dict[str, Any]],
    send_whatsapp_message_fn: Callable[[str, str], Awaitable[Any]],
    admin_phone: str,
    whatsapp_phone_id: str,
    whatsapp_token: str,
) -> APIRouter:
    router = APIRouter(tags=["admin-ops"])

    @router.get("/health")
    async def health():
        return {"status": "ok", "automation": is_automation_enabled_fn()}

    @router.get("/settings")
    async def get_settings():
        return load_settings_fn()

    @router.post("/settings")
    async def update_settings(
        automation_enabled: bool = None,
        followup_enabled: bool = None,
        followup_minutes: int = None,
    ):
        settings = load_settings_fn()
        if automation_enabled is not None:
            settings["automation_enabled"] = automation_enabled
        if followup_enabled is not None:
            settings["followup_enabled"] = followup_enabled
        if followup_minutes is not None:
            settings["followup_minutes"] = followup_minutes
        save_settings_fn(settings)
        return settings

    @router.post("/automation/start")
    async def start_automation():
        settings = load_settings_fn()
        settings["automation_enabled"] = True
        save_settings_fn(settings)
        return {"status": "started", "automation_enabled": True}

    @router.post("/automation/stop")
    async def stop_automation():
        settings = load_settings_fn()
        settings["automation_enabled"] = False
        save_settings_fn(settings)
        await notify_critical_action_fn(
            "OTOMASYON KAPATILDI",
            "Bot artık müşterilere cevap vermiyor!",
        )
        return {"status": "stopped", "automation_enabled": False}

    @router.get("/automation/status")
    async def automation_status():
        return {
            "automation_enabled": is_automation_enabled_fn(),
            "followup_enabled": is_followup_enabled_fn(),
        }

    @router.get("/conversations")
    async def list_conversations():
        files = list(conversations_dir.glob("*.json"))
        convs = []
        for f in files:
            try:
                with open(f, "r", encoding="utf-8") as file:
                    data = json.load(file)
                    convs.append(
                        {
                            "phone": data.get("phone"),
                            "messages": len(data.get("messages", [])),
                            "updated": data.get("updated_at"),
                        }
                    )
            except Exception:
                pass
        return {"conversations": convs}

    @router.get("/conversations/{phone}")
    async def get_conversation_api(phone: str):
        return load_conversation_fn(phone)

    @router.get("/test/admin-notification")
    async def test_admin_notification():
        test_message = (
            "TEST MESAJI - SISTEM CALISIYOR!\n\n"
            "Bu mesaji goruyorsan bildirim sistemi duzgun calisiyor.\n\n"
            f"Zaman: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Admin: {admin_phone}\n"
            f"WHATSAPP_PHONE_ID: {whatsapp_phone_id[:5]}... (gizli)\n\n"
            "Kassandra Bot Bildirim Sistemi"
        )
        success = await send_whatsapp_message_fn(admin_phone, test_message)
        return {
            "status": "sent" if success else "failed",
            "admin_phone": admin_phone,
            "whatsapp_phone_id_set": bool(whatsapp_phone_id),
            "whatsapp_token_set": bool(whatsapp_token),
            "message": "Telefonunu kontrol et!" if success else "Gonderim basarisiz - ayarlari kontrol et",
        }

    return router
