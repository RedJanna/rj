"""
Core package - Temel servisler

Bu paket kassandra_openai_bot.py'den ayrıştırılmış temel servisleri içerir.
"""

from app.core.settings_service import (
    SettingsService,
    get_settings_service,
    load_settings,
    save_settings,
    is_automation_enabled,
    is_followup_enabled,
    get_followup_minutes,
)

__all__ = [
    'SettingsService',
    'get_settings_service',
    'load_settings',
    'save_settings',
    'is_automation_enabled',
    'is_followup_enabled',
    'get_followup_minutes',
]
