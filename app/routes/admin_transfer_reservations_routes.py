"""Admin routes for transfer reservations."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Awaitable, Callable

from fastapi import APIRouter, Body

from app.services.conversation_store import load_conversation
from app.services.transfer_reservation_service import (
    get_transfer_reservation,
    list_transfer_reservations,
    normalize_transfer_status,
    update_transfer_reservation_details,
    update_transfer_reservation_status,
)
from app.utils.message_utils import detect_language


def _detect_customer_language(phone: str) -> str:
    if not phone:
        return "tr"
    try:
        conv = load_conversation(phone)
        messages = conv.get("messages", []) if isinstance(conv, dict) else []
        langs = []
        for msg in messages[-8:]:
            text = (msg.get("user_message") or "").strip()
            if not text:
                continue
            langs.append(detect_language(text))
        if not langs:
            return "tr"
        return Counter(langs).most_common(1)[0][0] or "tr"
    except Exception:
        return "tr"


def _confirm_message(lang: str, reservation: dict) -> str:
    route = reservation.get("transfer_route", "-")
    date = reservation.get("transfer_date", "-")
    ttime = reservation.get("transfer_time", "-")
    flight = reservation.get("flight_no", "-")
    if lang == "en":
        return (
            "Hello, your transfer reservation is confirmed.\n\n"
            f"📍 {route}\n"
            f"📅 {date}\n"
            f"🕒 {ttime}\n"
            f"✈️ Flight: {flight}\n\n"
            "We wish you a safe journey."
        )
    if lang == "ru":
        return (
            "Здравствуйте, ваш трансфер подтверждён.\n\n"
            f"📍 {route}\n"
            f"📅 {date}\n"
            f"🕒 {ttime}\n"
            f"✈️ Рейс: {flight}\n\n"
            "Желаем вам приятной поездки."
        )
    return (
        "Merhaba, transfer rezervasyonunuz onaylandı.\n\n"
        f"📍 {route}\n"
        f"📅 {date}\n"
        f"🕒 {ttime}\n"
        f"✈️ Uçuş: {flight}\n\n"
        "Güvenli yolculuklar dileriz."
    )


def _cancel_message(lang: str, reservation: dict, reason: str) -> str:
    reason_text = reason or "-"
    if lang == "en":
        return (
            "Hello, your transfer reservation has been cancelled.\n"
            f"Reason: {reason_text}\n\n"
            "If you wish, we can create a new transfer request."
        )
    if lang == "ru":
        return (
            "Здравствуйте, ваш трансфер был отменён.\n"
            f"Причина: {reason_text}\n\n"
            "При необходимости мы можем оформить новый запрос на трансфер."
        )
    return (
        "Merhaba, transfer rezervasyonunuz iptal edildi.\n"
        f"Gerekçe: {reason_text}\n\n"
        "Dilerseniz yeni bir transfer talebi oluşturabiliriz."
    )


def _update_message(lang: str, changes: list[str]) -> str:
    changes_text = "\n".join([f"• {c}" for c in changes]) if changes else "• Detay güncellendi"
    if lang == "en":
        return (
            "Hello, your transfer reservation has been updated.\n\n"
            "Updated details:\n"
            f"{changes_text}"
        )
    if lang == "ru":
        return (
            "Здравствуйте, ваш трансфер был обновлён.\n\n"
            "Обновлённые данные:\n"
            f"{changes_text}"
        )
    return (
        "Merhaba, transfer rezervasyonunuz güncellendi.\n\n"
        "Güncellenen bilgiler:\n"
        f"{changes_text}"
    )


def build_admin_transfer_reservations_router(
    *,
    send_whatsapp_message_fn: Callable[[str, str], Awaitable[bool]],
) -> APIRouter:
    router = APIRouter(tags=["admin-transfer-reservations"])

    @router.get("/admin/transfer-reservations")
    async def get_transfer_reservations(status: str = "pending", date: str = ""):
        norm_status = normalize_transfer_status(status)
        items = list_transfer_reservations(status=norm_status, date_query=date)
        return {
            "success": True,
            "count": len(items),
            "reservations": items,
            "filters": {"status": norm_status, "date": date},
        }

    @router.get("/admin/transfer-reservations/{reservation_id}")
    async def get_transfer_reservation_api(reservation_id: int):
        reservation = get_transfer_reservation(reservation_id)
        if not reservation:
            return {"success": False, "error": "Transfer rezervasyonu bulunamadı"}
        return {"success": True, "reservation": reservation}

    @router.post("/admin/transfer-reservations/{reservation_id}/confirm")
    async def confirm_transfer_reservation_api(
        reservation_id: int,
        body: dict = Body(default={}),
    ):
        notify_customer = bool((body or {}).get("notify_customer", True))
        reservation = update_transfer_reservation_status(
            reservation_id,
            status="confirmed",
            admin_note=str((body or {}).get("note", "")).strip(),
        )
        if not reservation:
            return {"success": False, "error": "Transfer rezervasyonu bulunamadı"}

        customer_phone = reservation.get("customer_phone", "")
        customer_lang = _detect_customer_language(customer_phone)
        if customer_phone and notify_customer:
            msg = _confirm_message(customer_lang, reservation)
            await send_whatsapp_message_fn(customer_phone, msg)

        return {
            "success": True,
            "message": "Transfer rezervasyonu onaylandı",
            "reservation": reservation,
            "notified_customer": bool(customer_phone and notify_customer),
            "customer_lang": customer_lang,
        }

    @router.post("/admin/transfer-reservations/{reservation_id}/cancel")
    async def cancel_transfer_reservation_api(
        reservation_id: int,
        body: dict = Body(default={}),
    ):
        reason = str((body or {}).get("reason", "")).strip()
        notify_customer = bool((body or {}).get("notify_customer", True))
        reservation = update_transfer_reservation_status(
            reservation_id,
            status="cancelled",
            admin_note=reason,
        )
        if not reservation:
            return {"success": False, "error": "Transfer rezervasyonu bulunamadı"}
        customer_phone = reservation.get("customer_phone", "")
        customer_lang = _detect_customer_language(customer_phone)
        notified = False
        if customer_phone and notify_customer:
            await send_whatsapp_message_fn(customer_phone, _cancel_message(customer_lang, reservation, reason))
            notified = True
        return {
            "success": True,
            "message": "Transfer rezervasyonu iptal edildi",
            "reservation": reservation,
            "notified_customer": notified,
            "customer_lang": customer_lang,
        }

    @router.post("/admin/transfer-reservations/{reservation_id}/update")
    async def update_transfer_reservation_api(
        reservation_id: int,
        body: dict = Body(default={}),
    ):
        old = get_transfer_reservation(reservation_id)
        notify_customer = bool((body or {}).get("notify_customer", True))
        changes = (body or {}).copy()
        changes.pop("notify_customer", None)
        changes["admin_note"] = (
            str(changes.get("admin_note") or "").strip()
            or f"Admin güncellemesi ({datetime.now().strftime('%Y-%m-%d %H:%M')})"
        )
        reservation = update_transfer_reservation_details(reservation_id, changes)
        if not reservation:
            return {"success": False, "error": "Transfer rezervasyonu bulunamadı"}
        customer_phone = reservation.get("customer_phone", "")
        customer_lang = _detect_customer_language(customer_phone)

        changed_fields = []
        if old:
            for field, label in [
                ("transfer_date", "Tarih"),
                ("transfer_time", "Saat"),
                ("flight_no", "Uçuş"),
                ("guest_text", "Kişi"),
                ("luggage_text", "Bagaj"),
                ("baby_seat", "Bebek koltuğu"),
                ("price_text", "Ücret"),
            ]:
                prev = str(old.get(field, "")).strip()
                curr = str(reservation.get(field, "")).strip()
                if prev != curr:
                    changed_fields.append(f"{label}: {prev or '-'} -> {curr or '-'}")

        notified = False
        if customer_phone and notify_customer:
            await send_whatsapp_message_fn(customer_phone, _update_message(customer_lang, changed_fields))
            notified = True

        return {
            "success": True,
            "message": "Transfer rezervasyonu güncellendi",
            "reservation": reservation,
            "changes": changed_fields,
            "notified_customer": notified,
            "customer_lang": customer_lang,
        }

    return router
