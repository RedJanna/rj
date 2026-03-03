from __future__ import annotations

from app.routes.metrics_routes import get_success_scorecard
from app.routes.metrics_routes import get_success_targets


def test_success_targets_route_shape():
    payload = get_success_targets()
    assert "targets" in payload
    assert "containment_rate" in payload["targets"]


def test_success_scorecard_route_uses_service(monkeypatch):
    monkeypatch.setattr(
        "app.routes.metrics_routes.evaluate_success_scorecard",
        lambda days=7: {"days": days, "event_total": 0, "metrics": {}},
    )
    payload = get_success_scorecard(days=14)
    assert payload["days"] == 14
    assert payload["event_total"] == 0
