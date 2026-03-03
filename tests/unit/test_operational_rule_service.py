from __future__ import annotations

from app.services.operational_rule_service import evaluate_operational_reservation_rule


def _history_with_last_assistant(text: str):
    return [{"role": "assistant", "content": text}]


def test_rez_id_info_rule():
    result = evaluate_operational_reservation_rule("Rez ID nedir?", [])
    assert result is not None
    assert result["status"] == "operational_rez_id_info"
    assert "rezervasyon numarası" in result["reply"].lower()


def test_cancel_request_starts_slot_collection():
    result = evaluate_operational_reservation_rule("Rezervasyonumu iptal etmek istiyorum.", [])
    assert result is not None
    assert result["status"] == "operational_cancel_collect_required"
    assert "Rezervasyon / Voucher" in result["reply"]
    assert "1- İptal Edilemez" in result["reply"]
    assert "2- Ücretsiz İptal" in result["reply"]


def test_cancel_request_with_rezid_still_requires_rate_type():
    result = evaluate_operational_reservation_rule("Rez ID 12345, rezervasyonumu iptal etmek istiyorum.", [])
    assert result is not None
    assert result["status"] == "operational_cancel_collect_required"
    assert "1- İptal Edilemez" in result["reply"]
    assert "2- Ücretsiz İptal" in result["reply"]


def test_cancel_request_with_voucher_no_still_requires_rate_type():
    result = evaluate_operational_reservation_rule("Voucher No 81.943.761, rezervasyonumu iptal etmek istiyorum.", [])
    assert result is not None
    assert result["status"] == "operational_cancel_collect_required"


def test_cancel_price_type_only_returns_missing_slots():
    history = _history_with_last_assistant(
        "İptal işleminiz için size yardımcı olayım. Rezervasyon / Voucher Numaranızı paylaşır mısınız? (1- İptal Edilemez, 2- Ücretsiz İptal)"
    )
    result = evaluate_operational_reservation_rule("1", history)
    assert result is not None
    assert result["status"] == "operational_cancel_collect_missing"
    assert "Eksik" in result["reply"]


def test_cancel_handoff_requires_rezid_and_rate_type():
    history = _history_with_last_assistant(
        "İptal işleminiz için size yardımcı olayım. Rezervasyon / Voucher Numaranızı paylaşır mısınız? (1- İptal Edilemez, 2- Ücretsiz İptal)"
    )
    result = evaluate_operational_reservation_rule("Rez ID 913331, 1", history)
    assert result is not None
    assert result["status"] == "operational_cancel_handoff"
    assert result["notify_admin_handoff"] is True
    assert result["handoff_category"] == "iptal_iade"


def test_cancel_handoff_uses_previous_user_rezid_from_nonstandard_history():
    history = [
        {
            "timestamp": "2026-02-28T12:00:00",
            "user_message": "Rez ID 55555",
            "bot_reply": "İptal işleminiz için size yardımcı olayım. Rezervasyon / Voucher Numaranızı paylaşır mısınız? (1- İptal Edilemez, 2- Ücretsiz İptal)",
        }
    ]
    result = evaluate_operational_reservation_rule("2", history)
    assert result is not None
    assert result["status"] == "operational_cancel_handoff"
    assert result["notify_admin_handoff"] is True


def test_date_change_flow_rule():
    result = evaluate_operational_reservation_rule(
        "15 Temmuz rezervasyonumu 22 Temmuz tarihine almak istiyorum.",
        [],
    )
    assert result is not None
    assert result["status"] == "operational_rezid_required"
    assert "rezervasyon numarası" in result["reply"].lower()


def test_booking_confirmation_code_question_returns_direct_info():
    result = evaluate_operational_reservation_rule(
        "Rezervasyonu kesinleştirdikten sonra bana WhatsApp’tan teyit mesajı ve rezervasyon kodu paylaşır mısınız?",
        [],
    )
    assert result is not None
    assert result["status"] == "operational_booking_confirmation_info"
    assert result["reply"] == "Rezervasyon kesinleştikten sonra sizlere rezervasyon kodu ve teyit mesajı paylaşılacaktır."


def test_booking_confirmation_info_localized_en():
    result = evaluate_operational_reservation_rule(
        "After booking confirmation, can you send booking code and confirmation on WhatsApp?",
        [],
        lang="en",
    )
    assert result is not None
    assert result["status"] == "operational_booking_confirmation_info"
    assert "booking code" in result["reply"].lower()


def test_booking_confirmation_info_localized_ru():
    result = evaluate_operational_reservation_rule(
        "После подтверждения бронирования отправите код брони в WhatsApp?",
        [],
        lang="ru",
    )
    assert result is not None
    assert result["status"] == "operational_booking_confirmation_info"
    assert "бронир" in result["reply"].lower()


def test_rez_id_info_localized_en():
    result = evaluate_operational_reservation_rule("What is Rez ID?", [], lang="en")
    assert result is not None
    assert result["status"] == "operational_rez_id_info"
    assert "reservation number" in result["reply"].lower()


def test_date_change_flow_rule_with_rezid():
    result = evaluate_operational_reservation_rule(
        "Rez ID: 12590, 15 Temmuz rezervasyonumu 22 Temmuz tarihine almak istiyorum.",
        [],
    )
    assert result is not None
    assert result["status"] == "operational_date_change_flow"
    assert "aynı oda tipinin müsaitliğini" in result["reply"]
    assert "müsait tüm oda tiplerini" in result["reply"]


def test_multi_room_partial_cancel_rule():
    result = evaluate_operational_reservation_rule(
        "3 odam var, sadece 1 odayı iptal etmek istiyorum.",
        [],
    )
    assert result is not None
    assert result["status"] == "operational_rezid_required"
    assert "rezervasyon numarası" in result["reply"].lower()


def test_multi_room_partial_cancel_rule_with_rezid():
    result = evaluate_operational_reservation_rule(
        "Rez ID 55555, 3 odam var, sadece 1 odayı iptal etmek istiyorum.",
        [],
    )
    assert result is not None
    assert result["status"] == "operational_partial_cancel_identify_room"
    assert "kalan odalarınız aynı şekilde korunacaktır" in result["reply"]


def test_price_availability_question_does_not_trigger_rezid_rule():
    result = evaluate_operational_reservation_rule(
        "Aynı tarihlerde deniz manzaralı oda müsait mi, varsa fiyat farkı ne kadar?",
        [],
    )
    assert result is None


def test_price_availability_followup_with_nonstandard_history_still_skips_rezid_rule():
    history = [
        {
            "timestamp": "2026-02-27T11:11:06.707112",
            "user_message": "10–13 Ağustos (3 gece) için standart oda toplam fiyat kaç TL?",
            "bot_reply": "Memnuniyetle yardımcı olurum...",
        }
    ]
    result = evaluate_operational_reservation_rule(
        "Aynı tarihlerde deniz manzaralı oda müsait mi, varsa fiyat farkı ne kadar?",
        history,
    )
    assert result is None


def test_room_price_comparison_question_does_not_trigger_rezid_rule():
    result = evaluate_operational_reservation_rule(
        "Odalardan biri deniz manzaralı, diğeri standart olursa fiyat nasıl değişir?",
        [],
    )
    assert result is None
