from __future__ import annotations

import pytest

from app.handlers.late_message_checks_handler import try_handle_late_message_checks


@pytest.mark.parametrize(
    "message",
    [
        "ok thank you",
        "great thanks",
        "perfect thanks",
        "thanks a lot",
        "much appreciated",
        "teşekkürler",
        "tamam teşekkürler",
        "oldu teşekkürler",
    ],
)
def test_gratitude_after_price_context_does_not_send_hard_closing(message):
    saved = []
    history = [
        {"role": "assistant", "content": "Price is 308 EUR for 2 nights, breakfast included."},
    ]

    def response_factory(reply: str, status: str = "ok"):
        return {"reply": reply, "status": status}

    result = try_handle_late_message_checks(
        user_message=message,
        phone="905551234567",
        history=history,
        start_time=0.0,
        is_conversation_ending_fn=lambda _msg: True,
        get_closing_message_fn=lambda _lang: "You're welcome! Feel free to reach out anytime.",
        detect_language_fn=lambda _msg: "en",
        add_to_history_fn=lambda *_args, **_kwargs: None,
        save_message_fn=lambda phone, user_message, bot_reply: saved.append((phone, user_message, bot_reply)),
        parse_turkish_date_fn=lambda _msg: None,
        is_hotel_open_fn=lambda _date: True,
        format_date_turkish_fn=lambda _date: "",
        get_welcome_message_fn=lambda _lang: "",
        schedule_followup_fn=lambda _phone: None,
        record_metric_fn=lambda *_args, **_kwargs: None,
        is_greeting_fn=lambda _msg: (False, "en"),
        is_menu_selection_fn=lambda _msg: (False, 0),
        get_menu_response_fn=lambda _sel, _lang: "",
        response_factory=response_factory,
    )

    assert result["status"] == "ok"
    assert "proceed with the reservation" in result["reply"].lower()
    assert saved and "proceed with the reservation" in saved[-1][2].lower()


@pytest.mark.parametrize(
    "message",
    [
        "thanks, do you also have transfer from dalaman airport?",
        "ok teşekkürler, transfer ücreti nedir?",
        "great thanks also what time is check-in?",
    ],
)
def test_gratitude_plus_new_question_should_continue_normal_flow(message):
    saved = []
    history = [
        {"role": "assistant", "content": "Price is 308 EUR for 2 nights, breakfast included."},
    ]

    result = try_handle_late_message_checks(
        user_message=message,
        phone="905551234567",
        history=history,
        start_time=0.0,
        is_conversation_ending_fn=lambda _msg: True,
        get_closing_message_fn=lambda _lang: "You're welcome! Feel free to reach out anytime.",
        detect_language_fn=lambda _msg: "en",
        add_to_history_fn=lambda *_args, **_kwargs: None,
        save_message_fn=lambda phone, user_message, bot_reply: saved.append((phone, user_message, bot_reply)),
        parse_turkish_date_fn=lambda _msg: None,
        is_hotel_open_fn=lambda _date: True,
        format_date_turkish_fn=lambda _date: "",
        get_welcome_message_fn=lambda _lang: "",
        schedule_followup_fn=lambda _phone: None,
        record_metric_fn=lambda *_args, **_kwargs: None,
        is_greeting_fn=lambda _msg: (False, "en"),
        is_menu_selection_fn=lambda _msg: (False, 0),
        get_menu_response_fn=lambda _sel, _lang: "",
        response_factory=lambda reply, status="ok": {"reply": reply, "status": status},
    )

    # Kapanış tetiklenmemeli; akış normal pipeline'da devam etmeli.
    assert result is None
    assert saved == []


def test_first_message_forces_welcome_even_if_not_greeting():
    saved = []
    history = []

    result = try_handle_late_message_checks(
        user_message="Ağustos'ta 2 yetişkin için fiyat alabilir miyim?",
        phone="905551234568",
        history=history,
        start_time=0.0,
        is_conversation_ending_fn=lambda _msg: False,
        get_closing_message_fn=lambda _lang: "",
        detect_language_fn=lambda _msg: "tr",
        add_to_history_fn=lambda *_args, **_kwargs: None,
        save_message_fn=lambda phone, user_message, bot_reply: saved.append((phone, user_message, bot_reply)),
        parse_turkish_date_fn=lambda _msg: None,
        is_hotel_open_fn=lambda _date: True,
        format_date_turkish_fn=lambda _date: "",
        get_welcome_message_fn=lambda _lang: "Kassandra Ölüdeniz'e hoş geldiniz.",
        schedule_followup_fn=lambda _phone: None,
        record_metric_fn=lambda *_args, **_kwargs: None,
        is_greeting_fn=lambda _msg: (False, "tr"),
        is_menu_selection_fn=lambda _msg: (False, 0),
        get_menu_response_fn=lambda _sel, _lang: "",
        response_factory=lambda reply, status="ok": {"reply": reply, "status": status},
    )

    assert result is not None
    assert result["status"] == "first_message"
    assert "hoş geldiniz" in result["reply"].lower()
    assert saved and "hoş geldiniz" in saved[-1][2].lower()
