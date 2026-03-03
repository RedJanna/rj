from datetime import datetime
from typing import Tuple

from app.services.handoff_critical_registry import (
    CRITICAL_INFO_QUESTION_PATTERNS as INFO_QUESTION_PATTERNS,
    CRITICAL_ISSUE_CATEGORIES,
    CRITICAL_TERM_EXCEPTIONS as TERM_EXCEPTIONS,
    NOTIFICATION_SETTINGS,
)

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
