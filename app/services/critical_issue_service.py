from datetime import datetime
from typing import Tuple

CRITICAL_ISSUE_CATEGORIES = {
    'complaint': {
        'priority': 5,
        'keywords_tr': ['berbat', 'rezalet', 'kötü', 'iğrenç', 'korkunç', 'skandal', 
                        'utanç', 'fiyasko', 'felaket', 'şikayet', 'memnuniyetsiz'],
        'keywords_en': ['terrible', 'horrible', 'awful', 'disgusting', 'worst',
                        'unacceptable', 'complaint', 'disappointed', 'angry', 'furious'],
        'auto_response_tr': 'Yaşadığınız olumsuz deneyim için çok üzgünüz. Konuyu en kısa sürede çözmek için müşteri temsilcimiz sizinle iletişime geçecektir.',
        'auto_response_en': 'We are very sorry for the negative experience. Our customer representative will contact you shortly to resolve this issue.',
        'notify_immediately': True
    },
    'cancellation': {
        'priority': 5,
        # NOT: "refund" ve "iade" sadece GERÇEK İADE TALEBİ için tetiklenmeli
        # "Non-refundable nedir?" gibi BİLGİ sorularında tetiklenmemeli!
        'keywords_tr': ['iade istiyorum', 'paramı geri', 'geri iade', 'para iadesi', 'iade talep'],
        'keywords_en': ['want refund', 'get refund', 'money back', 'request refund', 'refund please'],
        'auto_response_tr': 'İade talebinizi aldık. İşleminiz için sizinle en kısa sürede iletişime geçeceğiz.',
        'auto_response_en': 'We received your refund request. We will contact you shortly.',
        'notify_immediately': True
    },
    'emergency': {
        'priority': 5,
        'keywords_tr': ['acil yardım', 'acil durum', 'acil destek', 'ambulans', 'kaza', 'hastayım', 'tehlike', 'kayboldum'],
        'keywords_en': ['emergency', 'need help now', 'send help', 'sick', 'accident', 'lost', 'danger', 'ambulance'],
        'auto_response_tr': 'Acil durumunuz için hemen yardım gönderiyoruz. Otel telefonu: +90 533 250 32 77',
        'auto_response_en': 'We are sending help immediately for your emergency. Hotel phone: +90 533 250 32 77',
        'notify_immediately': True
    },
    'security_concern': {
        'priority': 5,
        'keywords_tr': ['güvenlik', 'hırsızlık', 'çalındı', 'kasa', 'tehdit', 'hırsız'],
        'keywords_en': ['security', 'theft', 'stolen', 'safe', 'threat', 'thief'],
        'auto_response_tr': 'Güvenlik ekibimiz derhal bilgilendirildi. En kısa sürede size dönüş yapılacaktır.',
        'auto_response_en': 'Our security team has been notified immediately. You will be contacted shortly.',
        'notify_immediately': True
    },
    'negative_review_threat': {
        'priority': 2,
        'keywords_tr': ['google yorum', 'kötü yorum', 'şikayet edeceğim', 'tripadvisor'],
        'keywords_en': ['google review', 'bad review', 'will complain', 'tripadvisor'],
        'auto_response_tr': None,
        'auto_response_en': None,
        'notify_immediately': False
    },
    'payment_issue': {
        'priority': 2,
        'keywords_tr': ['fatura', 'çekim yapılmış', 'yanlış ücret'],
        'keywords_en': ['invoice', 'wrong charge', 'overcharged'],
        'auto_response_tr': None,
        'auto_response_en': None,
        'notify_immediately': False
    },
    'health_hygiene': {
        'priority': 2,
        'keywords_tr': ['böcek', 'kirli', 'pis', 'hijyen', 'hamam böceği'],
        'keywords_en': ['bug', 'dirty', 'unclean', 'hygiene', 'cockroach', 'insect'],
        'auto_response_tr': None,
        'auto_response_en': None,
        'notify_immediately': False
    }
}

# BİLGİ SORUSU KALIPLARI
# Bu kalıplar varsa, mesaj büyük ihtimalle bir BİLGİ SORUSU, şikayet/talep DEĞİL!
INFO_QUESTION_PATTERNS = [
    # Türkçe soru kalıpları
    'nedir', 'ne demek', 'ne anlama', 'fark nedir', 'farkı nedir', 'farkı ne',
    'arasındaki fark', 'arasında fark', 'hangisi', 'nasıl', 'ne zaman',
    'kaç', 'kaçta', 'saat kaç', 'ne kadar sürer',
    
    # İngilizce soru kalıpları  
    'what is', "what's", 'what does', 'what are',
    'difference between', 'difference of', 'the difference',
    'which one', 'which is', 'how does', 'how do', 'how is',
    'when is', 'when does', 'how long', 'how much',
    
    # Karşılaştırma/bilgi talepleri
    'ile', 'arasında', 'between', 'versus', 'vs',
    'hakkında bilgi', 'about', 'explain', 'açıkla', 'anlat'
]

# İADE TALEBİ OLMAYAN TERİMLER
# Bu terimler "refund" veya "iade" içerse bile, bunlar TERIM, talep değil!
TERM_EXCEPTIONS = [
    'non-refundable', 'nonrefundable', 'no-refund', 'iade edilemez',
    'iade edilmeyen', 'iade yapılmaz', 'refundable', 'iade politikası',
    'cancellation policy', 'iptal politikası', 'refund policy'
]

NOTIFICATION_SETTINGS = {
    'active_hours': {
        'start': 7,   # 07:00
        'end': 2      # 02:00 (ertesi gün)
    },
    'night_contact': '+905304498453',
    'escalation_minutes': [0, 10, 30]
}

def is_within_notification_hours() -> bool:
    """Bildirim saatleri içinde mi kontrol et"""
    current_hour = datetime.now().hour
    start = NOTIFICATION_SETTINGS['active_hours']['start']
    end = NOTIFICATION_SETTINGS['active_hours']['end']
    
    if end < start:
        return current_hour >= start or current_hour < end
    else:
        return start <= current_hour < end

def is_info_question(message: str) -> bool:
    """
    Mesajın bir BİLGİ SORUSU olup olmadığını kontrol et.
    BİLGİ soruları şikayet/talep olarak işlenmemeli!
    """
    msg_lower = message.lower()
    
    # 1. Soru kalıbı var mı?
    has_question_pattern = any(pattern in msg_lower for pattern in INFO_QUESTION_PATTERNS)
    
    # 2. Terim istisnası var mı? (non-refundable, iade politikası, vb.)
    has_term_exception = any(term in msg_lower for term in TERM_EXCEPTIONS)
    
    # 3. Soru işareti var mı?
    has_question_mark = '?' in message
    
    # Eğer soru kalıbı veya terim istisnası varsa, BİLGİ SORUSU
    if has_question_pattern or has_term_exception:
        return True
    
    # Soru işareti varsa ve mesaj kısa değilse (>10 karakter), muhtemelen bilgi sorusu
    if has_question_mark and len(message) > 10:
        return True
    
    return False

def detect_critical_issue(message: str) -> Tuple[bool, str, int, dict]:
    """
    Kritik sorun tespit et.
    
    ÖNEMLİ: BİLGİ SORULARINI şikayet/talep olarak algılama!
    - "Non-refundable nedir?" → BİLGİ SORUSU (kritik değil)
    - "İade istiyorum!" → İADE TALEBİ (kritik)
    
    Returns: (is_critical, category, priority, category_info)
    """
    msg_lower = message.lower()
    
    # ═══════════════════════════════════════════════════════════════
    # ÖNCE: Bu bir BİLGİ SORUSU mu kontrol et!
    # BİLGİ sorularını şikayet/talep olarak işleme!
    # ═══════════════════════════════════════════════════════════════
    if is_info_question(message):
        # Bu bir bilgi sorusu - kritik sorun olarak işleme!
        return False, None, 0, {}
           
    # ═══════════════════════════════════════════════════════════════
    # SONRA: Gerçek kritik sorunları tespit et
    # ═══════════════════════════════════════════════════════════════
    for category, info in CRITICAL_ISSUE_CATEGORIES.items():
        keywords_tr = info.get('keywords_tr', [])
        keywords_en = info.get('keywords_en', [])
        
        for keyword in keywords_tr + keywords_en:
            if keyword in msg_lower:
                return True, category, info['priority'], info
    
    return False, None, 0, {}
