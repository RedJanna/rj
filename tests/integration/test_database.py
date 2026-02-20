"""
Integration Tests: Database Operations
======================================

SQLite veritabanı CRUD testleri.

Kapsam:
- Rezervasyon oluşturma
- Rezervasyon okuma
- Rezervasyon güncelleme
- Rezervasyon silme/iptal
"""

import pytest
import sys
import sqlite3
from pathlib import Path
from datetime import datetime

# Proje kökünü ekle
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ======================================================
# FIXTURES
# ======================================================

@pytest.fixture
def test_db(tmp_path):
    """Geçici test veritabanı"""
    db_path = tmp_path / "test_reservations.db"
    
    conn = sqlite3.connect(str(db_path))
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
    
    return db_path


@pytest.fixture
def db_connection(test_db):
    """Veritabanı bağlantısı"""
    conn = sqlite3.connect(str(test_db))
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


# ======================================================
# CRUD TESTLERİ
# ======================================================

class TestReservationCRUD:
    """Rezervasyon CRUD testleri"""
    
    @pytest.mark.integration
    def test_create_reservation(self, db_connection):
        """Rezervasyon oluşturma"""
        cursor = db_connection.cursor()
        
        cursor.execute("""
            INSERT INTO reservations 
            (conversation_id, meal_type, reservation_date, reservation_time, 
             guest_count, name, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            "test_conv_001",
            "dinner",
            "2026-05-15",
            "19:30",
            4,
            "Test Müşteri",
            "pending"
        ))
        
        db_connection.commit()
        
        # Verify
        cursor.execute("SELECT * FROM reservations WHERE conversation_id = ?", 
                      ("test_conv_001",))
        row = cursor.fetchone()
        
        assert row is not None
        assert row["name"] == "Test Müşteri"
        assert row["guest_count"] == 4
        assert row["status"] == "pending"
    
    
    @pytest.mark.integration
    def test_read_reservation(self, db_connection):
        """Rezervasyon okuma"""
        cursor = db_connection.cursor()
        
        # Önce oluştur
        cursor.execute("""
            INSERT INTO reservations 
            (conversation_id, meal_type, reservation_date, reservation_time, 
             guest_count, name, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ("test_conv_002", "lunch", "2026-06-20", "13:00", 2, "Okuma Testi", "confirmed"))
        db_connection.commit()
        
        # Oku
        cursor.execute("SELECT * FROM reservations WHERE conversation_id = ?",
                      ("test_conv_002",))
        row = cursor.fetchone()
        
        assert row is not None
        assert row["meal_type"] == "lunch"
        assert row["reservation_date"] == "2026-06-20"
    
    
    @pytest.mark.integration
    def test_update_reservation_status(self, db_connection):
        """Rezervasyon durumu güncelleme"""
        cursor = db_connection.cursor()
        
        # Oluştur
        cursor.execute("""
            INSERT INTO reservations 
            (conversation_id, meal_type, reservation_date, reservation_time, 
             guest_count, name, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ("test_conv_003", "dinner", "2026-07-10", "20:00", 3, "Güncelleme Testi", "pending"))
        db_connection.commit()
        
        # Güncelle
        cursor.execute("""
            UPDATE reservations SET status = ? WHERE conversation_id = ?
        """, ("confirmed", "test_conv_003"))
        db_connection.commit()
        
        # Verify
        cursor.execute("SELECT status FROM reservations WHERE conversation_id = ?",
                      ("test_conv_003",))
        row = cursor.fetchone()
        
        assert row["status"] == "confirmed"
    
    
    @pytest.mark.integration
    def test_cancel_reservation(self, db_connection):
        """Rezervasyon iptal"""
        cursor = db_connection.cursor()
        
        # Oluştur
        cursor.execute("""
            INSERT INTO reservations 
            (conversation_id, meal_type, reservation_date, reservation_time, 
             guest_count, name, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ("test_conv_004", "breakfast", "2026-08-01", "09:00", 2, "İptal Testi", "confirmed"))
        db_connection.commit()
        
        # İptal et
        cursor.execute("""
            UPDATE reservations SET status = ? WHERE conversation_id = ?
        """, ("cancelled", "test_conv_004"))
        db_connection.commit()
        
        # Verify
        cursor.execute("SELECT status FROM reservations WHERE conversation_id = ?",
                      ("test_conv_004",))
        row = cursor.fetchone()
        
        assert row["status"] == "cancelled"
    
    
    @pytest.mark.integration
    def test_get_reservations_by_date(self, db_connection):
        """Tarihe göre rezervasyon listesi"""
        cursor = db_connection.cursor()
        
        # Birden fazla rezervasyon oluştur
        reservations = [
            ("conv_date_001", "dinner", "2026-09-15", "19:00", 2, "Müşteri 1", "confirmed"),
            ("conv_date_002", "dinner", "2026-09-15", "20:00", 4, "Müşteri 2", "confirmed"),
            ("conv_date_003", "dinner", "2026-09-16", "19:30", 3, "Müşteri 3", "confirmed"),
        ]
        
        cursor.executemany("""
            INSERT INTO reservations 
            (conversation_id, meal_type, reservation_date, reservation_time, 
             guest_count, name, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, reservations)
        db_connection.commit()
        
        # 15 Eylül rezervasyonlarını getir
        cursor.execute("""
            SELECT * FROM reservations 
            WHERE reservation_date = ? AND status != 'cancelled'
            ORDER BY reservation_time
        """, ("2026-09-15",))
        
        rows = cursor.fetchall()
        
        assert len(rows) == 2
        assert rows[0]["name"] == "Müşteri 1"
        assert rows[1]["name"] == "Müşteri 2"
    
    
    @pytest.mark.integration
    def test_unique_conversation_id(self, db_connection):
        """conversation_id unique olmalı"""
        cursor = db_connection.cursor()
        
        # İlk kayıt
        cursor.execute("""
            INSERT INTO reservations 
            (conversation_id, meal_type, reservation_date, reservation_time, 
             guest_count, name, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ("unique_conv_001", "dinner", "2026-10-01", "19:00", 2, "Test", "pending"))
        db_connection.commit()
        
        # Aynı conversation_id ile tekrar - UNIQUE constraint hatası vermeli
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO reservations 
                (conversation_id, meal_type, reservation_date, reservation_time, 
                 guest_count, name, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, ("unique_conv_001", "lunch", "2026-10-02", "13:00", 3, "Test2", "pending"))
            db_connection.commit()


# ======================================================
# RESERVATION FLOW TESTLERİ
# ======================================================

class TestReservationFlowPersistence:
    """Rezervasyon akış verisi testleri"""
    
    @pytest.mark.integration
    def test_flow_file_operations(self, tmp_path):
        """Flow dosyası okuma/yazma"""
        import json
        
        flow_file = tmp_path / "test_flows.json"
        
        # Yaz
        flow_data = {
            "905551234567": {
                "state": "ask_guests",
                "data": {"date": "2026-05-15"},
                "updated_at": datetime.now().isoformat()
            }
        }
        
        flow_file.write_text(json.dumps(flow_data, ensure_ascii=False), encoding="utf-8")
        
        # Oku
        loaded = json.loads(flow_file.read_text(encoding="utf-8"))
        
        assert "905551234567" in loaded
        assert loaded["905551234567"]["state"] == "ask_guests"
        assert loaded["905551234567"]["data"]["date"] == "2026-05-15"