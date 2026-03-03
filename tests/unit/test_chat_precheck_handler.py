from __future__ import annotations

import pytest

import app.handlers.chat_precheck_handler as precheck


async def _noop_async(*_args, **_kwargs):
    return None


def _noop_sync(*_args, **_kwargs):
    return None


def _response_factory(*, reply: str, status: str):
    return {"reply": reply, "status": status}


def _base_kwargs(user_message: str):
    return dict(
        phone="905500000000",
        user_message=user_message,
        detect_language_fn=lambda _m: "tr",
        load_conversation_fn=lambda _p: {"messages": []},
        notify_admin_error_fn=_noop_async,
        save_message_fn=_noop_sync,
        is_safe_mode_fn=lambda: False,
        is_auto_safe_mode_fn=lambda: False,
        check_rate_limit_fn=lambda _p: (True, "ok"),
        is_automation_enabled_fn=lambda: True,
        is_operational_rules_enabled_fn=lambda: True,
        is_blacklisted_fn=lambda _p: False,
        is_paused_fn=lambda _p: False,
        cancel_followup_fn=_noop_sync,
        get_conversation_history_fn=lambda _p: [],
        handle_cancel_flow_v2_fn=_noop_async,
        detect_suspicious_message_fn=lambda _m: (False, "", "low"),
        notify_admin_suspicious_fn=_noop_async,
        ai_question_response="",
        suspicious_response="",
        add_to_history_fn=_noop_sync,
        detect_critical_issue_fn=lambda _m: (False, "", 0, {}),
        send_critical_notification_fn=_noop_async,
        response_factory=_response_factory,
        notify_admin_handoff_fn=_noop_async,
        activate_human_takeover_fn=_noop_sync,
        flow_context=None,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_precheck_skips_operational_rule_for_price_availability_followup(monkeypatch):
    called = {"count": 0}

    def _op_rule(_msg, _history, **_kwargs):
        called["count"] += 1
        return {"reply": "should-not-trigger", "status": "operational_rezid_required"}

    monkeypatch.setattr(precheck, "evaluate_operational_reservation_rule", _op_rule)

    result = await precheck.run_chat_prechecks(
        **_base_kwargs("Aynı tarihlerde deniz manzaralı oda müsait mi, varsa fiyat farkı ne kadar?")
    )

    assert called["count"] == 0
    assert result["response"] is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_precheck_runs_operational_rule_for_explicit_reservation_operation(monkeypatch):
    called = {"count": 0}

    def _op_rule(_msg, _history, **_kwargs):
        called["count"] += 1
        return {"reply": "İptal akışı başladı", "status": "operational_cancel_collect_required"}

    monkeypatch.setattr(precheck, "evaluate_operational_reservation_rule", _op_rule)

    result = await precheck.run_chat_prechecks(
        **_base_kwargs("Rezervasyonumu iptal etmek istiyorum")
    )

    assert called["count"] == 1
    assert result["response"] is not None
    assert result["response"]["status"] == "operational_cancel_collect_required"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_precheck_notifies_admin_when_customer_confirms_payment():
    notified: list[dict] = []

    async def _notify_admin_handoff(**kwargs):
        notified.append(kwargs)
        return True

    kwargs = _base_kwargs("Ödemeyi yaptım, dekontu da gönderdim.")
    kwargs["notify_admin_handoff_fn"] = _notify_admin_handoff

    result = await precheck.run_chat_prechecks(**kwargs)

    assert result["response"] is None
    assert len(notified) == 1
    assert notified[0]["category"] == "odeme_bildirimi"
    assert notified[0]["detected_intent"] == "PAYMENT_CONFIRMED"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_precheck_does_not_notify_admin_for_payment_method_question():
    notified: list[dict] = []

    async def _notify_admin_handoff(**kwargs):
        notified.append(kwargs)
        return True

    kwargs = _base_kwargs("Ödeme linki nasıl gönderiliyor?")
    kwargs["notify_admin_handoff_fn"] = _notify_admin_handoff

    result = await precheck.run_chat_prechecks(**kwargs)

    assert result["response"] is None
    assert notified == []
