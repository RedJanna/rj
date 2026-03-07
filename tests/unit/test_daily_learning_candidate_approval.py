from __future__ import annotations

import json
from datetime import datetime

from app.services import daily_learning_report_service as dls


def _write_jsonl(path, rows):
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")


def test_generate_draft_then_final_approve_integrates_external_files(tmp_path, monkeypatch):
    now = datetime(2026, 3, 3, 10, 30, 0)
    queue_file = tmp_path / "active_learning_queue.jsonl"
    _write_jsonl(
        queue_file,
        [
            {
                "ts": now.isoformat(),
                "message": "odada elektrikli scooter sarj edebilir miyim",
                "predicted_intent": "OUT_OF_SCOPE_OTHER",
                "confidence": 0.21,
                "reason": "low_confidence_below_auto_threshold",
                "lang": "tr",
            }
        ],
    )

    review_file = tmp_path / "scenario_review_queue.json"
    external_file = tmp_path / "external_scenarios.json"
    intent_examples_file = tmp_path / "scenario_intent_examples.json"
    draft_template_file = tmp_path / "senaryo_template_ornek.txt"
    draft_template_file.write_text("SENARYO TASLAK TEMPLATE", encoding="utf-8")
    drafts_dir = tmp_path / "yeni_senaryolar"

    monkeypatch.setattr(dls, "ACTIVE_LEARNING_FILE", queue_file)
    monkeypatch.setattr(dls, "TOPIC_REVIEW_FILE", review_file)
    monkeypatch.setattr(dls, "EXTERNAL_SCENARIOS_FILE", external_file)
    monkeypatch.setattr(dls, "INTENT_EXAMPLES_FILE", intent_examples_file)
    monkeypatch.setattr(dls, "SCENARIO_DRAFT_TEMPLATE_PATH", draft_template_file)
    monkeypatch.setattr(dls, "NEW_SCENARIOS_DIR", drafts_dir)
    monkeypatch.setattr(dls, "_refresh_intent_examples_cache", lambda: None)
    monkeypatch.setattr(
        dls,
        "_generate_scenario_text_with_gpt52",
        lambda **kwargs: "TASLAK SENARYO\nSlot 1: Tarih\nSlot 2: Kisi",
    )

    dls.sync_daily_topic_candidates(now=now)
    pending = dls.list_topic_candidates(status="pending", limit=10)
    assert len(pending) == 1

    candidate_id = pending[0]["candidate_id"]
    draft_result = dls.request_topic_candidate_draft(candidate_id, requested_by="tester", now=now)
    assert draft_result["success"] is True
    assert draft_result["draft_revision"] == 1
    assert draft_result["draft_model"] == "gpt-5.2"

    draft_path = drafts_dir / f"{candidate_id}_rev1.txt"
    assert draft_path.exists()
    assert "TASLAK SENARYO" in draft_path.read_text(encoding="utf-8")

    final_result = dls.finalize_topic_candidate_approval(candidate_id, approved_by="tester", now=now)
    assert final_result["success"] is True
    assert final_result["external_scenario_id"].startswith("al_")

    review_payload = json.loads(review_file.read_text(encoding="utf-8"))
    assert review_payload["items"][0]["status"] == "approved"
    assert review_payload["items"][0]["approved_by"] == "tester"
    assert review_payload["items"][0]["draft_model"] == "gpt-5.2"

    external_payload = json.loads(external_file.read_text(encoding="utf-8"))
    scenarios = external_payload.get("scenarios", [])
    assert len(scenarios) == 1
    assert scenarios[0]["question"] == "odada elektrikli scooter sarj edebilir miyim"
    assert scenarios[0]["intent"] == "OUT_OF_SCOPE_OTHER"

    intent_payload = json.loads(intent_examples_file.read_text(encoding="utf-8"))
    examples = intent_payload.get("intent_examples", {}).get("OUT_OF_SCOPE_OTHER", [])
    assert "odada elektrikli scooter sarj edebilir miyim" in examples


def test_draft_generation_is_reusable_and_redraft_increments_revision(tmp_path, monkeypatch):
    now = datetime(2026, 3, 3, 11, 0, 0)
    queue_file = tmp_path / "active_learning_queue.jsonl"
    _write_jsonl(
        queue_file,
        [
            {
                "ts": now.isoformat(),
                "message": "otelde drone iniş alanı var mı",
                "predicted_intent": "OUT_OF_SCOPE_OTHER",
                "confidence": 0.19,
                "reason": "novel_topic_out_of_scope",
                "lang": "tr",
            }
        ],
    )

    monkeypatch.setattr(dls, "ACTIVE_LEARNING_FILE", queue_file)
    monkeypatch.setattr(dls, "TOPIC_REVIEW_FILE", tmp_path / "scenario_review_queue.json")
    monkeypatch.setattr(dls, "EXTERNAL_SCENARIOS_FILE", tmp_path / "external_scenarios.json")
    monkeypatch.setattr(dls, "INTENT_EXAMPLES_FILE", tmp_path / "scenario_intent_examples.json")
    monkeypatch.setattr(dls, "SCENARIO_DRAFT_TEMPLATE_PATH", tmp_path / "senaryo_template_ornek.txt")
    monkeypatch.setattr(dls, "NEW_SCENARIOS_DIR", tmp_path / "yeni_senaryolar")
    monkeypatch.setattr(dls, "_refresh_intent_examples_cache", lambda: None)

    call_counter = {"n": 0}

    def _fake_generator(**kwargs):
        call_counter["n"] += 1
        return f"DRAFT V{call_counter['n']}"

    monkeypatch.setattr(dls, "_generate_scenario_text_with_gpt52", _fake_generator)

    dls.sync_daily_topic_candidates(now=now)
    candidate_id = dls.list_topic_candidates(status="pending", limit=1)[0]["candidate_id"]

    first = dls.request_topic_candidate_draft(candidate_id, requested_by="tester", now=now)
    second = dls.request_topic_candidate_draft(candidate_id, requested_by="tester", now=now)
    redraft = dls.request_topic_candidate_draft(candidate_id, requested_by="tester", now=now, force_regenerate=True)

    assert first["success"] is True
    assert second["success"] is True
    assert second["already_generated"] is True
    assert redraft["success"] is True
    assert redraft["draft_revision"] == 2

    draft_payload = json.loads((tmp_path / "scenario_review_queue.json").read_text(encoding="utf-8"))
    assert draft_payload["items"][0]["status"] == "draft_ready"

    final = dls.finalize_topic_candidate_approval(candidate_id, approved_by="tester", now=now)
    assert final["success"] is True
    assert call_counter["n"] == 2


def test_ingest_drafts_is_one_time_and_skips_duplicates(tmp_path, monkeypatch):
    now = datetime(2026, 3, 3, 12, 0, 0)
    queue_file = tmp_path / "active_learning_queue.jsonl"
    _write_jsonl(
        queue_file,
        [
            {
                "ts": now.isoformat(),
                "message": "evcil hayvan kabul ediyor musunuz",
                "predicted_intent": "LOCAL_FAQ_INFO",
                "confidence": 0.41,
                "reason": "low_confidence_below_auto_threshold",
                "lang": "tr",
            }
        ],
    )

    review_file = tmp_path / "scenario_review_queue.json"
    external_file = tmp_path / "external_scenarios.json"
    intent_examples_file = tmp_path / "scenario_intent_examples.json"
    ingest_state_file = tmp_path / "scenario_draft_ingest_state.json"
    draft_template_file = tmp_path / "senaryo_template_ornek.txt"
    draft_template_file.write_text("SENARYO TASLAK TEMPLATE", encoding="utf-8")
    drafts_dir = tmp_path / "yeni_senaryolar"

    monkeypatch.setattr(dls, "ACTIVE_LEARNING_FILE", queue_file)
    monkeypatch.setattr(dls, "TOPIC_REVIEW_FILE", review_file)
    monkeypatch.setattr(dls, "EXTERNAL_SCENARIOS_FILE", external_file)
    monkeypatch.setattr(dls, "INTENT_EXAMPLES_FILE", intent_examples_file)
    monkeypatch.setattr(dls, "SCENARIO_DRAFT_TEMPLATE_PATH", draft_template_file)
    monkeypatch.setattr(dls, "NEW_SCENARIOS_DIR", drafts_dir)
    monkeypatch.setattr(dls, "SCENARIO_INGEST_STATE_FILE", ingest_state_file)
    monkeypatch.setattr(dls, "_refresh_intent_examples_cache", lambda: None)
    monkeypatch.setattr(dls, "_generate_scenario_text_with_gpt52", lambda **kwargs: "DRAFT CONTENT")

    dls.sync_daily_topic_candidates(now=now)
    candidate_id = dls.list_topic_candidates(status="pending", limit=1)[0]["candidate_id"]
    draft = dls.request_topic_candidate_draft(candidate_id, requested_by="tester", now=now)
    assert draft["success"] is True

    first = dls.ingest_new_scenario_drafts(approved_by="tester", now=now)
    assert first["success"] is True
    assert first["integrated_count"] == 1
    assert first["skipped_count"] == 0

    second = dls.ingest_new_scenario_drafts(approved_by="tester", now=now)
    assert second["success"] is True
    assert second["integrated_count"] == 0
    assert second["skipped_count"] == 1
    assert any(r.get("status") == "skipped_already_processed" for r in second["results"])

    duplicate_file = drafts_dir / f"{candidate_id}_rev99.txt"
    duplicate_file.write_text((drafts_dir / f"{candidate_id}_rev1.txt").read_text(encoding="utf-8"), encoding="utf-8")
    third = dls.ingest_new_scenario_drafts(approved_by="tester", now=now)
    assert third["success"] is True
    assert third["integrated_count"] == 0
    assert any(r.get("status") == "skipped_duplicate_content" for r in third["results"])


def test_render_required_slots_section_uses_intent_contract_for_price_query():
    section = dls._render_required_slots_section("PRICE_QUERY")
    assert "📥 Gerekli Bilgiler (Slotlar - En Fazla 5):" in section
    assert "Giriş Tarihi" in section
    assert "Çıkış Tarihi" in section
    assert "Yetişkin Sayısı" in section
    assert "sistem normalize eder" in section


def test_enforce_required_slots_section_replaces_wrong_slot_block():
    draft = (
        "📋 Senaryo: Test\n\n"
        "📥 Gerekli Bilgiler (Slotlar - En Fazla 5):\n"
        "1) Telefon: (zorunlu)\n"
        "2) E-posta: (zorunlu)\n\n"
        "⚙️ Karar Kuralı (Business Logic):\n"
        "- test\n"
    )
    patched = dls._enforce_required_slots_section(draft, "PRICE_QUERY")
    assert "Telefon: (zorunlu)" not in patched
    assert "E-posta: (zorunlu)" not in patched
    assert "Giriş Tarihi" in patched
    assert "Çıkış Tarihi" in patched
    assert "Yetişkin Sayısı" in patched
