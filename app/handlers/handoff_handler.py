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

from app.utils.message_utils import detect_language
from app.services.conversation_store import add_to_history, save_message
from app.services.metrics_service import record_metric


# ======================================================
# BİLGİ SORUSU TESPİTİ
# ======================================================
# Bu kalıplar varsa, mesaj BİLGİ SORUSU - iade/iptal talebi DEĞİL!

INFO_QUESTION_PATTERNS = [
    # Türkçe soru kalıpları
    'nedir', 'ne demek', 'ne anlama', 'fark nedir', 'farkı nedir', 'farkı ne',
    'arasındaki fark', 'arasında fark', 'hangisi', 'nasıl çalışır', 'nasıl oluyor',
    'ne zaman', 'kaç', 'kaçta', 'ne kadar sürer', 'politikanız', 'kuralınız',
    # Türkçe soru ekleri — ödeme/bilgi soruları yakalamak için
    'yapılıyor mu', 'yapiliyor mu', 'kabul ediyor mu', 'kabul ediliyor mu',
    'mümkün mü', 'mumkun mu', 'yapabilir miyim', 'yapabilir misiniz',
    'nelerdir', 'midir', 'mudur',
    'oluyor mu', 'yapabiliyor mu', 'edebiliyor mu',
    'sunuyor musunuz', 'sağlıyor musunuz', 'kabul ediliyor',
    'kabul ediyorsunuz', 'kabul ediyor musunuz',

    # İngilizce soru kalıpları
    'what is', "what's", 'what does', 'what are', 'what do',
    'difference between', 'difference of', 'the difference',
    'which one', 'which is', 'how does', 'how do', 'how is',
    'when is', 'when does', 'how long', 'how much',
    'your policy', 'the policy', 'rules for',
    'do you accept', 'do you have', 'is there', 'are there',
    'can i', 'can we', 'is it possible',

    # Karşılaştırma/bilgi talepleri
    'ile arasında', 'between', 'versus', 'vs',
    'hakkında bilgi', 'about', 'explain', 'açıkla', 'anlat', 'öğrenmek'
]

# İADE/İPTAL TALEBİ OLMAYAN TERİMLER
# Bu terimler "refund", "cancel", "iade" içerse bile, bunlar TERİM!
TERM_EXCEPTIONS = [
    'non-refundable', 'nonrefundable', 'no-refund', 'iade edilemez',
    'iade edilmeyen', 'iade yapılmaz', 'refundable', 'iade politikası',
    'cancellation policy', 'iptal politikası', 'refund policy',
    'free cancellation', 'ücretsiz iptal', 'esnek fiyat', 'flexible'
]


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
        'olur mu', 'olabilir mi', 'sağlayabilir',
        # Türkçe handoff tetikleyicileri - bunlar varsa bilgi sorusu DEĞİL!
        'indirim', 'pahalı', 'pazarlık', 'ucuz',
        'şikayet', 'memnun değil', 'berbat', 'rezalet',
        'süpriz', 'sürpriz', 'evlilik teklif', 'balayı',
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


# ======================================================
# İNSANA DEVİR ANAHTAR KELİMELERİ (YENİDEN TASARLANDI)
# ======================================================
# 6 kategori: iptal_iade, sikayet, canli_destek, fiyat_pazarlik, ozel_istek, acil_durum
# + restoran_rezervasyon (ayrı akış olarak)

HANDOFF_KEYWORDS = {
    # ─────────────────────────────────────────────────────
    # 1. İPTAL / İADE TALEPLERİ
    # ─────────────────────────────────────────────────────
    "iptal_iade": {
        "keywords": [
            # Türkçe - GERÇEK talepler (tek başına "iade" veya "iptal" yetmez!)
            "iptal etmek istiyorum", "iptal edin", "iptal et",
            "rezervasyonu iptal", "rezervasyonumu iptal",
            "iade istiyorum", "iade edin", "para iade", "paramı iade",
            "geri ödeme istiyorum", "geri ödeme", "paramı geri", "parayı geri",
            "depozito iade", "kaporamı iade",
            # İngilizce - GERÇEK talepler
            "want to cancel", "please cancel", "cancel my", "cancel the",
            "cancel reservation", "cancel booking",
            "want refund", "want a refund", "get refund", "need refund",
            "money back", "get my money",
            # Rusça
            "хочу отменить", "отмените", "отменить бронирование", "отменить бронь",
            "хочу возврат", "верните деньги", "возврат средств",
        ],
        "priority": "high",
        "message_tr": "İptal/iade talebinizi aldım. Rezervasyon ekibimiz en kısa sürede size dönüş yapacaktır.",
        "message_en": "I've received your cancellation/refund request. Our reservation team will contact you shortly.",
        "message_ru": "Ваш запрос на отмену/возврат принят. Наша команда по бронированию свяжется с вами в ближайшее время.",
    },

    # ─────────────────────────────────────────────────────
    # 2. ŞİKAYET
    # ─────────────────────────────────────────────────────
    "sikayet": {
        "keywords": [
            # Türkçe (daha spesifik -> false positive azalt)
            "şikayetim var", "şikayetçiyim", "şikayet etmek istiyorum",
            "memnun değilim", "memnuniyetsiz",
            "berbat", "rezalet", "kabul edilemez",
            "çok kötü", "hiç beğenmedim", "iğrenç",
            # İngilizce
            "i have a complaint", "make a complaint", "complaint about",
            "not happy", "not satisfied", "terrible",
            "unacceptable", "disgusting", "awful", "horrible",
            "worst experience",
            # Rusça
            "жалоба", "хочу пожаловаться", "недоволен", "недовольна",
            "ужасно", "отвратительно", "неприемлемо",
        ],
        "priority": "critical",
        "message_tr": "Yaşadığınız durumdan dolayı çok üzgünüz. Yöneticimiz en kısa sürede sizinle iletişime geçecektir.",
        "message_en": "We're very sorry about your experience. Our manager will contact you as soon as possible.",
        "message_ru": "Нам очень жаль о вашем опыте. Наш менеджер свяжется с вами в ближайшее время.",
    },

    # ─────────────────────────────────────────────────────
    # 3. CANLI DESTEK TALEBİ
    # ─────────────────────────────────────────────────────
    "canli_destek": {
        "keywords": [
            # Türkçe
            "canlı destek", "canlı müşteri", "gerçek kişi",
            "yetkili ile", "yetkiliye", "yetkiliye bağla",
            "müdür", "temsilci", "insan ile", "insanla görüşmek",
            "birine bağla", "bağlar mısın", "bağlayın", "bağla beni",
            "operatör", "müşteri hizmetleri",
            # İngilizce
            "real person", "speak to someone", "human agent", "live support",
            "talk to manager", "representative", "live chat",
            "connect me", "transfer me",
            # Rusça
            "живой оператор", "живая поддержка", "настоящий человек",
            "менеджер", "представитель", "соедините с человеком",
        ],
        "priority": "medium",
        "message_tr": "Tabii, sizi canlı müşteri temsilcimize bağlıyorum. Lütfen biraz bekleyiniz.",
        "message_en": "Of course, I'm connecting you to our live customer representative. Please wait a moment.",
        "message_ru": "Конечно, соединяю вас с нашим представителем. Пожалуйста, подождите немного.",
    },

    # ─────────────────────────────────────────────────────
    # 4. FİYAT PAZARLIK / İNDİRİM TALEBİ
    # ─────────────────────────────────────────────────────
    "fiyat_pazarlik": {
        "keywords": [
            # Türkçe
            "indirim yapabilir", "indirim yapar mısınız", "indirim var mı",
            "çok pahalı", "fiyat düşer mi", "pazarlık",
            "fiyatı düşürün", "fiyat kırar mısınız", "fiyat kırın",
            "daha uygun", "daha ucuz olur mu",
            # İngilizce
            "discount", "too expensive", "lower price", "best price",
            "negotiate", "can you reduce", "cheaper rate",
            "special offer", "better deal",
            # Rusça
            "скидка", "слишком дорого", "снизить цену", "лучшая цена",
            "дешевле", "специальное предложение",
        ],
        "priority": "medium",
        "message_tr": "Fiyat talebinizi ilettim. Rezervasyon ekibimiz size özel bir teklif için dönüş yapacaktır.",
        "message_en": "I've forwarded your request. Our reservation team will contact you with a special offer.",
        "message_ru": "Ваш запрос передан. Наша команда по бронированию свяжется с вами со специальным предложением.",
    },

    # ─────────────────────────────────────────────────────
    # 5. ÖZEL İSTEK (Kutlama, romantik, sürpriz)
    # ─────────────────────────────────────────────────────
    "ozel_istek": {
        "keywords": [
            # Türkçe
            "evlilik teklifi", "sürpriz", "doğum günü kutlama",
            "yıldönümü", "balayı", "özel kutlama",
            "romantik akşam", "romantik süpriz",
            "pasta sipariş", "çiçek süsleme",
            # İngilizce
            "proposal", "surprise", "birthday celebration",
            "anniversary", "honeymoon", "romantic",
            "special celebration", "special arrangement",
            # Rusça
            "предложение руки", "сюрприз", "день рождения",
            "годовщина", "медовый месяц", "романтический",
            "особое торжество",
        ],
        "priority": "medium",
        "message_tr": "Özel gününüz için elimizden gelenin en iyisini yapmak istiyoruz. Ekibimiz detayları görüşmek için sizinle iletişime geçecektir.",
        "message_en": "We want to make your special day perfect. Our team will contact you to discuss the details.",
        "message_ru": "Мы хотим сделать ваш особенный день идеальным. Наша команда свяжется с вами для обсуждения деталей.",
    },

    # ─────────────────────────────────────────────────────
    # 6. ACİL DURUM
    # ─────────────────────────────────────────────────────
    "acil_durum": {
        "keywords": [
            # Türkçe
            "bugün giriş yapmam lazım", "bugün geliyorum",
            "acil transfer", "acil ulaşım",
            "uçak rötar", "uçağım rötar", "uçağımı kaçırdım",
            "şimdi gelmek istiyorum", "acil yardım",
            # İngilizce
            "today check-in", "arriving today",
            "urgent transfer", "emergency",
            "flight delay", "flight delayed", "missed my flight",
            "need immediate help", "urgent help",
            # Rusça
            "сегодня заезд", "приезжаю сегодня",
            "срочный трансфер", "экстренно",
            "задержка рейса", "опоздал на рейс",
            "срочная помощь",
        ],
        "priority": "critical",
        "message_tr": "Acil talebinizi aldım. Ekibimiz en kısa sürede sizinle iletişime geçecektir. Acil durumlarda +90 533 250 32 77 numarasını da arayabilirsiniz.",
        "message_en": "I've received your urgent request. Our team will contact you immediately. For emergencies, you can also call +90 533 250 32 77.",
        "message_ru": "Ваш срочный запрос принят. Наша команда немедленно свяжется с вами. По экстренным вопросам звоните +90 533 250 32 77.",
    },

    # ─────────────────────────────────────────────────────
    # RESTORAN REZERVASYONU (ayrı akış başlatıyor, direkt handoff değil)
    # ─────────────────────────────────────────────────────
    "restoran_rezervasyon": {
        "keywords": [
            # Türkçe - Temel
            "restoran rezervasyon", "restoranınızdan rezervasyon", "restorandan rezervasyon",
            "masa ayırt", "masa rezerv", "masa ayırtmak", "masa rezervasyonu",
            "yemek rezervasyonu", "yemek için rezervasyon",
            # Türkçe - Öğünler
            "akşam yemeği rezerv", "akşam yemeği için", "öğle yemeği için", "kahvaltı için rezerv",
            "akşam için masa", "öğle için masa",
            # Türkçe - Kutlamalar
            "doğum günü için restoran", "doğum günü için masa", "doğum günü rezervasyon",
            "yıldönümü için restoran", "yıldönümü için masa", "kutlama için masa",
            "özel gün için masa", "sürpriz için masa",
            # İngilizce
            "restaurant reservation", "book a table", "table reservation",
            "book table", "reserve a table", "reserve table",
            "book for dinner", "dinner reservation", "lunch reservation", "breakfast reservation",
            "can i book", "i want to book", "i'd like to book", "i would like to book",
            "make a reservation", "get a table", "table for",
            "birthday reservation", "birthday dinner", "anniversary dinner",
            "celebration dinner", "special occasion",
            # Rusça
            "бронь ресторана", "забронировать столик", "заказать столик",
            "ужин бронирование", "обед бронирование",
        ],
        "priority": "medium",
        "message_tr": "Restoran rezervasyonu için talebinizi aldım. Ekibimiz müsaitlik kontrolü yapıp size dönüş yapacaktır.",
        "message_en": "I've received your restaurant reservation request. Our team will check availability and contact you.",
        "message_ru": "Ваш запрос на бронирование ресторана принят. Наша команда проверит наличие мест и свяжется с вами.",
    },
}


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
    for category, data in HANDOFF_KEYWORDS.items():
        for keyword in data["keywords"]:
            if keyword in text_lower:
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
                customer_message=user_message
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
