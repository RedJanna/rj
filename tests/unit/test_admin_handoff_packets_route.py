from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.routes.admin_ops_routes import build_admin_ops_router


async def _get_json(app: FastAPI, path: str):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get(path)
        return resp.status_code, resp.json()


def _build_app(tmp_path):
    async def _noop_async(*args, **kwargs):
        return True

    app = FastAPI()
    router = build_admin_ops_router(
        load_settings_fn=lambda: {},
        save_settings_fn=lambda _: None,
        is_automation_enabled_fn=lambda: True,
        is_followup_enabled_fn=lambda: False,
        notify_critical_action_fn=_noop_async,
        conversations_dir=tmp_path,
        load_conversation_fn=lambda _: {},
        send_whatsapp_message_fn=_noop_async,
        admin_phone="905550000000",
        whatsapp_phone_id="pid",
        whatsapp_token="token",
    )
    app.include_router(router)
    return app


@pytest.mark.unit
@pytest.mark.asyncio
async def test_admin_handoff_packets_lists_valid_and_invalid(monkeypatch, tmp_path):
    valid_packet = {
        "packet_id": "abc123",
        "source": "chat_runtime",
        "category": "canli_destek",
        "priority": "medium",
        "customer_phone": "+905551112233",
        "customer_message": "Canlı destek istiyorum",
        "detected_intent": "HUMAN_REQUEST",
        "trigger_type": "soft",
        "sla_target_minutes": 20,
        "within_business_hours": True,
        "language_lock": "en",
    }

    def _fake_list_events(*args, **kwargs):
        return (
            [
                {
                    "ts": "2026-02-24T10:00:00+00:00",
                    "event": "handoff.packet",
                    "category": "canli_destek",
                    "meta": {"packet": valid_packet},
                },
                {
                    "ts": "2026-02-24T10:05:00+00:00",
                    "event": "handoff.packet_reject",
                    "category": "sikayet",
                    "meta": {"missing": ["priority"]},
                },
            ],
            2,
        )

    monkeypatch.setattr("app.routes.admin_ops_routes.list_events", _fake_list_events)
    app = _build_app(tmp_path)
    status, data = await _get_json(app, "/admin/handoff/packets?days=7&limit=10")
    assert status == 200
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["items"][0]["valid"] is True
    assert data["items"][1]["valid"] is False
    assert "priority" in data["items"][1]["missing"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_admin_handoff_packets_only_invalid_filter(monkeypatch, tmp_path):
    def _fake_list_events(*args, **kwargs):
        return (
            [
                {
                    "ts": "2026-02-24T10:00:00+00:00",
                    "event": "handoff.packet",
                    "category": "canli_destek",
                    "meta": {
                        "packet": {
                            "packet_id": "abc123",
                            "source": "chat_runtime",
                            "category": "canli_destek",
                            "priority": "medium",
                            "customer_phone": "+905551112233",
                            "customer_message": "Canlı destek istiyorum",
                            "detected_intent": "HUMAN_REQUEST",
                            "trigger_type": "soft",
                            "sla_target_minutes": 20,
                            "within_business_hours": True,
                            "language_lock": "en",
                        }
                    },
                },
                {
                    "ts": "2026-02-24T10:05:00+00:00",
                    "event": "handoff.packet_reject",
                    "category": "sikayet",
                    "meta": {"missing": ["priority"], "language_lock": "tr"},
                },
            ],
            2,
        )

    monkeypatch.setattr("app.routes.admin_ops_routes.list_events", _fake_list_events)
    app = _build_app(tmp_path)
    status, data = await _get_json(app, "/admin/handoff/packets?only_invalid=true")
    assert status == 200
    assert len(data["items"]) == 1
    assert data["items"][0]["valid"] is False
    assert data["items"][0]["debug"]["language_lock"] == "tr"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_admin_handoff_packets_after_deploy_filter(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DEPLOYED_AT", "2026-02-24T10:03:00+00:00")

    def _fake_list_events(*args, **kwargs):
        return (
            [
                {
                    "ts": "2026-02-24T10:00:00+00:00",
                    "event": "handoff.packet_reject",
                    "category": "sikayet",
                    "meta": {"missing": ["category"]},
                },
                {
                    "ts": "2026-02-24T10:05:00+00:00",
                    "event": "handoff.packet_reject",
                    "category": "sikayet",
                    "meta": {"missing": ["priority"]},
                },
            ],
            2,
        )

    monkeypatch.setattr("app.routes.admin_ops_routes.list_events", _fake_list_events)
    app = _build_app(tmp_path)
    status, data = await _get_json(app, "/admin/handoff/packets?only_invalid=true&after_deploy=true")
    assert status == 200
    assert data["effective_after_ts"] == "2026-02-24T10:03:00+00:00"
    assert len(data["items"]) == 1
    assert "priority" in data["items"][0]["missing"]
