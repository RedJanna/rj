import datetime as dt

import pytest

from app.services.elektraweb_booking_service import _extract_all_dates


def _day_month(iso_date: str) -> tuple[int, int]:
    d = dt.datetime.strptime(iso_date, "%Y-%m-%d")
    return d.day, d.month


@pytest.mark.unit
def test_extract_all_dates_parses_en_dash_single_month_range():
    dates = _extract_all_dates("23–26 Ağustos (3 gece) için toplam 4 yetişkin olacağız.")
    assert len(dates) >= 2
    assert _day_month(dates[0]) == (23, 8)
    assert _day_month(dates[1]) == (26, 8)


@pytest.mark.unit
def test_extract_all_dates_parses_mojibake_month_and_dash():
    dates = _extract_all_dates("23â€“26 AÄŸustos (3 gece) icin toplam 4 yetiskin.")
    assert len(dates) >= 2
    assert _day_month(dates[0]) == (23, 8)
    assert _day_month(dates[1]) == (26, 8)


@pytest.mark.unit
def test_extract_all_dates_parses_spanish_de_august_range():
    dates = _extract_all_dates("Precio total para 2 adultos del 14 al 18 de agosto de 2026.")
    assert len(dates) >= 2
    assert _day_month(dates[0]) == (14, 8)
    assert _day_month(dates[1]) == (18, 8)


@pytest.mark.unit
def test_extract_all_dates_parses_german_dotted_august_range():
    dates = _extract_all_dates("Gesamtpreis für 2 Erwachsene vom 14. bis 18. August 2026.")
    assert len(dates) >= 2
    assert _day_month(dates[0]) == (14, 8)
    assert _day_month(dates[1]) == (18, 8)


@pytest.mark.unit
def test_extract_all_dates_parses_chinese_range():
    dates = _extract_all_dates("请提供2026年8月14日至18日两位成人的总价。")
    assert len(dates) >= 2
    assert _day_month(dates[0]) == (14, 8)
    assert _day_month(dates[1]) == (18, 8)


@pytest.mark.unit
def test_extract_all_dates_parses_arabic_august_range():
    dates = _extract_all_dates("يرجى مشاركة السعر الإجمالي لشخصين بالغين من 14 إلى 18 أغسطس 2026.")
    assert len(dates) >= 2
    assert _day_month(dates[0]) == (14, 8)
    assert _day_month(dates[1]) == (18, 8)


@pytest.mark.unit
def test_extract_all_dates_parses_hindi_august_range():
    dates = _extract_all_dates("कृपया 14 से 18 अगस्त 2026 तक 2 वयस्कों के लिए कुल कीमत बताएं।")
    assert len(dates) >= 2
    assert _day_month(dates[0]) == (14, 8)
    assert _day_month(dates[1]) == (18, 8)


@pytest.mark.unit
def test_extract_all_dates_parses_uppercase_turkish_i_range_with_guest_payload():
    text = "1 EKİM İLE 3 ekim tarihleri arasında 2 yetişkin 1 çocuk için müsaitlik var mı"
    dates = _extract_all_dates(text)
    assert len(dates) >= 2
    assert _day_month(dates[0]) == (1, 10)
    assert _day_month(dates[1]) == (3, 10)
