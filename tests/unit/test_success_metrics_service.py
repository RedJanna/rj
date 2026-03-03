from __future__ import annotations

from app.services.success_metrics_service import evaluate_success_scorecard


def test_success_scorecard_computes_rates(monkeypatch):
    rows = [
        {"event": "openai", "response_time": 1.2},
        {"event": "local", "response_time": 0.8},
        {"event": "handoff", "response_time": 2.3},
        {"event": "clarify_loop", "response_time": 1.0},
        {"event": "handoff.false_positive", "response_time": 1.1},
        {"event": "auto.false_positive", "response_time": 0.9},
    ]

    monkeypatch.setattr(
        "app.services.success_metrics_service.list_events",
        lambda days=7, limit=10_000, offset=0: (rows, len(rows)),
    )
    data = evaluate_success_scorecard(days=7)

    assert data["event_total"] == 6
    assert data["counts"]["auto"] == 2
    assert data["counts"]["handoff"] >= 2
    assert data["metrics"]["containment_rate"]["actual"] is not None
    assert data["metrics"]["p95_response_time_seconds"]["actual"] is not None
