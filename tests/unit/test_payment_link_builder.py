from urllib.parse import parse_qs, urlparse

from app.handlers import booking_flow_handler as h


def test_build_payment_link_try_includes_currency_aliases_and_id():
    link = h._build_payment_link(
        voucher_no="89229425",
        last_name="Deneme",
        check_in="2026-10-01",
        room_type_id=438550,
        currency="TRY",
        amount=273,
    )
    qs = parse_qs(urlparse(link).query)

    assert qs.get("currency") == ["TRY"]
    assert qs.get("CurrencyCode") == ["TRY"]
    assert qs.get("currencyId") == ["142"]
    assert qs.get("DEPOSITCURRENCYID") == ["142"]
    assert qs.get("CurrencySymbol") == ["₺"]
    assert qs.get("Amount") == ["273"]
    assert qs.get("DEPOSITPRICE") == ["273"]

