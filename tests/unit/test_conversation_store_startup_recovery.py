from __future__ import annotations

import json
from datetime import datetime, timedelta

from app.services import conversation_store as cs


def test_hydrate_active_conversations_from_disk_restores_ram(tmp_path, monkeypatch):
    monkeypatch.setattr(cs, "CONVERSATIONS_DIR", tmp_path)
    cs.conversation_history.clear()
    cs.last_activity.clear()
    cs.recovered_active_phones.clear()

    phone = "905551112233"
    payload = {
        "phone": phone,
        "messages": [
            {
                "timestamp": datetime.now().isoformat(),
                "user_message": "Merhaba",
                "bot_reply": "Hoş geldiniz",
            }
        ],
        "updated_at": (datetime.now() - timedelta(days=2)).isoformat(),
    }
    (tmp_path / f"{phone}.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    result = cs.hydrate_active_conversations_from_disk(limit=20)
    assert result["restored"] == 1
    assert phone in cs.conversation_history
    assert phone in cs.last_activity
    assert cs.is_recovered_active_phone(phone) is True


def test_cleanup_conversation_and_flows_does_not_raise_when_flow_clear_fails(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(cs, "clear_conversation", lambda phone: calls.append(f"clear:{phone}"))

    original_import = __import__

    def _fake_import(name, *args, **kwargs):
        if name == "app.services.restaurant_reservation_flow_service":
            raise ImportError("mock import error")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _fake_import)

    cs._cleanup_conversation_and_flows("905500011122")

    assert calls == ["clear:905500011122"]
