import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.routes.admin_ops_routes as admin_ops_routes
from app.routes.admin_ops_routes import build_admin_ops_router


@pytest.mark.unit
def test_settings_update_rejects_invalid_room_keys(monkeypatch):
    state = {
        "automation_enabled": True,
        "followup_enabled": False,
        "followup_minutes": 10,
        "quiet_auto_room_keys": ["deluxe", "premium"],
        "quiet_handoff_room_keys": ["superior"],
    }

    def load_settings():
        return dict(state)

    def save_settings(new_settings):
        state.update(new_settings)

    async def _noop_async(*args, **kwargs):
        return True

    app = FastAPI()
    router = build_admin_ops_router(
        load_settings_fn=load_settings,
        save_settings_fn=save_settings,
        is_automation_enabled_fn=lambda: True,
        is_followup_enabled_fn=lambda: False,
        notify_critical_action_fn=_noop_async,
        conversations_dir=None,
        load_conversation_fn=lambda p: {},
        send_whatsapp_message_fn=_noop_async,
        admin_phone="905550000000",
        whatsapp_phone_id="pid",
        whatsapp_token="token",
    )
    app.include_router(router)

    @app.middleware("http")
    async def _inject_user(request, call_next):
        class _User:
            username = "test_admin"
        request.state.user = _User()
        request.state.auth_via_token = True
        return await call_next(request)

    client = TestClient(app)
    resp = client.post("/settings?quiet_auto_room_keys=deluxe,wrongRoom")
    data = resp.json()
    assert data["success"] is False
    assert "Geçersiz oda anahtarı" in data["error"]


@pytest.mark.unit
def test_settings_update_rejects_overlapping_quiet_keys():
    state = {
        "automation_enabled": True,
        "followup_enabled": False,
        "followup_minutes": 10,
        "quiet_auto_room_keys": ["deluxe", "premium"],
        "quiet_handoff_room_keys": ["superior"],
    }

    def load_settings():
        return dict(state)

    def save_settings(new_settings):
        state.update(new_settings)

    async def _noop_async(*args, **kwargs):
        return True

    app = FastAPI()
    router = build_admin_ops_router(
        load_settings_fn=load_settings,
        save_settings_fn=save_settings,
        is_automation_enabled_fn=lambda: True,
        is_followup_enabled_fn=lambda: False,
        notify_critical_action_fn=_noop_async,
        conversations_dir=None,
        load_conversation_fn=lambda p: {},
        send_whatsapp_message_fn=_noop_async,
        admin_phone="905550000000",
        whatsapp_phone_id="pid",
        whatsapp_token="token",
    )
    app.include_router(router)

    @app.middleware("http")
    async def _inject_user(request, call_next):
        class _User:
            username = "test_admin"
        request.state.user = _User()
        request.state.auth_via_token = True
        return await call_next(request)

    client = TestClient(app)
    resp = client.post("/settings?quiet_auto_room_keys=deluxe,premium&quiet_handoff_room_keys=superior,premium")
    data = resp.json()
    assert data["success"] is False
    assert "hem otomatik hem handoff olamaz" in data["error"]


@pytest.mark.unit
def test_settings_update_operational_rules_flag_and_status_reflects(monkeypatch):
    monkeypatch.setattr(admin_ops_routes, "append_settings_audit_entry", lambda **_kwargs: None)
    state = {
        "automation_enabled": True,
        "followup_enabled": False,
        "operational_rules_enabled": True,
        "followup_minutes": 10,
        "quiet_auto_room_keys": ["deluxe", "premium"],
        "quiet_handoff_room_keys": ["superior"],
    }

    def load_settings():
        return dict(state)

    def save_settings(new_settings):
        state.update(new_settings)

    async def _noop_async(*args, **kwargs):
        return True

    app = FastAPI()
    router = build_admin_ops_router(
        load_settings_fn=load_settings,
        save_settings_fn=save_settings,
        is_automation_enabled_fn=lambda: state.get("automation_enabled", True),
        is_followup_enabled_fn=lambda: state.get("followup_enabled", False),
        notify_critical_action_fn=_noop_async,
        conversations_dir=None,
        load_conversation_fn=lambda p: {},
        send_whatsapp_message_fn=_noop_async,
        admin_phone="905550000000",
        whatsapp_phone_id="pid",
        whatsapp_token="token",
    )
    app.include_router(router)

    @app.middleware("http")
    async def _inject_user(request, call_next):
        class _User:
            username = "test_admin"
        request.state.user = _User()
        request.state.auth_via_token = True
        return await call_next(request)

    client = TestClient(app)
    resp = client.post("/settings?operational_rules_enabled=false")
    data = resp.json()
    assert data["operational_rules_enabled"] is False

    status_resp = client.get("/automation/status")
    status_data = status_resp.json()
    assert status_data["operational_rules_enabled"] is False


@pytest.mark.unit
def test_settings_update_currency_policy_accepts_json_payload(monkeypatch):
    monkeypatch.setattr(admin_ops_routes, "append_settings_audit_entry", lambda **_kwargs: None)
    state = {
        "automation_enabled": True,
        "followup_enabled": False,
        "operational_rules_enabled": True,
        "followup_minutes": 10,
        "currency_enabled": {"EUR": True, "USD": True, "TRY": True, "GBP": True},
    }

    def load_settings():
        return dict(state)

    def save_settings(new_settings):
        state.update(new_settings)

    async def _noop_async(*args, **kwargs):
        return True

    app = FastAPI()
    router = build_admin_ops_router(
        load_settings_fn=load_settings,
        save_settings_fn=save_settings,
        is_automation_enabled_fn=lambda: state.get("automation_enabled", True),
        is_followup_enabled_fn=lambda: state.get("followup_enabled", False),
        notify_critical_action_fn=_noop_async,
        conversations_dir=None,
        load_conversation_fn=lambda p: {},
        send_whatsapp_message_fn=_noop_async,
        admin_phone="905550000000",
        whatsapp_phone_id="pid",
        whatsapp_token="token",
    )
    app.include_router(router)

    @app.middleware("http")
    async def _inject_user(request, call_next):
        class _User:
            username = "test_admin"
        request.state.user = _User()
        request.state.auth_via_token = True
        return await call_next(request)

    client = TestClient(app)
    resp = client.post('/settings?currency_enabled_json={"EUR":true,"USD":false,"TRY":true,"GBP":false}')
    data = resp.json()
    assert data["currency_enabled"] == {"EUR": True, "USD": False, "TRY": True, "GBP": False}


@pytest.mark.unit
def test_settings_update_currency_policy_rejects_invalid_json(monkeypatch):
    monkeypatch.setattr(admin_ops_routes, "append_settings_audit_entry", lambda **_kwargs: None)
    state = {
        "automation_enabled": True,
        "followup_enabled": False,
        "operational_rules_enabled": True,
        "followup_minutes": 10,
        "currency_enabled": {"EUR": True, "USD": True, "TRY": True, "GBP": True},
    }

    def load_settings():
        return dict(state)

    def save_settings(new_settings):
        state.update(new_settings)

    async def _noop_async(*args, **kwargs):
        return True

    app = FastAPI()
    router = build_admin_ops_router(
        load_settings_fn=load_settings,
        save_settings_fn=save_settings,
        is_automation_enabled_fn=lambda: state.get("automation_enabled", True),
        is_followup_enabled_fn=lambda: state.get("followup_enabled", False),
        notify_critical_action_fn=_noop_async,
        conversations_dir=None,
        load_conversation_fn=lambda p: {},
        send_whatsapp_message_fn=_noop_async,
        admin_phone="905550000000",
        whatsapp_phone_id="pid",
        whatsapp_token="token",
    )
    app.include_router(router)

    @app.middleware("http")
    async def _inject_user(request, call_next):
        class _User:
            username = "test_admin"
        request.state.user = _User()
        request.state.auth_via_token = True
        return await call_next(request)

    client = TestClient(app)
    resp = client.post("/settings?currency_enabled_json={invalid}")
    data = resp.json()
    assert data["success"] is False
    assert "gecersiz JSON" in data["error"]
