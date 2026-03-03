from __future__ import annotations

from typing import Dict


# Shared info-question filters used by handoff and critical detectors.
HANDOFF_INFO_QUESTION_PATTERNS = [
    'nedir', 'ne demek', 'ne anlama', 'fark nedir', 'farkı nedir', 'farkı ne',
    'arasındaki fark', 'arasında fark', 'hangisi', 'nasıl çalışır', 'nasıl oluyor',
    'ne zaman', 'kaç', 'kaçta', 'ne kadar sürer', 'politikanız', 'kuralınız',
    'yapılıyor mu', 'yapiliyor mu', 'kabul ediyor mu', 'kabul ediliyor mu',
    'mümkün mü', 'mumkun mu', 'yapabilir miyim', 'yapabilir misiniz',
    'nelerdir', 'midir', 'mudur',
    'oluyor mu', 'yapabiliyor mu', 'edebiliyor mu',
    'sunuyor musunuz', 'sağlıyor musunuz', 'kabul ediliyor',
    'kabul ediyorsunuz', 'kabul ediyor musunuz',
    'what is', "what's", 'what does', 'what are', 'what do',
    'difference between', 'difference of', 'the difference',
    'which one', 'which is', 'how does', 'how do', 'how is',
    'when is', 'when does', 'how long', 'how much',
    'your policy', 'the policy', 'rules for',
    'do you accept', 'do you have', 'is there', 'are there',
    'can i', 'can we', 'is it possible',
    'ile arasında', 'between', 'versus', 'vs',
    'hakkında bilgi', 'about', 'explain', 'açıkla', 'anlat', 'öğrenmek',
]

HANDOFF_TERM_EXCEPTIONS = [
    'non-refundable', 'nonrefundable', 'no-refund', 'iade edilemez',
    'iade edilmeyen', 'iade yapılmaz', 'refundable', 'iade politikası',
    'cancellation policy', 'iptal politikası', 'refund policy',
    'free cancellation', 'ücretsiz iptal', 'esnek fiyat', 'flexible',
]

# Central handoff category dictionary for detector + response templates.
HANDOFF_KEYWORDS = {
    "iptal_iade": {
        "keywords": [
            "iptal etmek istiyorum", "iptal edin", "iptal et",
            "rezervasyonu iptal", "rezervasyonumu iptal",
            "iade istiyorum", "iade edin", "para iade", "paramı iade",
            "geri ödeme istiyorum", "geri ödeme", "paramı geri", "parayı geri",
            "depozito iade", "kaporamı iade",
            "erken çıkmamız gerek", "erken cikmamiz gerek", "erken çıkış",
            "erken cikis", "kullanmadığımız geceler", "kullanmadigimiz geceler",
            "kullanılmayan geceler", "kullanilmayan geceler",
            "kısmi iade", "kismi iade", "iade alabilir miyiz", "iade alabilir miyim",
            "want to cancel", "please cancel", "cancel my", "cancel the",
            "cancel reservation", "cancel booking",
            "want refund", "want a refund", "get refund", "need refund",
            "money back", "get my money",
            "хочу отменить", "отмените", "отменить бронирование", "отменить бронь",
            "хочу возврат", "верните деньги", "возврат средств",
        ],
        "priority": "high",
        "message_tr": "İptal/iade talebinizi aldım. Rezervasyon ekibimiz en kısa sürede size dönüş yapacaktır.",
        "message_en": "I've received your cancellation/refund request. Our reservation team will contact you shortly.",
        "message_ru": "Ваш запрос на отмену/возврат принят. Наша команда по бронированию свяжется с вами в ближайшее время.",
    },
    "sikayet": {
        "keywords": [
            "şikayetim var", "şikayetçiyim", "şikayet etmek istiyorum",
            "memnun değilim", "memnuniyetsiz",
            "berbat", "rezalet", "kabul edilemez",
            "çok kötü", "hiç beğenmedim", "iğrenç",
            "i have a complaint", "make a complaint", "complaint about",
            "not happy", "not satisfied", "terrible",
            "unacceptable", "disgusting", "awful", "horrible",
            "worst experience",
            "жалоба", "хочу пожаловаться", "недоволен", "недовольна",
            "ужасно", "отвратительно", "неприемлемо",
        ],
        "priority": "critical",
        "message_tr": "Yaşadığınız durumdan dolayı çok üzgünüz. Yöneticimiz en kısa sürede sizinle iletişime geçecektir.",
        "message_en": "We're very sorry about your experience. Our manager will contact you as soon as possible.",
        "message_ru": "Нам очень жаль о вашем опыте. Наш менеджер свяжется с вами в ближайшее время.",
    },
    "canli_destek": {
        "keywords": [
            "canlı destek", "canlı müşteri", "gerçek kişi",
            "yetkili ile", "yetkiliye", "yetkiliye bağla",
            "müdür", "temsilci", "insan ile", "insanla görüşmek",
            "birine bağla", "bağlar mısın", "bağlayın", "bağla beni",
            "operatör", "müşteri hizmetleri",
            "real person", "speak to someone", "human agent", "live support",
            "talk to manager", "representative", "live chat",
            "connect me", "transfer me",
            "живой оператор", "живая поддержка", "настоящий человек",
            "менеджер", "представитель", "соедините с человеком",
        ],
        "priority": "medium",
        "message_tr": "Tabii, sizi canlı müşteri temsilcimize bağlıyorum. Lütfen biraz bekleyiniz.",
        "message_en": "Of course, I'm connecting you to our live customer representative. Please wait a moment.",
        "message_ru": "Конечно, соединяю вас с нашим представителем. Пожалуйста, подождите немного.",
    },
    "fiyat_pazarlik": {
        "keywords": [
            "indirim yapabilir", "indirim yapar mısınız", "indirim var mı",
            "çok pahalı", "fiyat düşer mi", "pazarlık",
            "fiyatı düşürün", "fiyat kırar mısınız", "fiyat kırın",
            "daha uygun", "daha ucuz olur mu",
            "discount", "too expensive", "lower price", "best price",
            "negotiate", "can you reduce", "cheaper rate",
            "special offer", "better deal",
            "скидка", "слишком дорого", "снизить цену", "лучшая цена",
            "дешевле", "специальное предложение",
        ],
        "priority": "medium",
        "message_tr": "Fiyat talebinizi ilettim. Rezervasyon ekibimiz size özel bir teklif için dönüş yapacaktır.",
        "message_en": "I've forwarded your request. Our reservation team will contact you with a special offer.",
        "message_ru": "Ваш запрос передан. Наша команда по бронированию свяжется с вами со специальным предложением.",
    },
    "ozel_istek": {
        "keywords": [
            "evlilik teklifi", "sürpriz", "doğum günü kutlama",
            "yıldönümü", "balayı", "özel kutlama",
            "romantik akşam", "romantik süpriz",
            "pasta sipariş", "çiçek süsleme",
            "balayi", "susleme", "cicek", "romantik masa",
            "oda surprizi", "odaya cicek", "odaya çiçek", "odaya not",
            "geç check-in", "gec check-in", "gece giriş", "gece giris",
            "01:30 giriş", "01:30 giris", "01.30 giriş", "01.30 giris",
            "anahtar teslimi",
            "proposal", "surprise", "birthday celebration",
            "anniversary", "honeymoon", "romantic",
            "special celebration", "special arrangement",
            "late check-in", "night check-in", "key handover",
            "предложение руки", "сюрприз", "день рождения",
            "годовщина", "медовый месяц", "романтический",
            "особое торжество",
        ],
        "priority": "medium",
        "message_tr": "Özel gününüz için elimizden gelenin en iyisini yapmak istiyoruz. Ekibimiz detayları görüşmek için sizinle iletişime geçecektir.",
        "message_en": "We want to make your special day perfect. Our team will contact you to discuss the details.",
        "message_ru": "Мы хотим сделать ваш особенный день идеальным. Наша команда свяжется с вами для обсуждения деталей.",
    },
    "acil_durum": {
        "keywords": [
            "bugün giriş yapmam lazım", "bugün geliyorum",
            "acil transfer", "acil ulaşım",
            "uçak rötar", "uçağım rötar", "uçağımı kaçırdım",
            "şimdi gelmek istiyorum", "acil yardım",
            "today check-in", "arriving today",
            "urgent transfer", "emergency",
            "flight delay", "flight delayed", "missed my flight",
            "need immediate help", "urgent help",
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
    "restoran_rezervasyon": {
        "keywords": [
            "restoran rezervasyon", "restoranınızdan rezervasyon", "restorandan rezervasyon",
            "masa ayırt", "masa rezerv", "masa ayırtmak", "masa rezervasyonu",
            "yemek rezervasyonu", "yemek için rezervasyon",
            "akşam yemeği rezerv", "akşam yemeği için", "öğle yemeği için", "kahvaltı için rezerv",
            "akşam için masa", "öğle için masa",
            "doğum günü için restoran", "doğum günü için masa", "doğum günü rezervasyon",
            "yıldönümü için restoran", "yıldönümü için masa", "kutlama için masa",
            "özel gün için masa", "sürpriz için masa",
            "restaurant reservation", "book a table", "table reservation",
            "book table", "reserve a table", "reserve table",
            "book for dinner", "dinner reservation", "lunch reservation", "breakfast reservation",
            "can i book", "i want to book", "i'd like to book", "i would like to book",
            "make a reservation", "get a table", "table for",
            "birthday reservation", "birthday dinner", "anniversary dinner",
            "celebration dinner", "special occasion",
            "бронь ресторана", "забронировать столик", "заказать столик",
            "ужин бронирование", "обед бронирование",
        ],
        "priority": "medium",
        "message_tr": "Restoran rezervasyonu için talebinizi aldım. Ekibimiz müsaitlik kontrolü yapıp size dönüş yapacaktır.",
        "message_en": "I've received your restaurant reservation request. Our team will check availability and contact you.",
        "message_ru": "Ваш запрос на бронирование ресторана принят. Наша команда проверит наличие мест и свяжется с вами.",
    },
}


# Central hard-takeover reasons used by price flow.
PRICE_HARD_HANDOFF_REASONS = {
    "price_negotiation",
    "group_pricing",
    "special_contract",
    "fiyat_sistemi_hatasi",
    "multi_room_quote_failed",
}

# Unknown-guard auto-intents that should not be treated as out-of-scope for handoff.
KNOWN_AUTO_INTENTS = {
    "PRICE_QUERY",
    "AVAILABILITY_QUERY",
    "HOTEL_BOOKING_CREATE",
    "HOTEL_BOOKING_MODIFY",
    "HOTEL_BOOKING_CANCEL",
    "RESTAURANT_BOOKING_CREATE",
    "RESTAURANT_BOOKING_MODIFY",
    "RESTAURANT_BOOKING_CANCEL",
    "PAYMENT_METHOD_QUERY",
    "PAYMENT_LINK_REQUEST",
    "LOCAL_FAQ_INFO",
}

# Global handoff policy map.
HANDOFF_BUSINESS_HOURS = {"start_hour": 7, "end_hour": 2}
DEFAULT_SLA_MINUTES = {"hard": 10, "soft": 30}
HANDOFF_POLICY_BY_CATEGORY: Dict[str, Dict[str, str | int]] = {
    "acil_durum": {"trigger_type": "hard", "min_priority": "critical", "sla_minutes": 10},
    "sikayet": {"trigger_type": "hard", "min_priority": "high", "sla_minutes": 10},
    "iptal_iade": {"trigger_type": "hard", "min_priority": "high", "sla_minutes": 15},
    "odeme_bildirimi": {"trigger_type": "hard", "min_priority": "high", "sla_minutes": 10},
    "security_concern": {"trigger_type": "hard", "min_priority": "critical", "sla_minutes": 10},
    "fiyat_sistemi_hatasi": {"trigger_type": "hard", "min_priority": "high", "sla_minutes": 15},
    "quiet_room_live_required": {"trigger_type": "soft", "min_priority": "medium", "sla_minutes": 30},
    "fiyat_handoff": {"trigger_type": "soft", "min_priority": "medium", "sla_minutes": 30},
    "fiyat_pazarlik": {"trigger_type": "soft", "min_priority": "medium", "sla_minutes": 30},
    "ozel_istek": {"trigger_type": "soft", "min_priority": "medium", "sla_minutes": 30},
    "canli_destek": {"trigger_type": "soft", "min_priority": "medium", "sla_minutes": 20},
    "restoran_rezervasyon": {"trigger_type": "soft", "min_priority": "medium", "sla_minutes": 20},
    "antalya_transfer": {"trigger_type": "soft", "min_priority": "medium", "sla_minutes": 30},
    "flow_orchestrator_handoff": {"trigger_type": "soft", "min_priority": "medium", "sla_minutes": 30},
}
PRIORITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}
RANK_PRIORITY = {v: k for k, v in PRIORITY_RANK.items()}


# Critical issue detection catalog.
CRITICAL_ISSUE_CATEGORIES = {
    'complaint': {
        'priority': 5,
        'keywords_tr': ['berbat', 'rezalet', 'kötü', 'iğrenç', 'korkunç', 'skandal', 'utanç', 'fiyasko', 'felaket', 'şikayet', 'memnuniyetsiz'],
        'keywords_en': ['terrible', 'horrible', 'awful', 'disgusting', 'worst', 'unacceptable', 'complaint', 'disappointed', 'angry', 'furious'],
        'auto_response_tr': 'Yaşadığınız olumsuz deneyim için çok üzgünüz. Konuyu en kısa sürede çözmek için müşteri temsilcimiz sizinle iletişime geçecektir.',
        'auto_response_en': 'We are very sorry for the negative experience. Our customer representative will contact you shortly to resolve this issue.',
        'notify_immediately': True,
    },
    'cancellation': {
        'priority': 5,
        'keywords_tr': ['iade istiyorum', 'paramı geri', 'geri iade', 'para iadesi', 'iade talep'],
        'keywords_en': ['want refund', 'get refund', 'money back', 'request refund', 'refund please'],
        'auto_response_tr': 'İade talebinizi aldık. İşleminiz için sizinle en kısa sürede iletişime geçeceğiz.',
        'auto_response_en': 'We received your refund request. We will contact you shortly.',
        'notify_immediately': True,
    },
    'emergency': {
        'priority': 5,
        'keywords_tr': ['acil yardım', 'acil durum', 'acil destek', 'ambulans', 'kaza', 'hastayım', 'tehlike', 'kayboldum'],
        'keywords_en': ['emergency', 'need help now', 'send help', 'sick', 'accident', 'lost', 'danger', 'ambulance'],
        'auto_response_tr': 'Acil durumunuz için hemen yardım gönderiyoruz. Otel telefonu: +90 533 250 32 77',
        'auto_response_en': 'We are sending help immediately for your emergency. Hotel phone: +90 533 250 32 77',
        'notify_immediately': True,
    },
    'security_concern': {
        'priority': 5,
        'keywords_tr': ['güvenlik', 'hırsızlık', 'çalındı', 'kasa', 'tehdit', 'hırsız'],
        'keywords_en': ['security', 'theft', 'stolen', 'safe', 'threat', 'thief'],
        'auto_response_tr': 'Güvenlik ekibimiz derhal bilgilendirildi. En kısa sürede size dönüş yapılacaktır.',
        'auto_response_en': 'Our security team has been notified immediately. You will be contacted shortly.',
        'notify_immediately': True,
    },
    'negative_review_threat': {
        'priority': 2,
        'keywords_tr': ['google yorum', 'kötü yorum', 'şikayet edeceğim', 'tripadvisor'],
        'keywords_en': ['google review', 'bad review', 'will complain', 'tripadvisor'],
        'auto_response_tr': None,
        'auto_response_en': None,
        'notify_immediately': False,
    },
    'payment_issue': {
        'priority': 2,
        'keywords_tr': ['fatura', 'çekim yapılmış', 'yanlış ücret'],
        'keywords_en': ['invoice', 'wrong charge', 'overcharged'],
        'auto_response_tr': None,
        'auto_response_en': None,
        'notify_immediately': False,
    },
    'health_hygiene': {
        'priority': 2,
        'keywords_tr': ['böcek', 'kirli', 'pis', 'hijyen', 'hamam böceği'],
        'keywords_en': ['bug', 'dirty', 'unclean', 'hygiene', 'cockroach', 'insect'],
        'auto_response_tr': None,
        'auto_response_en': None,
        'notify_immediately': False,
    },
}

CRITICAL_INFO_QUESTION_PATTERNS = [
    'nedir', 'ne demek', 'ne anlama', 'fark nedir', 'farkı nedir', 'farkı ne',
    'arasındaki fark', 'arasında fark', 'hangisi', 'nasıl', 'ne zaman',
    'kaç', 'kaçta', 'saat kaç', 'ne kadar sürer',
    'what is', "what's", 'what does', 'what are',
    'difference between', 'difference of', 'the difference',
    'which one', 'which is', 'how does', 'how do', 'how is',
    'when is', 'when does', 'how long', 'how much',
    'ile', 'arasında', 'between', 'versus', 'vs',
    'hakkında bilgi', 'about', 'explain', 'açıkla', 'anlat',
]

CRITICAL_TERM_EXCEPTIONS = [
    'non-refundable', 'nonrefundable', 'no-refund', 'iade edilemez',
    'iade edilmeyen', 'iade yapılmaz', 'refundable', 'iade politikası',
    'cancellation policy', 'iptal politikası', 'refund policy',
]

NOTIFICATION_SETTINGS = {
    'active_hours': {'start': 7, 'end': 2},
    'night_contact': '+905304498453',
    'escalation_minutes': [0, 10, 30],
}
