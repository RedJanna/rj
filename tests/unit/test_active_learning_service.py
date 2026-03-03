from __future__ import annotations

import json

from app.services import active_learning_service as als


def test_capture_active_learning_sample_writes_jsonl(tmp_path, monkeypatch):
    out = tmp_path / "active_learning_queue.jsonl"
    monkeypatch.setattr(als, "ACTIVE_LEARNING_FILE", out)

    als.capture_active_learning_sample(
        phone="+905551112233",
        message="fiyat ve musaitlik bakar misiniz",
        stage="router_v2",
        lang="tr",
        predicted_intent="hotel",
        confidence=0.41,
        reason="low_confidence_below_auto_threshold",
        metadata={"scores": {"hotel": 1, "restaurant": 1, "payment": 0}},
    )

    assert out.exists()
    rows = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == 1
    payload = json.loads(rows[0])
    assert payload["label_status"] == "pending"
    assert payload["stage"] == "router_v2"
    assert payload["predicted_intent"] == "hotel"
