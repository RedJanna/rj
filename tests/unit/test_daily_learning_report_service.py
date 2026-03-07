from __future__ import annotations

import json
from datetime import datetime

from app.services import daily_learning_report_service as dls


def test_build_daily_learning_report_with_novel_topic(tmp_path, monkeypatch):
    queue_file = tmp_path / "active_learning_queue.jsonl"
    today = datetime.now().isoformat()
    row = {
        "ts": today,
        "message": "odada elektrikli araba sarj noktasi var mi",
        "predicted_intent": "OUT_OF_SCOPE_OTHER",
        "confidence": 0.31,
        "reason": "low_confidence_below_auto_threshold",
        "lang": "tr",
    }
    queue_file.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

    template_file = tmp_path / "Senaryo template.txt"
    template_file.write_text(
        "Senaryo Başlığı: {topic_title}\nÖrnek Mesaj: {sample_message}\nNeden: {reason}\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(dls, "ACTIVE_LEARNING_FILE", queue_file)
    monkeypatch.setattr(dls, "SCENARIO_TEMPLATE_PATH", template_file)
    monkeypatch.setattr(dls, "TOPIC_REVIEW_FILE", tmp_path / "scenario_review_queue.json")
    monkeypatch.setattr(dls, "EXTERNAL_SCENARIOS_FILE", tmp_path / "external_scenarios.json")
    monkeypatch.setattr(dls, "INTENT_EXAMPLES_FILE", tmp_path / "scenario_intent_examples.json")

    report = dls.build_daily_learning_report()
    assert "Günlük Öğrenme Raporu" in report
    assert "elektrikli araba sarj" in report
    assert "Senaryo Başlığı" in report
    assert "Aday ID: al-" in report


def test_build_daily_learning_report_without_topic(tmp_path, monkeypatch):
    queue_file = tmp_path / "active_learning_queue.jsonl"
    queue_file.write_text("", encoding="utf-8")
    monkeypatch.setattr(dls, "ACTIVE_LEARNING_FILE", queue_file)
    monkeypatch.setattr(dls, "TOPIC_REVIEW_FILE", tmp_path / "scenario_review_queue.json")
    monkeypatch.setattr(dls, "EXTERNAL_SCENARIOS_FILE", tmp_path / "external_scenarios.json")
    monkeypatch.setattr(dls, "INTENT_EXAMPLES_FILE", tmp_path / "scenario_intent_examples.json")

    report = dls.build_daily_learning_report()
    assert "Yeni/farklı konu algılanmadı" in report
