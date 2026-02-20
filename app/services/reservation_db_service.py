"""
Reservation DB Service - Rezervasyon Veritabanı İşlemleri

Bu modül kassandra_openai_bot.py'den ayrıştırılmıştır.
Kaynak: kassandra_openai_bot.py satır 890-1106

SQLite veritabanı üzerinden rezervasyon CRUD işlemleri.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict


# ======================================================
# DOSYA YOLLARI
# ======================================================

RESERVATIONS_DB = Path("C:/KassandraOpenAI/data/reservations.db")
RESERVATION_FLOW_FILE = Path("C:/KassandraOpenAI/data/reservation_flows.json")


# ======================================================
# ENUM TANIMLARI
# ======================================================

class ReservationState(Enum):
    """Rezervasyon akış durumları"""
    IDLE = "idle"
    ASK_GUESTS = "ask_guests"
    ASK_DATE = "ask_date"
    ASK_TIME = "ask_time"
    ASK_NAME = "ask_name"
    ASK_SPECIAL = "ask_special"
    CONFIRM = "confirm"
    COMPLETED = "completed"


class ReservationStatus(Enum):
    """Rezervasyon durumları"""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


# ======================================================
# VERİTABANI BAŞLATMA
# ======================================================

def init_reservations_db():
    """Rezervasyon veritabanını başlat"""
    RESERVATIONS_DB.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(RESERVATIONS_DB))
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_phone TEXT NOT NULL,
            customer_name TEXT NOT NULL,
            meal_type TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            guest_count INTEGER NOT NULL,
            special_requests TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL,
            updated_at TEXT,
            notes TEXT,
            noshow_check_sent INTEGER DEFAULT 0
        )
    ''')
    
    conn.commit()
    conn.close()


# Veritabanını başlat
init_reservations_db()


# ======================================================
# REZERVASYON AKIŞ YÖNETİMİ (kassandra_openai_bot.py satır 890-990)
# ======================================================

def load_reservation_flows() -> dict:
    """Rezervasyon akış durumlarını yükle"""
    if RESERVATION_FLOW_FILE.exists():
        try:
            with open(RESERVATION_FLOW_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}


def save_reservation_flows(flows: dict):
    """Rezervasyon akış durumlarını kaydet"""
    RESERVATION_FLOW_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(RESERVATION_FLOW_FILE, 'w', encoding='utf-8') as f:
        json.dump(flows, f, indent=2, ensure_ascii=False)


def get_reservation_flow(phone: str) -> dict:
    """Bir müşterinin rezervasyon akış durumunu getir"""
    flows = load_reservation_flows()
    return flows.get(phone, {
        "state": ReservationState.IDLE.value,
        "data": {},
        "started_at": None
    })


def update_reservation_flow(phone: str, state: str, data: dict = None):
    """Rezervasyon akış durumunu güncelle"""
    flows = load_reservation_flows()
    now = datetime.now().isoformat()
    
    if phone not in flows:
        flows[phone] = {
            "state": state,
            "data": data or {},
            "started_at": now,
            "last_activity_at": now,
            "reminder_sent": False
        }
    else:
        flows[phone]["state"] = state
        flows[phone]["last_activity_at"] = now
        if data:
            flows[phone]["data"].update(data)
    save_reservation_flows(flows)


def clear_reservation_flow(phone: str):
    """Rezervasyon akışını temizle"""
    flows = load_reservation_flows()
    if phone in flows:
        del flows[phone]
        save_reservation_flows(flows)


def cleanup_stale_reservation_flows(max_age_hours: int = 1):
    """
    Eski (stale) rezervasyon akışlarını temizle.
    Varsayılan: 1 saatten eski akışlar silinir.
    """
    try:
        flows = load_reservation_flows()
        if not flows:
            return
        
        now = datetime.now()
        stale_phones = []
        
        for phone, flow in flows.items():
            started_at = flow.get("started_at")
            if started_at:
                try:
                    start_time = datetime.fromisoformat(started_at)
                    age_hours = (now - start_time).total_seconds() / 3600
                    if age_hours > max_age_hours:
                        stale_phones.append(phone)
                except:
                    stale_phones.append(phone)
        
        if stale_phones:
            for phone in stale_phones:
                del flows[phone]
            save_reservation_flows(flows)
            print(f"🧹 {len(stale_phones)} stale rezervasyon akışı temizlendi")
            
    except Exception as e:
        print(f"❌ Stale flow temizleme hatası: {e}")


# ======================================================
# REZERVASYON CRUD İŞLEMLERİ (kassandra_openai_bot.py satır 993-1106)
# ======================================================

def create_reservation(
    phone: str, 
    name: str, 
    meal_type: str, 
    date: str,
    time: str, 
    guest_count: int, 
    special_requests: str = ""
) -> int:
    """
    Yeni rezervasyon oluştur.
    Returns: reservation_id
    """
    conn = sqlite3.connect(str(RESERVATIONS_DB))
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO reservations 
        (customer_phone, customer_name, meal_type, date, time, guest_count, special_requests, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (phone, name, meal_type, date, time, guest_count, special_requests, datetime.now().isoformat()))
    
    reservation_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return reservation_id


def get_reservation(reservation_id: int) -> Optional[dict]:
    """Rezervasyon detayını getir"""
    conn = sqlite3.connect(str(RESERVATIONS_DB))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM reservations WHERE id = ?', (reservation_id,))
    row = cursor.fetchone()
    conn.close()
    
    return dict(row) if row else None


def get_reservations_by_date(date: str) -> List[dict]:
    """Belirli tarihteki rezervasyonları getir"""
    conn = sqlite3.connect(str(RESERVATIONS_DB))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM reservations 
        WHERE date = ? AND status NOT IN ('cancelled')
        ORDER BY time
    ''', (date,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def get_todays_reservations() -> List[dict]:
    """Bugünün rezervasyonlarını getir"""
    today = datetime.now().strftime("%Y-%m-%d")
    return get_reservations_by_date(today)


def get_upcoming_reservations(days: int = 7) -> List[dict]:
    """Gelecek X gündeki rezervasyonları getir"""
    conn = sqlite3.connect(str(RESERVATIONS_DB))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    today = datetime.now().strftime("%Y-%m-%d")
    future = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    
    cursor.execute('''
        SELECT * FROM reservations 
        WHERE date >= ? AND date <= ? AND status NOT IN ('cancelled', 'no_show')
        ORDER BY date, time
    ''', (today, future))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def update_reservation_status(reservation_id: int, status: str, notes: str = None):
    """Rezervasyon durumunu güncelle"""
    conn = sqlite3.connect(str(RESERVATIONS_DB))
    cursor = conn.cursor()
    
    if notes:
        cursor.execute('''
            UPDATE reservations 
            SET status = ?, updated_at = ?, notes = ?
            WHERE id = ?
        ''', (status, datetime.now().isoformat(), notes, reservation_id))
    else:
        cursor.execute('''
            UPDATE reservations 
            SET status = ?, updated_at = ?
            WHERE id = ?
        ''', (status, datetime.now().isoformat(), reservation_id))
    
    conn.commit()
    conn.close()


def cancel_reservation(reservation_id: int, reason: str = ""):
    """Rezervasyonu iptal et"""
    update_reservation_status(reservation_id, ReservationStatus.CANCELLED.value, reason)


def complete_reservation(reservation_id: int):
    """Rezervasyonu tamamlandı olarak işaretle"""
    update_reservation_status(reservation_id, ReservationStatus.COMPLETED.value)


def mark_no_show(reservation_id: int):
    """Müşteri gelmedi olarak işaretle"""
    update_reservation_status(reservation_id, ReservationStatus.NO_SHOW.value)


def confirm_reservation(reservation_id: int):
    """Rezervasyonu onayla"""
    update_reservation_status(reservation_id, ReservationStatus.CONFIRMED.value)


def get_customer_reservations(phone: str) -> List[dict]:
    """Müşterinin tüm rezervasyonlarını getir"""
    conn = sqlite3.connect(str(RESERVATIONS_DB))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM reservations 
        WHERE customer_phone = ?
        ORDER BY date DESC, time DESC
    ''', (phone,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def get_reservations_by_status(status: str) -> List[dict]:
    """Belirli durumdaki rezervasyonları getir"""
    conn = sqlite3.connect(str(RESERVATIONS_DB))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM reservations 
        WHERE status = ?
        ORDER BY date, time
    ''', (status,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def mark_noshow_check_sent(reservation_id: int):
    """No-show kontrol mesajı gönderildi olarak işaretle"""
    conn = sqlite3.connect(str(RESERVATIONS_DB))
    cursor = conn.cursor()
    cursor.execute('UPDATE reservations SET noshow_check_sent = 1 WHERE id = ?', (reservation_id,))
    conn.commit()
    conn.close()


def get_reservation_stats(days: int = 7) -> dict:
    """Rezervasyon istatistiklerini getir"""
    conn = sqlite3.connect(str(RESERVATIONS_DB))
    cursor = conn.cursor()
    
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    # Toplam
    cursor.execute('''
        SELECT COUNT(*) FROM reservations WHERE date >= ?
    ''', (start_date,))
    total = cursor.fetchone()[0]
    
    # Duruma göre
    cursor.execute('''
        SELECT status, COUNT(*) FROM reservations 
        WHERE date >= ?
        GROUP BY status
    ''', (start_date,))
    by_status = dict(cursor.fetchall())
    
    # Öğüne göre
    cursor.execute('''
        SELECT meal_type, COUNT(*) FROM reservations 
        WHERE date >= ?
        GROUP BY meal_type
    ''', (start_date,))
    by_meal = dict(cursor.fetchall())
    
    conn.close()
    
    return {
        "period_days": days,
        "total": total,
        "by_status": by_status,
        "by_meal_type": by_meal
    }


# ======================================================
# SINGLETON SERVICE
# ======================================================

class ReservationDBService:
    """Rezervasyon veritabanı servisi"""
    
    def __init__(self, db_path: Path = None):
        global RESERVATIONS_DB
        if db_path:
            RESERVATIONS_DB = db_path
        init_reservations_db()
    
    # CRUD metodları
    def create(self, *args, **kwargs) -> int:
        return create_reservation(*args, **kwargs)
    
    def get(self, reservation_id: int) -> Optional[dict]:
        return get_reservation(reservation_id)
    
    def update_status(self, reservation_id: int, status: str, notes: str = None):
        update_reservation_status(reservation_id, status, notes)
    
    def cancel(self, reservation_id: int, reason: str = ""):
        cancel_reservation(reservation_id, reason)
    
    # Query metodları
    def get_by_date(self, date: str) -> List[dict]:
        return get_reservations_by_date(date)
    
    def get_today(self) -> List[dict]:
        return get_todays_reservations()
    
    def get_upcoming(self, days: int = 7) -> List[dict]:
        return get_upcoming_reservations(days)
    
    def get_by_customer(self, phone: str) -> List[dict]:
        return get_customer_reservations(phone)
    
    def get_stats(self, days: int = 7) -> dict:
        return get_reservation_stats(days)
    
    # Flow yönetimi
    def get_flow(self, phone: str) -> dict:
        return get_reservation_flow(phone)
    
    def update_flow(self, phone: str, state: str, data: dict = None):
        update_reservation_flow(phone, state, data)
    
    def clear_flow(self, phone: str):
        clear_reservation_flow(phone)
    
    def cleanup_stale_flows(self, max_age_hours: int = 1):
        cleanup_stale_reservation_flows(max_age_hours)


_reservation_db_service: Optional[ReservationDBService] = None

def get_reservation_db_service() -> ReservationDBService:
    """Singleton reservation DB service döndür"""
    global _reservation_db_service
    if _reservation_db_service is None:
        _reservation_db_service = ReservationDBService()
    return _reservation_db_service
