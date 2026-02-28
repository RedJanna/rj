"""
Unit Tests: Message Utils
=========================

Test edilen modül: app/utils/message_utils.py

Kapsam:
- is_greeting() - Selamlama tespiti
- is_conversation_ending() - Kapanış tespiti
- detect_language() - Dil algılama
- is_menu_selection() - Menü seçimi
- get_welcome_message() - Karşılama mesajı
- get_closing_message() - Kapanış mesajı
"""

import pytest
import sys
from pathlib import Path

# Proje kökünü ekle
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.utils.message_utils import (
    is_greeting,
    is_conversation_ending,
    detect_language,
    detect_price_request,
    is_menu_selection,
    get_welcome_message,
    get_closing_message,
    get_menu_response,
    looks_like_transfer_message,
)


class TestIsGreeting:
    """is_greeting() fonksiyonu testleri"""
    
    # ==========================================
    # TÜRKÇE SELAMLAMALAR
    # ==========================================
    
    @pytest.mark.unit
    @pytest.mark.parametrize("input_text,expected_greeting,expected_lang", [
        ("merhaba", True, "tr"),
        ("Merhaba", True, "tr"),
        ("MERHABA", True, "tr"),
        ("selam", True, "tr"),
        ("selamlar", True, "tr"),
        ("merhabalar", True, "tr"),
        ("günaydın", True, "tr"),
        ("iyi akşamlar", True, "tr"),
        ("iyi günler", True, "tr"),
        ("naber", True, "tr"),
        ("nbr", True, "tr"),
    ])
    def test_turkish_greetings(self, input_text: str, expected_greeting: bool, expected_lang: str):
        """Türkçe selamlamaları test et"""
        is_greet, lang = is_greeting(input_text)
        assert is_greet == expected_greeting, f"Input: {input_text}"
        assert lang == expected_lang, f"Input: {input_text}, Expected lang: {expected_lang}, Got: {lang}"
    
    
    # ==========================================
    # İNGİLİZCE SELAMLAMALAR
    # ==========================================
    
    @pytest.mark.unit
    @pytest.mark.parametrize("input_text,expected_greeting,expected_lang", [
        ("hello", True, "en"),
        ("Hello", True, "en"),
        ("hi", True, "en"),
        ("Hi", True, "en"),
        ("hey", True, "en"),
        ("good morning", True, "en"),
        ("good afternoon", True, "en"),
        ("good evening", True, "en"),
        ("howdy", True, "en"),
        ("what's up", True, "en"),
    ])
    def test_english_greetings(self, input_text: str, expected_greeting: bool, expected_lang: str):
        """İngilizce selamlamaları test et"""
        is_greet, lang = is_greeting(input_text)
        assert is_greet == expected_greeting, f"Input: {input_text}"
        assert lang == expected_lang, f"Input: {input_text}, Expected lang: {expected_lang}, Got: {lang}"
    
    
    # ==========================================
    # SELAMLAMA OLMAYAN MESAJLAR
    # ==========================================
    
    @pytest.mark.unit
    @pytest.mark.parametrize("input_text", [
        "rezervasyon yapmak istiyorum",
        "fiyat nedir",
        "kahvaltı saat kaçta",
        "I want to book a table",
        "What time is breakfast?",
        "3 kişilik masa",
        "yarın akşam",
    ])
    def test_non_greetings(self, input_text: str):
        """Selamlama olmayan mesajları test et"""
        is_greet, _ = is_greeting(input_text)
        assert is_greet == False, f"Input: {input_text} should not be a greeting"


class TestIsConversationEnding:
    """is_conversation_ending() fonksiyonu testleri"""
    
    @pytest.mark.unit
    @pytest.mark.parametrize("input_text,expected", [
        ("teşekkürler", True),
        ("teşekkür ederim", True),
        ("sağol", True),
        ("sağolun", True),
        ("thanks", True),
        ("thank you", True),
        ("bye", True),
        ("goodbye", True),
        ("görüşürüz", True),
        ("hoşçakal", True),
        ("iyi günler", True),
        ("iyi akşamlar", True),
        ("iyi geceler", True),
        ("tamam bu kadar", True),
    ])
    def test_ending_phrases(self, input_text: str, expected: bool):
        """Konuşma bitiş ifadelerini test et"""
        result = is_conversation_ending(input_text)
        assert result == expected, f"Input: {input_text}"
    
    
    @pytest.mark.unit
    @pytest.mark.parametrize("input_text", [
        "merhaba",
        "rezervasyon istiyorum",
        "evet",
        "hayır",
        "devam edelim",
    ])
    def test_non_ending_phrases(self, input_text: str):
        """Bitiş olmayan ifadeleri test et"""
        result = is_conversation_ending(input_text)
        assert result == False, f"Input: {input_text} should not be ending"


class TestDetectLanguage:
    """detect_language() fonksiyonu testleri"""
    
    # ==========================================
    # TÜRKÇE TESPİTİ
    # ==========================================
    
    @pytest.mark.unit
    @pytest.mark.parametrize("input_text", [
        "Merhaba, nasılsınız?",
        "Kahvaltı saat kaçta?",
        "Rezervasyon yapmak istiyorum",
        "Çok güzel",
        "Teşekkürler",
        "Ödeme yapacağım",
        "Şimdi gelebilir miyim?",
    ])
    def test_turkish_detection(self, input_text: str):
        """Türkçe mesajları doğru algıla"""
        result = detect_language(input_text)
        assert result == "tr", f"Input: {input_text}, Expected: tr, Got: {result}"
    
    
    # ==========================================
    # İNGİLİZCE TESPİTİ
    # ==========================================
    
    @pytest.mark.unit
    @pytest.mark.parametrize("input_text", [
        "Hello, how are you?",
        "I want to make a reservation",
        "Can I book a table?",
        "What time is breakfast?",
        "Thank you very much",
        "Good morning",
        "Please help me",
    ])
    def test_english_detection(self, input_text: str):
        """İngilizce mesajları doğru algıla"""
        result = detect_language(input_text)
        assert result == "en", f"Input: {input_text}, Expected: en, Got: {result}"
    
    
    # ==========================================
    # EDGE CASES
    # ==========================================
    
    @pytest.mark.unit
    def test_mixed_language_turkish_chars_priority(self):
        """EN > TR önceliği: karışık mesajda EN seçilmeli"""
        result = detect_language("Hello, günaydın")
        assert result == "en"
    
    
    @pytest.mark.unit
    def test_keyboard_error_tolerance(self):
        """Klavye hatası toleransı (ı → i)"""
        # "Can ı book" → "Can i book" olarak algılanmalı
        result = detect_language("Can ı book a table?")
        assert result == "en"
    
    
    @pytest.mark.unit
    def test_default_is_english(self):
        """Belirsiz/kapsam dışı durumlarda varsayılan İngilizce"""
        result = detect_language("12345")
        assert result == "en"

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "input_text,expected",
        [
            ("hallo, ich möchte reservieren", "de"),
            ("hola, quiero reservar", "es"),
            ("bonjour, je veux réserver", "fr"),
            ("مرحبا اريد الحجز", "ar"),
            ("你好，我要预订", "zh"),
            ("नमस्ते मुझे बुकिंग चाहिए", "hi"),
            ("olá, quero reservar", "pt"),
            ("ქართული ტექსტი", "en"),
        ],
    )
    def test_multilanguage_priority_and_fallback(self, input_text: str, expected: str):
        result = detect_language(input_text)
        assert result == expected


class TestLooksLikeTransferMessage:
    @pytest.mark.unit
    @pytest.mark.parametrize("input_text", [
        "Dalaman Havalimanı 13 Haziran 17:00 iniş",
        "2 kişi, 1 bagaj ve 1 adet bebek koltuğu",
        "TK1234 uçuşu için transfer istiyorum",
    ])
    def test_detects_transfer_payload(self, input_text: str):
        assert looks_like_transfer_message(input_text) is True

    @pytest.mark.unit
    @pytest.mark.parametrize("input_text", [
        "2 yetişkin, 1 çocuk için oda fiyatı",
        "Kahvaltı saat kaçta başlıyor?",
        "Deluxe oda müsait mi?",
    ])
    def test_does_not_flag_non_transfer_messages(self, input_text: str):
        assert looks_like_transfer_message(input_text) is False


class TestDetectPriceRequest:
    @pytest.mark.unit
    def test_detects_room_suitability_with_guest_mix_without_dates(self):
        msg = "Do you have a room suitable for 2 adults + 1 child (7 years old)?"
        assert detect_price_request(msg, history=[]) is True

    @pytest.mark.unit
    def test_does_not_trigger_for_non_booking_suitability_sentence(self):
        msg = "Is August suitable for swimming?"
        assert detect_price_request(msg, history=[]) is False


class TestMenuSelection:
    """is_menu_selection() ve get_menu_response() testleri"""
    
    @pytest.mark.unit
    @pytest.mark.parametrize("input_text,expected_is_menu,expected_selection", [
        ("1", True, 1),
        ("2", True, 2),
        ("3", True, 3),
        ("4", True, 4),
        ("5", False, 0),
        ("0", False, 0),
        ("bir", False, 0),
        ("one", False, 0),
        ("merhaba", False, 0),
    ])
    def test_menu_selection(self, input_text: str, expected_is_menu: bool, expected_selection: int):
        """Menü seçimi tespitini test et"""
        is_menu, selection = is_menu_selection(input_text)
        assert is_menu == expected_is_menu, f"Input: {input_text}"
        assert selection == expected_selection, f"Input: {input_text}"
    
    
    @pytest.mark.unit
    def test_menu_responses_turkish(self):
        """Türkçe menü cevaplarını test et"""
        for i in range(1, 5):
            response = get_menu_response(i, "tr")
            assert response is not None
            assert len(response) > 0
    
    
    @pytest.mark.unit
    def test_menu_responses_english(self):
        """İngilizce menü cevaplarını test et"""
        for i in range(1, 5):
            response = get_menu_response(i, "en")
            assert response is not None
            assert len(response) > 0


class TestWelcomeAndClosingMessages:
    """Karşılama ve kapanış mesajları testleri"""
    
    @pytest.mark.unit
    def test_welcome_message_turkish(self):
        """Türkçe karşılama mesajı"""
        msg = get_welcome_message("tr")
        assert "Kassandra" in msg
        assert "hoş geldiniz" in msg.lower() or "merhaba" in msg.lower()
        assert "1." in msg  # Menü seçenekleri
        assert "2." in msg
        assert "3." in msg
        assert "4." in msg
    
    
    @pytest.mark.unit
    def test_welcome_message_english(self):
        """İngilizce karşılama mesajı"""
        msg = get_welcome_message("en")
        assert "Kassandra" in msg
        assert "welcome" in msg.lower() or "hello" in msg.lower()
        assert "1." in msg  # Menu options
        assert "2." in msg
        assert "3." in msg
        assert "4." in msg
    
    
    @pytest.mark.unit
    def test_closing_message_turkish(self):
        """Türkçe kapanış mesajı"""
        msg = get_closing_message("tr")
        assert "Kassandra" in msg
        assert len(msg) > 20
    
    
    @pytest.mark.unit
    def test_closing_message_english(self):
        """İngilizce kapanış mesajı"""
        msg = get_closing_message("en")
        assert "Kassandra" in msg
        assert len(msg) > 20
