"""
Followup Service - Takip Mesajları Servisi

Bu modül kassandra_openai_bot.py'den ayrıştırılmıştır.
Müşterilere takip mesajları planlar ve gönderir.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import List, Optional

from app.services.state_store_service import JsonStateRepository, resolve_data_file

# ======================================================
# FOLLOW-UP AYARLARI
# ======================================================

# Varsayılan bekleme süresi (dakika)
# 10. dakikada "sohbet sonlandırılacak" uyarısı
DEFAULT_FOLLOWUP_MINUTES = 10

# Maksimum yaş (dakika) - bu süreden eski follow-up'lar gönderilmez
FOLLOWUP_MAX_AGE_MINUTES = 30

# Grace period (saniye) - gönderim penceresi
FOLLOWUP_GRACE_SECONDS = 120

# Follow-up veritabanı dosyası
FOLLOWUP_FILE = resolve_data_file("followups.json", env_var="KASSANDRA_FOLLOWUP_FILE")
_FOLLOWUP_STORE = JsonStateRepository(FOLLOWUP_FILE)


# ======================================================
# FOLLOW-UP VERİTABANI
# ======================================================

def load_followups() -> dict:
    """Follow-up verilerini yükle"""
    default_data = {"pending": {}, "settings": {"minutes": DEFAULT_FOLLOWUP_MINUTES}, "last_cycle": {}}
    data = _FOLLOWUP_STORE.load_json(default=default_data)
    return data if isinstance(data, dict) else default_data


def save_followups(data: dict):
    """Follow-up verilerini kaydet"""
    _FOLLOWUP_STORE.save_json(data if isinstance(data, dict) else {})


def get_followup_minutes() -> int:
    """Follow-up bekleme süresini al"""
    data = load_followups()
    return data.get("settings", {}).get("minutes", DEFAULT_FOLLOWUP_MINUTES)


def set_followup_minutes(minutes: int) -> bool:
    """Follow-up bekleme süresini ayarla"""
    if minutes < 1 or minutes > 60:
        return False
    data = load_followups()
    if "settings" not in data:
        data["settings"] = {}
    data["settings"]["minutes"] = minutes
    save_followups(data)
    return True


# ======================================================
# FOLLOW-UP FONKSİYONLARI
# ======================================================

def schedule_followup(phone: str):
    """
    Yeni follow-up planla.
    
    Args:
        phone: Müşteri telefon numarası
    """
    if not phone:
        return
    
    data = load_followups()
    clean_phone = re.sub(r'[^\d]', '', phone)
    now = datetime.now()
    reminder_minutes = get_followup_minutes()
    
    data["pending"][clean_phone] = {
        "scheduled_at": now.isoformat(),
        "send_at": (now + timedelta(minutes=reminder_minutes)).isoformat(),
        "close_at": (now + timedelta(minutes=30)).isoformat(),
        "last_seen": now.isoformat(),
        "sent": False,
        "reminder_sent": False,
        "closed": False,
    }
    save_followups(data)


def cancel_followup(phone: str):
    """
    Follow-up iptal et (müşteri cevap verdi).
    
    Args:
        phone: Müşteri telefon numarası
    """
    if not phone:
        return
    
    data = load_followups()
    clean_phone = re.sub(r'[^\d]', '', phone)
    
    if clean_phone in data.get("pending", {}):
        del data["pending"][clean_phone]
        save_followups(data)


def mark_followup_sent(phone: str):
    """
    Follow-up gönderildi olarak işaretle.
    
    Args:
        phone: Müşteri telefon numarası
    """
    if not phone:
        return
    
    data = load_followups()
    clean_phone = re.sub(r'[^\d]', '', phone)
    
    if clean_phone in data.get("pending", {}):
        entry = data["pending"][clean_phone]
        if isinstance(entry, dict):
            entry["sent"] = True
            entry["reminder_sent"] = True
            entry["reminder_sent_at"] = datetime.now().isoformat()
            data["pending"][clean_phone] = entry
            save_followups(data)


def mark_followup_closed(phone: str):
    """Sohbet otomatik kapatma işlendi olarak işaretle ve kaydı kaldır."""
    if not phone:
        return
    data = load_followups()
    clean_phone = re.sub(r'[^\d]', '', phone)
    if clean_phone in data.get("pending", {}):
        del data["pending"][clean_phone]
        save_followups(data)


def drop_expired_followup(phone: str, reason: str):
    """
    Süresi geçmiş follow-up'ı sil (göndermeden).
    
    Args:
        phone: Müşteri telefon numarası
        reason: Silme nedeni
    """
    data = load_followups()
    clean_phone = re.sub(r'[^\d]', '', phone)
    
    if clean_phone in data.get("pending", {}):
        del data["pending"][clean_phone]
        save_followups(data)
        print(f"🗑️ Follow-up DROP edildi ({reason}): {clean_phone}")


def get_pending_followups() -> List[str]:
    """
    Gönderilmesi gereken follow-up'ları getir.
    
    ZOMBİ KORUMA: Sadece geçerli zaman penceresindekiler döner.
    Süresi geçenler otomatik silinir.
    
    Returns:
        Gönderilecek telefon numaraları listesi
    """
    data = load_followups()
    pending = []
    to_drop = []
    now = datetime.now()
    
    for phone, info in data.get("pending", {}).items():
        send_at = datetime.fromisoformat(info["send_at"])
        close_at_raw = info.get("close_at")
        close_at = datetime.fromisoformat(close_at_raw) if close_at_raw else (send_at + timedelta(minutes=20))
        last_seen = datetime.fromisoformat(info.get("last_seen", info["scheduled_at"]))
        
        # KURAL 1: Son mesaj çok eskiyse (30 dk+) reminder gönderme.
        # Bu kayıtlar get_expired_followups() ile otomatik kapatma/temizleme
        # akışına bırakılır.
        if (now - last_seen).total_seconds() > FOLLOWUP_MAX_AGE_MINUTES * 60:
            continue
        
        # KURAL 2: 30 dakikayı geçtiyse reminder gönderme
        if now >= close_at:
            continue

        # KURAL 3: Gönderim penceresi kontrolü
        deadline = send_at + timedelta(seconds=FOLLOWUP_GRACE_SECONDS)
        
        if now < send_at:
            # Henüz zamanı gelmedi
            continue
        elif now > deadline:
            # Zaman penceresi geçti
            to_drop.append((phone, f"Zaman penceresi geçti"))
            continue
        else:
            # Tam zamanında - gönder!
            if not info.get("reminder_sent", False):
                pending.append(phone)
    
    # Süresi geçenleri sil
    for phone, reason in to_drop:
        drop_expired_followup(phone, reason)
    
    return pending


def get_followup_stats() -> dict:
    """Follow-up istatistiklerini getir"""
    data = load_followups()
    pending = data.get("pending", {})
    
    return {
        "pending_count": len(pending),
        "followup_minutes": get_followup_minutes(),
        "max_age_minutes": FOLLOWUP_MAX_AGE_MINUTES,
        "grace_seconds": FOLLOWUP_GRACE_SECONDS,
    }


def get_expired_followups() -> List[str]:
    """
    30 dakika boyunca yanıt gelmeyen (otomatik kapatılacak) numaraları döndür.
    """
    data = load_followups()
    now = datetime.now()
    expired: List[str] = []
    for phone, info in data.get("pending", {}).items():
        if not isinstance(info, dict):
            continue
        close_at_raw = info.get("close_at")
        if not close_at_raw:
            continue
        try:
            close_at = datetime.fromisoformat(close_at_raw)
        except Exception:
            continue
        if now >= close_at and not info.get("closed", False):
            expired.append(phone)
    return expired


def clear_all_followups() -> int:
    """Tüm bekleyen follow-up'ları temizle"""
    data = load_followups()
    count = len(data.get("pending", {}))
    data["pending"] = {}
    save_followups(data)
    return count


def save_last_followup_cycle(sent: int, closed: int):
    """Son follow-up döngüsü özetini kaydet."""
    data = load_followups()
    data["last_cycle"] = {
        "sent": int(sent or 0),
        "closed": int(closed or 0),
        "checked_at": datetime.now().isoformat(),
    }
    save_followups(data)


# ======================================================
# FOLLOW-UP MESAJLARI
# ======================================================

FOLLOWUP_MESSAGES = {
    "tr": "Merhaba 👋\n\nGörüşmemiz yaklaşık 20 dakika içinde otomatik olarak sonlandırılacaktır. Devam etmek isterseniz lütfen bu mesaja yanıt verin. 😊",
    "en": "Hello 👋\n\nOur conversation will be automatically closed in about 20 minutes. If you'd like to continue, please reply to this message. 😊"
}


def get_followup_message(lang: str = "tr") -> str:
    """Takip mesajını getir"""
    return FOLLOWUP_MESSAGES.get(lang, FOLLOWUP_MESSAGES["tr"])


# ======================================================
# FOLLOW-UP SERVICE CLASS
# ======================================================

class FollowupService:
    """Takip mesajları servisi"""
    
    def __init__(self, whatsapp_sender=None):
        """
        Args:
            whatsapp_sender: WhatsApp mesaj gönderme fonksiyonu
        """
        self.send_whatsapp = whatsapp_sender
    
    def schedule(self, phone: str):
        """Follow-up planla"""
        schedule_followup(phone)
    
    def cancel(self, phone: str):
        """Follow-up iptal et"""
        cancel_followup(phone)
    
    def get_pending(self) -> List[str]:
        """Bekleyen follow-up'ları getir"""
        return get_pending_followups()
    
    async def send_pending(self, lang: str = "tr") -> int:
        """
        Bekleyen follow-up'ları gönder.
        
        Returns:
            Gönderilen mesaj sayısı
        """
        if not self.send_whatsapp:
            return 0
        
        pending = self.get_pending()
        sent_count = 0
        
        for phone in pending:
            try:
                message = get_followup_message(lang)
                await self.send_whatsapp(phone, message)
                mark_followup_sent(phone)
                sent_count += 1
                print(f"📤 Follow-up gönderildi: {phone[:6]}***")
            except Exception as e:
                print(f"❌ Follow-up gönderilemedi: {phone[:6]}*** - {e}")
        
        return sent_count
    
    def get_stats(self) -> dict:
        """İstatistikleri getir"""
        return get_followup_stats()
    
    def clear_all(self) -> int:
        """Tüm follow-up'ları temizle"""
        return clear_all_followups()


# Singleton instance
_followup_service: Optional[FollowupService] = None

def get_followup_service(whatsapp_sender=None) -> FollowupService:
    """Singleton followup service döndür"""
    global _followup_service
    if _followup_service is None:
        _followup_service = FollowupService(whatsapp_sender)
    return _followup_service
