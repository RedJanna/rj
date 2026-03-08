from __future__ import annotations

import json
import os
import re
from datetime import date as date_type
from typing import Any, Dict

from app.core.settings_service import load_settings

LANGUAGE_CODES = ["tr", "en", "ru", "de", "ar", "es", "fr", "zh", "hi", "pt"]

DEFAULT_WELCOME_I18N: dict[str, str] = {
    "tr": (
        "Merhaba,\n\n"
        "Kassandra Ölüdeniz'e hoş geldiniz. 🌊\n"
        "Size özel bir konaklama deneyimi hazırlamak için buradayım.\n\n"
        "Size nasıl yardımcı olabilirim?\n"
        "1. Rezervasyon / Oda bilgisi\n"
        "2. Transfer & Ulasim\n"
        "3. Restoran & kahvaltı\n"
        "4. Özel istekler (surpriz, kutlama, vb.)\n\n"
        "Seciminizi numara ile belirtebilir veya doğrudan sorunuzu yazabilirsiniz 😊"
    ),
    "en": (
        "Hello! 👋\n\n"
        "Welcome to Kassandra Ölüdeniz. 🌊\n"
        "I am here to help you with a special accommodation experience.\n\n"
        "How can I assist you today?\n"
        "1. Reservation / Room information\n"
        "2. Transfer & Transportation\n"
        "3. Restaurant & Breakfast\n"
        "4. Special requests (surprise, celebration, etc.)\n\n"
        "You can type a number or ask your question directly 😊"
    ),
    "ru": (
        "Здравствуйте! 👋\n\n"
        "Добро пожаловать в Kassandra Oludeniz. 🌊\n"
        "Я здесь, чтобы помочь вам организовать незабываемый отдых.\n\n"
        "Чем могу помочь?\n"
        "1. Бронирование / Информация о номерах\n"
        "2. Трансфер и транспорт\n"
        "3. Ресторан и завтрак\n"
        "4. Особые пожелания (сюрприз, праздник и т.д.)\n\n"
        "Вы можете выбрать номер или задать вопрос напрямую 😊"
    ),
    "de": (
        "Hallo! 👋\n\n"
        "Willkommen im Kassandra Oludeniz. 🌊\n"
        "Ich bin hier, um Ihnen bei einem besonderen Aufenthalt zu helfen.\n\n"
        "Wie kann ich Ihnen heute helfen?\n"
        "1. Reservierung / Zimmerinformationen\n"
        "2. Transfer & Transport\n"
        "3. Restaurant & Frühstück\n"
        "4. Sonderwünsche (Überraschung, Feier usw.)\n\n"
        "Sie können eine Nummer eingeben oder Ihre Frage direkt schreiben 😊"
    ),
    "ar": (
        "مرحبا! 👋\n\n"
        "مرحبا بك في Kassandra Oludeniz. 🌊\n"
        "أنا هنا لمساعدتك في تجربة إقامة مميزة.\n\n"
        "كيف يمكنني مساعدتك اليوم؟\n"
        "1. الحجز / معلومات الغرف\n"
        "2. النقل والمواصلات\n"
        "3. المطعم والإفطار\n"
        "4. الطلبات الخاصة (مفاجأة، احتفال، إلخ)\n\n"
        "يمكنك كتابة رقم الخيار أو إرسال سؤالك مباشرة 😊"
    ),
    "es": (
        "Hola! 👋\n\n"
        "Bienvenido a Kassandra Oludeniz. 🌊\n"
        "Estoy aqui para ayudarte con una experiencia de alojamiento especial.\n\n"
        "Como puedo ayudarte hoy?\n"
        "1. Reserva / Informacion de habitaciones\n"
        "2. Traslado y transporte\n"
        "3. Restaurante y desayuno\n"
        "4. Solicitudes especiales (sorpresa, celebracion, etc.)\n\n"
        "Puedes escribir un numero o hacer tu pregunta directamente 😊"
    ),
    "fr": (
        "Bonjour! 👋\n\n"
        "Bienvenue a Kassandra Oludeniz. 🌊\n"
        "Je suis la pour vous aider a organiser un sejour exceptionnel.\n\n"
        "Comment puis-je vous aider aujourd'hui ?\n"
        "1. Reservation / Informations sur les chambres\n"
        "2. Transfert et transport\n"
        "3. Restaurant et petit-dejeuner\n"
        "4. Demandes speciales (surprise, celebration, etc.)\n\n"
        "Vous pouvez taper un numero ou poser votre question directement 😊"
    ),
    "zh": (
        "您好！👋\n\n"
        "欢迎来到 Kassandra Oludeniz。🌊\n"
        "我在这里为您提供特别的住宿协助。\n\n"
        "今天我可以如何帮助您？\n"
        "1. 预订 / 房型信息\n"
        "2. 接送与交通\n"
        "3. 餐厅与早餐\n"
        "4. 特别需求（惊喜、庆祝等）\n\n"
        "您可以输入数字，或直接发送您的问题 😊"
    ),
    "hi": (
        "नमस्ते! 👋\n\n"
        "Kassandra Oludeniz में आपका स्वागत है। 🌊\n"
        "मैं आपकी विशेष ठहरने की योजना में मदद करने के लिए यहां हूं।\n\n"
        "आज मैं आपकी कैसे मदद कर सकता/सकती हूं?\n"
        "1. बुकिंग / कमरे की जानकारी\n"
        "2. ट्रांसफर और परिवहन\n"
        "3. रेस्टोरेंट और नाश्ता\n"
        "4. विशेष अनुरोध (सरप्राइज़, सेलिब्रेशन आदि)\n\n"
        "आप नंबर टाइप कर सकते हैं या अपना प्रश्न सीधे लिख सकते हैं 😊"
    ),
    "pt": (
        "Ola! 👋\n\n"
        "Bem-vindo ao Kassandra Oludeniz. 🌊\n"
        "Estou aqui para ajudar voce com uma experiencia de hospedagem especial.\n\n"
        "Como posso ajudar voce hoje?\n"
        "1. Reserva / Informacoes sobre quartos\n"
        "2. Transfer e transporte\n"
        "3. Restaurante e cafe da manha\n"
        "4. Pedidos especiais (surpresa, celebracao etc.)\n\n"
        "Voce pode digitar um numero ou fazer sua pergunta diretamente 😊"
    ),
}

DEFAULT_HOTEL_RUNTIME_INFO: dict[str, Any] = {
    "dalaman_transfer_fee_eur": 75,
    "antalya_transfer_fee_eur": 140,
    "hotel_opening_mmdd": "04-01",
    "hotel_closing_mmdd": "11-30",
    "free_cancellation_days_before_checkin": 5,
    "free_cancel_sales_followup_days_before_checkin": 5,
    "restaurant_bar_closing_time": "22:00",
    "pool_bar_closing_time": "22:00",
    "message_delay_seconds": 0,
    "admin_phone": "905304498453",
    "chef_phone": "905012969548",
    "welcome_message_tr": DEFAULT_WELCOME_I18N["tr"],
    "welcome_message_i18n": dict(DEFAULT_WELCOME_I18N),
}

_KNOWN_RUNTIME_KEYS = set(DEFAULT_HOTEL_RUNTIME_INFO.keys())


def _clean_phone(raw: Any) -> str:
    return "".join(ch for ch in str(raw or "") if ch.isdigit())


def _normalize_mmdd(raw: Any, default: str) -> str:
    text = str(raw or "").strip()
    if not re.fullmatch(r"\d{2}-\d{2}", text):
        return default
    month = int(text[:2])
    day = int(text[3:])
    if month < 1 or month > 12:
        return default
    if day < 1 or day > 31:
        return default
    return text


def _normalize_hhmm(raw: Any, default: str) -> str:
    text = str(raw or "").strip()
    if not re.fullmatch(r"\d{2}:\d{2}", text):
        return default
    hh = int(text[:2])
    mm = int(text[3:])
    if hh < 0 or hh > 23:
        return default
    if mm < 0 or mm > 59:
        return default
    return text


def normalize_hotel_runtime_info(payload: Dict[str, Any] | None) -> dict[str, Any]:
    out = dict(DEFAULT_HOTEL_RUNTIME_INFO)
    src = payload if isinstance(payload, dict) else {}

    def _read_int(key: str, default: int, min_value: int, max_value: int) -> int:
        try:
            val = int(src.get(key, default))
        except Exception:
            return default
        return max(min_value, min(max_value, val))

    out["dalaman_transfer_fee_eur"] = _read_int("dalaman_transfer_fee_eur", out["dalaman_transfer_fee_eur"], 0, 5000)
    out["antalya_transfer_fee_eur"] = _read_int("antalya_transfer_fee_eur", out["antalya_transfer_fee_eur"], 0, 5000)
    out["hotel_opening_mmdd"] = _normalize_mmdd(src.get("hotel_opening_mmdd"), out["hotel_opening_mmdd"])
    out["hotel_closing_mmdd"] = _normalize_mmdd(src.get("hotel_closing_mmdd"), out["hotel_closing_mmdd"])
    out["free_cancellation_days_before_checkin"] = _read_int(
        "free_cancellation_days_before_checkin",
        out["free_cancellation_days_before_checkin"],
        0,
        30,
    )
    out["free_cancel_sales_followup_days_before_checkin"] = _read_int(
        "free_cancel_sales_followup_days_before_checkin",
        out["free_cancel_sales_followup_days_before_checkin"],
        0,
        30,
    )
    out["restaurant_bar_closing_time"] = _normalize_hhmm(
        src.get("restaurant_bar_closing_time"), out["restaurant_bar_closing_time"]
    )
    out["pool_bar_closing_time"] = _normalize_hhmm(src.get("pool_bar_closing_time"), out["pool_bar_closing_time"])
    out["message_delay_seconds"] = _read_int("message_delay_seconds", out["message_delay_seconds"], 0, 12)

    admin_phone = _clean_phone(src.get("admin_phone") or out["admin_phone"])
    chef_phone = _clean_phone(src.get("chef_phone") or out["chef_phone"])
    out["admin_phone"] = admin_phone or out["admin_phone"]
    out["chef_phone"] = chef_phone or out["chef_phone"]

    tr_text = str(src.get("welcome_message_tr") or out["welcome_message_tr"]).strip()
    out["welcome_message_tr"] = tr_text or out["welcome_message_tr"]

    raw_i18n = src.get("welcome_message_i18n")
    merged_i18n: dict[str, str] = dict(DEFAULT_WELCOME_I18N)
    if isinstance(raw_i18n, dict):
        for code in LANGUAGE_CODES:
            val = str(raw_i18n.get(code) or "").strip()
            if val:
                merged_i18n[code] = val
    merged_i18n["tr"] = out["welcome_message_tr"]
    out["welcome_message_i18n"] = merged_i18n

    # Forward compatibility: preserve unknown keys from admin runtime payload.
    # This lets newly added runtime fields become immediately available without code changes.
    for key, value in src.items():
        if key in _KNOWN_RUNTIME_KEYS:
            continue
        out[key] = value

    return out


def get_hotel_runtime_info(settings: dict[str, Any] | None = None) -> dict[str, Any]:
    s = settings if isinstance(settings, dict) else load_settings()
    payload = s.get("hotel_runtime_info")
    return normalize_hotel_runtime_info(payload if isinstance(payload, dict) else {})


def get_message_delay_seconds() -> int:
    info = get_hotel_runtime_info()
    try:
        return int(info.get("message_delay_seconds") or 0)
    except Exception:
        return 0


def season_bounds_for_year(year: int, info: dict[str, Any] | None = None) -> tuple[date_type, date_type]:
    payload = info or get_hotel_runtime_info()
    open_mmdd = str(payload.get("hotel_opening_mmdd") or "04-01")
    close_mmdd = str(payload.get("hotel_closing_mmdd") or "11-30")
    open_month, open_day = [int(x) for x in open_mmdd.split("-")]
    close_month, close_day = [int(x) for x in close_mmdd.split("-")]
    return date_type(year, open_month, open_day), date_type(year, close_month, close_day)


def build_cancellation_policy_reply(lang: str = "tr", info: dict[str, Any] | None = None) -> str:
    payload = info or get_hotel_runtime_info()
    days = int(payload.get("free_cancellation_days_before_checkin") or 5)
    lang_norm = (lang or "en").strip().lower()
    if lang_norm == "tr":
        return (
            "Iptal/iade kosullari tarife gore degisir:\n"
            "- Iade yapilmaz (non-refundable): daha avantajli fiyattir, iptal/iade yoktur.\n"
            f"- Ucretsiz iptal tarifesi: fiyati daha yuksektir; giristen {days} gun oncesine kadar iptalde %100 geri odeme yapilir.\n"
            "- Giristen sonra iptal/iade secenegi bulunmamaktadir."
        )
    if lang_norm == "ru":
        return (
            "Условия отмены зависят от типа тарифа:\n"
            "- Невозвратный тариф: цена ниже, отмена/возврат не предусмотрены.\n"
            f"- Тариф с бесплатной отменой: цена выше, 100% возврат при отмене не позднее чем за {days} дней до заезда.\n"
            "- После заезда отмена/возврат не предусмотрены."
        )
    return (
        "Our cancellation policy depends on rate type:\n"
        "- Non-refundable: lower price, no cancellation/refund.\n"
        f"- Free Cancellation: higher price, 100% refund up to {days} days before check-in.\n"
        "- After check-in: no cancellation/refund is available."
    )


def maybe_generate_welcome_translations(welcome_message_tr: str, current_i18n: dict[str, str] | None = None) -> dict[str, str]:
    base = dict(DEFAULT_WELCOME_I18N)
    if isinstance(current_i18n, dict):
        for code in LANGUAGE_CODES:
            val = str(current_i18n.get(code) or "").strip()
            if val:
                base[code] = val
    tr_text = str(welcome_message_tr or "").strip()
    if not tr_text:
        return base
    base["tr"] = tr_text

    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return base

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        model = (os.getenv("OPENAI_MODEL") or "gpt-4.1-mini").strip() or "gpt-4.1-mini"
        target_langs = [c for c in LANGUAGE_CODES if c != "tr"]
        prompt = (
            "Translate this Turkish welcome message to target languages.\n"
            "Return strict JSON object only. Keys must be: "
            + ", ".join(target_langs)
            + ". Keep emojis, numbering and line breaks.\n\n"
            f"Turkish text:\n{tr_text}"
        )
        completion = client.chat.completions.create(
            model=model,
            temperature=0.1,
            messages=[
                {"role": "system", "content": "You are a professional hotel localization translator."},
                {"role": "user", "content": prompt},
            ],
        )
        raw = (completion.choices[0].message.content or "").strip()
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            for code in target_langs:
                val = str(parsed.get(code) or "").strip()
                if val:
                    base[code] = val
    except Exception:
        return base


def build_runtime_hard_override_block(info: dict[str, Any] | None = None) -> str:
    payload = info or get_hotel_runtime_info()
    open_mmdd = str(payload.get("hotel_opening_mmdd") or "04-01")
    close_mmdd = str(payload.get("hotel_closing_mmdd") or "11-30")
    dalaman_fee = int(payload.get("dalaman_transfer_fee_eur") or 75)
    antalya_fee = int(payload.get("antalya_transfer_fee_eur") or 140)
    free_cancel_days = int(payload.get("free_cancellation_days_before_checkin") or 5)
    sales_followup_days = int(payload.get("free_cancel_sales_followup_days_before_checkin") or 5)
    restaurant_close = str(payload.get("restaurant_bar_closing_time") or "22:00")
    pool_close = str(payload.get("pool_bar_closing_time") or "22:00")
    runtime_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return (
        "\n\nRUNTIME_HOTEL_CONFIG (HARD OVERRIDE):\n"
        f"- Season open/close (MM-DD): {open_mmdd} - {close_mmdd}\n"
        f"- Dalaman transfer one-way fee: {dalaman_fee} EUR\n"
        f"- Antalya transfer one-way fee: {antalya_fee} EUR\n"
        f"- Free cancellation window: {free_cancel_days} days before check-in\n"
        f"- Free-cancel sales follow-up lead time: {sales_followup_days} days before check-in\n"
        f"- Restaurant-bar closing time: {restaurant_close}\n"
        f"- Pool-bar closing time: {pool_close}\n"
        f"- Full runtime payload (JSON): {runtime_json}\n"
        "- If any static text conflicts with this block, ALWAYS use this block.\n"
        "- If a new key appears in runtime payload, treat it as authoritative."
    )
    return base
