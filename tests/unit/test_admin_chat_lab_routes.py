from __future__ import annotations

import json
from datetime import datetime

import pytest
from fastapi import FastAPI, Request, Response
from httpx import ASGITransport, AsyncClient

from app.routes.admin_misc_routes import build_admin_misc_router


def _build_app(tmp_path, monkeypatch):
    from app.services import admin_chat_lab_service as lab_service
    from app.routes import admin_misc_routes as route_mod

    trace_file = tmp_path / "decision_trace.jsonl"
    event_file = tmp_path / "admin_chat_lab_events.jsonl"
    backend_file = tmp_path / "backend_boot.log"

    monkeypatch.setattr(lab_service, "DECISION_TRACE_FILE", trace_file)
    monkeypatch.setattr(lab_service, "CHAT_LAB_EVENT_FILE", event_file)
    monkeypatch.setattr(lab_service, "BACKEND_BOOT_LOG_FILE", backend_file)

    app = FastAPI()

    @app.post("/chat")
    async def _chat_stub(payload: dict, request: Request, response: Response):
        phone = str(payload.get("phone") or "")
        message = str(payload.get("message") or "")
        correlation_id = request.headers.get("X-Correlation-Id", "stub-correlation")
        response.headers["X-Correlation-Id"] = correlation_id

        conversation = {
            "phone": phone,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "messages": [
                {
                    "timestamp": datetime.now().isoformat(),
                    "date": "2026-03-09",
                    "time": "12:00:00",
                    "user_message": message,
                    "bot_reply": "Stub cevap",
                }
            ],
        }
        (tmp_path / f"{phone}.json").write_text(json.dumps(conversation, ensure_ascii=False), encoding="utf-8")

        trace_rows = [
            {
                "ts": datetime.now().isoformat(),
                "correlation_id": correlation_id,
                "phone": phone,
                "stage": "intent_router",
                "primary_intent": "PRICE_QUERY",
                "semantic_intent": "PRICE_QUERY",
                "semantic_confidence": 0.88,
            },
            {
                "ts": datetime.now().isoformat(),
                "correlation_id": correlation_id,
                "phone": phone,
                "stage": "intent_routing",
                "slot_coverage": {
                    "required_slots": ["check_in_date", "check_out_date", "adult_count"],
                    "missing_required_slots": ["adult_count"],
                    "has_minimum_required": False,
                },
            },
        ]
        trace_file.parent.mkdir(parents=True, exist_ok=True)
        with trace_file.open("a", encoding="utf-8") as handle:
            for row in trace_rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        backend_file.write_text(
            json.dumps(
                {
                    "ts": datetime.now().isoformat(),
                    "correlation_id": correlation_id,
                    "phone": phone,
                    "event": "chat.response",
                    "status": "ok",
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        return {"reply": "Stub cevap", "status": "ok"}

    def _get_session(token: str):
        if token != "ok-token":
            return None

        class _Session:
            username = "admin"
            is_2fa_verified = True

        return _Session()

    class _User:
        totp_enabled = True

    router = build_admin_misc_router(
        app_ref=app,
        get_session_fn=_get_session,
        get_user_fn=lambda _username: _User(),
        get_openai_model_fn=lambda: "gpt-5.2-chat-latest",
        set_openai_model_fn=lambda _model: None,
        allowed_models=["gpt-5.2-chat-latest"],
        model_change_info={},
        send_whatsapp_message_fn=lambda *_args, **_kwargs: True,
        admin_phone="905550000000",
        whatsapp_phone_id="pid",
        whatsapp_token="token",
        conversations_dir=tmp_path,
        is_paused_fn=lambda _phone: False,
        authorized_persons={},
        admin_html="<html><div class=\"nav-links\"></div></html>",
        reminder_page_html="<html><div class=\"nav-links\"></div></html>",
        reservations_html="<html><div class=\"nav-links\"></div></html>",
        transfer_reservations_html="<html><div class=\"nav-links\"></div></html>",
        restaurant_plan_html="<html><div class=\"nav-links\"></div></html>",
        dashboard_html="<html><div class=\"nav-links\"></div></html>",
        admin_tools_html="<html><div class=\"nav-links\"></div></html>",
    )
    app.include_router(router)

    return app, trace_file, event_file


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_lab_page_requires_session_cookie(tmp_path, monkeypatch):
    app, _trace_file, _event_file = _build_app(tmp_path, monkeypatch)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver", follow_redirects=False) as client:
        resp = await client.get("/admin/chat-lab")
    assert resp.status_code == 302
    assert resp.headers.get("location") == "/admin/login"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_lab_send_returns_snapshot_and_records_event(tmp_path, monkeypatch):
    app, _trace_file, event_file = _build_app(tmp_path, monkeypatch)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/admin/chat-lab/send",
            json={"phone": "905551111111", "message": "Bana fiyat ver"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["chat"]["reply"] == "Stub cevap"
    assert data["snapshot"]["debug"]["intent"] == "PRICE_QUERY"
    assert data["snapshot"]["conversation"]["message_count"] == 1
    assert data["snapshot"]["backend_events"][0]["event"] == "chat.response"

    lines = event_file.read_text(encoding="utf-8").splitlines()
    assert lines
    last_row = json.loads(lines[-1])
    assert last_row["phone"] == "905551111111"
    assert last_row["status"] == "ok"
    assert last_row["correlation_id"] == data["correlation_id"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_lab_reset_returns_clean_snapshot(tmp_path, monkeypatch):
    app, _trace_file, event_file = _build_app(tmp_path, monkeypatch)
    from app.routes import admin_misc_routes as route_mod

    created = tmp_path / "905552222222.json"
    created.write_text(
        json.dumps(
            {
                "phone": "905552222222",
                "updated_at": datetime.now().isoformat(),
                "messages": [{"user_message": "Merhaba", "bot_reply": "Selam"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    def _purge(phone: str, *, hard_delete_bookings: bool = False):
        if created.exists():
            created.unlink()
        return {"success": True, "phone": phone, "cleared": ["conversation"]}

    monkeypatch.setattr(route_mod, "purge_phone_data", _purge)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post("/admin/chat-lab/reset", json={"phone": "905552222222"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["snapshot"]["conversation"]["exists"] is False
    lines = event_file.read_text(encoding="utf-8").splitlines()
    assert lines
    assert json.loads(lines[-1])["status"] == "reset"
