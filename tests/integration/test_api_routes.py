"""
Integration Tests: API Routes
=============================

FastAPI endpoint testleri.

Kapsam:
- /chat endpoint
- /admin/* endpoints
- Health check
- Error handling
"""

import pytest
import sys
import os
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

# Proje kökünü ekle
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Test ortamı değişkenleri
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("WHATSAPP_PHONE_ID", "test-phone")
os.environ.setdefault("WHATSAPP_TOKEN", "test-token")


# ======================================================
# FIXTURES
# ======================================================

@pytest.fixture(scope="module")
def client():
    """FastAPI test client"""
    from fastapi.testclient import TestClient
    import kassandra_openai_bot as bot
    
    # WhatsApp mock
    bot.send_whatsapp_message = AsyncMock(return_value=True)
    
    # QA devre dışı
    if hasattr(bot, 'QA_ENABLED'):
        bot.QA_ENABLED = False
    
    return TestClient(bot.app)


@pytest.fixture
def clean_conversation(client):
    """Her test öncesi konuşmayı temizle"""
    def _clean(phone: str):
        try:
            import kassandra_openai_bot as bot
            if hasattr(bot, 'purge_phone_data'):
                bot.purge_phone_data(phone)
            elif hasattr(bot, 'clear_conversation'):
                bot.clear_conversation(phone)
        except:
            pass
    return _clean


# ======================================================
# HEALTH CHECK TESTLERİ
# ======================================================

class TestHealthCheck:
    """Health check endpoint testleri"""
    
    @pytest.mark.integration
    def test_health_endpoint_exists(self, client):
        """Health endpoint mevcut olmalı"""
        response = client.get("/admin/health")
        assert response.status_code in [200, 401, 403], \
            f"Health endpoint hatası: {response.status_code}"
    
    
    @pytest.mark.integration
    def test_root_endpoint(self, client):
        """Root endpoint"""
        response = client.get("/")
        # 200 veya redirect olabilir
        assert response.status_code in [200, 307, 404]


# ======================================================
# CHAT ENDPOINT TESTLERİ
# ======================================================

class TestChatEndpoint:
    """POST /chat endpoint testleri"""
    
    @pytest.mark.integration
    def test_chat_valid_request(self, client, clean_conversation):
        """Geçerli chat isteği"""
        phone = "905551111001"
        clean_conversation(phone)
        
        response = client.post("/chat", json={
            "phone": phone,
            "message": "Merhaba",
            "coalesce_mode": "immediate"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data or "status" in data
    
    
    @pytest.mark.integration
    def test_chat_missing_phone(self, client):
        """Telefon numarası eksik"""
        response = client.post("/chat", json={
            "message": "Merhaba"
        })
        
        # 422 Validation Error veya 400 Bad Request
        assert response.status_code in [400, 422]
    
    
    @pytest.mark.integration
    def test_chat_missing_message(self, client):
        """Mesaj eksik"""
        response = client.post("/chat", json={
            "phone": "905551111002"
        })
        
        assert response.status_code in [400, 422]
    
    
    @pytest.mark.integration
    def test_chat_empty_message(self, client, clean_conversation):
        """Boş mesaj"""
        phone = "905551111003"
        clean_conversation(phone)
        
        response = client.post("/chat", json={
            "phone": phone,
            "message": "",
            "coalesce_mode": "immediate"
        })
        
        # Boş mesaj reddedilmeli veya varsayılan cevap verilmeli
        assert response.status_code in [200, 400, 422]
    
    
    @pytest.mark.integration
    def test_chat_greeting_response(self, client, clean_conversation):
        """Selamlama cevabı kontrolü"""
        phone = "905551111004"
        clean_conversation(phone)
        
        response = client.post("/chat", json={
            "phone": phone,
            "message": "Merhaba",
            "coalesce_mode": "immediate"
        })
        
        assert response.status_code == 200
        data = response.json()
        reply = data.get("reply", "").lower()
        
        # Selamlama cevabında Kassandra veya hoş geldiniz olmalı
        assert "kassandra" in reply or "hoş geldiniz" in reply or "merhaba" in reply
    
    
    @pytest.mark.integration
    def test_chat_local_faq_response(self, client, clean_conversation):
        """LOCAL FAQ cevabı"""
        phone = "905551111005"
        clean_conversation(phone)
        
        # Önce selamla
        client.post("/chat", json={
            "phone": phone,
            "message": "Merhaba",
            "coalesce_mode": "immediate"
        })
        
        # Sonra FAQ sorusu
        response = client.post("/chat", json={
            "phone": phone,
            "message": "WiFi var mı?",
            "coalesce_mode": "immediate"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Status local_faq olmalı veya wifi kelimesi geçmeli
        status = data.get("status", "")
        reply = data.get("reply", "").lower()
        
        assert status == "local_faq" or "wifi" in reply or "internet" in reply

    @pytest.mark.integration
    def test_chat_first_message_forces_welcome(self, client, clean_conversation):
        phone = "905551111006"
        clean_conversation(phone)

        response = client.post("/chat", json={
            "phone": phone,
            "message": "Fiyat bilgisi için giriş ve çıkış tarihlerinizi paylaşır mısınız?",
            "message_id": "msg-first-1",
        })
        assert response.status_code == 200
        data = response.json()
        reply = (data.get("reply") or "").lower()
        assert "kassandra" in reply and ("hoş geldiniz" in reply or "hos geldiniz" in reply)

    @pytest.mark.integration
    def test_chat_payment_method_after_reset(self, client, clean_conversation):
        phone = "905551111007"
        clean_conversation(phone)

        # Geçmiş sıfır sonrası ilk mesaj
        client.post("/chat", json={
            "phone": phone,
            "message": "Merhaba",
            "message_id": "msg-pay-1",
        })

        response = client.post("/chat", json={
            "phone": phone,
            "message": "Ödeme yöntemleriniz neler (kredi kartı/havale)?",
            "message_id": "msg-pay-2",
        })
        assert response.status_code == 200
        reply = (response.json().get("reply") or "").lower()
        assert "kredi kart" in reply
        assert "mail order" in reply
        assert ("havale" in reply) or ("eft" in reply)

    @pytest.mark.integration
    def test_chat_message_id_idempotency(self, client, clean_conversation):
        phone = "905551111008"
        clean_conversation(phone)
        payload = {
            "phone": phone,
            "message": "Merhaba",
            "message_id": "msg-idem-1",
        }
        first = client.post("/chat", json=payload)
        second = client.post("/chat", json=payload)
        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json().get("status") == "duplicate_message_id"

    @pytest.mark.integration
    def test_chat_restaurant_to_hotel_intent_override(self, client, clean_conversation):
        phone = "905551111009"
        clean_conversation(phone)

        # Restoran akışını başlat
        client.post("/chat", json={
            "phone": phone,
            "message": "Restoran rezervasyonu yapmak istiyorum",
            "message_id": "msg-rh-1",
        })

        # Sonraki mesajda otel/fiyat niyeti baskın olmalı
        response = client.post("/chat", json={
            "phone": phone,
            "message": "Oda fiyatı için 10-12 Ağustos 2 yetişkin",
            "message_id": "msg-rh-2",
        })
        assert response.status_code == 200
        reply = (response.json().get("reply") or "").lower()
        # Eski davranışta restoran formuna takılı kalabiliyordu; onu engellediğimizi kontrol et
        assert "kaç kişi, tarih, saat ve isim" not in reply

    @pytest.mark.integration
    def test_chat_router_v2_ambiguity_prompt(self, client, clean_conversation):
        phone = "905551111011"
        clean_conversation(phone)

        # İlk mesajda welcome gelir.
        client.post("/chat", json={
            "phone": phone,
            "message": "Merhaba",
            "message_id": "msg-amb-1",
        })

        # Belirsiz transactional niyet: net domain yok.
        response = client.post("/chat", json={
            "phone": phone,
            "message": "Rezervasyon için yardımcı olur musunuz?",
            "message_id": "msg-amb-2",
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "routing_clarification_required"
        assert data.get("reason_code") == "ambiguous_intent"
        assert data.get("next_expected_input") == "1|2|3|4"

    @pytest.mark.integration
    def test_chat_domain_lock_choice_applies(self, client, clean_conversation):
        phone = "905551111012"
        clean_conversation(phone)

        client.post("/chat", json={
            "phone": phone,
            "message": "Merhaba",
            "message_id": "msg-lock-1",
        })
        client.post("/chat", json={
            "phone": phone,
            "message": "Rezervasyon için yardımcı olur musunuz?",
            "message_id": "msg-lock-2",
        })
        response = client.post("/chat", json={
            "phone": phone,
            "message": "1",
            "message_id": "msg-lock-3",
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "domain_lock_set"
        assert data.get("reason_code") == "user_route_choice"


# ======================================================
# COALESCE MODE TESTLERİ
# ======================================================

class TestCoalesceMode:
    """Mesaj birleştirme testleri"""
    
    @pytest.mark.integration
    def test_immediate_mode(self, client, clean_conversation):
        """immediate mode - anında cevap"""
        phone = "905551111010"
        clean_conversation(phone)
        
        response = client.post("/chat", json={
            "phone": phone,
            "message": "Test mesajı",
            "coalesce_mode": "immediate"
        })
        
        assert response.status_code == 200
        data = response.json()
        # immediate modda reply olmalı
        assert "reply" in data or "status" in data


# ======================================================
# HATA DURUMU TESTLERİ
# ======================================================

class TestErrorHandling:
    """Hata durumu testleri"""
    
    @pytest.mark.integration
    def test_invalid_json(self, client):
        """Geçersiz JSON"""
        response = client.post(
            "/chat",
            content="invalid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422
    
    
    @pytest.mark.integration
    def test_wrong_content_type(self, client):
        """Yanlış content type"""
        response = client.post(
            "/chat",
            data="phone=123&message=test",
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        # 415 veya 422
        assert response.status_code in [415, 422, 400]


# ======================================================
# CONVERSATION PERSISTENCE TESTLERİ
# ======================================================

class TestConversationPersistence:
    """Konuşma sürekliliği testleri"""
    
    @pytest.mark.integration
    def test_conversation_context(self, client, clean_conversation):
        """Konuşma bağlamı korunmalı"""
        phone = "905551111020"
        clean_conversation(phone)
        
        # 1. Mesaj - Selamlama
        response1 = client.post("/chat", json={
            "phone": phone,
            "message": "Merhaba",
            "coalesce_mode": "immediate"
        })
        assert response1.status_code == 200
        
        # 2. Mesaj - Menü seçimi
        response2 = client.post("/chat", json={
            "phone": phone,
            "message": "1",
            "coalesce_mode": "immediate"
        })
        assert response2.status_code == 200
        
        # Her iki cevap da başarılı olmalı
        data1 = response1.json()
        data2 = response2.json()
        
        assert "reply" in data1 or "status" in data1
        assert "reply" in data2 or "status" in data2
