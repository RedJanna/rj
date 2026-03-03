from __future__ import annotations

from app.handlers.handoff_handler import detect_handoff_required


def test_special_request_late_checkin_and_birthday_triggers_handoff():
    msg = "Merhaba, gece 01:30 gibi giriş yapacağız ve eşim için doğum günü sürprizi istiyorum."
    needs_handoff, category, priority, *_ = detect_handoff_required(msg)
    assert needs_handoff is True
    assert category == "ozel_istek"
    assert priority == "medium"


def test_early_checkout_with_unused_nights_refund_triggers_handoff():
    msg = "Acil durum oldu, yarın erken çıkmamız gerekebilir. Kullanmadığımız geceler için iade alabilir miyiz?"
    needs_handoff, category, priority, *_ = detect_handoff_required(msg)
    assert needs_handoff is True
    assert category == "iptal_iade"
    assert priority == "high"


def test_cancellation_policy_information_question_does_not_trigger_handoff():
    msg = "İptal ve iade politikanız nedir, ücretsiz iptal son gün kaç gün önce?"
    needs_handoff, category, *_ = detect_handoff_required(msg)
    assert needs_handoff is False
    assert category == ""


def test_price_negotiation_question_is_not_forced_to_handoff():
    msg = "Fiyatlarınız çok pahalı geldi, indirim yapabilir misiniz?"
    needs_handoff, category, *_ = detect_handoff_required(msg)
    assert needs_handoff is False
    assert category == ""


def test_child_policy_discounted_rate_question_does_not_trigger_handoff():
    msg = "What's your child policy—does the child pay full price or a discounted rate?"
    needs_handoff, category, *_ = detect_handoff_required(msg)
    assert needs_handoff is False
    assert category == ""


def test_honeymoon_stay_pricing_question_does_not_force_special_request_handoff():
    msg = "Merhaba, Agustos ayında balayı için konaklama planlıyoruz, 3 gece fiyat alabilir miyim?"
    needs_handoff, category, *_ = detect_handoff_required(msg)
    assert needs_handoff is False
    assert category == ""


def test_room_surprise_request_without_stay_context_triggers_special_request_handoff():
    msg = "Odaya çiçek ve not ayarlamak istiyorum."
    needs_handoff, category, *_ = detect_handoff_required(msg)
    assert needs_handoff is True
    assert category == "ozel_istek"


def test_room_surprise_price_question_triggers_special_request_handoff():
    msg = "Odaya girişte küçük bir sürpriz (çiçek + not) ayarlayabilir misiniz, fiyatı ne olur?"
    needs_handoff, category, *_ = detect_handoff_required(msg)
    assert needs_handoff is True
    assert category == "ozel_istek"
