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
import json
import uuid
import importlib
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

# Proje kökünü ekle
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Test ortamı değişkenleri
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("WHATSAPP_PHONE_ID", "test-phone")
os.environ.setdefault("WHATSAPP_TOKEN", "test-token")


def _mid(prefix: str) -> str:
    """Create run-unique message ids to avoid cross-run idempotency collisions."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# ======================================================
# FIXTURES
# ======================================================

@pytest.fixture(scope="module")
def client(tmp_path_factory):
    """FastAPI test client"""
    from fastapi.testclient import TestClient

    tmp = tmp_path_factory.mktemp("it_api_routes")
    env_overrides = {
        "KASSANDRA_ENV": "test",
        "KASSANDRA_CONVERSATIONS_DIR": str(tmp / "conversations"),
        "KASSANDRA_MESSAGE_ID_FILE": str(tmp / "message_ids.json"),
        "KASSANDRA_FOLLOWUP_FILE": str(tmp / "followups.json"),
        "KASSANDRA_BOOKING_FLOW_FILE": str(tmp / "booking_flows.json"),
        "KASSANDRA_HOTEL_BOOKINGS_DB": str(tmp / "hotel_bookings.db"),
        "KASSANDRA_PRICE_FLOW_FILE": str(tmp / "price_flows.json"),
        "KASSANDRA_ROUTING_STATE_FILE": str(tmp / "routing_states.json"),
        "KASSANDRA_RESERVATIONS_DB": str(tmp / "reservations.db"),
        "KASSANDRA_RESERVATION_FLOW_FILE": str(tmp / "reservation_flows.json"),
        "KASSANDRA_REMINDERS_FILE": str(tmp / "reminders.json"),
        "KASSANDRA_REMINDER_LOG_FILE": str(tmp / "reminder_logs.json"),
        "METRICS_DB_PATH": str(tmp / "metrics.db"),
    }

    with patch.dict(os.environ, env_overrides, clear=False):
        import kassandra_fallback_eklenti as fallback_files

        # Legacy fallback modülü env kullanmıyor; testte paylaşılan C:/ dosyalarını izole et.
        fallback_files.RATE_LIMIT_FILE = tmp / "rate_limits.json"
        fallback_files.SAFE_MODE_FILE = tmp / "safe_mode.json"
        fallback_files.ERROR_COUNTER_FILE = tmp / "error_counter.json"

        import kassandra_openai_bot as bot

        # Ortam değişkenleri import-time okunduğu için app'i test env ile yeniden yükle.
        bot = importlib.reload(bot)

        from app.services.booking_flow_service import init_hotel_bookings_db

        init_hotel_bookings_db()

        # WhatsApp mock
        bot.send_whatsapp_message = AsyncMock(return_value=True)

        # LLM disambiguation/OpenAI fallback testte dış ağa çıkmasın.
        def _mock_openai_chat_create(*args, **kwargs):
            msg = ""
            try:
                messages = kwargs.get("messages") or []
                if messages:
                    msg = str(messages[-1].get("content") or "").lower()
            except Exception:
                msg = ""
            domain = "payment" if "ödeme" in msg or "odeme" in msg or "payment" in msg else "hotel"
            payload = json.dumps(
                {
                    "domain": domain,
                    "confidence": 0.95,
                    "rewritten_message": "A1 için ödeme linki gönderir misiniz?" if domain == "payment" else "Premium oda için rezervasyon yapmak istiyorum.",
                },
                ensure_ascii=False,
            )
            return Mock(choices=[Mock(message=Mock(content=payload))])

        try:
            bot.client.chat.completions.create = Mock(side_effect=_mock_openai_chat_create)
        except Exception:
            pass

        # QA devre dışı
        if hasattr(bot, "QA_ENABLED"):
            bot.QA_ENABLED = False

        yield TestClient(bot.app)


@pytest.fixture
def clean_conversation(client):
    """Her test öncesi konuşmayı temizle"""
    def _clean(phone: str):
        clean_phone = "".join(ch for ch in str(phone or "") if ch.isdigit())
        key_variants = {clean_phone, f"+{clean_phone}", f"  {clean_phone}  "}

        try:
            from app.services.conversation_store import purge_phone_data
            # Hard purge with booking cleanup for deterministic integration runs.
            purge_phone_data(phone, hard_delete_bookings=True)
        except Exception:
            pass

        try:
            from app.services.conversation_store import clear_conversation
            from app.services.message_id_service import clear_message_ids
            clear_conversation(phone)
            clear_message_ids(phone)
        except Exception:
            pass

        # Extra safety: reset booking flow state file(s) to avoid stale SELECT_ROOM state.
        flow_paths = []
        try:
            from app.services.booking_flow_service import BOOKING_FLOW_FILE
            flow_paths.append(Path(BOOKING_FLOW_FILE))
        except Exception:
            pass
        flow_paths.extend([Path("data/booking_flows.json"), Path("tests/data/booking_flows.json")])
        for p in flow_paths:
            if not p.exists():
                continue
            try:
                p.write_text("{}", encoding="utf-8")
            except Exception:
                # keep fixture best-effort; tests should proceed even if cleanup path fails
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
        # Konfigürasyona göre root korunuyor olabilir.
        assert response.status_code in [200, 307, 401, 404]

    @pytest.mark.integration
    def test_health_correlation_id_echo(self, client):
        correlation_id = "it-health-cid-001"
        response = client.get("/health", headers={"X-Correlation-Id": correlation_id})
        assert response.status_code == 200
        assert response.headers.get("X-Correlation-Id") == correlation_id

    @pytest.mark.integration
    def test_admin_unauthorized_has_correlation_id(self, client):
        correlation_id = "it-admin-cid-001"
        response = client.get("/admin/metrics", headers={"X-Correlation-Id": correlation_id})
        assert response.status_code in [401, 403, 302]
        assert response.headers.get("X-Correlation-Id") == correlation_id


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
    def test_chat_info_question_returns_non_empty_response(self, client, clean_conversation):
        """Bilgi sorusunda boş olmayan bir cevap dönmeli."""
        phone = "905551111005"
        clean_conversation(phone)
        
        # Önce selamla
        client.post("/chat", json={
            "phone": phone,
            "message": "Merhaba",
            "coalesce_mode": "immediate"
        })
        
        # Sonra bilgi sorusu
        response = client.post("/chat", json={
            "phone": phone,
            "message": "WiFi var mı?",
            "coalesce_mode": "immediate"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        status = data.get("status", "")
        reply = data.get("reply", "").lower()

        assert status != "local_faq"
        assert bool(reply.strip())

    @pytest.mark.integration
    def test_chat_first_message_forces_welcome(self, client, clean_conversation):
        phone = "905551111006"
        clean_conversation(phone)

        response = client.post("/chat", json={
            "phone": phone,
            "message": "Fiyat bilgisi için giriş ve çıkış tarihlerinizi paylaşır mısınız?",
            "message_id": _mid("msg-first-1"),
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
            "message_id": _mid("msg-pay-1"),
        })

        response = client.post("/chat", json={
            "phone": phone,
            "message": "Ödeme yöntemleriniz neler (kredi kartı/havale)?",
            "message_id": _mid("msg-pay-2"),
        })
        assert response.status_code == 200
        reply = (response.json().get("reply") or "").lower()
        assert "kredi kart" in reply
        assert "mail order" in reply
        assert ("havale" in reply) or ("eft" in reply)

    @pytest.mark.integration
    def test_chat_payment_link_try_flow_with_mocked_bookingapi(self, client, clean_conversation, monkeypatch):
        phone = "905551111107"
        clean_conversation(phone)

        from app.services.booking_flow_service import create_hotel_booking, update_hotel_booking_status

        booking = create_hotel_booking(
            {
                "customer_phone": phone,
                "guest_first_name": "Deneme",
                "guest_last_name": "Deneme",
                "guest_phone": "+905304498453",
                "guest_email": "gonenomeralperen@gmail.com",
                "hotel_id": 21966,
                "check_in": "2026-10-01",
                "check_out": "2026-10-06",
                "nights": 5,
                "adult_count": 2,
                "child_ages": [11, 12],
                "room_type": "PREMIUM",
                "room_type_display": "Premium - Jakuzili (45m2)",
                "room_type_id": 438550,
                "board_type_id": 44512,
                "rate_type_id": 24171,
                "rate_code_id": 183666,
                "price_agency_id": 247664,
                "currency": "EUR",
                "currency_id": 44,
                "total_price": 1365.0,
                "discounted_price": 1365.0,
                "is_refundable": False,
                "lang": "tr",
            }
        )
        update_hotel_booking_status(
            int(booking["id"]),
            "elektra_created",
            elektra_reservation_id="89227844",
        )

        calls = []

        async def _fake_update(*, hotel_id, reservation_id, updates, timeout_sec=20):
            calls.append(dict(updates))
            return {"success": True}

        monkeypatch.setattr("app.handlers.booking_flow_handler.update_elektraweb_reservation", _fake_update)
        # first_message branch'indeki follow-up yan etkilerini atlamak için geçmiş seed et.
        from app.services.conversation_store import get_conversation_file
        convo_file = get_conversation_file(phone)
        convo_file.parent.mkdir(parents=True, exist_ok=True)
        convo_file.write_text(
            json.dumps(
                {
                    "phone": phone,
                    "messages": [
                        {
                            "timestamp": "2026-01-01T00:00:00",
                            "date": "2026-01-01",
                            "time": "00:00:00",
                            "user_message": "Merhaba",
                            "bot_reply": "Hoş geldiniz",
                            "is_price_template": False,
                        }
                    ],
                    "created_at": "2026-01-01T00:00:00",
                    "updated_at": "2026-01-01T00:00:00",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        from app.services.routing_state_service import set_domain_lock
        set_domain_lock(phone, "payment", reason="test_payment_link_try_flow")

        # Odeme linki istegi -> para birimi sorulmali.
        r1 = client.post(
            "/chat",
            json={
                "phone": phone,
                # "ödeme"+"havale" ile payment skoru 2 olur, LLM disambiguation bypass edilir.
                "message": "A1 için ödeme havale linki gönder",
                "message_id": _mid("msg-paytry-1"),
            },
        )
        assert r1.status_code == 200
        assert r1.json().get("status") == "payment_currency_requested"

        # TRY secimi -> odeme linki donmeli.
        r2 = client.post(
            "/chat",
            json={
                "phone": phone,
                "message": "273 TRY",
                "message_id": _mid("msg-paytry-2"),
            },
        )
        assert r2.status_code == 200
        body = r2.json()
        assert body.get("status") == "payment_link_sent"
        reply_low = (body.get("reply") or "").lower()
        assert "273 try" in reply_low
        assert "currency=try" in reply_low

        # BookingAPI update payload kontrolu:
        assert calls, "updateReservation cagrilari bekleniyordu"
        assert any(c.get("ROOMID") == 438550 for c in calls)
        try_payloads = [c for c in calls if c.get("DEPOSITCURRENCYCODE") == "TRY"]
        assert try_payloads, "TRY odeme hazirlik payload'i bekleniyordu"
        for p in try_payloads:
            # TRY quote mismatch'i tetiklememek icin baz currency korunmali.
            assert p.get("currency-code") != "TRY"

    @pytest.mark.integration
    def test_chat_message_id_idempotency(self, client, clean_conversation):
        phone = "905551111008"
        clean_conversation(phone)
        payload = {
            "phone": phone,
            "message": "Merhaba",
            "message_id": _mid("msg-idem-1"),
        }
        first = client.post("/chat", json=payload)
        second = client.post("/chat", json=payload)
        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json().get("status") == "duplicate_message_id"

    @pytest.mark.integration
    def test_chat_correlation_id_header_and_trace(self, client, clean_conversation):
        phone = "905551111013"
        clean_conversation(phone)

        trace_file = Path("logs/decision_trace.jsonl")
        before_count = 0
        if trace_file.exists():
            before_count = len(trace_file.read_text(encoding="utf-8").splitlines())

        correlation_id = "it-correlation-12345"
        response = client.post(
            "/chat",
            json={
                "phone": phone,
                "message": "Merhaba",
                "message_id": _mid("msg-cid-1"),
            },
            headers={"X-Correlation-Id": correlation_id},
        )

        assert response.status_code == 200
        assert response.headers.get("X-Correlation-Id") == correlation_id

        assert trace_file.exists()
        lines = trace_file.read_text(encoding="utf-8").splitlines()
        new_lines = lines[before_count:]
        assert new_lines, "decision trace file should have at least one new line"

        found = False
        for line in new_lines:
            try:
                row = json.loads(line)
            except Exception:
                continue
            if row.get("correlation_id") == correlation_id:
                found = True
                break
        assert found, "correlation_id should be present in decision trace entries"

    @pytest.mark.integration
    def test_chat_metric_includes_correlation_id(self, client, clean_conversation):
        from app.services.metrics_service import list_events

        phone = "905551111014"
        clean_conversation(phone)
        correlation_id = "it-metric-cid-12345"

        response = client.post(
            "/chat",
            json={
                "phone": phone,
                "message": "Merhaba",
                "message_id": _mid("msg-cid-metric-1"),
            },
            headers={"X-Correlation-Id": correlation_id},
        )
        assert response.status_code == 200

        items, _ = list_events(days=1, limit=500, offset=0)
        found = any((item.get("meta") or {}).get("correlation_id") == correlation_id for item in items)
        assert found, "record_metric should persist correlation_id in meta"

    @pytest.mark.integration
    def test_chat_restaurant_to_hotel_intent_override(self, client, clean_conversation):
        phone = "905551111009"
        clean_conversation(phone)

        # Restoran akışını başlat
        client.post("/chat", json={
            "phone": phone,
            "message": "Restoran rezervasyonu yapmak istiyorum",
            "message_id": _mid("msg-rh-1"),
        })

        # Sonraki mesajda otel/fiyat niyeti baskın olmalı
        response = client.post("/chat", json={
            "phone": phone,
            "message": "Oda fiyatı için 10-12 Ağustos 2 yetişkin",
            "message_id": _mid("msg-rh-2"),
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
            "message_id": _mid("msg-amb-1"),
        })

        # Belirsiz transactional niyet: net domain yok.
        response = client.post("/chat", json={
            "phone": phone,
            "message": "Rezervasyon için yardımcı olur musunuz?",
            "message_id": _mid("msg-amb-2"),
        })
        assert response.status_code == 200
        data = response.json()
        status = data.get("status")
        reply = (data.get("reply") or "").lower()
        assert status in {"routing_clarification_required", "flow_orchestrator", "ok"}
        if status == "routing_clarification_required":
            assert data.get("reason_code") == "ambiguous_intent"
            assert data.get("next_expected_input") == "1|2|3|4"
        if status == "ok":
            assert ("rezervasyon" in reply) or ("tarih" in reply)

    @pytest.mark.integration
    def test_chat_domain_lock_choice_applies(self, client, clean_conversation):
        phone = "905551111012"
        clean_conversation(phone)

        client.post("/chat", json={
            "phone": phone,
            "message": "Merhaba",
            "message_id": _mid("msg-lock-1"),
        })
        client.post("/chat", json={
            "phone": phone,
            "message": "Rezervasyon için yardımcı olur musunuz?",
            "message_id": _mid("msg-lock-2"),
        })
        response = client.post("/chat", json={
            "phone": phone,
            "message": "1",
            "message_id": _mid("msg-lock-3"),
        })
        assert response.status_code == 200
        data = response.json()
        status = data.get("status")
        reply = (data.get("reply") or "").lower()
        assert status in {"domain_lock_set", "flow_orchestrator", "ok"}
        if status == "domain_lock_set":
            assert data.get("reason_code") == "user_route_choice"
        if status == "ok":
            assert ("rezervasyon" in reply) or ("oda" in reply) or ("tarih" in reply)


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
