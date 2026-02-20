from __future__ import annotations

from datetime import datetime


def build_notify_admin_reservation_change(
    *,
    send_whatsapp_message_fn,
    get_reservation_fn,
    admin_phone: str,
    restaurant_staff: dict,
):
    async def notify_admin_reservation_change(
        reservation_id: int,
        change_type: str,
        old_data: dict = None,
        new_data: dict = None,
        changed_by: str = "customer",
    ):
        reservation = get_reservation_fn(reservation_id)
        if not reservation:
            return

        type_info = {
            "update": ("🔄", "REZERVASYON GÜNCELLENDİ"),
            "cancel": ("❌", "REZERVASYON İPTAL EDİLDİ"),
            "confirm": ("✅", "REZERVASYON ONAYLANDI"),
            "modify": ("📝", "REZERVASYON DEĞİŞTİRİLDİ"),
            "reschedule": ("📅", "REZERVASYON TARİHİ DEĞİŞTİ"),
        }
        emoji, title = type_info.get(change_type, ("📋", "REZERVASYON DEĞİŞİKLİĞİ"))

        changes_text = ""
        if old_data and new_data:
            changes = []
            for key in ["date", "time", "guest_count", "customer_name"]:
                old_val = old_data.get(key, "")
                new_val = new_data.get(key, "")
                if str(old_val) != str(new_val):
                    key_names = {
                        "date": "Tarih",
                        "time": "Saat",
                        "guest_count": "Kişi",
                        "customer_name": "İsim",
                    }
                    changes.append(f"• {key_names.get(key, key)}: {old_val} → {new_val}")
            if changes:
                changes_text = "\n📝 DEĞİŞİKLİKLER:\n" + "\n".join(changes)

        msg = f"""{emoji} {title}

📋 Rezervasyon ID: #{reservation['id']}
👤 Müşteri: {reservation.get('customer_name', 'Bilinmiyor')}
📱 Telefon: {reservation.get('customer_phone', 'Bilinmiyor')}

📅 Tarih: {reservation.get('date', '')}
🕐 Saat: {reservation.get('time', '')}
👥 Kişi: {reservation.get('guest_count', '')}
{changes_text}

🕐 İşlem: {datetime.now().strftime('%d.%m.%Y %H:%M')}
👤 Yapan: {changed_by}
"""

        await send_whatsapp_message_fn(admin_phone, msg)
        manager_phone = restaurant_staff.get("manager", {}).get("phone")
        if manager_phone:
            await send_whatsapp_message_fn(manager_phone, msg)

    return notify_admin_reservation_change
