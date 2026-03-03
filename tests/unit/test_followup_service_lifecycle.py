from __future__ import annotations

import importlib
from datetime import datetime, timedelta

import pytest


@pytest.fixture
def followup_module(tmp_path, monkeypatch):
    followup_file = tmp_path / "followups.test.json"
    monkeypatch.setenv("KASSANDRA_FOLLOWUP_FILE", str(followup_file))
    import app.services.followup_service as fs

    return importlib.reload(fs)


def test_get_pending_followups_returns_due_reminder(followup_module):
    fs = followup_module
    now = datetime.now()
    phone = "905551111111"
    fs.save_followups(
        {
            "pending": {
                phone: {
                    "scheduled_at": (now - timedelta(minutes=5)).isoformat(),
                    "send_at": (now - timedelta(seconds=30)).isoformat(),
                    "close_at": (now + timedelta(minutes=20)).isoformat(),
                    "last_seen": (now - timedelta(minutes=5)).isoformat(),
                    "sent": False,
                    "reminder_sent": False,
                    "closed": False,
                }
            },
            "settings": {"minutes": 10},
        }
    )

    pending = fs.get_pending_followups()
    assert phone in pending


def test_get_expired_followups_returns_30_minute_idle(followup_module):
    fs = followup_module
    now = datetime.now()
    phone = "905552222222"
    fs.save_followups(
        {
            "pending": {
                phone: {
                    "scheduled_at": (now - timedelta(minutes=40)).isoformat(),
                    "send_at": (now - timedelta(minutes=30)).isoformat(),
                    "close_at": (now - timedelta(seconds=5)).isoformat(),
                    "last_seen": (now - timedelta(minutes=31)).isoformat(),
                    "sent": True,
                    "reminder_sent": True,
                    "closed": False,
                }
            },
            "settings": {"minutes": 10},
        }
    )

    expired = fs.get_expired_followups()
    assert phone in expired
    assert phone not in fs.get_pending_followups()


def test_mark_followup_sent_marks_entry_without_deleting(followup_module):
    fs = followup_module
    phone = "905553333333"
    fs.schedule_followup(phone)

    fs.mark_followup_sent(phone)

    data = fs.load_followups()
    entry = data.get("pending", {}).get(phone)
    assert isinstance(entry, dict)
    assert entry.get("sent") is True
    assert entry.get("reminder_sent") is True
    assert bool(entry.get("reminder_sent_at"))


def test_mark_followup_closed_deletes_entry(followup_module):
    fs = followup_module
    phone = "905554444444"
    fs.schedule_followup(phone)

    fs.mark_followup_closed(phone)

    data = fs.load_followups()
    assert phone not in data.get("pending", {})

