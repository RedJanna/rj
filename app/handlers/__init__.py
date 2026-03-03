"""
Handlers package - Mesaj işleyicileri

Bu paket kassandra_openai_bot.py'den ayrıştırılmış handler'ları içerir.
"""

from app.handlers.handoff_handler import HandoffHandler, get_handoff_handler, detect_handoff_required
from app.handlers.suspicious_handler import (
    SuspiciousHandler,
    get_suspicious_handler,
    detect_suspicious_message,
    SUSPICIOUS_KEYWORDS,
    MUST_ESCALATE_KEYWORDS,
)

__all__ = [
    # Handoff
    'HandoffHandler',
    'get_handoff_handler',
    'detect_handoff_required',
    # Suspicious
    'SuspiciousHandler',
    'get_suspicious_handler',
    'detect_suspicious_message',
    'SUSPICIOUS_KEYWORDS',
    'MUST_ESCALATE_KEYWORDS',
]
