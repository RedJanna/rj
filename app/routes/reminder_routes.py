"""
Reminder Routes - Hatırlatma API Endpoint'leri
==============================================
Admin paneli için hatırlatma yönetim API'leri.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Union
from datetime import datetime

from app.services.reminder_service import (
    get_reminder_stats,
    get_pending_reminders,
    get_reminder_logs,
    get_reminder_settings,
    update_reminder_setting,
    toggle_reminder_type,
    cancel_reminder,
    ReminderType
)

router = APIRouter(prefix="/admin/reminders", tags=["reminders"])


# ======================================================
# PYDANTIC MODELS
# ======================================================

class ReminderSettingUpdate(BaseModel):
    reminder_type: str
    key: str
    value: Union[str, int, bool]


class ReminderToggle(BaseModel):
    reminder_type: str
    enabled: bool


# ======================================================
# ENDPOINTS
# ======================================================

@router.get("/stats")
async def reminder_stats():
    """Hatırlatma istatistikleri"""
    return get_reminder_stats()


@router.get("/pending")
async def pending_reminders(reminder_type: Optional[str] = None):
    """Bekleyen hatırlatmalar"""
    reminders = get_pending_reminders(reminder_type)
    return {
        "count": len(reminders),
        "reminders": reminders
    }


@router.get("/logs")
async def reminder_logs(limit: int = 50, reminder_type: Optional[str] = None):
    """Hatırlatma logları"""
    logs = get_reminder_logs(limit, reminder_type)
    return {
        "count": len(logs),
        "logs": logs
    }


@router.get("/settings")
async def reminder_settings():
    """Hatırlatma ayarları"""
    return get_reminder_settings()


@router.post("/settings/update")
async def update_setting(data: ReminderSettingUpdate):
    """Hatırlatma ayarını güncelle"""
    success = update_reminder_setting(data.reminder_type, data.key, data.value)
    if not success:
        raise HTTPException(status_code=400, detail="Geçersiz hatırlatma türü")
    return {"success": True, "message": f"{data.reminder_type}.{data.key} güncellendi"}


@router.post("/toggle")
async def toggle_reminder(data: ReminderToggle):
    """Hatırlatma türünü aç/kapat"""
    success = toggle_reminder_type(data.reminder_type, data.enabled)
    if not success:
        raise HTTPException(status_code=400, detail="Geçersiz hatırlatma türü")
    
    status = "aktif" if data.enabled else "devre dışı"
    return {"success": True, "message": f"{data.reminder_type} {status}"}


@router.delete("/cancel/{reservation_id}")
async def cancel_reservation_reminder(reservation_id: str, reminder_type: Optional[str] = None):
    """Rezervasyon hatırlatmasını iptal et"""
    success = cancel_reminder(reservation_id, reminder_type)
    if not success:
        raise HTTPException(status_code=404, detail="Hatırlatma bulunamadı")
    return {"success": True, "message": "Hatırlatma iptal edildi"}


@router.get("/types")
async def reminder_types():
    """Hatırlatma türleri listesi"""
    return {
        "types": [
            {
                "id": ReminderType.RESTAURANT_15MIN,
                "name": "Restoran Hatırlatması",
                "description": "Rezervasyondan 15 dakika önce",
                "icon": "🍽️"
            },
            {
                "id": ReminderType.HOTEL_NON_REFUNDABLE,
                "name": "Otel (İptal Edilemez)",
                "description": "Check-in'den 7 gün önce",
                "icon": "🏨"
            },
            {
                "id": ReminderType.HOTEL_FREE_CANCEL,
                "name": "Otel (Ücretsiz İptal)",
                "description": "Check-in'den 5 gün önce",
                "icon": "🏨"
            },
            {
                "id": ReminderType.FLOW_INCOMPLETE,
                "name": "Yarım Kalan İşlem",
                "description": "5 dakika sonra hatırlatma",
                "icon": "⏳"
            }
        ]
    }
