import pytest

from app.handlers.elektra_price_entry_handler import try_handle_elektra_price_entry


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_detail_message_skips_elektra_price_entry():
    called = {"handle_elektra": False}

    async def _handle_elektra_price_request_fn(*args, **kwargs):
        called["handle_elektra"] = True
        return "ignored", "ignored", None

    result = await try_handle_elektra_price_entry(
        phone="905551110000",
        user_message="2 kişi, 1 bagaj ve 1 adet bebek koltuğu",
        history=[],
        detect_price_request_fn=lambda *_: True,
        is_price_flow_active_fn=lambda *_: False,
        detect_language_fn=lambda *_: "tr",
        handle_elektra_price_request_fn=_handle_elektra_price_request_fn,
        notify_admin_handoff_fn=lambda *_, **__: None,
        add_to_history_fn=lambda *_, **__: None,
        save_message_fn=lambda *_, **__: None,
        schedule_followup_fn=lambda *_, **__: None,
        response_factory=lambda **kwargs: kwargs,
        notify_admin_error_fn=lambda *_, **__: None,
        eleltra_config_error_cls=RuntimeError,
        natural_date_keywords=["haziran", "temmuz"],
        price_inquiry_keywords=["fiyat", "ücret", "price", "how much"],
        guest_keywords=["kişi", "kisilik", "guest", "adult"],
    )

    assert result is None
    assert called["handle_elektra"] is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_breakfast_policy_question_skips_elektra_price_entry():
    called = {"handle_elektra": False}

    async def _handle_elektra_price_request_fn(*args, **kwargs):
        called["handle_elektra"] = True
        return "ignored", "ignored", None

    result = await try_handle_elektra_price_entry(
        phone="905551110000",
        user_message="Bu fiyata kahvaltı dahil mi, değilse kişi başı ek ücret nedir?",
        history=[],
        detect_price_request_fn=lambda *_: True,
        is_price_flow_active_fn=lambda *_: False,
        detect_language_fn=lambda *_: "tr",
        handle_elektra_price_request_fn=_handle_elektra_price_request_fn,
        notify_admin_handoff_fn=lambda *_, **__: None,
        add_to_history_fn=lambda *_, **__: None,
        save_message_fn=lambda *_, **__: None,
        schedule_followup_fn=lambda *_, **__: None,
        response_factory=lambda **kwargs: kwargs,
        notify_admin_error_fn=lambda *_, **__: None,
        eleltra_config_error_cls=RuntimeError,
        natural_date_keywords=["haziran", "temmuz", "agustos", "ağustos"],
        price_inquiry_keywords=["fiyat", "ücret", "price", "how much"],
        guest_keywords=["kişi", "kisilik", "guest", "adult"],
    )

    assert result is None
    assert called["handle_elektra"] is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_child_policy_question_skips_elektra_price_entry():
    called = {"handle_elektra": False}

    async def _handle_elektra_price_request_fn(*args, **kwargs):
        called["handle_elektra"] = True
        return "ignored", "ignored", None

    result = await try_handle_elektra_price_entry(
        phone="905551110001",
        user_message="What's your child policy—does the child pay full price or a discounted rate?",
        history=[],
        detect_price_request_fn=lambda *_: True,
        is_price_flow_active_fn=lambda *_: False,
        detect_language_fn=lambda *_: "en",
        handle_elektra_price_request_fn=_handle_elektra_price_request_fn,
        notify_admin_handoff_fn=lambda *_, **__: None,
        add_to_history_fn=lambda *_, **__: None,
        save_message_fn=lambda *_, **__: None,
        schedule_followup_fn=lambda *_, **__: None,
        response_factory=lambda **kwargs: kwargs,
        notify_admin_error_fn=lambda *_, **__: None,
        eleltra_config_error_cls=RuntimeError,
        natural_date_keywords=["july", "august"],
        price_inquiry_keywords=["fiyat", "ücret", "price", "how much"],
        guest_keywords=["kişi", "kisilik", "guest", "adult"],
    )

    assert result is None
    assert called["handle_elektra"] is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_extra_bed_fee_question_skips_elektra_price_entry():
    called = {"handle_elektra": False}

    async def _handle_elektra_price_request_fn(*args, **kwargs):
        called["handle_elektra"] = True
        return "ignored", "ignored", None

    result = await try_handle_elektra_price_entry(
        phone="905551110002",
        user_message="Can you add an extra bed, and what is the nightly fee?",
        history=[],
        detect_price_request_fn=lambda *_: True,
        is_price_flow_active_fn=lambda *_: False,
        detect_language_fn=lambda *_: "en",
        handle_elektra_price_request_fn=_handle_elektra_price_request_fn,
        notify_admin_handoff_fn=lambda *_, **__: None,
        add_to_history_fn=lambda *_, **__: None,
        save_message_fn=lambda *_, **__: None,
        schedule_followup_fn=lambda *_, **__: None,
        response_factory=lambda **kwargs: kwargs,
        notify_admin_error_fn=lambda *_, **__: None,
        eleltra_config_error_cls=RuntimeError,
        natural_date_keywords=["july", "august"],
        price_inquiry_keywords=["fiyat", "ücret", "price", "how much"],
        guest_keywords=["kişi", "kisilik", "guest", "adult"],
    )

    assert result is None
    assert called["handle_elektra"] is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_room_suitability_query_does_not_reuse_history_date():
    captured = {"message": ""}

    async def _handle_elektra_price_request_fn(message, hotel_id, lang):
        captured["message"] = message
        return "Missing: date range", "ok", None

    user_message = "Do you have a room suitable for 2 adults + 1 child (7 years old)?"
    history = [{"content": "23-26 August for 4 adults"}]

    result = await try_handle_elektra_price_entry(
        phone="905551110003",
        user_message=user_message,
        history=history,
        detect_price_request_fn=lambda *_: True,
        is_price_flow_active_fn=lambda *_: False,
        detect_language_fn=lambda *_: "en",
        handle_elektra_price_request_fn=_handle_elektra_price_request_fn,
        notify_admin_handoff_fn=lambda *_, **__: None,
        add_to_history_fn=lambda *_, **__: None,
        save_message_fn=lambda *_, **__: None,
        schedule_followup_fn=lambda *_, **__: None,
        response_factory=lambda **kwargs: kwargs,
        notify_admin_error_fn=lambda *_, **__: None,
        eleltra_config_error_cls=RuntimeError,
        natural_date_keywords=["august"],
        price_inquiry_keywords=["price", "how much"],
        guest_keywords=["guest", "adult", "child"],
    )

    assert result is not None
    assert captured["message"] == user_message
    assert "date range" in (result.get("reply") or "").lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_price_entry_returns_price_result_status_when_offer_exists():
    async def _handle_elektra_price_request_fn(*_args, **_kwargs):
        return "price-reply", "ok", [{"room-type": "DELUXE ROOM"}]

    result = await try_handle_elektra_price_entry(
        phone="905551110005",
        user_message="14-18 August for 2 adults, total price?",
        history=[],
        detect_price_request_fn=lambda *_: True,
        is_price_flow_active_fn=lambda *_: False,
        detect_language_fn=lambda *_: "en",
        handle_elektra_price_request_fn=_handle_elektra_price_request_fn,
        notify_admin_handoff_fn=lambda *_, **__: None,
        add_to_history_fn=lambda *_, **__: None,
        save_message_fn=lambda *_, **__: None,
        schedule_followup_fn=lambda *_, **__: None,
        response_factory=lambda **kwargs: kwargs,
        notify_admin_error_fn=lambda *_, **__: None,
        eleltra_config_error_cls=RuntimeError,
        natural_date_keywords=["august"],
        price_inquiry_keywords=["price"],
        guest_keywords=["guest", "adult", "child"],
    )

    assert result is not None
    assert result["status"] == "price_result"
    assert result["is_price_template"] is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_price_entry_ignores_assistant_history_when_backfilling_guest_info():
    captured = {"message": ""}

    async def _handle_elektra_price_request_fn(message, hotel_id, lang):
        captured["message"] = message
        return "Missing: guest count", "ok", None

    user_message = "14 August price?"
    history = [
        {"role": "assistant", "content": "For 2 adults our available rooms are listed below."},
    ]

    result = await try_handle_elektra_price_entry(
        phone="905551110004",
        user_message=user_message,
        history=history,
        detect_price_request_fn=lambda *_: True,
        is_price_flow_active_fn=lambda *_: False,
        detect_language_fn=lambda *_: "en",
        handle_elektra_price_request_fn=_handle_elektra_price_request_fn,
        notify_admin_handoff_fn=lambda *_, **__: None,
        add_to_history_fn=lambda *_, **__: None,
        save_message_fn=lambda *_, **__: None,
        schedule_followup_fn=lambda *_, **__: None,
        response_factory=lambda **kwargs: kwargs,
        notify_admin_error_fn=lambda *_, **__: None,
        eleltra_config_error_cls=RuntimeError,
        natural_date_keywords=["august"],
        price_inquiry_keywords=["price"],
        guest_keywords=["guest", "adult", "child"],
    )

    assert result is not None
    assert captured["message"] == user_message


@pytest.mark.unit
@pytest.mark.asyncio
async def test_price_entry_prefers_locked_language_over_detector_for_template_language():
    captured = {"lang": ""}

    async def _handle_elektra_price_request_fn(message, hotel_id, lang):
        captured["lang"] = lang
        return "ok", "ok", [{"room-type": "DELUXE ROOM"}]

    result = await try_handle_elektra_price_entry(
        phone="905551110006",
        user_message="11-14 octubre, 2 adultos precio",
        history=[],
        locked_lang="es",
        detect_price_request_fn=lambda *_: True,
        is_price_flow_active_fn=lambda *_: False,
        detect_language_fn=lambda *_: "en",
        handle_elektra_price_request_fn=_handle_elektra_price_request_fn,
        notify_admin_handoff_fn=lambda *_, **__: None,
        add_to_history_fn=lambda *_, **__: None,
        save_message_fn=lambda *_, **__: None,
        schedule_followup_fn=lambda *_, **__: None,
        response_factory=lambda **kwargs: kwargs,
        notify_admin_error_fn=lambda *_, **__: None,
        eleltra_config_error_cls=RuntimeError,
        natural_date_keywords=["octubre"],
        price_inquiry_keywords=["precio"],
        guest_keywords=["adulto", "adultos"],
    )

    assert result is not None
    assert captured["lang"] == "es"
