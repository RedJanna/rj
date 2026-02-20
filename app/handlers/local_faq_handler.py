"""
Local FAQ Handler - LOCAL Soru-Cevap İşleyicisi

Bu modül kassandra_openai_bot.py'den ayrıştırılmıştır.
Sık sorulan sorulara API çağırmadan yerel olarak cevap verir.
"""

from __future__ import annotations

import time as time_module
from typing import Optional, Tuple

from app.utils.message_utils import (
    LOCAL_FAQ, LOCAL_MAX_WORDS, check_local_faq,
    detect_language,
)
from app.content.local_faq_data import normalize_local_faq_reply
from app.services.conversation_store import add_to_history, save_message
from app.services.metrics_service import record_metric

def _normalize_local_reply(reply: str, category: str, lang: str) -> str:
    return normalize_local_faq_reply(reply, category, lang)

class LocalFAQHandler:
    """LOCAL FAQ işleyicisi - API çağırmadan cevap verir"""
    
    def __init__(self, followup_scheduler=None):
        """
        Args:
            followup_scheduler: schedule_followup fonksiyonu (opsiyonel)
        """
        self.schedule_followup = followup_scheduler
    
    def handle(
        self,
        phone: str,
        user_message: str,
        start_time: float
    ) -> Tuple[bool, Optional[str], str]:
        """
        LOCAL FAQ kontrolü yap.
        
        Args:
            phone: Müşteri telefon numarası
            user_message: Müşteri mesajı
            start_time: İşlem başlangıç zamanı
            
        Returns:
            (handled: bool, reply: str or None, status: str)
        """
        # LOCAL FAQ kontrolü
        found, answer_tr, answer_en, category, answer_ru = check_local_faq(user_message)

        if not found:
            return False, None, ""

        # Dil algıla
        lang = detect_language(user_message)
        if lang == "ru":
            reply = answer_ru
        elif lang == "en":
            reply = answer_en
        else:
            reply = answer_tr
        reply = _normalize_local_reply(reply, category, lang)

        
        # Kaydet
        add_to_history(phone, "user", user_message)
        add_to_history(phone, "assistant", reply)
        save_message(phone, user_message, f"[LOCAL:{category}] {reply}")
        
        # Followup planla
        if self.schedule_followup:
            self.schedule_followup(phone)
        
        # Metrik
        elapsed = time_module.time() - start_time
        record_metric("local_faq", category=category, response_time=elapsed)
        
        print(f"✅ LOCAL cevap verildi: {category} ({elapsed*1000:.0f}ms)")
        
        return True, reply, "local_faq"
    
    def get_categories(self) -> list:
        """Mevcut LOCAL FAQ kategorilerini döndür"""
        return list(LOCAL_FAQ.keys())
    
    def get_category_keywords(self, category: str) -> list:
        """Belirli bir kategorinin anahtar kelimelerini döndür"""
        if category in LOCAL_FAQ:
            return LOCAL_FAQ[category].get("keywords", [])
        return []
    
    def add_category(
        self, 
        category: str, 
        keywords: list, 
        answer_tr: str, 
        answer_en: str
    ) -> bool:
        """
        Yeni LOCAL FAQ kategorisi ekle.
        NOT: Bu değişiklik sadece runtime'da geçerli, dosyaya yazılmaz.
        """
        if category in LOCAL_FAQ:
            return False
        
        LOCAL_FAQ[category] = {
            "keywords": keywords,
            "answer_tr": answer_tr,
            "answer_en": answer_en
        }
        return True


# Singleton instance
_local_faq_handler: Optional[LocalFAQHandler] = None

def get_local_faq_handler(followup_scheduler=None) -> LocalFAQHandler:
    """Singleton local faq handler döndür"""
    global _local_faq_handler
    if _local_faq_handler is None:
        _local_faq_handler = LocalFAQHandler(followup_scheduler)
    return _local_faq_handler
