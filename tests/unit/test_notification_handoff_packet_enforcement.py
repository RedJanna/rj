from __future__ import annotations

import pytest

from app.services.notification_service import NotificationService


@pytest.mark.asyncio
async def test_notify_admin_handoff_autofills_empty_category(monkeypatch):
    svc = NotificationService(admin_phones=["905551112233"], whatsapp_phone_id="x", whatsapp_token="y")

    async def _fake_send(_message: str, **_kwargs) -> bool:
        return True

    monkeypatch.setattr(svc, "send_whatsapp_admin", _fake_send)
    ok = await svc.notify_admin_handoff(
        category="",
        priority="medium",
        customer_phone="+905551112233",
        customer_message="test",
    )
    assert ok is True


@pytest.mark.asyncio
async def test_notify_admin_handoff_accepts_valid_packet(monkeypatch):
    svc = NotificationService(admin_phones=["905551112233"], whatsapp_phone_id="x", whatsapp_token="y")

    async def _fake_send(_message: str, **_kwargs) -> bool:
        return True

    monkeypatch.setattr(svc, "send_whatsapp_admin", _fake_send)
    ok = await svc.notify_admin_handoff(
        category="canli_destek",
        priority="medium",
        customer_phone="+905551112233",
        customer_message="Canlı desteğe bağlanmak istiyorum",
        detected_intent="HUMAN_AGENT_REQUEST",
        confidence=0.92,
        source="chat_routes",
    )
    assert ok is True


@pytest.mark.asyncio
async def test_notify_admin_handoff_autofill_uses_transfer_category(monkeypatch):
    svc = NotificationService(admin_phones=["905551112233"], whatsapp_phone_id="x", whatsapp_token="y")
    sent_messages: list[str] = []

    async def _fake_send(message: str, **_kwargs) -> bool:
        sent_messages.append(message)
        return True

    monkeypatch.setattr(svc, "send_whatsapp_admin", _fake_send)
    ok = await svc.notify_admin_handoff(
        category="",
        priority="medium",
        customer_phone="+905551112233",
        customer_message="transfer istiyorum",
        source="chat_routes.transfer_flow",
        detected_intent="UNKNOWN",
    )
    assert ok is True
    assert sent_messages
    assert "ANTALYA_TRANSFER" in sent_messages[0]


@pytest.mark.asyncio
async def test_notify_admin_handoff_passes_customer_exclusion(monkeypatch):
    svc = NotificationService(admin_phones=["905551112233", "905551119999"], whatsapp_phone_id="x", whatsapp_token="y")
    captured: dict = {}

    async def _fake_send(_message: str, **kwargs) -> bool:
        captured.update(kwargs)
        return True

    monkeypatch.setattr(svc, "send_whatsapp_admin", _fake_send)
    ok = await svc.notify_admin_handoff(
        category="canli_destek",
        priority="medium",
        customer_phone="+905551112233",
        customer_message="Canlı desteğe bağlanmak istiyorum",
    )
    assert ok is True
    assert "exclude_phones" in captured
    assert "+905551112233" in (captured.get("exclude_phones") or [])


@pytest.mark.asyncio
async def test_notify_admin_handoff_still_sends_when_only_admin_is_customer(monkeypatch):
    svc = NotificationService(admin_phones=["905551112233"], whatsapp_phone_id="x", whatsapp_token="y")
    captured: dict = {}

    async def _fake_send(_message: str, **kwargs) -> bool:
        captured.update(kwargs)
        return True

    monkeypatch.setattr(svc, "send_whatsapp_admin", _fake_send)
    ok = await svc.notify_admin_handoff(
        category="canli_destek",
        priority="high",
        customer_phone="+905551112233",
        customer_message="Lütfen canlı destek",
    )
    assert ok is True
    assert captured.get("exclude_phones") == []
