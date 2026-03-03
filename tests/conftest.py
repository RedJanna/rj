"""
Pytest Fixtures - Tüm testler için ortak yapılandırma

Bu dosya:
- Test veritabanı yönetimi
- Mock OpenAI client
- FastAPI test client
- Ortak yardımcı fonksiyonlar
"""

import os
import sys
import json
import pytest
import sqlite3
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
from typing import Generator, Dict, Any

import fastapi.testclient as fastapi_testclient
import starlette.testclient as starlette_testclient
import fastapi.concurrency as fastapi_concurrency
import fastapi.dependencies.utils as fastapi_dependency_utils
import fastapi.routing as fastapi_routing
import starlette.concurrency as starlette_concurrency

from tests.asgi_testclient_compat import TestClientCompat

# Proje kökünü Python path'e ekle
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Test ortamı değişkenleri
os.environ.setdefault("OPENAI_API_KEY", "test-key-not-real")
os.environ.setdefault("WHATSAPP_PHONE_ID", "test-phone-id")
os.environ.setdefault("WHATSAPP_TOKEN", "test-token")
os.environ.setdefault("KASSANDRA_ENV", "test")

# Compatibility patch: Starlette/FastAPI TestClient can block in this runtime.
fastapi_testclient.TestClient = TestClientCompat
starlette_testclient.TestClient = TestClientCompat


async def _run_in_threadpool_compat(func, *args, **kwargs):
    # CI/runtime bug workaround: anyio threadpool path can block indefinitely.
    # Test suite uses lightweight sync callables; running inline is safe here.
    return func(*args, **kwargs)


starlette_concurrency.run_in_threadpool = _run_in_threadpool_compat
fastapi_concurrency.run_in_threadpool = _run_in_threadpool_compat
fastapi_dependency_utils.run_in_threadpool = _run_in_threadpool_compat
fastapi_routing.run_in_threadpool = _run_in_threadpool_compat


# ======================================================
# PYTEST HOOKS
# ======================================================

def pytest_addoption(parser):
    """Pytest CLI opsiyonları"""
    parser.addoption(
        "--smoke",
        action="store_true",
        default=False,
        help="Sadece smoke işaretli testleri çalıştır"
    )


def pytest_collection_modifyitems(config, items):
    """--smoke verildiğinde smoke dışı testleri atla"""
    if not config.getoption("--smoke"):
        return

    skip_non_smoke = pytest.mark.skip(reason="Skipped by --smoke")
    for item in items:
        if "smoke" not in item.keywords:
            item.add_marker(skip_non_smoke)


# ======================================================
# DOSYA YOLLARI
# ======================================================

TEST_DATA_DIR = PROJECT_ROOT / "tests" / "reports"
TEST_DB_PATH = TEST_DATA_DIR / "test_reservations.db"
TEST_RESULTS_DB = TEST_DATA_DIR / "results.db"
TEST_FLOWS_FILE = TEST_DATA_DIR / "test_reservation_flows.json"


# ======================================================
# DATABASE FIXTURES
# ======================================================

@pytest.fixture(scope="session", autouse=True)
def setup_test_directories():
    """Test dizinlerini oluştur"""
    TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)
    yield
    # Cleanup sonrası (opsiyonel)


@pytest.fixture(scope="function")
def test_db() -> Generator[Path, None, None]:
    """
    Her test için temiz bir veritabanı oluşturur.
    Test bitince siler.
    """
    # Varsa eski DB'yi sil
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    
    # Yeni DB oluştur
    conn = sqlite3.connect(str(TEST_DB_PATH))
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT UNIQUE,
            meal_type TEXT,
            reservation_date TEXT,
            reservation_time TEXT,
            guest_count INTEGER,
            name TEXT,
            special_requests TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()
    
    yield TEST_DB_PATH
    
    # Cleanup
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.fixture(scope="function")
def test_flows_file() -> Generator[Path, None, None]:
    """
    Her test için temiz bir reservation flows dosyası.
    """
    if TEST_FLOWS_FILE.exists():
        TEST_FLOWS_FILE.unlink()
    
    # Boş JSON oluştur
    TEST_FLOWS_FILE.write_text("{}", encoding="utf-8")
    
    yield TEST_FLOWS_FILE
    
    # Cleanup
    if TEST_FLOWS_FILE.exists():
        TEST_FLOWS_FILE.unlink()


# ======================================================
# MOCK FIXTURES
# ======================================================

@pytest.fixture
def mock_openai_client():
    """
    OpenAI API mock'u - Unit testler için.
    Gerçek API çağrısı yapmaz.
    """
    mock_client = Mock()
    
    # chat.completions.create mock'u
    mock_completion = Mock()
    mock_completion.choices = [
        Mock(message=Mock(content="Bu bir test cevabıdır."))
    ]
    mock_client.chat.completions.create.return_value = mock_completion
    
    return mock_client


@pytest.fixture
def mock_openai_response():
    """Özelleştirilebilir OpenAI response factory"""
    def _create_response(content: str):
        mock_completion = Mock()
        mock_completion.choices = [
            Mock(message=Mock(content=content))
        ]
        return mock_completion
    return _create_response


@pytest.fixture
def mock_whatsapp_send():
    """WhatsApp mesaj gönderimi mock'u"""
    async def _mock_send(phone: str, message: str) -> bool:
        return True
    return AsyncMock(side_effect=_mock_send)


# ======================================================
# FASTAPI TEST CLIENT
# ======================================================

@pytest.fixture(scope="module")
def test_client():
    """
    FastAPI test client - Integration testler için.
    """
    # Bot import'u burada yapılır (side effects önlenir)
    from fastapi.testclient import TestClient
    
    # Mock'ları uygula
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "test-key",
        "WHATSAPP_PHONE_ID": "test-phone",
        "WHATSAPP_TOKEN": "test-token"
    }):
        # Bot modülünü import et
        import kassandra_openai_bot as bot
        
        # WhatsApp gönderimini devre dışı bırak
        bot.send_whatsapp_message = AsyncMock(return_value=True)
        
        # QA thread'i devre dışı bırak
        if hasattr(bot, 'QA_ENABLED'):
            bot.QA_ENABLED = False
        
        client = TestClient(bot.app)
        yield client


# ======================================================
# TEST DATA FIXTURES
# ======================================================

@pytest.fixture
def sample_reservation_data() -> Dict[str, Any]:
    """Örnek rezervasyon verisi"""
    return {
        "guest_count": 4,
        "date": "2026-05-15",
        "time": "19:30",
        "name": "Test Müşteri",
        "meal_type": "dinner",
        "special_requests": None
    }


@pytest.fixture
def sample_phone() -> str:
    """Test telefon numarası"""
    return "905001234567"


@pytest.fixture
def golden_scenarios() -> list:
    """Golden test senaryoları"""
    scenarios_file = PROJECT_ROOT / "tests" / "golden" / "scenarios" / "core_scenarios.json"
    if scenarios_file.exists():
        return json.loads(scenarios_file.read_text(encoding="utf-8"))
    return []


# ======================================================
# HELPER FUNCTIONS
# ======================================================

def create_test_reservation(db_path: Path, data: Dict[str, Any]) -> int:
    """Test için rezervasyon oluşturur, ID döner"""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO reservations 
        (conversation_id, meal_type, reservation_date, reservation_time, 
         guest_count, name, special_requests, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("conversation_id", f"test_{datetime.now().timestamp()}"),
        data.get("meal_type", "dinner"),
        data.get("date", "2026-05-15"),
        data.get("time", "19:30"),
        data.get("guest_count", 2),
        data.get("name", "Test"),
        data.get("special_requests"),
        data.get("status", "pending")
    ))
    
    reservation_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return reservation_id


def assert_keywords_in_response(response: str, expected: list, forbidden: list = None) -> Dict[str, Any]:
    """
    Golden test değerlendirmesi.
    
    Returns:
        {
            "passed": bool,
            "found": list,
            "missing": list,
            "forbidden_found": list,
            "score": float
        }
    """
    response_lower = response.lower()
    
    found = [kw for kw in expected if kw.lower() in response_lower]
    missing = [kw for kw in expected if kw.lower() not in response_lower]
    forbidden_found = []
    
    if forbidden:
        forbidden_found = [kw for kw in forbidden if kw.lower() in response_lower]
    
    score = len(found) / len(expected) if expected else 1.0
    passed = score >= 0.7 and len(forbidden_found) == 0
    
    return {
        "passed": passed,
        "found": found,
        "missing": missing,
        "forbidden_found": forbidden_found,
        "score": round(score, 2)
    }


# ======================================================
# TEST RESULT RECORDING
# ======================================================

@pytest.fixture(scope="session")
def test_results_recorder():
    """Test sonuçlarını SQLite'a kaydeder"""
    
    class ResultsRecorder:
        def __init__(self):
            self.db_path = TEST_RESULTS_DB
            self._init_db()
        
        def _init_db(self):
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS test_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    timestamp TEXT,
                    total INTEGER,
                    passed INTEGER,
                    failed INTEGER,
                    skipped INTEGER,
                    duration REAL,
                    report_json TEXT
                )
            """)
            conn.commit()
            conn.close()
        
        def record(self, results: Dict[str, Any]):
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO test_runs 
                (run_id, timestamp, total, passed, failed, skipped, duration, report_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                results.get("run_id", datetime.now().isoformat()),
                datetime.now().isoformat(),
                results.get("total", 0),
                results.get("passed", 0),
                results.get("failed", 0),
                results.get("skipped", 0),
                results.get("duration", 0.0),
                json.dumps(results, ensure_ascii=False)
            ))
            conn.commit()
            conn.close()
    
    return ResultsRecorder()
