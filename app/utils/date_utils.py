"""
Date Utils - Tarih/Zaman Yardımcı Fonksiyonları

Bu modül kassandra_openai_bot.py'den ayrıştırılmıştır.
Kaynak: kassandra_openai_bot.py satır 1178-1344

Tarih parse, format ve doğrulama işlemleri.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Tuple, Optional


# ======================================================
# SEZON AYARLARI
# ======================================================

SEASON_SETTINGS = {
    "season_start_month": 4,   # Nisan
    "season_start_day": 10,
    "season_end_month": 11,    # Kasım
    "season_end_day": 10,
}

# Öğün saatleri
MEAL_TIMES = {
    "breakfast": {
        "name_tr": "Kahvaltı",
        "name_en": "Breakfast",
        "start": "09:00",
        "end": "11:00",
        "last_reservation": "11:00",
        "min_advance_minutes": 5
    },
    "lunch": {
        "name_tr": "Öğle Yemeği",
        "name_en": "Lunch",
        "start": "12:00",
        "end": "16:00",
        "last_reservation": "16:00",
        "min_advance_minutes": 5
    },
    "dinner": {
        "name_tr": "Akşam Yemeği",
        "name_en": "Dinner",
        "start": "18:00",
        "end": "21:00",
        "last_reservation": "21:00",
        "min_advance_minutes": 5,
        "late_min_advance_minutes": 15,
        "late_start": "20:00"
    }
}


# ======================================================
# AY İSİMLERİ
# ======================================================

MONTHS_TR = {
    1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran",
    7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"
}

MONTHS_EN = {
    1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
    7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December"
}

# Parse için ay isimleri (küçük harf)
MONTHS_TR_PARSE = {
    "ocak": 1, "şubat": 2, "mart": 3, "nisan": 4, "mayıs": 5, "haziran": 6,
    "temmuz": 7, "ağustos": 8, "eylül": 9, "ekim": 10, "kasım": 11, "aralık": 12
}

MONTHS_EN_PARSE = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12
}

# Gün isimleri
DAYS_TR = ["pazartesi", "salı", "çarşamba", "perşembe", "cuma", "cumartesi", "pazar"]
DAYS_EN = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


# ======================================================
# TARİH PARSE FONKSİYONLARI (kassandra_openai_bot.py satır 1214-1285)
# ======================================================

def parse_date_input(date_text: str) -> Optional[str]:
    """
    Tarih girişini parse et ve YYYY-MM-DD formatına çevir.
    
    Desteklenen formatlar:
    - bugün, today
    - yarın, tomorrow
    - Gün adları (Pazartesi, Monday)
    - 15 Temmuz, July 15
    - 15/07, 15.07
    - 15/07/2025
    
    Returns: YYYY-MM-DD formatında tarih veya None
    """
    date_text = date_text.lower().strip()
    today = datetime.now()
    
    # "bugün", "yarın" gibi ifadeler
    if date_text in ["bugün", "today", "bugun"]:
        return today.strftime("%Y-%m-%d")
    elif date_text in ["yarın", "tomorrow", "yarin"]:
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Gün adları
    for i, day in enumerate(DAYS_TR + DAYS_EN):
        if day in date_text:
            target_day = i % 7
            current_day = today.weekday()
            days_ahead = target_day - current_day
            if days_ahead <= 0:
                days_ahead += 7
            return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    
    # Ay isimleri ile tarih (örn: "15 Temmuz", "July 15")
    all_months = {**MONTHS_TR_PARSE, **MONTHS_EN_PARSE}
    
    for month_name, month_num in all_months.items():
        if month_name in date_text:
            numbers = re.findall(r'\d+', date_text)
            if numbers:
                day = int(numbers[0])
                year = today.year
                # Eğer ay geçmişse gelecek yılı al
                if month_num < today.month or (month_num == today.month and day < today.day):
                    year += 1
                try:
                    return datetime(year, month_num, day).strftime("%Y-%m-%d")
                except:
                    pass
    
    # DD/MM veya DD.MM formatı
    patterns = [
        r'(\d{1,2})[./](\d{1,2})',  # 15/07 veya 15.07
        r'(\d{1,2})[./](\d{1,2})[./](\d{2,4})'  # 15/07/2025
    ]
    
    for pattern in patterns:
        match = re.search(pattern, date_text)
        if match:
            groups = match.groups()
            day = int(groups[0])
            month = int(groups[1])
            year = int(groups[2]) if len(groups) > 2 else today.year
            if year < 100:
                year += 2000
            try:
                return datetime(year, month, day).strftime("%Y-%m-%d")
            except:
                pass
    
    return None


# ======================================================
# TARİH FORMAT FONKSİYONLARI (kassandra_openai_bot.py satır 1288-1317)
# ======================================================

def format_date_turkish(date_str: str) -> str:
    """Tarihi Türkçe formata çevir: 3 Haziran 2026"""
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        day = date_obj.day
        month = MONTHS_TR[date_obj.month]
        year = date_obj.year
        return f"{day} {month} {year}"
    except:
        return date_str


def format_date_english(date_str: str) -> str:
    """Tarihi İngilizce formata çevir: 3 June 2026"""
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        day = date_obj.day
        month = MONTHS_EN[date_obj.month]
        year = date_obj.year
        return f"{day} {month} {year}"
    except:
        return date_str


def format_date_short(date_str: str) -> str:
    """Tarihi kısa formata çevir: 03/06/2026"""
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        return date_obj.strftime("%d/%m/%Y")
    except:
        return date_str


# ======================================================
# SEZON KONTROLÜ (kassandra_openai_bot.py satır 1320-1343)
# ======================================================

def is_within_season(date_str: str) -> Tuple[bool, str]:
    """
    Tarih sezon içinde mi kontrol et.
    Sezon: 10 Nisan - 10 Kasım
    
    Returns: (is_valid: bool, error_message: str)
    """
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        month = date_obj.month
        day = date_obj.day
        
        season_start = (SEASON_SETTINGS["season_start_month"], SEASON_SETTINGS["season_start_day"])
        season_end = (SEASON_SETTINGS["season_end_month"], SEASON_SETTINGS["season_end_day"])
        
        # 10 Nisan öncesi
        if (month, day) < season_start:
            return False, f"Üzgünüz, otelimiz ve restoranımız 10 Nisan - 10 Kasım tarihleri arasında hizmet vermektedir. Seçtiğiniz tarih ({format_date_turkish(date_str)}) sezon dışındadır."
        
        # 10 Kasım sonrası
        if (month, day) > season_end:
            return False, f"Üzgünüz, otelimiz ve restoranımız 10 Nisan - 10 Kasım tarihleri arasında hizmet vermektedir. Seçtiğiniz tarih ({format_date_turkish(date_str)}) sezon dışındadır."
        
        return True, ""
    except:
        return False, "Geçersiz tarih"


def is_within_season_en(date_str: str) -> Tuple[bool, str]:
    """İngilizce hata mesajı ile sezon kontrolü"""
    is_valid, _ = is_within_season(date_str)
    if not is_valid:
        formatted = format_date_english(date_str)
        return False, f"Sorry, our hotel and restaurant operate between April 10 - November 10. Your selected date ({formatted}) is outside the season."
    return True, ""


# ======================================================
# SAAT DOĞRULAMA (kassandra_openai_bot.py satır 1178-1212)
# ======================================================

def validate_reservation_time(meal_type: str, time_str: str) -> Tuple[bool, str]:
    """
    Rezervasyon saatini doğrula.
    
    Args:
        meal_type: breakfast, lunch, dinner
        time_str: HH:MM formatında saat
        
    Returns: (is_valid: bool, error_message: str)
    """
    meal_settings = MEAL_TIMES.get(meal_type)
    if not meal_settings:
        return False, "Geçersiz öğün tipi"
    
    try:
        req_time = datetime.strptime(time_str, "%H:%M").time()
        start_time = datetime.strptime(meal_settings["start"], "%H:%M").time()
        end_time = datetime.strptime(meal_settings["end"], "%H:%M").time()
        
        if req_time < start_time or req_time > end_time:
            return False, f"{meal_settings['name_tr']} için rezervasyon saati {meal_settings['start']} - {meal_settings['end']} arasında olmalıdır."
        
        return True, ""
    except:
        return False, "Geçersiz saat formatı. Lütfen HH:MM formatında girin (örn: 19:00)"


def get_meal_type_from_time(time_str: str) -> Optional[str]:
    """Saate göre öğün tipini belirle"""
    try:
        req_time = datetime.strptime(time_str, "%H:%M").time()
        
        for meal_type, settings in MEAL_TIMES.items():
            start = datetime.strptime(settings["start"], "%H:%M").time()
            end = datetime.strptime(settings["end"], "%H:%M").time()
            if start <= req_time <= end:
                return meal_type
        
        return None
    except:
        return None


def parse_time_input(text: str) -> Optional[str]:
    """
    Saat girişini parse et ve HH:MM formatına çevir.
    
    Desteklenen formatlar:
    - 19:00, 19.00
    - 19, 7pm, 7 pm
    - akşam 7, 7 evening
    """
    text = text.lower().strip()
    
    # HH:MM veya HH.MM formatı
    time_match = re.search(r'(\d{1,2})[:\.](\d{2})', text)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"
    
    # Sadece saat (örn: 19, 7pm)
    hour_match = re.search(r'(\d{1,2})\s*(pm|am)?', text)
    if hour_match:
        hour = int(hour_match.group(1))
        period = hour_match.group(2)
        
        if period == "pm" and hour < 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0
        
        if 0 <= hour <= 23:
            return f"{hour:02d}:00"
    
    return None


# ======================================================
# GEÇMİŞ TARİH KONTROLÜ
# ======================================================

def is_past_date(date_str: str) -> bool:
    """Tarih geçmişte mi?"""
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        return date_obj.date() < datetime.now().date()
    except:
        return True


def is_today(date_str: str) -> bool:
    """Tarih bugün mü?"""
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        return date_obj.date() == datetime.now().date()
    except:
        return False


def days_until(date_str: str) -> int:
    """Tarihe kaç gün var?"""
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        delta = date_obj.date() - datetime.now().date()
        return delta.days
    except:
        return -1


# ======================================================
# TARİH ARALIĞI
# ======================================================

def get_date_range(start_days: int = 0, end_days: int = 7) -> Tuple[str, str]:
    """Tarih aralığı döndür"""
    today = datetime.now()
    start = (today + timedelta(days=start_days)).strftime("%Y-%m-%d")
    end = (today + timedelta(days=end_days)).strftime("%Y-%m-%d")
    return start, end


def get_weekday_name(date_str: str, lang: str = "tr") -> str:
    """Haftanın gününü döndür"""
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        weekday = date_obj.weekday()
        if lang == "en":
            return DAYS_EN[weekday].capitalize()
        return DAYS_TR[weekday].capitalize()
    except:
        return ""
