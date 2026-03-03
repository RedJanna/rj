import pytest

from app.services import elektraweb_booking_service as ews
from app.services.elektraweb_booking_service import _format_price_reply


@pytest.mark.unit
def test_quiet_room_request_filters_out_noisy_room_types():
    offers = [
        {
            "room-type": "DELUXE ROOM",
            "cancellation-penalty": {"is-refundable": False},
            "discounted-price": 500.0,
            "currency": "EUR",
            "available": True,
            "rate-type": "İptal Edilemez",
        },
        {
            "room-type": "SUPERIOR ROOM",
            "cancellation-penalty": {"is-refundable": False},
            "discounted-price": 480.0,
            "currency": "EUR",
            "available": True,
            "rate-type": "İptal Edilemez",
        },
        {
            "room-type": "EXCLUSIVE LAND VIEW ROOM",
            "cancellation-penalty": {"is-refundable": False},
            "discounted-price": 450.0,
            "currency": "EUR",
            "available": True,
            "rate-type": "İptal Edilemez",
        },
    ]

    reply, success = _format_price_reply(
        offers,
        "tr",
        "2026-08-18",
        "2026-08-21",
        2,
        request_context_text="sessiz oda istiyorum",
    )

    assert success is True
    assert "Deluxe" in reply
    assert "Superior (30m2)" not in reply
    assert "Exclusive Sokak Manzarali" not in reply
    assert "Superior odalar da sessizdir" in reply


@pytest.mark.unit
def test_requested_room_feature_not_available_returns_feature_specific_message():
    offers = [
        {
            "room-type": "DELUXE ROOM",
            "cancellation-penalty": {"is-refundable": False},
            "discounted-price": 500.0,
            "currency": "EUR",
            "available": True,
            "rate-type": "İptal Edilemez",
        }
    ]

    reply, success = _format_price_reply(
        offers,
        "tr",
        "2026-08-18",
        "2026-08-21",
        2,
        request_context_text="deniz manzaralı oda istiyorum",
    )

    assert success is True
    assert "deniz manzaralı oda bulunmamaktadır" in reply
    assert "havuz manzaralı" in reply
    assert "cadde manzaralı" in reply


@pytest.mark.unit
def test_sea_view_price_difference_query_returns_no_sea_view_inventory_message():
    offers = [
        {
            "room-type": "DELUXE ROOM",
            "cancellation-penalty": {"is-refundable": False},
            "discounted-price": 500.0,
            "currency": "EUR",
            "available": True,
            "rate-type": "İptal Edilemez",
        },
        {
            "room-type": "SUPERIOR ROOM",
            "cancellation-penalty": {"is-refundable": False},
            "discounted-price": 650.0,
            "currency": "EUR",
            "available": True,
            "rate-type": "İptal Edilemez",
        },
    ]

    reply, success = _format_price_reply(
        offers,
        "tr",
        "2026-08-10",
        "2026-08-13",
        2,
        request_context_text="Aynı tarihlerde deniz manzaralı oda müsait mi, varsa fiyat farkı ne kadar?",
    )

    assert success is True
    assert "deniz manzaralı oda bulunmamaktadır" in reply
    assert "alternatif oda tipleri" in reply


@pytest.mark.unit
def test_standard_room_request_returns_only_standard_room_prices():
    offers = [
        {
            "room-type": "DELUXE ROOM",
            "cancellation-penalty": {"is-refundable": False},
            "discounted-price": 500.0,
            "currency": "EUR",
            "available": True,
            "rate-type": "İptal Edilemez",
        },
        {
            "room-type": "SUPERIOR ROOM",
            "cancellation-penalty": {"is-refundable": False},
            "discounted-price": 650.0,
            "currency": "EUR",
            "available": True,
            "rate-type": "İptal Edilemez",
        },
        {
            "room-type": "EXCLUSIVE LAND VIEW ROOM",
            "cancellation-penalty": {"is-refundable": False},
            "discounted-price": 900.0,
            "currency": "EUR",
            "available": True,
            "rate-type": "İptal Edilemez",
        },
    ]

    reply, success = _format_price_reply(
        offers,
        "tr",
        "2026-08-18",
        "2026-08-21",
        2,
        request_context_text="standart oda fiyatı nedir",
    )

    assert success is True
    assert "Deluxe" in reply
    assert "Superior (30m2)" in reply
    assert "Exclusive Sokak Manzarali" not in reply


@pytest.mark.unit
def test_pool_view_request_includes_superior_and_exclusive_pool_from_hotel_data():
    offers = [
        {
            "room-type": "DELUXE ROOM",
            "cancellation-penalty": {"is-refundable": False},
            "discounted-price": 500.0,
            "currency": "EUR",
            "available": True,
            "rate-type": "İptal Edilemez",
        },
        {
            "room-type": "SUPERIOR ROOM",
            "cancellation-penalty": {"is-refundable": False},
            "discounted-price": 650.0,
            "currency": "EUR",
            "available": True,
            "rate-type": "İptal Edilemez",
        },
        {
            "room-type": "EXCLUSIVE POOL VIEW ROOM",
            "cancellation-penalty": {"is-refundable": False},
            "discounted-price": 900.0,
            "currency": "EUR",
            "available": True,
            "rate-type": "İptal Edilemez",
        },
    ]

    reply, success = _format_price_reply(
        offers,
        "tr",
        "2026-08-18",
        "2026-08-21",
        2,
        request_context_text="havuz manzaralı oda fiyatı nedir",
    )

    assert success is True
    assert "Superior (30m2)" in reply
    assert "Exclusive Havuz Manzarali (40m2)" in reply
    assert "Deluxe (25m2)" not in reply


@pytest.mark.unit
def test_resolve_room_key_from_label_supports_turkish_aliases():
    assert ews._resolve_room_key_from_label("Exclusive Havuz Manzaralı") == "exclusivePool"
    assert ews._resolve_room_key_from_label("Exclusive Sokak Manzaralı") == "exclusiveLand"


@pytest.mark.unit
def test_rate_type_fallback_uses_bookable_contract_when_public_types_missing():
    offers = [
        {
            "room-type": "PREMIUM ROOM",
            "cancellation-penalty": {"is-refundable": False},
            "discounted-price": 755.0,
            "currency": "EUR",
            "available": True,
            "rate-type": "Kontrat",
            "room-to-sell": 2,
            "rate-rules": {"stop-sell": False},
            "availability-arr": [2, 2, 2],
        }
    ]

    reply, success = _format_price_reply(
        offers,
        "tr",
        "2026-08-10",
        "2026-08-13",
        2,
    )

    assert success is True
    assert "Premium - Jakuzili" in reply
    assert "Maalesef" not in reply


@pytest.mark.unit
@pytest.mark.asyncio
async def test_coerce_offer_currency_converts_prices_to_try(monkeypatch):
    async def _fake_rates(*_args, **_kwargs):
        # 1 EUR = 40 TRY
        return {"EUR": 40.0, "TRY": 1.0}

    monkeypatch.setattr(ews, "_fetch_exchange_rates_map", _fake_rates)

    offers = [
        {
            "room-type": "DELUXE ROOM",
            "discounted-price": 100.0,
            "price": 100.0,
            "currency": "EUR",
            "cancellation-penalty": {"is-refundable": False},
            "available": True,
            "rate-type": "İptal Edilemez",
        }
    ]

    converted = await ews._coerce_offer_currency(
        offers,
        requested_currency="TRY",
        hotel_id="21966",
        rate_date="2026-08-10",
    )

    assert converted[0]["currency"] == "TRY"
    assert converted[0]["discounted-price"] == 4000.0


@pytest.mark.unit
def test_try_currency_is_rendered_with_lira_symbol_in_turkish_reply():
    offers = [
        {
            "room-type": "DELUXE ROOM",
            "cancellation-penalty": {"is-refundable": False},
            "discounted-price": 12000.0,
            "currency": "TRY",
            "available": True,
            "rate-type": "İptal Edilemez",
        }
    ]

    reply, success = _format_price_reply(
        offers,
        "tr",
        "2026-08-10",
        "2026-08-13",
        2,
    )

    assert success is True
    assert "₺" in reply


@pytest.mark.unit
def test_russian_reply_uses_cyrillic_room_names():
    offers = [
        {
            "room-type": "PENTHOUSE ROOM",
            "cancellation-penalty": {"is-refundable": False},
            "discounted-price": 966.0,
            "currency": "EUR",
            "available": True,
            "rate-type": "İptal Edilemez",
        }
    ]

    reply, success = _format_price_reply(
        offers,
        "ru",
        "2026-08-14",
        "2026-08-18",
        2,
    )

    assert success is True
    assert "Пентхаус" in reply
    assert "Penthouse with Jacuzzi" not in reply
