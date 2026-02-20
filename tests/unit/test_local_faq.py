"""
Unit Tests: Local FAQ
=====================

Test edilen modül: app/utils/message_utils.py (check_local_faq)
                   app/handlers/local_faq_handler.py

Kapsam:
- Tüm LOCAL_FAQ kategorileri
- Keyword matching
- Dil bazlı cevaplar
- Edge cases
"""

import pytest
import sys
from pathlib import Path

# Proje kökünü ekle
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.utils.message_utils import check_local_faq, LOCAL_FAQ, LOCAL_MAX_WORDS


class TestCheckLocalFAQ:
    """check_local_faq() fonksiyonu testleri"""
    
    # ==========================================
    # KAHVALTI
    # ==========================================
    
    @pytest.mark.unit
    @pytest.mark.parametrize("input_text", [
        "kahvaltı",
        "kahvaltı saat kaçta",
        "kahvaltı saati",
        "kahvaltı kaçta",
        "breakfast",
        "kahvaltı dahil mi",
    ])
    def test_breakfast_questions(self, input_text: str):
        """Kahvaltı sorularını test et"""
        found, answer_tr, answer_en, category, _answer_ru = check_local_faq(input_text)
        assert found == True, f"Input: {input_text}"
        assert category == "kahvalti", f"Input: {input_text}, Got category: {category}"
        assert "08:00" in answer_tr or "08:30" in answer_tr, f"Kahvaltı saati cevapta olmalı"
        assert "10:30" in answer_tr, f"Kahvaltı bitiş saati cevapta olmalı"
    
    
    # ==========================================
    # CHECK-IN / CHECK-OUT
    # ==========================================
    
    @pytest.mark.unit
    @pytest.mark.parametrize("input_text,expected_category", [
        ("check-in", "check_in"),
        ("check in", "check_in"),
        ("giriş saati", "check_in"),
        ("check-out", "check_out"),
        ("check out", "check_out"),
        ("çıkış saati", "check_out"),
    ])
    def test_checkin_checkout(self, input_text: str, expected_category: str):
        """Check-in/out sorularını test et"""
        found, answer_tr, answer_en, category, _answer_ru = check_local_faq(input_text)
        assert found == True, f"Input: {input_text}"
        assert category == expected_category, f"Input: {input_text}"
        
        if "check_in" in category:
            assert "14:00" in answer_tr, "Check-in 14:00 olmalı"
        elif "check_out" in category:
            assert "12:00" in answer_tr, "Check-out 12:00 olmalı"
    
    
    # ==========================================
    # HAVUZ
    # ==========================================
    
    @pytest.mark.unit
    @pytest.mark.parametrize("input_text", [
        "havuz var mı",
        "havuz",
        "pool",
        "yüzme",
    ])
    def test_pool_questions(self, input_text: str):
        """Havuz sorularını test et"""
        found, answer_tr, answer_en, category, _answer_ru = check_local_faq(input_text)
        assert found == True, f"Input: {input_text}"
        assert "havuz" in category, f"Input: {input_text}"
        # Havuz VAR olduğunu doğrula
        assert "evet" in answer_tr.lower() or "var" in answer_tr.lower() or "mevcut" in answer_tr.lower()
    
    
    @pytest.mark.unit
    def test_heated_pool_question(self):
        """Isıtmalı havuz sorusu"""
        found, answer_tr, answer_en, category, _answer_ru = check_local_faq("ısıtmalı havuz")
        assert found == True
        # Havuz ısıtmasız olduğunu doğrula
        assert "ısıtma" in answer_tr.lower() or "heated" in answer_en.lower()
    
    
    # ==========================================
    # TRANSFER
    # ==========================================
    
    @pytest.mark.unit
    @pytest.mark.parametrize("input_text", [
        "transfer fiyat",
        "transfer ücreti",
        "havalimanı transfer",
        "airport transfer",
    ])
    def test_transfer_questions(self, input_text: str):
        """Transfer sorularını test et"""
        found, answer_tr, answer_en, category, _answer_ru = check_local_faq(input_text)
        assert found == True, f"Input: {input_text}"
        assert category == "transfer", f"Input: {input_text}"
        # 75€ fiyat kontrolü
        assert "75" in answer_tr, f"Transfer fiyatı 75€ olmalı"
        assert "€" in answer_tr or "euro" in answer_tr.lower()
    
    
    # ==========================================
    # WIFI
    # ==========================================
    
    @pytest.mark.unit
    @pytest.mark.parametrize("input_text", [
        "wifi",
        "wi-fi",
        "internet",
        "kablosuz",
    ])
    def test_wifi_questions(self, input_text: str):
        """WiFi sorularını test et"""
        found, answer_tr, answer_en, category, _answer_ru = check_local_faq(input_text)
        assert found == True, f"Input: {input_text}"
        assert category == "wifi", f"Input: {input_text}"
        # Ücretsiz WiFi olduğunu doğrula
        assert "ücretsiz" in answer_tr.lower() or "free" in answer_en.lower()
    
    
    # ==========================================
    # KONUM / ADRES
    # ==========================================
    
    @pytest.mark.unit
    @pytest.mark.parametrize("input_text", [
        "nerede",
        "adres",
        "konum",
        "location",
    ])
    def test_location_questions(self, input_text: str):
        """Konum sorularını test et"""
        found, answer_tr, answer_en, category, _answer_ru = check_local_faq(input_text)
        assert found == True, f"Input: {input_text}"
        assert category == "adres", f"Input: {input_text}"
        # Ölüdeniz/Fethiye olduğunu doğrula
        assert "ölüdeniz" in answer_tr.lower() or "fethiye" in answer_tr.lower()
    
    
    # ==========================================
    # SEZON
    # ==========================================
    
    @pytest.mark.unit
    @pytest.mark.parametrize("input_text", [
        "sezon",
        "ne zaman açık",
        "açık mısınız",
    ])
    def test_season_questions(self, input_text: str):
        """Sezon sorularını test et"""
        found, answer_tr, answer_en, category, _answer_ru = check_local_faq(input_text)
        assert found == True, f"Input: {input_text}"
        assert category == "sezon", f"Input: {input_text}"
        # Nisan-Kasım olduğunu doğrula
        assert "nisan" in answer_tr.lower() or "april" in answer_en.lower()
        assert "kasım" in answer_tr.lower() or "november" in answer_en.lower()
    
    
    # ==========================================
    # KELİME SINIRI
    # ==========================================
    
    @pytest.mark.unit
    def test_word_limit_exceeded(self):
        """Kelime sınırı aşıldığında LOCAL FAQ çalışmamalı"""
        # LOCAL_MAX_WORDS = 5, bu yüzden 6+ kelime LOCAL'a gitmemeli
        long_message = "Ben yarın sabah kahvaltı için rezervasyon yapmak istiyorum acaba"
        found, _, _, _, _ = check_local_faq(long_message)
        assert found == False, "Uzun mesajlar LOCAL FAQ'a gitmemeli"
    
    
    @pytest.mark.unit
    def test_word_limit_within(self):
        """Kelime sınırı içinde LOCAL FAQ çalışmalı"""
        short_message = "kahvaltı saat kaçta"  # 3 kelime
        found, _, _, _, _ = check_local_faq(short_message)
        assert found == True, "Kısa mesajlar LOCAL FAQ'a gitmeli"
    
    
    # ==========================================
    # BULUNAMAYAN SORULAR
    # ==========================================
    
    @pytest.mark.unit
    @pytest.mark.parametrize("input_text", [
        "jakuzili oda",
        "fiyat ne kadar",
        # "ne yemek var" ÇIKARILDI - "yemek" kelimesi restoran kategorisinde var
        # ve eşleşmesi DOĞRU davranış
        "merhaba",
        "teşekkürler",
        "random text",
    ])
    def test_not_found_questions(self, input_text: str):
        """LOCAL FAQ'da olmayan sorular"""
        found, _, _, category, _ = check_local_faq(input_text)
        # Bu sorular FAQ'da yok, found=False olmalı
        # Not: Bazıları kelime sınırı nedeniyle de False dönebilir
        assert found == False or category == "", f"Input: {input_text} should not match FAQ"
    
    
    # ==========================================
    # RESTORAN (YENİ TEST)
    # ==========================================
    
    @pytest.mark.unit
    @pytest.mark.parametrize("input_text", [
        "restoran",
        "yemek",
        "ne yemek var",
        "akşam yemeği",
    ])
    def test_restaurant_questions(self, input_text: str):
        """Restoran sorularını test et"""
        found, answer_tr, answer_en, category, _answer_ru = check_local_faq(input_text)
        assert found == True, f"Input: {input_text}"
        assert category == "restoran", f"Input: {input_text}, Got category: {category}"
        # Restoran saatleri cevapta olmalı
        assert "11:00" in answer_tr or "22:00" in answer_tr, f"Restoran saatleri cevapta olmalı"
    
    
    # ==========================================
    # TÜM KATEGORİLERİN VAR OLDUĞUNU DOĞRULA
    # ==========================================
    
    @pytest.mark.unit
    def test_all_categories_have_required_fields(self):
        """Tüm FAQ kategorileri gerekli alanlara sahip olmalı"""
        required_fields = ["keywords", "answer_tr", "answer_en"]
        
        for category, data in LOCAL_FAQ.items():
            for field in required_fields:
                assert field in data, f"Category '{category}' missing field '{field}'"
                assert data[field], f"Category '{category}' has empty '{field}'"
    
    
    @pytest.mark.unit
    def test_local_max_words_is_reasonable(self):
        """LOCAL_MAX_WORDS makul bir değer olmalı"""
        assert LOCAL_MAX_WORDS >= 3, "En az 3 kelime olmalı"
        assert LOCAL_MAX_WORDS <= 10, "En fazla 10 kelime olmalı"
