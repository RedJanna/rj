from __future__ import annotations

from datetime import datetime

from app.services.handoff_policy_service import apply_handoff_policy
from app.services.handoff_policy_service import is_within_handoff_business_hours


def test_handoff_policy_hard_trigger_priority_floor():
    policy = apply_handoff_policy("acil_durum", "low")
    assert policy["trigger_type"] == "hard"
    # hard category should never stay low
    assert policy["effective_priority"] in {"high", "critical"}
    assert int(policy["sla_target_minutes"]) <= 10


def test_handoff_policy_soft_trigger_default():
    policy = apply_handoff_policy("fiyat_handoff", "low")
    assert policy["trigger_type"] == "soft"
    assert policy["effective_priority"] in {"medium", "high", "critical"}
    assert int(policy["sla_target_minutes"]) >= 20


def test_business_hours_window_spans_midnight():
    assert is_within_handoff_business_hours(datetime(2026, 2, 24, 23, 0, 0)) is True
    assert is_within_handoff_business_hours(datetime(2026, 2, 25, 1, 30, 0)) is True
    assert is_within_handoff_business_hours(datetime(2026, 2, 25, 3, 0, 0)) is False
