# ============================================================
# KASSANDRA BOT - FALLBACK & GÜVENLİK EKLENTİSİ
# ============================================================
# Bu dosyayı proje kökünde tut ve mevcut bot dosyasında import et.
# İsteğe bağlı: KASSANDRA_ROOT ve ilgili dosya env değişkenleriyle yollar override edilebilir.
# ============================================================

from datetime import datetime, timedelta
from pathlib import Path
import json
import os
import re
import time

# ======================================================
# DOSYA YOLU ÇÖZÜMLEME (ÇAPRAZ ORTAM)
# ======================================================

_PROJECT_ROOT = Path(
    (os.getenv("KASSANDRA_ROOT") or str(Path(__file__).resolve().parent)).strip()
).expanduser()


def _resolve_state_file(env_var: str, default_name: str) -> Path:
    raw = (os.getenv(env_var) or "").strip()
    if raw:
        return Path(raw).expanduser()
    return _PROJECT_ROOT / default_name


# ======================================================
# RATE LIMITING (FLOOD KORUMASI)
# ======================================================

RATE_LIMIT_FILE = _resolve_state_file("KASSANDRA_RATE_LIMIT_FILE", "rate_limits.json")
RATE_LIMIT_WINDOW_SECONDS = 60  # 60 saniye içinde
RATE_LIMIT_MAX_MESSAGES = 10   # Maksimum 10 mesaj
RATE_LIMIT_BLOCK_MINUTES = 5   # Aşınca 5 dakika blokla

def load_rate_limits() -> dict:
    if RATE_LIMIT_FILE.exists():
        try:
            with open(RATE_LIMIT_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {"limits": {}, "blocked": {}}

def save_rate_limits(data: dict):
    RATE_LIMIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(RATE_LIMIT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def check_rate_limit(phone: str) -> tuple:
    """
    Rate limit kontrolü.
    Returns: (is_allowed: bool, reason: str)
    """
    if not phone:
        return True, "ok"
    
    clean_phone = re.sub(r'[^\d]', '', phone)
    data = load_rate_limits()
    now = time.time()
    
    # Bloklu mu kontrol et
    if clean_phone in data.get("blocked", {}):
        block_until = data["blocked"][clean_phone].get("until", 0)
        if now < block_until:
            remaining = int(block_until - now)
            return False, f"rate_limited_{remaining}s"
        else:
            del data["blocked"][clean_phone]
            save_rate_limits(data)
    
    # Mesaj sayısını kontrol et
    if "limits" not in data:
        data["limits"] = {}
    
    if clean_phone not in data["limits"]:
        data["limits"][clean_phone] = {"messages": [], "total_count": 0}
    
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS
    data["limits"][clean_phone]["messages"] = [
        ts for ts in data["limits"][clean_phone]["messages"] if ts > cutoff
    ]
    
    current_count = len(data["limits"][clean_phone]["messages"])
    if current_count >= RATE_LIMIT_MAX_MESSAGES:
        data["blocked"][clean_phone] = {
            "until": now + (RATE_LIMIT_BLOCK_MINUTES * 60),
            "reason": "flood",
            "blocked_at": datetime.now().isoformat()
        }
        save_rate_limits(data)
        return False, "rate_limited_flood"
    
    data["limits"][clean_phone]["messages"].append(now)
    data["limits"][clean_phone]["total_count"] = data["limits"][clean_phone].get("total_count", 0) + 1
    save_rate_limits(data)
    
    return True, "ok"

def unblock_rate_limit(phone: str) -> bool:
    """Numarayı bloktan çıkar"""
    data = load_rate_limits()
    clean_phone = re.sub(r'[^\d]', '', phone)
    if clean_phone in data.get("blocked", {}):
        del data["blocked"][clean_phone]
        save_rate_limits(data)
        return True
    return False


# ======================================================
# GÜVENLİ MOD
# ======================================================

SAFE_MODE_FILE = _resolve_state_file("KASSANDRA_SAFE_MODE_FILE", "safe_mode.json")

def load_safe_mode() -> dict:
    if SAFE_MODE_FILE.exists():
        try:
            with open(SAFE_MODE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {"enabled": False, "auto_enabled": False}

def save_safe_mode(data: dict):
    SAFE_MODE_FILE.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = datetime.now().isoformat()
    with open(SAFE_MODE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def is_safe_mode() -> bool:
    """Manuel güvenli mod açık mı?"""
    return load_safe_mode().get("enabled", False)

def is_auto_safe_mode() -> bool:
    """Otomatik güvenli mod açık mı?"""
    return load_safe_mode().get("auto_enabled", False)

def enable_safe_mode():
    """Güvenli modu aç"""
    data = load_safe_mode()
    data["enabled"] = True
    save_safe_mode(data)

def disable_safe_mode():
    """Güvenli modu kapat"""
    data = load_safe_mode()
    data["enabled"] = False
    data["auto_enabled"] = False
    save_safe_mode(data)
    clear_errors()


# ======================================================
# GÜVENLİ MOD MESAJLARI
# ======================================================

SAFE_MODE_MESSAGE_TR = """Merhaba,

Şu an sistemimizde bakım yapılmaktadır. En kısa sürede size dönüş yapacağız.

Acil durumlar için: +90 533 250 32 77

Kassandra Boutique Hotel"""

SAFE_MODE_MESSAGE_EN = """Hello,

Our system is currently under maintenance. We will get back to you as soon as possible.

For urgent matters: +90 533 250 32 77

Kassandra Boutique Hotel"""

RATE_LIMIT_MESSAGE_TR = """Çok fazla mesaj gönderdiniz. Lütfen birkaç dakika bekleyip tekrar deneyin.

Acil durumlar için: +90 533 250 32 77"""

RATE_LIMIT_MESSAGE_EN = """You have sent too many messages. Please wait a few minutes and try again.

For urgent matters: +90 533 250 32 77"""

FALLBACK_ERROR_MESSAGE_TR = """Teknik bir sorun yaşıyoruz. Lütfen birkaç dakika sonra tekrar deneyin.

Acil durumlar için bizi arayabilirsiniz: +90 533 250 32 77

Kassandra Boutique Hotel"""

FALLBACK_ERROR_MESSAGE_EN = """We are experiencing technical difficulties. Please try again in a few minutes.

For urgent matters, please call us: +90 533 250 32 77

Kassandra Boutique Hotel"""

def get_safe_mode_message(lang: str = "tr") -> str:
    return SAFE_MODE_MESSAGE_EN if lang == "en" else SAFE_MODE_MESSAGE_TR

def get_rate_limit_message(lang: str = "tr") -> str:
    return RATE_LIMIT_MESSAGE_EN if lang == "en" else RATE_LIMIT_MESSAGE_TR

def get_fallback_error_message(lang: str = "tr") -> str:
    return FALLBACK_ERROR_MESSAGE_EN if lang == "en" else FALLBACK_ERROR_MESSAGE_TR


# ======================================================
# HATA SAYACI (Otomatik güvenli mod)
# ======================================================

ERROR_COUNTER_FILE = _resolve_state_file("KASSANDRA_ERROR_COUNTER_FILE", "error_counter.json")
ERROR_THRESHOLD = 5  # 5 hata üst üste gelirse güvenli moda geç
ERROR_WINDOW_MINUTES = 10

def load_error_counter() -> dict:
    if ERROR_COUNTER_FILE.exists():
        try:
            with open(ERROR_COUNTER_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {"errors": [], "auto_safe_mode": False}

def save_error_counter(data: dict):
    ERROR_COUNTER_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(ERROR_COUNTER_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def record_error(error_type: str, details: str = ""):
    """Hata kaydet ve gerekirse otomatik güvenli moda geç"""
    data = load_error_counter()
    now = datetime.now()
    
    data["errors"].append({
        "timestamp": now.isoformat(),
        "type": error_type,
        "details": details[:200]
    })
    
    cutoff = now - timedelta(minutes=ERROR_WINDOW_MINUTES)
    data["errors"] = [
        e for e in data["errors"] 
        if datetime.fromisoformat(e["timestamp"]) > cutoff
    ]
    
    if len(data["errors"]) >= ERROR_THRESHOLD:
        # Otomatik güvenli modu aç
        safe_data = load_safe_mode()
        safe_data["auto_enabled"] = True
        safe_data["auto_enabled_at"] = now.isoformat()
        save_safe_mode(safe_data)
        print(f"⚠️ OTOMATİK GÜVENLİ MOD AKTİF! {len(data['errors'])} hata {ERROR_WINDOW_MINUTES} dk içinde.")
    
    save_error_counter(data)

def clear_errors():
    """Hata sayacını sıfırla"""
    save_error_counter({"errors": []})

def get_error_stats() -> dict:
    """Hata istatistikleri"""
    data = load_error_counter()
    return {
        "error_count": len(data.get("errors", [])),
        "errors": data.get("errors", [])[-10:]  # Son 10 hata
    }


# ======================================================
# YARDIMCI FONKSİYONLAR
# ======================================================

def get_system_status() -> dict:
    """Tüm sistem durumunu getir"""
    return {
        "safe_mode": is_safe_mode(),
        "auto_safe_mode": is_auto_safe_mode(),
        "error_count": len(load_error_counter().get("errors", [])),
        "timestamp": datetime.now().isoformat()
    }


# ======================================================
# KULLANIM ÖRNEĞİ (chat endpoint'inde)
# ======================================================
"""
# /chat endpoint'inin BAŞINA ekle:

from kassandra_fallback_eklenti import (
    check_rate_limit, is_safe_mode, is_auto_safe_mode,
    get_safe_mode_message, get_rate_limit_message, get_fallback_error_message,
    record_error
)

# Endpoint içinde, mevcut kontrollerden ÖNCE:

    lang = detect_language(user_message) if user_message else "tr"
    
    # Güvenli mod kontrolü
    if is_safe_mode() or is_auto_safe_mode():
        reply = get_safe_mode_message(lang)
        save_message(phone, user_message, reply)
        return ChatResponse(reply=reply, status="safe_mode")
    
    # Rate limit kontrolü
    is_allowed, rate_reason = check_rate_limit(phone)
    if not is_allowed:
        reply = get_rate_limit_message(lang)
        save_message(phone, user_message, reply)
        return ChatResponse(reply=reply, status=rate_reason)

# OpenAI except bloğunda:

    except Exception as e:
        record_error("openai_api", str(e))
        reply = get_fallback_error_message(lang)
        save_message(phone, user_message, reply)
        return ChatResponse(reply=reply, status="error")
"""
