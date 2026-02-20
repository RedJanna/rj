from __future__ import annotations

import os
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse


PUBLIC_ADMIN_PATHS = {
    "/admin/login",
    "/admin/verify-2fa",
    "/admin/setup-2fa",
}


def configure_http(app, require_admin):
    cors_raw = os.getenv(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173",
    )
    cors_allow_origins = [origin.strip() for origin in cors_raw.split(",") if origin.strip()]
    cors_allow_all = cors_allow_origins == ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_allow_origins,
        allow_credentials=not cors_allow_all,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def enforce_admin_auth(request: Request, call_next):
        started = time.perf_counter()
        client_ip = getattr(request.client, "host", "-")
        path = request.url.path.rstrip("/") or "/"
        if path.startswith("/admin") and path not in PUBLIC_ADMIN_PATHS:
            try:
                require_admin(request=request)
            except HTTPException as exc:
                redirect_target = (exc.headers or {}).get("X-Redirect")
                accepts_html = "text/html" in request.headers.get("accept", "")
                if redirect_target and accepts_html:
                    elapsed_ms = (time.perf_counter() - started) * 1000
                    print(
                        f"[HTTP] {request.method} {request.url.path} -> 302 "
                        f"{elapsed_ms:.1f}ms ip={client_ip}"
                    )
                    return RedirectResponse(url=redirect_target, status_code=302)
                elapsed_ms = (time.perf_counter() - started) * 1000
                print(
                    f"[HTTP] {request.method} {request.url.path} -> {exc.status_code} "
                    f"{elapsed_ms:.1f}ms ip={client_ip}"
                )
                return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000
        print(
            f"[HTTP] {request.method} {request.url.path} -> {response.status_code} "
            f"{elapsed_ms:.1f}ms ip={client_ip}"
        )
        return response


def get_system_test_router():
    app_env = os.getenv("KASSANDRA_ENV", "production").strip().lower()
    system_tests_enabled = app_env in {"dev", "development", "test", "local"}
    if system_tests_enabled:
        try:
            from tests.system_test.system_test_routes import router as system_test_router
        except Exception as system_test_import_error:
            print(f"⚠️ system_test_router yüklenemedi: {system_test_import_error}")
            system_test_router = APIRouter()
    else:
        system_test_router = APIRouter()
    return system_test_router


def wire_routes(app, *, ctx: dict, system_test_router):
    app.include_router(system_test_router, dependencies=[Depends(ctx["require_admin"])])
    app.include_router(ctx["metrics_router"], dependencies=[Depends(ctx["require_admin"])])
    app.include_router(ctx["reminder_router"], dependencies=[Depends(ctx["require_admin"])])
    app.include_router(ctx["pytest_router"], dependencies=[Depends(ctx["require_admin"])])
    app.include_router(ctx["auth_router"])
    app.include_router(
        ctx["build_admin_stats_router"](
            reservations_db=ctx["RESERVATIONS_DB"],
            get_metrics_summary_fn=ctx["get_metrics_summary"],
        ),
        dependencies=[Depends(ctx["require_admin"])],
    )
    app.include_router(
        ctx["build_hotel_bookings_router"](
            get_pending_hotel_bookings_fn=ctx["get_pending_hotel_bookings"],
            get_all_hotel_bookings_fn=ctx["get_all_hotel_bookings"],
            get_hotel_booking_stats_fn=ctx["get_hotel_booking_stats"],
            get_hotel_booking_fn=ctx["get_hotel_booking"],
            create_hotel_booking_fn=ctx.get("create_hotel_booking"),
            update_hotel_booking_status_fn=ctx["update_hotel_booking_status"],
            create_elektraweb_reservation_fn=ctx["create_elektraweb_reservation"],
            get_elektraweb_reservation_fn=ctx.get("get_elektraweb_reservation"),
            update_elektraweb_reservation_fn=ctx.get("update_elektraweb_reservation"),
            cancel_elektraweb_reservation_fn=ctx.get("cancel_elektraweb_reservation"),
            hoteladvisor_select_fn=ctx.get("hoteladvisor_select"),
            hoteladvisor_execute_fn=ctx.get("hoteladvisor_execute"),
            hoteladvisor_function_fn=ctx.get("hoteladvisor_function"),
            hoteladvisor_update_fn=ctx.get("hoteladvisor_update"),
            get_reservation_guests_fn=ctx.get("get_reservation_guests"),
            save_reservation_guest_fn=ctx.get("save_reservation_guest"),
            get_portal_installments_fn=ctx.get("get_portal_installments"),
            send_whatsapp_message_fn=ctx["send_whatsapp_message"],
            booking_status=ctx["BookingStatus"],
            admin_phone=ctx["ADMIN_PHONE"],
            elektra_config_error_cls=ctx["ElektrawebConfigError"],
        ),
        dependencies=[Depends(ctx["require_admin"])],
    )
    app.include_router(
        ctx["build_admin_safety_router"](
            enable_safe_mode_fn=ctx["enable_safe_mode"],
            disable_safe_mode_fn=ctx["disable_safe_mode"],
            get_system_status_fn=ctx["get_system_status"],
            unblock_rate_limit_fn=ctx["unblock_rate_limit"],
            get_error_stats_fn=ctx["get_error_stats"],
            clear_errors_fn=ctx["clear_errors"],
            notify_critical_action_fn=ctx["notify_critical_action"],
        ),
        dependencies=[Depends(ctx["require_admin"])],
    )
    app.include_router(
        ctx["build_admin_reservations_router"](
            reservations_db=ctx["RESERVATIONS_DB"],
            reservation_status=ctx["ReservationStatus"],
            get_reservations_by_date_fn=ctx["get_reservations_by_date"],
            get_upcoming_reservations_fn=ctx["get_upcoming_reservations"],
            get_todays_reservations_fn=ctx["get_todays_reservations"],
            get_reservation_fn=ctx["get_reservation"],
            update_reservation_status_fn=ctx["update_reservation_status"],
            cancel_reservation_fn=ctx["cancel_reservation"],
            notify_admin_cancel_v2_fn=ctx["_notify_admin_cancel_v2"],
            get_customer_reservations_fn=ctx["get_customer_reservations"],
            send_whatsapp_message_fn=ctx["send_whatsapp_message"],
            admin_phone=ctx["ADMIN_PHONE"],
        ),
        dependencies=[Depends(ctx["require_admin"])],
    )
    app.include_router(
        ctx["build_restaurant_plan_router"](
            project_root=ctx["Path"](__file__).resolve().parents[2],
            restaurant_staff=ctx["RESTAURANT_STAFF"],
        ),
        dependencies=[Depends(ctx["require_admin"])],
    )

    flow_service = ctx["ChatFlowService"](
        api_key=ctx["API_KEY_ENV"],
        model_getter=ctx["_get_openai_model_runtime"],
        system_prompt_getter=ctx["_get_system_prompt_runtime"],
        detect_language_fn=ctx["detect_language"],
        check_local_faq_fn=ctx["check_local_faq"],
    )

    app.include_router(
        ctx["build_admin_misc_router"](
            app_ref=app,
            get_session_fn=ctx["get_session"],
            get_user_fn=ctx["get_user"],
            get_openai_model_fn=ctx["_get_openai_model_runtime"],
            set_openai_model_fn=ctx["_set_openai_model_runtime"],
            allowed_models=ctx["ALLOWED_MODELS"],
            model_change_info=ctx["_model_change_info"],
            send_whatsapp_message_fn=ctx["send_whatsapp_message"],
            admin_phone=ctx["ADMIN_PHONE"],
            whatsapp_phone_id=ctx["WHATSAPP_PHONE_ID"],
            whatsapp_token=ctx["WHATSAPP_TOKEN"],
            conversations_dir=ctx["CONVERSATIONS_DIR"],
            is_paused_fn=ctx["is_paused"],
            authorized_persons=ctx["AUTHORIZED_PERSONS"],
            admin_html=ctx["ADMIN_HTML"],
            reminder_page_html=ctx["REMINDER_PAGE_HTML"],
            reservations_html=ctx["RESERVATIONS_HTML"],
            restaurant_plan_html=ctx["RESTAURANT_PLAN_HTML"],
            dashboard_html=ctx["DASHBOARD_HTML"],
            admin_tools_html=ctx["ADMIN_TOOLS_HTML"],
        ),
        dependencies=[Depends(ctx["require_admin"])],
    )
    app.include_router(
        ctx["build_admin_ops_router"](
            load_settings_fn=ctx["load_settings"],
            save_settings_fn=ctx["save_settings"],
            is_automation_enabled_fn=ctx["is_automation_enabled"],
            is_followup_enabled_fn=ctx["is_followup_enabled"],
            notify_critical_action_fn=ctx["notify_critical_action"],
            conversations_dir=ctx["CONVERSATIONS_DIR"],
            load_conversation_fn=ctx["load_conversation"],
            send_whatsapp_message_fn=ctx["send_whatsapp_message"],
            admin_phone=ctx["ADMIN_PHONE"],
            whatsapp_phone_id=ctx["WHATSAPP_PHONE_ID"],
            whatsapp_token=ctx["WHATSAPP_TOKEN"],
        )
    )
    app.include_router(
        ctx["build_admin_monitoring_router"](
            bot_start_time=ctx["BOT_START_TIME"],
            openai_client=ctx["client"],
            get_openai_model_fn=ctx["_get_openai_model_runtime"],
            whatsapp_phone_id=ctx["WHATSAPP_PHONE_ID"],
            whatsapp_token=ctx["WHATSAPP_TOKEN"],
            error_logs=ctx["ERROR_LOGS"],
            check_local_faq_fn=ctx["check_local_faq"],
            detect_language_fn=ctx["detect_language"],
            get_openai_response_fn=ctx["get_openai_response"],
        ),
        dependencies=[Depends(ctx["require_admin"])],
    )
    app.include_router(
        ctx["build_local_faq_router"](
            local_faq=ctx["LOCAL_FAQ"],
            local_max_words=ctx["LOCAL_MAX_WORDS"],
            check_local_faq_fn=ctx["check_local_faq"],
        ),
        dependencies=[Depends(ctx["require_admin"])],
    )
    app.include_router(
        ctx["build_flow_router"](
            flow_service=flow_service,
            get_conversation_history_fn=ctx["get_conversation_history"],
        ),
        dependencies=[Depends(ctx["require_admin"])],
    )
    access_control_router = ctx["build_access_control_router"](notify_critical_action=ctx["notify_critical_action"])
    app.include_router(access_control_router, dependencies=[Depends(ctx["require_admin"])])
    app.include_router(
        ctx["build_followup_router"](
            is_followup_enabled_fn=ctx["is_followup_enabled"],
            get_pending_followups_fn=ctx["get_pending_followups"],
            send_whatsapp_message_fn=ctx["send_whatsapp_message"],
            get_followup_message_fn=ctx["get_followup_message"],
            mark_followup_sent_fn=ctx["mark_followup_sent"],
            save_message_fn=ctx["save_message"],
            schedule_conversation_cleanup_fn=ctx["schedule_conversation_cleanup"],
            followup_grace_seconds=ctx["FOLLOWUP_GRACE_SECONDS"],
            followup_max_age_minutes=ctx["FOLLOWUP_MAX_AGE_MINUTES"],
            load_followups_fn=ctx["load_followups"],
            save_followups_fn=ctx["save_followups"],
            get_followup_minutes_fn=ctx["get_followup_minutes"],
        ),
        dependencies=[Depends(ctx["require_admin"])],
    )
    app.include_router(
        ctx["build_chat_router"](
            run_chat_prechecks_fn=ctx["run_chat_prechecks"],
            detect_handoff_required_fn=ctx["detect_handoff_required"],
            try_start_restaurant_reservation_flow_fn=ctx["try_start_restaurant_reservation_flow"],
            restaurant_settings=ctx["RESTAURANT_SETTINGS"],
            clear_reservation_flow_fn=ctx["clear_reservation_flow"],
            notify_admin_handoff_fn=ctx["notify_admin_handoff"],
            detect_language_fn=ctx["detect_language"],
            add_to_history_fn=ctx["add_to_history"],
            save_message_fn=ctx["save_message"],
            extract_date_from_message_fn=ctx["extract_date_from_message"],
            parse_date_input_fn=ctx["parse_date_input"],
            extract_date_phrase_fn=ctx["extract_date_phrase"],
            is_within_season_fn=ctx["is_within_season"],
            extract_time_from_message_fn=ctx["extract_time_from_message"],
            get_meal_type_from_time_fn=ctx["get_meal_type_from_time"],
            update_reservation_flow_fn=ctx["update_reservation_flow"],
            reservation_state_cls=ctx["ReservationState"],
            record_metric_fn=ctx["record_metric"],
            try_handle_handoff_and_reservation_flow_fn=ctx["try_handle_handoff_and_reservation_flow"],
            get_reservation_flow_fn=ctx["get_reservation_flow"],
            handle_reservation_flow_fn=ctx["handle_reservation_flow"],
            try_handle_booking_flow_entry_fn=ctx["try_handle_booking_flow_entry"],
            handle_booking_flow_fn=ctx["handle_booking_flow"],
            send_whatsapp_message_fn=ctx["send_whatsapp_message"],
            admin_phone=ctx["ADMIN_PHONE"],
            try_handle_price_flow_entry_fn=ctx["try_handle_price_flow_entry"],
            handle_price_flow_fn=ctx["handle_price_flow"],
            notify_admin_error_fn=ctx["notify_admin_error"],
            schedule_followup_fn=ctx["schedule_followup"],
            try_handle_late_message_checks_fn=ctx["try_handle_late_message_checks"],
            is_conversation_ending_fn=ctx["is_conversation_ending"],
            get_closing_message_fn=ctx["get_closing_message"],
            parse_turkish_date_fn=ctx["parse_turkish_date"],
            is_hotel_open_fn=ctx["is_hotel_open"],
            format_date_turkish_fn=ctx["format_date_turkish"],
            get_welcome_message_fn=ctx["get_welcome_message"],
            is_greeting_fn=ctx["is_greeting"],
            is_menu_selection_fn=ctx["is_menu_selection"],
            get_menu_response_fn=ctx["get_menu_response"],
            try_handle_elektra_price_entry_fn=ctx["try_handle_elektra_price_entry"],
            detect_price_request_fn=ctx["detect_price_request"],
            is_price_flow_active_fn=ctx["is_price_flow_active"],
            handle_elektra_price_request_fn=ctx["handle_elektra_price_request"],
            elektra_config_error_cls=ctx["ElektrawebConfigError"],
            price_natural_date_keywords=ctx["PRICE_NATURAL_DATE_KEYWORDS"],
            price_inquiry_keywords=ctx["PRICE_INQUIRY_KEYWORDS"],
            price_guest_keywords=ctx["PRICE_GUEST_KEYWORDS"],
            try_handle_canonical_and_local_fn=ctx["try_handle_canonical_and_local"],
            check_local_faq_fn=ctx["check_local_faq"],
            canonical_greeting_keywords=ctx["CANONICAL_GREETING_KEYWORDS"],
            kanonik_fiyat_exclusions=ctx["KANONIK_FIYAT_EXCLUSIONS"],
            erken_giris_keywords=ctx["ERKEN_GIRIS_KEYWORDS"],
            gec_cikis_keywords=ctx["GEC_CIKIS_KEYWORDS"],
            handle_openai_fallback_fn=ctx["handle_openai_fallback"],
            openai_client=ctx["client"],
            openai_model=ctx["OPENAI_MODEL"],
            info_system_prompt=ctx["INFO_SYSTEM_PROMPT"],
            maybe_start_qa_background_fn=ctx["maybe_start_qa_background"],
            qa_enabled=ctx["QA_ENABLED"],
            qa_agent=ctx["QA_AGENT"],
            qa_fail_notifications=ctx["_qa_fail_notifications"],
            record_error_fn=ctx["record_error"],
            load_conversation_fn=ctx["load_conversation"],
            is_safe_mode_fn=ctx["is_safe_mode"],
            is_auto_safe_mode_fn=ctx["is_auto_safe_mode"],
            check_rate_limit_fn=ctx["check_rate_limit"],
            is_automation_enabled_fn=ctx["is_automation_enabled"],
            is_blacklisted_fn=ctx["is_blacklisted"],
            is_paused_fn=ctx["is_paused"],
            cancel_followup_fn=ctx["cancel_followup"],
            get_conversation_history_fn=ctx["get_conversation_history"],
            handle_cancel_flow_v2_fn=ctx["handle_cancel_flow_v2"],
            detect_suspicious_message_fn=ctx["detect_suspicious_message"],
            notify_admin_suspicious_fn=ctx["notify_admin_suspicious"],
            ai_question_response=ctx["AI_QUESTION_RESPONSE"],
            suspicious_response=ctx["SUSPICIOUS_RESPONSE"],
            detect_critical_issue_fn=ctx["detect_critical_issue"],
            send_critical_notification_fn=ctx["send_critical_notification"],
            get_price_flow_fn=ctx["get_price_flow"],
            get_booking_flow_fn=ctx["get_booking_flow"],
            get_active_flow_fn=ctx["get_active_flow"],
            set_active_flow_fn=ctx["set_active_flow"],
            clear_active_flow_fn=ctx["clear_active_flow"],
            get_domain_lock_fn=ctx["get_domain_lock"],
            set_domain_lock_fn=ctx["set_domain_lock"],
            clear_domain_lock_fn=ctx["clear_domain_lock"],
            is_processed_message_id_fn=ctx["is_processed_message_id"],
            mark_message_id_processed_fn=ctx["mark_message_id_processed"],
            trace_decision_fn=ctx["trace_decision"],
        )
    )
