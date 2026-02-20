"""
Greeting Handler - Selamlama, Menü ve İlk Mesaj İşleyicisi

Bu modül kassandra_openai_bot.py'den ayrıştırılmıştır.
Selamlama mesajları, menü seçimleri ve ilk mesaj kontrollerini yönetir.
"""

from __future__ import annotations

import time as time_module
from typing import Optional, Tuple

from app.utils.message_utils import (
    is_greeting, get_welcome_message,
    is_menu_selection, get_menu_response,
    detect_language,
)
from app.services.conversation_store import (
    get_conversation_history, add_to_history, save_message,
)
from app.services.metrics_service import record_metric


class GreetingHandler:
    """Selamlama ve menü işleyicisi"""
    
    def __init__(self, followup_scheduler=None):
        """
        Args:
            followup_scheduler: schedule_followup fonksiyonu (opsiyonel)
        """
        self.schedule_followup = followup_scheduler
    
    def handle_first_message(
        self, 
        phone: str, 
        user_message: str, 
        history: list,
        start_time: float
    ) -> Tuple[bool, Optional[str], str]:
        """
        İlk mesaj kontrolü - yeni müşteri ise karşılama mesajı gönder.
        
        Args:
            phone: Müşteri telefon numarası
            user_message: Müşteri mesajı
            history: Konuşma geçmişi
            start_time: İşlem başlangıç zamanı
            
        Returns:
            (handled: bool, reply: str or None, status: str)
        """
        # History boşsa bu ilk mesaj
        if not history or len(history) == 0:
            # Dil algıla
            lang = detect_language(user_message)
            reply = get_welcome_message(lang)
            
            # Kaydet
            add_to_history(phone, "user", user_message)
            add_to_history(phone, "assistant", reply)
            save_message(phone, user_message, f"[İLK MESAJ] {reply}")
            
            # Followup planla
            if self.schedule_followup:
                self.schedule_followup(phone)
            
            # Metrik
            elapsed = time_module.time() - start_time
            record_metric("first_message", response_time=elapsed)
            
            return True, reply, "first_message"
        
        return False, None, ""
    
    def handle_greeting(
        self, 
        phone: str, 
        user_message: str,
        start_time: float
    ) -> Tuple[bool, Optional[str], str]:
        """
        Selamlama kontrolü - merhaba, hi, hello vb.
        
        Args:
            phone: Müşteri telefon numarası
            user_message: Müşteri mesajı
            start_time: İşlem başlangıç zamanı
            
        Returns:
            (handled: bool, reply: str or None, status: str)
        """
        is_greet, lang = is_greeting(user_message)
        
        if is_greet:
            # Karşılama mesajı
            reply = get_welcome_message(lang)
            
            # Kaydet
            add_to_history(phone, "user", user_message)
            add_to_history(phone, "assistant", reply)
            save_message(phone, user_message, reply)
            
            # Followup planla
            if self.schedule_followup:
                self.schedule_followup(phone)
            
            # Metrik
            elapsed = time_module.time() - start_time
            record_metric("greeting", response_time=elapsed)
            
            return True, reply, "ok"
        
        return False, None, ""
    
    def handle_menu_selection(
        self, 
        phone: str, 
        user_message: str,
        history: list,
        start_time: float
    ) -> Tuple[bool, Optional[str], str]:
        """
        Menü seçimi kontrolü - 1, 2, 3, 4.
        
        Args:
            phone: Müşteri telefon numarası
            user_message: Müşteri mesajı
            history: Konuşma geçmişi
            start_time: İşlem başlangıç zamanı
            
        Returns:
            (handled: bool, reply: str or None, status: str)
        """
        is_menu, selection = is_menu_selection(user_message)
        
        if is_menu:
            # Konuşma geçmişinden dil belirle
            conversation_lang = "tr"
            if history:
                recent_text = " ".join([m.get("content", "") for m in history[-4:]])
                conversation_lang = detect_language(recent_text)
            
            reply = get_menu_response(selection, conversation_lang)
            
            # Kaydet
            add_to_history(phone, "user", user_message)
            add_to_history(phone, "assistant", reply)
            save_message(phone, user_message, reply)
            
            # Followup planla
            if self.schedule_followup:
                self.schedule_followup(phone)
            
            # Metrik
            elapsed = time_module.time() - start_time
            record_metric("menu", category=f"menu_{selection}", response_time=elapsed)
            
            return True, reply, "ok"
        
        return False, None, ""
    
    def process(
        self, 
        phone: str, 
        user_message: str, 
        history: list,
        start_time: float
    ) -> Tuple[bool, Optional[str], str]:
        """
        Tüm selamlama/menü kontrollerini sırayla yap.
        
        Args:
            phone: Müşteri telefon numarası
            user_message: Müşteri mesajı
            history: Konuşma geçmişi
            start_time: İşlem başlangıç zamanı
            
        Returns:
            (handled: bool, reply: str or None, status: str)
        """
        # 1. İlk mesaj kontrolü
        handled, reply, status = self.handle_first_message(phone, user_message, history, start_time)
        if handled:
            return handled, reply, status
        
        # 2. Selamlama kontrolü
        handled, reply, status = self.handle_greeting(phone, user_message, start_time)
        if handled:
            return handled, reply, status
        
        # 3. Menü seçimi kontrolü
        handled, reply, status = self.handle_menu_selection(phone, user_message, history, start_time)
        if handled:
            return handled, reply, status
        
        # Hiçbiri değil
        return False, None, ""


# Singleton instance (opsiyonel)
_greeting_handler: Optional[GreetingHandler] = None

def get_greeting_handler(followup_scheduler=None) -> GreetingHandler:
    """Singleton greeting handler döndür"""
    global _greeting_handler
    if _greeting_handler is None:
        _greeting_handler = GreetingHandler(followup_scheduler)
    return _greeting_handler
