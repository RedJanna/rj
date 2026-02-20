"""
Suspicious Handler - Şüpheli/Tehlikeli Mesaj Tespiti

Bu modül kassandra_openai_bot.py'den ayrıştırılmıştır.
Kaynak: kassandra_openai_bot.py satır 2213-2293

Şüpheli mesajları tespit eder ve kategorize eder.
"""

from __future__ import annotations

from typing import Tuple


# ======================================================
# ŞÜPHELİ KELİMELER (kassandra_openai_bot.py satır 2218-2237)
# ======================================================

SUSPICIOUS_KEYWORDS = [
    # Yapay zeka soruları - ASLA EVET DEME
    "yapay zeka", "robot musun", "bot musun", "ai mısın", "insan mısın",
    "gerçek insan", "canlı mısın", "otomatik", "chatgpt", "gpt",

    # Manipülasyon girişimleri
    "acil", "vefat", "öldü", "hasta", "kaza", "ambulans", "hastane",
    "ölüm", "cenaze", "hayatını kaybetti",

    # Dolandırıcılık girişimleri
    # NOT: "kredi kartı" tek başına şüpheli DEĞİL — müşteriler doğal olarak
    # "kredi kartı ile ödeme" der. Sadece kart NUMARASI/CVV istemek fraud'dur.
    "iban", "para gönder", "para at", "hesap numarası",
    "kart numarası", "kart numaranı", "kredi kartı numara",
    "cvv", "şifre ver", "password", "gizli bilgi",

    # Kişisel bilgi toplama
    "ev adresi", "telefon numarası ver", "özel numara", "kişisel bilgi",
    "nerede oturuyor", "evi nerede",

    # Sistem manipülasyonu
    "hack", "sistemi kır", "bypass", "güvenlik aç", "admin şifre",
    "root", "database", "veritabanı"
]


# ======================================================
# KESİNLİKLE İNSANA YÖNLENDİRİLECEK DURUMLAR (kassandra_openai_bot.py satır 2241-2244)
# ======================================================

MUST_ESCALATE_KEYWORDS = [
    "intihar", "kendime zarar", "ölmek istiyorum", "tehdit",
    "dava", "avukat", "polis", "savcı", "mahkeme"
]


# ======================================================
# ŞÜPHELİ MESAJ TESPİT FONKSİYONU (kassandra_openai_bot.py satır 2246-2293)
# ======================================================

def detect_suspicious_message(text: str) -> Tuple[bool, str, str]:
    """
    Şüpheli mesaj tespiti.
    
    Args:
        text: Kontrol edilecek mesaj metni
        
    Returns:
        (is_suspicious: bool, reason: str, severity: str)
        severity: "low", "medium", "high", "critical", "none"
    """
    text_lower = text.lower()
    
    # Kritik durumlar (HEMEN insana yönlendir)
    for keyword in MUST_ESCALATE_KEYWORDS:
        if keyword in text_lower:
            return True, f"Kritik anahtar kelime: {keyword}", "critical"
    
    # Yapay zeka soruları
    ai_questions = ["yapay zeka", "robot musun", "bot musun", "ai mısın", 
                    "insan mısın", "gerçek insan", "canlı mısın", "chatgpt", "gpt"]
    for keyword in ai_questions:
        if keyword in text_lower:
            return True, "Yapay zeka sorusu", "high"
    
    # Dolandırıcılık girişimi
    # NOT: "kredi kartı" tek başına fraud DEĞİL — müşteriler ödeme yöntemi olarak söyler.
    # Sadece kart numarası / CVV / şifre istemek gerçek fraud'dur.
    fraud_keywords = [
        "iban", "para gönder", "para at",
        "kart numarası", "kart numaranı", "kredi kartı numara",
        "cvv", "şifre ver",
    ]
    for keyword in fraud_keywords:
        if keyword in text_lower:
            return True, f"Dolandırıcılık girişimi: {keyword}", "critical"
    
    # Manipülasyon girişimi
    manipulation_keywords = ["acil", "vefat", "öldü", "cenaze", "hayatını kaybetti"]
    manipulation_count = sum(1 for kw in manipulation_keywords if kw in text_lower)
    if manipulation_count >= 1:
        # "acil" tek başına düşük, ama diğerleriyle birlikte yüksek
        if any(kw in text_lower for kw in ["vefat", "öldü", "cenaze", "hayatını kaybetti"]):
            return True, "Manipülasyon girişimi (ölüm/acil)", "high"
        elif "acil" in text_lower and len(text) > 50:
            return True, "Acil durum iddiası", "medium"
    
    # Kişisel bilgi toplama
    personal_keywords = ["numarası ver", "adresi ver", "nerede oturuyor", "özel bilgi"]
    for keyword in personal_keywords:
        if keyword in text_lower:
            return True, f"Kişisel bilgi talebi: {keyword}", "medium"
    
    # Genel şüpheli kelime sayısı
    suspicious_count = sum(1 for kw in SUSPICIOUS_KEYWORDS if kw in text_lower)
    if suspicious_count >= 2:
        return True, f"{suspicious_count} şüpheli kelime tespit edildi", "medium"
    
    return False, "", "none"


# ======================================================
# SUSPICIOUS HANDLER CLASS
# ======================================================

class SuspiciousHandler:
    """Şüpheli mesaj işleyicisi"""
    
    def __init__(self, notification_service=None):
        """
        Args:
            notification_service: Admin bildirim servisi
        """
        self.notification_service = notification_service
    
    def check(self, text: str) -> Tuple[bool, str, str]:
        """
        Mesajı kontrol et.
        
        Returns:
            (is_suspicious, reason, severity)
        """
        return detect_suspicious_message(text)
    
    async def handle(
        self,
        phone: str,
        user_message: str
    ) -> Tuple[bool, str, str]:
        """
        Şüpheli mesajı işle ve gerekirse admin'e bildir.
        
        Returns:
            (is_suspicious, reason, severity)
        """
        is_suspicious, reason, severity = self.check(user_message)
        
        if is_suspicious and self.notification_service:
            await self.notification_service.notify_admin_suspicious(
                severity=severity,
                reason=reason,
                customer_phone=phone,
                customer_message=user_message
            )
        
        return is_suspicious, reason, severity
    
    def is_ai_question(self, text: str) -> bool:
        """Yapay zeka sorusu mu?"""
        text_lower = text.lower()
        ai_keywords = ["yapay zeka", "robot musun", "bot musun", "ai mısın", 
                       "insan mısın", "gerçek insan", "canlı mısın", "chatgpt", "gpt"]
        return any(kw in text_lower for kw in ai_keywords)
    
    def is_fraud_attempt(self, text: str) -> bool:
        """Dolandırıcılık girişimi mi?"""
        text_lower = text.lower()
        fraud_keywords = [
            "iban", "para gönder", "para at",
            "kart numarası", "kart numaranı", "kredi kartı numara",
            "cvv", "şifre ver",
        ]
        return any(kw in text_lower for kw in fraud_keywords)
    
    def must_escalate(self, text: str) -> bool:
        """Kesinlikle insana yönlendirilmeli mi?"""
        text_lower = text.lower()
        return any(kw in text_lower for kw in MUST_ESCALATE_KEYWORDS)


# Singleton instance
_suspicious_handler = None

def get_suspicious_handler(notification_service=None) -> SuspiciousHandler:
    """Singleton suspicious handler döndür"""
    global _suspicious_handler
    if _suspicious_handler is None:
        _suspicious_handler = SuspiciousHandler(notification_service)
    return _suspicious_handler
