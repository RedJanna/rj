from __future__ import annotations

from fastapi import APIRouter


def build_followup_router(
    *,
    is_followup_enabled_fn,
    get_pending_followups_fn,
    send_whatsapp_message_fn,
    get_followup_message_fn,
    mark_followup_sent_fn,
    mark_followup_closed_fn,
    get_expired_followups_fn,
    save_last_followup_cycle_fn,
    save_message_fn,
    schedule_conversation_cleanup_fn,
    followup_grace_seconds: int,
    followup_max_age_minutes: int,
    load_followups_fn,
    save_followups_fn,
    get_followup_minutes_fn,
):
    router = APIRouter()

    @router.post("/check-followups")
    async def check_followups():
        if not is_followup_enabled_fn():
            return {"status": "followup_disabled", "sent": 0}
        pending = get_pending_followups_fn()
        sent_count = 0
        for phone in pending:
            success = await send_whatsapp_message_fn(phone, get_followup_message_fn())
            if success:
                mark_followup_sent_fn(phone)
                save_message_fn(phone, "[FOLLOW-UP]", get_followup_message_fn())
                sent_count += 1
                print(f"✅ Follow-up gönderildi: {phone}")
        # 30 dk yanıt yoksa otomatik kapat/temizle
        expired = get_expired_followups_fn()
        closed_count = 0
        for phone in expired:
            try:
                schedule_conversation_cleanup_fn(phone, delay_minutes=0)
                mark_followup_closed_fn(phone)
                closed_count += 1
                print(f"🧹 Sohbet otomatik kapatıldı/temizlendi: {phone}")
            except Exception as e:
                print(f"❌ Otomatik kapatma hatası ({phone}): {e}")
        save_last_followup_cycle_fn(sent_count, closed_count)
        return {
            "status": "ok",
            "sent": sent_count,
            "closed": closed_count,
            "pending_processed": len(pending),
            "grace_seconds": followup_grace_seconds,
            "max_age_minutes": followup_max_age_minutes,
        }

    @router.post("/admin/followups/clear-all")
    async def clear_all_followups():
        data = load_followups_fn()
        count = len(data.get("pending", {}))
        save_followups_fn({"pending": {}})
        return {"status": "ok", "cleared": count}

    @router.get("/admin/followups/pending")
    async def get_pending_followups_list():
        data = load_followups_fn()
        return {
            "pending_count": len(data.get("pending", {})),
            "pending": data.get("pending", {}),
            "last_cycle": data.get("last_cycle", {}),
            "settings": {
                "grace_seconds": followup_grace_seconds,
                "max_age_minutes": followup_max_age_minutes,
                "followup_minutes": get_followup_minutes_fn(),
            },
        }

    return router
