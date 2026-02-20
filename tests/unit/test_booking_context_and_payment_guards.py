from app.handlers.booking_flow_handler import (
    _extract_group_stage1_data,
    _extract_group_stage2_selections,
    _extract_booking_alias_index,
    _extract_context_id,
    _extract_multi_room_request,
    _is_generic_payment_method_question,
    _is_group_quote_request,
)


def test_extract_context_id():
    assert _extract_context_id("CTX-AB12CD34 için ödeme linki gönder") == "CTX-AB12CD34"
    assert _extract_context_id("reference ctx-abcd1234") == "CTX-ABCD1234"
    assert _extract_context_id("referans yok") == ""


def test_extract_booking_alias_index():
    assert _extract_booking_alias_index("A1 için ödeme") == 1
    assert _extract_booking_alias_index("#A2 link gönder") == 2
    assert _extract_booking_alias_index("A10") == 10
    assert _extract_booking_alias_index("rezervasyon") == 0


def test_generic_payment_method_question_guard():
    assert _is_generic_payment_method_question("Ödeme yöntemleriniz neler?")
    assert _is_generic_payment_method_question("payment methods?")
    assert not _is_generic_payment_method_question("A1 için ödeme linki gönder")


def test_extract_multi_room_request():
    parsed = _extract_multi_room_request("13 kişi için 3 adet oda rezerve etmek istiyorum")
    assert parsed["guest_count"] == 13
    assert parsed["room_count"] == 3


def test_extract_multi_room_request_with_family_count():
    parsed = _extract_multi_room_request("3 adet aile için fiyat almak istiyorum")
    assert parsed["family_count"] == 3
    assert parsed["room_count"] == 0


def test_group_quote_detects_family_price_message():
    assert _is_group_quote_request("3 adet aile için fiyat almak istiyorum")


def test_extract_group_stage1_data():
    msg = """GRUP FİYAT TALEP FORMU
- Giriş: 2026-08-10
- Çıkış: 2026-08-13
A1 | Yetişkin: 2 | Çocuk: 5, 8 | Oda adedi: 1
A2 | Yetişkin: 3 | Çocuk:  | Oda adedi: 2
"""
    data = _extract_group_stage1_data(msg)
    assert data["check_in"] == "2026-08-10"
    assert data["check_out"] == "2026-08-13"
    assert len(data["families"]) == 2
    assert data["families"][0]["alias"] == "A1"
    assert data["families"][0]["child_ages"] == [5, 8]


def test_extract_group_stage2_selections():
    msg = """ODA SEÇİM FORMU
A1 -> Seçim: Superior / Ücretsiz İptal
A2 -> Seçim: Deluxe / İade Yapılmaz
"""
    selections = _extract_group_stage2_selections(msg)
    assert selections["A1"].startswith("Superior")
    assert selections["A2"].startswith("Deluxe")
