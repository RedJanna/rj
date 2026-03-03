from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes.followup_routes import build_followup_router


def test_check_followups_sends_reminder_and_closes_expired():
    sent_messages: list[tuple[str, str]] = []
    saved_messages: list[tuple[str, str, str]] = []
    cleanup_calls: list[tuple[str, int]] = []
    closed_phones: list[str] = []
    cycle_stats: list[tuple[int, int]] = []

    pending = ["905551111111"]
    expired = ["905552222222"]

    async def send_whatsapp_message(phone: str, message: str) -> bool:
        sent_messages.append((phone, message))
        return True

    def save_message(phone: str, user_message: str, bot_reply: str):
        saved_messages.append((phone, user_message, bot_reply))

    def schedule_cleanup(phone: str, delay_minutes: int = 5):
        cleanup_calls.append((phone, delay_minutes))

    def mark_closed(phone: str):
        closed_phones.append(phone)

    def save_last_cycle(sent: int, closed: int):
        cycle_stats.append((sent, closed))

    app = FastAPI()
    app.include_router(
        build_followup_router(
            is_followup_enabled_fn=lambda: True,
            get_pending_followups_fn=lambda: pending,
            send_whatsapp_message_fn=send_whatsapp_message,
            get_followup_message_fn=lambda: "followup-warning",
            mark_followup_sent_fn=lambda phone: None,
            mark_followup_closed_fn=mark_closed,
            get_expired_followups_fn=lambda: expired,
            save_last_followup_cycle_fn=save_last_cycle,
            save_message_fn=save_message,
            schedule_conversation_cleanup_fn=schedule_cleanup,
            followup_grace_seconds=120,
            followup_max_age_minutes=30,
            load_followups_fn=lambda: {"pending": {}},
            save_followups_fn=lambda _data: None,
            get_followup_minutes_fn=lambda: 10,
        )
    )
    client = TestClient(app)

    response = client.post("/check-followups")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert data["sent"] == 1
    assert data["closed"] == 1
    assert data["pending_processed"] == 1

    assert sent_messages == [("905551111111", "followup-warning")]
    assert saved_messages == [("905551111111", "[FOLLOW-UP]", "followup-warning")]
    assert cleanup_calls == [("905552222222", 0)]
    assert closed_phones == ["905552222222"]
    assert cycle_stats == [(1, 1)]
