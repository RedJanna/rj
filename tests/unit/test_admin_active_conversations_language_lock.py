from __future__ import annotations

import json
from datetime import datetime

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.routes.admin_misc_routes import build_admin_misc_router


def _build_app(conversations_dir):
    async def _noop_send(_phone: str, _msg: str):
        return True

    app = FastAPI()
    router = build_admin_misc_router(
        app_ref=app,
        get_session_fn=lambda _token: None,
        get_user_fn=lambda _username: None,
        get_openai_model_fn=lambda: "gpt-4.1-mini",
        set_openai_model_fn=lambda _model: None,
        allowed_models=["gpt-4.1-mini"],
        model_change_info={},
        send_whatsapp_message_fn=_noop_send,
        admin_phone="905550000000",
        whatsapp_phone_id="pid",
        whatsapp_token="token",
        conversations_dir=conversations_dir,
        is_paused_fn=lambda _phone: False,
        authorized_persons={},
        admin_html="<html></html>",
        reminder_page_html="<html></html>",
        reservations_html="<html></html>",
        transfer_reservations_html="<html></html>",
        restaurant_plan_html="<html></html>",
        dashboard_html="<html></html>",
        admin_tools_html="<html></html>",
    )
    app.include_router(router)
    return app


@pytest.mark.unit
@pytest.mark.asyncio
async def test_active_conversations_returns_language_lock(tmp_path):
    now_iso = datetime.now().isoformat()
    tr_then_en_switch = {
        "phone": "905551111111",
        "updated_at": now_iso,
        "messages": [
            {"user_message": "Merhaba"},
            {"user_message": "Can you speak English?"},
        ],
    }
    ru_only = {
        "phone": "905552222222",
        "updated_at": now_iso,
        "messages": [
            {"user_message": "Привет"},
            {"user_message": "Цена?"},
        ],
    }

    (tmp_path / "905551111111.json").write_text(json.dumps(tr_then_en_switch, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "905552222222.json").write_text(json.dumps(ru_only, ensure_ascii=False), encoding="utf-8")

    app = _build_app(tmp_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/admin/active-conversations")
        assert resp.status_code == 200
        data = resp.json()
    assert data["active_count"] == 2

    by_phone = {item["phone"]: item for item in data["conversations"]}
    assert by_phone["905551111111"]["language_lock"] == "en"
    assert by_phone["905552222222"]["language_lock"] == "ru"
    assert "paused_reason" in by_phone["905551111111"]
    assert "paused_minutes" in by_phone["905551111111"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_active_conversations_includes_pause_reason_when_present(tmp_path, monkeypatch):
    now_iso = datetime.now().isoformat()
    paused_conv = {
        "phone": "905553333333",
        "updated_at": now_iso,
        "messages": [{"user_message": "Merhaba"}],
    }
    (tmp_path / "905553333333.json").write_text(json.dumps(paused_conv, ensure_ascii=False), encoding="utf-8")

    from app.routes import admin_misc_routes as route_mod

    monkeypatch.setattr(
        route_mod,
        "load_paused",
        lambda: {
            "paused": {
                "905553333333": {
                    "paused_at": now_iso,
                    "reason": "human_takeover:test_pause_reason",
                }
            }
        },
    )

    app = _build_app(tmp_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/admin/active-conversations")
        assert resp.status_code == 200
        data = resp.json()

    by_phone = {item["phone"]: item for item in data["conversations"]}
    assert by_phone["905553333333"]["is_paused"] is True
    assert by_phone["905553333333"]["paused_reason"] == "human_takeover:test_pause_reason"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_reservations_page_requires_session_cookie(tmp_path):
    app = _build_app(tmp_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver", follow_redirects=False) as client:
        resp = await client.get("/admin/reservations-page")
    assert resp.status_code == 302
    assert resp.headers.get("location") == "/admin/login"
