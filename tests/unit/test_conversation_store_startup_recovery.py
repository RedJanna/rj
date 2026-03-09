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


def test_get_conversation_history_clears_stale_ram_when_disk_conversation_expired(monkeypatch):
    phone = "905500022233"
    old_iso = (datetime.now() - timedelta(minutes=cs.HISTORY_EXPIRY_MINUTES + 5)).isoformat()

    cs.conversation_history[phone] = [
        {"role": "assistant", "content": "Restoran rezervasyonu için adım adım ilerleyeceğiz."}
    ]
    cs.last_activity[phone] = datetime.now()
    cs.recovered_active_phones.add(phone)

    monkeypatch.setattr(
        cs,
        "load_conversation",
        lambda _p: {
            "phone": phone,
            "messages": [{"user_message": "eski", "bot_reply": "eski"}],
            "updated_at": old_iso,
        },
    )

    history = cs.get_conversation_history(phone)

    assert history == []
    assert phone not in cs.conversation_history
    assert phone not in cs.last_activity
    assert phone not in cs.recovered_active_phones


def test_save_message_clears_runtime_state_when_history_expired(monkeypatch):
    phone = "905500033344"
    old_iso = (datetime.now() - timedelta(minutes=cs.HISTORY_EXPIRY_MINUTES + 5)).isoformat()
    saved_payloads: list[dict] = []
    cleanup_calls: list[str] = []

    class _Repo:
        def save_dict(self, payload):
            saved_payloads.append(payload)

    monkeypatch.setattr(
        cs,
        "load_conversation",
        lambda _p: {
            "phone": phone,
            "messages": [{"user_message": "eski", "bot_reply": "eski"}],
            "created_at": old_iso,
            "updated_at": old_iso,
        },
    )
    monkeypatch.setattr(cs, "_conversation_repo", lambda _p: _Repo())
    monkeypatch.setattr(cs, "_clear_runtime_state_for_fresh_conversation", lambda p: cleanup_calls.append(p))

    cs.save_message(phone, "Merhaba", "Hoş geldiniz")

    assert cleanup_calls == [phone]
    assert len(saved_payloads) == 1
    assert len(saved_payloads[0]["messages"]) == 1
    assert saved_payloads[0]["messages"][0]["user_message"] == "Merhaba"
