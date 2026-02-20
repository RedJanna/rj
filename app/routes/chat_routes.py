from __future__ import annotations

import time as time_module
import re
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel


class ChatRequest(BaseModel):
    phone: str
    message: str
    message_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    reservation_log: Optional[str] = None
    is_price_template: bool = False
    status: str = "ok"
    reason_code: Optional[str] = None
    next_expected_input: Optional[str] = None


_TR_SPELLING_MAP = {
    "yas": "yaş",
    "cocuk": "çocuk",
    "secim": "seçim",
    "secenek": "seçenek",
    "secenegi": "seçeneği",
    "iki": "iki",
    "ozel": "özel",
    "isteginiz": "isteğiniz",
    "numarasi": "numarası",
    "musait": "müsait",
    "sectiginiz": "seçtiğiniz",
    "farkli": "farklı",
    "bulunamadi": "bulunamadı",
    "yetiskin": "yetişkin",
    "sayin": "sayın",
    "tesekkur": "teşekkür",
    "ederiz": "ederiz",
    "kahvalti": "kahvaltı",
    "iptal": "iptal",
    "odeme": "ödeme",
    "gonder": "gönder",
    "guncel": "güncel",
    "musteri": "müşteri",
    "ucretsiz": "ücretsiz",
    "cikis": "çıkış",
    "giris": "giriş",
    "degisiklik": "değişiklik",
    "saglayici": "sağlayıcı",
    "olustur": "oluştur",
    "olusturuldu": "oluşturuldu",
    "yontem": "yöntem",
    "iletisim": "iletişim",
    "hizli": "hızlı",
    "sifre": "şifre",
    "konusma": "konuşma",
    "kisa": "kısa",
}


def _normalize_turkish_reply_text(text: str) -> str:
    if not text:
        return text
    out = text
    for src, dst in _TR_SPELLING_MAP.items():
        out = re.sub(rf"\b{re.escape(src)}\b", dst, out, flags=re.IGNORECASE)
        out = re.sub(rf"\b{re.escape(src.capitalize())}\b", dst.capitalize(), out)
        out = re.sub(rf"\b{re.escape(src.upper())}\b", dst.upper(), out)
    return out


def build_chat_router(
    *,
    run_chat_prechecks_fn,
    detect_handoff_required_fn,
    try_start_restaurant_reservation_flow_fn,
    restaurant_settings,
    clear_reservation_flow_fn,
    notify_admin_handoff_fn,
    detect_language_fn,
    add_to_history_fn,
    save_message_fn,
    extract_date_from_message_fn,
    parse_date_input_fn,
    extract_date_phrase_fn,
    is_within_season_fn,
    extract_time_from_message_fn,
    get_meal_type_from_time_fn,
    update_reservation_flow_fn,
    reservation_state_cls,
    record_metric_fn,
    try_handle_handoff_and_reservation_flow_fn,
    get_reservation_flow_fn,
    handle_reservation_flow_fn,
    try_handle_booking_flow_entry_fn,
    handle_booking_flow_fn,
    send_whatsapp_message_fn,
    admin_phone: str,
    try_handle_price_flow_entry_fn,
    handle_price_flow_fn,
    notify_admin_error_fn,
    schedule_followup_fn,
    try_handle_late_message_checks_fn,
    is_conversation_ending_fn,
    get_closing_message_fn,
    parse_turkish_date_fn,
    is_hotel_open_fn,
    format_date_turkish_fn,
    get_welcome_message_fn,
    is_greeting_fn,
    is_menu_selection_fn,
    get_menu_response_fn,
    try_handle_elektra_price_entry_fn,
    detect_price_request_fn,
    is_price_flow_active_fn,
    handle_elektra_price_request_fn,
    elektra_config_error_cls,
    price_natural_date_keywords,
    price_inquiry_keywords,
    price_guest_keywords,
    try_handle_canonical_and_local_fn,
    check_local_faq_fn,
    canonical_greeting_keywords,
    kanonik_fiyat_exclusions,
    erken_giris_keywords,
    gec_cikis_keywords,
    handle_openai_fallback_fn,
    openai_client,
    openai_model: str,
    info_system_prompt: str,
    maybe_start_qa_background_fn,
    qa_enabled: bool,
    qa_agent,
    qa_fail_notifications: list,
    record_error_fn,
    load_conversation_fn,
    is_safe_mode_fn,
    is_auto_safe_mode_fn,
    check_rate_limit_fn,
    is_automation_enabled_fn,
    is_blacklisted_fn,
    is_paused_fn,
    cancel_followup_fn,
    get_conversation_history_fn,
    handle_cancel_flow_v2_fn,
    detect_suspicious_message_fn,
    notify_admin_suspicious_fn,
    ai_question_response: str,
    suspicious_response: str,
    detect_critical_issue_fn,
    send_critical_notification_fn,
    get_price_flow_fn,
    get_booking_flow_fn,
    get_active_flow_fn,
    set_active_flow_fn,
    clear_active_flow_fn,
    get_domain_lock_fn,
    set_domain_lock_fn,
    clear_domain_lock_fn,
    is_processed_message_id_fn,
    mark_message_id_processed_fn,
    trace_decision_fn,
):
    router = APIRouter()

    @router.post("/chat", response_model=ChatResponse)
    async def chat_endpoint(payload: ChatRequest):
        start_time = time_module.time()
        user_message = payload.message.strip()
        phone = payload.phone.strip() if payload.phone else None
        message_id = (payload.message_id or "").strip()
        initial_lang = detect_language_fn(user_message or "")

        def resp(
            reply: str,
            status: str = "ok",
            reservation_log=None,
            is_price_template: bool = False,
            reason_code: Optional[str] = None,
            next_expected_input: Optional[str] = None,
        ):
            normalized_reply = reply
            if (initial_lang or "tr") != "en":
                normalized_reply = _normalize_turkish_reply_text(reply or "")
            return ChatResponse(
                reply=normalized_reply,
                status=status,
                reservation_log=reservation_log,
                is_price_template=is_price_template,
                reason_code=reason_code,
                next_expected_input=next_expected_input,
            )

        # Idempotency: Ayni message_id bir daha islenmesin.
        if phone and message_id and is_processed_message_id_fn(phone, message_id):
            trace_decision_fn(
                {
                    "phone": phone,
                    "message_id": message_id,
                    "event": "duplicate_message_id",
                    "message_preview": (user_message or "")[:120],
                }
            )
            return resp(reply="", status="duplicate_message_id")
        if phone and message_id:
            mark_message_id_processed_fn(phone, message_id)

        precheck = await run_chat_prechecks_fn(
            phone=phone,
            user_message=user_message,
            detect_language_fn=detect_language_fn,
            load_conversation_fn=load_conversation_fn,
            notify_admin_error_fn=notify_admin_error_fn,
            save_message_fn=save_message_fn,
            is_safe_mode_fn=is_safe_mode_fn,
            is_auto_safe_mode_fn=is_auto_safe_mode_fn,
            check_rate_limit_fn=check_rate_limit_fn,
            is_automation_enabled_fn=is_automation_enabled_fn,
            is_blacklisted_fn=is_blacklisted_fn,
            is_paused_fn=is_paused_fn,
            cancel_followup_fn=cancel_followup_fn,
            get_conversation_history_fn=get_conversation_history_fn,
            handle_cancel_flow_v2_fn=handle_cancel_flow_v2_fn,
            detect_suspicious_message_fn=detect_suspicious_message_fn,
            notify_admin_suspicious_fn=notify_admin_suspicious_fn,
            ai_question_response=ai_question_response,
            suspicious_response=suspicious_response,
            add_to_history_fn=add_to_history_fn,
            detect_critical_issue_fn=detect_critical_issue_fn,
            send_critical_notification_fn=send_critical_notification_fn,
            response_factory=resp,
        )
        if precheck["response"] is not None:
            trace_decision_fn(
                {
                    "phone": phone,
                    "message_id": message_id,
                    "event": "precheck_response",
                    "status": getattr(precheck["response"], "status", ""),
                }
            )
            return precheck["response"]
        lang = precheck["lang"]
        history = precheck["history"]

        # KRITIK KURAL: Konusma gecmisi yoksa ilk cevap her zaman karsilama mesaji olmalidir.
        if not history:
            welcome_message = get_welcome_message_fn(lang or detect_language_fn(user_message))
            add_to_history_fn(phone, "user", user_message)
            add_to_history_fn(phone, "assistant", welcome_message)
            save_message_fn(phone, user_message, welcome_message)
            schedule_followup_fn(phone)
            elapsed = time_module.time() - start_time
            record_metric_fn("first_message", response_time=elapsed)
            trace_decision_fn(
                {
                    "phone": phone,
                    "message_id": message_id,
                    "event": "first_message",
                    "lang": lang,
                    "route": "welcome",
                }
            )
            return resp(reply=welcome_message, status="first_message")

        # Domain lock secim adimi: belirsiz rota sorusundan sonra 1-2-3-4 secimi.
        current_domain_lock = get_domain_lock_fn(phone)
        normalized_msg = (user_message or "").strip().lower()
        if current_domain_lock == "awaiting_choice":
            if normalized_msg in {"1", "2", "3", "4"}:
                if normalized_msg == "1":
                    set_domain_lock_fn(phone, "hotel", reason="user_choice")
                    reply = (
                        "Harika, oda fiyatı/rezervasyon tarafına geçiyorum.\n"
                        "Lütfen giriş-çıkış tarihi ve kişi bilgisini yazın. (Örn: 10-13 Ağustos, 2 yetişkin)"
                    ) if lang != "en" else (
                        "Great, switching to room pricing/reservation.\n"
                        "Please share check-in/check-out dates and guest details. (e.g. 10-13 Aug, 2 adults)"
                    )
                elif normalized_msg == "2":
                    set_domain_lock_fn(phone, "restaurant", reason="user_choice")
                    reply = (
                        "Tamam, restoran rezervasyonuna geçiyorum.\n"
                        "Lütfen kişi sayısı, tarih, saat ve rezervasyon adını yazın."
                    ) if lang != "en" else (
                        "Okay, switching to restaurant reservation.\n"
                        "Please share guest count, date, time, and reservation name."
                    )
                elif normalized_msg == "3":
                    set_domain_lock_fn(phone, "payment", reason="user_choice")
                    reply = (
                        "Tamam, ödeme konusuna geçiyorum.\n"
                        "Genel ödeme yöntemleri için bilgi verebilirim veya aktif rezervasyon referansı ile ödeme linki hazırlayabilirim."
                    ) if lang != "en" else (
                        "Okay, switching to payment.\n"
                        "I can share general payment methods or prepare a payment link with an active reservation reference."
                    )
                else:
                    clear_domain_lock_fn(phone)
                    reply = (
                        "Tamam, serbest soru-cevap modundayız. Sorunuzu doğrudan yazabilirsiniz."
                    ) if lang != "en" else (
                        "Okay, we are now in free Q&A mode. You can ask your question directly."
                    )

                add_to_history_fn(phone, "user", user_message)
                add_to_history_fn(phone, "assistant", reply)
                save_message_fn(phone, user_message, reply)
                trace_decision_fn(
                    {
                        "phone": phone,
                        "message_id": message_id,
                        "event": "domain_lock_choice_applied",
                        "choice": normalized_msg,
                        "domain_lock": get_domain_lock_fn(phone),
                    }
                )
                return resp(reply=reply, status="domain_lock_set", reason_code="user_route_choice")

            if lang == "en":
                reply = (
                    "I want to route your request correctly. Which one is it?\n"
                    "1. Room price / reservation\n"
                    "2. Restaurant reservation\n"
                    "3. Payment methods or payment link\n"
                    "4. Other"
                )
            elif lang == "ru":
                reply = (
                    "Чтобы правильно помочь, уточните, пожалуйста:\n"
                    "1. Цена номера / бронирование\n"
                    "2. Бронирование ресторана\n"
                    "3. Способы оплаты или ссылка на оплату\n"
                    "4. Другое"
                )
            else:
                reply = (
                    "Doğru yönlendirme yapabilmem için lütfen seçin:\n"
                    "1. Oda fiyatı / rezervasyon\n"
                    "2. Restoran rezervasyonu\n"
                    "3. Ödeme yöntemleri veya ödeme linki\n"
                    "4. Diğer"
                )
            add_to_history_fn(phone, "user", user_message)
            add_to_history_fn(phone, "assistant", reply)
            save_message_fn(phone, user_message, reply)
            return resp(
                reply=reply,
                status="routing_clarification_required",
                reason_code="awaiting_route_choice",
                next_expected_input="1|2|3|4",
            )

        def _intent_scores(msg: str) -> tuple[int, int, int]:
            low = (msg or "").lower()
            restaurant_words = {
                "restoran", "restaurant", "masa", "table", "kahvalt", "dinner", "lunch", "breakfast",
                "aksam yemegi", "akşam yemeği", "ogle yemegi", "öğle yemeği",
            }
            hotel_words = {
                "oda", "room", "fiyat", "ücret", "ucret", "müsait", "musait", "availability",
                "book", "booking", "reservation", "konaklama", "adult", "yetiskin", "yetişkin",
                "check-in", "check in", "check-out", "check out",
            }
            payment_words = {
                "odeme", "ödeme", "kredi kart", "mail order", "havale", "eft", "payment", "transfer",
            }
            r_score = sum(1 for w in restaurant_words if w in low)
            h_score = sum(1 for w in hotel_words if w in low)
            p_score = sum(1 for w in payment_words if w in low)
            return r_score, h_score, p_score

        def _build_ambiguity_prompt(lang_code: str) -> str:
            if lang_code == "en":
                return (
                    "I want to route your request correctly. Which one is it?\n"
                    "1. Room price / reservation\n"
                    "2. Restaurant reservation\n"
                    "3. Payment methods or payment link\n"
                    "4. Other"
                )
            if lang_code == "ru":
                return (
                    "Чтобы правильно помочь, уточните, пожалуйста:\n"
                    "1. Цена номера / бронирование\n"
                    "2. Бронирование ресторана\n"
                    "3. Способы оплаты или ссылка на оплату\n"
                    "4. Другое"
                )
            return (
                "Doğru yönlendirme yapabilmem için lütfen seçin:\n"
                "1. Oda fiyatı / rezervasyon\n"
                "2. Restoran rezervasyonu\n"
                "3. Ödeme yöntemleri veya ödeme linki\n"
                "4. Diğer"
            )

        def _route_decision_v2(
            msg: str,
            *,
            lang_code: str,
            restaurant_flow_active: bool,
            booking_flow_active: bool,
            price_flow_active: bool,
            domain_lock: Optional[str],
        ) -> dict:
            low = (msg or "").lower()
            r_score, h_score, p_score = _intent_scores(msg)
            transaction_words = {
                "rezervasyon", "reservation", "book", "booking",
                "fiyat", "price", "oda", "room", "restoran", "restaurant",
                "odeme", "ödeme", "payment", "havale", "eft", "transfer",
            }
            has_transaction_signal = any(w in low for w in transaction_words)
            info_words = {
                "wifi", "kahvalti", "kahvaltı", "pool", "havuz",
                "check in", "check-in", "check out", "check-out",
                "konum", "location", "adres", "address",
            }
            is_info_question = any(w in low for w in info_words)

            # Active flow always wins unless user gives a stronger conflicting signal.
            if booking_flow_active:
                return {"domain": "hotel", "confidence": 1.0, "ambiguous": False, "reason": "active_booking_flow", "scores": {"restaurant": r_score, "hotel": h_score, "payment": p_score}}
            if price_flow_active:
                return {"domain": "hotel", "confidence": 1.0, "ambiguous": False, "reason": "active_price_flow", "scores": {"restaurant": r_score, "hotel": h_score, "payment": p_score}}
            if restaurant_flow_active and r_score >= h_score:
                return {"domain": "restaurant", "confidence": 0.95, "ambiguous": False, "reason": "active_restaurant_flow", "scores": {"restaurant": r_score, "hotel": h_score, "payment": p_score}}

            score_map = {"restaurant": r_score, "hotel": h_score, "payment": p_score}
            if domain_lock in {"hotel", "restaurant", "payment"}:
                top_domain = max(score_map.items(), key=lambda kv: kv[1])[0]
                top_score = score_map[top_domain]
                lock_score = score_map.get(domain_lock, 0)
                explicit_override = (top_domain != domain_lock) and (top_score >= 2) and ((top_score - lock_score) >= 1)
                if not explicit_override:
                    return {
                        "domain": domain_lock,
                        "confidence": 0.9,
                        "ambiguous": False,
                        "reason": "domain_lock",
                        "scores": score_map,
                    }

            ranked = sorted(
                [("restaurant", r_score), ("hotel", h_score), ("payment", p_score)],
                key=lambda x: x[1],
                reverse=True,
            )
            top_domain, top_score = ranked[0]
            second_score = ranked[1][1]

            if top_score == 0:
                return {"domain": "unknown", "confidence": 0.0, "ambiguous": bool(has_transaction_signal and not is_info_question), "reason": "no_signal", "scores": {"restaurant": r_score, "hotel": h_score, "payment": p_score}}

            confidence = min(1.0, 0.45 + (top_score * 0.15) + ((top_score - second_score) * 0.1))
            ambiguous = bool(has_transaction_signal and top_score < 2 and (top_score - second_score) <= 1)
            return {
                "domain": top_domain,
                "confidence": confidence,
                "ambiguous": ambiguous,
                "reason": "keyword_scoring",
                "scores": score_map,
            }

        reservation_flow = get_reservation_flow_fn(phone)
        is_restaurant_flow_active = (
            reservation_flow.get("state") != reservation_state_cls.IDLE.value
        )
        booking_flow = get_booking_flow_fn(phone)
        is_booking_flow_active = bool(booking_flow and booking_flow.get("state"))
        price_flow = get_price_flow_fn(phone)
        is_price_flow_active = bool(price_flow and price_flow.get("state"))

        route_v2 = _route_decision_v2(
            user_message,
            lang_code=lang,
            restaurant_flow_active=is_restaurant_flow_active,
            booking_flow_active=is_booking_flow_active,
            price_flow_active=is_price_flow_active,
            domain_lock=current_domain_lock,
        )

        # Acik konu degisikliginde lock kirilsin.
        if current_domain_lock in {"hotel", "restaurant", "payment"}:
            if route_v2.get("reason") == "keyword_scoring" and route_v2.get("domain") != current_domain_lock and route_v2.get("confidence", 0) >= 0.7:
                clear_domain_lock_fn(phone)

        if route_v2.get("ambiguous") and not (is_restaurant_flow_active or is_booking_flow_active or is_price_flow_active):
            reply = _build_ambiguity_prompt(lang)
            set_domain_lock_fn(phone, "awaiting_choice", reason="router_v2_ambiguous")
            add_to_history_fn(phone, "user", user_message)
            add_to_history_fn(phone, "assistant", reply)
            save_message_fn(phone, user_message, reply)
            trace_decision_fn(
                {
                    "phone": phone,
                    "message_id": message_id,
                    "event": "router_v2_ambiguous",
                    "decision": route_v2,
                    "message_preview": (user_message or "")[:120],
                }
            )
            return resp(
                reply=reply,
                status="routing_clarification_required",
                reason_code="ambiguous_intent",
                next_expected_input="1|2|3|4",
            )

        needs_handoff, handoff_category, handoff_priority, handoff_msg_tr, handoff_msg_en, handoff_msg_ru = detect_handoff_required_fn(user_message)
        allow_restaurant_entry = bool(is_restaurant_flow_active or route_v2.get("domain") in ("restaurant", "unknown"))
        if allow_restaurant_entry:
            restaurant_start_response = await try_start_restaurant_reservation_flow_fn(
                needs_handoff=needs_handoff,
                handoff_category=handoff_category,
                user_message=user_message,
                phone=phone,
                start_time=start_time,
                history=history,
                restaurant_settings=restaurant_settings,
                clear_reservation_flow_fn=clear_reservation_flow_fn,
                notify_admin_handoff_fn=notify_admin_handoff_fn,
                detect_language_fn=detect_language_fn,
                add_to_history_fn=add_to_history_fn,
                save_message_fn=save_message_fn,
                response_factory=resp,
                extract_date_from_message_fn=extract_date_from_message_fn,
                parse_date_input_fn=parse_date_input_fn,
                extract_date_phrase_fn=extract_date_phrase_fn,
                is_within_season_fn=is_within_season_fn,
                extract_time_from_message_fn=extract_time_from_message_fn,
                get_meal_type_from_time_fn=get_meal_type_from_time_fn,
                update_reservation_flow_fn=update_reservation_flow_fn,
                reservation_state_cls=reservation_state_cls,
                record_metric_fn=record_metric_fn,
            )
            if restaurant_start_response is not None:
                return restaurant_start_response

        handoff_or_reservation_response = await try_handle_handoff_and_reservation_flow_fn(
            needs_handoff=needs_handoff,
            handoff_category=handoff_category,
            handoff_priority=handoff_priority,
            handoff_msg_tr=handoff_msg_tr,
            handoff_msg_en=handoff_msg_en,
            handoff_msg_ru=handoff_msg_ru,
            user_message=user_message,
            phone=phone,
            start_time=start_time,
            notify_admin_handoff_fn=notify_admin_handoff_fn,
            detect_language_fn=detect_language_fn,
            add_to_history_fn=add_to_history_fn,
            save_message_fn=save_message_fn,
            record_metric_fn=record_metric_fn,
            get_reservation_flow_fn=get_reservation_flow_fn,
            reservation_state_cls=reservation_state_cls,
            handle_reservation_flow_fn=handle_reservation_flow_fn,
            response_factory=resp,
        )
        if handoff_or_reservation_response is not None:
            return handoff_or_reservation_response

        # HARD SEPARATION: Restoran ve otel rezervasyon akislari birbirine dusmesin.
        # Karar: Router v2 skor + aktif flow.
        r_score = int(route_v2["scores"]["restaurant"])
        h_score = int(route_v2["scores"]["hotel"])
        p_score = int(route_v2["scores"]["payment"])
        block_hotel_paths = bool(is_restaurant_flow_active and h_score < 2)

        # Kullanici acik bir sekilde otel/fiyat tarafina geciyorsa restoran flow kilidi kirilsin.
        if is_restaurant_flow_active and h_score >= 2 and h_score >= r_score:
            clear_reservation_flow_fn(phone)
            is_restaurant_flow_active = False
            block_hotel_paths = False
            set_active_flow_fn(phone, "hotel", reason="explicit_hotel_override")

        # Tek merkez flow state'i güncelle (routing_state_service).
        if is_booking_flow_active:
            set_active_flow_fn(phone, "booking", reason="booking_flow_active")
        elif is_price_flow_active:
            set_active_flow_fn(phone, "price", reason="price_flow_active")
        elif is_restaurant_flow_active:
            set_active_flow_fn(phone, "restaurant", reason="reservation_flow_active")
        elif route_v2.get("domain") == "hotel" and route_v2.get("confidence", 0) >= 0.55:
            set_active_flow_fn(phone, "hotel", reason="hotel_intent")
        elif route_v2.get("domain") == "restaurant" and route_v2.get("confidence", 0) >= 0.55:
            set_active_flow_fn(phone, "restaurant", reason="restaurant_intent")
        elif route_v2.get("domain") == "payment" and route_v2.get("confidence", 0) >= 0.55:
            set_active_flow_fn(phone, "payment", reason="payment_intent")
        else:
            clear_active_flow_fn(phone)

        trace_decision_fn(
            {
                "phone": phone,
                "message_id": message_id,
                "event": "routing_decision",
                "router_v2": route_v2,
                "active_flow": get_active_flow_fn(phone),
                "restaurant_flow_active": is_restaurant_flow_active,
                "booking_flow_active": is_booking_flow_active,
                "price_flow_active": is_price_flow_active,
                "scores": {"restaurant": r_score, "hotel": h_score, "payment": p_score},
                "block_hotel_paths": block_hotel_paths,
                "message_preview": (user_message or "")[:120],
            }
        )

        if block_hotel_paths:
            # Restoran baglaminda otel booking/fiyat bloklarina girme.
            # Rezervasyon flow aktifse yukarida zaten handle edildi; burada sadece emniyet.
            handled_local = try_handle_canonical_and_local_fn(
                user_message=user_message,
                phone=phone,
                start_time=start_time,
                history=history,
                check_local_faq_fn=check_local_faq_fn,
                detect_language_fn=detect_language_fn,
                get_welcome_message_fn=get_welcome_message_fn,
                add_to_history_fn=add_to_history_fn,
                save_message_fn=save_message_fn,
                schedule_followup_fn=schedule_followup_fn,
                record_metric_fn=record_metric_fn,
                response_factory=resp,
                update_reservation_flow_fn=update_reservation_flow_fn,
                reservation_state_cls=reservation_state_cls,
                canonical_greeting_keywords=canonical_greeting_keywords,
                kanonik_fiyat_exclusions=kanonik_fiyat_exclusions,
                erken_giris_keywords=erken_giris_keywords,
                gec_cikis_keywords=gec_cikis_keywords,
            )
            if handled_local is not None:
                return handled_local

        if not block_hotel_paths:
            async def _run_booking_entry():
                return await try_handle_booking_flow_entry_fn(
                    phone=phone,
                    user_message=user_message,
                    history=history,
                    start_time=start_time,
                    detect_language_fn=detect_language_fn,
                    handle_booking_flow_fn=handle_booking_flow_fn,
                    add_to_history_fn=add_to_history_fn,
                    save_message_fn=save_message_fn,
                    record_metric_fn=record_metric_fn,
                    send_whatsapp_message_fn=send_whatsapp_message_fn,
                    admin_phone=admin_phone,
                    response_factory=resp,
                )

            async def _run_price_flow_entry():
                return await try_handle_price_flow_entry_fn(
                    phone=phone,
                    user_message=user_message,
                    history=history,
                    lang=lang,
                    start_time=start_time,
                    handle_price_flow_fn=handle_price_flow_fn,
                    notify_admin_handoff_fn=notify_admin_handoff_fn,
                    notify_admin_error_fn=notify_admin_error_fn,
                    add_to_history_fn=add_to_history_fn,
                    save_message_fn=save_message_fn,
                    schedule_followup_fn=schedule_followup_fn,
                    record_metric_fn=record_metric_fn,
                    response_factory=resp,
                    handle_booking_flow_fn=handle_booking_flow_fn,
                    detect_language_fn=detect_language_fn,
                )

            active_flow_hint = get_active_flow_fn(phone)
            if active_flow_hint == "price":
                price_flow_entry_response = await _run_price_flow_entry()
                if price_flow_entry_response is not None:
                    return price_flow_entry_response
                booking_entry_response = await _run_booking_entry()
                if booking_entry_response is not None:
                    return booking_entry_response
            else:
                booking_entry_response = await _run_booking_entry()
                if booking_entry_response is not None:
                    return booking_entry_response
                price_flow_entry_response = await _run_price_flow_entry()
                if price_flow_entry_response is not None:
                    return price_flow_entry_response

        late_checks_response = try_handle_late_message_checks_fn(
            user_message=user_message,
            phone=phone,
            history=history,
            start_time=start_time,
            is_conversation_ending_fn=is_conversation_ending_fn,
            get_closing_message_fn=get_closing_message_fn,
            detect_language_fn=detect_language_fn,
            add_to_history_fn=add_to_history_fn,
            save_message_fn=save_message_fn,
            parse_turkish_date_fn=parse_turkish_date_fn,
            is_hotel_open_fn=is_hotel_open_fn,
            format_date_turkish_fn=format_date_turkish_fn,
            get_welcome_message_fn=get_welcome_message_fn,
            schedule_followup_fn=schedule_followup_fn,
            record_metric_fn=record_metric_fn,
            is_greeting_fn=is_greeting_fn,
            is_menu_selection_fn=is_menu_selection_fn,
            get_menu_response_fn=get_menu_response_fn,
            response_factory=resp,
        )
        if late_checks_response is not None:
            return late_checks_response

        if not block_hotel_paths:
            price_entry_response = await try_handle_elektra_price_entry_fn(
                phone=phone,
                user_message=user_message,
                history=history,
                detect_price_request_fn=detect_price_request_fn,
                is_price_flow_active_fn=is_price_flow_active_fn,
                detect_language_fn=detect_language_fn,
                handle_elektra_price_request_fn=handle_elektra_price_request_fn,
                notify_admin_handoff_fn=notify_admin_handoff_fn,
                add_to_history_fn=add_to_history_fn,
                save_message_fn=save_message_fn,
                schedule_followup_fn=schedule_followup_fn,
                response_factory=resp,
                notify_admin_error_fn=notify_admin_error_fn,
                eleltra_config_error_cls=elektra_config_error_cls,
                natural_date_keywords=price_natural_date_keywords,
                price_inquiry_keywords=price_inquiry_keywords,
                guest_keywords=price_guest_keywords,
            )
            if price_entry_response is not None:
                return price_entry_response

        handled_local = try_handle_canonical_and_local_fn(
            user_message=user_message,
            phone=phone,
            start_time=start_time,
            history=history,
            check_local_faq_fn=check_local_faq_fn,
            detect_language_fn=detect_language_fn,
            get_welcome_message_fn=get_welcome_message_fn,
            add_to_history_fn=add_to_history_fn,
            save_message_fn=save_message_fn,
            schedule_followup_fn=schedule_followup_fn,
            record_metric_fn=record_metric_fn,
            response_factory=resp,
            update_reservation_flow_fn=update_reservation_flow_fn,
            reservation_state_cls=reservation_state_cls,
            canonical_greeting_keywords=canonical_greeting_keywords,
            kanonik_fiyat_exclusions=kanonik_fiyat_exclusions,
            erken_giris_keywords=erken_giris_keywords,
            gec_cikis_keywords=gec_cikis_keywords,
        )
        if handled_local is not None:
            return handled_local

        return await handle_openai_fallback_fn(
            client=openai_client,
            openai_model=openai_model,
            info_system_prompt=info_system_prompt,
            history=history,
            user_message=user_message,
            phone=phone,
            start_time=start_time,
            add_to_history_fn=add_to_history_fn,
            save_message_fn=save_message_fn,
            schedule_followup_fn=schedule_followup_fn,
            record_metric_fn=record_metric_fn,
            maybe_start_qa_background_fn=maybe_start_qa_background_fn,
            qa_enabled=qa_enabled,
            qa_agent=qa_agent,
            admin_phone=admin_phone,
            send_whatsapp_message_fn=send_whatsapp_message_fn,
            qa_fail_notifications=qa_fail_notifications,
            record_error_fn=record_error_fn,
            response_factory=resp,
        )

    return router
