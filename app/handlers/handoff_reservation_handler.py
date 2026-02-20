from __future__ import annotations

import time


async def try_handle_handoff_and_reservation_flow(
    *,
    needs_handoff: bool,
    handoff_category: str,
    handoff_priority: str,
    handoff_msg_tr: str,
    handoff_msg_en: str,
    handoff_msg_ru: str = "",
    user_message: str,
    phone: str,
    start_time: float,
    notify_admin_handoff_fn,
    detect_language_fn,
    add_to_history_fn,
    save_message_fn,
    record_metric_fn,
    get_reservation_flow_fn,
    reservation_state_cls,
    handle_reservation_flow_fn,
    response_factory,
):
    if needs_handoff:
        await notify_admin_handoff_fn(
            category=handoff_category,
            priority=handoff_priority,
            customer_phone=phone or "Bilinmiyor",
            customer_message=user_message,
        )
        lang = detect_language_fn(user_message)
        if lang == "ru" and handoff_msg_ru:
            reply = handoff_msg_ru
        elif lang == "en":
            reply = handoff_msg_en
        else:
            reply = handoff_msg_tr
        add_to_history_fn(phone, "user", user_message)
        add_to_history_fn(phone, "assistant", reply)
        save_message_fn(phone, user_message, f"[İNSANA DEVİR - {handoff_category.upper()}] {reply}")
        elapsed = time.time() - start_time
        record_metric_fn("handoff", category=handoff_category, response_time=elapsed)
        return response_factory(reply=reply, status="handoff")

    reservation_flow = get_reservation_flow_fn(phone)
    if reservation_flow["state"] != reservation_state_cls.IDLE.value:
        result = await handle_reservation_flow_fn(phone, user_message, reservation_flow)
        if result:
            if isinstance(result, tuple) and len(result) == 2:
                reply, status_override = result
            else:
                reply, status_override = result, None
            add_to_history_fn(phone, "user", user_message)
            add_to_history_fn(phone, "assistant", reply)
            save_message_fn(phone, user_message, f"[REZERVASYON] {reply}")
            elapsed = time.time() - start_time
            record_metric_fn("reservation_flow", response_time=elapsed)
            return response_factory(reply=reply, status=(status_override or "reservation_flow"))

    return None
