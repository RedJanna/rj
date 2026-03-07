"""
Settings Service - Ayar Yönetimi

Bu modül kassandra_openai_bot.py'den ayrıştırılmıştır.
Kaynak: kassandra_openai_bot.py satır 2300-2339

Global otomasyon durumu ve ayarları yönetir.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Any


# ======================================================
# AYAR DOSYASI (kassandra_openai_bot.py satır 2304)
# ======================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETTINGS_FILE = Path(
    os.getenv("KASSANDRA_SETTINGS_FILE", str(PROJECT_ROOT / "settings.json"))
).expanduser()
SETTINGS_AUDIT_FILE = Path(
    os.getenv("KASSANDRA_SETTINGS_AUDIT_FILE", str(PROJECT_ROOT / "data" / "settings_audit.json"))
).expanduser()

VALID_ROOM_KEYS = ["deluxe", "superior", "exclusiveLand", "exclusivePool", "penthouseLand", "penthouse", "premium"]
DEFAULT_CURRENCY_POLICY = {"EUR": True, "USD": True, "TRY": True, "GBP": True}
DEFAULT_LANGUAGE_POLICY = {
    "en": True,
    "tr": True,
    "ru": True,
    "de": True,
    "ar": True,
    "es": True,
    "fr": True,
    "zh": True,
    "hi": True,
    "pt": True,
}


@dataclass(frozen=True)
class EnvSetting:
    key: str
    required: bool
    default: str = ""
    description: str = ""
    critical: bool = False


ENV_SETTINGS: tuple[EnvSetting, ...] = (
    EnvSetting(
        key="OPENAI_API_KEY",
        required=True,
        description="OpenAI API key (chat yanitlari icin zorunlu)",
        critical=True,
    ),
    EnvSetting(
        key="OPENAI_MODEL",
        required=False,
        default="gpt-4.1-mini",
        description="Varsayilan OpenAI modeli",
    ),
    EnvSetting(
        key="ELEKTRA_API_BASE_URL",
        required=False,
        default="https://bookingapi.elektraweb.com",
        description="Elektra Booking API base URL",
    ),
    EnvSetting(
        key="WEBHOOK_URL",
        required=False,
        default="",
        description="Dis sistem webhook callback URL (opsiyonel)",
    ),
    EnvSetting(
        key="Elektra_Booking",
        required=False,
        default="",
        description="Elektra booking API key",
    ),
    EnvSetting(
        key="WHATSAPP_PHONE_ID",
        required=False,
        default="",
        description="Meta WhatsApp phone number id",
    ),
    EnvSetting(
        key="WHATSAPP_TOKEN",
        required=False,
        default="",
        description="Meta WhatsApp access token",
    ),
    EnvSetting(
        key="FLOW_ORCHESTRATOR_MODE",
        required=False,
        default="shadow",
        description="Flow orchestrator modu: off|shadow|active",
    ),
)


def get_env_settings_schema() -> dict:
    """Ayar semasini zorunlu/opsiyonel olarak dondur."""
    required = [s for s in ENV_SETTINGS if s.required]
    optional = [s for s in ENV_SETTINGS if not s.required]
    return {
        "required": [s.key for s in required],
        "optional": [s.key for s in optional],
        "details": {
            s.key: {
                "required": s.required,
                "default": s.default,
                "description": s.description,
                "critical": s.critical,
            }
            for s in ENV_SETTINGS
        },
    }


def _missing_critical_env_keys() -> list[str]:
    missing: list[str] = []
    for setting in ENV_SETTINGS:
        if not setting.critical:
            continue
        val = (os.getenv(setting.key) or "").strip()
        if not val:
            missing.append(setting.key)
    return missing


def validate_startup_environment(*, raise_on_error: bool = True) -> list[str]:
    """
    Kritik ortam degiskenlerini dogrula.

    Returns:
        Eksik kritik degisken adlari.
    """
    missing = _missing_critical_env_keys()
    if missing and raise_on_error:
        keys = ", ".join(missing)
        raise RuntimeError(
            "Kritik ortam degiskenleri eksik: "
            f"{keys}. Ornek: PowerShell'de `$env:OPENAI_API_KEY = \"...\"` "
            "veya `.env` dosyasinda `OPENAI_API_KEY=...`."
        )
    return missing


# ======================================================
# AYAR FONKSİYONLARI (kassandra_openai_bot.py satır 2306-2339)
# ======================================================

def load_settings() -> dict:
    """
    Ayarları yükle.
    Kaynak: kassandra_openai_bot.py satır 2306-2320
    """
    defaults = {
        "automation_enabled": True,
        "followup_enabled": False,
        "operational_rules_enabled": True,
        "followup_minutes": 10,
        "session_duration_hours": 24,
        "quiet_auto_room_keys": ["deluxe", "premium"],
        "quiet_handoff_room_keys": ["superior"],
        "standard_room_keys": ["deluxe", "superior"],
        "currency_enabled": dict(DEFAULT_CURRENCY_POLICY),
        "language_enabled": dict(DEFAULT_LANGUAGE_POLICY),
        "updated_at": datetime.now().isoformat(),
        "updated_by": "system"
    }
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    return {**defaults, **loaded}
        except:
            pass
    return defaults


def save_settings(settings: dict):
    """
    Ayarları kaydet.
    Kaynak: kassandra_openai_bot.py satır 2322-2327
    """
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    settings["updated_at"] = datetime.now().isoformat()
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)


def normalize_language_policy(payload: dict[str, Any] | None) -> dict[str, bool]:
    merged = dict(DEFAULT_LANGUAGE_POLICY)
    if not isinstance(payload, dict):
        return merged
    for code in merged.keys():
        if code in payload:
            merged[code] = bool(payload.get(code))
    return merged


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


def is_operational_rules_enabled() -> bool:
    """Deterministik operasyon kural motoru açık mı?"""
    return load_settings().get("operational_rules_enabled", True)


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
        "operational_rules_enabled": True,
        "followup_minutes": 10,
        "session_duration_hours": 24,
        "quiet_auto_room_keys": ["deluxe", "premium"],
        "quiet_handoff_room_keys": ["superior"],
        "standard_room_keys": ["deluxe", "superior"],
        "currency_enabled": dict(DEFAULT_CURRENCY_POLICY),
        "updated_at": datetime.now().isoformat(),
        "updated_by": "system_reset"
    }
    save_settings(default_settings)
    return True


def _normalize_room_keys(values: Optional[list[str]]) -> list[str]:
    out: list[str] = []
    for v in values or []:
        key = (v or "").strip().lower()
        if key and key not in out:
            out.append(key)
    return out


def get_quiet_room_policy() -> dict:
    """
    Sessiz oda politikasını getir.
    - quiet_auto_room_keys: bot otomatik rezervasyon akışında izinli
    - quiet_handoff_room_keys: canlı temsilciye devredilecek
    """
    settings = load_settings()
    auto_keys = settings.get("quiet_auto_room_keys", ["deluxe", "premium"])
    handoff_keys = settings.get("quiet_handoff_room_keys", ["superior"])
    standard_keys = settings.get("standard_room_keys", ["deluxe", "superior"])
    return {
        "quiet_auto_room_keys": _normalize_room_keys(auto_keys),
        "quiet_handoff_room_keys": _normalize_room_keys(handoff_keys),
        "standard_room_keys": _normalize_room_keys(standard_keys),
    }


def get_valid_room_keys() -> list[str]:
    return list(VALID_ROOM_KEYS)


def get_currency_policy() -> dict[str, bool]:
    """
    Aktif para birimleri politikasini getir.
    Diger/eksik degerlerde guvenli varsayim olarak varsayilanlari kullan.
    """
    settings = load_settings()
    raw = settings.get("currency_enabled")
    if not isinstance(raw, dict):
        return dict(DEFAULT_CURRENCY_POLICY)
    out = dict(DEFAULT_CURRENCY_POLICY)
    for code in out.keys():
        if code in raw:
            out[code] = bool(raw.get(code))
    return out


def _load_settings_audit() -> list[dict]:
    if SETTINGS_AUDIT_FILE.exists():
        try:
            with open(SETTINGS_AUDIT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
    return []


def _save_settings_audit(items: list[dict]) -> None:
    SETTINGS_AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_AUDIT_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)


def append_settings_audit_entry(
    *,
    key: str,
    old_value: Any,
    new_value: Any,
    updated_by: str,
    source: str = "admin_settings_api",
) -> None:
    items = _load_settings_audit()
    items.append(
        {
            "ts": datetime.now().isoformat(),
            "key": key,
            "old_value": old_value,
            "new_value": new_value,
            "updated_by": updated_by,
            "source": source,
        }
    )
    if len(items) > 1000:
        items = items[-1000:]
    _save_settings_audit(items)


def get_settings_audit(limit: int = 100) -> list[dict]:
    items = _load_settings_audit()
    if limit <= 0:
        return []
    return list(reversed(items[-limit:]))


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

    def is_operational_rules_enabled(self) -> bool:
        """Deterministik operasyon kural motoru açık mı?"""
        return is_operational_rules_enabled()
    
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
