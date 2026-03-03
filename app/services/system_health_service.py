"""
System Health Service - Sistem Sağlık Servisi

Bu modül kassandra_openai_bot.py'den ayrıştırılmıştır.
Kaynak: kassandra_openai_bot.py satır 5123-5371

Sistem sağlığı, API durumu ve hata log yönetimi.
"""

from __future__ import annotations

import platform
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from app.services.error_code_service import derive_error_code

# Psutil opsiyonel import
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


# ======================================================
# HATA LOG AYARLARI (satır 5265-5267)
# ======================================================

ERROR_LOGS: List[dict] = []
MAX_ERROR_LOGS = 100


# ======================================================
# HATA LOGLAMA (satır 5269-5287)
# ======================================================

def log_error(error_type: str, message: str, details: dict = None, code: str | None = None):
    """
    Hata logla
    Kaynak: kassandra_openai_bot.py satır 5269-5287
    """
    global ERROR_LOGS
    
    error_code = (code or "").strip() or derive_error_code(
        event="system.log_error",
        error_type=error_type,
        message=message,
    )
    error_entry = {
        "timestamp": datetime.now().isoformat(),
        "code": error_code,
        "type": error_type,
        "message": message,
        "details": details or {}
    }
    
    ERROR_LOGS.append(error_entry)
    
    # Maximum log sayısını aşarsa eski logları sil
    if len(ERROR_LOGS) > MAX_ERROR_LOGS:
        ERROR_LOGS = ERROR_LOGS[-MAX_ERROR_LOGS:]
    
    # Console'a da yazdır
    print(f"❌ ERROR [{error_code}/{error_type}]: {message}")


def get_error_logs(hours: int = 24, error_type: str = None) -> dict:
    """
    Son X saatteki hata loglarını döndür
    Kaynak: kassandra_openai_bot.py satır 5290-5317
    """
    cutoff_time = datetime.now() - timedelta(hours=hours)
    
    # Filtreleme
    filtered_logs = []
    for log in ERROR_LOGS:
        try:
            log_time = datetime.fromisoformat(log["timestamp"])
            if log_time >= cutoff_time:
                if error_type is None or log["type"] == error_type:
                    filtered_logs.append(log)
        except:
            pass
    
    # İstatistikler
    error_counts = {}
    for log in filtered_logs:
        error_counts[log["type"]] = error_counts.get(log["type"], 0) + 1
    
    return {
        "period_hours": hours,
        "total_errors": len(filtered_logs),
        "error_counts": error_counts,
        "logs": filtered_logs[-50:],
        "timestamp": datetime.now().isoformat()
    }


def clear_error_logs():
    """Hata loglarını temizle"""
    global ERROR_LOGS
    ERROR_LOGS = []


# ======================================================
# SİSTEM SAĞLIĞI (satır 5127-5195)
# ======================================================

def get_system_health(bot_start_time: datetime = None) -> dict:
    """
    Sistem sağlık bilgilerini döndür
    Kaynak: kassandra_openai_bot.py satır 5127-5195
    """
    try:
        result = {
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "cpu": {},
            "ram": {},
            "disk": {},
            "uptime": {},
            "system": {}
        }
        
        if not PSUTIL_AVAILABLE:
            result["status"] = "limited"
            result["error"] = "psutil not available"
            return result
        
        # CPU kullanımı
        cpu_percent = psutil.cpu_percent(interval=1)
        result["cpu"] = {
            "percent": cpu_percent,
            "status": "critical" if cpu_percent > 90 else "warning" if cpu_percent > 80 else "normal"
        }
        
        # RAM kullanımı
        memory = psutil.virtual_memory()
        ram_percent = memory.percent
        ram_used_gb = round(memory.used / (1024**3), 2)
        ram_total_gb = round(memory.total / (1024**3), 2)
        result["ram"] = {
            "percent": ram_percent,
            "used_gb": ram_used_gb,
            "total_gb": ram_total_gb,
            "status": "critical" if ram_percent > 90 else "warning" if ram_percent > 80 else "normal"
        }
        
        # Disk kullanımı
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        disk_used_gb = round(disk.used / (1024**3), 2)
        disk_total_gb = round(disk.total / (1024**3), 2)
        result["disk"] = {
            "percent": disk_percent,
            "used_gb": disk_used_gb,
            "total_gb": disk_total_gb,
            "status": "critical" if disk_percent > 90 else "warning" if disk_percent > 85 else "normal"
        }
        
        # Uptime
        if bot_start_time:
            uptime_seconds = (datetime.now() - bot_start_time).total_seconds()
            uptime_days = int(uptime_seconds // 86400)
            uptime_hours = int((uptime_seconds % 86400) // 3600)
            uptime_minutes = int((uptime_seconds % 3600) // 60)
            result["uptime"] = {
                "days": uptime_days,
                "hours": uptime_hours,
                "minutes": uptime_minutes,
                "formatted": f"{uptime_days}g {uptime_hours}s {uptime_minutes}dk"
            }
        
        # Platform bilgisi
        result["system"] = {
            "os": platform.system(),
            "python_version": platform.python_version(),
        }
        
        return result
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


# ======================================================
# API DURUM KONTROLÜ (satır 5198-5258)
# ======================================================

def get_api_status(
    openai_client=None,
    openai_model: str = None,
    whatsapp_phone_id: str = None,
    whatsapp_token: str = None
) -> dict:
    """
    Tüm API bağlantı durumlarını kontrol et
    Kaynak: kassandra_openai_bot.py satır 5202-5258
    """
    results = {
        "timestamp": datetime.now().isoformat(),
        "apis": {}
    }
    
    # OpenAI API kontrolü
    if openai_client:
        try:
            start_time = datetime.now()
            test_response = openai_client.chat.completions.create(
                model=openai_model or "gpt-4o-mini",
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5
            )
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            results["apis"]["openai"] = {
                "status": "ok",
                "response_time_ms": round(elapsed, 2),
                "model": openai_model
            }
        except Exception as e:
            results["apis"]["openai"] = {
                "status": "error",
                "error": str(e)
            }
    else:
        results["apis"]["openai"] = {
            "status": "not_configured",
            "error": "OpenAI client not provided"
        }
    
    # WhatsApp API kontrolü
    if whatsapp_phone_id and whatsapp_token:
        results["apis"]["whatsapp"] = {
            "status": "ok",
            "phone_id": whatsapp_phone_id[:10] + "...",
            "token_present": True
        }
    else:
        results["apis"]["whatsapp"] = {
            "status": "error",
            "error": "Token veya Phone ID eksik"
        }
    
    # Genel durum
    all_ok = all(api.get("status") == "ok" for api in results["apis"].values())
    results["overall_status"] = "ok" if all_ok else "degraded"
    
    return results


# ======================================================
# SERVICE CLASS
# ======================================================

class SystemHealthService:
    """Sistem sağlık servisi"""
    
    def __init__(self, bot_start_time: datetime = None):
        self.bot_start_time = bot_start_time or datetime.now()
    
    def get_health(self) -> dict:
        """Sistem sağlığı"""
        return get_system_health(self.bot_start_time)
    
    def get_api_status(self, **kwargs) -> dict:
        """API durumu"""
        return get_api_status(**kwargs)
    
    def log_error(self, error_type: str, message: str, details: dict = None):
        """Hata logla"""
        log_error(error_type, message, details)
    
    def get_error_logs(self, hours: int = 24, error_type: str = None) -> dict:
        """Hata logları"""
        return get_error_logs(hours, error_type)
    
    def clear_logs(self):
        """Logları temizle"""
        clear_error_logs()


# Global instance
_system_health_service: Optional[SystemHealthService] = None

def get_system_health_service(bot_start_time: datetime = None) -> SystemHealthService:
    """Singleton system health service döndür"""
    global _system_health_service
    if _system_health_service is None:
        _system_health_service = SystemHealthService(bot_start_time)
    return _system_health_service


# ======================================================
# EXPORT
# ======================================================

__all__ = [
    'ERROR_LOGS',
    'MAX_ERROR_LOGS',
    'log_error',
    'get_error_logs',
    'clear_error_logs',
    'get_system_health',
    'get_api_status',
    'SystemHealthService',
    'get_system_health_service',
]
