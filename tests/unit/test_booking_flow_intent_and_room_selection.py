import pytest

from app.handlers import booking_flow_handler as h
from app.handlers.booking_flow_handler import detect_booking_intent, _parse_room_selection


@pytest.mark.unit
def test_detect_booking_intent_with_turkish_chars():
    assert detect_booking_intent("exclusive pool oda için rezervasyon oluştur")


@pytest.mark.unit
def test_detect_booking_intent_does_not_trigger_for_price_information_question():
    assert not detect_booking_intent("Bu fiyata kahvaltı dahil mi, değilse kişi başı ek ücret nedir?")


@pytest.mark.unit
def test_detect_booking_intent_does_not_trigger_for_restaurant_reservation_sentence():
    assert not detect_booking_intent("Akşam yemeği için rezervasyon yapmak istiyorum.")


@pytest.mark.unit
def test_detect_booking_intent_with_start_booking_phrase():
    assert detect_booking_intent(
        "Tamam, rezervasyonu başlatalım: isim-soyisim ve telefonumu göndereyim mi?"
    )


@pytest.mark.unit
def test_parse_room_selection_with_typo_exclusvie():
    rooms = [
        {"room_key": "exclusivePool", "is_refundable": False, "room_display": "Exclusive Pool"},
        {"room_key": "exclusivePool", "is_refundable": True, "room_display": "Exclusive Pool"},
    ]
    selected = _parse_room_selection("exclusvie pool oda için rezervasyon oluştur", rooms)
    assert selected is not None
    assert selected["room_key"] == "exclusivePool"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_booking_requirements_question_returns_info_instead_of_room_list(monkeypatch):
    async def _no_payment(*_args, **_kwargs):
        return None

    monkeypatch.setattr(h, "_looks_like_room_stock_question", lambda _msg: False)
    monkeypatch.setattr(h, "get_booking_flow", lambda _phone: {"state": h.BookingFlowState.IDLE, "data": {}})
    monkeypatch.setattr(h, "_handle_payment_intent", _no_payment)
    monkeypatch.setattr(h, "get_price_offers", lambda _phone: {"offers": [{"dummy": True}], "query_params": {}})
    async def _fake_start(_phone, _message, _cached, _lang):
        return {
            "reply": "Lütfen aşağıdaki bilgileri yazın.\nTek tek ilerleyeceğiz. İlk adım: Ad Soyad",
            "status": "booking_flow",
            "log": None,
        }

    monkeypatch.setattr(h, "_start_booking_flow", _fake_start)

    result = await h.handle_booking_flow(
        phone="905551112233",
        message="Tamam, rezervasyonu başlatmak istiyorum; hangi bilgileri iletmem gerekiyor?",
        lang="tr",
    )

    assert result is not None
    assert result["status"] == "booking_requirements_info"
    assert "Tek tek" in result["reply"]
    assert "Ad Soyad" in result["reply"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_booking_requirements_share_question_without_cache_returns_requirements(monkeypatch):
    async def _no_payment(*_args, **_kwargs):
        return None

    monkeypatch.setattr(h, "_looks_like_room_stock_question", lambda _msg: False)
    monkeypatch.setattr(h, "get_booking_flow", lambda _phone: {"state": h.BookingFlowState.IDLE, "data": {}})
    monkeypatch.setattr(h, "_handle_payment_intent", _no_payment)
    monkeypatch.setattr(h, "get_price_offers", lambda _phone: {})

    result = await h.handle_booking_flow(
        phone="905551112244",
        message="Tamam, rezervasyonu başlatalım: isim-soyisim ve telefonumu göndereyim mi?",
        lang="tr",
    )

    assert result is not None
    assert result["status"] == "booking_requirements_info"
    assert "tek tek" in result["reply"].lower()
    assert "ad soyad" in result["reply"].lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_handle_booking_flow_ignores_restaurant_booking_sentence_without_cache(monkeypatch):
    async def _no_payment(*_args, **_kwargs):
        return None

    monkeypatch.setattr(h, "_looks_like_room_stock_question", lambda _msg: False)
    monkeypatch.setattr(h, "get_booking_flow", lambda _phone: {"state": h.BookingFlowState.IDLE, "data": {}})
    monkeypatch.setattr(h, "_handle_payment_intent", _no_payment)
    monkeypatch.setattr(h, "get_price_offers", lambda _phone: {})

    result = await h.handle_booking_flow(
        phone="905551112255",
        message="Akşam yemeği için rezervasyon yapmak istiyorum.",
        lang="tr",
    )

    assert result is None
