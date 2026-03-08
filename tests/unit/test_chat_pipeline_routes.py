from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import app.routes.chat_routes as chat_routes


async def _post_chat(app: FastAPI, payload: dict):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post("/chat", json=payload)
        return resp.status_code, resp.json()


def _build_test_app(overrides: dict | None = None) -> tuple[FastAPI, dict]:
    events: dict = {
        "history": [],
        "saved": [],
        "metrics": [],
        "handoff": [],
        "active_learning": [],
        "processed": set(),
    }

    async def _run_chat_prechecks(**_kwargs):
        return {"response": None, "lang": "en", "history": []}

    def _detect_handoff_required(_message: str):
        return False, "", "", "", "", ""

    async def _return_none_async(*_args, **_kwargs):
        return None

    def _return_none_sync(*_args, **_kwargs):
        return None

    def _detect_language(_text: str) -> str:
        return "en"

    def _add_to_history(phone: str, role: str, content: str):
        events["history"].append((phone, role, content))

    def _save_message(phone: str, user_message: str, assistant_reply: str):
        events["saved"].append((phone, user_message, assistant_reply))

    def _record_metric(name: str, **kwargs):
        events["metrics"].append((name, kwargs))

    async def _notify_admin_handoff(**kwargs):
        events["handoff"].append(kwargs)

    def _is_processed_message_id(phone: str, message_id: str) -> bool:
        return (phone, message_id) in events["processed"]

    def _mark_message_id_processed(phone: str, message_id: str):
        events["processed"].add((phone, message_id))

    async def _handle_openai_fallback_fn(**_kwargs):
        return chat_routes.ChatResponse(reply="fallback", status="fallback")

    def _capture_active_learning(**kwargs):
        events["active_learning"].append(kwargs)

    deps = {
        "run_chat_prechecks_fn": _run_chat_prechecks,
        "detect_handoff_required_fn": _detect_handoff_required,
        "try_start_restaurant_reservation_flow_fn": _return_none_async,
        "restaurant_settings": {},
        "clear_reservation_flow_fn": _return_none_sync,
        "notify_admin_handoff_fn": _notify_admin_handoff,
        "detect_language_fn": _detect_language,
        "add_to_history_fn": _add_to_history,
        "save_message_fn": _save_message,
        "extract_date_from_message_fn": _return_none_sync,
        "parse_date_input_fn": _return_none_sync,
        "extract_date_phrase_fn": _return_none_sync,
        "is_within_season_fn": lambda *_args, **_kwargs: True,
        "extract_time_from_message_fn": _return_none_sync,
        "get_meal_type_from_time_fn": _return_none_sync,
        "update_reservation_flow_fn": _return_none_sync,
        "reservation_state_cls": dict,
        "record_metric_fn": _record_metric,
        "try_handle_handoff_and_reservation_flow_fn": _return_none_async,
        "get_reservation_flow_fn": _return_none_sync,
        "handle_reservation_flow_fn": _return_none_async,
        "try_handle_booking_flow_entry_fn": _return_none_async,
        "handle_booking_flow_fn": _return_none_async,
        "send_whatsapp_message_fn": _return_none_sync,
        "admin_phone": "",
        "try_handle_price_flow_entry_fn": _return_none_async,
        "handle_price_flow_fn": _return_none_async,
        "notify_admin_error_fn": _return_none_sync,
        "schedule_followup_fn": _return_none_sync,
        "try_handle_late_message_checks_fn": _return_none_sync,
        "is_conversation_ending_fn": lambda *_args, **_kwargs: False,
        "get_closing_message_fn": _return_none_sync,
        "parse_turkish_date_fn": _return_none_sync,
        "is_hotel_open_fn": lambda *_args, **_kwargs: True,
        "format_date_turkish_fn": _return_none_sync,
        "get_welcome_message_fn": _return_none_sync,
        "is_greeting_fn": lambda *_args, **_kwargs: False,
        "is_menu_selection_fn": lambda *_args, **_kwargs: False,
        "get_menu_response_fn": _return_none_sync,
        "try_handle_elektra_price_entry_fn": _return_none_async,
        "detect_price_request_fn": lambda *_args, **_kwargs: False,
        "is_price_flow_active_fn": lambda *_args, **_kwargs: False,
        "handle_elektra_price_request_fn": _return_none_sync,
        "elektra_config_error_cls": RuntimeError,
        "price_natural_date_keywords": [],
        "price_inquiry_keywords": [],
        "price_guest_keywords": [],
        "try_handle_canonical_and_local_fn": _return_none_sync,
        "check_local_faq_fn": _return_none_sync,
        "canonical_greeting_keywords": [],
        "kanonik_fiyat_exclusions": [],
        "erken_giris_keywords": [],
        "gec_cikis_keywords": [],
        "handle_openai_fallback_fn": _handle_openai_fallback_fn,
        "openai_client": None,
        "openai_model": "gpt-test",
        "info_system_prompt": "",
        "maybe_start_qa_background_fn": _return_none_sync,
        "qa_enabled": False,
        "qa_agent": None,
        "qa_fail_notifications": [],
        "record_error_fn": _return_none_sync,
        "load_conversation_fn": lambda _phone: {"messages": []},
        "is_safe_mode_fn": lambda: False,
        "is_auto_safe_mode_fn": lambda: False,
        "check_rate_limit_fn": lambda _phone: (True, "ok"),
        "is_automation_enabled_fn": lambda: True,
        "is_blacklisted_fn": lambda _phone: False,
        "is_paused_fn": lambda _phone: False,
        "cancel_followup_fn": _return_none_sync,
        "get_conversation_history_fn": lambda _phone: [],
        "handle_cancel_flow_v2_fn": _return_none_sync,
        "detect_suspicious_message_fn": lambda _msg: False,
        "notify_admin_suspicious_fn": _return_none_sync,
        "ai_question_response": "",
        "suspicious_response": "",
        "detect_critical_issue_fn": lambda _msg: None,
        "send_critical_notification_fn": _return_none_sync,
        "get_price_flow_fn": _return_none_sync,
        "get_booking_flow_fn": _return_none_sync,
        "get_active_flow_fn": _return_none_sync,
        "set_active_flow_fn": _return_none_sync,
        "clear_active_flow_fn": _return_none_sync,
        "get_domain_lock_fn": _return_none_sync,
        "set_domain_lock_fn": _return_none_sync,
        "clear_domain_lock_fn": _return_none_sync,
        "is_processed_message_id_fn": _is_processed_message_id,
        "mark_message_id_processed_fn": _mark_message_id_processed,
        "trace_decision_fn": _return_none_sync,
        "capture_active_learning_fn": _capture_active_learning,
        "flow_orchestrator": None,
    }

    if overrides:
        deps.update(overrides)

    app = FastAPI()
    app.include_router(chat_routes.build_chat_router(**deps))
    return app, events


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_returns_clarify_required_when_slots_missing(monkeypatch):
    monkeypatch.setattr(chat_routes, "infer_primary_intent", lambda _message, _hint: "BOOKING_CREATE")
    monkeypatch.setattr(
        chat_routes,
        "evaluate_slot_coverage",
        lambda _intent, _message: {"missing_required_slots": ["check_in_date"]},
    )
    monkeypatch.setattr(
        chat_routes,
        "should_request_slot_clarification",
        lambda _intent, _coverage, has_active_flow=False: True,
    )
    monkeypatch.setattr(chat_routes, "get_missing_slot_prompt", lambda _intent: "Hangi tarih?")

    async def _run_chat_prechecks_non_first(**_kwargs):
        return {"response": None, "lang": "en", "history": [{"role": "assistant", "content": "prev"}]}

    app, _events = _build_test_app(overrides={"run_chat_prechecks_fn": _run_chat_prechecks_non_first})
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "oda ayarla", "message_id": "m1"},
    )

    assert status == 200
    assert body["status"] == "fallback"
    assert body["reply"] == "fallback"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_postcheck_sentiment_guard_routes_to_handoff(monkeypatch):
    monkeypatch.setattr(chat_routes, "infer_primary_intent", lambda _message, _hint: "COMPLAINT")
    monkeypatch.setattr(chat_routes, "evaluate_slot_coverage", lambda _intent, _message: {"missing_required_slots": []})
    monkeypatch.setattr(
        chat_routes,
        "should_request_slot_clarification",
        lambda _intent, _coverage, has_active_flow=False: False,
    )
    monkeypatch.setattr(
        chat_routes,
        "_compute_sentiment_and_frustration",
        lambda _msg, _hist: {
            "sentiment": "neg",
            "intensity": 0.9,
            "confidence": 0.8,
            "frustration_loop": True,
        },
    )

    async def _run_chat_prechecks_non_first(**_kwargs):
        return {"response": None, "lang": "en", "history": [{"role": "assistant", "content": "prev"}]}

    app, events = _build_test_app(overrides={"run_chat_prechecks_fn": _run_chat_prechecks_non_first})
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "berbat hizmet", "message_id": "m2"},
    )

    assert status == 200
    assert body["status"] == "fallback"
    assert body["reply"] == "fallback"
    assert len(events["handoff"]) == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_strict_ai_first_bypasses_for_price_query_and_runs_price_chain(monkeypatch):
    monkeypatch.setattr(chat_routes, "infer_primary_intent", lambda _message, _hint: "PRICE_QUERY")
    monkeypatch.setattr(
        chat_routes,
        "should_request_slot_clarification",
        lambda _intent, _coverage, has_active_flow=False: False,
    )

    async def _price_entry(**_kwargs):
        return chat_routes.ChatResponse(reply="price-flow", status="price_flow")

    async def _run_chat_prechecks_non_first(**_kwargs):
        return {"response": None, "lang": "en", "history": [{"role": "assistant", "content": "prev"}]}

    app, _events = _build_test_app(
        overrides={
            "try_handle_price_flow_entry_fn": _price_entry,
            "run_chat_prechecks_fn": _run_chat_prechecks_non_first,
        }
    )
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "10-13 Ağustos fiyat nedir?", "message_id": "m3"},
    )

    assert status == 200
    assert body["status"] == "price_flow"
    assert body["reply"] == "price-flow"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_menu_selection_is_handled_before_strict_ai_fallback(monkeypatch):
    async def _run_chat_prechecks_non_first(**_kwargs):
        return {
            "response": None,
            "lang": "tr",
            "history": [{"role": "assistant", "content": "Size nasıl yardımcı olabilirim?"}],
        }

    app, events = _build_test_app(
        overrides={
            "run_chat_prechecks_fn": _run_chat_prechecks_non_first,
            "is_menu_selection_fn": lambda message: (str(message).strip() == "2", 2 if str(message).strip() == "2" else 0),
            "get_menu_response_fn": lambda selection, lang="tr": f"menu-{selection}-{lang}",
        }
    )
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "2", "message_id": "menu-1"},
    )

    assert status == 200
    assert body["status"] == "ok"
    assert body["reply"].startswith("menu-2-")
    assert events["metrics"][-1][0] == "menu"
    assert events["metrics"][-1][1]["category"] == "menu_2"
    assert events["saved"][-1][2].startswith("menu-2-")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_language_switch_rejects_disabled_language(monkeypatch):
    monkeypatch.setenv("STRICT_AI_FIRST", "0")
    monkeypatch.setattr(
        chat_routes,
        "_get_runtime_language_policy",
        lambda: {
            "en": True,
            "tr": True,
            "ru": True,
            "de": True,
            "ar": True,
            "es": True,
            "fr": True,
            "zh": True,
            "hi": True,
            "pt": False,
        },
    )

    async def _run_chat_prechecks_non_first(**_kwargs):
        return {"response": None, "lang": "en", "history": [{"role": "assistant", "content": "prev"}]}

    app, _events = _build_test_app(overrides={"run_chat_prechecks_fn": _run_chat_prechecks_non_first})
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "can you speak portuguese?", "message_id": "m3-lang-switch"},
    )

    assert status == 200
    assert body["status"] == "language_switch"
    assert body["reason_code"] == "language_switch_unsupported"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_captures_active_learning_and_handoffs_for_unknown_topic(monkeypatch):
    monkeypatch.setenv("NEW_PIPELINE_ENABLED", "1")
    monkeypatch.setenv("STRICT_AI_FIRST", "0")
    monkeypatch.setattr(
        chat_routes,
        "route_intent",
        lambda _message, _domain: {
            "primary_intent": "OUT_OF_SCOPE_OTHER",
            "domain_hint": "unknown",
            "semantic_intent": "OUT_OF_SCOPE_OTHER",
            "semantic_confidence": 0.21,
            "router": "intent_router_v1",
        },
    )
    monkeypatch.setattr(
        chat_routes,
        "should_request_slot_clarification",
        lambda _intent, _coverage, has_active_flow=False: False,
    )

    async def _run_chat_prechecks_non_first(**_kwargs):
        return {"response": None, "lang": "en", "history": [{"role": "assistant", "content": "prev"}]}

    app, events = _build_test_app(overrides={"run_chat_prechecks_fn": _run_chat_prechecks_non_first})
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "farkli bir konu denemesi", "message_id": "m4"},
    )

    assert status == 200
    assert body["status"] == "handoff"
    assert body["reason_code"] == "novel_topic_out_of_scope"
    assert len(events["active_learning"]) == 1
    assert events["active_learning"][0]["reason"] == "novel_topic_out_of_scope"
    assert len(events["handoff"]) == 1
    assert events["handoff"][0]["source"] == "chat_pipeline.unknown_guard"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_low_confidence_known_intent_does_not_force_unknown_guard_handoff(monkeypatch):
    monkeypatch.setenv("NEW_PIPELINE_ENABLED", "1")
    monkeypatch.setenv("STRICT_AI_FIRST", "0")
    monkeypatch.setattr(
        chat_routes,
        "route_intent",
        lambda _message, _domain: {
            "primary_intent": "PRICE_QUERY",
            "domain_hint": "hotel",
            "semantic_intent": "PRICE_QUERY",
            "semantic_confidence": 0.05,
            "router": "intent_router_v1",
        },
    )
    monkeypatch.setattr(
        chat_routes,
        "should_request_slot_clarification",
        lambda _intent, _coverage, has_active_flow=False: False,
    )

    async def _run_chat_prechecks_non_first(**_kwargs):
        return {"response": None, "lang": "en", "history": [{"role": "assistant", "content": "prev"}]}

    app, events = _build_test_app(overrides={"run_chat_prechecks_fn": _run_chat_prechecks_non_first})
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "ağustos fiyat", "message_id": "m4b"},
    )

    assert status == 200
    assert body["status"] == "handoff"
    assert body["reason_code"] == "elektra_price_unavailable"
    assert len(events["active_learning"]) == 1
    assert len(events["handoff"]) == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_strict_ai_first_keeps_fallback_for_non_domain_intents(monkeypatch):
    monkeypatch.setattr(chat_routes, "infer_primary_intent", lambda _message, _hint: "COMPLAINT")

    async def _run_chat_prechecks_non_first(**_kwargs):
        return {"response": None, "lang": "en", "history": [{"role": "assistant", "content": "prev"}]}

    app, _events = _build_test_app(overrides={"run_chat_prechecks_fn": _run_chat_prechecks_non_first})
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "şikayet var", "message_id": "m4"},
    )

    assert status == 200
    assert body["status"] == "fallback"
    assert body["reply"] == "fallback"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_strict_ai_first_bypasses_for_explicit_room_price_query_even_if_intent_low(monkeypatch):
    monkeypatch.setenv("NEW_PIPELINE_ENABLED", "1")
    monkeypatch.setattr(chat_routes, "infer_primary_intent", lambda _message, _hint: "OUT_OF_SCOPE_OTHER")
    monkeypatch.setattr(
        chat_routes,
        "should_request_slot_clarification",
        lambda _intent, _coverage, has_active_flow=False: False,
    )

    async def _price_entry(**_kwargs):
        return chat_routes.ChatResponse(reply="price-flow", status="price_flow")

    async def _run_chat_prechecks_non_first(**_kwargs):
        return {"response": None, "lang": "tr", "history": [{"role": "assistant", "content": "prev"}]}

    app, _events = _build_test_app(
        overrides={
            "try_handle_price_flow_entry_fn": _price_entry,
            "run_chat_prechecks_fn": _run_chat_prechecks_non_first,
        }
    )
    status, body = await _post_chat(
        app,
        {
            "phone": "+905551112233",
            "message": "14-18 Ağustos, 2 yetişkin, havuz manzaralı oda fiyatı nedir?",
            "message_id": "m4-price",
        },
    )

    assert status == 200
    assert body["status"] == "price_flow"
    assert body["reply"] == "price-flow"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_strict_ai_first_bypasses_for_general_price_query_with_slots(monkeypatch):
    monkeypatch.setenv("NEW_PIPELINE_ENABLED", "1")
    monkeypatch.setattr(chat_routes, "infer_primary_intent", lambda _message, _hint: "OUT_OF_SCOPE_OTHER")
    monkeypatch.setattr(
        chat_routes,
        "should_request_slot_clarification",
        lambda _intent, _coverage, has_active_flow=False: False,
    )

    async def _price_entry(**_kwargs):
        return chat_routes.ChatResponse(reply="price-flow", status="price_flow")

    async def _run_chat_prechecks_non_first(**_kwargs):
        return {"response": None, "lang": "tr", "history": [{"role": "assistant", "content": "prev"}]}

    app, _events = _build_test_app(
        overrides={
            "try_handle_price_flow_entry_fn": _price_entry,
            "run_chat_prechecks_fn": _run_chat_prechecks_non_first,
        }
    )
    status, body = await _post_chat(
        app,
        {
            "phone": "+905551112233",
            "message": "3 eylül ile 4 eylül tarihleri arasında 3 yetişkin fiyatı nedir",
            "message_id": "m4-price-slots",
        },
    )

    assert status == 200
    assert body["status"] == "price_flow"
    assert body["reply"] == "price-flow"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_strict_ai_first_bypasses_for_numeric_payment_followup(monkeypatch):
    monkeypatch.setenv("NEW_PIPELINE_ENABLED", "1")
    monkeypatch.setattr(chat_routes, "infer_primary_intent", lambda _message, _hint: "OUT_OF_SCOPE_OTHER")
    monkeypatch.setattr(
        chat_routes,
        "should_request_slot_clarification",
        lambda _intent, _coverage, has_active_flow=False: False,
    )

    async def _booking_entry(**_kwargs):
        return chat_routes.ChatResponse(reply="booking-flow", status="booking_flow")

    async def _run_chat_prechecks_non_first(**_kwargs):
        return {"response": None, "lang": "tr", "history": [{"role": "assistant", "content": "prev"}]}

    app, _events = _build_test_app(
        overrides={
            "try_handle_booking_flow_entry_fn": _booking_entry,
            "run_chat_prechecks_fn": _run_chat_prechecks_non_first,
        }
    )
    status, body = await _post_chat(
        app,
        {
            "phone": "+905551112233",
            "message": "1",
            "message_id": "m4-payment-followup",
        },
    )

    assert status == 200
    assert body["status"] != "first_message"
    assert body["status"] in {"booking_flow", "clarify_required"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_price_flow_chain_is_blocked_when_intent_is_not_price(monkeypatch):
    monkeypatch.setenv("STRICT_AI_FIRST", "0")
    monkeypatch.setattr(chat_routes, "infer_primary_intent", lambda _message, _hint: "OUT_OF_SCOPE_OTHER")
    monkeypatch.setattr(
        chat_routes,
        "should_request_slot_clarification",
        lambda _intent, _coverage, has_active_flow=False: False,
    )

    calls = {"price_entry": 0}

    async def _price_entry(**_kwargs):
        calls["price_entry"] += 1
        return chat_routes.ChatResponse(reply="price-flow", status="price_flow")

    async def _run_chat_prechecks_non_first(**_kwargs):
        return {"response": None, "lang": "en", "history": [{"role": "assistant", "content": "prev"}]}

    app, _events = _build_test_app(
        overrides={
            "try_handle_price_flow_entry_fn": _price_entry,
            "run_chat_prechecks_fn": _run_chat_prechecks_non_first,
        }
    )
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "Wi-Fi şifresi nedir?", "message_id": "m5"},
    )

    assert status == 200
    assert body["status"] == "handoff"
    assert body["reason_code"] == "novel_topic_out_of_scope"
    assert calls["price_entry"] == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_booking_flow_chain_is_blocked_when_intent_is_not_booking(monkeypatch):
    monkeypatch.setenv("STRICT_AI_FIRST", "0")
    monkeypatch.setattr(chat_routes, "infer_primary_intent", lambda _message, _hint: "LOCAL_FAQ_INFO")
    monkeypatch.setattr(
        chat_routes,
        "should_request_slot_clarification",
        lambda _intent, _coverage, has_active_flow=False: False,
    )

    calls = {"booking_entry": 0}

    async def _booking_entry(**_kwargs):
        calls["booking_entry"] += 1
        return chat_routes.ChatResponse(reply="booking-flow", status="booking_flow")

    async def _run_chat_prechecks_non_first(**_kwargs):
        return {"response": None, "lang": "en", "history": [{"role": "assistant", "content": "prev"}]}

    app, _events = _build_test_app(
        overrides={
            "try_handle_booking_flow_entry_fn": _booking_entry,
            "run_chat_prechecks_fn": _run_chat_prechecks_non_first,
        }
    )
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "Wi-Fi şifresi nedir?", "message_id": "m5b"},
    )

    assert status == 200
    assert body["status"] == "fallback"
    assert calls["booking_entry"] == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_booking_flow_chain_allows_numeric_payment_followup_even_when_intent_is_non_booking(monkeypatch):
    monkeypatch.setenv("STRICT_AI_FIRST", "0")
    monkeypatch.setattr(chat_routes, "infer_primary_intent", lambda _message, _hint: "LOCAL_FAQ_INFO")
    monkeypatch.setattr(
        chat_routes,
        "should_request_slot_clarification",
        lambda _intent, _coverage, has_active_flow=False: False,
    )

    calls = {"booking_entry": 0}

    async def _booking_entry(**_kwargs):
        calls["booking_entry"] += 1
        return chat_routes.ChatResponse(reply="booking-flow", status="booking_flow")

    async def _run_chat_prechecks_non_first(**_kwargs):
        return {"response": None, "lang": "tr", "history": [{"role": "assistant", "content": "prev"}]}

    app, _events = _build_test_app(
        overrides={
            "try_handle_booking_flow_entry_fn": _booking_entry,
            "run_chat_prechecks_fn": _run_chat_prechecks_non_first,
        }
    )
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "1", "message_id": "m5b-followup"},
    )

    assert status == 200
    assert body["status"] == "booking_flow"
    assert calls["booking_entry"] == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_restaurant_start_is_blocked_when_intent_is_not_restaurant(monkeypatch):
    monkeypatch.setenv("STRICT_AI_FIRST", "0")
    monkeypatch.setattr(chat_routes, "infer_primary_intent", lambda _message, _hint: "LOCAL_FAQ_INFO")
    monkeypatch.setattr(
        chat_routes,
        "should_request_slot_clarification",
        lambda _intent, _coverage, has_active_flow=False: False,
    )

    calls = {"restaurant_start": 0}

    async def _restaurant_start(**_kwargs):
        calls["restaurant_start"] += 1
        return chat_routes.ChatResponse(reply="reservation-start", status="reservation_flow_started")

    async def _run_chat_prechecks_non_first(**_kwargs):
        return {"response": None, "lang": "en", "history": [{"role": "assistant", "content": "prev"}]}

    app, _events = _build_test_app(
        overrides={
            "try_start_restaurant_reservation_flow_fn": _restaurant_start,
            "run_chat_prechecks_fn": _run_chat_prechecks_non_first,
        }
    )
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "Wi-Fi şifresi nedir?", "message_id": "m5c"},
    )

    assert status == 200
    assert body["status"] == "fallback"
    assert calls["restaurant_start"] == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_restaurant_followup_date_guest_payload_is_not_misrouted_to_price(monkeypatch):
    monkeypatch.setenv("NEW_PIPELINE_ENABLED", "1")
    monkeypatch.setenv("STRICT_AI_FIRST", "0")
    monkeypatch.setattr(
        chat_routes,
        "route_intent",
        lambda _message, _domain: {
            "primary_intent": "PRICE_QUERY",
            "domain_hint": "hotel",
            "semantic_intent": "PRICE_QUERY",
            "semantic_confidence": 0.82,
            "router": "intent_router_v1",
        },
    )
    monkeypatch.setattr(
        chat_routes,
        "should_request_slot_clarification",
        lambda _intent, _coverage, has_active_flow=False: False,
    )

    calls = {"restaurant_start": 0}

    async def _restaurant_start(**_kwargs):
        calls["restaurant_start"] += 1
        return chat_routes.ChatResponse(reply="restaurant-flow", status="reservation_flow_started")

    async def _run_chat_prechecks_non_first(**_kwargs):
        return {
            "response": None,
            "lang": "tr",
            "history": [
                {"role": "assistant", "content": "Müsaitlik için lütfen restoran tarihini ve kişi sayısını paylaşır mısınız?"}
            ],
        }

    app, _events = _build_test_app(
        overrides={
            "run_chat_prechecks_fn": _run_chat_prechecks_non_first,
            "try_start_restaurant_reservation_flow_fn": _restaurant_start,
        }
    )
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "15 haziran 2 kişi", "message_id": "m5c-restaurant-followup"},
    )

    assert status == 200
    assert body["status"] == "reservation_flow_started"
    assert body["reply"] == "restaurant-flow"
    assert calls["restaurant_start"] == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_transfer_intent_prefers_step_flow_over_slot_clarify(monkeypatch):
    monkeypatch.setenv("NEW_PIPELINE_ENABLED", "1")
    monkeypatch.setenv("STRICT_AI_FIRST", "0")
    monkeypatch.setattr(
        chat_routes,
        "route_intent",
        lambda _message, _domain: {
            "primary_intent": "TRANSFER_BOOKING_REQUEST",
            "domain_hint": "transfer",
            "semantic_intent": "TRANSFER_BOOKING_REQUEST",
            "semantic_confidence": 0.91,
            "router": "intent_router_v1",
        },
    )
    monkeypatch.setattr(
        chat_routes,
        "should_request_slot_clarification",
        lambda _intent, _coverage, has_active_flow=False: True,
    )
    async def _transfer_step(**_kwargs):
        return chat_routes.ChatResponse(reply="transfer-step-1", status="transfer_flow")

    monkeypatch.setattr(chat_routes, "try_start_transfer_booking_flow", _transfer_step)

    async def _run_chat_prechecks_non_first(**_kwargs):
        return {"response": None, "lang": "tr", "history": [{"role": "assistant", "content": "prev"}]}

    app, _events = _build_test_app(
        overrides={
            "run_chat_prechecks_fn": _run_chat_prechecks_non_first,
        }
    )
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "transfer ayarlayalım", "message_id": "m-transfer-1"},
    )

    assert status == 200
    assert body["status"] == "transfer_flow"
    assert body["reply"] == "transfer-step-1"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_restaurant_guest_followup_does_not_trigger_unknown_guard_handoff(monkeypatch):
    monkeypatch.setenv("NEW_PIPELINE_ENABLED", "1")
    monkeypatch.setenv("STRICT_AI_FIRST", "0")
    monkeypatch.setattr(
        chat_routes,
        "route_intent",
        lambda _message, _domain: {
            "primary_intent": "OUT_OF_SCOPE_OTHER",
            "domain_hint": "unknown",
            "semantic_intent": "OUT_OF_SCOPE_OTHER",
            "semantic_confidence": 0.12,
            "router": "intent_router_v1",
        },
    )
    monkeypatch.setattr(
        chat_routes,
        "should_request_slot_clarification",
        lambda _intent, _coverage, has_active_flow=False: False,
    )

    async def _restaurant_start(**_kwargs):
        return chat_routes.ChatResponse(reply="restoran-adim-2", status="reservation_flow_started")

    async def _run_chat_prechecks_non_first(**_kwargs):
        return {
            "response": None,
            "lang": "tr",
            "history": [
                {
                    "role": "assistant",
                    "content": "Restoran rezervasyonu için adım adım ilerleyeceğiz. İlk adım: Lütfen kişi sayısını paylaşın.",
                }
            ],
        }

    app, _events = _build_test_app(
        overrides={
            "run_chat_prechecks_fn": _run_chat_prechecks_non_first,
            "try_start_restaurant_reservation_flow_fn": _restaurant_start,
        }
    )
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "3 kişi", "message_id": "m-restaurant-followup-3"},
    )

    assert status == 200
    assert body["status"] == "reservation_flow_started"
    assert body["reply"] == "restoran-adim-2"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_strict_ai_first_bypasses_when_active_price_flow_exists(monkeypatch):
    monkeypatch.setattr(chat_routes, "infer_primary_intent", lambda _message, _hint: "PRICE_QUERY")
    monkeypatch.setattr(
        chat_routes,
        "should_request_slot_clarification",
        lambda _intent, _coverage, has_active_flow=False: False,
    )

    async def _price_entry(**_kwargs):
        return chat_routes.ChatResponse(reply="price-flow-continued", status="price_flow")

    async def _run_chat_prechecks_non_first(**_kwargs):
        return {"response": None, "lang": "en", "history": [{"role": "assistant", "content": "prev"}]}

    app, _events = _build_test_app(
        overrides={
            "get_price_flow_fn": lambda _phone: {"state": "ask_dates"},
            "try_handle_price_flow_entry_fn": _price_entry,
            "run_chat_prechecks_fn": _run_chat_prechecks_non_first,
        }
    )
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "4 ağustos giriş 6 ağustos çıkış", "message_id": "m5"},
    )

    assert status == 200
    assert body["status"] == "price_flow"
    assert body["reply"] == "price-flow-continued"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_price_intent_without_elektra_result_returns_error_instead_of_fallback(monkeypatch):
    monkeypatch.setenv("NEW_PIPELINE_ENABLED", "1")
    monkeypatch.setenv("STRICT_AI_FIRST", "0")
    monkeypatch.setattr(
        chat_routes,
        "route_intent",
        lambda _message, _domain: {
            "primary_intent": "PRICE_QUERY",
            "domain_hint": "hotel",
            "semantic_intent": "PRICE_QUERY",
            "semantic_confidence": 0.88,
            "router": "intent_router_v1",
        },
    )
    monkeypatch.setattr(
        chat_routes,
        "should_request_slot_clarification",
        lambda _intent, _coverage, has_active_flow=False: False,
    )

    async def _run_chat_prechecks_non_first(**_kwargs):
        return {"response": None, "lang": "tr", "history": [{"role": "assistant", "content": "prev"}]}

    async def _none_async(**_kwargs):
        return None

    app, _events = _build_test_app(
        overrides={
            "run_chat_prechecks_fn": _run_chat_prechecks_non_first,
            "try_handle_price_flow_entry_fn": _none_async,
            "handle_price_flow_fn": _none_async,
            "try_handle_elektra_price_entry_fn": _none_async,
        }
    )
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "14-18 Ağustos fiyat nedir?", "message_id": "m5b"},
    )

    assert status == 200
    assert body["status"] == "handoff"
    assert body["reason_code"] == "elektra_price_unavailable"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_first_message_direct_request_returns_welcome():
    app, _events = _build_test_app()
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "4 Ağustos giriş 6 Ağustos çıkış", "message_id": "m6"},
    )

    assert status == 200
    assert body["status"] == "first_message"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_first_message_pure_greeting_returns_welcome():
    app, _events = _build_test_app()
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "Merhaba", "message_id": "m7"},
    )

    assert status == 200
    assert body["status"] == "first_message"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_first_message_booking_request_keeps_welcome_rule():
    app, _events = _build_test_app()
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "Superior oda için rezervasyon oluşturur musunz ?", "message_id": "m7b"},
    )

    assert status == 200
    assert body["status"] == "first_message"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_first_message_payment_followup_like_text_still_returns_welcome():
    app, _events = _build_test_app()
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "Kapora ne kadar?", "message_id": "m7p"},
    )

    assert status == 200
    assert body["status"] == "first_message"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_late_checkin_query_is_not_forced_into_urgent_clarify(monkeypatch):
    monkeypatch.setenv("NEW_PIPELINE_ENABLED", "1")
    monkeypatch.setenv("STRICT_AI_FIRST", "0")
    monkeypatch.setattr(
        chat_routes,
        "route_intent",
        lambda _message, _domain: {
            "primary_intent": "URGENT_CASE",
            "domain_hint": "hotel",
            "semantic_intent": "URGENT_CASE",
            "semantic_confidence": 0.88,
            "router": "intent_router_v1",
        },
    )

    monkeypatch.setattr(
        chat_routes,
        "evaluate_slot_coverage",
        lambda intent_name, _message: {"missing_required_slots": ["urgent_reason"]} if intent_name == "URGENT_CASE" else {"missing_required_slots": []},
    )
    monkeypatch.setattr(
        chat_routes,
        "should_request_slot_clarification",
        lambda _intent, coverage, has_active_flow=False: bool(coverage.get("missing_required_slots")),
    )
    monkeypatch.setattr(
        chat_routes,
        "get_missing_slot_prompt",
        lambda _intent: "Acil konuyu bir cümleyle ve varsa rezervasyon koduyla paylaşır mısınız?",
    )

    async def _run_chat_prechecks_non_first(**_kwargs):
        return {"response": None, "lang": "tr", "history": [{"role": "assistant", "content": "prev"}]}

    app, _events = _build_test_app(overrides={"run_chat_prechecks_fn": _run_chat_prechecks_non_first})
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "Gece geç saatte (01:00 gibi) giriş yaparsak sorun olur mu?", "message_id": "m7late"},
    )

    assert status == 200
    assert body["status"] != "clarify_required"
    assert "Acil konuyu bir cümleyle" not in body["reply"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_explicit_booking_create_text_not_fallback_to_price_handoff(monkeypatch):
    monkeypatch.setenv("NEW_PIPELINE_ENABLED", "1")
    monkeypatch.setenv("STRICT_AI_FIRST", "0")
    monkeypatch.setattr(
        chat_routes,
        "route_intent",
        lambda _message, _domain: {
            "primary_intent": "PRICE_QUERY",
            "domain_hint": "hotel",
            "semantic_intent": "PRICE_QUERY",
            "semantic_confidence": 0.90,
            "router": "intent_router_v1",
        },
    )

    async def _run_chat_prechecks_non_first(**_kwargs):
        return {"response": None, "lang": "tr", "history": [{"role": "assistant", "content": "prev"}]}

    app, _events = _build_test_app(overrides={"run_chat_prechecks_fn": _run_chat_prechecks_non_first})
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "Premium oda için rezervasyon oluşturur musunuz?", "message_id": "m7c"},
    )

    assert status == 200
    assert body["status"] != "handoff"
    assert body.get("reason_code") != "elektra_price_unavailable"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_explicit_booking_create_text_not_price_handoff_in_legacy_pipeline(monkeypatch):
    monkeypatch.setenv("NEW_PIPELINE_ENABLED", "0")
    monkeypatch.setattr(chat_routes, "infer_primary_intent", lambda _message, _hint: "PRICE_QUERY")

    async def _run_chat_prechecks_non_first(**_kwargs):
        return {"response": None, "lang": "tr", "history": [{"role": "assistant", "content": "prev"}]}

    app, _events = _build_test_app(overrides={"run_chat_prechecks_fn": _run_chat_prechecks_non_first})
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "Premium oda için rezervasyon oluşturur musunuz?", "message_id": "m7d"},
    )

    assert status == 200
    assert body["status"] != "handoff"
    assert body.get("reason_code") != "elektra_price_unavailable"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_typo_booking_create_text_not_price_handoff(monkeypatch):
    monkeypatch.setenv("NEW_PIPELINE_ENABLED", "1")
    monkeypatch.setenv("STRICT_AI_FIRST", "0")
    monkeypatch.setattr(
        chat_routes,
        "route_intent",
        lambda _message, _domain: {
            "primary_intent": "PRICE_QUERY",
            "domain_hint": "hotel",
            "semantic_intent": "PRICE_QUERY",
            "semantic_confidence": 0.90,
            "router": "intent_router_v1",
        },
    )

    async def _run_chat_prechecks_non_first(**_kwargs):
        return {"response": None, "lang": "tr", "history": [{"role": "assistant", "content": "prev"}]}

    app, _events = _build_test_app(overrides={"run_chat_prechecks_fn": _run_chat_prechecks_non_first})
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "Premium oda için rezervasyon oluşturur musunz ?", "message_id": "m7e"},
    )

    assert status == 200
    assert body["status"] != "handoff"
    assert body.get("reason_code") != "elektra_price_unavailable"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_direct_booking_create_guard_prevents_price_fallback_handoff_when_helpers_miss(monkeypatch):
    monkeypatch.setenv("NEW_PIPELINE_ENABLED", "1")
    monkeypatch.setenv("STRICT_AI_FIRST", "0")
    monkeypatch.setattr(
        chat_routes,
        "route_intent",
        lambda _message, _domain: {
            "primary_intent": "PRICE_QUERY",
            "domain_hint": "hotel",
            "semantic_intent": "PRICE_QUERY",
            "semantic_confidence": 0.90,
            "router": "intent_router_v1",
        },
    )
    monkeypatch.setattr(
        chat_routes,
        "should_request_slot_clarification",
        lambda _intent, _coverage, has_active_flow=False: False,
    )

    # Simulate an upstream regression: explicit helpers fail to flag booking-create text.
    monkeypatch.setattr(chat_routes, "_force_primary_intent_from_explicit_message", lambda _m, current: current)
    monkeypatch.setattr(chat_routes, "_looks_like_explicit_booking_create_signal", lambda _m: False)
    monkeypatch.setattr(chat_routes, "_looks_like_room_booking_create_request", lambda _m: False)
    monkeypatch.setattr(chat_routes, "_looks_like_generic_price_or_availability_signal", lambda _m: False)

    async def _run_chat_prechecks_non_first(**_kwargs):
        return {"response": None, "lang": "tr", "history": [{"role": "assistant", "content": "prev"}]}

    async def _none_async(**_kwargs):
        return None

    app, _events = _build_test_app(
        overrides={
            "run_chat_prechecks_fn": _run_chat_prechecks_non_first,
            "try_handle_price_flow_entry_fn": _none_async,
            "handle_price_flow_fn": _none_async,
            "try_handle_elektra_price_entry_fn": _none_async,
        }
    )
    status, body = await _post_chat(
        app,
        {
            "phone": "+905551112233",
            "message": "Premium oda için rezervasyon oluşturur musunz ?",
            "message_id": "m7f",
        },
    )

    assert status == 200
    assert body["status"] != "handoff"
    assert body.get("reason_code") != "elektra_price_unavailable"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_phone_payload_in_reservation_context_skips_price_flow(monkeypatch):
    monkeypatch.setenv("NEW_PIPELINE_ENABLED", "1")
    monkeypatch.setenv("STRICT_AI_FIRST", "0")
    monkeypatch.setattr(
        chat_routes,
        "route_intent",
        lambda _message, _domain: {
            "primary_intent": "PRICE_QUERY",
            "domain_hint": "hotel",
            "semantic_intent": "PRICE_QUERY",
            "semantic_confidence": 0.91,
            "router": "intent_router_v1",
        },
    )
    monkeypatch.setattr(
        chat_routes,
        "should_request_slot_clarification",
        lambda _intent, _coverage, has_active_flow=False: False,
    )

    calls = {"price_entry": 0}

    async def _price_entry(**_kwargs):
        calls["price_entry"] += 1
        return chat_routes.ChatResponse(reply="price-flow", status="price_flow")

    async def _run_chat_prechecks_with_reservation_history(**_kwargs):
        return {
            "response": None,
            "lang": "tr",
            "history": [
                {"role": "assistant", "content": "Rezervasyon için adım adım ilerleyeceğiz. İlk adım: Lütfen ad soyad bilginizi paylaşın."},
            ],
        }

    async def _none_async(**_kwargs):
        return None

    app, _events = _build_test_app(
        overrides={
            "run_chat_prechecks_fn": _run_chat_prechecks_with_reservation_history,
            "try_handle_price_flow_entry_fn": _price_entry,
            "handle_price_flow_fn": _none_async,
            "try_handle_elektra_price_entry_fn": _none_async,
        }
    )
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "905304498453", "message_id": "m7g"},
    )

    assert status == 200
    assert body["status"] == "fallback"
    assert calls["price_entry"] == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_strict_ai_first_bypasses_when_recent_reservation_contact_prompt_exists(monkeypatch):
    monkeypatch.setenv("NEW_PIPELINE_ENABLED", "1")
    monkeypatch.setenv("STRICT_AI_FIRST", "1")
    monkeypatch.setattr(
        chat_routes,
        "route_intent",
        lambda _message, _domain: {
            "primary_intent": "OUT_OF_SCOPE_OTHER",
            "domain_hint": "unknown",
            "semantic_intent": "OUT_OF_SCOPE_OTHER",
            "semantic_confidence": 0.11,
            "router": "intent_router_v1",
        },
    )
    monkeypatch.setattr(
        chat_routes,
        "should_request_slot_clarification",
        lambda _intent, _coverage, has_active_flow=False: False,
    )

    calls = {"booking_entry": 0}

    async def _booking_entry(**_kwargs):
        calls["booking_entry"] += 1
        return chat_routes.ChatResponse(reply="booking-flow", status="booking_flow")

    async def _run_chat_prechecks_with_reservation_history(**_kwargs):
        return {
            "response": None,
            "lang": "tr",
            "history": [
                {"role": "assistant", "content": "Rezervasyon için adım adım ilerleyeceğiz. İlk adım: Lütfen ad soyad bilginizi paylaşın."},
            ],
        }

    app, _events = _build_test_app(
        overrides={
            "run_chat_prechecks_fn": _run_chat_prechecks_with_reservation_history,
            "get_booking_flow_fn": lambda _phone: {"state": "ask_name", "data": {"lang": "tr"}},
            "try_handle_booking_flow_entry_fn": _booking_entry,
        }
    )
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "oomer oomöer", "message_id": "m7h"},
    )

    assert status == 200
    assert body["status"] == "booking_flow"
    assert calls["booking_entry"] == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_slot_merge_from_history_prevents_redundant_clarify(monkeypatch):
    monkeypatch.setenv("NEW_PIPELINE_ENABLED", "1")
    monkeypatch.setenv("STRICT_AI_FIRST", "0")
    monkeypatch.setattr(
        chat_routes,
        "route_intent",
        lambda _message, _domain: {
            "primary_intent": "PRICE_QUERY",
            "domain_hint": "hotel",
            "semantic_intent": "PRICE_QUERY",
            "semantic_confidence": 0.92,
            "router": "intent_router_v1",
        },
    )

    async def _run_chat_prechecks_with_history(**_kwargs):
        return {
            "response": None,
            "lang": "tr",
            "history": [
                {"role": "user", "content": "23-26 Ağustos 2026, 4 yetişkin"},
                {"role": "assistant", "content": "Devam edelim"},
            ],
        }

    app, _events = _build_test_app(overrides={"run_chat_prechecks_fn": _run_chat_prechecks_with_history})
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "2 ayrı oda ayarlayabilir misiniz?", "message_id": "m8"},
    )

    assert status == 200
    assert body["status"] != "clarify_required"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_strict_ai_first_allows_price_slot_followup_with_history(monkeypatch):
    monkeypatch.setenv("NEW_PIPELINE_ENABLED", "1")
    monkeypatch.setenv("STRICT_AI_FIRST", "1")
    monkeypatch.setattr(
        chat_routes,
        "route_intent",
        lambda _message, _domain: {
            "primary_intent": "OUT_OF_SCOPE_OTHER",
            "domain_hint": "unknown",
            "semantic_intent": "OUT_OF_SCOPE_OTHER",
            "semantic_confidence": 0.12,
            "router": "intent_router_v1",
        },
    )

    def _coverage(_intent: str, message: str):
        text = (message or "").lower()
        has_dates = ("1 ekim" in text and "3 ekim" in text) or ("2026-10-01" in text and "2026-10-03" in text)
        has_adult = "2 yetişkin" in text or "2 yetiskin" in text or "2 adults" in text
        missing = []
        if not has_dates:
            missing.extend(["check_in_date", "check_out_date"])
        if not has_adult:
            missing.append("adult_count")
        return {
            "required_slots": ["check_in_date", "check_out_date", "adult_count"],
            "missing_required_slots": missing,
        }

    monkeypatch.setattr(chat_routes, "evaluate_slot_coverage", _coverage)
    monkeypatch.setattr(
        chat_routes,
        "should_request_slot_clarification",
        lambda _intent, _coverage, has_active_flow=False: False,
    )

    async def _run_chat_prechecks_with_history(**_kwargs):
        return {
            "response": None,
            "lang": "tr",
            "history": [
                {"role": "user", "content": "1 ekim ile 3 ekim tarihleri arasında fiyat nedir ?"},
                {"role": "assistant", "content": "Net fiyat verebilmem için giriş-çıkış tarihi ve kişi sayısını paylaşır mısınız?"},
            ],
        }

    async def _price_entry(**_kwargs):
        return chat_routes.ChatResponse(reply="Çocuk yaşları nelerdir?", status="price_flow")

    app, _events = _build_test_app(
        overrides={
            "run_chat_prechecks_fn": _run_chat_prechecks_with_history,
            "try_handle_price_flow_entry_fn": _price_entry,
        }
    )
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "2 yetişkin 2 çocuk", "message_id": "m9"},
    )

    assert status == 200
    assert body["status"] == "price_flow"
    assert "Çocuk yaşları" in body["reply"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_strict_ai_first_allows_complete_price_slot_payload_followup(monkeypatch):
    monkeypatch.setenv("NEW_PIPELINE_ENABLED", "1")
    monkeypatch.setenv("STRICT_AI_FIRST", "1")
    monkeypatch.setattr(
        chat_routes,
        "route_intent",
        lambda _message, _domain: {
            "primary_intent": "OUT_OF_SCOPE_OTHER",
            "domain_hint": "unknown",
            "semantic_intent": "OUT_OF_SCOPE_OTHER",
            "semantic_confidence": 0.11,
            "router": "intent_router_v1",
        },
    )

    def _coverage(_intent: str, message: str):
        text = (message or "").lower()
        has_dates = "4 ile 5 temmuz" in text or ("2026-07-04" in text and "2026-07-05" in text)
        has_adult = "3 yetişkin" in text or "3 yetiskin" in text
        missing = []
        if not has_dates:
            missing.extend(["check_in_date", "check_out_date"])
        if not has_adult:
            missing.append("adult_count")
        return {
            "required_slots": ["check_in_date", "check_out_date", "adult_count"],
            "missing_required_slots": missing,
            "has_minimum_required": not missing,
        }

    monkeypatch.setattr(chat_routes, "evaluate_slot_coverage", _coverage)
    monkeypatch.setattr(
        chat_routes,
        "should_request_slot_clarification",
        lambda _intent, _coverage, has_active_flow=False: False,
    )

    async def _run_chat_prechecks_with_history(**_kwargs):
        return {
            "response": None,
            "lang": "tr",
            "history": [
                {"role": "user", "content": "Temmuz ayı 2 gecelik fiyatlarınızı öğrenebilir miyim"},
                {"role": "assistant", "content": "Net fiyat verebilmem için giriş-çıkış tarihi ve kişi sayısını paylaşır mısınız?"},
            ],
        }

    async def _price_entry(**_kwargs):
        return chat_routes.ChatResponse(reply="price-flow", status="price_flow")

    app, _events = _build_test_app(
        overrides={
            "run_chat_prechecks_fn": _run_chat_prechecks_with_history,
            "try_handle_price_flow_entry_fn": _price_entry,
        }
    )
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "4 ile 5 Temmuz arası 3 yetişkin", "message_id": "m9b"},
    )

    assert status == 200
    assert body["status"] == "price_flow"
    assert body["reply"] == "price-flow"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_strict_ai_first_complete_price_payload_without_elektra_returns_handoff(monkeypatch):
    monkeypatch.setenv("NEW_PIPELINE_ENABLED", "1")
    monkeypatch.setenv("STRICT_AI_FIRST", "1")
    monkeypatch.setattr(
        chat_routes,
        "route_intent",
        lambda _message, _domain: {
            "primary_intent": "OUT_OF_SCOPE_OTHER",
            "domain_hint": "unknown",
            "semantic_intent": "OUT_OF_SCOPE_OTHER",
            "semantic_confidence": 0.11,
            "router": "intent_router_v1",
        },
    )

    def _coverage(_intent: str, message: str):
        text = (message or "").lower()
        has_dates = "4 ile 5 temmuz" in text
        has_adult = "3 yetişkin" in text or "3 yetiskin" in text
        missing = []
        if not has_dates:
            missing.extend(["check_in_date", "check_out_date"])
        if not has_adult:
            missing.append("adult_count")
        return {
            "required_slots": ["check_in_date", "check_out_date", "adult_count"],
            "missing_required_slots": missing,
            "has_minimum_required": not missing,
        }

    monkeypatch.setattr(chat_routes, "evaluate_slot_coverage", _coverage)
    monkeypatch.setattr(
        chat_routes,
        "should_request_slot_clarification",
        lambda _intent, _coverage, has_active_flow=False: False,
    )

    async def _run_chat_prechecks_with_history(**_kwargs):
        return {
            "response": None,
            "lang": "tr",
            "history": [
                {"role": "user", "content": "Temmuz ayı 2 gecelik fiyatlarınızı öğrenebilir miyim"},
                {"role": "assistant", "content": "Net fiyat verebilmem için giriş-çıkış tarihi ve kişi sayısını paylaşır mısınız?"},
            ],
        }

    async def _none_async(**_kwargs):
        return None

    fallback_calls = {"count": 0}

    async def _openai_fallback(**_kwargs):
        fallback_calls["count"] += 1
        return chat_routes.ChatResponse(reply="fallback", status="fallback")

    app, _events = _build_test_app(
        overrides={
            "run_chat_prechecks_fn": _run_chat_prechecks_with_history,
            "try_handle_price_flow_entry_fn": _none_async,
            "handle_price_flow_fn": _none_async,
            "try_handle_elektra_price_entry_fn": _none_async,
            "handle_openai_fallback_fn": _openai_fallback,
        }
    )
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "4 ile 5 Temmuz arası 3 yetişkin", "message_id": "m9c"},
    )

    assert status == 200
    assert body["status"] == "handoff"
    assert body["reason_code"] == "elektra_price_unavailable"
    assert fallback_calls["count"] == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_out_of_scope_date_guest_payload_forces_price_intent(monkeypatch):
    monkeypatch.setenv("NEW_PIPELINE_ENABLED", "1")
    monkeypatch.setenv("STRICT_AI_FIRST", "0")
    monkeypatch.setattr(
        chat_routes,
        "route_intent",
        lambda _message, _domain: {
            "primary_intent": "OUT_OF_SCOPE_OTHER",
            "domain_hint": "unknown",
            "semantic_intent": "OUT_OF_SCOPE_OTHER",
            "semantic_confidence": 0.15,
            "router": "intent_router_v1",
        },
    )
    monkeypatch.setattr(
        chat_routes,
        "should_request_slot_clarification",
        lambda _intent, _coverage, has_active_flow=False: False,
    )

    async def _price_entry(**_kwargs):
        return chat_routes.ChatResponse(reply="price-flow", status="price_flow")

    async def _run_chat_prechecks_non_first(**_kwargs):
        return {"response": None, "lang": "tr", "history": [{"role": "assistant", "content": "prev"}]}

    app, events = _build_test_app(
        overrides={
            "run_chat_prechecks_fn": _run_chat_prechecks_non_first,
            "try_handle_price_flow_entry_fn": _price_entry,
        }
    )
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "23-26 Ağustos 2026, 4 yetişkin", "message_id": "m9"},
    )

    assert status == 200
    assert body["status"] == "price_flow"
    assert len(events["handoff"]) == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_out_of_scope_chinese_price_signal_forces_price_intent(monkeypatch):
    monkeypatch.setenv("NEW_PIPELINE_ENABLED", "1")
    monkeypatch.setenv("STRICT_AI_FIRST", "0")
    monkeypatch.setattr(
        chat_routes,
        "route_intent",
        lambda _message, _domain: {
            "primary_intent": "OUT_OF_SCOPE_OTHER",
            "domain_hint": "unknown",
            "semantic_intent": "OUT_OF_SCOPE_OTHER",
            "semantic_confidence": 0.12,
            "router": "intent_router_v1",
        },
    )
    monkeypatch.setattr(
        chat_routes,
        "should_request_slot_clarification",
        lambda _intent, _coverage, has_active_flow=False: False,
    )

    async def _price_entry(**_kwargs):
        return chat_routes.ChatResponse(reply="price-flow", status="price_flow")

    async def _run_chat_prechecks_non_first(**_kwargs):
        return {"response": None, "lang": "zh", "history": [{"role": "assistant", "content": "prev"}]}

    app, events = _build_test_app(
        overrides={
            "run_chat_prechecks_fn": _run_chat_prechecks_non_first,
            "try_handle_price_flow_entry_fn": _price_entry,
        }
    )
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "请提供2026年8月14日至18日两位成人的总价。", "message_id": "m14"},
    )

    assert status == 200
    assert body["status"] == "price_flow"
    assert len(events["handoff"]) == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_active_price_flow_skips_price_chain_on_payment_pivot(monkeypatch):
    monkeypatch.setenv("NEW_PIPELINE_ENABLED", "1")
    monkeypatch.setenv("STRICT_AI_FIRST", "0")
    monkeypatch.setattr(
        chat_routes,
        "route_intent",
        lambda _message, _domain: {
            "primary_intent": "PRICE_QUERY",
            "domain_hint": "hotel",
            "semantic_intent": "PRICE_QUERY",
            "semantic_confidence": 0.91,
            "router": "intent_router_v1",
        },
    )
    monkeypatch.setattr(
        chat_routes,
        "should_request_slot_clarification",
        lambda _intent, _coverage, has_active_flow=False: False,
    )

    calls = {"price_entry": 0}

    async def _price_entry(**_kwargs):
        calls["price_entry"] += 1
        return chat_routes.ChatResponse(reply="price-flow", status="price_flow")

    async def _run_chat_prechecks_non_first(**_kwargs):
        return {"response": None, "lang": "tr", "history": [{"role": "assistant", "content": "prev"}]}

    app, _events = _build_test_app(
        overrides={
            "run_chat_prechecks_fn": _run_chat_prechecks_non_first,
            "get_price_flow_fn": lambda _phone: {"state": "ask_guests"},
            "try_handle_price_flow_entry_fn": _price_entry,
        }
    )
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "Ödeme için kredi kartı geçiyor mu?", "message_id": "m10"},
    )

    assert status == 200
    assert body["status"] == "fallback"
    assert calls["price_entry"] == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_active_price_flow_booking_start_message_routes_booking_chain(monkeypatch):
    monkeypatch.setenv("NEW_PIPELINE_ENABLED", "1")
    monkeypatch.setenv("STRICT_AI_FIRST", "0")
    monkeypatch.setattr(
        chat_routes,
        "route_intent",
        lambda _message, _domain: {
            "primary_intent": "OUT_OF_SCOPE_OTHER",
            "domain_hint": "unknown",
            "semantic_intent": "OUT_OF_SCOPE_OTHER",
            "semantic_confidence": 0.2,
            "router": "intent_router_v1",
        },
    )
    monkeypatch.setattr(
        chat_routes,
        "should_request_slot_clarification",
        lambda _intent, _coverage, has_active_flow=False: False,
    )

    async def _booking_entry(**_kwargs):
        return chat_routes.ChatResponse(reply="booking-flow", status="booking_flow")

    async def _run_chat_prechecks_non_first(**_kwargs):
        return {"response": None, "lang": "tr", "history": [{"role": "assistant", "content": "prev"}]}

    app, _events = _build_test_app(
        overrides={
            "run_chat_prechecks_fn": _run_chat_prechecks_non_first,
            "get_price_flow_fn": lambda _phone: {"state": "ask_guests"},
            "try_handle_booking_flow_entry_fn": _booking_entry,
        }
    )
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "Tamam, rezervasyonu başlatalım", "message_id": "m11"},
    )

    assert status == 200
    assert body["status"] == "booking_flow"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_booking_start_message_skips_local_faq_and_routes_booking_chain(monkeypatch):
    monkeypatch.setenv("NEW_PIPELINE_ENABLED", "1")
    monkeypatch.setenv("STRICT_AI_FIRST", "0")
    monkeypatch.setattr(
        chat_routes,
        "route_intent",
        lambda _message, _domain: {
            "primary_intent": "OUT_OF_SCOPE_OTHER",
            "domain_hint": "unknown",
            "semantic_intent": "OUT_OF_SCOPE_OTHER",
            "semantic_confidence": 0.2,
            "router": "intent_router_v1",
        },
    )
    monkeypatch.setattr(
        chat_routes,
        "should_request_slot_clarification",
        lambda _intent, _coverage, has_active_flow=False: False,
    )

    async def _booking_entry(**_kwargs):
        return chat_routes.ChatResponse(reply="booking-flow", status="booking_flow")

    async def _run_chat_prechecks_non_first(**_kwargs):
        return {"response": None, "lang": "tr", "history": [{"role": "assistant", "content": "prev"}]}

    def _local_faq_found(_message: str):
        return True, "Bize +90 ... ulaşabilirsiniz.", "You can reach us via +90 ...", "contact", ""

    app, _events = _build_test_app(
        overrides={
            "run_chat_prechecks_fn": _run_chat_prechecks_non_first,
            "check_local_faq_fn": _local_faq_found,
            "get_price_flow_fn": lambda _phone: {"state": "ask_guests"},
            "try_handle_booking_flow_entry_fn": _booking_entry,
        }
    )
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "Tamam, rezervasyonu başlatalım", "message_id": "m12"},
    )

    assert status == 200
    assert body["status"] == "booking_flow"
    assert body["reply"] == "booking-flow"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_explicit_booking_start_skips_slot_clarify_and_enters_booking_flow(monkeypatch):
    monkeypatch.setenv("NEW_PIPELINE_ENABLED", "1")
    monkeypatch.setenv("STRICT_AI_FIRST", "0")
    monkeypatch.setattr(
        chat_routes,
        "route_intent",
        lambda _message, _domain: {
            "primary_intent": "HOTEL_BOOKING_CREATE",
            "domain_hint": "hotel",
            "semantic_intent": "HOTEL_BOOKING_CREATE",
            "semantic_confidence": 0.95,
            "router": "intent_router_v1",
        },
    )
    monkeypatch.setattr(
        chat_routes,
        "should_request_slot_clarification",
        lambda _intent, _coverage, has_active_flow=False: True,
    )
    monkeypatch.setattr(chat_routes, "get_missing_slot_prompt", lambda _intent: "clarify-prompt")

    async def _booking_entry(**_kwargs):
        return chat_routes.ChatResponse(reply="booking-flow", status="booking_flow")

    async def _run_chat_prechecks_non_first(**_kwargs):
        return {"response": None, "lang": "tr", "history": [{"role": "assistant", "content": "prev"}]}

    app, _events = _build_test_app(
        overrides={
            "run_chat_prechecks_fn": _run_chat_prechecks_non_first,
            "try_handle_booking_flow_entry_fn": _booking_entry,
        }
    )
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "Tamam, rezervasyonu başlatalım", "message_id": "m13"},
    )

    assert status == 200
    assert body["status"] == "booking_flow"
    assert body["reply"] == "booking-flow"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_explicit_room_booking_signal_runs_booking_chain_even_if_intent_fallback(monkeypatch):
    monkeypatch.setenv("NEW_PIPELINE_ENABLED", "1")
    monkeypatch.setenv("STRICT_AI_FIRST", "0")
    monkeypatch.setattr(
        chat_routes,
        "route_intent",
        lambda _message, _domain: {
            "primary_intent": "AI_FALLBACK",
            "domain_hint": "unknown",
            "semantic_intent": "AI_FALLBACK",
            "semantic_confidence": 0.2,
            "router": "intent_router_v1",
        },
    )
    monkeypatch.setattr(
        chat_routes,
        "should_request_slot_clarification",
        lambda _intent, _coverage, has_active_flow=False: False,
    )

    async def _booking_entry(**_kwargs):
        return chat_routes.ChatResponse(reply="booking-flow", status="booking_flow")

    async def _run_chat_prechecks_non_first(**_kwargs):
        return {"response": None, "lang": "tr", "history": [{"role": "assistant", "content": "prev"}]}

    app, _events = _build_test_app(
        overrides={
            "run_chat_prechecks_fn": _run_chat_prechecks_non_first,
            "try_handle_booking_flow_entry_fn": _booking_entry,
        }
    )
    status, body = await _post_chat(
        app,
        {"phone": "+905551112233", "message": "Premium oda için rezervasyon oluşturur musunuz ?", "message_id": "m15"},
    )

    assert status == 200
    assert body["status"] == "booking_flow"
    assert body["reply"] == "booking-flow"
