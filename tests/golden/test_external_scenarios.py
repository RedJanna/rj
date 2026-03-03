"""
External Golden Scenario Tests
==============================

Dış kaynaktan entegre edilen senaryolar için opsiyonel regresyon paketi.
Varsayılan pipeline'ı uzatmamak için sadece GOLDEN_EXTERNAL=1 iken çalışır.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


EXTERNAL_FILE = Path(__file__).parent / "scenarios" / "external_scenarios.json"


def _enabled() -> bool:
    return (os.getenv("GOLDEN_EXTERNAL", "0").strip().lower() in {"1", "true", "yes", "on"})


def _load_external_scenarios() -> list[dict]:
    if not EXTERNAL_FILE.exists():
        return []
    try:
        payload = json.loads(EXTERNAL_FILE.read_text(encoding="utf-8"))
        scenarios = payload.get("scenarios", [])
        if isinstance(scenarios, list):
            return scenarios
    except Exception:
        return []
    return []


def _reset_phone_state(phone: str) -> None:
    try:
        from app.services.conversation_store import purge_phone_data

        purge_phone_data(phone)
        return
    except Exception:
        pass
    try:
        from app.services.booking_flow_service import clear_booking_flow
        from app.services.conversation_store import clear_conversation
        from app.services.price_flow_service import clear_price_flow
        from app.services.restaurant_reservation_flow_service import clear_reservation_flow

        clear_conversation(phone)
        clear_reservation_flow(phone)
        clear_price_flow(phone)
        clear_booking_flow(phone)
    except Exception:
        pass


@pytest.fixture(scope="module")
def bot_client():
    os.environ["FLOW_ORCHESTRATOR_MODE"] = "off"
    os.environ.setdefault("OPENAI_API_KEY", "test-key")
    os.environ.setdefault("WHATSAPP_PHONE_ID", "test-phone")
    os.environ.setdefault("WHATSAPP_TOKEN", "test-token")

    from fastapi.testclient import TestClient
    import kassandra_openai_bot as bot

    bot.send_whatsapp_message = AsyncMock(return_value=True)
    if hasattr(bot, "QA_ENABLED"):
        bot.QA_ENABLED = False

    return TestClient(bot.app)


@pytest.mark.golden
@pytest.mark.external
@pytest.mark.skipif(not _enabled(), reason="Set GOLDEN_EXTERNAL=1 to run external scenario suite")
@pytest.mark.parametrize("scenario", _load_external_scenarios(), ids=lambda s: s.get("id", "unknown"))
def test_external_scenario_reply_sanity(bot_client, scenario: dict):
    phone = f"9055577{abs(hash(scenario.get('id', 'x'))) % 100000:05d}"
    _reset_phone_state(phone)

    response = bot_client.post(
        "/chat",
        json={"phone": phone, "message": scenario.get("question", ""), "coalesce_mode": "immediate"},
    )

    assert response.status_code == 200
    body = response.json()
    reply = str(body.get("reply") or "").strip()
    status = str(body.get("status") or "")

    assert reply, f"empty reply for {scenario.get('id')}"
    assert status not in {"error"}, f"unexpected error status for {scenario.get('id')}: {body}"
