import pytest

from app.core import settings_service


@pytest.mark.unit
def test_get_quiet_room_policy_defaults(monkeypatch):
    monkeypatch.setattr(
        settings_service,
        "load_settings",
        lambda: {
            "automation_enabled": True,
            "followup_enabled": False,
            "followup_minutes": 10,
        },
    )
    policy = settings_service.get_quiet_room_policy()
    assert policy["quiet_auto_room_keys"] == ["deluxe", "premium"]
    assert policy["quiet_handoff_room_keys"] == ["superior"]
    assert policy["standard_room_keys"] == ["deluxe", "superior"]


@pytest.mark.unit
def test_get_quiet_room_policy_normalizes_values(monkeypatch):
    monkeypatch.setattr(
        settings_service,
        "load_settings",
        lambda: {
            "quiet_auto_room_keys": ["Deluxe", " premium ", "deluxe"],
            "quiet_handoff_room_keys": [" Superior ", "superior"],
            "standard_room_keys": [" Deluxe ", "deluxe"],
        },
    )
    policy = settings_service.get_quiet_room_policy()
    assert policy["quiet_auto_room_keys"] == ["deluxe", "premium"]
    assert policy["quiet_handoff_room_keys"] == ["superior"]
    assert policy["standard_room_keys"] == ["deluxe"]
