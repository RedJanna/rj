"""
Handlers package - Mesaj işleyicileri

Bu paket kassandra_openai_bot.py'den ayrıştırılmış handler'ları içerir.
"""

from app.handlers.greeting_handler import GreetingHandler, get_greeting_handler
from app.handlers.handoff_handler import HandoffHandler, get_handoff_handler, detect_handoff_required
from app.handlers.local_faq_handler import LocalFAQHandler, get_local_faq_handler
from app.handlers.reservation_handler import ReservationHandler, get_reservation_handler
from app.handlers.suspicious_handler import (
    SuspiciousHandler,
    get_suspicious_handler,
    detect_suspicious_message,
    SUSPICIOUS_KEYWORDS,
    MUST_ESCALATE_KEYWORDS,
)

__all__ = [
    # Greeting
    'GreetingHandler',
    'get_greeting_handler',
    # Handoff
    'HandoffHandler',
    'get_handoff_handler',
    'detect_handoff_required',
    # Local FAQ
    'LocalFAQHandler',
    'get_local_faq_handler',
    # Reservation
    'ReservationHandler',
    'get_reservation_handler',
    # Suspicious
    'SuspiciousHandler',
    'get_suspicious_handler',
    'detect_suspicious_message',
    'SUSPICIOUS_KEYWORDS',
    'MUST_ESCALATE_KEYWORDS',
]
