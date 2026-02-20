from __future__ import annotations

import re

import httpx


def clean_message_for_customer(message: str) -> str:
    """Dahili etiketleri müşteriye giden metinden temizle."""
    internal_tags = [
        r"\[RESERVATION\]\s*",
        r"\[REZERVASYON\]\s*",
        r"\[HANDOFF\]\s*",
        r"\[İNSANA DEVİR[^\]]*\]\s*",
        r"\[LOCAL[^\]]*\]\s*",
        r"\[OPENAI\]\s*",
        r"\[DEBUG\]\s*",
        r"\[SYSTEM\]\s*",
        r"\[ERROR\]\s*",
        r"\[ŞÜPHELİ[^\]]*\]\s*",
        r"\[SUSPICIOUS[^\]]*\]\s*",
        r"\[REZERVASYON BAŞLADI\]\s*",
    ]
    cleaned = message
    for tag in internal_tags:
        cleaned = re.sub(tag, "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def build_whatsapp_sender(whatsapp_phone_id: str, whatsapp_token: str):
    async def send_whatsapp_message(phone: str, message: str) -> bool:
        clean_message = clean_message_for_customer(message)
        if not whatsapp_phone_id or not whatsapp_token:
            print("WhatsApp API bilgileri eksik!")
            return False

        url = f"https://graph.facebook.com/v22.0/{whatsapp_phone_id}/messages"
        headers = {"Authorization": f"Bearer {whatsapp_token}", "Content-Type": "application/json"}
        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "text",
            "text": {"body": clean_message},
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload)
                return response.status_code == 200
        except Exception as e:
            print(f"WhatsApp mesaj gönderme hatası: {e}")
            return False

    return send_whatsapp_message
