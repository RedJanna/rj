from __future__ import annotations

import asyncio
import threading
from datetime import datetime


def maybe_start_qa_background(
    *,
    qa_enabled: bool,
    qa_agent,
    user_message: str,
    reply: str,
    phone: str,
    admin_phone: str,
    send_whatsapp_message_fn,
    qa_fail_notifications: list,
):
    if not (qa_enabled and reply and user_message):
        return

    try:
        def run_qa():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                evaluation = loop.run_until_complete(qa_agent.evaluate(user_message, reply, phone))
                if evaluation.get("overall_score", 5) >= 4:
                    return

                now = datetime.now()
                qa_fail_notifications[:] = [t for t in qa_fail_notifications if (now - t).total_seconds() < 3600]
                if len(qa_fail_notifications) >= 5:
                    print(f"⚠️ QA - bildirim limiti aşıldı (son 1 saatte {len(qa_fail_notifications)} bildirim)")
                    return

                score = evaluation.get("overall_score", 0)
                issues = evaluation.get("issues", [])
                emoji = "🔴" if score < 2.5 else "🟡"
                level = "FAIL" if score < 2.5 else "REVIEW"
                notify_msg = f"""{emoji} QA {level} UYARISI
📊 Skor: {score}/5
📱 Telefon: {phone[:6]}*** 
❓ Müşteri:
{user_message[:150]}
🤖 Bot:
{reply[:200]}
⚠️ Sorunlar:
{chr(10).join(['• ' + i for i in issues[:3]]) if issues else '• Belirtilmedi'}"""
                loop.run_until_complete(send_whatsapp_message_fn(admin_phone, notify_msg))
                qa_fail_notifications.append(now)
                print(f"📤 QA {level} bildirimi gönderildi ({len(qa_fail_notifications)}/5)")
            finally:
                loop.close()

        qa_thread = threading.Thread(target=run_qa, daemon=True)
        qa_thread.start()
    except Exception as e:
        print(f"QA thread hatası: {e}")
