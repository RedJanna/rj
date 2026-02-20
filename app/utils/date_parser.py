"""
Date Parser - Turkce Tarih Parse

Mesaj icindeki Turkce/Ingilizce tarih ifadelerini parse eder.
date_utils.parse_date_input() uzerinden calisir, date nesnesi dondurur.
"""

from __future__ import annotations

from datetime import datetime, date
from typing import Optional

from app.utils.date_utils import parse_date_input


def parse_turkish_date(text: str) -> Optional[date]:
    """
    Turkce veya Ingilizce mesajdan tarih cikarir.

    Desteklenen formatlar:
    - bugun, yarin, tomorrow
    - 15 Temmuz, July 15
    - 15/07, 15.07.2026
    - Pazartesi, Monday

    Returns: date nesnesi veya None
    """
    if not text:
        return None

    iso_str = parse_date_input(text)
    if not iso_str:
        return None

    try:
        return datetime.strptime(iso_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
