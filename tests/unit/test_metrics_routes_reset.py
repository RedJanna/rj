from __future__ import annotations

import pytest

from app.routes.metrics_routes import reset_metrics_events


@pytest.mark.unit
def test_metrics_reset_endpoint_exists_and_deletes(monkeypatch):
    deleted_calls: list[str] = []

    def _fake_reset(event_prefix: str = "") -> int:
        deleted_calls.append(event_prefix)
        return 7

    monkeypatch.setattr("app.routes.metrics_routes.reset_metrics", _fake_reset)

    data = reset_metrics_events(event_prefix="handoff.packet")
    assert data["status"] == "ok"
    assert data["deleted"] == 7
    assert data["event_prefix"] == "handoff.packet"
    assert deleted_calls == ["handoff.packet"]
