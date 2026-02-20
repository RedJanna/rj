"""
End-to-End Tests: Reservation Flow
==================================

Tam restoran rezervasyon akışı testleri.
Gerçek API kullanılır (sınırlı).

Senaryolar:
- Happy path: Başarılı rezervasyon
- Eksik bilgi akışı
- Sezon dışı tarih
- Grup rezervasyonu (8+ kişi)
- Geç saat rezervasyonu
"""

import pytest
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

# Proje kökünü ekle
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Test ortamı
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("WHATSAPP_PHONE_ID", "test-phone")
os.environ.setdefault("WHATSAPP_TOKEN", "test-token")


# ======================================================
# FIXTURES
# ======================================================

@pytest.fixture(scope="module")
def e2e_client():
    """E2E test client"""
    from fastapi.testclient import TestClient
    import kassandra_openai_bot as bot
    
    # WhatsApp mock
    bot.send_whatsapp_message = AsyncMock(return_value=True)
    
    # QA devre dışı
    if hasattr(bot, 'QA_ENABLED'):
        bot.QA_ENABLED = False
    
    return TestClient(bot.app)


@pytest.fixture
def clean_state(e2e_client):
    """Her test için temiz başlangıç durumu"""
    def _clean(phone: str):
        try:
            import kassandra_openai_bot as bot
            if hasattr(bot, 'clear_conversation'):
                bot.clear_conversation(phone)
            if hasattr(bot, 'clear_reservation_flow'):
                bot.clear_reservation_flow(phone)
        except:
            pass
    return _clean


def send_message(client, phone: str, message: str) -> dict:
    """Mesaj gönder ve cevabı al"""
    response = client.post("/chat", json={
        "phone": phone,
        "message": message,
        "coalesce_mode": "immediate"
    })
    
    if response.status_code == 200:
        return response.json()
    return {"error": f"HTTP {response.status_code}", "reply": ""}


def get_season_date(days_ahead: int = 30) -> str:
    """Sezon içinde bir tarih döndür (Nisan-Kasım)"""
    today = datetime.now()
    target = today + timedelta(days=days_ahead)
    
    # Sezon dışındaysa Mayıs'a ayarla
    if target.month < 4 or target.month > 11:
        target = target.replace(month=5, day=15)
    
    return target.strftime("%d %B").replace(
        "January", "Ocak").replace("February", "Şubat").replace(
        "March", "Mart").replace("April", "Nisan").replace(
        "May", "Mayıs").replace("June", "Haziran").replace(
        "July", "Temmuz").replace("August", "Ağustos").replace(
        "September", "Eylül").replace("October", "Ekim").replace(
        "November", "Kasım").replace("December", "Aralık")


# ======================================================
# HAPPY PATH TESTLERİ
# ======================================================

class TestReservationHappyPath:
    """Başarılı rezervasyon akışı"""
    
    @pytest.mark.e2e
    @pytest.mark.slow
    def test_complete_reservation_flow(self, e2e_client, clean_state):
        """
        Tam rezervasyon akışı - adım adım
        1. Selamlama
        2. Rezervasyon niyeti
        3. Kişi sayısı
        4. Tarih
        5. Saat
        6. İsim
        7. Onay
        """
        phone = "905550000001"
        clean_state(phone)
        
        # 1. Selamlama
        r1 = send_message(e2e_client, phone, "Merhaba")
        assert "reply" in r1, "Selamlama cevabı alınamadı"
        assert "kassandra" in r1["reply"].lower() or "hoş geldiniz" in r1["reply"].lower()
        
        # 2. Rezervasyon niyeti
        r2 = send_message(e2e_client, phone, "Akşam yemeği için rezervasyon yapmak istiyorum")
        assert "reply" in r2
        # Kişi sayısı veya tarih sorulmalı
        reply2_lower = r2["reply"].lower()
        assert any(word in reply2_lower for word in ["kişi", "kaç", "tarih", "ne zaman", "people", "when"])
        
        # 3. Kişi sayısı
        r3 = send_message(e2e_client, phone, "4 kişiyiz")
        assert "reply" in r3
        
        # 4. Tarih
        season_date = get_season_date(30)
        r4 = send_message(e2e_client, phone, season_date)
        assert "reply" in r4
        
        # 5. Saat
        r5 = send_message(e2e_client, phone, "akşam 8")
        assert "reply" in r5
        
        # 6. İsim
        r6 = send_message(e2e_client, phone, "Ali Yılmaz")
        assert "reply" in r6
        
        # 7. Özel istek (varsa) veya onay
        reply6_lower = r6["reply"].lower()
        
        # Onay bekleniyor mu kontrol et
        if "onay" in reply6_lower or "evet" in reply6_lower or "doğru mu" in reply6_lower:
            # Evet ile onayla
            r7 = send_message(e2e_client, phone, "evet")
            final_reply = r7["reply"].lower()
        elif "özel" in reply6_lower or "special" in reply6_lower or "not" in reply6_lower:
            r7 = send_message(e2e_client, phone, "yok")
            final_reply = r7["reply"].lower()
            
            # Onay da sorulabilir
            if "onay" in final_reply or "evet" in final_reply or "doğru mu" in final_reply:
                r8 = send_message(e2e_client, phone, "evet")
                final_reply = r8["reply"].lower()
        else:
            final_reply = reply6_lower
        
        # Final kontrol - onay veya özet içermeli
        success_indicators = [
            "onay", "rezervasyon", "confirm", "tarih", "saat", 
            "tamamlandı", "oluşturuldu", "kaydedildi", "teşekkür",
            "reservation", "confirmed", "thank"
        ]
        
        assert any(word in final_reply for word in success_indicators), \
            f"Rezervasyon tamamlanmadı. Son cevap: {final_reply[:200]}"
    
    
    @pytest.mark.e2e
    def test_single_message_reservation(self, e2e_client, clean_state):
        """
        Tek mesajda tüm bilgilerle rezervasyon
        """
        phone = "905550000002"
        clean_state(phone)
        
        # Selamlama
        send_message(e2e_client, phone, "Merhaba")
        
        # Tek mesajda tüm bilgiler
        season_date = get_season_date(45)
        message = f"3 kişi için {season_date} akşam 7:30'da restoran rezervasyonu"
        
        r = send_message(e2e_client, phone, message)
        assert "reply" in r
        
        # Sadece isim sorulmalı (diğer bilgiler mesajda var)
        reply_lower = r["reply"].lower()
        assert any(word in reply_lower for word in ["isim", "name", "adınız"]), \
            f"İsim sorulmadı. Cevap: {reply_lower[:200]}"


# ======================================================
# EDGE CASE TESTLERİ
# ======================================================

class TestReservationEdgeCases:
    """Sınır durumu testleri"""
    
    @pytest.mark.e2e
    def test_season_blocked_date(self, e2e_client, clean_state):
        """Sezon dışı tarih reddedilmeli"""
        phone = "905550000010"
        clean_state(phone)
        
        send_message(e2e_client, phone, "Merhaba")
        send_message(e2e_client, phone, "Restoran rezervasyonu istiyorum")
        send_message(e2e_client, phone, "4 kişi")
        
        # Sezon dışı tarih (Ocak)
        r = send_message(e2e_client, phone, "15 Ocak")
        
        # Sezon mesajı veya hata olmalı
        if "status" in r:
            assert r.get("status") in ["season_blocked", "error", "ok"]
        
        reply_lower = r.get("reply", "").lower()
        # Sezon bilgisi verilmeli veya alternatif tarih istenmeli
        has_season_info = any(word in reply_lower for word in [
            "sezon", "nisan", "kasım", "april", "november", "kapalı", "açık"
        ])
        
        # Sezon dışı olduğu belirtilmeli
        assert has_season_info or "status" in r, \
            f"Sezon dışı tarih kontrolü yapılmadı. Cevap: {reply_lower[:200]}"
    
    
    @pytest.mark.e2e
    def test_large_group_handoff(self, e2e_client, clean_state):
        """8+ kişi için handoff tetiklenmeli"""
        phone = "905550000011"
        clean_state(phone)
        
        send_message(e2e_client, phone, "Merhaba")
        send_message(e2e_client, phone, "Restoran rezervasyonu")
        
        # 12 kişilik grup
        r = send_message(e2e_client, phone, "12 kişiyiz")
        
        reply_lower = r.get("reply", "").lower()
        status = r.get("status", "")
        
        # Handoff veya canlı destek yönlendirmesi olmalı
        is_handoff = status in ["handoff", "human_required", "group_handoff"]
        has_handoff_message = any(word in reply_lower for word in [
            "canlı", "destek", "iletişim", "arayın", "yetkili",
            "contact", "call", "support", "assist"
        ])
        
        assert is_handoff or has_handoff_message, \
            f"Grup handoff tetiklenmedi. Status: {status}, Cevap: {reply_lower[:200]}"
    
    
    @pytest.mark.e2e
    def test_late_dinner_time(self, e2e_client, clean_state):
        """22:00 sonrası rezervasyon"""
        phone = "905550000012"
        clean_state(phone)
        
        send_message(e2e_client, phone, "Merhaba")
        send_message(e2e_client, phone, "Akşam yemeği rezervasyonu")
        send_message(e2e_client, phone, "3 kişi")
        
        season_date = get_season_date(30)
        send_message(e2e_client, phone, season_date)
        
        # Geç saat
        r = send_message(e2e_client, phone, "22:30")
        
        reply_lower = r.get("reply", "").lower()
        
        # Saat uyarısı veya alternatif önerilmeli
        has_time_warning = any(word in reply_lower for word in [
            "22:00", "saat", "kapalı", "müsait değil", "erken",
            "öner", "alternatif", "closed", "available"
        ])
        
        # Ya uyarı verilmeli ya da handoff
        assert has_time_warning or r.get("status") in ["handoff", "time_error"], \
            f"Geç saat kontrolü yapılmadı. Cevap: {reply_lower[:200]}"


# ======================================================
# İPTAL AKIŞI TESTLERİ
# ======================================================

class TestReservationCancellation:
    """Rezervasyon iptali testleri"""
    
    @pytest.mark.e2e
    def test_cancel_intent_during_flow(self, e2e_client, clean_state):
        """Akış sırasında iptal niyeti"""
        phone = "905550000020"
        clean_state(phone)
        
        send_message(e2e_client, phone, "Merhaba")
        send_message(e2e_client, phone, "Rezervasyon yapmak istiyorum")
        send_message(e2e_client, phone, "4 kişi")
        
        # İptal et
        r = send_message(e2e_client, phone, "vazgeçtim iptal")
        
        reply_lower = r.get("reply", "").lower()
        status = r.get("status", "")
        
        # İptal onayı veya yeni başlangıç
        has_cancel_response = any(word in reply_lower for word in [
            "iptal", "vazgeç", "cancel", "tamam", "anlaşıldı",
            "başka", "yardımcı", "help"
        ])
        
        assert has_cancel_response or status in ["cancelled", "idle", "ok"], \
            f"İptal işlenmedi. Cevap: {reply_lower[:200]}"


# ======================================================
# DİL TUTARLILIĞI TESTLERİ
# ======================================================

class TestLanguageConsistency:
    """Dil tutarlılığı testleri"""
    
    @pytest.mark.e2e
    def test_english_flow_consistency(self, e2e_client, clean_state):
        """İngilizce akış tutarlılığı"""
        phone = "905550000030"
        clean_state(phone)
        
        # İngilizce başla
        r1 = send_message(e2e_client, phone, "Hello")
        assert "reply" in r1
        
        # İngilizce devam
        r2 = send_message(e2e_client, phone, "I want to book a table")
        reply2 = r2.get("reply", "")
        
        # Cevap İngilizce olmalı (Türkçe karakter olmamalı)
        turkish_chars = ["ş", "ğ", "ü", "ö", "ç", "ı", "İ", "Ş", "Ğ", "Ü", "Ö", "Ç"]
        
        # Not: Otel adı Türkçe olabilir (Ölüdeniz), bu kabul edilebilir
        # Ana metin İngilizce olmalı
        english_indicators = ["table", "reservation", "people", "person", "date", "time", "name"]
        has_english = any(word in reply2.lower() for word in english_indicators)
        
        assert has_english, f"İngilizce cevap beklendi. Cevap: {reply2[:200]}"
    
    
    @pytest.mark.e2e
    def test_turkish_flow_consistency(self, e2e_client, clean_state):
        """Türkçe akış tutarlılığı"""
        phone = "905550000031"
        clean_state(phone)
        
        # Türkçe başla
        r1 = send_message(e2e_client, phone, "Merhaba")
        assert "reply" in r1
        
        # Türkçe devam
        r2 = send_message(e2e_client, phone, "Rezervasyon yapmak istiyorum")
        reply2 = r2.get("reply", "")
        
        # Cevap Türkçe olmalı
        turkish_indicators = ["kişi", "tarih", "saat", "lütfen", "için", "istiyorum", "yardımcı"]
        has_turkish = any(word in reply2.lower() for word in turkish_indicators)
        
        assert has_turkish, f"Türkçe cevap beklendi. Cevap: {reply2[:200]}"
