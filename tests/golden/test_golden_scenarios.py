"""
Golden Scenario Tests
=====================

Senaryo bazlı testler.
Bot cevaplarının beklenen anahtar kelimeleri içerip içermediğini test eder.

Çalıştırma:
    pytest tests/golden/test_golden_scenarios.py -v
    pytest tests/golden/test_golden_scenarios.py -v -k "breakfast"
    pytest tests/golden/test_golden_scenarios.py -v --smoke
"""

import pytest
import sys
import json
import re
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

# Proje kökünü ekle
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.golden.evaluator import GoldenEvaluator, load_scenarios, save_results


# Smoke senaryoları (core_scenarios.json içindeki smoke=true kayıtları)
def load_smoke_scenarios():
    scenarios = load_scenarios()
    smoke = [s for s in scenarios if s.get("smoke", False)]
    if smoke:
        return smoke
    # Fallback: smoke etiketi yoksa ilk 10 core senaryo
    core = [s for s in scenarios if s.get("is_core", True)]
    return core[:10]


SMOKE_SCENARIOS = load_smoke_scenarios()


def build_test_phone(seed: str) -> str:
    """Senaryo id'sinden stabil, 12 haneli test telefonu üretir."""
    digits = re.sub(r"\D", "", seed)
    if not digits:
        digits = "".join(str(ord(ch) % 10) for ch in seed)
    digits = (digits + "0" * 7)[:7]
    return f"90555{digits}"


# ======================================================
# FIXTURES
# ======================================================

@pytest.fixture(scope="module")
def evaluator():
    """Golden evaluator instance"""
    return GoldenEvaluator()


@pytest.fixture(scope="module")
def core_scenarios():
    """Core test senaryolarını yükle"""
    scenarios = load_scenarios()
    if not scenarios:
        # Varsayılan senaryolar
        scenarios = get_default_scenarios()
    return scenarios


@pytest.fixture(scope="module")
def bot_client():
    """Bot test client"""
    import os
    os.environ["FLOW_ORCHESTRATOR_MODE"] = "off"
    os.environ.setdefault("OPENAI_API_KEY", "test-key")
    os.environ.setdefault("WHATSAPP_PHONE_ID", "test-phone")
    os.environ.setdefault("WHATSAPP_TOKEN", "test-token")
    
    from fastapi.testclient import TestClient
    import kassandra_openai_bot as bot
    
    # WhatsApp gönderimini devre dışı bırak
    bot.send_whatsapp_message = AsyncMock(return_value=True)
    
    if hasattr(bot, 'QA_ENABLED'):
        bot.QA_ENABLED = False
    
    return TestClient(bot.app)


def _reset_phone_state(phone: str) -> None:
    """Telefon için test izolasyonunu garanti et."""
    try:
        from app.services.conversation_store import purge_phone_data
        purge_phone_data(phone)
        return
    except Exception:
        pass
    try:
        from app.services.conversation_store import clear_conversation
        from app.services.restaurant_reservation_flow_service import clear_reservation_flow
        from app.services.price_flow_service import clear_price_flow
        from app.services.booking_flow_service import clear_booking_flow

        clear_conversation(phone)
        clear_reservation_flow(phone)
        clear_price_flow(phone)
        clear_booking_flow(phone)
    except Exception:
        pass


# ======================================================
# VARSAYILAN SENARYOLAR
# ======================================================

def get_default_scenarios():
    """Varsayılan test senaryoları - LOCAL_FAQ ile uyumlu kısa sorular"""
    return [
        {
            "id": "selamlama",
            "category": "selamlama",
            "question": "Merhaba",
            "expected_keywords": ["Kassandra"],
            "forbidden_keywords": [],
            "description": "Karşılama mesajı",
            "is_core": True
        },
        {
            "id": "kahvalti",
            "category": "bilgi",
            "question": "kahvaltı saati",
            "expected_keywords": ["08:00", "10:30"],
            "forbidden_keywords": [],
            "description": "Kahvaltı saatleri",
            "is_core": True
        },
        {
            "id": "wifi",
            "category": "bilgi",
            "question": "wifi",
            "expected_keywords": ["var", "ücretsiz"],
            "forbidden_keywords": ["yok"],
            "description": "WiFi bilgisi",
            "is_core": True
        },
        {
            "id": "havuz",
            "category": "bilgi",
            "question": "havuz",
            "expected_keywords": ["havuz"],
            "forbidden_keywords": [],
            "description": "Havuz bilgisi",
            "is_core": True
        },
        {
            "id": "checkin",
            "category": "bilgi",
            "question": "check-in",
            "expected_keywords": ["14:00"],
            "forbidden_keywords": [],
            "description": "Check-in saati",
            "is_core": True
        }
    ]


# ======================================================
# YARDIMCI FONKSİYONLAR
# ======================================================

def get_bot_response(
    client,
    question: str,
    phone: str = "905551234567",
    reset_state: bool = True,
) -> str:
    """Bot'tan cevap al"""
    if reset_state:
        _reset_phone_state(phone)
    
    response = client.post("/chat", json={
        "phone": phone,
        "message": question,
        "coalesce_mode": "immediate"
    })
    
    if response.status_code == 200:
        data = response.json()
        return data.get("reply", "")
    return ""


# ======================================================
# SELAMLAMA TESTLERİ
# ======================================================

class TestGreetingScenarios:
    """Selamlama senaryoları"""
    
    @pytest.mark.golden
    def test_turkish_greeting(self, bot_client, evaluator):
        """Türkçe selamlama testi"""
        scenario = {
            "id": "greeting_tr",
            "question": "Merhaba",
            "expected_keywords": ["Kassandra", "1.", "2.", "3.", "4."],
            "forbidden_keywords": [],
            "description": "Türkçe selamlama"
        }
        
        response = get_bot_response(bot_client, scenario["question"])
        result = evaluator.evaluate(response, scenario)
        
        assert result["decision"] == "PASS", \
            f"Selamlama testi başarısız. Eksik: {result['missing_expected']}"
    
    
    @pytest.mark.golden
    def test_english_greeting(self, bot_client, evaluator):
        """İngilizce selamlama testi"""
        scenario = {
            "id": "greeting_en",
            "question": "Hello",
            "expected_keywords": ["Kassandra", "1.", "2.", "3.", "4."],
            "forbidden_keywords": [],
            "description": "İngilizce selamlama"
        }
        
        response = get_bot_response(bot_client, scenario["question"])
        result = evaluator.evaluate(response, scenario)
        
        assert result["decision"] == "PASS", \
            f"Selamlama testi başarısız. Eksik: {result['missing_expected']}"


# ======================================================
# BİLGİ SORU TESTLERİ
# ======================================================

class TestInfoScenarios:
    """Bilgi sorusu senaryoları"""
    
    @pytest.mark.golden
    @pytest.mark.parametrize("scenario_id,question,expected,forbidden", [
        ("breakfast", "Kahvaltı saat kaçta?", ["08:00", "10:30"], ["07:00", "11:00"]),
        ("checkin", "Check-in saat kaçta?", ["14:00"], ["15:00", "13:00"]),
        ("checkout", "Check-out saat kaçta?", ["12:00"], ["11:00", "10:00"]),
        ("wifi", "WiFi var mı?", ["var", "ücretsiz"], ["yok", "ücretli"]),
        ("pool", "Havuz var mı?", ["havuz", "var"], ["yok"]),
        ("transfer", "Transfer ücreti?", ["75", "€"], ["50", "100"]),
        ("location", "Otel nerede?", ["Ölüdeniz", "Fethiye"], ["Bodrum"]),
    ])
    def test_info_questions(self, bot_client, evaluator, scenario_id, question, expected, forbidden):
        """Bilgi soruları parametrik testi"""
        scenario = {
            "id": scenario_id,
            "question": question,
            "expected_keywords": expected,
            "forbidden_keywords": forbidden,
            "description": f"{scenario_id} bilgi testi"
        }
        
        phone = build_test_phone(scenario_id)
        get_bot_response(bot_client, "Merhaba", phone=phone, reset_state=True)
        response = get_bot_response(bot_client, question, phone=phone, reset_state=False)
        if (
            scenario_id == "transfer"
            and "Doğru yönlendirme yapabilmem için lütfen seçin" in (response or "")
        ):
            get_bot_response(bot_client, "2", phone=phone, reset_state=False)
            response = get_bot_response(bot_client, question, phone=phone, reset_state=False)
        result = evaluator.evaluate(response, scenario)
        
        assert result["decision"] in ["PASS", "REVIEW"], \
            f"{scenario_id} testi başarısız. Cevap: {response[:100]}... Eksik: {result['missing_expected']}"


# ======================================================
# SEZON TESTLERİ
# ======================================================

class TestSeasonScenarios:
    """Sezon ile ilgili senaryolar"""
    
    @pytest.mark.golden
    def test_season_info(self, bot_client, evaluator):
        """Sezon bilgisi testi"""
        scenario = {
            "id": "season",
            "question": "Otel ne zaman açık?",
            "expected_keywords": ["Nisan", "Kasım"],
            "forbidden_keywords": ["yıl boyunca", "12 ay"],
            "description": "Sezon 10 Nisan - 10 Kasım"
        }
        
        phone = "905551998877"
        get_bot_response(bot_client, "Merhaba", phone=phone, reset_state=True)
        response = get_bot_response(bot_client, scenario["question"], phone=phone, reset_state=False)
        result = evaluator.evaluate(response, scenario)
        
        assert result["decision"] in ["PASS", "REVIEW"], \
            f"Sezon testi başarısız. Eksik: {result['missing_expected']}"


# ======================================================
# REZERVASYON TESTLERİ
# ======================================================

class TestReservationScenarios:
    """Rezervasyon senaryoları"""
    
    @pytest.mark.golden
    def test_reservation_intent_detection(self, bot_client, evaluator):
        """Rezervasyon niyeti tespiti"""
        scenario = {
            "id": "reservation_intent",
            "question": "Akşam yemeği için rezervasyon yapmak istiyorum",
            "expected_keywords": ["tarih", "saat", "kişi"],
            "forbidden_keywords": [],
            "description": "Rezervasyon için bilgi istemeli"
        }
        
        # Önce selamlama
        get_bot_response(bot_client, "Merhaba", phone="905559999001")
        
        # Sonra rezervasyon talebi
        response = get_bot_response(bot_client, scenario["question"], phone="905559999001", reset_state=False)
        if "Doğru yönlendirme yapabilmem için lütfen seçin" in (response or ""):
            get_bot_response(bot_client, "2", phone="905559999001", reset_state=False)
            response = get_bot_response(bot_client, scenario["question"], phone="905559999001", reset_state=False)
        result = evaluator.evaluate(response, scenario)
        
        # En az bir bilgi sorulmalı
        assert result["score"] >= 0.3, \
            f"Rezervasyon niyeti algılanmadı. Cevap: {response[:150]}"


# ======================================================
# TÜM SENARYOLARI ÇALIŞTIR
# ======================================================

class TestAllCoreScenarios:
    """Tüm core senaryoları çalıştır"""
    
    @pytest.mark.golden
    @pytest.mark.slow
    def test_all_scenarios(self, bot_client, evaluator, core_scenarios):
        """Tüm core senaryoları test et ve rapor oluştur"""
        responses = {}
        
        for scenario in core_scenarios:
            phone = build_test_phone(scenario["id"])
            
            # Her senaryo için temiz konuşma
            _reset_phone_state(phone)
            
            # Selamlama gerekiyorsa önce selamla
            if scenario.get("category") != "selamlama":
                get_bot_response(bot_client, "Merhaba", phone=phone, reset_state=True)
            
            # Soruyu sor
            response = get_bot_response(
                bot_client,
                scenario["question"],
                phone=phone,
                reset_state=(scenario.get("category") == "selamlama"),
            )
            responses[scenario["id"]] = response
        
        # Toplu değerlendirme
        report = evaluator.evaluate_batch(responses, core_scenarios)
        
        # Sonuçları kaydet
        try:
            save_results(report)
        except:
            pass
        
        # Raporu yazdır
        print(evaluator.format_report(report))
        
        # Assertion - %45 eşik (LOCAL_FAQ bazı soruları karşılamayabilir)
        # Bu test OpenAI'a bağlı olduğu için esnek tutulmalı
        assert report["pass_rate"] >= 45, \
            f"Genel başarı oranı %45'in altında: %{report['pass_rate']}"


# ======================================================
# SMOKE SENARYOLARI
# ======================================================

class TestSmokeScenarios:
    """Kritik smoke senaryoları"""

    @pytest.mark.golden
    @pytest.mark.smoke
    @pytest.mark.parametrize(
        "scenario",
        SMOKE_SCENARIOS,
        ids=[s.get("id", "unknown") for s in SMOKE_SCENARIOS],
    )
    def test_smoke_core_scenarios(self, bot_client, evaluator, scenario):
        """Smoke etiketli kritik senaryolar"""
        phone = build_test_phone(scenario["id"])
        menu_prompt = "Size nasıl yardımcı olabilirim?"

        if scenario.get("id") == "transfer_price":
            # transfer smoke: ilk mesajda menü dönmesi zorunlu, sonra 2 ile transfer akışı
            first_response = get_bot_response(bot_client, scenario["question"], phone=phone, reset_state=True)
            assert menu_prompt in first_response, f"İlk mesajda menü bekleniyordu. Cevap: {first_response[:280]}"
            assert "2. Transfer" in first_response or "2) Transfer" in first_response, \
                f"İlk menüde transfer seçeneği bekleniyordu. Cevap: {first_response[:280]}"

            get_bot_response(bot_client, "2", phone=phone, reset_state=False)
            response = get_bot_response(bot_client, scenario["question"], phone=phone, reset_state=False)

            # Bazı akışlarda tekrar menü gelebilir; bir kez daha 2 seçip soruyu yineleriz.
            if menu_prompt in response or "Doğru yönlendirme yapabilmem için lütfen seçin" in response:
                get_bot_response(bot_client, "2", phone=phone, reset_state=False)
                response = get_bot_response(bot_client, "transfer fiyat", phone=phone, reset_state=False)
        elif scenario.get("category") != "selamlama":
            get_bot_response(bot_client, "Merhaba", phone=phone, reset_state=True)
            response = get_bot_response(bot_client, scenario["question"], phone=phone, reset_state=False)
        else:
            response = get_bot_response(bot_client, scenario["question"], phone=phone, reset_state=True)

        result = evaluator.evaluate(response, scenario)

        assert result["decision"] in ["PASS", "REVIEW"], \
            (
                f"Smoke scenario başarısız: {scenario['id']}. "
                f"Eksik: {result['missing_expected']}. "
                f"Cevap: {response[:280]}"
            )


# ======================================================
# EVALUATOR UNIT TESTLERİ
# ======================================================

class TestGoldenEvaluator:
    """Evaluator unit testleri"""
    
    @pytest.mark.unit
    def test_keyword_check_exact(self, evaluator):
        """Tam eşleşme kontrolü"""
        assert evaluator.check_keyword("Kahvaltı 08:00-10:30", "08:00") == True
        assert evaluator.check_keyword("Kahvaltı 08:00-10:30", "07:00") == False
    
    
    @pytest.mark.unit
    def test_keyword_check_alias(self, evaluator):
        """Alias kontrolü"""
        # "var" alias'ları: mevcut, bulunur, evet
        assert evaluator.check_keyword("Havuz mevcuttur", "var") == True
        assert evaluator.check_keyword("Evet, havuzumuz bulunmaktadır", "var") == True
    
    
    @pytest.mark.unit
    def test_keyword_check_case_insensitive(self, evaluator):
        """Büyük/küçük harf duyarsız"""
        assert evaluator.check_keyword("KAHVALTI DAHİL", "dahil") == True
        assert evaluator.check_keyword("WiFi VAR", "wifi") == True
    
    
    @pytest.mark.unit
    def test_evaluate_pass(self, evaluator):
        """PASS değerlendirmesi"""
        scenario = {
            "id": "test",
            "expected_keywords": ["kahvaltı", "08:00", "10:30"],
            "forbidden_keywords": ["07:00"]
        }
        response = "Kahvaltımız 08:00-10:30 saatleri arasındadır."
        
        result = evaluator.evaluate(response, scenario)
        assert result["decision"] == "PASS"
        assert result["score"] == 1.0
    
    
    @pytest.mark.unit
    def test_evaluate_fail_missing(self, evaluator):
        """FAIL - eksik keyword"""
        scenario = {
            "id": "test",
            "expected_keywords": ["14:00", "check-in"],
            "forbidden_keywords": []
        }
        response = "Giriş saatiniz konusunda yardımcı olabilirim."
        
        result = evaluator.evaluate(response, scenario)
        assert result["decision"] == "FAIL"
        assert "14:00" in result["missing_expected"]
    
    
    @pytest.mark.unit
    def test_evaluate_fail_forbidden(self, evaluator):
        """FAIL - yasak keyword bulundu"""
        scenario = {
            "id": "test",
            "expected_keywords": ["havuz", "var"],
            "forbidden_keywords": ["yok", "kapalı"]
        }
        response = "Maalesef havuzumuz şu anda kapalı."
        
        result = evaluator.evaluate(response, scenario)
        assert result["decision"] == "FAIL"
        assert "kapalı" in result["found_forbidden"]
