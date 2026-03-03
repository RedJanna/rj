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
    is_operational_rules_enabled,
    get_followup_minutes,
    get_env_settings_schema,
    validate_startup_environment,
)

__all__ = [
    'SettingsService',
    'get_settings_service',
    'load_settings',
    'save_settings',
    'is_automation_enabled',
    'is_followup_enabled',
    'is_operational_rules_enabled',
    'get_followup_minutes',
    'get_env_settings_schema',
    'validate_startup_environment',
]
