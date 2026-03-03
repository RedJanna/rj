# === TIMESTAMP FOR ALL PRINTS ===
import builtins
from datetime import datetime as _dt
_orig_print = builtins.print
import sys
from app.services.request_context_service import get_current_correlation_id
def _ts_print(*a, **k):
    correlation_id = str(get_current_correlation_id() or "").strip() or "n/a"
    prefix = f"[{_dt.now().strftime('%Y-%m-%d %H:%M:%S')} cid={correlation_id}]"
    try:
        _orig_print(prefix, *a, **k)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        def _clean(x):
            s = str(x)
            return s.encode(enc, errors="replace").decode(enc, errors="replace")
        _orig_print(_clean(prefix), *[_clean(x) for x in a], **k)
builtins.print = _ts_print
# === END TIMESTAMP ===
from kassandra_fallback_eklenti import (
    check_rate_limit, is_safe_mode, is_auto_safe_mode,
    get_safe_mode_message, get_rate_limit_message, get_fallback_error_message,
    record_error, enable_safe_mode, disable_safe_mode, get_system_status,
    unblock_rate_limit, get_error_stats, clear_errors
)
from typing import Optional
from app.routes.metrics_routes import router as metrics_router
from app.core.admin_auth import require_admin
from app.utils.message_utils import (
    # greeting/closing/menu
    is_conversation_ending, get_closing_message,
    is_greeting, get_welcome_message,
    is_menu_selection, get_menu_response,
    # language / hotel / price
    detect_language, detect_hotel, detect_price_request,
    extract_date_phrase,
    # local faq
    LOCAL_FAQ, LOCAL_MAX_WORDS, check_local_faq,
)
from fastapi import FastAPI
# ---- Consolidated imports (moved from below) ----
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from app.services.access_control_service import is_blacklisted, is_paused
from apscheduler.schedulers.background import BackgroundScheduler
import os
import re
import asyncio
import time as time_module  # Metrik için

# Ortam degiskenlerini (varsa) proje kokundeki .env dosyasindan yukle.
# NOT: OS seviyesinde set edilen env degerlerini ezmeyiz (override=False).
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DOTENV_PATH = _PROJECT_ROOT / ".env"
if _DOTENV_PATH.exists():
    load_dotenv(dotenv_path=_DOTENV_PATH, override=False)
    print(f"[ENV] .env yüklendi: {_DOTENV_PATH}")

# ======================================================
# YENİ MODÜL IMPORT'LARI (Parçalama sonrası)
# ======================================================
from app.handlers.handoff_handler import detect_handoff_required
from app.handlers.suspicious_handler import (
    detect_suspicious_message,
)
from app.core.settings_service import (
    load_settings, save_settings,
    is_automation_enabled, is_followup_enabled, is_operational_rules_enabled, get_followup_minutes
)
from app.services.followup_service import (
    load_followups, save_followups,
    schedule_followup, cancel_followup, mark_followup_sent, mark_followup_closed,
    save_last_followup_cycle,
    get_pending_followups, get_followup_message,
    get_expired_followups,
    FOLLOWUP_FILE, FOLLOWUP_GRACE_SECONDS, FOLLOWUP_MAX_AGE_MINUTES
)
from app.services.qa_agent_service import QAAgentService
from app.services.whatsapp_sender import build_whatsapp_sender
from app.services.reservation_notifications import build_notify_admin_reservation_change
from app.services.openai_response_service import build_openai_response_fn
from app.services.reservation_pdf_sender import build_reservation_pdf_sender
from app.services.qa_background_service import maybe_start_qa_background
from app.services.notification_service import (
    notify_admin_handoff, notify_admin_error,
    notify_admin_suspicious, send_critical_notification,
    notify_critical_action
)
from app.services.elektraweb_booking_service import (
    handle_elektra_price_request,
    ElektrawebConfigError,
    create_elektraweb_reservation,
    get_elektraweb_reservation,
    update_elektraweb_reservation,
    cancel_elektraweb_reservation,
)
from app.services.elektra_hoteladvisor_service import (
    hoteladvisor_select,
    hoteladvisor_execute,
    hoteladvisor_function,
    hoteladvisor_update,
    get_reservation_guests,
    save_reservation_guest,
    get_portal_installments,
)
from app.services.booking_flow_service import (
    BookingStatus,
    BookingFlowAdapter,
    init_hotel_bookings_db,
    create_hotel_booking,
    get_hotel_booking,
    get_booking_flow,
    update_hotel_booking_status,
    get_pending_hotel_bookings,
    get_all_hotel_bookings,
    get_hotel_booking_stats,
    cleanup_stale_booking_flows,
)
from app.handlers.booking_flow_handler import handle_booking_flow
from app.handlers.openai_fallback_handler import handle_openai_fallback
from app.handlers.restaurant_start_handler import try_start_restaurant_reservation_flow
from app.handlers.elektra_price_entry_handler import try_handle_elektra_price_entry
from app.handlers.booking_flow_entry_handler import try_handle_booking_flow_entry
from app.handlers.price_flow_entry_handler import try_handle_price_flow_entry
from app.handlers.chat_precheck_handler import run_chat_prechecks
from app.handlers.handoff_reservation_handler import try_handle_handoff_and_reservation_flow
from app.handlers.late_message_checks_handler import try_handle_late_message_checks
from app.services.price_flow_service import (
    PriceFlowAdapter,
    save_price_flow,
    get_price_flow,
    clear_price_flow,
    is_waiting_for_guest_count,
    is_price_flow_active,
    save_last_query,
    get_last_query,
)
from app.handlers.price_flow_handler import (
    handle_price_flow,
)
from app.services.restaurant_reservation_flow_service import (
    RestaurantReservationFlowAdapter,
    ReservationState,
    ReservationStatus,
    get_reservation_flow,
    update_reservation_flow,
    clear_reservation_flow,
    should_break_reservation_flow,
    detect_correction_in_message,
    create_reservation,
    format_reservation_confirmation,
    is_within_season,
    get_meal_type_from_time,
    RESTAURANT_SETTINGS,
    cleanup_stale_reservation_flows,
    cancel_reservation,
    get_reservation,
    get_customer_reservations,
    get_reservations_by_date,
    parse_date_input,
    init_reservations_db,
    RESERVATIONS_DB,
    RESERVATION_FLOW_FILE,
    get_upcoming_reservations,
    get_todays_reservations,
    update_reservation_status,
)
# Hatırlatma Sistemi
from app.services.reminder_service import (
    schedule_restaurant_reminder,
    process_due_reminders,
)
from app.routes.reminder_routes import router as reminder_router
from app.routes.pytest_routes import router as pytest_router
from app.routes.auth_routes import router as auth_router
from app.routes.admin_stats_routes import build_admin_stats_router
from app.routes.admin_safety_routes import build_admin_safety_router
from app.routes.admin_reservations_routes import build_admin_reservations_router
from app.routes.admin_transfer_reservations_routes import build_admin_transfer_reservations_router
from app.routes.admin_ops_routes import build_admin_ops_router
from app.routes.admin_monitoring_routes import build_admin_monitoring_router
from app.routes.hotel_bookings_routes import build_hotel_bookings_router
from app.routes.restaurant_plan_routes import build_restaurant_plan_router
from app.routes.admin_misc_routes import build_admin_misc_router
from app.routes.flow_routes import build_flow_router
from app.routes.local_faq_routes import build_local_faq_router
from app.routes.followup_routes import build_followup_router
from app.routes.system_routes import build_system_router
from app.routes.chat_routes import build_chat_router
from app.routes.access_control_routes import build_access_control_router
from app.lifecycle.scheduler_setup import register_scheduler_lifecycle
from app.bootstrap.runtime_entities import (
    ADMIN_PHONE,
    AUTHORIZED_PERSONS,
    RESTAURANT_STAFF,
    ALLOWED_MODELS,
    MODEL_CHANGE_INFO_TEMPLATE,
)
from app.bootstrap.legacy_wiring import configure_http, get_system_test_router, wire_routes
from app.flows.chat_flow_service import ChatFlowService
from app.flows.flow_orchestrator import FlowOrchestrator
from app.flows.reservation_flow_runtime import build_reservation_flow_handler
from app.flows.reservation_parsing import (
    is_hotel_open,
    format_date_turkish,
    format_date_english,
    extract_time_from_message,
    extract_date_from_message,
    extract_all_reservation_info,
)
from app.bootstrap.admin_bootstrap import ensure_initial_admin_user
from app.web.reminder_page import REMINDER_PAGE_HTML
from app.web.transfer_reservations_page import TRANSFER_RESERVATIONS_HTML
from app.web.login_page import LOGIN_PAGE_HTML
from app.core.auth_service import initialize_admin_user, get_session, get_user
from app.services.system_health_service import (
    log_error, get_error_logs, get_system_health, get_api_status,
    ERROR_LOGS, MAX_ERROR_LOGS,
)
from app.services.metrics_service import (
    load_metrics, create_empty_metrics, save_metrics,
    record_metric, get_metrics_summary,
)
from app.services.critical_issue_service import (
    CRITICAL_ISSUE_CATEGORIES,
    NOTIFICATION_SETTINGS,
    is_within_notification_hours,
    detect_critical_issue,
)
from app.services.conversation_store import (
    load_conversation, save_message, save_conversation,
    get_conversation_history, add_to_history,
    clear_conversation, schedule_conversation_cleanup,
    CONVERSATIONS_DIR, hydrate_active_conversations_from_disk,
)
from app.services.routing_state_service import (
    get_active_flow,
    set_active_flow,
    clear_active_flow,
    get_domain_lock,
    set_domain_lock,
    clear_domain_lock,
    resolve_flow_order_for_context,
)
from app.services.message_id_service import (
    is_processed_message_id,
    mark_message_id_processed,
)
from app.services.decision_trace_service import trace_decision
from app.services.active_learning_service import capture_active_learning_sample
from app.services.daily_learning_report_service import build_daily_learning_report
from app.services.cancel_service import handle_cancel_flow_v2, init_cancel_service, _notify_admin_cancel_v2
from app.services.pdf_service import generate_reservation_pdf
import psutil
import platform
# Refactor split: helpers / templates
from app.utils.date_parser import parse_turkish_date
from app.web.admin_pages import (
    ADMIN_HTML, RESERVATIONS_HTML, DASHBOARD_HTML, ADMIN_TOOLS_HTML, RESTAURANT_PLAN_HTML,
)
from app.content.prompts import (
    HANDOFF_RESPONSE_TR, HANDOFF_RESPONSE_EN,
    AI_QUESTION_RESPONSE, SUSPICIOUS_RESPONSE,
)
from app.content.chat_keywords import (
    PRICE_NATURAL_DATE_KEYWORDS,
    PRICE_INQUIRY_KEYWORDS,
    PRICE_GUEST_KEYWORDS,
)
from app.content.system_prompt import INFO_SYSTEM_PROMPT
BOT_START_TIME = datetime.now()
FLOW_ORCHESTRATOR_MODE = os.getenv("FLOW_ORCHESTRATOR_MODE", "shadow").strip().lower() or "shadow"
FLOW_ORCHESTRATOR = FlowOrchestrator(
    flows=[
        ("restaurant", RestaurantReservationFlowAdapter()),
        ("price", PriceFlowAdapter()),
        ("booking", BookingFlowAdapter()),
    ],
    mode=FLOW_ORCHESTRATOR_MODE,
    flow_selector=lambda context, available_flow_names: resolve_flow_order_for_context(
        message=context.message,
        state=context.state or {},
        available_flow_names=available_flow_names,
    ),
)
# >>> ADD_START: QA_AGENT_CLASS
# ======================================================
# QA AGENT - Cevap Kalitesi Değerlendirme
# ======================================================
QA_ENABLED = True
QA_LOG_FILE = str(_PROJECT_ROOT / "data" / "qa_evaluations.json")
_qa_fail_notifications = []  # QA FAIL bildirim spam önleme için
# <<< ADD_END: QA_AGENT_CLASS
# ======================================================
# 1. OpenAI client
# ======================================================
API_KEY_ENV = os.getenv("OPENAI_API_KEY", "").strip()
if not API_KEY_ENV:
    raise RuntimeError(
        "OpenAI API anahtarı bulunamadı. Lütfen OPENAI_API_KEY ortam değişkenini ayarla."
    )
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini"
client = OpenAI(api_key=API_KEY_ENV)
QA_AGENT = QAAgentService(client, OPENAI_MODEL, QA_LOG_FILE)
# ======================================================
# 2. WHATSAPP API AYARLARI (Follow-up için gerekli)
# ======================================================
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID", "").strip()  # Meta Phone Number ID
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "").strip()  # Meta Access Token
send_whatsapp_message = build_whatsapp_sender(WHATSAPP_PHONE_ID, WHATSAPP_TOKEN)
send_reservation_pdf = build_reservation_pdf_sender(
    generate_reservation_pdf_fn=generate_reservation_pdf,
    whatsapp_phone_id=WHATSAPP_PHONE_ID,
    whatsapp_token=WHATSAPP_TOKEN,
)
handle_reservation_flow = build_reservation_flow_handler(
    get_conversation_history_fn=get_conversation_history,
    detect_language_fn=detect_language,
    update_reservation_flow_fn=update_reservation_flow,
    clear_reservation_flow_fn=clear_reservation_flow,
    should_break_reservation_flow_fn=should_break_reservation_flow,
    detect_correction_in_message_fn=detect_correction_in_message,
    extract_all_reservation_info_fn=extract_all_reservation_info,
    get_meal_type_from_time_fn=get_meal_type_from_time,
    notify_admin_handoff_fn=notify_admin_handoff,
    is_within_season_fn=is_within_season,
    reservation_state_cls=ReservationState,
    format_date_turkish_fn=format_date_turkish,
    format_date_english_fn=format_date_english,
    create_reservation_fn=create_reservation,
    format_reservation_confirmation_fn=format_reservation_confirmation,
    send_reservation_pdf_fn=send_reservation_pdf,
    schedule_restaurant_reminder_fn=schedule_restaurant_reminder,
)
# Yapay zeka sorusuna verilecek STANDART CEVAP
# Şüpheli durumda verilecek STANDART CEVAP
notify_admin_reservation_change = build_notify_admin_reservation_change(
    send_whatsapp_message_fn=send_whatsapp_message,
    get_reservation_fn=get_reservation,
    admin_phone=ADMIN_PHONE,
    restaurant_staff=RESTAURANT_STAFF,
)
# ======================================================
# 13. FastAPI APP
# ======================================================
app = FastAPI(title="Kassandra WhatsApp Bot")
configure_http(app, require_admin)
system_test_router = get_system_test_router()
try:
    recovery_limit = int(os.getenv("ACTIVE_CONVERSATION_RECOVERY_LIMIT", "300"))
except Exception:
    recovery_limit = 300
_recovery = hydrate_active_conversations_from_disk(limit=max(1, recovery_limit))
print(
    "[ACTIVE-CONV] Startup recovery done | "
    f"scanned={_recovery.get('scanned', 0)} restored={_recovery.get('restored', 0)}"
)
def _get_openai_model_runtime() -> str:
    return OPENAI_MODEL
def _set_openai_model_runtime(new_model: str) -> None:
    global OPENAI_MODEL
    OPENAI_MODEL = new_model
def _get_system_prompt_runtime() -> str:
    return INFO_SYSTEM_PROMPT
get_openai_response = build_openai_response_fn(
    client=client,
    model_getter=_get_openai_model_runtime,
    system_prompt_getter=_get_system_prompt_runtime,
    get_conversation_history_fn=get_conversation_history,
)
_model_change_info = dict(MODEL_CHANGE_INFO_TEMPLATE)
wire_routes(app, ctx=globals(), system_test_router=system_test_router)
# ======================================================
# SCHEDULER - Günlük Rapor & Self-Test
# ======================================================
scheduler = BackgroundScheduler()
# <<< ADD_END: COALESCE_BACKGROUND_JOB
# Stale flow temizliği: Her 1 saatte bir (24 saatten düşürüldü)
scheduler.add_job(cleanup_stale_reservation_flows, 'interval', hours=1)


def _split_whatsapp_report(message: str, limit: int = 3200) -> list[str]:
    text = (message or "").strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    lines = text.splitlines()
    current = ""
    for line in lines:
        candidate = f"{current}\n{line}".strip() if current else line
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
        current = line
    if current:
        chunks.append(current)
    return chunks


def _run_daily_learning_report():
    """Günlük aktif öğrenme raporunu admin'e gönderir."""
    try:
        report_text = build_daily_learning_report()
        parts = _split_whatsapp_report(report_text)
        for idx, part in enumerate(parts, start=1):
            header = f"[{idx}/{len(parts)}]\n" if len(parts) > 1 else ""
            asyncio.run(send_whatsapp_message(ADMIN_PHONE, f"{header}{part}"))
        print("📘 Günlük öğrenme raporu gönderildi")
    except Exception as e:
        print(f"❌ Günlük öğrenme raporu hatası: {e}")


def _run_followup_cycle():
    """10.dk hatırlatma gönder, 30.dk yanıtsız sohbetleri otomatik kapat/temizle."""
    if not is_followup_enabled():
        return
    try:
        pending = get_pending_followups()
        for phone in pending:
            ok = asyncio.run(send_whatsapp_message(phone, get_followup_message()))
            if ok:
                mark_followup_sent(phone)
                save_message(phone, "[FOLLOW-UP]", get_followup_message())
                print(f"✅ Follow-up gönderildi (scheduler): {phone}")

        expired = get_expired_followups()
        for phone in expired:
            schedule_conversation_cleanup(phone, delay_minutes=0)
            mark_followup_closed(phone)
            print(f"🧹 Sohbet otomatik kapatıldı/temizlendi (scheduler): {phone}")
        save_last_followup_cycle(sent=len(pending), closed=len(expired))
    except Exception as e:
        print(f"❌ Follow-up cycle hatası: {e}")


# Follow-up kontrolü: dakikada 1
scheduler.add_job(_run_followup_cycle, 'interval', minutes=1)
# Günlük öğrenme raporu: her gün 09:00
scheduler.add_job(_run_daily_learning_report, 'cron', hour=9, minute=0, id='daily_learning_report_job')
register_scheduler_lifecycle(
    app=app,
    scheduler=scheduler,
    init_reservations_db_fn=init_reservations_db,
    init_hotel_bookings_db_fn=init_hotel_bookings_db,
    init_cancel_service_fn=init_cancel_service,
    load_conversation_fn=load_conversation,
    save_conversation_fn=save_conversation,
    send_whatsapp_message_fn=send_whatsapp_message,
    admin_phone=ADMIN_PHONE,
    cancel_reservation_fn=cancel_reservation,
    get_reservation_fn=get_reservation,
    get_customer_reservations_fn=get_customer_reservations,
    reservation_status=ReservationStatus,
    process_due_reminders_fn=process_due_reminders,
)
ensure_initial_admin_user(initialize_admin_user_fn=initialize_admin_user)
