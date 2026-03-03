from __future__ import annotations

import time
from app.services.handoff_critical_registry import PRICE_HARD_HANDOFF_REASONS

_PRICE_HANDOFF_DEFAULTS = {
    "tr": "Detaylı fiyat bilgisi için sizi ekibimizle bağlıyorum. Lütfen biraz bekleyin.",
    "en": "I'll connect you with our team for detailed pricing. Please wait a moment.",
    "ru": "Для подробной информации о ценах я подключаю вас к нашей команде. Пожалуйста, подождите.",
    "de": "Für detaillierte Preisinformationen verbinde ich Sie mit unserem Team. Bitte warten Sie einen Moment.",
    "ar": "للحصول على تفاصيل الأسعار، سأقوم بوصلك بفريقنا. يرجى الانتظار لحظة.",
    "es": "Para obtener información detallada de precios, te conecto con nuestro equipo. Espera un momento, por favor.",
    "fr": "Pour des informations tarifaires détaillées, je vous mets en relation avec notre équipe. Veuillez patienter un instant.",
    "zh": "如需详细价格信息，我将为您转接到我们的团队，请稍候。",
    "hi": "विस्तृत मूल्य जानकारी के लिए मैं आपको हमारी टीम से जोड़ रहा हूँ। कृपया एक क्षण प्रतीक्षा करें।",
    "pt": "Para informações detalhadas de preços, vou conectá-lo à nossa equipe. Aguarde um momento, por favor.",
}


def _is_room_stock_question(text: str) -> bool:
    low = (text or "").lower()
    room_markers = ["deluxe", "superior", "exclusive", "penthouse", "premium"]
    stock_markers = ["kaç adet", "kac adet", "kaç oda", "kac oda", "müsait", "musait", "available", "remaining", "left"]
    return any(r in low for r in room_markers) and any(s in low for s in stock_markers)


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
        # ÖNEMLİ: Aktif transfer konuşması varsa price flow tetiklenmemeli
        from app.utils.message_utils import _is_transfer_conversation_active, looks_like_transfer_message
        if _is_transfer_conversation_active(history):
            print("🚫 price_flow_entry: Aktif transfer konuşması tespit edildi, price flow atlanıyor")
            return None
        if looks_like_transfer_message(user_message):
            print("🚫 price_flow_entry: Transfer detay mesajı tespit edildi, price flow atlanıyor")
            return None

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
            # Soft handoff: fiyat tarafindaki gecici/sistemsel sorunlarda konusmayi kilitleme.
            if handoff_reason in PRICE_HARD_HANDOFF_REASONS:
                try:
                    from app.services.access_control_service import activate_human_takeover
                    activate_human_takeover(phone, reason=f"price_flow:{handoff_reason}")
                except Exception:
                    pass
            admin_msg = f"Fiyat handoff: {handoff_reason}"
            if error_type:
                admin_msg += f"\nElektra hata: HANDOFF:{error_type}"
            admin_msg += f"\nMesaj: {user_message[:200]}"
            await notify_admin_handoff_fn(
                category="fiyat_handoff",
                priority="medium",
                customer_phone=phone or "Bilinmiyor",
                customer_message=admin_msg,
                source="price_flow_entry_handler",
                detected_intent="PRICE_QUERY",
                confidence=0.85,
                conversation_summary=f"price_flow handoff reason={handoff_reason}",
                attempted_actions=["price_flow_handle", "handoff_route"],
                suggested_reply=(pf_reply or "")[:240],
                tags=["price_flow", "handoff"],
            )

            if (not pf_reply) or str(pf_reply).startswith("HANDOFF:"):
                lang_norm = (lang or "en").strip().lower()
                pf_reply = _PRICE_HANDOFF_DEFAULTS.get(lang_norm, _PRICE_HANDOFF_DEFAULTS["en"])
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
        if pf_is_price and not _is_room_stock_question(user_message):
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
