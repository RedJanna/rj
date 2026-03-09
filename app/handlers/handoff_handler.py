"""
Handoff Handler - İnsana Devir İşleyicisi

Bu modül kassandra_openai_bot.py'den ayrıştırılmıştır.
İnsana devir gerektiren durumları tespit eder ve yönetir.

GÜNCELLEME 2026-02-14:
- Tüm handoff kategorileri sıfırdan yeniden tasarlandı
- 6 kategori: iptal_iade, sikayet, canli_destek, fiyat_pazarlik, ozel_istek, acil_durum
- Kaldırılan kategoriler: erken_gec (KANONIK cevap oldu), rezervasyon_degisiklik (OpenAI cevaplar)
- Restoran rezervasyonu ayrı akış olarak korundu
- BİLGİ SORUSU tespiti korundu
"""

from __future__ import annotations

import time as time_module
from datetime import datetime
from typing import Optional, Tuple
import re

from app.utils.message_utils import detect_language
from app.services.conversation_store import add_to_history, save_message
from app.services.metrics_service import record_metric
from app.services.handoff_critical_registry import (
    HANDOFF_INFO_QUESTION_PATTERNS as INFO_QUESTION_PATTERNS,
    HANDOFF_KEYWORDS,
    HANDOFF_TERM_EXCEPTIONS as TERM_EXCEPTIONS,
)


def _turkish_lower(text: str) -> str:
    """Türkçe uyumlu küçük harf dönüşümü.

    Python'ın str.lower() metodu Türkçe İ → i̇ (i + combining dot) yapar.
    Bu da 'indirim' gibi keyword eşleşmelerini bozar.
    Bu fonksiyon İ → i ve I → ı dönüşümünü doğru yapar.
    """
    result = text.replace('İ', 'i').replace('I', 'ı')
    return result.lower()


def is_info_question(message: str) -> bool:
    """
    Mesajın bir BİLGİ SORUSU olup olmadığını kontrol et.
    BİLGİ soruları insana devir edilmemeli!

    Örnekler:
    - "Non-refundable nedir?" → BİLGİ SORUSU ✓
    - "İade politikanız nedir?" → BİLGİ SORUSU ✓
    - "İade istiyorum" → İADE TALEBİ (devir gerekli)
    """
    msg_lower = _turkish_lower(message)

    # 1. Soru kalıbı var mı?
    has_question_pattern = any(pattern in msg_lower for pattern in INFO_QUESTION_PATTERNS)

    # 2. Terim istisnası var mı? (non-refundable, iade politikası, vb.)
    has_term_exception = any(term in msg_lower for term in TERM_EXCEPTIONS)

    # 3. Soru işareti var mı?
    has_question_mark = '?' in message

    # Eğer soru kalıbı veya terim istisnası varsa, BİLGİ SORUSU
    if has_question_pattern or has_term_exception:
        return True

    # Soru işareti varsa ve mesaj TALEP belirteci içermiyorsa → bilgi sorusu
    # DİKKAT: Handoff keyword'lerini (şikayet, indirim, pazarlık, vb.) buradan geçirmeli!
    talep_indicators = [
        # Türkçe talep belirteçleri
        'istiyorum', 'isterim', 'yapın', 'edin', 'lütfen',
        'yapabilir misiniz', 'yapabilir misınız', 'mümkün mü',
        'ayarlayabilir misiniz', 'ayarlayabilir', 'organize edebilir',
        'olur mu', 'olabilir mi', 'sağlayabilir',
        # Türkçe handoff tetikleyicileri - bunlar varsa bilgi sorusu DEĞİL!
        'indirim', 'pahalı', 'pazarlık', 'ucuz',
        'şikayet', 'memnun değil', 'berbat', 'rezalet',
        'süpriz', 'sürpriz', 'evlilik teklif', 'balayı',
        'balayi', 'susleme', 'çiçek', 'cicek', 'romantik masa',
        'doğum günü', 'yıldönümü', 'kutlama', 'romantik',
        'iptal', 'iade', 'geri ödeme',
        'canlı destek', 'yetkili', 'gerçek kişi', 'operatör',
        'acil', 'hemen', 'bugün giriş', 'uçak rötar',
        # İngilizce talep belirteçleri
        'want', 'need', 'please do', 'can you', 'could you',
        'discount', 'expensive', 'negotiate',
        'complaint', 'terrible', 'unacceptable',
        'surprise', 'proposal', 'honeymoon', 'anniversary',
        'cancel', 'refund', 'money back',
        'real person', 'human agent', 'live support',
        'urgent', 'emergency', 'flight delay',
    ]
    has_talep = any(ind in msg_lower for ind in talep_indicators)

    if has_question_mark and not has_talep:
        return True

    return False


def _is_late_checkin_info_query(message: str) -> bool:
    """Geç check-in hakkında bilgi sorusunu handoff'tan muaf tut."""
    low = _turkish_lower(message or "")
    if not low:
        return False
    has_late_arrival = any(
        k in low
        for k in (
            "geç check-in", "gec check-in", "gece giriş", "gece giris",
            "late check-in", "late check in", "night check-in", "night check in",
            "check-in", "check in",
        )
    )
    has_question = ("?" in (message or "")) or any(
        q in low for q in ("olur mu", "mümkün mü", "mumkun mu", "sorun olur mu", "possible", "can i", "is it ok")
    )
    return has_late_arrival and has_question


def _is_quiet_room_live_handoff_query(message: str) -> bool:
    low = _turkish_lower(message or "")
    if not low:
        return False
    return ("sessiz oda" in low) or ("quiet room" in low)




def detect_handoff_required(text: str) -> Tuple[bool, str, str, str, str, str]:
    """
    İnsana devir gerekiyor mu kontrol et.

    ÖNEMLİ: BİLGİ SORULARINI devir etme!
    - "Non-refundable nedir?" → BİLGİ SORUSU (devir etme!)
    - "İade istiyorum!" → İADE TALEBİ (devir et)

    Args:
        text: Müşteri mesajı

    Returns:
        (needs_handoff: bool, category: str, priority: str, response_tr: str, response_en: str, response_ru: str)
    """
    text_lower = _turkish_lower(text)

    # ═══════════════════════════════════════════════════════════════
    # ÖNCE: Bu bir BİLGİ SORUSU mu kontrol et!
    # BİLGİ soruları insana devir edilmemeli - OpenAI cevaplayabilir!
    # ═══════════════════════════════════════════════════════════════
    if is_info_question(text):
        return (False, "", "", "", "", "")
    if _is_late_checkin_info_query(text):
        return (False, "", "", "", "", "")
    if _is_quiet_room_live_handoff_query(text):
        return (
            True,
            "quiet_room_live_required",
            "medium",
            "Sessiz oda talepleriniz canlı müşteri temsilcimiz tarafından yönetilmektedir. Sizi şimdi temsilcimize bağlıyorum.",
            "Quiet room requests are handled by our live representative. I am connecting you now.",
            "Запросы на тихий номер обрабатывает наш живой представитель. Подключаю вас сейчас.",
        )

    # ═══════════════════════════════════════════════════════════════
    # ÖZEL KONTROL: Restoran/masa + rezervasyon kombinasyonu
    # ═══════════════════════════════════════════════════════════════
    restoran_indicators = ["restoran", "masa", "yemek", "akşam", "öğle", "kahvaltı",
                          "restaurant", "table", "dinner", "lunch", "breakfast",
                          "ресторан", "столик", "ужин", "обед", "завтрак"]
    rezervasyon_indicators = ["rezervasyon", "ayırt", "ayır", "reservation", "book", "reserve",
                             "бронирование", "забронировать", "заказать"]
    special_occasion_indicators = ["doğum günü", "yıldönümü", "kutlama", "sürpriz", "özel gün",
                                   "birthday", "anniversary", "celebration", "surprise",
                                   "день рождения", "годовщина", "праздник", "сюрприз"]

    has_restoran = any(ind in text_lower for ind in restoran_indicators)
    has_rezervasyon = any(ind in text_lower for ind in rezervasyon_indicators)
    has_special = any(ind in text_lower for ind in special_occasion_indicators)

    # Restoran + Rezervasyon VEYA Özel Gün + Rezervasyon → Restoran rezervasyonu
    if (has_restoran and has_rezervasyon) or (has_special and has_rezervasyon):
        data = HANDOFF_KEYWORDS["restoran_rezervasyon"]
        return (False, "restoran_rezervasyon", data["priority"], data["message_tr"], data["message_en"], data.get("message_ru", data["message_en"]))

    # ═══════════════════════════════════════════════════════════════
    # Normal keyword kontrolü
    # ═══════════════════════════════════════════════════════════════
    has_stay_pricing_context = (
        any(k in text_lower for k in ("fiyat", "ucret", "ücret", "price", "cost", "musait", "müsait", "availability"))
        and any(
            k in text_lower
            for k in (
                "konaklama", "gece", "night",
                "yetiskin", "yetişkin", "adult", "check-in", "check in",
                "tarih", "date",
            )
        )
    )

    for category, data in HANDOFF_KEYWORDS.items():
        # Balayi/ozel kutlama kelimeleri fiyat sorgusuyla birlikte gelebilir.
        # Bu durumda once fiyat/musaitlik akisina izin ver; saf ozel-istek
        # talepleri (susleme, romantik masa vb.) yine handoff olur.
        if category == "ozel_istek" and has_stay_pricing_context:
            continue
        for keyword in data["keywords"]:
            kw = str(keyword or "").strip()
            if not kw:
                continue
            # Tek kelime ASCII keyword'lerde tam kelime eslesmesi kullan.
            # Boylece "discount" -> "discounted" yanlis pozitiflerini engelle.
            if re.fullmatch(r"[a-z]+", kw):
                if not re.search(rf"\b{re.escape(kw)}\b", text_lower):
                    continue
            elif kw not in text_lower:
                continue
            return (
                True,
                category,
                data["priority"],
                data["message_tr"],
                data["message_en"],
                data.get("message_ru", data["message_en"]),
            )

    return (False, "", "", "", "", "")


class HandoffHandler:
    """İnsana devir işleyicisi"""

    def __init__(self, notification_service=None):
        """
        Args:
            notification_service: Admin bildirim servisi
        """
        self.notification_service = notification_service

    async def handle(
        self,
        phone: str,
        user_message: str,
        start_time: float
    ) -> Tuple[bool, Optional[str], str]:
        """
        İnsana devir kontrolü yap.

        Args:
            phone: Müşteri telefon numarası
            user_message: Müşteri mesajı
            start_time: İşlem başlangıç zamanı

        Returns:
            (handled: bool, reply: str or None, status: str)
        """
        needs_handoff, category, priority, msg_tr, msg_en, msg_ru = detect_handoff_required(user_message)

        if not needs_handoff:
            return False, None, ""

        # Admin'e bildir
        if self.notification_service:
            await self.notification_service.notify_admin_handoff(
                category=category,
                priority=priority,
                customer_phone=phone or "Bilinmiyor",
                customer_message=user_message,
                source="handoff_handler",
                detected_intent="HUMAN_AGENT_REQUEST",
                confidence=1.0,
                conversation_summary=f"handoff_handler category={category}",
                attempted_actions=["detect_handoff_required"],
                suggested_reply=(msg_tr or msg_en or msg_ru or "")[:240],
                tags=["handoff_handler"],
            )

        # Müşteriye uygun dilde cevap ver
        lang = detect_language(user_message)
        if lang == "ru":
            reply = msg_ru
        elif lang == "en":
            reply = msg_en
        else:
            reply = msg_tr

        # Kaydet
        add_to_history(phone, "user", user_message)
        add_to_history(phone, "assistant", reply)
        save_message(phone, user_message, f"[İNSANA DEVİR - {category.upper()}] {reply}")

        # Metrik
        elapsed = time_module.time() - start_time
        record_metric("handoff", category=category, response_time=elapsed)

        return True, reply, f"handoff_{category}"

    def is_restaurant_reservation(self, text: str) -> bool:
        """Restoran rezervasyonu mu kontrol et"""
        _, category, _, _, _, _ = detect_handoff_required(text)
        return category == "restoran_rezervasyon"


# Singleton instance
_handoff_handler: Optional[HandoffHandler] = None

def get_handoff_handler(notification_service=None) -> HandoffHandler:
    """Singleton handoff handler döndür"""
    global _handoff_handler
    if _handoff_handler is None:
        _handoff_handler = HandoffHandler(notification_service)
    return _handoff_handler
