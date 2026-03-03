"""
Reminder Service - Hatırlatma Servisi
=====================================
Restoran ve otel rezervasyonları için otomatik hatırlatma sistemi.

Restoran: Rezervasyon saatine 15 dakika kala
Otel (İptal Edilemez): 7 gün önce
Otel (Ücretsiz İptal): 5 gün önce
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

from app.services.state_store_service import JsonStateRepository, resolve_data_file

# ======================================================
# CONFIGURATION
# ======================================================

REMINDERS_FILE = resolve_data_file("reminders.json", env_var="KASSANDRA_REMINDERS_FILE")
REMINDER_LOG_FILE = resolve_data_file("reminder_logs.json", env_var="KASSANDRA_REMINDER_LOG_FILE")
_REMINDER_STORE = JsonStateRepository(REMINDERS_FILE)
_REMINDER_LOG_STORE = JsonStateRepository(REMINDER_LOG_FILE)

class ReminderType(str, Enum):
    RESTAURANT_15MIN = "restaurant_15min"      # Restoran: 15 dk önce
    HOTEL_NON_REFUNDABLE = "hotel_7days"       # Otel iptal edilemez: 7 gün önce
    HOTEL_FREE_CANCEL = "hotel_5days"          # Otel ücretsiz iptal: 5 gün önce
    FLOW_INCOMPLETE = "flow_incomplete"        # Yarım kalan akış: 5 dk sonra

# Hatırlatma ayarları
REMINDER_SETTINGS = {
    ReminderType.RESTAURANT_15MIN: {
        "minutes_before": 15,
        "message_tr": "🍽️ Hatırlatma: {guest_name} adına {time} için {guest_count} kişilik restoran rezervasyonunuz 15 dakika sonra başlayacak. Sizi bekliyoruz! 😊",
        "message_en": "🍽️ Reminder: Your restaurant reservation for {guest_count} guests at {time} under {guest_name} starts in 15 minutes. See you soon! 😊",
        "enabled": True
    },
    ReminderType.HOTEL_NON_REFUNDABLE: {
        "days_before": 7,
        "message_tr": "🏨 Hatırlatma: {guest_name} adına {check_in} tarihli otel rezervasyonunuz 1 hafta sonra başlayacak. Bu rezervasyon iptal edilemez türdedir. Detaylar için bizimle iletişime geçebilirsiniz.",
        "message_en": "🏨 Reminder: Your hotel reservation for {check_in} under {guest_name} starts in 1 week. This is a non-refundable booking. Contact us for details.",
        "enabled": True
    },
    ReminderType.HOTEL_FREE_CANCEL: {
        "days_before": 5,
        "message_tr": "🏨 Hatırlatma: {guest_name} adına {check_in} tarihli otel rezervasyonunuz 5 gün sonra başlayacak. Ücretsiz iptal süreniz yaklaşıyor. Planlarınızda değişiklik varsa bize bildirin.",
        "message_en": "🏨 Reminder: Your hotel reservation for {check_in} under {guest_name} starts in 5 days. Your free cancellation period is ending soon. Let us know if your plans change.",
        "enabled": True
    },
    ReminderType.FLOW_INCOMPLETE: {
        "minutes_after": 5,
        "message_tr": "Merhaba! Rezervasyon işleminiz yarım kaldı. Devam etmek ister misiniz? 😊",
        "message_en": "Hi! Your reservation process was interrupted. Would you like to continue? 😊",
        "enabled": True
    }
}


# ======================================================
# DATA MODELS
# ======================================================

@dataclass
class ScheduledReminder:
    """Planlanmış hatırlatma"""
    id: str
    phone: str
    reminder_type: str
    reservation_id: str
    scheduled_time: str  # ISO format
    message: str
    language: str
    sent: bool = False
    sent_at: Optional[str] = None
    created_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


@dataclass
class ReminderLog:
    """Hatırlatma log kaydı"""
    id: str
    phone: str
    reminder_type: str
    reservation_id: str
    sent_at: str
    status: str  # "sent", "failed", "skipped"
    message: str
    error: Optional[str] = None


# ======================================================
# FILE OPERATIONS
# ======================================================

def load_reminders() -> Dict[str, dict]:
    """Planlanmış hatırlatmaları yükle"""
    default_data = {"scheduled": [], "settings": {}}
    data = _REMINDER_STORE.load_json(default=default_data)
    return data if isinstance(data, dict) else default_data


def save_reminders(data: dict) -> None:
    """Hatırlatmaları kaydet"""
    _REMINDER_STORE.save_json(data if isinstance(data, dict) else {})


def load_reminder_logs() -> List[dict]:
    """Hatırlatma loglarını yükle"""
    data = _REMINDER_LOG_STORE.load_json(default=[])
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("logs"), list):
        return data["logs"]
    return []


def save_reminder_log(log: ReminderLog) -> None:
    """Hatırlatma log kaydı ekle"""
    logs = load_reminder_logs()
    logs.append(asdict(log))
    
    # Son 1000 log tut
    if len(logs) > 1000:
        logs = logs[-1000:]
    
    _REMINDER_LOG_STORE.save_json(logs)


# ======================================================
# REMINDER SCHEDULING
# ======================================================

def schedule_restaurant_reminder(
    phone: str,
    reservation_id: str,
    reservation_datetime: datetime,
    guest_name: str,
    guest_count: int,
    language: str = "tr"
) -> Optional[ScheduledReminder]:
    """
    Restoran rezervasyonu için 15 dk öncesine hatırlatma planla
    """
    settings = REMINDER_SETTINGS[ReminderType.RESTAURANT_15MIN]
    if not settings["enabled"]:
        return None
    
    # 15 dakika önce
    reminder_time = reservation_datetime - timedelta(minutes=settings["minutes_before"])
    
    # Geçmiş zaman kontrolü
    if reminder_time <= datetime.now():
        return None
    
    # Mesajı hazırla
    time_str = reservation_datetime.strftime("%H:%M")
    message_template = settings["message_tr"] if language == "tr" else settings["message_en"]
    message = message_template.format(
        guest_name=guest_name,
        guest_count=guest_count,
        time=time_str
    )
    
    reminder = ScheduledReminder(
        id=f"rest_{reservation_id}_{reminder_time.strftime('%Y%m%d%H%M')}",
        phone=phone,
        reminder_type=ReminderType.RESTAURANT_15MIN,
        reservation_id=reservation_id,
        scheduled_time=reminder_time.isoformat(),
        message=message,
        language=language
    )
    
    # Kaydet
    data = load_reminders()
    
    # Aynı rezervasyon için mevcut hatırlatmayı kaldır
    data["scheduled"] = [r for r in data["scheduled"] 
                         if not (r["reservation_id"] == reservation_id 
                                and r["reminder_type"] == ReminderType.RESTAURANT_15MIN)]
    
    data["scheduled"].append(asdict(reminder))
    save_reminders(data)
    
    print(f"📅 Restoran hatırlatması planlandı: {phone[:6]}*** - {reminder_time.strftime('%d/%m %H:%M')}")
    return reminder


def schedule_hotel_reminder(
    phone: str,
    reservation_id: str,
    check_in_date: datetime,
    guest_name: str,
    is_refundable: bool,
    language: str = "tr"
) -> Optional[ScheduledReminder]:
    """
    Otel rezervasyonu için hatırlatma planla
    - İptal edilemez: 7 gün önce
    - Ücretsiz iptal: 5 gün önce
    """
    if is_refundable:
        reminder_type = ReminderType.HOTEL_FREE_CANCEL
        settings = REMINDER_SETTINGS[ReminderType.HOTEL_FREE_CANCEL]
        days_before = settings["days_before"]
    else:
        reminder_type = ReminderType.HOTEL_NON_REFUNDABLE
        settings = REMINDER_SETTINGS[ReminderType.HOTEL_NON_REFUNDABLE]
        days_before = settings["days_before"]
    
    if not settings["enabled"]:
        return None
    
    # Hatırlatma zamanı
    reminder_time = check_in_date - timedelta(days=days_before)
    # Sabah 10:00'da gönder
    reminder_time = reminder_time.replace(hour=10, minute=0, second=0)
    
    # Geçmiş zaman kontrolü
    if reminder_time <= datetime.now():
        return None
    
    # Mesajı hazırla
    check_in_str = check_in_date.strftime("%d/%m/%Y")
    message_template = settings["message_tr"] if language == "tr" else settings["message_en"]
    message = message_template.format(
        guest_name=guest_name,
        check_in=check_in_str
    )
    
    reminder = ScheduledReminder(
        id=f"hotel_{reservation_id}_{reminder_time.strftime('%Y%m%d')}",
        phone=phone,
        reminder_type=reminder_type,
        reservation_id=reservation_id,
        scheduled_time=reminder_time.isoformat(),
        message=message,
        language=language
    )
    
    # Kaydet
    data = load_reminders()
    
    # Aynı rezervasyon için mevcut hatırlatmayı kaldır
    data["scheduled"] = [r for r in data["scheduled"] 
                         if not (r["reservation_id"] == reservation_id 
                                and r["reminder_type"] in [ReminderType.HOTEL_NON_REFUNDABLE, ReminderType.HOTEL_FREE_CANCEL])]
    
    data["scheduled"].append(asdict(reminder))
    save_reminders(data)
    
    print(f"📅 Otel hatırlatması planlandı: {phone[:6]}*** - {reminder_time.strftime('%d/%m/%Y')}")
    return reminder


def cancel_reminder(reservation_id: str, reminder_type: Optional[str] = None) -> bool:
    """Hatırlatmayı iptal et"""
    data = load_reminders()
    original_count = len(data["scheduled"])
    
    if reminder_type:
        data["scheduled"] = [r for r in data["scheduled"] 
                           if not (r["reservation_id"] == reservation_id 
                                  and r["reminder_type"] == reminder_type)]
    else:
        data["scheduled"] = [r for r in data["scheduled"] 
                           if r["reservation_id"] != reservation_id]
    
    if len(data["scheduled"]) < original_count:
        save_reminders(data)
        print(f"🗑️ Hatırlatma iptal edildi: {reservation_id}")
        return True
    return False


# ======================================================
# REMINDER PROCESSING
# ======================================================

async def process_due_reminders(send_message_func) -> List[ReminderLog]:
    """
    Zamanı gelen hatırlatmaları işle ve gönder.
    
    Args:
        send_message_func: async def send_message(phone, message) -> bool
    
    Returns:
        Gönderilen hatırlatmaların log listesi
    """
    data = load_reminders()
    now = datetime.now()
    logs = []
    
    for reminder in data["scheduled"]:
        if reminder.get("sent"):
            continue
        
        scheduled_time = datetime.fromisoformat(reminder["scheduled_time"])
        
        # Zamanı gelmiş mi?
        if scheduled_time <= now:
            phone = reminder["phone"]
            message = reminder["message"]
            
            try:
                # Mesajı gönder
                success = await send_message_func(phone, message)
                
                if success:
                    reminder["sent"] = True
                    reminder["sent_at"] = now.isoformat()
                    status = "sent"
                    error = None
                    print(f"📨 Hatırlatma gönderildi: {phone[:6]}*** - {reminder['reminder_type']}")
                else:
                    status = "failed"
                    error = "Message send failed"
                    print(f"❌ Hatırlatma gönderilemedi: {phone[:6]}***")
                
            except Exception as e:
                status = "failed"
                error = str(e)
                print(f"❌ Hatırlatma hatası: {phone[:6]}*** - {e}")
            
            # Log kaydet
            log = ReminderLog(
                id=reminder["id"],
                phone=phone,
                reminder_type=reminder["reminder_type"],
                reservation_id=reminder["reservation_id"],
                sent_at=now.isoformat(),
                status=status,
                message=message[:100] + "..." if len(message) > 100 else message,
                error=error
            )
            save_reminder_log(log)
            logs.append(log)
    
    # Güncellenmiş verileri kaydet
    save_reminders(data)
    
    # Eski gönderilmiş hatırlatmaları temizle (7 günden eski)
    cleanup_old_reminders()
    
    return logs


def cleanup_old_reminders():
    """7 günden eski gönderilmiş hatırlatmaları temizle"""
    data = load_reminders()
    cutoff = datetime.now() - timedelta(days=7)
    
    original_count = len(data["scheduled"])
    data["scheduled"] = [
        r for r in data["scheduled"]
        if not r.get("sent") or datetime.fromisoformat(r.get("sent_at", "2099-01-01")) > cutoff
    ]
    
    if len(data["scheduled"]) < original_count:
        save_reminders(data)
        print(f"🧹 {original_count - len(data['scheduled'])} eski hatırlatma temizlendi")


# ======================================================
# SETTINGS MANAGEMENT
# ======================================================

def get_reminder_settings() -> dict:
    """Tüm hatırlatma ayarlarını döndür"""
    data = load_reminders()
    
    # Varsayılan ayarları kullan, kaydedilmiş ayarlarla birleştir
    settings = {}
    for rtype, default_settings in REMINDER_SETTINGS.items():
        saved = data.get("settings", {}).get(rtype, {})
        settings[rtype] = {**default_settings, **saved}
    
    return settings


def update_reminder_setting(reminder_type: str, key: str, value) -> bool:
    """Hatırlatma ayarını güncelle"""
    if reminder_type not in [rt.value for rt in ReminderType]:
        return False
    
    data = load_reminders()
    if "settings" not in data:
        data["settings"] = {}
    if reminder_type not in data["settings"]:
        data["settings"][reminder_type] = {}
    
    data["settings"][reminder_type][key] = value
    save_reminders(data)
    
    print(f"⚙️ Hatırlatma ayarı güncellendi: {reminder_type}.{key} = {value}")
    return True


def toggle_reminder_type(reminder_type: str, enabled: bool) -> bool:
    """Hatırlatma türünü aç/kapat"""
    return update_reminder_setting(reminder_type, "enabled", enabled)


# ======================================================
# STATISTICS
# ======================================================

def get_reminder_stats() -> dict:
    """Hatırlatma istatistiklerini döndür"""
    data = load_reminders()
    logs = load_reminder_logs()
    
    # Bekleyen hatırlatmalar
    pending = [r for r in data["scheduled"] if not r.get("sent")]
    sent = [r for r in data["scheduled"] if r.get("sent")]
    
    # Tip bazlı sayılar
    pending_by_type = {}
    for r in pending:
        rtype = r.get("reminder_type", "unknown")
        pending_by_type[rtype] = pending_by_type.get(rtype, 0) + 1
    
    # Son 24 saat log istatistikleri
    cutoff = datetime.now() - timedelta(hours=24)
    recent_logs = [l for l in logs if datetime.fromisoformat(l.get("sent_at", "2000-01-01")) > cutoff]
    
    sent_count = len([l for l in recent_logs if l.get("status") == "sent"])
    failed_count = len([l for l in recent_logs if l.get("status") == "failed"])
    
    return {
        "pending_total": len(pending),
        "pending_by_type": pending_by_type,
        "sent_total": len(sent),
        "last_24h": {
            "sent": sent_count,
            "failed": failed_count
        },
        "settings": get_reminder_settings()
    }


def get_pending_reminders(reminder_type: Optional[str] = None) -> List[dict]:
    """Bekleyen hatırlatmaları listele"""
    data = load_reminders()
    pending = [r for r in data["scheduled"] if not r.get("sent")]
    
    if reminder_type:
        pending = [r for r in pending if r.get("reminder_type") == reminder_type]
    
    # Zamana göre sırala
    pending.sort(key=lambda x: x.get("scheduled_time", ""))
    
    return pending


def get_reminder_logs(limit: int = 50, reminder_type: Optional[str] = None) -> List[dict]:
    """Hatırlatma loglarını listele"""
    logs = load_reminder_logs()
    
    if reminder_type:
        logs = [l for l in logs if l.get("reminder_type") == reminder_type]
    
    # En yeniden eskiye sırala
    logs.sort(key=lambda x: x.get("sent_at", ""), reverse=True)
    
    return logs[:limit]
