from __future__ import annotations

import os
import re
import time

from app.content.automation_info import get_runtime_text
from app.services.error_code_service import derive_error_code
from app.services.structured_log_service import log_event


_AI_HANDOFF_PATTERNS = [
    r"\bcanl[ıi]\s+(destek|m[üu]şteri temsilci\w*)\b",
    r"\bm[üu]şteri temsilci\w*\s+(aktar|y[öo]nlendir)",
    r"\blive\s+(support|agent|representative)\b",
    r"\bhuman\s+(agent|representative)\b",
    r"\bconnecting you\b.*\b(live|support|agent)\b",
    r"\baktar[ıi]yorum\b",
    r"\by[öo]nlendiriyorum\b",
]


def _ai_reply_requests_handoff(reply: str) -> bool:
    text = (reply or "").strip().lower()
    if not text:
        return False
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in _AI_HANDOFF_PATTERNS)


def _looks_like_booking_intent(text: str) -> bool:
    low = (text or "").strip().lower()
    if not low:
        return False
    intent_markers = [
        "rezervasyon yapmak istiyorum",
        "rezervasyon istiyorum",
        "rezervasyon oluştur",
        "oda ayırt",
        "oda ayirt",
        "book",
        "reserve",
        "make a reservation",
        "i want this room",
        "i'd like to book",
    ]
    return any(marker in low for marker in intent_markers)


def _reservation_domain(text: str) -> str:
    low = (text or "").strip().lower()
    if any(k in low for k in ("transfer", "havaliman", "airport", "uçuş", "ucus", "flight")):
        return "transfer"
    if any(k in low for k in ("restoran", "restaurant", "masa", "table", "dinner", "akşam yemeği", "aksam yemegi")):
        return "restaurant"
    return "hotel"


def _single_step_reservation_prompt(lang: str, domain: str) -> str:
    lang_norm = (lang or "").strip().lower()
    dom = (domain or "hotel").strip().lower()
    if lang_norm == "en":
        if dom == "transfer":
            return "We will proceed step by step. First step: Please share your transfer date."
        if dom == "restaurant":
            return "We will proceed step by step. First step: For how many guests would you like to reserve?"
        return "To continue your reservation, we will proceed step by step. First step: Please share your full name (first and last name)."
    if dom == "transfer":
        return "Transfer talebi için adım adım ilerleyeceğiz. İlk adım: Lütfen transfer tarihini paylaşın."
    if dom == "restaurant":
        return "Restoran rezervasyonu için adım adım ilerleyeceğiz. İlk adım: Lütfen kişi sayısını paylaşın."
    return "Rezervasyon için adım adım ilerleyeceğiz. İlk adım: Lütfen ad soyad bilginizi paylaşın."


def _looks_like_any_reservation_intent(text: str) -> bool:
    low = (text or "").strip().lower()
    if _looks_like_booking_intent(low):
        return True
    markers = [
        "rezervasyon",
        "reservation",
        "restoran",
        "restaurant",
        "transfer",
        "book a table",
        "table reservation",
        "airport transfer",
    ]
    return any(m in low for m in markers)


def _sanitize_ai_reply(reply: str, user_message: str) -> str:
    text = (reply or "").strip()
    if not text:
        return text

    # Teknik placeholder satırlarını müşteriye gösterme.
    text = re.sub(
        r"\[[^\]\n]*(?:fiyat bilgisi|m[üu]saitlik kontrol)[^\]\n]*\]",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"^.*m[üu]saitlik ve fiyat bilgisi i[cç]in .*kontrol.*$",
        "",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    booking_contact_block_pattern = (
        r"(?:"
        r"Rezervasyonunuzu ilerletebilmem i[cç]in l[üu]tfen:|"
        r"L[üu]tfen rezervasyonunuzu olu[şs]turabilmem i[cç]in a[şs]a[gğ][ıi]daki bilgileri payla[şs][ıi]r m[ıi]s[ıi]n[ıi]z\??|"
        r"To proceed with your reservation, please share:|"
        r"To create the transfer, please share.*?:|"
        r"To create your restaurant reservation, please share.*?:"
        r")[\s\S]*$"
    )
    generic_multi_info_block_pattern = (
        r"(?is)"
        r"(?:"
        r"[^\n]*(?:a[şs]a[gğ][ıi]daki\s+bilgileri\s+payla[şs][ıi]n|following\s+details?\s+to\s+share)[^\n]*:?[\t ]*(?:\n|$)"
        r"(?:\s*(?:\d+[\)\.\-:]|[-*])\s*.+(?:\n|$)){2,}"
        r"|"
        r"(?:l[üu]tfen|please)[^\n]*(?:bilgi|details?)[^\n]*(?:payla[şs]|share)[^\n]*:?[\t ]*(?:\n|$)"
        r"(?:\s*(?:\d+[\)\.\-:]|[-*])\s*.+(?:\n|$)){2,}"
        r"|"
        r"(?:^|\n)(?:\s*(?:\d+[\)\.\-:]|[-*])\s*.+(?:\n|$)){3,}$"
        r")"
    )

    # Toplu bilgi isteme bloğu varsa, rezervasyon niyetinde tek-adım isteme mesajına indir.
    # Rezervasyon niyeti yoksa bloğu tamamen kaldır.
    if re.search(booking_contact_block_pattern, text, flags=re.IGNORECASE):
        if _looks_like_any_reservation_intent(user_message):
            lang = "en" if re.search(r"\b(?:to proceed with your reservation|please share)\b", text, flags=re.IGNORECASE) else "tr"
            domain = _reservation_domain(user_message + "\n" + text)
            text = re.sub(
                booking_contact_block_pattern,
                _single_step_reservation_prompt(lang, domain),
                text,
                flags=re.IGNORECASE,
            ).strip()
        else:
            text = re.sub(
                booking_contact_block_pattern,
                "",
                text,
                flags=re.IGNORECASE,
            ).strip()
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
    elif _looks_like_any_reservation_intent(user_message) and re.search(generic_multi_info_block_pattern, text, flags=re.IGNORECASE | re.MULTILINE):
        lang = "en" if re.search(r"\b(?:please|reservation|transfer|restaurant)\b", text, flags=re.IGNORECASE) and not re.search(r"[çğıöşüÇĞİÖŞÜ]", text) else "tr"
        domain = _reservation_domain(user_message + "\n" + text)
        text = re.sub(
            generic_multi_info_block_pattern,
            _single_step_reservation_prompt(lang, domain),
            text,
            flags=re.IGNORECASE | re.MULTILINE,
        ).strip()
        text = re.sub(r"\n{3,}", "\n\n", text).strip()

    return text


async def handle_openai_fallback(
    *,
    client,
    openai_model: str,
    info_system_prompt: str,
    history: list,
    user_message: str,
    phone: str,
    start_time: float,
    add_to_history_fn,
    save_message_fn,
    schedule_followup_fn,
    record_metric_fn,
    maybe_start_qa_background_fn,
    qa_enabled: bool,
    qa_agent,
    admin_phone: str,
    send_whatsapp_message_fn,
    qa_fail_notifications: list,
    record_error_fn,
    response_factory,
    flow_context=None,
    notify_admin_handoff_fn=None,
    activate_human_takeover_fn=None,
    detected_intent: str = "AI_FALLBACK",
    handoff_source: str = "chat_pipeline.ai_fallback",
):
    correlation_id = getattr(flow_context, "correlation_id", None) if flow_context is not None else None
    # Test ortaminda dis OpenAI cagrisi yapma; deterministic yanit don.
    if os.getenv("OPENAI_API_KEY", "").strip().lower().startswith("test-"):
        fallback_reply = (
            "Elbette, rezervasyon konusunda yardımcı olabilirim. "
            "Lütfen tarih aralığı ve kişi bilgisi paylaşın."
        )
        add_to_history_fn(phone, "user", user_message)
        add_to_history_fn(phone, "assistant", fallback_reply)
        save_message_fn(phone, user_message, fallback_reply)
        schedule_followup_fn(phone)
        elapsed = time.time() - start_time
        record_metric_fn("openai", category="test_fallback", response_time=elapsed)
        return response_factory(reply=fallback_reply, status="ok")

    try:
        messages = [{"role": "system", "content": info_system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})
        completion = client.chat.completions.create(
            model=openai_model,
            messages=messages,
            temperature=0.3,
            max_tokens=500,
        )
        reply = _sanitize_ai_reply(completion.choices[0].message.content, user_message)
        add_to_history_fn(phone, "user", user_message)
        add_to_history_fn(phone, "assistant", reply)
        save_message_fn(phone, user_message, reply)
        schedule_followup_fn(phone)
        elapsed = time.time() - start_time
        record_metric_fn("openai", category="general", response_time=elapsed)
        maybe_start_qa_background_fn(
            qa_enabled=qa_enabled,
            qa_agent=qa_agent,
            user_message=user_message,
            reply=reply,
            phone=phone,
            admin_phone=admin_phone,
            send_whatsapp_message_fn=send_whatsapp_message_fn,
            qa_fail_notifications=qa_fail_notifications,
        )
        if _ai_reply_requests_handoff(reply):
            try:
                if callable(notify_admin_handoff_fn):
                    await notify_admin_handoff_fn(
                        category="canli_destek",
                        priority="high",
                        customer_phone=phone,
                        customer_message=user_message,
                        source=handoff_source,
                        detected_intent=detected_intent,
                        confidence=0.75,
                        conversation_summary="AI reply indicated human handoff.",
                        attempted_actions=["openai_fallback"],
                        suggested_reply=(reply or "")[:240],
                        tags=["ai_declared_handoff", "strict_ai_first_guard"],
                        correlation_id=correlation_id,
                    )
            except Exception:
                pass
            try:
                if callable(activate_human_takeover_fn):
                    activate_human_takeover_fn(phone, reason="ai_declared_handoff")
            except Exception:
                pass
            log_event(
                "chat.openai.handoff_inferred",
                correlation_id=correlation_id,
                phone=phone,
                detected_intent=detected_intent,
            )
            return response_factory(reply=reply, status="handoff")
        log_event(
            "chat.openai.success",
            correlation_id=correlation_id,
            phone=phone,
            message_len=len(user_message or ""),
        )
        return response_factory(reply=reply, status="ok")
    except Exception as e:
        error_msg = str(e)
        error_type = type(e).__name__
        error_code = derive_error_code(
            event="chat.openai.error",
            error_type=error_type,
            message=error_msg,
        )
        print(f"❌ CHAT HATASI [{error_code}/{error_type}]: {error_msg}")
        log_event(
            "chat.openai.error",
            level="ERROR",
            correlation_id=correlation_id,
            phone=phone,
            error_code=error_code,
            error_type=error_type,
            error_message=error_msg[:300],
        )
        record_error_fn("chat_error", f"{error_code}: {error_type}: {error_msg}")
        elapsed = time.time() - start_time
        record_metric_fn("error", category=f"chat_{error_type}", response_time=elapsed)
        try:
            admin_alert = f"""🔴 TEKNİK HATA
⏱️ Süre: {elapsed:.1f}s
📱 Telefon: {phone or 'Bilinmiyor'}
❌ Hata Tipi: {error_type}
❌ Hata: {error_msg[:300]}
💬 Mesaj:
{user_message[:150] if user_message else 'Bilinmiyor'}"""
            await send_whatsapp_message_fn(admin_phone, admin_alert)
        except Exception as notify_err:
            print(f"Admin bildirim hatası: {notify_err}")

        from app.utils.message_utils import detect_language as _detect_lang

        err_lang = _detect_lang(user_message) if user_message else "tr"
        fallback_reply = get_runtime_text(
            ("fallback", "technical_error"),
            lang=err_lang,
            default="Teknik bir aksaklık oluştu. İsterseniz sizi canlı destek ekibimize bağlayabilirim.",
        )
        save_message_fn(phone, user_message, f"[HATA - {error_type}] {error_msg[:100]}")
        add_to_history_fn(phone, "user", user_message)
        add_to_history_fn(phone, "assistant", fallback_reply)
        save_message_fn(phone, user_message, f"[FALLBACK-DETERMINISTIC] {fallback_reply}")
        schedule_followup_fn(phone)
        print(f"⚠️ Deterministic fallback uygulandı: {error_type}")
        return response_factory(reply=fallback_reply, status="fallback_deterministic")
