"""
Unit Tests: Reservation Info Extraction
=======================================

Test edilen modül: app/services/restaurant_reservation_flow_service.py

Kapsam:
- extract_guest_count() - Kişi sayısı çıkarma
- extract_date() - Tarih çıkarma
- extract_time() - Saat çıkarma
- extract_name() - İsim çıkarma
- extract_all_reservation_info() - Tüm bilgileri çıkarma
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Proje kökünü ekle
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.restaurant_reservation_flow_service import (
    extract_guest_count,
    extract_date,
    extract_time,
    extract_all_reservation_info,
    get_meal_type_from_time,
    is_within_season,
    should_break_reservation_flow,
    validate_reservation_time,
)


class TestExtractGuestCount:
    """extract_guest_count() fonksiyonu testleri"""
    
    @pytest.mark.unit
    @pytest.mark.parametrize("input_text,expected", [
        ("3 kişi", 3),
        ("3 kişilik", 3),
        ("5 kişi için", 5),
        ("2 kişiyiz", 2),
        ("4 misafir", 4),
        ("for 4 people", 4),
        ("4 people", 4),
        ("2 guests", 2),
        ("1 person", 1),
        ("3 adults", 3),
        ("kişi sayısı 4 olacak", 4),
        ("kisi sayisi 5 olarak guncelle", 5),
        ("guest count is 6", 6),
    ])
    def test_numeric_guest_counts(self, input_text: str, expected: int):
        """Sayısal kişi sayısı çıkarımı"""
        result = extract_guest_count(input_text)
        assert result == expected, f"Input: {input_text}, Expected: {expected}, Got: {result}"
    
    
    @pytest.mark.unit
    @pytest.mark.parametrize("input_text,expected", [
        ("iki kişi", 2),
        ("üç kişilik", 3),
        ("dört kişi için", 4),
        ("two people", 2),
        ("three guests", 3),
        ("four persons", 4),
    ])
    def test_word_guest_counts(self, input_text: str, expected: int):
        """Yazıyla yazılmış kişi sayısı"""
        result = extract_guest_count(input_text)
        assert result == expected, f"Input: {input_text}, Expected: {expected}, Got: {result}"
    
    
    @pytest.mark.unit
    @pytest.mark.parametrize("input_text", [
        "merhaba",
        "rezervasyon istiyorum",
        "yarın akşam",
        "saat 8",
    ])
    def test_no_guest_count(self, input_text: str):
        """Kişi sayısı içermeyen mesajlar"""
        result = extract_guest_count(input_text)
        assert result is None, f"Input: {input_text} should return None"
    
    
    @pytest.mark.unit
    def test_guest_count_range(self):
        """Makul olmayan kişi sayıları reddedilmeli"""
        # 0 veya negatif
        assert extract_guest_count("0 kişi") is None
        # 50'den fazla
        assert extract_guest_count("100 kişi") is None


class TestExtractDate:
    """extract_date() fonksiyonu testleri"""
    
    @pytest.mark.unit
    def test_tomorrow(self):
        """Yarın"""
        result = extract_date("yarın")
        expected = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        assert result == expected
    
    
    @pytest.mark.unit
    def test_today(self):
        """Bugün"""
        result = extract_date("bugün")
        expected = datetime.now().strftime("%Y-%m-%d")
        assert result == expected
    
    
    @pytest.mark.unit
    @pytest.mark.parametrize("input_text", [
        "15 Mayıs",
        "15 mayıs",
        "Mayıs 15",
    ])
    def test_turkish_date_formats(self, input_text: str):
        """Türkçe tarih formatları"""
        result = extract_date(input_text)
        assert result is not None, f"Input: {input_text}"
        assert "-05-15" in result, f"Input: {input_text}, Got: {result}"
    
    
    @pytest.mark.unit
    @pytest.mark.parametrize("input_text", [
        "June 15",
        "15 June",
        "15 july",
    ])
    def test_english_date_formats(self, input_text: str):
        """İngilizce tarih formatları"""
        result = extract_date(input_text)
        assert result is not None, f"Input: {input_text}"
    
    
    @pytest.mark.unit
    @pytest.mark.parametrize("input_text", [
        "15/05",
        "15.05",
        "15/05/2026",
        "15.05.2026",
    ])
    def test_numeric_date_formats(self, input_text: str):
        """Sayısal tarih formatları"""
        result = extract_date(input_text)
        assert result is not None, f"Input: {input_text}"
    
    
    @pytest.mark.unit
    def test_complex_message_with_date_and_guests(self):
        """Kişi sayısı ve tarih birlikte - kişi sayısı tarih olarak algılanmamalı"""
        result = extract_date("3 kişi için 15 Mayıs")
        assert result is not None
        # 3 değil, 15 Mayıs olmalı
        assert "-05-15" in result, f"Got: {result}"


class TestGetMealTypeFromTime:
    """get_meal_type_from_time() fonksiyonu testleri"""
    
    @pytest.mark.unit
    @pytest.mark.parametrize("time,expected", [
        ("09:00", "breakfast"),
        ("09:30", "breakfast"),
        ("10:00", "breakfast"),
        ("10:30", "breakfast"),
        ("12:00", "lunch"),
        ("13:00", "lunch"),
        ("14:00", "lunch"),
        ("15:00", "lunch"),
        ("18:00", "dinner"),
        ("19:00", "dinner"),
        ("19:30", "dinner"),
        ("20:00", "dinner"),
        ("21:00", "dinner"),
        ("21:30", "dinner"),
    ])
    def test_meal_type_mapping(self, time: str, expected: str):
        """Saate göre öğün tipi"""
        result = get_meal_type_from_time(time)
        assert result == expected, f"Time: {time}, Expected: {expected}, Got: {result}"


class TestIsWithinSeason:
    """is_within_season() fonksiyonu testleri"""
    
    @pytest.mark.unit
    @pytest.mark.parametrize("date,expected_within", [
        ("2026-04-10", True),   # Sezon başı
        ("2026-05-15", True),   # Sezon ortası
        ("2026-07-01", True),   # Yaz
        ("2026-10-15", True),   # Sezon sonu yakını
        ("2026-11-10", True),   # Sezon sonu
        ("2026-04-09", False),  # Sezon öncesi
        ("2026-11-11", False),  # Sezon sonrası
        ("2026-01-15", False),  # Kış
        ("2026-12-25", False),  # Aralık
    ])
    def test_season_dates(self, monkeypatch, date: str, expected_within: bool):
        """Sezon tarihleri kontrolü"""
        monkeypatch.setattr(
            "app.services.restaurant_reservation_flow_service.season_bounds_for_year",
            lambda year: (
                datetime(year, 4, 10).date(),
                datetime(year, 11, 10).date(),
            ),
        )
        result, message = is_within_season(date)
        assert result == expected_within, f"Date: {date}, Expected: {expected_within}, Got: {result}, Message: {message}"

    @pytest.mark.unit
    def test_season_message_uses_runtime_dates(self, monkeypatch):
        monkeypatch.setattr(
            "app.utils.date_utils.season_bounds_for_year",
            lambda year: (
                datetime(year, 4, 20).date(),
                datetime(year, 11, 10).date(),
            ),
        )
        result, message = is_within_season("2026-04-15")
        assert result is False
        assert "20 Nisan" in message
        assert "10 Kasım" in message


class TestValidateReservationTime:
    """validate_reservation_time() fonksiyonu testleri"""
    
    @pytest.mark.unit
    def test_valid_dinner_time(self):
        """Geçerli akşam yemeği saati"""
        # 18:00-22:00 arası geçerli
        result, message = validate_reservation_time("19:30", "dinner")
        assert result == True, f"Message: {message}"
    
    
    @pytest.mark.unit
    def test_invalid_early_dinner(self):
        """Çok erken akşam yemeği"""
        result, message = validate_reservation_time("16:00", "dinner")
        assert result == False, "16:00 akşam yemeği için çok erken"
    
    
    @pytest.mark.unit
    def test_invalid_late_dinner(self):
        """Çok geç akşam yemeği"""
        result, message = validate_reservation_time("23:00", "dinner")
        assert result == False, "23:00 akşam yemeği için çok geç"


class TestReservationFlowBreakGuard:
    """Onay aşamasındaki düzeltmeler fallback'e düşmeden akışta kalmalı."""

    @pytest.mark.unit
    def test_confirm_state_does_not_break_on_guest_count_change(self):
        assert should_break_reservation_flow("Kişi sayısı 4 olacak", "confirm") is False

    @pytest.mark.unit
    def test_confirm_state_still_breaks_irrelevant_message(self):
        assert should_break_reservation_flow("Bana wifi şifresini de söyler misin?", "confirm") is True


class TestExtractAllReservationInfo:
    """extract_all_reservation_info() fonksiyonu testleri"""
    
    @pytest.mark.unit
    def test_complete_message(self):
        """Tüm bilgileri içeren mesaj"""
        message = "3 kişi için yarın akşam 8'de rezervasyon"
        result = extract_all_reservation_info(message)
        
        assert result["guest_count"] == 3
        assert result["date"] is not None
        assert result["time"] == "20:00"
        assert result["has_any_info"] == True
    
    
    @pytest.mark.unit
    def test_partial_message(self):
        """Kısmi bilgi içeren mesaj"""
        message = "4 kişiyiz"
        result = extract_all_reservation_info(message)
        
        assert result["guest_count"] == 4
        assert result["has_any_info"] == True
    
    
    @pytest.mark.unit
    def test_empty_message(self):
        """Bilgi içermeyen mesaj"""
        message = "merhaba"
        result = extract_all_reservation_info(message)
        
        assert result["guest_count"] is None
        assert result["date"] is None
        assert result["time"] is None
        assert result["has_any_info"] == False
