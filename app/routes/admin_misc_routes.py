"""Admin UI/tools/model routes extracted from legacy monolith."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse


def build_admin_misc_router(
    app_ref: Any,
    get_session_fn: Callable[[str], Any],
    get_user_fn: Callable[[str], Any],
    get_openai_model_fn: Callable[[], str],
    set_openai_model_fn: Callable[[str], None],
    allowed_models: List[str],
    model_change_info: Dict[str, Any],
    send_whatsapp_message_fn: Callable[[str, str], Awaitable[Any]],
    admin_phone: str,
    whatsapp_phone_id: str,
    whatsapp_token: str,
    conversations_dir: Path,
    is_paused_fn: Callable[[str], bool],
    authorized_persons: Dict[str, str],
    admin_html: str,
    reminder_page_html: str,
    reservations_html: str,
    restaurant_plan_html: str,
    dashboard_html: str,
    admin_tools_html: str,
) -> APIRouter:
    router = APIRouter(tags=["admin-misc"])

    @router.get("/admin", response_class=HTMLResponse)
    async def admin_panel(request: Request):
        session_token = request.cookies.get("kassandra_session")
        if not session_token:
            return RedirectResponse(url="/admin/login", status_code=302)
        session = get_session_fn(session_token)
        if not session:
            return RedirectResponse(url="/admin/login", status_code=302)
        user = get_user_fn(session.username)
        if user and user.totp_enabled and not session.is_2fa_verified:
            return RedirectResponse(url="/admin/verify-2fa", status_code=302)
        if user and not user.totp_enabled:
            return RedirectResponse(url="/admin/setup-2fa", status_code=302)
        return admin_html

    @router.get("/", response_class=HTMLResponse)
    async def root():
        return """<html><head><meta http-equiv="refresh" content="0; url=/admin"></head></html>"""

    @router.get("/admin/reminders-page", response_class=HTMLResponse)
    async def reminders_page(request: Request):
        session_token = request.cookies.get("kassandra_session")
        if not session_token:
            return RedirectResponse(url="/admin/login", status_code=302)
        session = get_session_fn(session_token)
        if not session or (get_user_fn(session.username) and get_user_fn(session.username).totp_enabled and not session.is_2fa_verified):
            return RedirectResponse(url="/admin/login", status_code=302)
        return reminder_page_html

    @router.get("/admin/reservations-page", response_class=HTMLResponse)
    async def reservations_page():
        return reservations_html

    @router.get("/admin/restaurant-plan", response_class=HTMLResponse)
    async def restaurant_plan_page(request: Request):
        session_token = request.cookies.get("kassandra_session")
        if not session_token:
            return RedirectResponse(url="/admin/login", status_code=302)
        session = get_session_fn(session_token)
        if not session or (get_user_fn(session.username) and get_user_fn(session.username).totp_enabled and not session.is_2fa_verified):
            return RedirectResponse(url="/admin/login", status_code=302)
        return HTMLResponse(restaurant_plan_html, headers={"Content-Type": "text/html; charset=utf-8"})

    @router.get("/admin/dashboard", response_class=HTMLResponse)
    async def dashboard_page():
        return dashboard_html

    @router.post("/admin/send-message")
    async def send_manual_message(phone: str, message: str):
        clean_phone = re.sub(r"[^\d]", "", phone)
        success = await send_whatsapp_message_fn(clean_phone, message)
        return {
            "status": "sent" if success else "failed",
            "phone": clean_phone,
            "message_preview": message[:50] + "..." if len(message) > 50 else message,
        }

    @router.get("/admin/active-conversations")
    async def get_active_conversations():
        files = list(conversations_dir.glob("*.json"))
        active = []
        now = datetime.now()
        for f in files:
            try:
                with open(f, "r", encoding="utf-8") as file:
                    data = json.load(file)
                    updated = datetime.fromisoformat(data.get("updated_at", "2000-01-01"))
                    if (now - updated).total_seconds() < 1800:
                        messages = data.get("messages", [])
                        last_msg = messages[-1] if messages else {}
                        active.append(
                            {
                                "phone": data.get("phone"),
                                "last_message": last_msg.get("user_message", "")[:50],
                                "last_time": data.get("updated_at"),
                                "message_count": len(messages),
                                "is_paused": is_paused_fn(data.get("phone")),
                                "minutes_ago": int((now - updated).total_seconds() / 60),
                            }
                        )
            except Exception:
                pass
        active.sort(key=lambda x: x.get("last_time", ""), reverse=True)
        return {"active_count": len(active), "conversations": active}

    @router.get("/admin/authorized-persons")
    async def get_authorized_persons_api():
        return {"persons": authorized_persons}

    @router.get("/admin/all-endpoints")
    async def get_all_endpoints():
        endpoints = []
        for route in app_ref.routes:
            if hasattr(route, "methods") and hasattr(route, "path"):
                for method in route.methods:
                    if method != "HEAD":
                        endpoints.append({"method": method, "path": route.path, "name": route.name or ""})
        grouped = {}
        for ep in endpoints:
            prefix = ep["path"].split("/")[1] if "/" in ep["path"] else "root"
            grouped.setdefault(prefix, []).append(ep)
        return {"total": len(endpoints), "endpoints": endpoints, "grouped": grouped}

    @router.get("/admin/tools", response_class=HTMLResponse)
    async def admin_tools():
        return admin_tools_html

    @router.get("/admin/model")
    async def get_current_model():
        return {
            "current_model": get_openai_model_fn(),
            "allowed_models": allowed_models,
            "changed_at": model_change_info.get("changed_at"),
            "changed_by": model_change_info.get("changed_by"),
            "previous_model": model_change_info.get("previous_model"),
        }

    @router.post("/admin/model")
    async def change_model(request: Request):
        try:
            body = await request.json()
            new_model = body.get("model", "").strip()
        except Exception:
            return {"success": False, "error": "Geçersiz JSON body"}
        if not new_model:
            return {"success": False, "error": "Model adı boş olamaz"}
        if new_model not in allowed_models:
            return {"success": False, "error": f"Geçersiz model: {new_model}. İzin verilen: {', '.join(allowed_models)}"}

        old_model = get_openai_model_fn()
        if new_model == old_model:
            return {"success": False, "error": "Seçilen model zaten aktif"}

        set_openai_model_fn(new_model)
        now_str = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        model_change_info["changed_at"] = now_str
        model_change_info["changed_by"] = "Admin Panel"
        model_change_info["previous_model"] = old_model
        try:
            notify_msg = (
                f"Model Degisikligi\n"
                f"Eski: {old_model}\n"
                f"Yeni: {new_model}\n"
                f"Zaman: {now_str}\n"
                f"Degistiren: Admin Panel"
            )
            await send_whatsapp_message_fn(admin_phone, notify_msg)
        except Exception as e:
            print(f"[MODEL] Admin bildirim hatası: {e}")
        return {"success": True, "old_model": old_model, "new_model": new_model, "changed_at": now_str}

    @router.get("/test/check-config")
    async def check_config():
        return {
            "admin_phone": admin_phone,
            "whatsapp_phone_id": whatsapp_phone_id[:10] + "..." if whatsapp_phone_id else "BOŞ!",
            "whatsapp_token": "Ayarlanmış ✅" if whatsapp_token else "BOŞ! ❌",
            "status": "OK" if (whatsapp_phone_id and whatsapp_token) else "HATA - Ayarlar eksik!",
        }

    return router
