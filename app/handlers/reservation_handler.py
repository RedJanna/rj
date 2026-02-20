"""
Reservation Handler - Restoran Rezervasyonu İşleyicisi

Bu modül kassandra_openai_bot.py'den ayrıştırılmıştır.
Restoran rezervasyon akışını yönetir.

NOT: Bu dosya temel yapıyı içerir. 
     handle_reservation_flow fonksiyonu kassandra_openai_bot.py'den import edilir.
"""

from __future__ import annotations

import re
import time as time_module
from datetime import datetime
from typing import Optional, Tuple

from app.utils.message_utils import detect_language
from app.services.conversation_store import add_to_history, save_message
from app.services.metrics_service import record_metric


# Restoran ayarları
RESTAURANT_SETTINGS = {
    "max_auto_reservation": 8,  # 8 kişiden fazla ise canlı destek
    "min_advance_minutes": 60,  # Minimum 1 saat önceden rezervasyon
}

# Öğün saatleri
MEAL_TIMES = {
    "breakfast": {"start": "09:00", "end": "11:00"},
    "lunch": {"start": "12:00", "end": "16:00"},
    "dinner": {"start": "18:00", "end": "21:00"},
}


def get_meal_type_from_time(time_str: str) -> Optional[str]:
    """
    Saatten öğün tipini belirle.
    
    Args:
        time_str: Saat (HH:MM formatında)
        
    Returns:
        Öğün tipi ('breakfast', 'lunch', 'dinner') veya None
    """
    try:
        hour = int(time_str.split(":")[0])
        
        if 9 <= hour < 11:
            return "breakfast"
        elif 12 <= hour < 16:
            return "lunch"
        elif 18 <= hour < 21:
            return "dinner"
        else:
            return None
    except:
        return None


def format_date_turkish(date_str: str) -> str:
    """Tarihi Türkçe formatla (2024-07-15 → 15 Temmuz 2024)"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        months_tr = {
            1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan",
            5: "Mayıs", 6: "Haziran", 7: "Temmuz", 8: "Ağustos",
            9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"
        }
        return f"{dt.day} {months_tr[dt.month]} {dt.year}"
    except:
        return date_str


def format_date_english(date_str: str) -> str:
    """Tarihi İngilizce formatla (2024-07-15 → July 15, 2024)"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%B %d, %Y")
    except:
        return date_str


def is_within_season(date_str: str) -> Tuple[bool, str]:
    """
    Tarih sezon içinde mi kontrol et (10 Nisan - 10 Kasım).
    
    Returns:
        (is_valid: bool, error_message: str)
    """
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        year = dt.year
        
        season_start = datetime(year, 4, 10)  # 10 Nisan
        season_end = datetime(year, 11, 10)   # 10 Kasım
        
        if season_start <= dt <= season_end:
            return True, ""
        else:
            formatted = format_date_turkish(date_str)
            return False, f"Maalesef otelimiz ve restoranımız 10 Nisan - 10 Kasım tarihleri arasında hizmet vermektedir. Seçtiğiniz tarih ({formatted}) sezon dışındadır."
    except:
        return False, "Tarih formatı hatalı."


class ReservationHandler:
    """Restoran rezervasyonu işleyicisi"""
    
    def __init__(
        self, 
        notification_service=None,
        reservation_service=None
    ):
        """
        Args:
            notification_service: Admin bildirim servisi
            reservation_service: Rezervasyon veritabanı servisi
        """
        self.notification_service = notification_service
        self.reservation_service = reservation_service
    
    async def handle_flow(
        self,
        phone: str,
        user_message: str,
        flow: dict,
        start_time: float
    ) -> Tuple[bool, Optional[str], str]:
        """
        Rezervasyon akışını işle.
        """
        # 1. Gelen user_message’i geçmişe ekle
        save_message(phone, "user", user_message)
        add_to_history(phone, {"role": "user", "content": user_message})

        # 2. Flow verisini al
        current = self.reservation_service.get_reservation_flow(phone) or {}
        state = current.get("state", ReservationState.IDLE.value)
        data = current.get("data", {}) or {}

        # 3. Eğer dil henüz set değilse, mesajdan tespit et ve kaydet
        if "lang" not in data or data["lang"] not in ("tr", "en"):
            lang = detect_language(user_message)
            data["lang"] = lang
            # Akışı “misafir sayısı sor” aşamasına geçir (örnek)
            self.reservation_service.update_reservation_flow(
                phone, ReservationState.ASK_GUESTS.value, data
            )
            state = ReservationState.ASK_GUESTS.value

        # 4. Asıl rezervasyon mantığını çalıştır
        #    (kassandra_openai_bot içindeki handle_reservation_flow’u import edin)
        from app.handlers.kassandra_openai_bot import handle_reservation_flow
        handled, reply, status = await handle_reservation_flow(
            phone, user_message, state, data
        )

        # 5. Bot yanıtını kaydet
        if reply:
            save_message(phone, "assistant", reply)
            add_to_history(phone, {"role": "assistant", "content": reply})

        return handled, reply, status
    
    def is_in_flow(self, phone: str) -> bool:
        """Müşteri rezervasyon akışında mı?"""
        # reservation_service'den kontrol et
        if self.reservation_service:
            flow = self.reservation_service.get_reservation_flow(phone)
            return flow["state"] != "idle"
        return False
    
    def get_flow_state(self, phone: str) -> dict:
        """Mevcut akış durumunu getir"""
        if self.reservation_service:
            return self.reservation_service.get_reservation_flow(phone)
        return {"state": "idle", "data": {}}
    
    def clear_flow(self, phone: str) -> bool:
        """Akışı temizle"""
        if self.reservation_service:
            self.reservation_service.clear_reservation_flow(phone)
            return True
        return False


# Singleton instance
_reservation_handler: Optional[ReservationHandler] = None

def get_reservation_handler(
    notification_service=None,
    reservation_service=None
) -> ReservationHandler:
    """Singleton reservation handler döndür"""
    global _reservation_handler
    if _reservation_handler is None:
        _reservation_handler = ReservationHandler(
            notification_service, 
            reservation_service
        )
    return _reservation_handler


# Uyumluluk için export
__all__ = [
    'ReservationHandler',
    'get_reservation_handler',
    'get_meal_type_from_time',
    'format_date_turkish',
    'format_date_english',
    'is_within_season',
    'RESTAURANT_SETTINGS',
    'MEAL_TIMES',
]
