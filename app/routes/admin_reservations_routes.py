"""Admin reservation routes extracted from the legacy monolith."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict

from fastapi import APIRouter


def build_admin_reservations_router(
    reservations_db: Path,
    reservation_status: Any,
    get_reservations_by_date_fn: Callable[[str], Any],
    get_upcoming_reservations_fn: Callable[[int], Any],
    get_todays_reservations_fn: Callable[[], Any],
    get_reservation_fn: Callable[[int], Any],
    update_reservation_status_fn: Callable[[int, str], Any],
    cancel_reservation_fn: Callable[[int, str], Any],
    notify_admin_cancel_v2_fn: Callable[..., Awaitable[Any]],
    get_customer_reservations_fn: Callable[[str], Any],
    send_whatsapp_message_fn: Callable[[str, str], Awaitable[Any]],
    admin_phone: str,
    format_reservation_confirmation_fn: Callable[[Dict[str, Any], str], str] | None = None,
    send_reservation_pdf_fn: Callable[[str, Dict[str, Any]], Awaitable[Any]] | None = None,
) -> APIRouter:
    router = APIRouter(tags=["admin-reservations"])

    @router.get("/admin/reservations")
    async def get_reservations(
        date: str = None,
        name: str = None,
        phone: str = None,
        status: str = None,
        days: int = 7,
    ):
        try:
            conn = sqlite3.connect(str(reservations_db))
            cursor = conn.cursor()
            query = "SELECT * FROM reservations WHERE 1=1"
            params = []

            if date:
                parsed_date = None
                for fmt in ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"]:
                    try:
                        parsed_date = datetime.strptime(date, fmt).strftime("%Y-%m-%d")
                        break
                    except Exception:
                        continue
                if parsed_date:
                    query += " AND date = ?"
                    params.append(parsed_date)
            else:
                today = datetime.now().strftime("%Y-%m-%d")
                future = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
                query += " AND date >= ? AND date <= ?"
                params.extend([today, future])

            if name:
                query += " AND LOWER(customer_name) LIKE ?"
                params.append(f"%{name.lower()}%")

            if phone:
                clean_phone = "".join(filter(str.isdigit, phone))
                query += " AND customer_phone LIKE ?"
                params.append(f"%{clean_phone}%")

            st = (status or "active").strip().lower()
            if st in ["all", "*"]:
                pass
            elif st == "active":
                query += " AND status IN (?, ?)"
                params.extend([reservation_status.PENDING.value, reservation_status.CONFIRMED.value])
            elif st in ["inactive", "archived"]:
                query += " AND status IN (?, ?, ?)"
                params.extend(
                    [
                        reservation_status.CANCELLED.value,
                        reservation_status.COMPLETED.value,
                        reservation_status.NO_SHOW.value,
                    ]
                )
            else:
                query += " AND status = ?"
                params.append(st)

            query += " ORDER BY date ASC, time ASC"
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            reservations = []
            for row in rows:
                reservations.append(
                    {
                        "id": row[0],
                        "customer_phone": row[1],
                        "customer_name": row[2],
                        "meal_type": row[3],
                        "date": row[4],
                        "time": row[5],
                        "guest_count": row[6],
                        "special_requests": row[7] if len(row) > 7 else "",
                        "status": row[8] if len(row) > 8 else "pending",
                        "created_at": row[9] if len(row) > 9 else "",
                    }
                )

            return {
                "success": True,
                "count": len(reservations),
                "reservations": reservations,
                "filters": {"date": date, "name": name, "phone": phone, "status": status},
            }
        except Exception as e:
            if date:
                reservations = get_reservations_by_date_fn(date)
            else:
                reservations = get_upcoming_reservations_fn(days)
            return {"count": len(reservations), "reservations": reservations, "error": str(e)}

    @router.get("/admin/reservations/search")
    async def search_reservations(q: str = ""):
        if not q or len(q) < 2:
            return {"error": "En az 2 karakter girin", "reservations": []}
        try:
            conn = sqlite3.connect(str(reservations_db))
            cursor = conn.cursor()

            search_term = f"%{q.lower()}%"
            clean_phone = "".join(filter(str.isdigit, q))
            query = """
                SELECT * FROM reservations
                WHERE LOWER(customer_name) LIKE ?
                   OR customer_phone LIKE ?
                ORDER BY date DESC, time DESC
                LIMIT 50
            """
            cursor.execute(query, (search_term, f"%{clean_phone}%"))
            rows = cursor.fetchall()
            conn.close()

            reservations = []
            for row in rows:
                reservations.append(
                    {
                        "id": row[0],
                        "customer_phone": row[1],
                        "customer_name": row[2],
                        "meal_type": row[3],
                        "date": row[4],
                        "time": row[5],
                        "guest_count": row[6],
                        "special_requests": row[7] if len(row) > 7 else "",
                        "status": row[8] if len(row) > 8 else "pending",
                    }
                )
            return {"success": True, "query": q, "count": len(reservations), "reservations": reservations}
        except Exception as e:
            return {"error": str(e), "reservations": []}

    @router.get("/admin/reservations/today")
    async def get_todays_reservations_api():
        reservations = get_todays_reservations_fn()
        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "count": len(reservations),
            "reservations": reservations,
        }

    @router.get("/admin/reservations/{reservation_id}")
    async def get_reservation_api(reservation_id: int):
        reservation = get_reservation_fn(reservation_id)
        if not reservation:
            return {"error": "Rezervasyon bulunamadi"}
        return reservation

    @router.post("/admin/reservations/{reservation_id}/confirm")
    async def confirm_reservation_api(reservation_id: int):
        updated = update_reservation_status_fn(reservation_id, reservation_status.CONFIRMED.value)
        reservation = get_reservation_fn(reservation_id)
        if not reservation:
            return {"status": "error", "message": "Rezervasyon bulunamadi"}

        customer_phone = str(reservation.get("customer_phone") or "").strip()
        notify_sent = False
        pdf_sent = False
        notify_error = ""
        pdf_error = ""

        if customer_phone:
            try:
                if callable(format_reservation_confirmation_fn):
                    customer_msg = format_reservation_confirmation_fn(reservation, "tr")
                else:
                    customer_msg = (
                        "Rezervasyonunuz onaylandı. ✅\n\n"
                        f"Tarih: {reservation.get('date', '-')}\n"
                        f"Saat: {reservation.get('time', '-')}\n"
                        f"Kişi: {reservation.get('guest_count', '-')}\n"
                    )
                notify_sent = bool(await send_whatsapp_message_fn(customer_phone, customer_msg))
            except Exception as e:
                notify_error = str(e)

            try:
                if callable(send_reservation_pdf_fn):
                    pdf_sent = bool(await send_reservation_pdf_fn(customer_phone, reservation))
            except Exception as e:
                pdf_error = str(e)

        return {
            "status": "ok",
            "message": "Rezervasyon onaylandi",
            "reservation_id": reservation_id,
            "updated": bool(updated),
            "customer_notified": notify_sent,
            "pdf_sent": pdf_sent,
            "notify_error": notify_error,
            "pdf_error": pdf_error,
        }

    @router.post("/admin/reservations/{reservation_id}/send-pdf")
    async def send_reservation_pdf_api(reservation_id: int):
        reservation = get_reservation_fn(reservation_id)
        if not reservation:
            return {"status": "error", "message": "Rezervasyon bulunamadi"}

        customer_phone = str(reservation.get("customer_phone") or "").strip()
        if not customer_phone:
            return {"status": "error", "message": "Müşteri telefonu bulunamadi", "pdf_sent": False}

        if not callable(send_reservation_pdf_fn):
            return {"status": "error", "message": "PDF gonderim servisi tanimli degil", "pdf_sent": False}

        try:
            pdf_sent = bool(await send_reservation_pdf_fn(customer_phone, reservation))
        except Exception as e:
            return {
                "status": "error",
                "message": "PDF gonderimi sirasinda hata olustu",
                "pdf_sent": False,
                "error": str(e),
            }

        return {
            "status": "ok" if pdf_sent else "error",
            "message": "PDF gonderildi" if pdf_sent else "PDF gonderilemedi",
            "reservation_id": reservation_id,
            "customer_phone": customer_phone,
            "pdf_sent": pdf_sent,
        }

    @router.post("/admin/reservations/{reservation_id}/cancel")
    async def cancel_reservation_api(reservation_id: int, reason: str = ""):
        cancel_reservation_fn(reservation_id, reason)
        try:
            reservation = None
            try:
                reservation = get_reservation_fn(reservation_id)
            except Exception:
                reservation = None
            await notify_admin_cancel_v2_fn(reservation, phone="-", reason=reason, source="admin_panel")
        except Exception:
            pass
        return {"status": "ok", "message": "Rezervasyon iptal edildi"}

    @router.post("/admin/reservations/{reservation_id}/complete")
    async def complete_reservation_api(reservation_id: int):
        update_reservation_status_fn(reservation_id, reservation_status.COMPLETED.value)
        return {"status": "ok", "message": "Rezervasyon tamamlandi (musteri geldi)"}

    @router.post("/admin/reservations/{reservation_id}/noshow")
    async def noshow_reservation_api(reservation_id: int):
        update_reservation_status_fn(reservation_id, reservation_status.NO_SHOW.value)
        return {"status": "ok", "message": "No-show olarak isaretlendi"}

    @router.post("/admin/reservations/{reservation_id}/update")
    async def update_reservation_details(
        reservation_id: int,
        time: str = None,
        date: str = None,
        guest_count: int = None,
        special_requests: str = None,
        notify_customer: bool = True,
    ):
        try:
            conn = sqlite3.connect(str(reservations_db))
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM reservations WHERE id = ?", (reservation_id,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                return {"status": "error", "message": "Rezervasyon bulunamadi"}

            old_time = row[5]
            old_date = row[4]
            old_guest_count = row[6]
            customer_phone = row[1]
            customer_name = row[2]

            updates = []
            params = []
            changes = []
            if time and time != old_time:
                updates.append("time = ?")
                params.append(time)
                changes.append(f"Saat: {old_time} -> {time}")
            if date and date != old_date:
                updates.append("date = ?")
                params.append(date)
                changes.append(f"Tarih: {old_date} -> {date}")
            if guest_count and guest_count != old_guest_count:
                updates.append("guest_count = ?")
                params.append(guest_count)
                changes.append(f"Kisi: {old_guest_count} -> {guest_count}")
            if special_requests is not None:
                updates.append("special_requests = ?")
                params.append(special_requests)
                changes.append("Özel istek güncellendi")
            if not updates:
                conn.close()
                return {"status": "error", "message": "Güncellenecek alan belirtilmedi"}

            updates.append("updated_at = ?")
            params.append(datetime.now().isoformat())
            params.append(reservation_id)
            query = f"UPDATE reservations SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            conn.commit()
            conn.close()

            print(f"Rezervasyon #{reservation_id} güncellendi: {', '.join(changes)}")
            admin_msg = (
                "REZERVASYON GÜNCELLENDİ\n\n"
                f"Rezervasyon: #{reservation_id}\n"
                f"Müşteri: {customer_name}\n"
                f"Telefon: {customer_phone}\n\n"
                "Değişiklikler:\n"
                + "\n".join([f"- {c}" for c in changes])
            )
            await send_whatsapp_message_fn(admin_phone, admin_msg)

            if notify_customer and customer_phone:
                customer_msg = (
                    "Rezervasyonunuz güncellendi.\n\n"
                    f"Sayın {customer_name},\n"
                    + "\n".join([f"- {c}" for c in changes])
                )
                await send_whatsapp_message_fn(customer_phone, customer_msg)

            return {
                "status": "ok",
                "message": "Rezervasyon guncellendi",
                "changes": changes,
                "reservation_id": reservation_id,
            }
        except Exception as e:
            print(f"Rezervasyon guncelleme hatasi: {e}")
            return {"status": "error", "message": str(e)}

    @router.get("/admin/reservations/customer/{phone}")
    async def get_customer_reservations_api(phone: str):
        reservations = get_customer_reservations_fn(phone)
        return {"phone": phone, "count": len(reservations), "reservations": reservations}

    return router
