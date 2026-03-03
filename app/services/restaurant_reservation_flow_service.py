"""
Restaurant Reservation Flow Service - Restoran Rezervasyon Akış Sistemi

Bu modül kassandra_openai_bot.py'den ayrıştırılmıştır.
Kaynak: kassandra_openai_bot.py satır 890-1802

Restoran rezervasyon akışını, CRUD operasyonlarını ve bildirimleri yönetir.

v2.0 - Akıllı Bilgi Çıkarma: Tek mesajdan tüm rezervasyon bilgilerini çıkarır
"""

from __future__ import annotations

import re
import json
import sqlite3
from app.services.datetime_parser import extract_time_from_text
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Tuple, Optional, List, Dict
from enum import Enum

from app.flows.flow_contract import FlowContext, FlowResult
from app.services.state_store_service import JsonStateRepository, resolve_data_file

# ======================================================
# ENUM'LAR
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


class ReservationStatus(Enum):
    """Rezervasyon durumları"""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"
    COMPLETED = "completed"


# ======================================================
# DOSYA YOLLARI
# ======================================================

RESERVATIONS_DB = resolve_data_file("reservations.db", env_var="KASSANDRA_RESERVATIONS_DB")
RESERVATION_FLOW_FILE = resolve_data_file("reservation_flows.json", env_var="KASSANDRA_RESERVATION_FLOW_FILE")
_RESERVATION_FLOW_STORE = JsonStateRepository(RESERVATION_FLOW_FILE)


# ======================================================
# RESTORAN AYARLARI
# ======================================================

RESTAURANT_SETTINGS = {
    "name": "Kassandra Ölüdeniz Restoran",
    "season_start_month": 4,
    "season_start_day": 10,
    "season_end_month": 11,
    "season_end_day": 10,
    "max_auto_reservation": 9,  # 9 kişiye kadar bot akışı, 10+ canlı destek
    "location_url": "google.com/maps/place//data=!4m2!3m1!1s0x14c04131882c8de9:0x40a2254ec58061ec?sa=X&ved=1t:8290&ictx=111",
    "meal_times": {
        "breakfast": {
            "start": "09:00",
            "end": "11:00",
            "name_tr": "Kahvaltı",
            "name_en": "Breakfast"
        },
        "lunch": {
            "start": "12:00",
            "end": "16:00",
            "name_tr": "Öğle Yemeği",
            "name_en": "Lunch"
        },
        "dinner": {
            "start": "18:00",
            "end": "22:00",
            "name_tr": "Akşam Yemeği",
            "name_en": "Dinner"
        }
    }
}


# ======================================================
# AKIŞ KIRMA KELİMELERİ
# ======================================================

FLOW_BREAK_KEYWORDS = {
    "fiyat": ["fiyat", "price", "kaç para", "ne kadar", "ücret", "tarife"],
    "oda": ["oda", "room", "süit", "suite", "jakuzi", "balkon"],
    "bilgi": ["nerede", "where", "nasıl giderim", "havuz", "plaj", "kahvaltı saati"],
    "iptal": ["iptal", "cancel", "vazgeç", "istemiyorum"]
}


# ======================================================
# 🆕 AKILLI BİLGİ ÇIKARMA SİSTEMİ
# ======================================================

def extract_guest_count(message: str) -> Optional[int]:
    """
    Mesajdan kişi sayısını çıkar.
    Örnekler: "3 kişi", "5 kişilik", "for 4 people", "4 guests"
    """
    msg_lower = message.lower()
    
    # Türkçe kalıplar
    patterns_tr = [
        r'(\d+)\s*kişi',           # 3 kişi, 3kişi
        r'(\d+)\s*kişilik',        # 3 kişilik
        r'(\d+)\s*kisilik',        # 3 kisilik (ı olmadan)
        r'(\d+)\s*misafir',        # 3 misafir
        r'(\d+)\s*yetişkin',       # 3 yetişkin
    ]
    
    # İngilizce kalıplar
    patterns_en = [
        r'(\d+)\s*people',         # 4 people
        r'(\d+)\s*person',         # 1 person
        r'(\d+)\s*guests?',        # 3 guests, 1 guest
        r'for\s*(\d+)',            # for 4
        r'(\d+)\s*adults?',        # 3 adults
    ]
    
    all_patterns = patterns_tr + patterns_en
    
    for pattern in all_patterns:
        match = re.search(pattern, msg_lower)
        if match:
            count = int(match.group(1))
            if 1 <= count <= 50:  # Makul aralık
                return count
    
    # Yazıyla yazılmış sayılar
    word_to_num = {
        "bir": 1, "iki": 2, "üç": 3, "dört": 4, "beş": 5,
        "altı": 6, "yedi": 7, "sekiz": 8, "dokuz": 9, "on": 10,
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10
    }
    
    for word, num in word_to_num.items():
        if word in msg_lower:
            # "iki kişi", "three people" gibi kalıpları kontrol et
            if re.search(rf'{word}\s*(kişi|kisilik|people|person|guests?)', msg_lower):
                return num
    
    return None


def extract_time(message: str) -> Optional[str]:
    return extract_time_from_text(message)
def extract_date(message: str) -> Optional[str]:
    """Mesajdan tarihi çıkar ve YYYY-MM-DD döndür."""
    return parse_date_input(message)


def extract_name(message: str) -> Optional[str]:
    """
    Mesajdan isim çıkarmaya çalışır.
    Testler isim doğrulamıyor; akışı bozmayacak şekilde tasarlanmıştır.
    """
    text = (message or "").strip()
    if not text:
        return None

    patterns = [
        r"(?:adım|ismim)\s*[:\-]?\s*([A-Za-zÇĞİÖŞÜçğıöşü]+(?:\s+[A-Za-zÇĞİÖŞÜçğıöşü]+){0,2})",
        r"(?:isim)\s*[:\-]?\s*([A-Za-zÇĞİÖŞÜçğıöşü]+(?:\s+[A-Za-zÇĞİÖŞÜçğıöşü]+){0,2})",
        r"(?:my name is|name is|i am)\s*[:\-]?\s*([A-Za-z]+(?:\s+[A-Za-z]+){0,2})",
    ]

    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if not m:
            continue
        name = (m.group(1) or "").strip()
        if not name or any(ch.isdigit() for ch in name):
            continue
        bad = {"rezervasyon", "reservation", "yarın", "yarin", "bugün", "bugun", "akşam", "aksam", "today", "tomorrow"}
        if any(w in name.lower() for w in bad):
            continue
        if len(name) > 60:
            continue
        return name

    return None


def extract_all_reservation_info(message: str) -> Dict[str, any]:
    """
    🆕 TEK MESAJDAN TÜM REZERVASYON BİLGİLERİNİ ÇIKAR
    
    Returns:
        {
            "guest_count": int or None,
            "date": str (YYYY-MM-DD) or None,
            "time": str (HH:MM) or None,
            "name": str or None,
            "meal_type": str or None,
            "has_any_info": bool  # Herhangi bir bilgi var mı?
        }
    """
    result = {
        "guest_count": extract_guest_count(message),
        "date": extract_date(message),
        "time": extract_time(message),
        "name": extract_name(message),
        "meal_type": None,
        "has_any_info": False
    }
    
    # Saatten öğün tipini belirle
    if result["time"]:
        result["meal_type"] = get_meal_type_from_time(result["time"])
    
    # Herhangi bir bilgi var mı?
    result["has_any_info"] = any([
        result["guest_count"],
        result["date"],
        result["time"]
    ])
    
    return result


def get_missing_reservation_fields(flow_data: dict, extracted: dict) -> List[str]:
    """
    Eksik alanları belirle.
    flow_data: Mevcut akış verisi
    extracted: Yeni çıkarılan bilgiler
    
    Returns: Eksik alan isimleri listesi
    """
    missing = []
    
    # Kişi sayısı
    if not flow_data.get("guest_count") and not extracted.get("guest_count"):
        missing.append("guest_count")
    
    # Tarih
    if not flow_data.get("date") and not extracted.get("date"):
        missing.append("date")
    
    # Saat
    if not flow_data.get("time") and not extracted.get("time"):
        missing.append("time")
    
    # İsim - en son sorulacak
    if not flow_data.get("name") and not extracted.get("name"):
        missing.append("name")
    
    return missing


def merge_reservation_data(existing: dict, extracted: dict) -> dict:
    """
    Mevcut ve yeni çıkarılan verileri birleştir.
    Yeni veri varsa onu kullan, yoksa eskiyi koru.
    """
    merged = dict(existing)
    
    if extracted.get("guest_count"):
        merged["guest_count"] = extracted["guest_count"]
    
    if extracted.get("date"):
        merged["date"] = extracted["date"]
    
    if extracted.get("time"):
        merged["time"] = extracted["time"]
        # Saatten öğün tipini güncelle
        merged["meal_type"] = get_meal_type_from_time(extracted["time"])
    
    if extracted.get("name"):
        merged["name"] = extracted["name"]
    
    return merged


def determine_next_state(flow_data: dict) -> str:
    """
    Mevcut verilere göre sonraki state'i belirle.
    Eksik bilgiye göre hangi soruyu soracağımızı döndürür.
    """
    if not flow_data.get("guest_count"):
        return ReservationState.ASK_GUESTS.value
    
    if not flow_data.get("date"):
        return ReservationState.ASK_DATE.value
    
    if not flow_data.get("time"):
        return ReservationState.ASK_TIME.value
    
    if not flow_data.get("name"):
        return ReservationState.ASK_NAME.value
    
    # Tüm zorunlu bilgiler tamam - onay aşamasına geç
    return ReservationState.CONFIRM.value


def generate_smart_response(flow_data: dict, extracted: dict, lang: str = "tr") -> Tuple[str, str]:
    """
    🆕 AKILLI CEVAP OLUŞTUR
    
    Eksik bilgilere göre tek bir soru sor.
    Verilen bilgileri onaylayarak devam et.
    
    Returns: (response_message, next_state)
    """
    # Verileri birleştir
    merged = merge_reservation_data(flow_data, extracted)
    
    # Sonraki state'i belirle
    next_state = determine_next_state(merged)
    
    # Onay aşamasına geldiyse
    if next_state == ReservationState.CONFIRM.value:
        formatted_date = format_date_turkish(merged["date"]) if lang == "tr" else format_date_english(merged["date"])
        
        if lang == "tr":
            response = f"""Harika! Rezervasyon bilgilerinizi onaylayalım:

📅 Tarih: {formatted_date}
🕐 Saat: {merged["time"]}
👥 Kişi: {merged["guest_count"]}
👤 İsim: {merged["name"]}

Bu bilgiler doğru mu? (Evet/Hayır)"""
        else:
            response = f"""Great! Let's confirm your reservation:

📅 Date: {formatted_date}
🕐 Time: {merged["time"]}
👥 Guests: {merged["guest_count"]}
👤 Name: {merged["name"]}

Is this correct? (Yes/No)"""
        
        return response, next_state
    
    # Bilgi toplama aşaması - alınan bilgileri onayla ve eksik olanı sor
    acknowledgment_parts = []
    
    if extracted.get("guest_count"):
        if lang == "tr":
            acknowledgment_parts.append(f"{extracted['guest_count']} kişi")
        else:
            acknowledgment_parts.append(f"{extracted['guest_count']} guests")
    
    if extracted.get("date"):
        formatted = format_date_turkish(extracted["date"]) if lang == "tr" else format_date_english(extracted["date"])
        acknowledgment_parts.append(formatted)
    
    if extracted.get("time"):
        acknowledgment_parts.append(extracted["time"])
    
    # Onay mesajı
    if acknowledgment_parts:
        if lang == "tr":
            ack = f"Harika! {', '.join(acknowledgment_parts)} not ettim. "
        else:
            ack = f"Great! Noted: {', '.join(acknowledgment_parts)}. "
    else:
        ack = ""
    
    # Eksik bilgiyi sor
    questions = {
        "tr": {
            ReservationState.ASK_GUESTS.value: "Kaç kişilik rezervasyon yapmak istersiniz?",
            ReservationState.ASK_DATE.value: "Hangi tarih için rezervasyon yapmak istersiniz? (örn: yarın, 15 Temmuz)",
            ReservationState.ASK_TIME.value: "Saat kaç için uygun olur? (örn: 19:00, 20:30)",
            ReservationState.ASK_NAME.value: "Rezervasyon hangi isim adına olsun?",
        },
        "en": {
            ReservationState.ASK_GUESTS.value: "How many guests will there be?",
            ReservationState.ASK_DATE.value: "Which date would you like? (e.g., tomorrow, July 15)",
            ReservationState.ASK_TIME.value: "What time would you prefer? (e.g., 7:00 PM, 8:30 PM)",
            ReservationState.ASK_NAME.value: "What name should the reservation be under?",
        }
    }
    
    question = questions.get(lang, questions["tr"]).get(next_state, "")
    
    return ack + question, next_state


# ======================================================
# AKIŞ KIRICI FONKSİYONLARI
# ======================================================

def should_break_reservation_flow(message: str, current_state: str) -> bool:
    """
    Müşteri rezervasyon akışı dışında bir şey mi soruyor?
    """
    msg_lower = message.lower().strip()
    
    # İptal kelimeleri her zaman akışı kırar
    if any(kw in msg_lower for kw in FLOW_BREAK_KEYWORDS["iptal"]):
        return True
    
    # Onay state'inde sadece evet/hayır bekliyoruz
    if current_state == ReservationState.CONFIRM.value:
        confirm_words = ["evet", "hayır", "yes", "no", "onay", "tamam", "iptal", "ok", "hayir"]
        if not any(w in msg_lower for w in confirm_words):
            return True
    
    # Diğer state'lerde fiyat veya oda sorusu akışı kırar
    if current_state not in [ReservationState.IDLE.value, ReservationState.CONFIRM.value]:
        for category, keywords in FLOW_BREAK_KEYWORDS.items():
            if category in ["fiyat", "oda", "bilgi"]:
                if len(msg_lower.split()) >= 3:
                    if any(kw in msg_lower for kw in keywords):
                        return True
    
    return False


def detect_correction_in_message(message: str, current_state: str) -> dict:
    """
    Müşteri bir düzeltme mi yapıyor?
    """
    msg_lower = message.lower()
    
    correction_indicators = ["pardon", "değil", "yanlış", "düzelt", "aslında", "sorry", "actually"]
    
    if any(ind in msg_lower for ind in correction_indicators):
        numbers = re.findall(r'\d+', message)
        if numbers and current_state in [ReservationState.ASK_DATE.value, ReservationState.ASK_TIME.value]:
            return {
                "is_correction": True,
                "field": "guest_count",
                "new_value": int(numbers[-1])
            }
    
    return {"is_correction": False}


# ======================================================
# REZERVASYON AKIŞ FONKSİYONLARI
# ======================================================

def load_reservation_flows() -> dict:
    """Rezervasyon akış durumlarını yükle"""
    return _RESERVATION_FLOW_STORE.load_dict()


def save_reservation_flows(flows: dict):
    """Rezervasyon akış durumlarını kaydet"""
    _RESERVATION_FLOW_STORE.save_dict(flows if isinstance(flows, dict) else {})


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


def cleanup_stale_reservation_flows(max_age_hours: int = 1) -> int:
    """Eski (stale) rezervasyon akışlarını temizle."""
    try:
        flows = load_reservation_flows()
        if not flows:
            return 0
        
        now = datetime.now()
        cleaned_count = 0
        phones_to_remove = []
        
        for phone, flow in flows.items():
            started_at_str = flow.get("started_at")
            if started_at_str:
                try:
                    started_at = datetime.fromisoformat(started_at_str)
                    age_hours = (now - started_at).total_seconds() / 3600
                    
                    if age_hours > max_age_hours:
                        phones_to_remove.append(phone)
                        cleaned_count += 1
                        print(f"🧹 Stale flow temizlendi: {phone} ({age_hours:.1f} saat eski)")
                except:
                    phones_to_remove.append(phone)
                    cleaned_count += 1
            else:
                phones_to_remove.append(phone)
                cleaned_count += 1
        
        for phone in phones_to_remove:
            del flows[phone]
        
        if cleaned_count > 0:
            save_reservation_flows(flows)
            print(f"✅ Toplam {cleaned_count} stale rezervasyon akışı temizlendi")
        
        return cleaned_count
    except Exception as e:
        print(f"❌ Stale flow temizleme hatası: {e}")
        return 0


# ======================================================
# VERITABANI CRUD İŞLEMLERİ
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
            created_at TEXT,
            updated_at TEXT,
            notes TEXT,
            noshow_check_sent INTEGER DEFAULT 0
        )
    ''')
    
    conn.commit()
    conn.close()


def create_reservation(phone: str, name: str, meal_type: str, date: str, 
                       time: str, guest_count: int, special_requests: str = "",
                       lang: str = "tr") -> dict:
    """
    Yeni rezervasyon oluştur
    
    Returns:
        dict: Oluşturulan rezervasyon bilgileri (id dahil)
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
    
    # Rezervasyon bilgilerini dict olarak döndür
    return {
        "id": reservation_id,
        "customer_phone": phone,
        "customer_name": name,
        "meal_type": meal_type,
        "date": date,
        "time": time,
        "guest_count": guest_count,
        "special_requests": special_requests,
        "lang": lang
    }


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


# ======================================================
# TARİH/SAAT YARDIMCI FONKSİYONLARI
# ======================================================

def validate_reservation_time(time_str: str, meal_type: str) -> Tuple[bool, str]:
    """Rezervasyon saatini doğrula.

    Test uyumu için imza: (time_str, meal_type).
    Geriye dönük uyum: Eğer argümanlar ters geldiyse otomatik swap yapar.

    Hata kodları:
      - INVALID_MEAL_TYPE
      - INVALID_TIME_FORMAT
      - OUT_OF_MEAL_TIME
    """
    # Backward-compat: validate_reservation_time(meal_type, time_str) çağrısı varsa
    if time_str in RESTAURANT_SETTINGS.get("meal_times", {}) and re.match(r"^\d{1,2}:\d{2}$", str(meal_type)):
        time_str, meal_type = meal_type, time_str

    meal_settings = RESTAURANT_SETTINGS["meal_times"].get(meal_type)
    if not meal_settings:
        return False, "INVALID_MEAL_TYPE"

    try:
        req_time = datetime.strptime(time_str, "%H:%M").time()
        start_time = datetime.strptime(meal_settings["start"], "%H:%M").time()
        end_time = datetime.strptime(meal_settings["end"], "%H:%M").time()

        if req_time < start_time or req_time > end_time:
            return False, "OUT_OF_MEAL_TIME"

        return True, ""
    except Exception:
        return False, "INVALID_TIME_FORMAT"

    try:
        req_time = datetime.strptime(time_str, "%H:%M").time()
        start_time = datetime.strptime(meal_settings["start"], "%H:%M").time()
        end_time = datetime.strptime(meal_settings["end"], "%H:%M").time()

        if req_time < start_time or req_time > end_time:
            return False, "OUT_OF_MEAL_TIME"

        return True, ""
    except Exception:
        return False, "INVALID_TIME_FORMAT"


def get_meal_type_from_time(time_str: str) -> Optional[str]:
    """Saate göre öğün tipini belirle"""
    try:
        req_time = datetime.strptime(time_str, "%H:%M").time()
        
        for meal_type, settings in RESTAURANT_SETTINGS["meal_times"].items():
            start = datetime.strptime(settings["start"], "%H:%M").time()
            end = datetime.strptime(settings["end"], "%H:%M").time()
            if start <= req_time <= end:
                return meal_type
        
        return None
    except:
        return None


def parse_date_input(date_text: str) -> Optional[str]:
    """Tarih girişini parse et ve YYYY-MM-DD formatına çevir.

    Mesaj içinde geçer ("3 kişi için 15 Mayıs" gibi).
    """
    date_text = (date_text or "").lower().strip()
    if not date_text:
        return None

    today = datetime.now()

    # hızlı anahtar kelimeler
    if any(w in date_text for w in ["bugun", "bugün", "today"]):
        return today.strftime("%Y-%m-%d")
    if any(w in date_text for w in ["yarin", "yarın", "tomorrow"]):
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")

    # hafta sonu
    if "hafta sonu" in date_text or "weekend" in date_text:
        days_until_saturday = (5 - today.weekday()) % 7
        if days_until_saturday == 0:
            days_until_saturday = 7
        return (today + timedelta(days=days_until_saturday)).strftime("%Y-%m-%d")

    # kişi sayısı ifadelerini temizle (tarih yakalamayı bozmasın)
    cleaned = re.sub(r"\b\d+\s*(kişi|kisi|kişilik|kisilik|people|persons?|guests?|adults?)\b", " ", date_text)

    # gün adları
    days_tr = ["pazartesi", "salı", "çarşamba", "perşembe", "cuma", "cumartesi", "pazar"]
    days_en = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

    for i, day in enumerate(days_tr + days_en):
        if day in cleaned:
            target_day = i % 7
            current_day = today.weekday()
            days_ahead = target_day - current_day
            if days_ahead <= 0:
                days_ahead += 7
            if any(w in cleaned for w in ["haftaya", "gelecek hafta", "önümüzdeki hafta", "next week"]):
                days_ahead += 7
            return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    # ay isimleri
    months_tr = {
        "ocak": 1, "şubat": 2, "mart": 3, "nisan": 4, "mayıs": 5, "haziran": 6,
        "temmuz": 7, "ağustos": 8, "eylül": 9, "ekim": 10, "kasım": 11, "aralık": 12
    }
    months_en = {
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12
    }

    all_months = {**months_tr, **months_en}
    for month_name, month_num in all_months.items():
        if month_name not in cleaned:
            continue

        patterns = [
            rf"(\d{{1,2}})\s*{month_name}",  # 15 Mayıs / 15 June
            rf"{month_name}\s*(\d{{1,2}})",  # Mayıs 15 / June 15
        ]

        day = None
        for pat in patterns:
            m = re.search(pat, cleaned)
            if m:
                day = int(m.group(1))
                break

        if day is not None and 1 <= day <= 31:
            year = today.year
            if (month_num, day) < (today.month, today.day):
                year += 1
            try:
                return datetime(year, month_num, day).strftime("%Y-%m-%d")
            except Exception:
                pass

    # sayısal formatlar: 15/05, 15.05, 15/05/2026, 15.05.2026
    m = re.search(r"\b(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?\b", cleaned)
    if m:
        day = int(m.group(1))
        month = int(m.group(2))
        year_raw = m.group(3)

        if year_raw:
            year = int(year_raw)
            if year < 100:
                year += 2000
        else:
            year = today.year
            if (month, day) < (today.month, today.day):
                year += 1

        try:
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except Exception:
            return None

    return None


def format_date_turkish(date_str: str) -> str:
    """Tarihi Türkçe formata çevir: 3 Haziran 2026"""
    months_tr = {
        1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran",
        7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"
    }
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        day = date_obj.day
        month = months_tr[date_obj.month]
        year = date_obj.year
        return f"{day} {month} {year}"
    except:
        return date_str


def format_date_english(date_str: str) -> str:
    """Tarihi İngilizce formata çevir: 3 June 2026"""
    months_en = {
        1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
        7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December"
    }
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        day = date_obj.day
        month = months_en[date_obj.month]
        year = date_obj.year
        return f"{day} {month} {year}"
    except:
        return date_str


def is_within_season(date_str: str, lang: str = "tr") -> Tuple[bool, str]:
    """Tarih sezon içinde mi kontrol et."""
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        month = date_obj.month
        day = date_obj.day
        
        season_start = (RESTAURANT_SETTINGS["season_start_month"], RESTAURANT_SETTINGS["season_start_day"])
        season_end = (RESTAURANT_SETTINGS["season_end_month"], RESTAURANT_SETTINGS["season_end_day"])
        
        if (month, day) < season_start:
            if lang == "en":
                return False, (
                    "Sorry, our restaurant is open only from April 10 to November 10. Please tell me another date and time, and I can help you."
                )
            return False, (
                "Üzgünüz, restoranımız 10 Nisan - 10 Kasım tarihleri arasında hizmet vermektedir."
            )
        
        if (month, day) > season_end:
            if lang == "en":
                return False, (
                    "Sorry, our restaurant is open only from April 10 to November 10. Please tell me another date and time, and I can help you."
                )
            return False, (
                "Üzgünüz, restoranımız 10 Nisan - 10 Kasım tarihleri arasında hizmet vermektedir."
            )
        
        return True, ""
    except:
        return False, "Geçersiz tarih"


# ======================================================
# ONAY MESAJI OLUŞTURMA
# ======================================================

def format_reservation_confirmation(reservation: dict, lang: str = "tr") -> str:
    """Rezervasyon onay mesajını oluştur"""
    meal_names_tr = {
        "breakfast": "Kahvaltı",
        "lunch": "Öğle Yemeği",
        "dinner": "Akşam Yemeği"
    }
    
    meal_names_en = {
        "breakfast": "Breakfast",
        "lunch": "Lunch",
        "dinner": "Dinner"
    }
    
    meal_emojis = {
        "breakfast": "☕",
        "lunch": "🍽️",
        "dinner": "🌙"
    }
    
    meal_type = reservation.get("meal_type", "dinner")
    emoji = meal_emojis.get(meal_type, "🍽️")
    
    if lang == "en":
        meal_name = meal_names_en.get(meal_type, "Meal")
        formatted_date = format_date_english(reservation['date'])
        
        message = f"""✅ Your reservation has been confirmed!

{emoji} {meal_name} Reservation
━━━━━━━━━━━━━━━━━━━━━━━━
📅 Date: {formatted_date}
🕐 Time: {reservation['time']}
👥 Guests: {reservation['guest_count']}
👤 Name: {reservation['customer_name']}"""
        
        if reservation.get('special_requests'):
            message += f"\n📝 Note: {reservation['special_requests']}"
        
        message += f"""

🆔 Reservation No: #{reservation['id']}

📍 Location: {RESTAURANT_SETTINGS['location_url']}

For cancellation or changes, please contact us.
Have a great day! 🙏"""
    else:
        meal_name = meal_names_tr.get(meal_type, "Yemek")
        formatted_date = format_date_turkish(reservation['date'])
        
        message = f"""✅ Rezervasyonunuz başarıyla oluşturuldu!

{emoji} {meal_name} Rezervasyonu
━━━━━━━━━━━━━━━━━━━━━━━━
📅 Tarih: {formatted_date}
🕐 Saat: {reservation['time']}
👥 Kişi: {reservation['guest_count']}
👤 İsim: {reservation['customer_name']}"""
        
        if reservation.get('special_requests'):
            message += f"\n📝 Not: {reservation['special_requests']}"
        
        message += f"""

🆔 Rezervasyon No: #{reservation['id']}

📍 Restoran Konumu: {RESTAURANT_SETTINGS['location_url']}

Herhangi bir değişiklik veya iptal talebinizde bize yazabilirsiniz.
Afiyetle bekleriz. 🍽️"""
    
    return message


# ======================================================
# DİL TESPİTİ
# ======================================================

def detect_language(text: str) -> str:
    """
    Merkez dil tespit politikasini kullan.
    Restoran akisi icin unsupported dillerde varsayilan TR davranisi korunur.
    """
    from app.utils.message_utils import detect_language as detect_language_global

    detected = (detect_language_global(text or "") or "tr").strip().lower()
    if detected in {"en", "tr"}:
        return detected
    return "tr"


class RestaurantReservationFlowAdapter:
    """Minimal orchestrator adapter for restaurant flow contract."""

    flow_name = "restaurant"

    def can_handle(self, context: FlowContext) -> bool:
        flow_state = (context.state or {}).get(self.flow_name) or {}
        current_state = flow_state.get("state")
        if current_state and current_state != ReservationState.IDLE.value:
            return True
        msg = (context.message or "").lower()
        keywords = ("restoran", "restaurant", "masa", "rezervasyon", "reservation")
        return any(k in msg for k in keywords)

    def handle(self, context: FlowContext) -> FlowResult:
        user_id = (context.user_id or "").strip()
        if not user_id:
            return FlowResult(
                reply_messages=[],
                next_state=context.state or {},
                side_effects=[],
                handoff={"reason": "missing_user_id", "target": "human"},
            )

        locale = (context.locale or "tr").lower()
        lang = "en" if locale.startswith("en") else "tr"

        current_flow = get_reservation_flow(user_id)
        current_data = (current_flow or {}).get("data") or {}
        extracted = extract_all_reservation_info(context.message or "")
        merged = merge_reservation_data(current_data, extracted)
        reply, next_state_name = generate_smart_response(current_data, extracted, lang=lang)
        update_reservation_flow(user_id, next_state_name, merged)

        next_state = dict(context.state or {})
        next_state[self.flow_name] = {
            "state": next_state_name,
            "data": merged,
        }
        return FlowResult(
            reply_messages=[reply] if reply else [],
            next_state=next_state,
            side_effects=[{"type": "state_update", "flow": self.flow_name}],
            handoff=None,
        )


# ======================================================
# EXPORT
# ======================================================

__all__ = [
    # Enum'lar
    'ReservationState',
    'ReservationStatus',
    # Ayarlar
    'RESTAURANT_SETTINGS',
    'RESERVATIONS_DB',
    'RESERVATION_FLOW_FILE',
    # 🆕 Akıllı bilgi çıkarma
    'extract_guest_count',
    'extract_time',
    'extract_date',
    'extract_name',
    'extract_all_reservation_info',
    'get_missing_reservation_fields',
    'merge_reservation_data',
    'determine_next_state',
    'generate_smart_response',
    # Flow fonksiyonları
    'load_reservation_flows',
    'save_reservation_flows',
    'get_reservation_flow',
    'update_reservation_flow',
    'clear_reservation_flow',
    'cleanup_stale_reservation_flows',
    'should_break_reservation_flow',
    'detect_correction_in_message',
    # CRUD
    'init_reservations_db',
    'create_reservation',
    'get_reservation',
    'get_reservations_by_date',
    'get_todays_reservations',
    'get_upcoming_reservations',
    'update_reservation_status',
    'cancel_reservation',
    'get_customer_reservations',
    # Tarih/Saat
    'validate_reservation_time',
    'get_meal_type_from_time',
    'parse_date_input',
    'format_date_turkish',
    'format_date_english',
    'is_within_season',
    # Mesaj
    'format_reservation_confirmation',
    'detect_language',
    # Orchestrator adapter
    'RestaurantReservationFlowAdapter',
]
