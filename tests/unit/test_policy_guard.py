from app.services.policy_guard_service import evaluate_policy_guard, is_new_pipeline_enabled


def test_policy_guard_uses_runtime_cancellation_window(monkeypatch):
    monkeypatch.setattr(
        "app.services.policy_guard_service.build_cancellation_policy_reply",
        lambda lang: f"runtime-policy-{lang}-8days",
    )
    result = evaluate_policy_guard("Sezonda iptal kosullari nasil?", lang="tr")
    assert result["handled"] is True
    assert result["reply"] == "runtime-policy-tr-8days"


def test_policy_guard_handles_cancellation_policy_question_tr():
    result = evaluate_policy_guard("Sezonda iptal kosullari nasil?", lang="tr")
    assert result["handled"] is True
    assert result["status"] == "policy_guard_cancellation_policy"


def test_policy_guard_does_not_handle_direct_cancel_request():
    result = evaluate_policy_guard("Rezervasyonumu iptal etmek istiyorum", lang="tr")
    assert result["handled"] is False


def test_policy_guard_handles_cancellation_policy_question_en():
    result = evaluate_policy_guard(
        "Can you share refundable and non-refundable options with cancellation rules?",
        lang="en",
    )
    assert result["handled"] is True
    assert result["status"] == "policy_guard_cancellation_policy"


def test_policy_guard_handles_cancellation_policy_question_es():
    result = evaluate_policy_guard(
        "¿Puede indicar tarifas reembolsables y no reembolsables con reglas de cancelación?",
        lang="es",
    )
    assert result["handled"] is True
    assert result["status"] == "policy_guard_cancellation_policy"


def test_policy_guard_handles_cancellation_policy_question_ar():
    result = evaluate_policy_guard(
        "هل يمكن توضيح الأسعار القابلة للاسترداد وغير القابلة للاسترداد مع سياسة الإلغاء؟",
        lang="ar",
    )
    assert result["handled"] is True
    assert result["status"] == "policy_guard_cancellation_policy"


def test_policy_guard_handles_cancellation_policy_question_pt():
    result = evaluate_policy_guard(
        "Pode informar tarifas reembolsáveis e não reembolsáveis com regras de cancelamento?",
        lang="pt",
    )
    assert result["handled"] is True
    assert result["status"] == "policy_guard_cancellation_policy"


def test_policy_guard_does_not_handle_direct_cancel_request_en():
    result = evaluate_policy_guard("I want to cancel my reservation", lang="en")
    assert result["handled"] is False


def test_policy_guard_returns_cyrillic_for_russian_reply():
    result = evaluate_policy_guard("Какие условия отмены и возврата?", lang="ru")
    assert result["handled"] is True
    assert any("а" <= ch.lower() <= "я" or ch.lower() == "ё" for ch in result["reply"])


def test_policy_guard_does_not_short_circuit_mixed_intent_long_ru_message():
    msg = (
        "Здравствуйте! Есть ли свободные номера на 14-18 августа 2026 для 2 взрослых? "
        "Какие refundable и non-refundable тарифы, и можно ли заказать трансфер? "
        "Какая предоплата нужна для брони?"
    )
    result = evaluate_policy_guard(msg, lang="ru")
    assert result["handled"] is False


def test_policy_guard_does_not_short_circuit_mixed_intent_long_en_message():
    msg = (
        "Do you have availability for 14-18 August 2026 for 2 adults? "
        "Please share total room price, refundable and non-refundable options, "
        "late check-out fee and airport transfer cost."
    )
    result = evaluate_policy_guard(msg, lang="en")
    assert result["handled"] is False


def test_new_pipeline_flag_parser():
    assert is_new_pipeline_enabled("1") is True
    assert is_new_pipeline_enabled("true") is True
    assert is_new_pipeline_enabled("0") is False
    assert is_new_pipeline_enabled(None) is False
