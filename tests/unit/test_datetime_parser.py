"""
Unit Tests: DateTime Parser
===========================

Test edilen modül: app/services/datetime_parser.py
Fonksiyon: extract_time_from_text()

Kapsam:
- Standart saat formatları (19:30, 19.30, 19h30)
- Türkçe ifadeler (akşam 8, 8 buçuk, saat 7)
- İngilizce ifadeler (8 pm, at 7)
- Edge case'ler ve hatalı girdiler
"""

import pytest
import sys
from pathlib import Path

# Proje kökünü ekle
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.datetime_parser import extract_time_from_text


class TestExtractTimeFromText:
    """extract_time_from_text() fonksiyonu testleri"""
    
    # ==========================================
    # STANDART FORMATLAR
    # ==========================================
    
    @pytest.mark.unit
    @pytest.mark.parametrize("input_text,expected", [
        ("19:30", "19:30"),
        ("19.30", "19:30"),
        ("19h30", "19:30"),
        ("08:00", "08:00"),
        ("8:00", "08:00"),
        ("09:45", "09:45"),
        ("23:59", "23:59"),
        ("00:00", "00:00"),
    ])
    def test_standard_time_formats(self, input_text: str, expected: str):
        """Standart saat formatlarını test et"""
        result = extract_time_from_text(input_text)
        assert result == expected, f"Input: {input_text}, Expected: {expected}, Got: {result}"
    
    
    # ==========================================
    # TÜRKÇE İFADELER
    # ==========================================
    
    @pytest.mark.unit
    @pytest.mark.parametrize("input_text,expected", [
        ("saat 8", "08:00"),
        ("saat 19", "19:00"),
        ("saat 7'de", "07:00"),
        ("8'de", "08:00"),
        ("19'da", "19:00"),
        ("akşam 7", "19:00"),
        ("akşam 8", "20:00"),
        ("akşam 9", "21:00"),
        ("gece 10", "22:00"),
        ("sabah 9", "09:00"),
        ("öğlen 1", "13:00"),
        ("öğle 12", "12:00"),
    ])
    def test_turkish_time_expressions(self, input_text: str, expected: str):
        """Türkçe saat ifadelerini test et"""
        result = extract_time_from_text(input_text)
        assert result == expected, f"Input: {input_text}, Expected: {expected}, Got: {result}"
    
    
    @pytest.mark.unit
    @pytest.mark.parametrize("input_text,expected", [
        ("8 buçuk", "08:30"),
        ("8 buçuk akşam", "20:30"),
        ("akşam 8 buçuk", "20:30"),
        ("7 buçuk akşam yemeği", "19:30"),
        ("sabah 9 buçuk", "09:30"),
    ])
    def test_turkish_half_hour(self, input_text: str, expected: str):
        """Türkçe 'buçuk' ifadelerini test et"""
        result = extract_time_from_text(input_text)
        assert result == expected, f"Input: {input_text}, Expected: {expected}, Got: {result}"
    
    
    # ==========================================
    # İNGİLİZCE İFADELER
    # ==========================================
    
    @pytest.mark.unit
    @pytest.mark.parametrize("input_text,expected", [
        ("8 pm", "20:00"),
        ("8pm", "20:00"),
        ("7 pm", "19:00"),
        ("12 pm", "12:00"),
        ("12 am", "00:00"),
        ("at 7", "07:00"),
        ("at 19", "19:00"),
    ])
    def test_english_time_expressions(self, input_text: str, expected: str):
        """İngilizce saat ifadelerini test et"""
        result = extract_time_from_text(input_text)
        assert result == expected, f"Input: {input_text}, Expected: {expected}, Got: {result}"
    
    
    # ==========================================
    # BAĞLAMSAL İFADELER
    # ==========================================
    
    @pytest.mark.unit
    @pytest.mark.parametrize("input_text,expected", [
        ("akşam yemeği için", "19:30"),
        ("dinner reservation", "19:30"),
        ("akşam", "19:30"),
        ("evening", "19:30"),
        ("öğlen yemeği", "13:00"),
        ("lunch", "13:00"),
        ("kahvaltı", "10:00"),
        ("breakfast", "10:00"),
    ])
    def test_contextual_defaults(self, input_text: str, expected: str):
        """Bağlamsal varsayılan saatleri test et"""
        result = extract_time_from_text(input_text)
        assert result == expected, f"Input: {input_text}, Expected: {expected}, Got: {result}"
    
    
    # ==========================================
    # KARMAŞIK MESAJLAR
    # ==========================================
    
    @pytest.mark.unit
    @pytest.mark.parametrize("input_text,expected", [
        ("3 kişi için akşam 8'de rezervasyon", "20:00"),
        ("yarın saat 19:30 için masa ayırtmak istiyorum", "19:30"),
        ("15 Mayıs akşam 7 buçukta 4 kişilik", "19:30"),
        ("Can I book for 7pm tomorrow?", "19:00"),
        ("Table for 4 at 8 pm please", "20:00"),
    ])
    def test_complex_messages(self, input_text: str, expected: str):
        """Karmaşık mesajlardan saat çıkarımını test et"""
        result = extract_time_from_text(input_text)
        assert result == expected, f"Input: {input_text}, Expected: {expected}, Got: {result}"
    
    
    # ==========================================
    # EDGE CASES
    # ==========================================
    
    @pytest.mark.unit
    @pytest.mark.parametrize("input_text", [
        "",
        None,
        "merhaba",
        "hello",
        "rezervasyon yapmak istiyorum",
        "kaç kişisiniz",
    ])
    def test_no_time_found(self, input_text):
        """Saat içermeyen mesajlarda None dönmeli"""
        result = extract_time_from_text(input_text or "")
        assert result is None, f"Input: {input_text}, Expected: None, Got: {result}"
    
    
    @pytest.mark.unit
    def test_person_count_not_confused_with_time(self):
        """Kişi sayısı saat olarak algılanmamalı"""
        # "3 kişi" → 3 saat olarak algılanmamalı
        result = extract_time_from_text("3 kişi için rezervasyon")
        # Saat bağlamı olmadığı için None veya akşam default
        assert result is None or result == "19:30"
    
    
    @pytest.mark.unit
    def test_date_not_confused_with_time(self):
        """Tarih içindeki sayılar saat olarak algılanmamalı"""
        # "15 Mayıs" → 15 saat olarak algılanmamalı
        result = extract_time_from_text("15 Mayıs için")
        assert result is None or result != "15:00"
    
    
    # ==========================================
    # GEÇERSİZ SAATLER
    # ==========================================
    
    @pytest.mark.unit
    @pytest.mark.parametrize("input_text", [
        "25:00",
        "saat 25",
        "99:99",
    ])
    def test_invalid_hours(self, input_text: str):
        """Geçersiz saat değerleri reddedilmeli"""
        result = extract_time_from_text(input_text)
        assert result is None, f"Input: {input_text} should return None, got: {result}"