from __future__ import annotations

import time


async def try_handle_price_flow_entry(
    *,
    phone: str,
    user_message: str,
    history: list,
    lang: str,
    start_time: float,
    handle_price_flow_fn,
    notify_admin_handoff_fn,
    notify_admin_error_fn,
    add_to_history_fn,
    save_message_fn,
    schedule_followup_fn,
    record_metric_fn,
    response_factory,
    handle_booking_flow_fn,
    detect_language_fn,
):
    try:
        price_flow_result = await handle_price_flow_fn(phone, user_message, history=history, lang=lang)
        if price_flow_result is None:
            return None

        pf_reply = price_flow_result.get("reply", "")
        pf_status = price_flow_result.get("status", "price_flow")
        pf_log = price_flow_result.get("log")
        pf_is_price = price_flow_result.get("is_price_template", False)

        if pf_status == "handoff":
            raw_reply = (pf_reply or "").strip()
            error_type = None
            if raw_reply.startswith("HANDOFF:"):
                error_type = raw_reply.replace("HANDOFF:", "", 1).strip() or "UNKNOWN"
                pf_reply = ""
            handoff_reason = price_flow_result.get("handoff_reason", "fiyat_sorusu")
            admin_msg = f"Fiyat handoff: {handoff_reason}"
            if error_type:
                admin_msg += f"\nElektra hata: HANDOFF:{error_type}"
            admin_msg += f"\nMesaj: {user_message[:200]}"
            await notify_admin_handoff_fn("fiyat_handoff", "medium", phone or "Bilinmiyor", admin_msg)

            if (not pf_reply) or str(pf_reply).startswith("HANDOFF:"):
                if lang == "en":
                    pf_reply = "I'll connect you with our team for detailed pricing. Please wait a moment."
                else:
                    pf_reply = "Detaylı fiyat bilgisi için sizi ekibimizle bağlıyorum. Lütfen biraz bekleyin."
            add_to_history_fn(phone, "user", user_message)
            add_to_history_fn(phone, "assistant", pf_reply)
            save_message_fn(phone, user_message, f"[FİYAT-HANDOFF: {handoff_reason}] {pf_reply}")
            return response_factory(reply=pf_reply, status="handoff")

        if pf_status == "error":
            await notify_admin_error_fn(
                error_type="PRICE_FLOW_ERROR",
                customer_phone=phone or "Bilinmiyor",
                customer_message=user_message,
                error_details=pf_log or "Bilinmeyen hata",
            )

        if not pf_reply:
            return None

        auto_booking_reply = None
        if pf_is_price:
            try:
                from app.handlers.booking_flow_handler import _has_room_selection, _detect_full_booking_message
                if _has_room_selection(user_message) or _detect_full_booking_message(user_message):
                    auto_booking = await handle_booking_flow_fn(
                        phone,
                        user_message,
                        history=history,
                        lang=detect_language_fn(user_message),
                    )
                    if auto_booking and auto_booking.get("reply"):
                        auto_booking_reply = auto_booking["reply"]
                        print("[AUTO-BOOKING] Fiyat sonrasi otomatik booking flow basladi")
            except Exception as abf_err:
                print(f"[AUTO-BOOKING] Hata: {abf_err}")

        combined_reply = pf_reply + ("\n\n---\n\n" + auto_booking_reply if auto_booking_reply else "")
        add_to_history_fn(phone, "user", user_message)
        add_to_history_fn(phone, "assistant", combined_reply)
        save_message_fn(
            phone,
            user_message,
            combined_reply,
            is_price_template=pf_is_price if not auto_booking_reply else False,
        )
        schedule_followup_fn(phone)
        elapsed = time.time() - start_time
        record_metric_fn("price_flow", category=pf_status, response_time=elapsed)
        return response_factory(
            reply=combined_reply,
            reservation_log=pf_log,
            is_price_template=pf_is_price if not auto_booking_reply else False,
            status="booking_flow" if auto_booking_reply else pf_status,
        )
    except Exception as e:
        print(f"Price flow handler hatasi: {e}")
        return None
