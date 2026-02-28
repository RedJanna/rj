from __future__ import annotations

import os
import re
import time as time_module
from difflib import SequenceMatcher
from typing import Any, Optional

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from app.content.intent_taxonomy import INTENT_AUTO_CONFIDENCE_THRESHOLD
from app.flows.flow_context import FlowContext as RequestFlowContext
from app.services.correlation_service import CORRELATION_HEADER, resolve_correlation_id
from app.services.flow_fsm_service import decide_execution_order
from app.services.intent_policy_service import infer_primary_intent
from app.services.intent_router_service import infer_domain_hint, route_intent
from app.services.policy_guard_service import evaluate_policy_guard, is_new_pipeline_enabled
from app.services.slot_contract_service import (
    evaluate_slot_coverage,
    get_missing_slot_prompt,
    should_request_slot_clarification,
)
from app.services.structured_log_service import log_event


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
    "ozel": "özel",
    "isteginiz": "isteğiniz",
    "numarasi": "numarası",
    "musait": "müsait",
    "farkli": "farklı",
    "bulunamadi": "bulunamadı",
    "yetiskin": "yetişkin",
    "tesekkur": "teşekkür",
    "kahvalti": "kahvaltı",
    "odeme": "ödeme",
    "guncel": "güncel",
    "musteri": "müşteri",
    "ucretsiz": "ücretsiz",
    "cikis": "çıkış",
    "giris": "giriş",
    "degisiklik": "değişiklik",
    "iletisim": "iletişim",
    "hizli": "hızlı",
    "sifre": "şifre",
    "konusma": "konuşma",
    "kisa": "kısa",
}

_TR_ASCII_SIGNAL_WORDS = {
    "kahvalti",
    "dahil",
    "degilse",
    "kisi",
    "yetiskin",
    "cocuk",
    "giris",
    "cikis",
    "havalimani",
    "rezervasyon",
    "fiyat",
    "ucret",
    "musait",
    "kapora",
    "odeme",
    "tesekkur",
    "yardimci",
    "balayi",
    "surpriz",
}


LANGUAGE_PRIORITY = ["en", "tr", "ru", "de", "ar", "es", "fr", "zh", "hi", "pt"]
TRANSLATION_ONLY_LANGS = {"de", "ar", "es", "fr", "zh", "hi", "pt"}
LANGUAGE_NAME_ALIASES = {
    "en": ["english", "ingilizce"],
    "tr": ["turkish", "türkçe", "turkce"],
    "ru": ["russian", "rusça", "rusca", "русский", "по-русски"],
    "de": ["german", "almanca", "deutsch"],
    "ar": ["arabic", "arapça", "arapca", "العربية", "عربي"],
    "es": ["spanish", "ispanyolca", "español", "espanol"],
    "fr": ["french", "fransızca", "fransizca", "français", "francais"],
    "zh": ["chinese", "çince", "cince", "中文", "汉语", "漢語"],
    "hi": ["hindi", "hintçe", "hintce", "हिंदी"],
    "pt": ["portuguese", "portekizce", "português", "portugues"],
}
LANGUAGE_SWITCH_MARKERS = [
    "speak",
    "talk",
    "continue in",
    "write in",
    "konuş",
    "konusalim",
    "konuşalım",
    "devam edelim",
    "yaz",
]
UNSUPPORTED_LANGUAGE_HINTS = [
    "japanese",
    "japonca",
    "日本語",
    "italian",
    "italyanca",
    "italiano",
    "korean",
    "korece",
    "한국어",
]


def _normalize_turkish_reply_text(text: str) -> str:
    if not text:
        return text
    out = text
    for src, dst in _TR_SPELLING_MAP.items():
        out = re.sub(rf"\b{re.escape(src)}\b", dst, out, flags=re.IGNORECASE)
        out = re.sub(rf"\b{re.escape(src.capitalize())}\b", dst.capitalize(), out)
        out = re.sub(rf"\b{re.escape(src.upper())}\b", dst.upper(), out)
    return out


def _normalize_language_code(lang: str) -> str:
    code = (lang or "").strip().lower()
    return code if code in LANGUAGE_PRIORITY else "en"


def _extract_language_switch_request(text: str) -> tuple[str, bool]:
    low = (text or "").strip().lower()
    if not low:
        return "", False
    has_marker = any(marker in low for marker in LANGUAGE_SWITCH_MARKERS) or "?" in low
    for lang, aliases in LANGUAGE_NAME_ALIASES.items():
        if any(alias in low for alias in aliases) and has_marker:
            return lang, True
    if has_marker and any(hint in low for hint in UNSUPPORTED_LANGUAGE_HINTS):
        return "en", False
    return "", False


def _language_switch_confirmation(target_lang: str, supported: bool) -> str:
    if not supported:
        return "I can continue in English. Supported languages: English, Turkish, Russian, German, Arabic, Spanish, French, Chinese, Hindi, Portuguese."
    if target_lang == "tr":
        return "Elbette, Türkçe devam edebiliriz. Size nasıl yardımcı olabilirim?"
    if target_lang == "ru":
        return "Конечно, можем продолжить на русском. Чем могу помочь?"
    if target_lang == "en":
        return "Yes, of course. We can continue in English. How can I help you?"
    return "Sure. We can continue in this language. How can I help you?"


def _extract_language_from_switch_confirmation(text: str) -> str:
    low = (text or "").strip().lower()
    if not low:
        return ""
    if "türkçe devam" in low or "turkce devam" in low:
        return "tr"
    if "continue in english" in low:
        return "en"
    if "продолжить на русском" in low:
        return "ru"
    return ""


def _looks_like_turkish_ascii_message(text: str) -> bool:
    raw = (text or "").strip().lower()
    if not raw:
        return False
    # Turkish chars are already a strong signal.
    if any(ch in raw for ch in ("ç", "ğ", "ı", "ö", "ş", "ü")):
        return True
    tokens = re.findall(r"[a-zA-Z]+", raw)
    if not tokens:
        return False
    hits = sum(1 for token in tokens if token in _TR_ASCII_SIGNAL_WORDS)
    return hits >= 2


def _resolve_language_lock(phone: str, user_message: str, load_conversation_fn, detect_language_fn) -> str:
    raw_msg = (user_message or "").strip()

    def _is_ambiguous_lang_message(text: str) -> bool:
        t = (text or "").strip()
        if not t:
            return True
        if re.fullmatch(r"[\d\W_]+", t):
            return True
        low = t.lower()
        # Slot cevapları (Rez ID / Voucher / kısa kodlar) dil sinyali sayılmamalı.
        if re.fullmatch(
            r"(?:rez(?:ervasyon)?|reservation|voucher)\s*(?:id|no|number)?[\s:#\-]*[a-z0-9\.\-]+",
            low,
        ):
            return True
        # Birden fazla slotu tek mesajda dolduran payloadlar da (Rez ID + ad soyad + 1/2)
        # dil kilidini değiştirmemeli.
        has_rez_slot = bool(
            re.search(
                r"(?:rez(?:ervasyon)?\s*(?:id|no)?|reservation\s*(?:id|no)?|voucher\s*(?:no|number)?)\s*[:#\-]?\s*[a-z0-9\.\-]{4,}",
                low,
            )
        )
        has_name_slot = any(marker in low for marker in ("ad soyad", "full name", "name"))
        has_rate_choice = bool(re.search(r"(?:^|[\s,;:\-])[12](?:$|[\s,;:\-])", low))
        if has_rez_slot and (has_name_slot or has_rate_choice):
            return True
        return len(t) <= 2

    direct_target, _ = _extract_language_switch_request(user_message or "")
    if direct_target:
        return direct_target
    current = _normalize_language_code(detect_language_fn(user_message or ""))
    if current == "en" and _looks_like_turkish_ascii_message(raw_msg):
        current = "tr"

    if not phone:
        return "tr" if _is_ambiguous_lang_message(raw_msg) else current
    try:
        conv = load_conversation_fn(phone) or {}
        messages = conv.get("messages") or []
        for msg in reversed(messages):
            txt = (msg.get("user_message") or "").strip()
            target, _ = _extract_language_switch_request(txt)
            if target:
                return target
            bot_txt = (msg.get("bot_reply") or "").strip()
            bot_target, _ = _extract_language_switch_request(bot_txt)
            if bot_target:
                return bot_target
            confirmed_target = _extract_language_from_switch_confirmation(bot_txt)
            if confirmed_target:
                return confirmed_target

        # Açık ve yeterince uzun mevcut kullanıcı mesajı, geçmiş dil tahminini ezebilsin.
        # Explicit dil değişimi varsa yukarıda zaten return edilmiştir.
        if not _is_ambiguous_lang_message(raw_msg):
            token_count = len(re.findall(r"\w+", raw_msg, flags=re.UNICODE))
            if token_count >= 4:
                return current

        for msg in reversed(messages):
            txt = (msg.get("user_message") or "").strip()
            if txt:
                if _is_ambiguous_lang_message(txt):
                    continue
                return _normalize_language_code(detect_language_fn(txt))
        if messages:
            for msg in reversed(messages):
                bot_txt = (msg.get("bot_reply") or "").strip()
                if not bot_txt:
                    continue
                return _normalize_language_code(detect_language_fn(bot_txt))
    except Exception:
        pass
    if _is_ambiguous_lang_message(raw_msg):
        return "tr"
    return current


def _translate_reply_if_needed(reply: str, target_lang: str, openai_client, openai_model: str) -> str:
    text = (reply or "").strip()
    lang = _normalize_language_code(target_lang)
    if not text or lang not in TRANSLATION_ONLY_LANGS:
        return text
    if not openai_client or os.getenv("OPENAI_API_KEY", "").strip().lower().startswith("test-"):
        return text
    try:
        translated = openai_client.chat.completions.create(
            model=openai_model,
            temperature=0,
            max_tokens=700,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"Translate the assistant message to {lang.upper()}. "
                        "Keep meaning exactly, preserve URLs/phone numbers, output only translation."
                    ),
                },
                {"role": "user", "content": text},
            ],
        )
        content = (translated.choices[0].message.content or "").strip()
        return content or text
    except Exception:
        return text


def _compute_sentiment_and_frustration(user_message: str, history: list[dict]) -> dict[str, Any]:
    text = (user_message or "").lower()
    negative_words = [
        "saçma", "berbat", "kötü", "rezalet", "şikayet", "sinir", "angry", "bad", "terrible", "useless",
    ]
    positive_words = ["teşekkür", "harika", "iyi", "thanks", "great", "perfect"]

    neg = sum(1 for w in negative_words if w in text)
    pos = sum(1 for w in positive_words if w in text)

    if neg > pos:
        sentiment = "neg"
    elif pos > neg:
        sentiment = "pos"
    else:
        sentiment = "neu"

    intensity = min(1.0, 0.25 + (abs(neg - pos) * 0.2)) if (neg or pos) else 0.2
    confidence = min(1.0, 0.4 + ((neg + pos) * 0.1))

    recent_user_messages: list[str] = []
    for item in history[-8:]:
        if item.get("role") == "user":
            recent_user_messages.append((item.get("content") or "").strip().lower())

    current = (user_message or "").strip().lower()
    repeat_count = 0
    for prev in recent_user_messages[-4:]:
        if not prev or not current:
            continue
        ratio = SequenceMatcher(None, prev, current).ratio()
        if ratio >= 0.82:
            repeat_count += 1
    frustration_loop = repeat_count >= 2

    return {
        "sentiment": sentiment,
        "intensity": round(float(intensity), 3),
        "confidence": round(float(confidence), 3),
        "frustration_loop": frustration_loop,
    }


def _domain_hint_from_message(message: str) -> str:
    m = (message or "").lower()
    if any(k in m for k in ["restaurant", "restoran", "masa"]):
        return "restaurant"
    if any(k in m for k in ["ödeme", "odeme", "payment", "link"]):
        return "payment"
    if any(k in m for k in ["fiyat", "price", "oda", "rezervasyon", "booking"]):
        return "hotel"
    return "unknown"


def _should_bypass_strict_ai_first(message: str) -> bool:
    """
    Fiyat/müsaitlik/rezervasyon niyeti varsa deterministic flow'lara öncelik ver.
    Bu sayede LLM'in teknik placeholder veya erken bilgi isteme üretmesi engellenir.
    """
    domain_hint = infer_domain_hint(message)
    intent = infer_primary_intent(message, domain_hint)
    return intent in {"PRICE_QUERY", "AVAILABILITY_QUERY", "HOTEL_BOOKING_CREATE"}


def _should_send_first_message_welcome(message: str) -> bool:
    if str(os.getenv("DISABLE_FIRST_WELCOME", "false")).strip().lower() in {"1", "true", "yes", "on"}:
        return False
    text = (message or "").strip().lower()
    if not text:
        return True
    if text in {"1", "2", "3", "4"}:
        return True
    greeting_markers = [
        "merhaba",
        "selam",
        "slm",
        "hello",
        "hi",
        "hey",
        "привет",
        "здравствуйте",
    ]
    return any(text == marker or text.startswith(f"{marker} ") for marker in greeting_markers)


def build_chat_router(**deps):
    router = APIRouter()
    new_pipeline_enabled = is_new_pipeline_enabled(os.getenv("NEW_PIPELINE_ENABLED"))
    strict_ai_first = str(os.getenv("STRICT_AI_FIRST", "true")).strip().lower() in {"1", "true", "yes", "on"}

    @router.post("/chat", response_model=ChatResponse)
    async def chat_endpoint(payload: ChatRequest, request: Request, response: Response):
        start_time = time_module.time()
        user_message = (payload.message or "").strip()
        phone = (payload.phone or "").strip()
        message_id = (payload.message_id or "").strip()

        correlation_id = (
            getattr(getattr(request, "state", object()), "correlation_id", None)
            or resolve_correlation_id(getattr(request, "headers", {}))
        )
        response.headers[CORRELATION_HEADER] = correlation_id

        flow_context = RequestFlowContext(
            correlation_id=correlation_id,
            phone=phone,
            message_id=message_id or None,
            request_path=request.url.path,
            request_method=request.method,
        )

        detect_language_fn = deps["detect_language_fn"]
        load_conversation_fn = deps["load_conversation_fn"]
        initial_lang = _resolve_language_lock(phone, user_message, load_conversation_fn, detect_language_fn)

        def _locked_detect_language_fn(_: str) -> str:
            return initial_lang

        log_event(
            "chat.request.received",
            correlation_id=correlation_id,
            phone=phone,
            message_id=message_id,
            path=request.url.path,
            method=request.method,
            message_len=len(user_message),
        )

        def trace_event(payload_dict):
            deps["trace_decision_fn"]({**flow_context.as_dict(), **(payload_dict or {})})

        def resp(
            reply: str,
            status: str = "ok",
            reservation_log=None,
            is_price_template: bool = False,
            reason_code: Optional[str] = None,
            next_expected_input: Optional[str] = None,
        ):
            normalized_reply = reply or ""
            if initial_lang == "tr":
                normalized_reply = _normalize_turkish_reply_text(normalized_reply)
            normalized_reply = _translate_reply_if_needed(
                normalized_reply,
                initial_lang,
                deps["openai_client"],
                deps["openai_model"],
            )
            elapsed_ms = int((time_module.time() - start_time) * 1000)
            log_event(
                "chat.response",
                correlation_id=correlation_id,
                phone=phone,
                message_id=message_id,
                status=status,
                reason_code=reason_code,
                elapsed_ms=elapsed_ms,
            )
            return ChatResponse(
                reply=normalized_reply,
                status=status,
                reservation_log=reservation_log,
                is_price_template=is_price_template,
                reason_code=reason_code,
                next_expected_input=next_expected_input,
            )

        # STAGE 1: Ingress
        if phone and message_id and deps["is_processed_message_id_fn"](phone, message_id):
            trace_event({"stage": "ingress", "event": "duplicate_message_id"})
            return resp(reply="", status="duplicate_message_id")
        if phone and message_id:
            deps["mark_message_id_processed_fn"](phone, message_id)

        # STAGE 2: Context/State Builder + STAGE 4: Gating/Moderation
        precheck = await deps["run_chat_prechecks_fn"](
            phone=phone,
            user_message=user_message,
            detect_language_fn=_locked_detect_language_fn,
            load_conversation_fn=deps["load_conversation_fn"],
            notify_admin_error_fn=deps["notify_admin_error_fn"],
            save_message_fn=deps["save_message_fn"],
            is_safe_mode_fn=deps["is_safe_mode_fn"],
            is_auto_safe_mode_fn=deps["is_auto_safe_mode_fn"],
            check_rate_limit_fn=deps["check_rate_limit_fn"],
            is_automation_enabled_fn=deps["is_automation_enabled_fn"],
            is_operational_rules_enabled_fn=deps.get("is_operational_rules_enabled_fn", lambda: True),
            is_blacklisted_fn=deps["is_blacklisted_fn"],
            is_paused_fn=deps["is_paused_fn"],
            cancel_followup_fn=deps["cancel_followup_fn"],
            get_conversation_history_fn=deps["get_conversation_history_fn"],
            handle_cancel_flow_v2_fn=deps["handle_cancel_flow_v2_fn"],
            detect_suspicious_message_fn=deps["detect_suspicious_message_fn"],
            notify_admin_suspicious_fn=deps["notify_admin_suspicious_fn"],
            ai_question_response=deps["ai_question_response"],
            suspicious_response=deps["suspicious_response"],
            add_to_history_fn=deps["add_to_history_fn"],
            detect_critical_issue_fn=deps["detect_critical_issue_fn"],
            send_critical_notification_fn=deps["send_critical_notification_fn"],
            response_factory=resp,
            notify_admin_handoff_fn=deps["notify_admin_handoff_fn"],
            activate_human_takeover_fn=deps.get("activate_human_takeover_fn", lambda *_a, **_k: None),
            flow_context=flow_context,
        )
        if precheck["response"] is not None:
            trace_event({"stage": "gating", "event": "blocked", "status": getattr(precheck["response"], "status", "")})
            return precheck["response"]

        lang = _normalize_language_code(precheck.get("lang") or initial_lang)
        history = precheck.get("history") or []

        if not history and _should_send_first_message_welcome(user_message):
            welcome_reply = deps["get_welcome_message_fn"](lang)
            deps["add_to_history_fn"](phone, "user", user_message)
            deps["add_to_history_fn"](phone, "assistant", welcome_reply)
            deps["save_message_fn"](phone, user_message, welcome_reply)
            deps["schedule_followup_fn"](phone)
            deps["record_metric_fn"]("first_message", response_time=time_module.time() - start_time)
            trace_event({"stage": "response_generator", "event": "first_message_welcome"})
            return resp(reply=welcome_reply, status="first_message")

        has_active_domain_flow = bool(
            deps["get_reservation_flow_fn"](phone)
            or deps["get_price_flow_fn"](phone)
            or deps["get_booking_flow_fn"](phone)
            or deps["get_active_flow_fn"](phone)
        )

        if strict_ai_first and not (has_active_domain_flow or _should_bypass_strict_ai_first(user_message)):
            trace_event({"stage": "response_generator", "event": "strict_ai_first"})
            return await deps["handle_openai_fallback_fn"](
                client=deps["openai_client"],
                openai_model=deps["openai_model"],
                info_system_prompt=deps["info_system_prompt"],
                history=history,
                user_message=user_message,
                phone=phone,
                start_time=start_time,
                add_to_history_fn=deps["add_to_history_fn"],
                save_message_fn=deps["save_message_fn"],
                schedule_followup_fn=deps["schedule_followup_fn"],
                record_metric_fn=deps["record_metric_fn"],
                maybe_start_qa_background_fn=deps["maybe_start_qa_background_fn"],
                qa_enabled=deps["qa_enabled"],
                qa_agent=deps["qa_agent"],
                admin_phone=deps["admin_phone"],
                send_whatsapp_message_fn=deps["send_whatsapp_message_fn"],
                qa_fail_notifications=deps["qa_fail_notifications"],
                record_error_fn=deps["record_error_fn"],
                response_factory=resp,
                flow_context=flow_context,
                notify_admin_handoff_fn=deps.get("notify_admin_handoff_fn"),
                activate_human_takeover_fn=deps.get("activate_human_takeover_fn"),
                detected_intent="AI_FALLBACK",
                handoff_source="chat_pipeline.strict_ai_first",
            )
        if strict_ai_first:
            trace_event(
                {
                    "stage": "response_generator",
                    "event": "strict_ai_first_bypassed_for_domain_flow",
                    "has_active_domain_flow": has_active_domain_flow,
                }
            )

        # STAGE 3: Sentiment & Frustration
        sf = _compute_sentiment_and_frustration(user_message, history)
        trace_event({"stage": "sentiment", **sf})

        # Explicit language switch
        switch_target, switch_supported = _extract_language_switch_request(user_message)
        if switch_target:
            switch_reply = _language_switch_confirmation(switch_target, switch_supported)
            deps["add_to_history_fn"](phone, "user", user_message)
            deps["add_to_history_fn"](phone, "assistant", switch_reply)
            deps["save_message_fn"](phone, user_message, switch_reply)
            deps["schedule_followup_fn"](phone)
            deps["record_metric_fn"]("language_switch", category=switch_target, response_time=time_module.time() - start_time)
            trace_event({"stage": "context", "event": "language_switch", "target": switch_target, "supported": switch_supported})
            return resp(
                reply=switch_reply,
                status="language_switch",
                reason_code="language_switch_supported" if switch_supported else "language_switch_unsupported",
            )

        if new_pipeline_enabled:
            policy = evaluate_policy_guard(user_message, lang=initial_lang)
            trace_event({"stage": "policy_guard", "enabled": True, "handled": bool(policy.get("handled")), "meta": policy.get("meta")})
            if policy.get("handled"):
                deps["add_to_history_fn"](phone, "user", user_message)
                deps["add_to_history_fn"](phone, "assistant", policy.get("reply", ""))
                deps["save_message_fn"](phone, user_message, policy.get("reply", ""))
                deps["schedule_followup_fn"](phone)
                deps["record_metric_fn"]("policy_guard", category=policy.get("status", "policy_guard"), response_time=time_module.time() - start_time)
                return resp(
                    reply=policy.get("reply", ""),
                    status=policy.get("status", "policy_guard"),
                    reason_code=policy.get("reason_code"),
                )

        # STAGE 5: Intent + Routing
        domain_hint = infer_domain_hint(user_message) if new_pipeline_enabled else _domain_hint_from_message(user_message)
        if new_pipeline_enabled:
            routed = route_intent(user_message, domain_hint)
            primary_intent = routed["primary_intent"]
            trace_event({"stage": "intent_router", "enabled": True, **routed})
        else:
            primary_intent = infer_primary_intent(user_message, domain_hint)
        slot_coverage = evaluate_slot_coverage(primary_intent, user_message)
        trace_event(
            {
                "stage": "intent_routing",
                "primary_intent": primary_intent,
                "domain_hint": domain_hint,
                "slot_coverage": slot_coverage,
            }
        )

        has_active_flow = bool(
            deps["get_active_flow_fn"](phone)
            or deps["get_reservation_flow_fn"](phone)
            or deps["get_price_flow_fn"](phone)
            or deps["get_booking_flow_fn"](phone)
        )
        if should_request_slot_clarification(primary_intent, slot_coverage, has_active_flow=has_active_flow):
            clarify_prompt = get_missing_slot_prompt(primary_intent) or "Lutfen eksik bilgileri tamamlayin."
            deps["add_to_history_fn"](phone, "user", user_message)
            deps["add_to_history_fn"](phone, "assistant", clarify_prompt)
            deps["save_message_fn"](phone, user_message, clarify_prompt)
            deps["record_metric_fn"]("clarify_loop", category=primary_intent, response_time=time_module.time() - start_time)
            return resp(reply=clarify_prompt, status="clarify_required", reason_code="missing_required_slots")

        # STAGE 6: Tool/Flow Executor
        needs_handoff, handoff_category, handoff_priority, handoff_msg_tr, handoff_msg_en, handoff_msg_ru = deps[
            "detect_handoff_required_fn"
        ](user_message)

        restaurant_response = await deps["try_start_restaurant_reservation_flow_fn"](
            needs_handoff=needs_handoff,
            handoff_category=handoff_category,
            user_message=user_message,
            phone=phone,
            start_time=start_time,
            history=history,
            restaurant_settings=deps["restaurant_settings"],
            clear_reservation_flow_fn=deps["clear_reservation_flow_fn"],
            notify_admin_handoff_fn=deps["notify_admin_handoff_fn"],
            detect_language_fn=_locked_detect_language_fn,
            add_to_history_fn=deps["add_to_history_fn"],
            save_message_fn=deps["save_message_fn"],
            response_factory=resp,
            extract_date_from_message_fn=deps["extract_date_from_message_fn"],
            parse_date_input_fn=deps["parse_date_input_fn"],
            extract_date_phrase_fn=deps["extract_date_phrase_fn"],
            is_within_season_fn=deps["is_within_season_fn"],
            extract_time_from_message_fn=deps["extract_time_from_message_fn"],
            get_meal_type_from_time_fn=deps["get_meal_type_from_time_fn"],
            update_reservation_flow_fn=deps["update_reservation_flow_fn"],
            reservation_state_cls=deps["reservation_state_cls"],
            record_metric_fn=deps["record_metric_fn"],
        )
        if restaurant_response is not None:
            return restaurant_response

        handoff_or_reservation = await deps["try_handle_handoff_and_reservation_flow_fn"](
            needs_handoff=needs_handoff,
            handoff_category=handoff_category,
            handoff_priority=handoff_priority,
            handoff_msg_tr=handoff_msg_tr,
            handoff_msg_en=handoff_msg_en,
            handoff_msg_ru=handoff_msg_ru,
            user_message=user_message,
            phone=phone,
            start_time=start_time,
            notify_admin_handoff_fn=deps["notify_admin_handoff_fn"],
            detect_language_fn=_locked_detect_language_fn,
            add_to_history_fn=deps["add_to_history_fn"],
            save_message_fn=deps["save_message_fn"],
            record_metric_fn=deps["record_metric_fn"],
            get_reservation_flow_fn=deps["get_reservation_flow_fn"],
            reservation_state_cls=deps["reservation_state_cls"],
            handle_reservation_flow_fn=deps["handle_reservation_flow_fn"],
            response_factory=resp,
            flow_context=flow_context,
        )
        if handoff_or_reservation is not None:
            return handoff_or_reservation

        async def _run_booking_chain():
            booking_entry = await deps["try_handle_booking_flow_entry_fn"](
                phone=phone,
                user_message=user_message,
                history=history,
                start_time=start_time,
                detect_language_fn=_locked_detect_language_fn,
                handle_booking_flow_fn=deps["handle_booking_flow_fn"],
                add_to_history_fn=deps["add_to_history_fn"],
                save_message_fn=deps["save_message_fn"],
                record_metric_fn=deps["record_metric_fn"],
                send_whatsapp_message_fn=deps["send_whatsapp_message_fn"],
                admin_phone=deps["admin_phone"],
                response_factory=resp,
            )
            if booking_entry is not None:
                return booking_entry

            booking_flow_result = await deps["handle_booking_flow_fn"](phone, user_message, history=history, lang=lang)
            if booking_flow_result is not None:
                if isinstance(booking_flow_result, dict):
                    return resp(
                        reply=booking_flow_result.get("reply", ""),
                        status=booking_flow_result.get("status", "booking_flow"),
                        reservation_log=booking_flow_result.get("log"),
                    )
                return booking_flow_result
            return None

        async def _run_price_chain():
            price_entry = await deps["try_handle_price_flow_entry_fn"](
                phone=phone,
                user_message=user_message,
                history=history,
                lang=lang,
                start_time=start_time,
                handle_price_flow_fn=deps["handle_price_flow_fn"],
                notify_admin_handoff_fn=deps["notify_admin_handoff_fn"],
                notify_admin_error_fn=deps["notify_admin_error_fn"],
                add_to_history_fn=deps["add_to_history_fn"],
                save_message_fn=deps["save_message_fn"],
                schedule_followup_fn=deps["schedule_followup_fn"],
                record_metric_fn=deps["record_metric_fn"],
                handle_booking_flow_fn=deps["handle_booking_flow_fn"],
                detect_language_fn=_locked_detect_language_fn,
                response_factory=resp,
            )
            if price_entry is not None:
                return price_entry

            price_flow_result = await deps["handle_price_flow_fn"](
                phone=phone,
                message=user_message,
                history=history,
                lang=lang,
            )
            if price_flow_result is not None:
                return price_flow_result
            return None

        if new_pipeline_enabled:
            active_flow = deps["get_active_flow_fn"](phone)
            fsm_decision = decide_execution_order(message=user_message, active_flow=active_flow)
            trace_event({"stage": "flow_fsm", "enabled": True, **fsm_decision})
            execution_order = fsm_decision.get("order") or ["booking", "price"]
        else:
            execution_order = ["booking", "price"]

        for chain in execution_order:
            if chain == "price":
                result = await _run_price_chain()
            else:
                result = await _run_booking_chain()
            if result is not None:
                return result

        elektra_entry = await deps["try_handle_elektra_price_entry_fn"](
            phone=phone,
            user_message=user_message,
            history=history,
            detect_price_request_fn=deps["detect_price_request_fn"],
            is_price_flow_active_fn=deps["is_price_flow_active_fn"],
            detect_language_fn=_locked_detect_language_fn,
            handle_elektra_price_request_fn=deps["handle_elektra_price_request_fn"],
            notify_admin_handoff_fn=deps["notify_admin_handoff_fn"],
            add_to_history_fn=deps["add_to_history_fn"],
            save_message_fn=deps["save_message_fn"],
            schedule_followup_fn=deps["schedule_followup_fn"],
            response_factory=resp,
            notify_admin_error_fn=deps["notify_admin_error_fn"],
            eleltra_config_error_cls=deps["elektra_config_error_cls"],
            natural_date_keywords=deps["price_natural_date_keywords"],
            price_inquiry_keywords=deps["price_inquiry_keywords"],
            guest_keywords=deps["price_guest_keywords"],
        )
        if elektra_entry is not None:
            return elektra_entry

        late_response = deps["try_handle_late_message_checks_fn"](
            phone=phone,
            user_message=user_message,
            history=history,
            start_time=start_time,
            is_conversation_ending_fn=deps["is_conversation_ending_fn"],
            get_closing_message_fn=deps["get_closing_message_fn"],
            parse_turkish_date_fn=deps["parse_turkish_date_fn"],
            is_hotel_open_fn=deps["is_hotel_open_fn"],
            format_date_turkish_fn=deps["format_date_turkish_fn"],
            get_welcome_message_fn=deps["get_welcome_message_fn"],
            is_greeting_fn=deps["is_greeting_fn"],
            is_menu_selection_fn=deps["is_menu_selection_fn"],
            get_menu_response_fn=deps["get_menu_response_fn"],
            add_to_history_fn=deps["add_to_history_fn"],
            save_message_fn=deps["save_message_fn"],
            schedule_followup_fn=deps["schedule_followup_fn"],
            record_metric_fn=deps["record_metric_fn"],
            detect_language_fn=_locked_detect_language_fn,
            response_factory=resp,
        )
        if late_response is not None:
            return late_response

        # STAGE 7: Deterministic local FAQ (canonical flow removed)
        local_faq_fn = deps.get("check_local_faq_fn")
        if callable(local_faq_fn):
            try:
                found, answer_tr, answer_en, _category, answer_ru = local_faq_fn(user_message)
            except Exception:
                found, answer_tr, answer_en, answer_ru = False, "", "", ""
            if found:
                if lang == "en":
                    local_reply = answer_en or answer_tr
                elif lang == "ru":
                    local_reply = answer_ru or answer_en or answer_tr
                else:
                    local_reply = answer_tr or answer_en
                if local_reply:
                    deps["add_to_history_fn"](phone, "user", user_message)
                    deps["add_to_history_fn"](phone, "assistant", local_reply)
                    deps["save_message_fn"](phone, user_message, local_reply)
                    deps["schedule_followup_fn"](phone)
                    deps["record_metric_fn"](
                        "local_faq",
                        response_time=time_module.time() - start_time,
                    )
                    return resp(reply=local_reply, status="local_faq")

        # STAGE 8: Postcheck (basit kural: dusuk confidence + negatif duygu -> handoff)
        if sf["sentiment"] == "neg" and sf["intensity"] >= 0.75 and sf["frustration_loop"]:
            try:
                await deps["notify_admin_handoff_fn"](
                    category="canli_destek",
                    priority="high",
                    customer_phone=phone,
                    customer_message=user_message,
                    source="chat_pipeline.postcheck",
                    detected_intent=primary_intent,
                    confidence=0.4,
                    conversation_summary="negative sentiment + frustration loop",
                    attempted_actions=["postcheck_sentiment_guard"],
                    suggested_reply="Musteriye insan destegi sunuldu.",
                    tags=["postcheck", "sentiment_guard"],
                    correlation_id=correlation_id,
                )
            except Exception:
                pass
            handoff_reply = "I am connecting you to our live support team."
            deps["add_to_history_fn"](phone, "user", user_message)
            deps["add_to_history_fn"](phone, "assistant", handoff_reply)
            deps["save_message_fn"](phone, user_message, handoff_reply)
            return resp(reply=handoff_reply, status="handoff", reason_code="postcheck_sentiment_guard")

        # STAGE 9: Auto reply via LLM fallback
        return await deps["handle_openai_fallback_fn"](
            client=deps["openai_client"],
            openai_model=deps["openai_model"],
            info_system_prompt=deps["info_system_prompt"],
            history=history,
            user_message=user_message,
            phone=phone,
            start_time=start_time,
            add_to_history_fn=deps["add_to_history_fn"],
            save_message_fn=deps["save_message_fn"],
            schedule_followup_fn=deps["schedule_followup_fn"],
            record_metric_fn=deps["record_metric_fn"],
            maybe_start_qa_background_fn=deps["maybe_start_qa_background_fn"],
            qa_enabled=deps["qa_enabled"],
            qa_agent=deps["qa_agent"],
            admin_phone=deps["admin_phone"],
            send_whatsapp_message_fn=deps["send_whatsapp_message_fn"],
            qa_fail_notifications=deps["qa_fail_notifications"],
            record_error_fn=deps["record_error_fn"],
            response_factory=resp,
            flow_context=flow_context,
            notify_admin_handoff_fn=deps.get("notify_admin_handoff_fn"),
            activate_human_takeover_fn=deps.get("activate_human_takeover_fn"),
            detected_intent=primary_intent,
            handoff_source="chat_pipeline.stage9_fallback",
        )

    return router
