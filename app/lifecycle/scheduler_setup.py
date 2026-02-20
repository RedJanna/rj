from __future__ import annotations

import asyncio


def register_scheduler_lifecycle(
    *,
    app,
    scheduler,
    init_reservations_db_fn,
    init_hotel_bookings_db_fn,
    init_cancel_service_fn,
    load_conversation_fn,
    save_conversation_fn,
    send_whatsapp_message_fn,
    admin_phone: str,
    cancel_reservation_fn,
    get_reservation_fn,
    get_customer_reservations_fn,
    reservation_status,
    process_due_reminders_fn,
):
    @app.on_event("startup")
    async def startup_event():
        init_reservations_db_fn()
        init_hotel_bookings_db_fn()
        scheduler.start()
        init_cancel_service_fn(
            load_conversation=load_conversation_fn,
            save_conversation=save_conversation_fn,
            send_whatsapp_message=send_whatsapp_message_fn,
            ADMIN_PHONE=admin_phone,
            cancel_reservation=cancel_reservation_fn,
            get_reservation=get_reservation_fn,
            get_customer_reservations=get_customer_reservations_fn,
            ReservationStatus=reservation_status,
        )
        print("✅ Scheduler başlatıldı:")
        print("   🧹 Stale flow temizliği: Her 1 saatte")
        print("   📨 Rezervasyon hatırlatma: Her 5 dakikada")
        print("   📊 Dashboard: /admin/dashboard")

    @app.on_event("shutdown")
    async def shutdown_event():
        scheduler.shutdown()
        print("🛑 Scheduler durduruldu")

    async def check_due_reminders():
        try:
            await process_due_reminders_fn(send_whatsapp_message_fn)
        except Exception as e:
            print(f"❌ Hatırlatma kontrol hatası: {e}")

    def run_reminder_check():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(check_due_reminders())
            loop.close()
        except Exception as e:
            print(f"❌ Reminder check runner hatası: {e}")

    scheduler.add_job(run_reminder_check, "interval", minutes=1, id="reminder_check_job")
