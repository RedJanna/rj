from __future__ import annotations

import re
from datetime import datetime, timedelta

from app.services.datetime_parser import extract_time_from_text
from app.services.restaurant_reservation_flow_service import parse_date_input


def is_hotel_open(check_date=None):
    """Otel açık mı? Sezon: 10 Nisan - 10 Kasım"""
    from datetime import date as date_type, datetime as datetime_type

    if check_date is None:
        check_date = date_type.today()

    if isinstance(check_date, datetime_type):
        check_date = check_date.date()

    year = check_date.year
    season_start = date_type(year, 4, 10)
    season_end = date_type(year, 11, 10)
    return season_start <= check_date <= season_end


def format_date_turkish(dt):
    from datetime import datetime as datetime_type

    if isinstance(dt, str):
        try:
            dt = datetime_type.strptime(dt, "%Y-%m-%d").date()
        except Exception:
            return dt
    if isinstance(dt, datetime_type):
        dt = dt.date()

    months_tr = {
        1: "Ocak",
        2: "Şubat",
        3: "Mart",
        4: "Nisan",
        5: "Mayıs",
        6: "Haziran",
        7: "Temmuz",
        8: "Ağustos",
        9: "Eylül",
        10: "Ekim",
        11: "Kasım",
        12: "Aralık",
    }
    return f"{dt.day} {months_tr[dt.month]} {dt.year}"


def format_date_english(dt):
    from datetime import datetime as datetime_type

    if isinstance(dt, str):
        try:
            dt = datetime_type.strptime(dt, "%Y-%m-%d").date()
        except Exception:
            return dt
    if isinstance(dt, datetime_type):
        dt = dt.date()

    months_en = {
        1: "January",
        2: "February",
        3: "March",
        4: "April",
        5: "May",
        6: "June",
        7: "July",
        8: "August",
        9: "September",
        10: "October",
        11: "November",
        12: "December",
    }
    return f"{months_en[dt.month]} {dt.day}, {dt.year}"


def extract_guest_count(message: str):
    msg_lower = message.lower()
    patterns = [
        r"(\d+)\s*kişi",
        r"(\d+)\s*kişilik",
        r"(\d+)\s*people",
        r"(\d+)\s*person",
        r"(\d+)\s*guests?",
        r"for\s*(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, msg_lower)
        if match:
            count = int(match.group(1))
            if 1 <= count <= 50:
                return count
    return None


def extract_time_from_message(message: str):
    return extract_time_from_text(message)


def extract_date_from_message(message: str):
    msg_lower = message.lower()
    today = datetime.now()

    if any(w in msg_lower for w in ["bugün", "bugun", "today"]):
        return today.strftime("%Y-%m-%d")
    if any(w in msg_lower for w in ["yarın", "yarin", "tomorrow"]):
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")
    if "hafta sonu" in msg_lower or "weekend" in msg_lower:
        days_until_saturday = (5 - today.weekday()) % 7
        if days_until_saturday == 0:
            days_until_saturday = 7
        return (today + timedelta(days=days_until_saturday)).strftime("%Y-%m-%d")

    days_tr = ["pazartesi", "salı", "çarşamba", "perşembe", "cuma", "cumartesi", "pazar"]
    days_en = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for i, day in enumerate(days_tr + days_en):
        if day in msg_lower:
            target_day = i % 7
            current_day = today.weekday()
            days_ahead = target_day - current_day
            if days_ahead <= 0:
                days_ahead += 7
            return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    months_tr = {
        "ocak": 1,
        "şubat": 2,
        "mart": 3,
        "nisan": 4,
        "mayıs": 5,
        "haziran": 6,
        "temmuz": 7,
        "ağustos": 8,
        "eylül": 9,
        "ekim": 10,
        "kasım": 11,
        "aralık": 12,
    }
    months_en = {
        "january": 1,
        "february": 2,
        "march": 3,
        "april": 4,
        "may": 5,
        "june": 6,
        "july": 7,
        "august": 8,
        "september": 9,
        "october": 10,
        "november": 11,
        "december": 12,
    }
    all_months = {**months_tr, **months_en}

    for month_name, month_num in all_months.items():
        if month_name in msg_lower:
            patterns = [rf"(\d{{1,2}})\s*{month_name}", rf"{month_name}\s*(\d{{1,2}})"]
            day = None
            for pattern in patterns:
                match = re.search(pattern, msg_lower)
                if match:
                    day = int(match.group(1))
                    break
            if day is None:
                clean_text = re.sub(r"\d+\s*kişi", "", msg_lower)
                numbers = re.findall(r"\d+", clean_text)
                if numbers:
                    day = int(numbers[0])
            if day and 1 <= day <= 31:
                year = today.year
                if month_num < today.month or (month_num == today.month and day < today.day):
                    year += 1
                try:
                    return datetime(year, month_num, day).strftime("%Y-%m-%d")
                except Exception:
                    pass

    date_patterns = [r"(\d{1,2})[./](\d{1,2})[./](\d{2,4})", r"(\d{1,2})[./](\d{1,2})"]
    for pattern in date_patterns:
        match = re.search(pattern, message)
        if not match:
            continue
        groups = match.groups()
        day = int(groups[0])
        month = int(groups[1])
        year = int(groups[2]) if len(groups) > 2 else today.year
        if year < 100:
            year += 2000
        if 1 <= day <= 31 and 1 <= month <= 12:
            try:
                return datetime(year, month, day).strftime("%Y-%m-%d")
            except Exception:
                pass
    return None


def extract_all_reservation_info(message: str):
    date_result = extract_date_from_message(message)
    if not date_result:
        try:
            date_result = parse_date_input(message)
        except Exception:
            pass
    return {
        "guest_count": extract_guest_count(message),
        "date": date_result,
        "time": extract_time_from_message(message),
    }
