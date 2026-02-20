"""
Settings Service - Ayar Yönetimi

Bu modül kassandra_openai_bot.py'den ayrıştırılmıştır.
Kaynak: kassandra_openai_bot.py satır 2300-2339

Global otomasyon durumu ve ayarları yönetir.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional


# ======================================================
# AYAR DOSYASI (kassandra_openai_bot.py satır 2304)
# ======================================================

SETTINGS_FILE = Path("C:/KassandraOpenAI/settings.json")


# ======================================================
# AYAR FONKSİYONLARI (kassandra_openai_bot.py satır 2306-2339)
# ======================================================

def load_settings() -> dict:
    """
    Ayarları yükle.
    Kaynak: kassandra_openai_bot.py satır 2306-2320
    """
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {
        "automation_enabled": True,
        "followup_enabled": False,
        "followup_minutes": 10,
        "updated_at": datetime.now().isoformat(),
        "updated_by": "system"
    }


def save_settings(settings: dict):
    """
    Ayarları kaydet.
    Kaynak: kassandra_openai_bot.py satır 2322-2327
    """
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    settings["updated_at"] = datetime.now().isoformat()
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)


def is_automation_enabled() -> bool:
    """
    Otomasyon açık mı?
    Kaynak: kassandra_openai_bot.py satır 2329-2331
    """
    return load_settings().get("automation_enabled", True)


def is_followup_enabled() -> bool:
    """
    Follow-up açık mı?
    Kaynak: kassandra_openai_bot.py satır 2333-2335
    """
    return load_settings().get("followup_enabled", True)


def get_followup_minutes() -> int:
    """
    Follow-up süresi (dakika).
    Kaynak: kassandra_openai_bot.py satır 2337-2339
    """
    return load_settings().get("followup_minutes", 10)


# ======================================================
# EK YARDIMCI FONKSİYONLAR
# ======================================================

def set_automation_enabled(enabled: bool, updated_by: str = "admin") -> bool:
    """Otomasyonu aç/kapat"""
    settings = load_settings()
    settings["automation_enabled"] = enabled
    settings["updated_by"] = updated_by
    save_settings(settings)
    return True


def set_followup_enabled(enabled: bool, updated_by: str = "admin") -> bool:
    """Follow-up'ı aç/kapat"""
    settings = load_settings()
    settings["followup_enabled"] = enabled
    settings["updated_by"] = updated_by
    save_settings(settings)
    return True


def set_followup_minutes(minutes: int, updated_by: str = "admin") -> bool:
    """Follow-up süresini ayarla"""
    if minutes < 1 or minutes > 60:
        return False
    settings = load_settings()
    settings["followup_minutes"] = minutes
    settings["updated_by"] = updated_by
    save_settings(settings)
    return True


def get_all_settings() -> dict:
    """Tüm ayarları getir"""
    return load_settings()


def reset_settings() -> bool:
    """Ayarları varsayılana sıfırla"""
    default_settings = {
        "automation_enabled": True,
        "followup_enabled": False,
        "followup_minutes": 10,
        "updated_at": datetime.now().isoformat(),
        "updated_by": "system_reset"
    }
    save_settings(default_settings)
    return True


# ======================================================
# SETTINGS SERVICE CLASS
# ======================================================

class SettingsService:
    """Ayar yönetim servisi"""
    
    def __init__(self, settings_file: Path = None):
        """
        Args:
            settings_file: Ayar dosyası yolu (opsiyonel)
        """
        global SETTINGS_FILE
        if settings_file:
            SETTINGS_FILE = settings_file
    
    def load(self) -> dict:
        """Ayarları yükle"""
        return load_settings()
    
    def save(self, settings: dict):
        """Ayarları kaydet"""
        save_settings(settings)
    
    def is_automation_enabled(self) -> bool:
        """Otomasyon açık mı?"""
        return is_automation_enabled()
    
    def is_followup_enabled(self) -> bool:
        """Follow-up açık mı?"""
        return is_followup_enabled()
    
    def get_followup_minutes(self) -> int:
        """Follow-up süresi"""
        return get_followup_minutes()
    
    def set_automation(self, enabled: bool, updated_by: str = "admin") -> bool:
        """Otomasyonu ayarla"""
        return set_automation_enabled(enabled, updated_by)
    
    def set_followup(self, enabled: bool, updated_by: str = "admin") -> bool:
        """Follow-up'ı ayarla"""
        return set_followup_enabled(enabled, updated_by)
    
    def set_followup_time(self, minutes: int, updated_by: str = "admin") -> bool:
        """Follow-up süresini ayarla"""
        return set_followup_minutes(minutes, updated_by)
    
    def get_all(self) -> dict:
        """Tüm ayarları getir"""
        return get_all_settings()
    
    def reset(self) -> bool:
        """Varsayılana sıfırla"""
        return reset_settings()


# Singleton instance
_settings_service: Optional[SettingsService] = None

def get_settings_service() -> SettingsService:
    """Singleton settings service döndür"""
    global _settings_service
    if _settings_service is None:
        _settings_service = SettingsService()
    return _settings_service
