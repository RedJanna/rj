from __future__ import annotations

import httpx
import re


def build_reservation_pdf_sender(*, generate_reservation_pdf_fn, whatsapp_phone_id: str, whatsapp_token: str):
    async def send_reservation_pdf(phone: str, reservation: dict) -> bool:
        try:
            clean_phone = re.sub(r"[^\d]", "", phone or "")
            if not clean_phone:
                print("PDF gönderimi atlandı: geçersiz telefon")
                return False
            pdf_path = generate_reservation_pdf_fn(reservation)
            if not pdf_path:
                print("PDF oluşturulamadı")
                return False

            upload_url = f"https://graph.facebook.com/v22.0/{whatsapp_phone_id}/media"
            with open(pdf_path, "rb") as pdf_file:
                files = {"file": (f"rezervasyon_{reservation['id']}.pdf", pdf_file, "application/pdf")}
                data = {"messaging_product": "whatsapp"}
                headers = {"Authorization": f"Bearer {whatsapp_token}"}
                async with httpx.AsyncClient() as client_http:
                    upload_response = await client_http.post(upload_url, headers=headers, files=files, data=data)
                    if upload_response.status_code != 200:
                        print(f"PDF upload hatası: {upload_response.text}")
                        return False
                    media_id = upload_response.json().get("id")

            message_url = f"https://graph.facebook.com/v22.0/{whatsapp_phone_id}/messages"
            payload = {
                "messaging_product": "whatsapp",
                "to": clean_phone,
                "type": "document",
                "document": {
                    "id": media_id,
                    "filename": f"Kassandra_Rezervasyon_{reservation['id']}.pdf",
                    "caption": f"🍽️ Rezervasyon Onay Belgesi\n#{reservation['id']}",
                },
            }
            async with httpx.AsyncClient() as client_http:
                response = await client_http.post(
                    message_url,
                    headers={"Authorization": f"Bearer {whatsapp_token}", "Content-Type": "application/json"},
                    json=payload,
                )
                if response.status_code == 200:
                    print(f"✅ PDF gönderildi: {phone}")
                    return True
                print(f"❌ PDF gönderme hatası: {response.text}")
                return False
        except Exception as e:
            print(f"❌ PDF gönderme hatası: {e}")
            return False

    return send_reservation_pdf
