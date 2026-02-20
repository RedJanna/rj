"""
Followup Service - Takip Mesajları Servisi

Bu modül kassandra_openai_bot.py'den ayrıştırılmıştır.
Müşterilere takip mesajları planlar ve gönderir.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional


# ======================================================
# FOLLOW-UP AYARLARI
# ======================================================

# Varsayılan bekleme süresi (dakika)
DEFAULT_FOLLOWUP_MINUTES = 3

# Maksimum yaş (dakika) - bu süreden eski follow-up'lar gönderilmez
FOLLOWUP_MAX_AGE_MINUTES = 30

# Grace period (saniye) - gönderim penceresi
FOLLOWUP_GRACE_SECONDS = 120

# Follow-up veritabanı dosyası
FOLLOWUP_FILE = Path("data/followups.json")


# ======================================================
# FOLLOW-UP VERİTABANI
# ======================================================

def load_followups() -> dict:
    """Follow-up verilerini yükle"""
    if FOLLOWUP_FILE.exists():
        try:
            return json.loads(FOLLOWUP_FILE.read_text(encoding="utf-8"))
        except:
            pass
    return {"pending": {}, "settings": {"minutes": DEFAULT_FOLLOWUP_MINUTES}}


def save_followups(data: dict):
    """Follow-up verilerini kaydet"""
    FOLLOWUP_FILE.parent.mkdir(parents=True, exist_ok=True)
    FOLLOWUP_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


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
    
    data["pending"][clean_phone] = {
        "scheduled_at": now.isoformat(),
        "send_at": (now + timedelta(minutes=get_followup_minutes())).isoformat(),
        "last_seen": now.isoformat(),
        "sent": False
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
        last_seen = datetime.fromisoformat(info.get("last_seen", info["scheduled_at"]))
        
        # KURAL 1: Son mesaj çok eski mi? (30 dk+)
        if (now - last_seen).total_seconds() > FOLLOWUP_MAX_AGE_MINUTES * 60:
            to_drop.append((phone, "Son mesaj çok eski"))
            continue
        
        # KURAL 2: Gönderim penceresi kontrolü
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
            if not info.get("sent", False):
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


def clear_all_followups() -> int:
    """Tüm bekleyen follow-up'ları temizle"""
    data = load_followups()
    count = len(data.get("pending", {}))
    data["pending"] = {}
    save_followups(data)
    return count


# ======================================================
# FOLLOW-UP MESAJLARI
# ======================================================

FOLLOWUP_MESSAGES = {
    "tr": "Merhaba! 👋\n\nBaşka bir konuda yardımcı olabilir miyim?\n\nSorularınız için buradayım. 😊",
    "en": "Hello! 👋\n\nIs there anything else I can help you with?\n\nI'm here for your questions. 😊"
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
