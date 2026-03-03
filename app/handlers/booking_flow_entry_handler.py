from __future__ import annotations

import os
import time

PUBLIC_BASE_URL = (os.getenv("PUBLIC_BASE_URL") or "https://api.nexlumeai.com").rstrip("/")


async def try_handle_booking_flow_entry(
    *,
    phone: str,
    user_message: str,
    history: list,
    start_time: float,
    detect_language_fn,
    handle_booking_flow_fn,
    add_to_history_fn,
    save_message_fn,
    record_metric_fn,
    send_whatsapp_message_fn,
    admin_phone: str,
    response_factory,
):
    try:
        booking_result = await handle_booking_flow_fn(phone, user_message, history=history, lang=detect_language_fn(user_message))
        if booking_result is None:
            return None

        bf_reply = booking_result.get("reply", "")
        bf_status = booking_result.get("status", "booking_flow")
        bf_log = booking_result.get("log")
        if not bf_reply:
            return None

        add_to_history_fn(phone, "user", user_message)
        add_to_history_fn(phone, "assistant", bf_reply)
        save_message_fn(phone, user_message, bf_reply)
        elapsed = time.time() - start_time
        record_metric_fn("booking_flow", category=bf_status, response_time=elapsed)

        if bf_status == "booking_pending_approval":
            try:
                bd = booking_result.get("booking_data", {})
                bid = booking_result.get("booking_id", "?")
                guest_name = f"{bd.get('guest_first_name', '')} {bd.get('guest_last_name', '')}".strip()
                price = bd.get("discounted_price") or bd.get("total_price", 0)
                refund_txt = "Ücretsiz İptal" if bd.get("is_refundable") else "İade yapılmaz"
                # Cocuk bilgisi
                child_ages = bd.get("child_ages", [])
                child_txt = ""
                if child_ages:
                    ages_str = ", ".join(f"{a} yaş" for a in child_ages)
                    child_txt = f" + {len(child_ages)} çocuk ({ages_str})"
                admin_msg = (
                    f"🏨 *YENi OTEL REZ TALEBi*\n\n"
                    f"📋 Talep #{bid}\n"
                    f"📱 Müşteri: {phone}\n"
                    f"👤 Misafir: {guest_name}\n"
                    f"📅 {bd.get('check_in', '')} → {bd.get('check_out', '')}\n"
                    f"🌙 {bd.get('nights', 0)} gece\n"
                    f"🛏️ {bd.get('room_type_display', bd.get('room_type', ''))}\n"
                    f"💰 {price} {bd.get('currency', 'EUR')} ({refund_txt})\n"
                    f"👥 {bd.get('adult_count', 0)} yetişkin{child_txt}\n\n"
                    f"👉 Admin panel: {PUBLIC_BASE_URL}/admin/hotel-bookings-page"
                )
                await send_whatsapp_message_fn(admin_phone, admin_msg)
            except Exception as notify_err:
                print(f"[BOOKING] Admin bildirim hatasi: {notify_err}")

        return response_factory(reply=bf_reply, reservation_log=bf_log, status=bf_status)
    except Exception as e:
        print(f"Booking flow handler hatasi: {e}")
        return None
