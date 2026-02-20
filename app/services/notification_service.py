"""
Notification Service - Admin Bildirimleri

Bu modül kassandra_openai_bot.py'den ayrıştırılmıştır.
WhatsApp ve Telegram üzerinden admin bildirimlerini yönetir.

GÜNCELLEME: kassandra_openai_bot.py satır 2563-2661 fonksiyonları eklendi.
"""

from __future__ import annotations

import httpx
import os
from datetime import datetime
from typing import Optional


# ======================================================
# ADMIN BİLDİRİM AYARLARI
# ======================================================

# WhatsApp Admin numaraları
ADMIN_PHONES = [
    "905304498453",  # Ana admin - Ömer Alperen Gönen
]

# Telegram Bot ayarları (opsiyonel)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# WhatsApp API ayarları
WHATSAPP_API_URL = "https://graph.facebook.com/v22.0"
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID", "")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")  # DÜZELTME: WHATSAPP_ACCESS_TOKEN -> WHATSAPP_TOKEN

# Debug: Token kontrolü
if WHATSAPP_TOKEN:
    print(f"✅ NotificationService: WHATSAPP_TOKEN ayarlanmış")
else:
    print(f"❌ NotificationService: WHATSAPP_TOKEN BOŞ!")


class NotificationService:
    """Admin bildirim servisi"""
    
    def __init__(
        self,
        admin_phones: list = None,
        whatsapp_phone_id: str = None,
        whatsapp_token: str = None,
        telegram_token: str = None,
        telegram_chat_id: str = None,
    ):
        self.admin_phones = admin_phones or ADMIN_PHONES
        self.whatsapp_phone_id = whatsapp_phone_id or WHATSAPP_PHONE_ID
        self.whatsapp_token = whatsapp_token or WHATSAPP_TOKEN  # DÜZELTME
        self.telegram_token = telegram_token or TELEGRAM_BOT_TOKEN
        self.telegram_chat_id = telegram_chat_id or TELEGRAM_CHAT_ID
    
    async def send_whatsapp_admin(self, message: str) -> bool:
        """WhatsApp üzerinden admin'e mesaj gönder"""
        if not self.whatsapp_token:
            print("⚠️ WhatsApp token ayarlanmamış")
            return False
        
        url = f"{WHATSAPP_API_URL}/{self.whatsapp_phone_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.whatsapp_token}",
            "Content-Type": "application/json"
        }
        
        success_count = 0
        async with httpx.AsyncClient() as client:
            for admin_phone in self.admin_phones:
                try:
                    payload = {
                        "messaging_product": "whatsapp",
                        "to": admin_phone,
                        "type": "text",
                        "text": {"body": message}
                    }
                    response = await client.post(url, headers=headers, json=payload, timeout=10)
                    if response.status_code == 200:
                        success_count += 1
                    else:
                        print(f"❌ WhatsApp gönderim hatası: {response.status_code}")
                except Exception as e:
                    print(f"❌ WhatsApp gönderim hatası: {e}")
        
        return success_count > 0
    
    async def send_telegram_admin(self, message: str) -> bool:
        """Telegram üzerinden admin'e mesaj gönder"""
        if not self.telegram_token or not self.telegram_chat_id:
            return False
        
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "chat_id": self.telegram_chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                }
                response = await client.post(url, json=payload, timeout=10)
                return response.status_code == 200
        except Exception as e:
            print(f"❌ Telegram gönderim hatası: {e}")
            return False
    
    # ======================================================
    # HATA BİLDİRİMİ (kassandra_openai_bot.py satır 2604-2618)
    # ======================================================
    async def notify_admin_error(
        self,
        error_type: str,
        customer_phone: str,
        customer_message: str,
        error_details: str = ""
    ) -> bool:
        """Admin'e hata bildirimi gönder - müşteri bekliyor!"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        message = f"""⚠️ SİSTEM HATASI - MÜŞTERİ BEKLİYOR!

📱 Müşteri: {customer_phone}
💬 Mesajı: {customer_message[:100]}...

❌ Hata: {error_type}
📝 Detay: {error_details[:200]}

⏰ Zaman: {timestamp}

🔴 Müşteriye cevap VERİLMEDİ - Manuel dönüş yapın!"""
        
        return await self.send_whatsapp_admin(message)
    
    # ======================================================
    # İNSANA DEVİR BİLDİRİMİ (kassandra_openai_bot.py satır 2171-2210)
    # ======================================================
    async def notify_admin_handoff(
        self,
        category: str,
        priority: str,
        customer_phone: str,
        customer_message: str
    ) -> bool:
        """Admin'e İNSANA DEVİR bildirimi gönder"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        priority_emoji = {
            "low": "🟢",
            "medium": "🟡", 
            "high": "🟠",
            "critical": "🔴"
        }.get(priority, "⚠️")
        
        category_names = {
            "iptal_iade": "İPTAL/İADE TALEBİ",
            "sikayet": "ŞİKAYET",
            "rezervasyon_degisiklik": "REZ. DEĞİŞİKLİK",
            "fiyat_pazarlik": "FİYAT PAZARLIK",
            "ozel_istek": "ÖZEL İSTEK",
            "acil_durum": "ACİL DURUM",
            "erken_gec": "ERKEN GİRİŞ/GEÇ ÇIKIŞ",
            "canli_destek": "CANLI DESTEK TALEBİ",
            "restoran_rezervasyon": "RESTORAN REZERVASYONU"
        }
        
        cat_name = category_names.get(category, category.upper())
        
        message = f"""{priority_emoji} İNSANA DEVİR - {cat_name}

📱 Müşteri: {customer_phone}
💬 Mesajı: {customer_message[:200]}

📂 Kategori: {cat_name}
🎯 Öncelik: {priority.upper()}

⏰ Zaman: {timestamp}

👤 Müşteriye "size dönüş yapacağız" denildi.
📞 Manuel dönüş yapın!"""
        
        print(f"{priority_emoji} Admin'e handoff bildirimi gönderildi: {cat_name}")
        return await self.send_whatsapp_admin(message)
    
    # ======================================================
    # ŞÜPHELİ MESAJ BİLDİRİMİ (kassandra_openai_bot.py satır 2636-2661)
    # ======================================================
    async def notify_admin_suspicious(
        self,
        severity: str,
        reason: str,
        customer_phone: str,
        customer_message: str
    ) -> bool:
        """Admin'e ŞÜPHELİ MESAJ bildirimi gönder - HEMEN BAK!"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        severity_emoji = {
            "low": "🟡",
            "medium": "🟠", 
            "high": "🔴",
            "critical": "🚨"
        }.get(severity, "⚠️")
        
        message = f"""{severity_emoji} ŞÜPHELİ MESAJ TESPİT EDİLDİ!

📱 Müşteri: {customer_phone}
💬 Mesajı: {customer_message[:150]}

⚠️ Sebep: {reason}
🎯 Seviye: {severity.upper()}

⏰ Zaman: {timestamp}

👀 Konuşmayı kontrol edin!"""
        
        print(f"{severity_emoji} Admin'e şüpheli mesaj bildirimi gönderildi: {reason}")
        return await self.send_whatsapp_admin(message)
    
    # ======================================================
    # KRİTİK SORUN BİLDİRİMİ (kassandra_openai_bot.py satır 2563-2601)
    # ======================================================
    async def notify_admin_critical(
        self,
        category: str,
        priority: int,
        customer_phone: str,
        customer_message: str,
        additional_info: str = ""
    ) -> bool:
        """Kritik sorun bildirimi gönder"""
        timestamp = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        
        priority_emoji = "🔴" if priority >= 5 else "🟡" if priority >= 3 else "🟢"
        
        message = f"""{priority_emoji} KRİTİK SORUN BİLDİRİMİ

📌 Kategori: {category.upper()}
⚡ Öncelik: {priority}/5
📱 Müşteri: {customer_phone}

💬 Mesaj:
{customer_message[:300]}

{additional_info}

🕐 Zaman: {timestamp}

⚠️ Lütfen müşteri ile iletişime geçin!"""
        
        return await self.send_whatsapp_admin(message)
    
    # ======================================================
    # KRİTİK İŞLEM BİLDİRİMİ (kassandra_openai_bot.py satır 2621-2633)
    # ======================================================
    async def notify_critical_action(
        self,
        action: str,
        details: str = ""
    ) -> bool:
        """Kritik admin işlemleri için bildirim gönder"""
        timestamp = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        
        message = f"""🚨 KRİTİK SİSTEM İŞLEMİ

🔧 İşlem: {action}
📝 Detay: {details}
⏰ Zaman: {timestamp}

⚠️ Bu işlemi siz yapmadıysanız hemen kontrol edin!"""
        
        print(f"🚨 Kritik işlem bildirimi gönderildi: {action}")
        return await self.send_whatsapp_admin(message)
    
    # ======================================================
    # REZERVASYON BİLDİRİMİ (Ek fonksiyon)
    # ======================================================
    async def notify_admin_reservation(
        self,
        reservation_type: str,
        customer_phone: str,
        details: dict
    ) -> bool:
        """Rezervasyon bildirimi gönder"""
        timestamp = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        
        details_text = "\n".join([f"• {k}: {v}" for k, v in details.items()])
        
        message = f"""📅 YENİ REZERVASYON

⏰ Zaman: {timestamp}
📂 Tür: {reservation_type}
📱 Müşteri: {customer_phone}

📋 Detaylar:
{details_text}"""
        
        return await self.send_whatsapp_admin(message)


# ======================================================
# GLOBAL INSTANCE
# ======================================================

_notification_service: Optional[NotificationService] = None

def get_notification_service() -> NotificationService:
    """Singleton notification service döndür"""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service


# ======================================================
# UYUMLULUK FONKSİYONLARI (Eski kod ile uyum için)
# ======================================================

async def notify_admin_error(*args, **kwargs):
    return await get_notification_service().notify_admin_error(*args, **kwargs)

async def notify_admin_handoff(*args, **kwargs):
    return await get_notification_service().notify_admin_handoff(*args, **kwargs)

async def notify_admin_suspicious(*args, **kwargs):
    return await get_notification_service().notify_admin_suspicious(*args, **kwargs)

async def send_critical_notification(*args, **kwargs):
    return await get_notification_service().notify_admin_critical(*args, **kwargs)

async def notify_critical_action(*args, **kwargs):
    return await get_notification_service().notify_critical_action(*args, **kwargs)
