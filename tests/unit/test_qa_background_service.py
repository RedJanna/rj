from __future__ import annotations

import pytest

import app.services.qa_background_service as qa_bg


class _ImmediateThread:
    def __init__(self, target, daemon=True):
        self._target = target
        self.daemon = daemon

    def start(self):
        self._target()


class _StubQAAgent:
    def __init__(self, evaluation: dict):
        self._evaluation = evaluation

    async def evaluate(self, user_message: str, bot_reply: str, phone: str):
        return self._evaluation


def _patch_sync_thread(monkeypatch):
    monkeypatch.setattr(qa_bg.threading, "Thread", _ImmediateThread)
    monkeypatch.setattr(qa_bg, "record_metric", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr(qa_bg, "log_event", lambda *_args, **_kwargs: None)


@pytest.mark.unit
def test_qa_background_does_not_notify_for_pass(monkeypatch):
    _patch_sync_thread(monkeypatch)
    sent_messages: list[str] = []

    async def _send(_phone, message):
        sent_messages.append(message)

    qa_bg.maybe_start_qa_background(
        qa_enabled=True,
        qa_agent=_StubQAAgent(
            {
                "decision": "PASS",
                "overall_score": 4.6,
                "scores": {"groundedness": 4.5, "correctness": 4.7, "completeness": 4.5, "clarity": 4.7},
                "issues": [],
                "suggestions": [],
                "hallucinations": [],
            }
        ),
        user_message="Havuz var mı?",
        reply="Evet, havuzumuz mevcut.",
        phone="905500000001",
        admin_phone="905500000999",
        send_whatsapp_message_fn=_send,
        qa_fail_notifications=[],
    )

    assert sent_messages == []


@pytest.mark.unit
def test_qa_background_does_not_notify_for_normal_review(monkeypatch):
    _patch_sync_thread(monkeypatch)
    sent_messages: list[str] = []

    async def _send(_phone, message):
        sent_messages.append(message)

    qa_bg.maybe_start_qa_background(
        qa_enabled=True,
        qa_agent=_StubQAAgent(
            {
                "decision": "REVIEW",
                "overall_score": 3.2,
                "scores": {"groundedness": 3.0, "correctness": 3.0, "completeness": 3.5, "clarity": 3.3},
                "issues": ["Cevap biraz kısa"],
                "suggestions": ["Detay artırılabilir"],
                "hallucinations": [],
            }
        ),
        user_message="Check-in saati?",
        reply="14:00 sonrası giriş yapabilirsiniz.",
        phone="905500000001",
        admin_phone="905500000999",
        send_whatsapp_message_fn=_send,
        qa_fail_notifications=[],
    )

    assert sent_messages == []


@pytest.mark.unit
def test_qa_background_sends_critical_notification_for_hallucination(monkeypatch):
    _patch_sync_thread(monkeypatch)
    sent_messages: list[str] = []

    async def _send(_phone, message):
        sent_messages.append(message)

    qa_bg.maybe_start_qa_background(
        qa_enabled=True,
        qa_agent=_StubQAAgent(
            {
                "decision": "FAIL",
                "overall_score": 1.8,
                "scores": {"groundedness": 1.5, "correctness": 1.0, "completeness": 2.0, "clarity": 2.7},
                "issues": ["Yanlış fiyat bilgisi verildi"],
                "suggestions": ["Sadece doğrulanmış fiyat bilgisini kullan"],
                "hallucinations": ["Sistemde olmayan fiyat uyduruldu"],
            }
        ),
        user_message="20-22 Mayıs fiyat nedir?",
        reply="Toplam 100 EUR.",
        phone="905500000111",
        admin_phone="905500000999",
        send_whatsapp_message_fn=_send,
        qa_fail_notifications=[],
    )

    assert len(sent_messages) == 1
    assert "QA CRITICAL UYARISI" in sent_messages[0]
    assert "Halüsinasyon" in sent_messages[0]


@pytest.mark.unit
def test_qa_background_deduplicates_same_alert(monkeypatch):
    _patch_sync_thread(monkeypatch)
    sent_messages: list[str] = []
    notification_state: list = []
    evaluation = {
        "decision": "FAIL",
        "overall_score": 2.0,
        "scores": {"groundedness": 2.0, "correctness": 2.0, "completeness": 2.0, "clarity": 2.0},
        "issues": ["Eksik bilgi"],
        "suggestions": ["Cevabı tamamla"],
        "hallucinations": [],
    }

    async def _send(_phone, message):
        sent_messages.append(message)

    qa_bg.maybe_start_qa_background(
        qa_enabled=True,
        qa_agent=_StubQAAgent(evaluation),
        user_message="Kahvaltı dahil mi?",
        reply="Evet.",
        phone="905500000111",
        admin_phone="905500000999",
        send_whatsapp_message_fn=_send,
        qa_fail_notifications=notification_state,
    )
    qa_bg.maybe_start_qa_background(
        qa_enabled=True,
        qa_agent=_StubQAAgent(evaluation),
        user_message="Kahvaltı dahil mi?",
        reply="Evet.",
        phone="905500000111",
        admin_phone="905500000999",
        send_whatsapp_message_fn=_send,
        qa_fail_notifications=notification_state,
    )

    assert len(sent_messages) == 1
