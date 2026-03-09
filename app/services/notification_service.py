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
from app.services.handoff_packet_service import build_handoff_packet, validate_handoff_packet
from app.services.handoff_policy_service import apply_handoff_policy
from app.services.handoff_policy_service import HANDOFF_POLICY_BY_CATEGORY
from app.services.metrics_service import record_metric
from app.services.conversation_store import load_conversation
from app.utils.message_utils import detect_language


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
_CHEF_PHONE_ENV = os.getenv("RESTAURANT_CHEF_PHONE", "").strip()
RESTAURANT_CHEF_PHONE = _CHEF_PHONE_ENV or "905012969548"

# Debug: Token kontrolü
if WHATSAPP_TOKEN:
    print(f"✅ NotificationService: WHATSAPP_TOKEN ayarlanmış")
else:
    print(f"❌ NotificationService: WHATSAPP_TOKEN BOŞ!")


def _normalize_handoff_category(
    *,
    category: str,
    source: str,
    detected_intent: str,
    tags: list[str] | None,
) -> str:
    raw = (category or "").strip().lower()
    if raw:
        return raw

    intent = (detected_intent or "").strip().upper()
    src = (source or "").strip().lower()
    tagset = {str(t).strip().lower() for t in (tags or []) if str(t).strip()}

    if "restaurant" in src or "restoran" in src or "restaurant_reservation" in tagset:
        return "restoran_rezervasyon"
    if "transfer" in src or "transfer" in tagset:
        return "antalya_transfer"
    if "payment_confirmation" in src or "payment_confirmation" in tagset or intent == "PAYMENT_CONFIRMED":
        return "odeme_bildirimi"
    if "quiet_room" in src or "quiet_room_handoff" in tagset:
        return "quiet_room_live_required"
    if intent in {"COMPLAINT", "CANCEL_REFUND_REQUEST"}:
        return "sikayet" if intent == "COMPLAINT" else "iptal_iade"
    if intent == "HUMAN_REQUEST":
        return "canli_destek"
    if intent == "PRICE_QUERY":
        return "fiyat_handoff"

    # Safe fallback for unknown/empty category cases.
    fallback = "canli_destek"
    if fallback in HANDOFF_POLICY_BY_CATEGORY:
        return fallback
    return next(iter(HANDOFF_POLICY_BY_CATEGORY.keys()), "canli_destek")


def _extract_switch_target(text: str) -> str:
    t = (text or "").lower()
    if not t:
        return ""
    if any(k in t for k in ["english", "ingilizce"]):
        return "en"
    if any(k in t for k in ["türkçe", "turkce", "turkish"]):
        return "tr"
    if any(k in t for k in ["рус", "russian", "rusça", "rusca"]):
        return "ru"
    if any(k in t for k in ["almanca", "german", "deutsch"]):
        return "de"
    if any(k in t for k in ["arapça", "arabic", "العربية"]):
        return "ar"
    if any(k in t for k in ["ispanyolca", "spanish", "español", "espanol"]):
        return "es"
    if any(k in t for k in ["fransızca", "french", "français", "francais"]):
        return "fr"
    if any(k in t for k in ["çince", "cince", "chinese", "中文"]):
        return "zh"
    if any(k in t for k in ["hintçe", "hintce", "hindi", "हिंदी"]):
        return "hi"
    if any(k in t for k in ["portekizce", "portuguese", "português", "portugues"]):
        return "pt"
    return ""


def _infer_language_lock(customer_phone: str, customer_message: str) -> str:
    phone = (customer_phone or "").strip()
    try:
        if phone:
            conv = load_conversation(phone) or {}
            messages = conv.get("messages") or []
            # latest explicit switch
            for item in reversed(messages):
                txt = (item.get("user_message") or "").strip()
                target = _extract_switch_target(txt)
                if target:
                    return target
            # first user message lock
            for item in messages:
                txt = (item.get("user_message") or "").strip()
                if txt:
                    return detect_language(txt) or "en"
    except Exception:
        pass
    return detect_language(customer_message or "") or "en"


class NotificationService:
    """Admin bildirim servisi"""
    
    def __init__(
        self,
        admin_phones: list = None,
        whatsapp_phone_id: str = None,
        whatsapp_token: str = None,
        telegram_token: str = None,
        telegram_chat_id: str = None,
        restaurant_chef_phone: str | None = None,
    ):
        self.admin_phones = admin_phones or ADMIN_PHONES
        self.whatsapp_phone_id = whatsapp_phone_id or WHATSAPP_PHONE_ID
        self.whatsapp_token = whatsapp_token or WHATSAPP_TOKEN  # DÜZELTME
        self.telegram_token = telegram_token or TELEGRAM_BOT_TOKEN
        self.telegram_chat_id = telegram_chat_id or TELEGRAM_CHAT_ID
        chef_phone_candidate = restaurant_chef_phone if restaurant_chef_phone is not None else RESTAURANT_CHEF_PHONE
        if not str(chef_phone_candidate or "").strip():
            chef_phone_candidate = RESTAURANT_CHEF_PHONE
        self.restaurant_chef_phone = self._normalize_phone(chef_phone_candidate)

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        return "".join(ch for ch in str(phone or "") if ch.isdigit())

    def _has_alternate_admin_target(self, customer_phone: str) -> bool:
        customer = self._normalize_phone(customer_phone)
        if not customer:
            return bool(self.admin_phones)
        for admin_phone in self.admin_phones:
            if self._normalize_phone(admin_phone) != customer:
                return True
        return False

    async def send_whatsapp_admin(self, message: str, *, exclude_phones: Optional[list[str]] = None) -> bool:
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
        excluded = {self._normalize_phone(p) for p in (exclude_phones or []) if self._normalize_phone(p)}
        async with httpx.AsyncClient() as client:
            for admin_phone in self.admin_phones:
                if self._normalize_phone(admin_phone) in excluded:
                    continue
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
                        detail = (response.text or "").strip()
                        if len(detail) > 400:
                            detail = detail[:400] + "..."
                        print(f"❌ WhatsApp gönderim hatası: status={response.status_code} phone={admin_phone} detail={detail}")
                except Exception as e:
                    print(f"❌ WhatsApp gönderim hatası: {e}")
        
        return success_count > 0

    async def send_whatsapp_to_phone(self, phone: str, message: str) -> bool:
        """WhatsApp üzerinden tek bir numaraya mesaj gönder."""
        if not self.whatsapp_token:
            print("⚠️ WhatsApp token ayarlanmamış")
            return False

        target_phone = self._normalize_phone(phone)
        if not target_phone:
            return False

        url = f"{WHATSAPP_API_URL}/{self.whatsapp_phone_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.whatsapp_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": target_phone,
            "type": "text",
            "text": {"body": message}
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload, timeout=10)
            if response.status_code == 200:
                return True
            detail = (response.text or "").strip()
            if len(detail) > 400:
                detail = detail[:400] + "..."
            print(f"❌ WhatsApp tekli gönderim hatası: status={response.status_code} phone={target_phone} detail={detail}")
            return False
        except Exception as e:
            print(f"❌ WhatsApp tekli gönderim hatası: {e}")
            return False
    
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

        return await self.send_whatsapp_admin(message, exclude_phones=[customer_phone])
    
    # ======================================================
    # İNSANA DEVİR BİLDİRİMİ (kassandra_openai_bot.py satır 2171-2210)
    # ======================================================
    async def notify_admin_handoff(
        self,
        category: str,
        priority: str,
        customer_phone: str,
        customer_message: str,
        *,
        source: str = "chat_runtime",
        detected_intent: str = "unknown",
        confidence: float | None = None,
        conversation_summary: str = "",
        attempted_actions: list[str] | None = None,
        suggested_reply: str = "",
        tags: list[str] | None = None,
        correlation_id: str = "",
    ) -> bool:
        """Admin'e İNSANA DEVİR bildirimi gönder"""
        normalized_category = _normalize_handoff_category(
            category=category,
            source=source,
            detected_intent=detected_intent,
            tags=tags,
        )
        if normalized_category != (category or "").strip().lower():
            record_metric(
                "handoff.category_autofill",
                category=normalized_category,
                meta={
                    "requested_category": (category or "").strip().lower(),
                    "source": source,
                    "detected_intent": detected_intent,
                },
            )

        policy = apply_handoff_policy(normalized_category, priority)
        effective_priority = str(policy["effective_priority"])
        trigger_type = str(policy["trigger_type"])
        sla_target_minutes = int(policy["sla_target_minutes"])
        within_business_hours = bool(policy["within_business_hours"])

        normalized_tags = list(tags or [])
        normalized_tags.extend(
            [
                f"trigger:{trigger_type}",
                f"sla:{sla_target_minutes}m",
                "mesai_ici" if within_business_hours else "mesai_disi",
            ]
        )
        language_lock = _infer_language_lock(customer_phone, customer_message)
        normalized_tags.append(f"lang:{language_lock}")

        packet = build_handoff_packet(
            category=normalized_category,
            priority=effective_priority,
            customer_phone=customer_phone,
            customer_message=customer_message,
            source=source,
            detected_intent=detected_intent,
            confidence=confidence,
            conversation_summary=conversation_summary,
            attempted_actions=attempted_actions,
            suggested_reply=suggested_reply,
            tags=normalized_tags,
            correlation_id=correlation_id,
            trigger_type=trigger_type,
            sla_target_minutes=sla_target_minutes,
            within_business_hours=within_business_hours,
            language_lock=language_lock,
        )
        ok, missing = validate_handoff_packet(packet)
        if not ok:
            print(f"❌ Handoff packet reject (missing/invalid): {missing}")
            record_metric(
                "handoff.packet_reject",
                category=category or "unknown",
                meta={
                    "missing": missing,
                    "source": source,
                    "detected_intent": detected_intent,
                    "confidence": confidence,
                    "correlation_id": correlation_id,
                    "language_lock": language_lock,
                },
            )
            return False
        record_metric(
            "handoff.packet",
            category=category or "unknown",
            meta={"packet": packet},
        )

        timestamp = datetime.now().strftime("%H:%M:%S")
        
        priority_emoji = {
            "low": "🟢",
            "medium": "🟡", 
            "high": "🟠",
            "critical": "🔴"
        }.get(effective_priority, "⚠️")
        
        category_names = {
            "iptal_iade": "İPTAL/İADE TALEBİ",
            "sikayet": "ŞİKAYET",
            "rezervasyon_degisiklik": "REZ. DEĞİŞİKLİK",
            "fiyat_pazarlik": "FİYAT PAZARLIK",
            "ozel_istek": "ÖZEL İSTEK",
            "acil_durum": "ACİL DURUM",
            "erken_gec": "ERKEN GİRİŞ/GEÇ ÇIKIŞ",
            "canli_destek": "CANLI DESTEK TALEBİ",
            "restoran_rezervasyon": "RESTORAN REZERVASYONU",
            "odeme_bildirimi": "ÖDEME BİLDİRİMİ",
        }
        
        cat_name = category_names.get(normalized_category, normalized_category.upper())
        
        message = f"""{priority_emoji} İNSANA DEVİR - {cat_name}

📱 Müşteri: {customer_phone}
💬 Mesajı: {customer_message[:200]}
🧾 Packet: {packet.get('packet_id')}
🧠 Intent: {packet.get('detected_intent')} (conf: {packet.get('confidence') if packet.get('confidence') is not None else 'n/a'})
📡 Source: {packet.get('source')}

📂 Kategori: {cat_name}
🎯 Öncelik: {effective_priority.upper()}
🚦 Trigger: {trigger_type.upper()}
⏱️ SLA: {sla_target_minutes} dk
🕘 Mesai: {"İÇİ" if within_business_hours else "DIŞI"}

⏰ Zaman: {timestamp}

👤 Müşteriye "size dönüş yapacağız" denildi.
📞 Manuel dönüş yapın!"""
        
        print(f"{priority_emoji} Admin'e handoff bildirimi gönderildi: {cat_name} ({trigger_type}, SLA={sla_target_minutes}dk)")
        # Kritik kural: human takeover/pause tetiklendiyse admin bildirimi asla sessizce düşmemeli.
        # Eğer tek admin numarası müşteri numarası ile aynıysa, exclusion kaldırılır ve yine gönderilir.
        if self._has_alternate_admin_target(customer_phone):
            admin_sent = await self.send_whatsapp_admin(message, exclude_phones=[customer_phone])
        else:
            print("⚠️ Handoff bildirimi fallback: admin ve müşteri aynı numara, exclusion kaldırıldı.")
            admin_sent = await self.send_whatsapp_admin(message, exclude_phones=[])

        chef_sent = False
        if normalized_category == "restoran_rezervasyon":
            chef_phone = self._normalize_phone(self.restaurant_chef_phone)
            customer_norm = self._normalize_phone(customer_phone)
            if chef_phone and chef_phone != customer_norm:
                chef_sent = await self.send_whatsapp_to_phone(chef_phone, message)
                if chef_sent:
                    print(f"✅ Chef bildirimi gönderildi: {chef_phone}")
                else:
                    print(f"⚠️ Chef bildirimi gönderilemedi: {chef_phone}")

        return admin_sent or chef_sent
    
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
        return await self.send_whatsapp_admin(message, exclude_phones=[customer_phone])
    
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

        return await self.send_whatsapp_admin(message, exclude_phones=[customer_phone])
    
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

        return await self.send_whatsapp_admin(message, exclude_phones=[customer_phone])


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
