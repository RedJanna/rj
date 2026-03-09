from __future__ import annotations

from app.services.intent_normalizer_service import (
    force_primary_intent_from_explicit_message,
    looks_like_explicit_booking_create_signal,
    looks_like_generic_price_or_availability_signal,
    looks_like_booking_payment_followup,
)


def test_force_primary_intent_prefers_price_query_for_explicit_price_text():
    intent = force_primary_intent_from_explicit_message(
        "fiyat bilgisi verir misiniz?",
        "PAYMENT_LINK_REQUEST",
        looks_like_price_slot_payload_fn=lambda _m: False,
    )
    assert intent == "PRICE_QUERY"


def test_force_primary_intent_uses_payment_link_when_explicit():
    intent = force_primary_intent_from_explicit_message(
        "payment link gönder",
        "PRICE_QUERY",
        looks_like_price_slot_payload_fn=lambda _m: False,
    )
    assert intent == "PAYMENT_LINK_REQUEST"


def test_force_primary_intent_prefers_booking_for_explicit_booking_create_text():
    intent = force_primary_intent_from_explicit_message(
        "Premium oda için rezervasyon oluşturur musunuz?",
        "PRICE_QUERY",
        looks_like_price_slot_payload_fn=lambda _m: False,
    )
    assert intent == "HOTEL_BOOKING_CREATE"


def test_force_primary_intent_prefers_restaurant_booking_when_context_is_restaurant():
    intent = force_primary_intent_from_explicit_message(
        "Akşam yemeği için rezervasyon yapmak istiyorum.",
        "HOTEL_BOOKING_CREATE",
        looks_like_price_slot_payload_fn=lambda _m: False,
    )
    assert intent == "RESTAURANT_BOOKING_CREATE"


def test_multilingual_price_signal_detects_arabic_price_query():
    assert looks_like_generic_price_or_availability_signal("يرجى مشاركة السعر الإجمالي من 14 إلى 18 أغسطس.") is True


def test_multilingual_price_signal_detects_chinese_total_price_query():
    assert looks_like_generic_price_or_availability_signal("请提供2026年8月14日至18日两位成人的总价。") is True


def test_generic_price_signal_ignores_restaurant_availability_question():
    assert looks_like_generic_price_or_availability_signal("Akşam yemeği için müsaitlik var mı?") is False


def test_explicit_booking_create_signal_handles_typo_variant():
    assert looks_like_explicit_booking_create_signal("Premium oda için rezervasyon oluşturur musunz ?") is True


def test_explicit_booking_create_signal_handles_confusable_letters():
    # First "o" in "olusturur" is Cyrillic small o.
    text = "Premium oda için rezervasyon оlusturur musunz ?"
    assert looks_like_explicit_booking_create_signal(text) is True


def test_booking_payment_followup_detects_turkish_deposit_question():
    assert looks_like_booking_payment_followup(
        "Rezervasyonu tutmak için kapora gerekiyorsa ne kadar ve ne zamana kadar yatırmalıyız?"
    ) is True


def test_booking_payment_followup_does_not_treat_menu_selection_as_payment():
    assert looks_like_booking_payment_followup("2") is False


def test_force_primary_intent_keeps_restaurant_when_dinner_availability_is_asked():
    intent = force_primary_intent_from_explicit_message(
        "Akşam yemeği için müsaitlik var mı?",
        "RESTAURANT_BOOKING_CREATE",
        looks_like_price_slot_payload_fn=lambda _m: False,
    )
    assert intent == "RESTAURANT_BOOKING_CREATE"


def test_force_primary_intent_routes_wifi_question_to_local_faq():
    intent = force_primary_intent_from_explicit_message(
        "WiFi var mı?",
        "PRICE_QUERY",
        looks_like_price_slot_payload_fn=lambda _m: False,
    )
    assert intent == "LOCAL_FAQ_INFO"


def test_force_primary_intent_routes_transfer_fee_question_to_transfer_info():
    intent = force_primary_intent_from_explicit_message(
        "Antalya transfer ücreti ne kadar?",
        "PRICE_QUERY",
        looks_like_price_slot_payload_fn=lambda _m: False,
    )
    assert intent == "TRANSFER_INFO"
