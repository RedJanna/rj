"""app/handlers/booking_flow_handler.py

Otel rezervasyon (booking) konusma akisi - State Machine.
Fiyat listesi gosterildikten sonra musteri "bu odayi istiyorum" derse
adim adim bilgi toplar, onayla, admin'e iletir.

TEMEL KURAL: Insan onayi olmadan ASLA rezervasyon olusturulmaz.

v1 - 2026-02-15
"""

from __future__ import annotations

import os
import json
import re
import hashlib
import unicodedata
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
from app.services.elektra_hoteladvisor_service import (
    hoteladvisor_function,
    hoteladvisor_select,
    hoteladvisor_execute,
    hoteladvisor_update,
)
from app.services.notification_service import notify_admin_handoff
from app.services.access_control_service import activate_human_takeover
from app.services.metrics_service import record_metric
from app.services.elektraweb_booking_service import fetch_price
from app.services.elektraweb_booking_service import update_elektraweb_reservation

from app.services.booking_flow_service import (
    BookingFlowState,
    BookingStatus,
    get_booking_flow,
    save_booking_flow,
    clear_booking_flow,
    is_booking_flow_active,
    get_price_offers,
    get_available_rooms_from_offers,
    find_offer_by_selection,
    create_hotel_booking,
    get_latest_booking_by_phone,
    get_hotel_booking,
    get_booking_by_context_id,
    get_active_bookings_by_phone,
    save_payment_context,
    get_payment_context,
    clear_payment_context,
    ROOM_TYPE_MAP,
)
from app.core.settings_service import get_quiet_room_policy


# ============================
# Turkish lowercase helper
# ============================

def _turkish_lower(text: str) -> str:
    result = text.replace("\u0130", "i").replace("I", "\u0131")
    return result.lower()


def _normalize_match_text(text: str) -> str:
    """Turkce karakterleri normalize edip karsilastirma metni uret."""
    low = _turkish_lower(text or "")
    return (
        low.replace("ç", "c")
        .replace("ğ", "g")
        .replace("ı", "i")
        .replace("ö", "o")
        .replace("ş", "s")
        .replace("ü", "u")
    )


# ============================
# Booking Intent Detection
# ============================

BOOKING_INTENT_TR = [
    "bu odayi istiyorum", "bu odayi istiyorum",
    "rezervasyon yaptirmak", "rezervasyon yaptirmak istiyorum",
    "oda ayirtmak", "oda ayirmak",
    "rezervasyon yapmak", "rez yapmak",
    "ayirtmak istiyorum",
    "superior istiyorum", "deluxe istiyorum", "exclusive istiyorum",
    "penthouse istiyorum", "premium istiyorum",
    "iade yapilmaz istiyorum", "ucretsiz iptal istiyorum",
    "bu odayi alayim", "bu odayi seciyorum",
    "rezervasyon olustur", "rez olustur",
    "bu oda olsun", "tercih ediyorum",
    "oda secmek istiyorum", "oda secimi",
    "rezervasyon istiyorum",
    "rezerve etmek", "rezerve istiyorum",
    "odayi istiyorum", "odayi alayim",
    "oda istiyorum", "oda alayim",
    # Oda + rezervasyon kaliplari
    "rezervasyon yapabilir", "rezervasyon yapabilir miyiz",
    "rezervasyon yapabilir miyim", "rezervasyon yaptirabili",
    "rezervasyon yapnak istiyorum",
    "oda rezervasyonu", "oda rezervasyon",
    "oda icin rezervasyon", "odasi icin rezervasyon",
    # "X oda istiyorum / tercih ediyorum" kaliplari
    "superior oda", "deluxe oda", "exclusive oda",
    "penthouse oda", "premium oda",
    "superior odayi", "deluxe odayi", "exclusive odayi",
    "penthouse odayi", "premium odayi",
    # Genel rezervasyon ifadeleri
    "rez yapabilir miyiz", "rez yapabilir miyim",
    "konaklama istiyorum", "konaklamak istiyorum",
    "kalmak istiyorum", "oda tutmak",
    # Rezervasyonu başlatma / bilgi paylaşma niyeti
    "rezervasyonu baslatalim", "rezervasyonu baslatalim",
    "rezervasyonu baslatalım", "rezervasyonu baslat",
    "rezervasyonu olusturalim", "rezervasyonu olustur",
    "rezervasyon baslatalim", "rezervasyonu baslatmak istiyorum",
    "isim soyisim ve telefonumu gondereyim",
    "ad soyad ve telefonumu gondereyim",
]

BOOKING_INTENT_EN = [
    "i want this room", "i'd like to book",
    "book this room", "make a reservation",
    "reserve this room", "i want to reserve",
    "i'll take", "i want the",
    "book the superior", "book the deluxe",
    "book the exclusive", "book the penthouse",
    "book the premium", "i choose",
    "i'd like the", "create reservation",
    "i want to book",
    # Extended patterns
    "can we reserve", "can i reserve", "can we book",
    "can i book", "like to reserve",
    "want to make a reservation", "want a reservation",
    "superior room", "deluxe room", "exclusive room",
    "penthouse room", "premium room",
]


def detect_booking_intent(message: str) -> bool:
    """Mesajda otel booking niyeti var mi?"""
    low = _normalize_match_text(message or "")
    for kw in BOOKING_INTENT_TR:
        if _normalize_match_text(kw) in low:
            return True
    for kw in BOOKING_INTENT_EN:
        if _normalize_match_text(kw) in low:
            return True

    # Regex tabanli yakalama: "rezervasyonu başlatalım/oluşturalım" gibi varyantlar
    if re.search(r"\brezerv\w*\s*(?:baslat|olustur|onay)\w*", low):
        return True
    if re.search(r"\b(?:start|create)\s*(?:the\s*)?(?:booking|reservation)\b", low):
        return True

    # "İsim-soyisim + telefon paylaşayım mı?" ifadesi booking bağlamıyla geldiyse intent kabul et.
    has_booking_cue = any(k in low for k in ("rezerv", "reservation", "booking", "book"))
    has_identity_share = any(k in low for k in ("isim", "ad soyad", "name", "full name"))
    has_contact_share = any(k in low for k in ("telefon", "phone", "numara", "contact"))
    has_share_verb = any(k in low for k in ("gondereyim", "paylas", "share", "send"))
    if has_booking_cue and has_identity_share and has_contact_share and (has_share_verb or "?" in low):
        return True

    return False


def _is_booking_requirements_question(message: str) -> bool:
    """Kullanici rezervasyon icin hangi bilgilerin gerekli oldugunu soruyor mu?"""
    low = _normalize_match_text(message or "")
    if not low:
        return False

    has_booking_cue = any(k in low for k in ("rezerv", "reservation", "booking", "book"))
    if not has_booking_cue:
        return False

    info_markers = (
        "hangi bilgi",
        "hangi bilgileri",
        "hangi detay",
        "hangi bilgileri ilet",
        "hangi bilgileri gondere",
        "hangi bilgi gerekli",
        "hangi belg",
        "what information",
        "which information",
        "which details",
        "what details",
        "what should i send",
        "what do i need",
        "what do you need",
        "isim-soyisim ve telefonumu gondereyim",
        "isim soyisim ve telefonumu gondereyim",
        "ad soyad ve telefonumu gondereyim",
        "name surname and phone",
        "name and phone",
    )
    if any(k in low for k in info_markers):
        return True

    # "isim-soyisim ve telefonumu göndereyim mi?" gibi niyet/soru kaliplari
    has_identity = any(k in low for k in ("isim", "ad soyad", "name", "surname", "full name"))
    has_contact = any(k in low for k in ("telefon", "phone", "numara", "contact"))
    has_share = any(k in low for k in ("gondereyim", "paylasayim", "send", "share"))
    if has_identity and has_contact and has_share and "?" in low:
        return True

    return False


def _build_booking_requirements_reply(lang: str = "tr") -> str:
    if lang == "en":
        return (
            "To start your reservation, we will collect your details step by step.\n"
            "First step: Please share your full name (first and last name)."
        )
    return (
        "Rezervasyonu başlatmak için bilgileri tek tek alacağım.\n"
        "İlk adım: Lütfen ad soyad bilginizi paylaşın."
    )


def _message_looks_like_booking_intent(message: str) -> bool:
    """Mesaj isme degil rezervasyon niyetine benziyorsa True don."""
    return detect_booking_intent(message or "")


def _next_guest_info_state(data: Dict[str, Any]) -> str:
    if not data.get("guest_first_name"):
        return BookingFlowState.ASK_NAME
    if not data.get("guest_phone"):
        return BookingFlowState.ASK_PHONE
    if not data.get("guest_email"):
        return BookingFlowState.ASK_EMAIL
    return BookingFlowState.ASK_SPECIAL


def _guest_info_step_prompt(state: str, lang: str) -> str:
    if state == BookingFlowState.ASK_NAME:
        if lang == "en":
            return "Please provide the following details one by one. First step: Full name (first and last name)."
        return "Lütfen aşağıdaki bilgileri yazın.\nTek tek ilerleyeceğiz. İlk adım: Ad Soyad"
    if state == BookingFlowState.ASK_PHONE:
        if lang == "en":
            return "Please share your phone number."
        return "Lütfen telefon numaranızı paylaşır mısınız?"
    if state == BookingFlowState.ASK_EMAIL:
        if lang == "en":
            return "Please share your email address. (Optional: type 'skip')"
        return "Lütfen e-posta adresinizi paylaşır mısınız? (Opsiyonel: 'geç' yazabilirsiniz)"
    return ""


# ============================
# Room Selection Parsing
# ============================

ROOM_NAME_ALIASES = {
    "deluxe": "deluxe",
    "superior": "superior",
    "exclusive sokak": "exclusiveLand",
    "exclusive land": "exclusiveLand",
    "exclusive street": "exclusiveLand",
    "sokak manzara": "exclusiveLand",
    "exclusive havuz": "exclusivePool",
    "exclusive pool": "exclusivePool",
    "exclusvie pool": "exclusivePool",
    "exlusive pool": "exclusivePool",
    "havuz manzara": "exclusivePool",
    "penthouse land jakuzili": "penthouseLand",
    "penthouse land jacuzzi": "penthouseLand",
    "penthouse land": "penthouseLand",
    "penthouseland": "penthouseLand",
    "penthouse": "penthouse",
    "jakuzi": "penthouse",
    "premium": "premium",
}


def _parse_room_selection(message: str, rooms: List[Dict]) -> Optional[Dict]:
    """Musteri mesajindan oda secimi parse et.
    Numara (1, 2, 3...) veya oda adi + iade tipi ile secim."""
    low = _normalize_match_text(message or "").strip()

    # 1) Numara ile secim
    m = re.match(r"^(\d+)$", low.strip())
    if m:
        idx = int(m.group(1))
        return find_offer_by_selection(rooms, idx)

    # 2) Oda adi ile secim
    selected_room_key = None
    for alias, key in ROOM_NAME_ALIASES.items():
        if _normalize_match_text(alias) in low:
            selected_room_key = key
            break

    if not selected_room_key:
        return None

    # Iade durumu
    wants_refundable = None
    refundable_keywords = ["ucretsiz iptal", "free cancel", "iade edilebilir", "refundable"]
    non_refundable_keywords = ["iade yapilmaz", "non refundable", "non-refundable", "iade yok"]

    for kw in non_refundable_keywords:
        if kw in low:
            wants_refundable = False
            break
    if wants_refundable is None:
        for kw in refundable_keywords:
            if kw in low:
                wants_refundable = True
                break

    # Eslestir
    candidates = [r for r in rooms if r["room_key"] == selected_room_key]
    if not candidates:
        return None

    if wants_refundable is not None:
        for c in candidates:
            if c["is_refundable"] == wants_refundable:
                return c

    # Iade belirtilmediyse: non-refundable tercih (ucuz olan)
    for c in candidates:
        if not c["is_refundable"]:
            return c
    return candidates[0]


# ============================
# Name Parsing
# ============================

def _parse_guest_name(message: str) -> Optional[Dict[str, str]]:
    """Ad-soyad parse et. Returns {"first_name": ..., "last_name": ...} or None."""
    text = unicodedata.normalize("NFKC", (message or "").strip())

    # "Adim X Y" veya "ismim X Y" veya "My name is X Y" kaliplarini temizle
    patterns = [
        r"(?:ad[ıi]m|ismim|benim ad[ıi]m|my name is|name is|i am|ben)\s+",
    ]
    for pat in patterns:
        text = re.sub(pat, "", text, flags=re.IGNORECASE).strip()

    # Baslangic/bitis noktalamasini temizle
    text = text.strip(".,!?;:")

    # Kelimeler
    words = text.split()
    if not words:
        return None

    def _is_valid_name_piece(value: str) -> bool:
        v = (value or "").strip()
        if len(v) < 2:
            return False
        for ch in v:
            if ch in {" ", "-", "'", "."}:
                continue
            if not ch.isalpha():
                return False
        return True

    # Tek kelime: first_name olarak kabul et, last_name bos
    if len(words) == 1:
        name = words[0].strip()
        if _is_valid_name_piece(name):
            return {"first_name": name.title(), "last_name": ""}
        return None

    # 2+ kelime: ilk kelime first_name, geri kalan last_name
    # Ancak cok uzun (5+ kelime) ise muhtemelen isim degil
    if len(words) > 5:
        return None

    first = words[0].strip()
    last = " ".join(words[1:]).strip()

    # Gecerlilik: en az 2 karakter, harflerden olussin
    if not _is_valid_name_piece(first):
        return None
    if last and not _is_valid_name_piece(last):
        return None

    return {"first_name": first.title(), "last_name": last.title()}


# ============================
# Message Builders
# ============================

def _build_room_selection_message(rooms: List[Dict], lang: str = "tr") -> str:
    """Numarali oda listesi olustur."""
    if lang == "en":
        lines = [
            "Which room would you like to reserve?\n",
            "Available Rooms",
        ]
        for i, room in enumerate(rooms, 1):
            refund_text = "Free Cancellation" if room["is_refundable"] else "Non-refundable"
            lines.append(f"{i}. {room['room_display']} - {refund_text}: {room['price']} {room['currency']}")
        lines.append("\nPlease enter the number of your choice or the room name.")
        return "\n".join(lines)

    lines = [
        "Hangi odayı rezerve etmek istersiniz?\n",
        "Mevcut Odalar",
    ]
    for i, room in enumerate(rooms, 1):
        refund_text = "Ücretsiz İptal" if room["is_refundable"] else "İade yapılmaz"
        lines.append(f"{i}. {room['room_display']} - {refund_text}: {room['price']} {room['currency']}")
    lines.append("\nLütfen seçim numarasını veya oda adını yazın.")
    return "\n".join(lines)


def _build_booking_summary(flow_data: Dict, lang: str = "tr") -> str:
    """Rezervasyon ozeti mesaji."""
    refund_text_tr = "Ücretsiz İptal" if flow_data.get("is_refundable") else "İade yapılmaz"
    refund_text_en = "Free Cancellation" if flow_data.get("is_refundable") else "Non-refundable"
    price = flow_data.get("discounted_price") or flow_data.get("total_price", 0)
    currency = flow_data.get("currency", "EUR")
    guest_name = f"{flow_data.get('guest_first_name', '')} {flow_data.get('guest_last_name', '')}".strip()
    special = flow_data.get("special_requests", "")

    guest_phone = flow_data.get("guest_phone", "")
    guest_email = flow_data.get("guest_email", "")

    # Cocuk bilgisi
    child_ages = flow_data.get("child_ages", [])
    child_text_en = ""
    child_text_tr = ""
    if child_ages:
        ages_en = ", ".join(f"age {a}" for a in child_ages)
        child_text_en = f" + {len(child_ages)} children ({ages_en})"
        ages_tr = " ve ".join(f"{a} yaş" for a in child_ages)
        child_text_tr = f" + {len(child_ages)} çocuk ({ages_tr})"

    if lang == "en":
        lines = [
            "RESERVATION SUMMARY",
            "=" * 25,
            f"Check-in: {flow_data.get('check_in', '?')}",
            f"Check-out: {flow_data.get('check_out', '?')}",
            f"Duration: {flow_data.get('nights', '?')} nights",
            f"Room: {flow_data.get('room_type_display', flow_data.get('room_type', '?'))}",
            f"Price: {price} {currency} ({refund_text_en})",
            f"Guests: {flow_data.get('adult_count', '?')} adults{child_text_en}",
            f"Guest Name: {guest_name}",
        ]
        if guest_phone:
            lines.append(f"Phone: {guest_phone}")
        if guest_email:
            lines.append(f"Email: {guest_email}")
        if special:
            lines.append(f"Special Requests: {special}")
        lines.append("=" * 25)
        lines.append("\nDo you confirm? (Yes / No)")
        return "\n".join(lines)

    lines = [
        "REZERVASYON ÖZETİ",
        "=" * 25,
        f"Giriş: {flow_data.get('check_in', '?')}",
        f"Çıkış: {flow_data.get('check_out', '?')}",
        f"Süre: {flow_data.get('nights', '?')} gece",
        f"Oda: {flow_data.get('room_type_display', flow_data.get('room_type', '?'))}",
        f"Fiyat: {price} {currency} ({refund_text_tr})",
        f"Kişi: {flow_data.get('adult_count', '?')} yetişkin{child_text_tr}",
        f"Misafir: {guest_name}",
    ]
    if guest_phone:
        lines.append(f"Telefon: {guest_phone}")
    if guest_email:
        lines.append(f"E-posta: {guest_email}")
    if special:
        lines.append(f"Özel İstek: {special}")
    lines.append("=" * 25)
    lines.append("\nOnaylıyor musunuz? (Evet / Hayır)")
    return "\n".join(lines)


def _build_booking_pending_reply(
    *,
    lang: str,
    booking_id: Any,
    booking_ctx: str,
    room_display: str,
    check_in: str,
    check_out: str,
    price: Any,
    currency: str,
) -> str:
    """Onay sonrası müşteriye giden rezervasyon alındı mesajı."""
    if lang == "en":
        return (
            f"✅ Your reservation request has been received.\n\n"
            f"📋 Request No: #{booking_id}\n"
            f"🔖 Reference: {booking_ctx}\n"
            f"🛏️ Room: {room_display}\n"
            f"📅 Dates: {check_in} - {check_out}\n"
            f"💶 Price: {_format_money(price)} {currency}\n\n"
            f"Our team will review your request as soon as possible and send you a confirmation message.\n"
            f"After Elektra confirmation, we will share your official reservation number / Voucher No."
        )
    return (
        f"✅ Rezervasyon talebiniz alındı.\n\n"
        f"📋 Talep No: #{booking_id}\n"
        f"🔖 Referans: {booking_ctx}\n"
        f"🛏️ Oda: {room_display}\n"
        f"📅 Tarih: {check_in} - {check_out}\n"
        f"💶 Fiyat: {_format_money(price)} {currency}\n\n"
        f"Ekibimiz talebinizi en kısa sürede inceleyip sizi bilgilendirecektir.\n"
        f"Elektra onayı sonrası resmi rezervasyon numarası / Voucher No bilginizi sizinle mutlaka paylaşacağız."
    )


# ============================
# Cancel / Exit Detection
# ============================

CANCEL_KEYWORDS = [
    "iptal", "vazgec", "vazgeciyorum", "istemiyorum",
    "cancel", "stop", "dur", "birakmak", "birak",
    "cik", "cikis",
]


def _is_cancel(message: str) -> bool:
    low = _turkish_lower(message or "").strip()
    # "ücretsiz iptal" = fiyat tipi seçimi, gerçek iptal DEĞİL
    non_cancel_phrases = [
        "ucretsiz iptal", "free cancel", "free cancellation",
        "iptal edilemez", "iptal edilemeyen",
    ]
    for phrase in non_cancel_phrases:
        if phrase in low:
            return False
    return any(kw in low for kw in CANCEL_KEYWORDS)


# ============================
# Payment Intent Detection
# ============================

def _format_money(value: Any) -> str:
    try:
        v = float(value)
    except Exception:
        return str(value)
    if abs(v - int(v)) < 1e-9:
        return str(int(v))
    return f"{v:.2f}".rstrip("0").rstrip(".")


def _extract_currency_from_text(text: str) -> str:
    low = _turkish_lower(text or "")
    if any(k in low for k in ["eur", "euro", "€"]):
        return "EUR"
    if any(k in low for k in ["usd", "dolar", "$"]):
        return "USD"
    if any(k in low for k in ["try", "tl", "₺", "türk lirası", "turk lirasi"]):
        return "TRY"
    if any(k in low for k in ["gbp", "sterlin", "£", "pound"]):
        return "GBP"
    return ""


def _extract_amount_from_text(text: str) -> float:
    nums = re.findall(r"(\d+(?:[.,]\d+)?)", text or "")
    if not nums:
        return 0.0
    raw = nums[0].replace(",", ".")
    try:
        return float(raw)
    except Exception:
        return 0.0


CONFIRMATION_FORM_KEYWORDS = [
    "konfirmasyon formu",
    "rezervasyon onay formu",
    "onay formu",
    "confirmation form",
    "confirmation url",
]

PAYMENT_LINK_KEYWORDS = [
    "odeme linki", "odeme link", "ödeme linki", "ödeme link",
    "payment link", "pay online", "kredi karti ile", "kredi kartı ile",
    "banka karti", "banka kartı", "kart ile odeme", "kart ile ödeme",
    "1",  # Mesajdaki "1" sadece son booking onay mesajiyla birlikte anlam kazanir
]

BANK_TRANSFER_KEYWORDS = [
    "havale", "eft", "banka transferi", "bank transfer",
    "wire transfer", "havale ile", "eft ile",
    "2",  # Mesajdaki "2" de ayni sekilde
]

PAYMENT_METHOD_INFO_KEYWORDS = [
    "odeme yontem", "ödeme yöntem", "odeme secenek", "ödeme seçenek",
    "nasil odeme", "nasıl ödeme", "hangi odeme", "hangi ödeme",
    "payment method", "payment methods", "how can i pay", "ways to pay",
]

PAYMENT_ACTION_KEYWORDS = [
    "odeme linki", "ödeme linki", "payment link", "pay online",
    "link gonder", "link gönder", "odeme yap", "ödeme yap",
    "kredi karti ile", "kredi kartı ile", "havale", "eft", "bank transfer",
]


def _is_generic_payment_method_question(message: str) -> bool:
    low = _turkish_lower(message or "").strip()
    # Acik odeme-link aksiyonlarini "genel bilgi sorusu" sayma.
    if any(kw in low for kw in ["odeme link", "ödeme link", "payment link", "pay online", "link gonder", "link gönder"]):
        return False
    if any(kw in low for kw in PAYMENT_METHOD_INFO_KEYWORDS):
        return True
    # Soru cümlesi + yöntem/seçenek kelimeleri → bilgi talebi (aksiyon değil)
    if "?" in low and any(k in low for k in ["yontem", "yöntem", "secenek", "seçenek", "method"]):
        return True
    return False


def _build_payment_method_info_reply(lang: str) -> str:
    code = _turkish_lower(lang or "tr")
    if code.startswith("en"):
        return (
            "You can pay via credit card payment link, mail order form, or bank transfer (EFT/wire). "
            "If you want, I can continue with the suitable payment option for your reservation."
        )
    return (
        "Ödeme yöntemlerimiz: kredi kartı ile ödeme linki, mail order formu ve banka havalesi/EFT. "
        "İsterseniz rezervasyonunuz için uygun ödeme adımıyla devam edebilirim."
    )


def _should_allow_automated_payment_link(message: str, booking: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(booking, dict):
        return False
    explicit_ref = bool(_extract_context_id(message) or _extract_booking_alias_index(message))
    if not explicit_ref:
        return False
    if _env_flag("PAYMENT_LINK_AUTOMATION_ENABLED", default=False):
        return True
    env_name = str(os.getenv("KASSANDRA_ENV", "production") or "").strip().lower()
    return env_name in {"test", "local", "dev", "development"}


def _extract_multi_room_request(message: str) -> Dict[str, int]:
    low = _turkish_lower(message or "")
    guest = 0
    room = 0
    family = 0
    m_guest = re.search(r"(\d+)\s*(kisi|kişi|yetiskin|yetişkin|adult|people|guest)", low)
    if m_guest:
        try:
            guest = int(m_guest.group(1))
        except Exception:
            guest = 0
    m_room = re.search(r"(\d+)\s*(adet\s*)?(oda|room)", low)
    if m_room:
        try:
            room = int(m_room.group(1))
        except Exception:
            room = 0
    m_family = re.search(r"(\d+)\s*(adet\s*)?(aile|family|families)", low)
    if m_family:
        try:
            family = int(m_family.group(1))
        except Exception:
            family = 0
    return {"guest_count": guest, "room_count": room, "family_count": family}


def _is_group_quote_request(message: str) -> bool:
    low = _turkish_lower(message or "")
    if "grup fiyat talep formu" in low or "oda secim formu" in low:
        return True
    multi = _extract_multi_room_request(message)
    is_price_like = any(
        k in low for k in ["fiyat", "price", "teklif", "quote", "rezervasyon", "reservation", "oda", "room"]
    )
    group_keywords = [
        "aile", "grup", "birden fazla", "multiple families", "group",
        "misafir toplulugu", "misafir topluluğu",
    ]
    return bool(
        multi.get("room_count", 0) >= 2
        or (multi.get("family_count", 0) >= 2 and is_price_like)
        or any(k in low for k in group_keywords)
    )


def _env_flag(name: str, default: bool = False) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return default


def _allow_legacy_hoteladvisor_payment_fallback() -> bool:
    """Odeme tarafinda eski HOTEL_RES/SP akisini sadece acikca istenirse kullan."""
    mode = str(os.getenv("PAYMENT_SUPPLIER_MODE", "bookingapi") or "").strip().lower()
    # Varsayilan: bookingapi-only.
    if mode in {"bookingapi", "booking_api", "api_only"}:
        return False
    return _env_flag("PAYMENT_SUPPLIER_FALLBACK_HOTELADVISOR", default=False)


def _allow_auto_try_hoteladvisor_fallback(profile: str) -> bool:
    """TRY odemesinde bookingapi basarisiz olursa tenant-bazli fallback izni."""
    forced = _env_flag("PAYMENT_TRY_FORCE_HOTELADVISOR_FALLBACK", default=True)
    if not forced:
        return False
    return str(profile or "").strip().lower() in {"tenant_21966", "legacy_ota"}


def _payment_update_profile(hotel_id: int, booking: Optional[Dict[str, Any]]) -> str:
    """Tenant'e gore update payload profilini sec."""
    raw = str(os.getenv("PAYMENT_UPDATE_PROFILE", "auto") or "").strip().lower()
    if raw and raw != "auto":
        return raw
    if int(hotel_id or 0) == 21966:
        return "tenant_21966"
    if isinstance(booking, dict) and int(booking.get("hotel_id") or 0) == 21966:
        return "tenant_21966"
    return "default"


def _build_group_stage1_template(lang: str = "tr") -> str:
    if lang == "en":
        return (
            "GROUP PRICE REQUEST FORM\n"
            "Group Code: (auto)\n\n"
            "GENERAL\n"
            "- Check-in:\n"
            "- Check-out:\n"
            "- Total family/group count:\n"
            "- Total guests:\n\n"
            "FAMILIES (one row per family)\n"
            "A1 | Adults: | Children: (ages) | Room count:\n"
            "A2 | Adults: | Children: (ages) | Room count:\n"
            "A3 | Adults: | Children: (ages) | Room count:\n\n"
            "PREFERENCE\n"
            "- Room type preference (optional):\n"
            "- Cancellation type (Free Cancellation / Non-refundable):\n"
            "- Budget note (optional):"
        )
    return (
        "GRUP FİYAT TALEP FORMU\n"
        "Grup Kodu: (otomatik)\n\n"
        "GENEL\n"
        "- Giriş:\n"
        "- Çıkış:\n"
        "- Toplam aile/grup sayısı:\n"
        "- Toplam kişi:\n\n"
        "AİLELER (her satır bir aile)\n"
        "A1 | Yetişkin: | Çocuk: (yaşlar) | Oda adedi:\n"
        "A2 | Yetişkin: | Çocuk: (yaşlar) | Oda adedi:\n"
        "A3 | Yetişkin: | Çocuk: (yaşlar) | Oda adedi:\n\n"
        "TERCİH\n"
        "- Oda tipi tercihi (opsiyonel):\n"
        "- İptal tipi (Ücretsiz İptal / İade Yapılmaz):\n"
        "- Bütçe notu (opsiyonel):"
    )


def _generate_booking_context_id(phone: str) -> str:
    clean = re.sub(r"\D", "", phone or "")
    seed = f"{clean}|{datetime.now().isoformat()}"
    return f"CTX-{hashlib.sha1(seed.encode('utf-8')).hexdigest()[:8].upper()}"


def _extract_group_stage1_data(message: str) -> Dict[str, Any]:
    text = message or ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    check_in = ""
    check_out = ""
    preference = ""
    cancellation = ""
    budget = ""
    families: List[Dict[str, Any]] = []

    for ln in lines:
        low = _turkish_lower(ln)
        if low.startswith("- giris:") or low.startswith("- giriş:") or low.startswith("- check-in:"):
            check_in = ln.split(":", 1)[1].strip() if ":" in ln else ""
            continue
        if low.startswith("- cikis:") or low.startswith("- çıkış:") or low.startswith("- check-out:"):
            check_out = ln.split(":", 1)[1].strip() if ":" in ln else ""
            continue
        if low.startswith("- oda tipi tercihi"):
            preference = ln.split(":", 1)[1].strip() if ":" in ln else ""
            continue
        if low.startswith("- iptal tipi") or low.startswith("- cancellation type"):
            cancellation = ln.split(":", 1)[1].strip() if ":" in ln else ""
            continue
        if low.startswith("- bütçe notu") or low.startswith("- budget note"):
            budget = ln.split(":", 1)[1].strip() if ":" in ln else ""
            continue

        m = re.match(
            r"^\s*A(\d+)\s*\|\s*Yetişkin:\s*(\d+)\s*\|\s*Çocuk:\s*([^|]*)\|\s*Oda adedi:\s*(\d+)\s*$",
            ln,
            flags=re.IGNORECASE,
        )
        if not m:
            m = re.match(
                r"^\s*A(\d+)\s*\|\s*Adults:\s*(\d+)\s*\|\s*Children:\s*([^|]*)\|\s*Room count:\s*(\d+)\s*$",
                ln,
                flags=re.IGNORECASE,
            )
        if m:
            idx = int(m.group(1))
            adults = int(m.group(2))
            child_text = (m.group(3) or "").strip()
            rooms = int(m.group(4))
            child_ages = [int(x) for x in re.findall(r"\d+", child_text) if 0 <= int(x) <= 16]
            families.append(
                {
                    "alias": f"A{idx}",
                    "adults": adults,
                    "child_ages": child_ages,
                    "room_count": rooms,
                }
            )

    return {
        "check_in": check_in,
        "check_out": check_out,
        "preference": preference,
        "cancellation": cancellation,
        "budget": budget,
        "families": sorted(families, key=lambda x: x["alias"]),
    }


def _build_group_stage2_template(group_data: Dict[str, Any], lang: str = "tr") -> str:
    families = group_data.get("families", [])
    lines: List[str] = []
    for fam in families:
        lines.append(f"{fam['alias']} -> Seçim:")
    if lang == "en":
        lines = [ln.replace("Seçim", "Selection") for ln in lines]
        return (
            "ROOM SELECTION FORM\n"
            f"Group Code: {group_data.get('group_code','')}\n\n"
            + "\n".join(lines)
            + "\n\nSpecial requests:"
        )
    return (
        "ODA SEÇİM FORMU\n"
        f"Grup Kodu: {group_data.get('group_code','')}\n\n"
        + "\n".join(lines)
        + "\n\nÖzel istek:"
    )


def _extract_group_stage2_selections(message: str) -> Dict[str, str]:
    selections: Dict[str, str] = {}
    for ln in (message or "").splitlines():
        m = re.match(r"^\s*(A\d+)\s*->\s*(?:Seçim|Selection)\s*:\s*(.+?)\s*$", ln, flags=re.IGNORECASE)
        if m:
            selections[m.group(1).upper()] = m.group(2).strip()
    return selections


def _parse_selection_preferences(selection_text: str) -> Dict[str, Any]:
    low = _normalize_match_text(selection_text or "")

    room_aliases = {
        "deluxe": "deluxe",
        "superior": "superior",
        "exclusive land": "exclusiveLand",
        "exclusive street": "exclusiveLand",
        "exclusive pool": "exclusivePool",
        "penthouse land": "penthouseLand",
        "penthouse": "penthouse",
        "premium": "premium",
    }
    room_key = ""
    for k, v in room_aliases.items():
        if k in low:
            room_key = v
            break

    is_refundable: Optional[bool] = None
    if any(k in low for k in ["ucretsiz iptal", "free cancel", "refundable", "free cancellation"]):
        is_refundable = True
    elif any(k in low for k in ["iade yapilmaz", "non refundable", "non-refundable", "iptal edilemez"]):
        is_refundable = False

    return {"room_key": room_key, "is_refundable": is_refundable}


def _format_rate_label(is_refundable: bool, lang: str) -> str:
    if lang == "en":
        return "Free Cancellation" if is_refundable else "Non-refundable"
    return "Ücretsiz İptal" if is_refundable else "İade Yapılmaz"


async def _build_group_family_quote(
    *,
    alias: str,
    selection_text: str,
    fam: Dict[str, Any],
    check_in: str,
    check_out: str,
    hotel_id: str,
    lang: str,
) -> Dict[str, Any]:
    adults = int(fam.get("adults") or 0)
    child_ages = [int(a) for a in (fam.get("child_ages") or []) if 0 <= int(a) <= 16]
    room_count = int(fam.get("room_count") or 1)

    preferences = _parse_selection_preferences(selection_text)
    pref_room_key = preferences.get("room_key") or ""
    pref_refundable = preferences.get("is_refundable", None)

    api_json = await fetch_price(
        hotel_id=str(hotel_id),
        from_date=check_in,
        to_date=check_out,
        adult=max(adults, 1),
        child_ages=child_ages or None,
        language=(lang or "tr"),
    )

    offers: List[Dict[str, Any]] = []
    if isinstance(api_json, list):
        offers = [x for x in api_json if isinstance(x, dict)]
    elif isinstance(api_json, dict):
        for key in ("data", "result", "offers", "prices"):
            if isinstance(api_json.get(key), list):
                offers = [x for x in api_json.get(key) if isinstance(x, dict)]
                break

    rooms = get_available_rooms_from_offers(offers, lang)
    if not rooms:
        return {
            "alias": alias,
            "ok": False,
            "error": "no_rooms",
        }

    candidates = rooms[:]
    if pref_room_key:
        filtered = [r for r in candidates if r.get("room_key") == pref_room_key]
        if filtered:
            candidates = filtered
    if pref_refundable is not None:
        filtered = [r for r in candidates if bool(r.get("is_refundable")) == bool(pref_refundable)]
        if filtered:
            candidates = filtered
    if not candidates:
        return {
            "alias": alias,
            "ok": False,
            "error": "selection_not_available",
        }

    selected = min(candidates, key=lambda r: float(r.get("price") or 0))
    unit_price = float(selected.get("price") or 0)
    subtotal = unit_price * max(room_count, 1)
    return {
        "alias": alias,
        "ok": True,
        "room_display": selected.get("room_display") or selected.get("room_type") or "-",
        "is_refundable": bool(selected.get("is_refundable")),
        "currency": selected.get("currency") or "EUR",
        "unit_price": unit_price,
        "room_count": room_count,
        "subtotal": subtotal,
        "adults": adults,
        "child_ages": child_ages,
    }


def _parse_dt_safe(value: Any) -> Optional[datetime]:
    try:
        if not value:
            return None
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def _is_recent_booking_for_payment(booking: Dict[str, Any], max_hours: int = 24) -> bool:
    ts = _parse_dt_safe(booking.get("updated_at")) or _parse_dt_safe(booking.get("created_at"))
    if not ts:
        return False
    return (datetime.now() - ts).total_seconds() <= max_hours * 3600


def _is_test_phone(phone: str) -> bool:
    clean = re.sub(r"\D", "", phone or "")
    if not clean:
        return False
    configured = (os.getenv("KASSANDRA_TEST_PHONES") or "").strip()
    if configured:
        tests = {re.sub(r"\D", "", p) for p in configured.split(",") if p.strip()}
        if clean in tests:
            return True
    prefix = (os.getenv("KASSANDRA_TEST_PHONE_PREFIX") or "999").strip()
    return bool(prefix and clean.startswith(prefix))


def _extract_context_id(message: str) -> str:
    m = re.search(r"\b(CTX-[A-Z0-9]{6,})\b", (message or "").upper())
    return m.group(1).strip() if m else ""


def _extract_booking_alias_index(message: str) -> int:
    m = re.search(r"(?:#\s*)?A(\d{1,2})\b", (message or "").upper())
    if not m:
        return 0
    try:
        return int(m.group(1))
    except Exception:
        return 0


def _format_booking_selection_list(bookings: List[Dict[str, Any]], lang: str) -> str:
    lines: List[str] = []
    for idx, b in enumerate(bookings, start=1):
        room = b.get("room_type_display") or b.get("room_type") or "-"
        ci = b.get("check_in") or "-"
        co = b.get("check_out") or "-"
        pax = b.get("adult_count") or 0
        ctx = b.get("booking_context_id") or "-"
        lines.append(f"#A{idx} | {ci}-{co} | {pax} yetiskin | {room} | {ctx}")
    if lang == "en":
        return (
            "I found more than one active reservation. Please choose which one to continue:\n"
            + "\n".join(lines)
            + "\n\nExample: 'A1 payment link' or 'CTX-XXXXXXX payment link'."
        )
    return (
        "Birden fazla aktif rezervasyon buldum. Lütfen hangisi için işlem yapmak istediğinizi seçin:\n"
        + "\n".join(lines)
        + "\n\nÖrnek: 'A1 için ödeme linki gönder' veya 'CTX-XXXXXXX için ödeme linki gönder'."
    )


async def _convert_amount_by_exchange_rate(
    *,
    amount: float,
    from_currency: str,
    to_currency: str,
    hotel_id: int,
    rate_date: str,
) -> float:
    from_cur = (from_currency or "EUR").strip().upper()
    to_cur = (to_currency or "EUR").strip().upper()
    if amount <= 0:
        return 0.0
    if from_cur == to_cur:
        return float(amount)
    try:
        payload = {"DATE": rate_date, "HOTELID": int(hotel_id)}
        raw = await hoteladvisor_function("FN_HOTEL_EXCHANGERATES_ALL", payload=payload, timeout_sec=15)

        def _collect_rows(node: Any, out: List[Dict[str, Any]]) -> None:
            if isinstance(node, dict):
                # Kur satiri olabilecek dict
                has_rate_key = any(k in node for k in ("RATE", "rate"))
                has_currency_key = any(k in node for k in ("CURRENCY", "currency", "CURCODE", "curcode", "CURRENCYCODE", "currencycode"))
                if has_rate_key and has_currency_key:
                    out.append(node)
                # Wrapper objelerde alt listeleri de tara
                for v in node.values():
                    if isinstance(v, (dict, list)):
                        _collect_rows(v, out)
            elif isinstance(node, list):
                for item in node:
                    if isinstance(item, (dict, list)):
                        _collect_rows(item, out)

        rows: List[Dict[str, Any]] = []
        _collect_rows(raw, rows)
        rates: Dict[str, float] = {}
        for r in rows:
            if not isinstance(r, dict):
                continue
            c = str(
                r.get("CURRENCY")
                or r.get("currency")
                or r.get("CURCODE")
                or r.get("curcode")
                or r.get("CURRENCYCODE")
                or r.get("currencycode")
                or ""
            ).strip().upper()
            try:
                rv = float(r.get("RATE") if r.get("RATE") is not None else r.get("rate"))
            except Exception:
                continue
            if c and rv > 0:
                rates[c] = rv
        if from_cur not in rates or to_cur not in rates:
            print(
                "[PAYMENT] WARN: exchange rows parsed but target currency missing | "
                f"have={sorted(list(rates.keys()))} need={from_cur}->{to_cur}"
            )
            raise RuntimeError(f"missing exchange rate ({from_cur}->{to_cur})")
        # RATE: ilgili para biriminin TRY karsiligi varsayimi
        amount_try = float(amount) * float(rates[from_cur])
        converted = amount_try / float(rates[to_cur])
        return float(converted)
    except Exception as e:
        raise RuntimeError(f"exchange rate conversion failed ({from_cur}->{to_cur}): {e}")


def _build_payment_link(
    *,
    voucher_no: str,
    last_name: str,
    check_in: str,
    room_type_id: Any,
    currency: str,
    amount: int,
) -> str:
    base = "https://kassandra-butik-otel.rezervasyonal.com/Online"
    cur = str(currency or "").strip().upper()
    amt = int(amount or 0)
    currency_id_map = {"TRY": "142"}
    cur_id = currency_id_map.get(cur, "")

    params: List[tuple[str, str]] = [
        ("Voucherno", str(voucher_no or "")),
        ("LastName", str(last_name or "")),
        ("CheckInDate", str(check_in or "")),
        ("RoomTypeId", str(room_type_id or "")),
        ("submit", "true"),
        ("redirect", "Deposit"),
        # Tenant farklari icin para birimi/tutar alias'lari.
        ("Currency", cur),
        ("currency", cur),
        ("CurrencyCode", cur),
        ("currencyCode", cur),
        ("CurCode", cur),
        ("curcode", cur),
        ("Amount", str(amt)),
        ("amount", str(amt)),
        ("PaymentAmount", str(amt)),
        ("paymentAmount", str(amt)),
        ("DepositAmount", str(amt)),
        ("depositAmount", str(amt)),
        ("DEPOSITPRICE", str(amt)),
    ]
    if cur_id:
        params.extend(
            [
                ("CurrencyId", cur_id),
                ("currencyId", cur_id),
                ("CURRENCYID", cur_id),
                ("DEPOSITCURRENCYID", cur_id),
            ]
        )
    if cur == "TRY":
        params.extend(
            [
                ("DEPOSITCURRENCYCODE", "TRY"),
                ("depositCurrencyCode", "TRY"),
                # Bazi tenant'larda legacy kod "TL" olarak beklenebiliyor.
                ("DOVIZKODU", "TL"),
                ("DOVIZKODUISO", "TRY"),
                ("CurrencyLocal", "TL"),
                ("CurrencySymbol", "₺"),
            ]
        )
    return f"{base}?{urlencode(params)}"


def _currency_display_label(currency_code: str) -> str:
    code = str(currency_code or "").strip().upper()
    if code == "TRY":
        return "TRY (₺)"
    return code


def _extract_rows_from_hoteladvisor(raw: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            if node:
                rows.append(node)
            for v in node.values():
                if isinstance(v, (dict, list)):
                    _walk(v)
        elif isinstance(node, list):
            for item in node:
                if isinstance(item, (dict, list)):
                    _walk(item)

    _walk(raw)
    return rows


def _parse_booking_child_ages(booking: Optional[Dict[str, Any]]) -> List[int]:
    if not isinstance(booking, dict):
        return []
    raw = booking.get("child_ages")
    if isinstance(raw, list):
        values = raw
    elif isinstance(raw, str):
        try:
            values = json.loads(raw)
        except Exception:
            values = []
    else:
        values = []
    ages: List[int] = []
    for v in values:
        try:
            age = int(v)
            if 0 <= age <= 17:
                ages.append(age)
        except Exception:
            continue
    return ages


def _build_update_guest_list_from_booking(booking: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(booking, dict):
        return []
    first = str(booking.get("guest_first_name") or "").strip() or "Guest"
    last = str(booking.get("guest_last_name") or "").strip() or "Guest"
    phone = str(booking.get("guest_phone") or "").strip()
    email = str(booking.get("guest_email") or "").strip()
    adults = max(1, int(booking.get("adult_count") or 1))
    child_ages = _parse_booking_child_ages(booking)

    guest_list: List[Dict[str, Any]] = []
    first_adult: Dict[str, Any] = {
        "title-id": 1,
        "gender": 0,
        "country": "TR",
        "name": first,
        "surname": last,
    }
    if phone:
        first_adult["phone"] = phone
    if email:
        first_adult["email"] = email
    guest_list.append(first_adult)

    for _ in range(max(0, adults - 1)):
        guest_list.append(
            {
                "title-id": 1,
                "gender": 0,
                "country": "TR",
                "name": "",
                "surname": "",
            }
        )

    base_year = 2026
    for idx, age in enumerate(child_ages, start=1):
        year = max(2008, base_year - int(age))
        birth = f"{year}-01-01"
        guest_list.append(
            {
                "title-id": 2,
                "gender": 0,
                "country": "TR",
                "name": f"CHILD{idx}",
                "surname": "",
                "birthday": birth,
                "birth-date": birth,
            }
        )
    return guest_list


def _extract_supplier_pax_from_error(err_text: str) -> Optional[Dict[str, int]]:
    txt = str(err_text or "")
    m = re.search(
        r"as found adult:\s*(\d+)\s*,\s*and elder-child-count:\s*(\d+)\s*younger-child-count:\s*(\d+)\s*baby-count:\s*(\d+)",
        txt,
        re.IGNORECASE,
    )
    if not m:
        return None
    try:
        return {
            "adult": int(m.group(1)),
            "elder": int(m.group(2)),
            "younger": int(m.group(3)),
            "baby": int(m.group(4)),
        }
    except Exception:
        return None


def _build_guest_list_for_supplier_pax(booking: Optional[Dict[str, Any]], pax: Dict[str, int]) -> List[Dict[str, Any]]:
    if not isinstance(booking, dict):
        return []
    first = str(booking.get("guest_first_name") or "").strip() or "Guest"
    last = str(booking.get("guest_last_name") or "").strip() or "Guest"
    phone = str(booking.get("guest_phone") or "").strip()
    email = str(booking.get("guest_email") or "").strip()

    adult_n = max(1, int(pax.get("adult") or 1))
    elder_n = max(0, int(pax.get("elder") or 0))
    younger_n = max(0, int(pax.get("younger") or 0))
    baby_n = max(0, int(pax.get("baby") or 0))

    guest_list: List[Dict[str, Any]] = []
    first_adult: Dict[str, Any] = {
        "title-id": 1,
        "gender": 0,
        "country": "TR",
        "name": first,
        "surname": last,
    }
    if phone:
        first_adult["phone"] = phone
    if email:
        first_adult["email"] = email
    guest_list.append(first_adult)

    for _ in range(max(0, adult_n - 1)):
        guest_list.append(
            {
                "title-id": 1,
                "gender": 0,
                "country": "TR",
                "name": "",
                "surname": "",
            }
        )

    def _add_child(idx: int, age: int) -> None:
        year = 2026 - int(age)
        birth = f"{max(2008, year):04d}-01-01"
        guest_list.append(
            {
                "title-id": 2,
                "gender": 0,
                "country": "TR",
                "name": f"CHILD{idx}",
                "surname": "",
                "birthday": birth,
                "birth-date": birth,
            }
        )

    c_idx = 1
    for _ in range(elder_n):
        _add_child(c_idx, 11)
        c_idx += 1
    for _ in range(younger_n):
        _add_child(c_idx, 5)
        c_idx += 1
    for _ in range(baby_n):
        _add_child(c_idx, 1)
        c_idx += 1
    return guest_list


def _attach_ota_required_alias_fields(
    payload: Dict[str, Any],
    booking: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """SP_EASYPMS_RESUPDATE_OTA icin ROOMID vb alanlarin aliaslarini ekle."""
    out = dict(payload or {})
    if not isinstance(booking, dict):
        return out

    alias_sources = {
        "ROOMID": int(booking.get("room_type_id") or 0),
        "BOARDID": int(booking.get("board_type_id") or 0),
        "RATETYPEID": int(booking.get("rate_type_id") or 0),
        "RATECODEID": int(booking.get("rate_code_id") or 0),
        "PRICEAGENCYID": int(booking.get("price_agency_id") or 0),
    }
    for key, value in alias_sources.items():
        if value <= 0:
            continue
        out[key] = value
        out[f"@{key}"] = value
        out[key.lower()] = value

    try:
        total_price = float(booking.get("discounted_price") or booking.get("total_price") or 0.0)
    except Exception:
        total_price = 0.0
    if total_price > 0:
        out["TOTALPRICE"] = total_price
        out["@TOTALPRICE"] = total_price

    currency_code = str(booking.get("currency") or "EUR").strip().upper()
    if currency_code:
        out["CURRENCYCODE"] = currency_code
        out["@CURRENCYCODE"] = currency_code

    return out


def _payment_payload_log_view(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Loglarda gereksiz buyuk alanlari kisaltarak goster."""
    out = dict(payload or {})
    guest_list = out.get("guest-list")
    if isinstance(guest_list, list):
        out["guest-list-count"] = len(guest_list)
        out.pop("guest-list", None)
    return out


def _extract_required_try_quote_from_error(err_text: str) -> Optional[float]:
    txt = str(err_text or "")
    m = re.search(r"must be\s*([0-9]+(?:\.[0-9]+)?)\s*TRY", txt, re.IGNORECASE)
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None


async def _prepare_try_payment_on_supplier(
    *,
    reservation_id: str,
    hotel_id: int,
    try_amount: int,
    booking: Optional[Dict[str, Any]] = None,
) -> bool:
    if try_amount <= 0:
        return False
    try:
        profile = _payment_update_profile(hotel_id, booking)
        last_supplier_pax: Optional[Dict[str, int]] = None
        # 0) bookingapi updateReservation ile TRY alanlarini farkli payload varyantlariyla dene.
        base_update: Dict[str, Any] = {}
        if isinstance(booking, dict):
            # bookingapi updateReservation bu tenant'ta zorunlu alanlar bekliyor.
            # Bu nedenle yerel booking kaydindaki cekirdek alanlari da gonder.
            base_update = {
                "room-type-id": int(booking.get("room_type_id") or 0),
                "board-type-id": int(booking.get("board_type_id") or 0),
                "rate-type-id": int(booking.get("rate_type_id") or 0),
                "rate-code-id": int(booking.get("rate_code_id") or 0),
                "price-agency-id": int(booking.get("price_agency_id") or 0),
                "currency-code": str(booking.get("currency") or "EUR").strip().upper(),
                "total-price": float(booking.get("discounted_price") or booking.get("total_price") or 0.0),
                "adult-count": int(booking.get("adult_count") or 1),
                "check-in": str(booking.get("check_in") or ""),
                "check-out": str(booking.get("check_out") or ""),
                "room-count": 1,
                "contact-first-name": str(booking.get("guest_first_name") or ""),
                "contact-last-name": str(booking.get("guest_last_name") or ""),
                "contact-phone": str(booking.get("guest_phone") or ""),
                "contact-email": str(booking.get("guest_email") or ""),
                "nationality": "TR",
            }
            # Tenant SP_EASYPMS_RESUPDATE_OTA bazen legacy alan adlari istiyor.
            if profile in {"tenant_21966", "legacy_ota"}:
                if int(booking.get("room_type_id") or 0) > 0:
                    base_update["ROOMID"] = int(booking.get("room_type_id"))
                if int(booking.get("board_type_id") or 0) > 0:
                    base_update["BOARDID"] = int(booking.get("board_type_id"))
                if int(booking.get("rate_type_id") or 0) > 0:
                    base_update["RATETYPEID"] = int(booking.get("rate_type_id"))
                if int(booking.get("rate_code_id") or 0) > 0:
                    base_update["RATECODEID"] = int(booking.get("rate_code_id"))
            guest_list = _build_update_guest_list_from_booking(booking)
            if guest_list:
                base_update["guest-list"] = guest_list
            # Bos/0 degerleri gondermeyelim.
            base_update = {
                k: v for k, v in base_update.items()
                if v not in ("", None, 0, 0.0)
            }
            base_update = _attach_ota_required_alias_fields(base_update, booking)

        bookingapi_payloads: List[Dict[str, Any]] = [
            {
                **base_update,
                "DEPOSITPERCENT": 0,
                "deposit-percent": 0,
                "DEPOSITPRICE": int(try_amount),
                "deposit-amount": int(try_amount),
                "payment-amount": int(try_amount),
                "prepayment-amount": int(try_amount),
                "DEPOSITCURRENCYID": 142,
                "DEPOSITCURRENCYCODE": "TRY",
                "deposit-currency": "TRY",
            },
            {
                **base_update,
                # HAR'daki update/HOTEL_RES'e daha yakin varyant
                "DEPOSITCURRENCYID": "142",
                "DEPOSITPERCENT": "",
                "DEPOSITPRICE": str(int(try_amount)),
                "DEPOSITCURRENCYCODE": "TRY",
            },
            {
                **base_update,
                # Daha minimal varyant
                "DEPOSITPRICE": int(try_amount),
                "DEPOSITCURRENCYID": 142,
                "DEPOSITCURRENCYCODE": "TRY",
            },
        ]
        for idx, update_payload in enumerate(bookingapi_payloads, start=1):
            try:
                up_resp = await update_elektraweb_reservation(
                    hotel_id=int(hotel_id),
                    reservation_id=str(reservation_id),
                    updates=update_payload,
                    timeout_sec=20,
                )
                print(
                    "[PAYMENT] bookingapi updateReservation TRY fields OK | "
                    f"profile={profile} variant={idx} res_id={reservation_id} "
                    f"payload={json.dumps(_payment_payload_log_view(update_payload), ensure_ascii=False)} "
                    f"resp={json.dumps(up_resp, ensure_ascii=False)[:220]}"
                )
                record_metric(
                    event="payment_update_ok",
                    category="bookingapi_try_fields",
                    meta={
                        "hotel_id": int(hotel_id),
                        "reservation_id": str(reservation_id),
                        "profile": profile,
                        "variant": int(idx),
                    },
                )
                return True
            except Exception as bookingapi_exc:
                pax = _extract_supplier_pax_from_error(str(bookingapi_exc))
                if pax:
                    last_supplier_pax = pax
                    retry_payload = dict(update_payload)
                    retry_payload.update(
                        {
                            "adult-count": int(pax["adult"]),
                            "elder-child-count": int(pax["elder"]),
                            "younger-child-count": int(pax["younger"]),
                            "baby-count": int(pax["baby"]),
                            "child-count": int(pax["elder"] + pax["younger"] + pax["baby"]),
                            "children-count": int(pax["elder"] + pax["younger"] + pax["baby"]),
                            "CHD1": int(pax["elder"]),
                            "CHD2": int(pax["younger"]),
                            "BABY": int(pax["baby"]),
                        }
                    )
                    retry_guest_list = _build_guest_list_for_supplier_pax(booking, pax)
                    if retry_guest_list:
                        retry_payload["guest-list"] = retry_guest_list
                    try:
                        up_resp = await update_elektraweb_reservation(
                            hotel_id=int(hotel_id),
                            reservation_id=str(reservation_id),
                            updates=retry_payload,
                            timeout_sec=20,
                        )
                        print(
                            "[PAYMENT] bookingapi updateReservation TRY fields OK after pax remap | "
                            f"profile={profile} variant={idx} pax={pax} res_id={reservation_id} "
                            f"resp={json.dumps(up_resp, ensure_ascii=False)[:220]}"
                        )
                        record_metric(
                            event="payment_pax_remap_ok",
                            category="bookingapi_try_fields",
                            meta={
                                "hotel_id": int(hotel_id),
                                "reservation_id": str(reservation_id),
                                "profile": profile,
                                "variant": int(idx),
                                "pax": pax,
                            },
                        )
                        return True
                    except Exception as retry_exc:
                        required_try_quote = _extract_required_try_quote_from_error(str(retry_exc))
                        if required_try_quote and required_try_quote > 0:
                            quote_payload = dict(retry_payload)
                            quote_payload["currency-code"] = "TRY"
                            quote_payload["CURRENCYCODE"] = "TRY"
                            quote_payload["total-price"] = float(required_try_quote)
                            try:
                                up_resp = await update_elektraweb_reservation(
                                    hotel_id=int(hotel_id),
                                    reservation_id=str(reservation_id),
                                    updates=quote_payload,
                                    timeout_sec=20,
                                )
                                print(
                                    "[PAYMENT] bookingapi updateReservation TRY fields OK after quote remap | "
                                    f"profile={profile} variant={idx} quote={required_try_quote} res_id={reservation_id} "
                                    f"resp={json.dumps(up_resp, ensure_ascii=False)[:220]}"
                                )
                                record_metric(
                                    event="payment_quote_remap_ok",
                                    category="bookingapi_try_fields",
                                    meta={
                                        "hotel_id": int(hotel_id),
                                        "reservation_id": str(reservation_id),
                                        "profile": profile,
                                        "variant": int(idx),
                                        "required_try_quote": float(required_try_quote),
                                    },
                                )
                                return True
                            except Exception as quote_exc:
                                print(
                                    "[PAYMENT] WARN: bookingapi TRY quote-remap retry failed | "
                                    f"profile={profile} variant={idx} quote={required_try_quote} err={quote_exc}"
                                )
                        print(
                            "[PAYMENT] WARN: bookingapi TRY pax-remap retry failed | "
                            f"profile={profile} variant={idx} pax={pax} err={retry_exc}"
                        )
                print(
                    "[PAYMENT] WARN: bookingapi updateReservation TRY fields failed | "
                    f"profile={profile} variant={idx} "
                    f"payload={json.dumps(_payment_payload_log_view(update_payload), ensure_ascii=False)} "
                    f"err={bookingapi_exc}"
                )

        # 0b) Fallback: fiyat/oda reprice tetiklememek icin minimal TRY payload dene.
        minimal_try_payloads: List[Dict[str, Any]] = [
            {
                "DEPOSITPRICE": int(try_amount),
                "DEPOSITCURRENCYID": 142,
                "DEPOSITCURRENCYCODE": "TRY",
                "deposit-currency": "TRY",
                "CurrencyCode": "TRY",
                "currencyCode": "TRY",
            },
            {
                "DEPOSITPRICE": str(int(try_amount)),
                "DEPOSITCURRENCYID": "142",
                "DEPOSITCURRENCYCODE": "TRY",
                "DOVIZKODU": "TL",
            },
            {
                "DEPOSITPERCENT": 0,
                "DEPOSITPRICE": int(try_amount),
                "DEPOSITCURRENCYID": 142,
                "DEPOSITCURRENCYCODE": "TRY",
            },
        ]
        for idx, minimal_payload in enumerate(minimal_try_payloads, start=1):
            if last_supplier_pax:
                minimal_payload.update(
                    {
                        "adult-count": int(last_supplier_pax["adult"]),
                        "elder-child-count": int(last_supplier_pax["elder"]),
                        "younger-child-count": int(last_supplier_pax["younger"]),
                        "baby-count": int(last_supplier_pax["baby"]),
                        "child-count": int(
                            last_supplier_pax["elder"]
                            + last_supplier_pax["younger"]
                            + last_supplier_pax["baby"]
                        ),
                        "children-count": int(
                            last_supplier_pax["elder"]
                            + last_supplier_pax["younger"]
                            + last_supplier_pax["baby"]
                        ),
                    }
                )
            try:
                up_resp = await update_elektraweb_reservation(
                    hotel_id=int(hotel_id),
                    reservation_id=str(reservation_id),
                    updates=minimal_payload,
                    timeout_sec=20,
                )
                print(
                    "[PAYMENT] bookingapi minimal TRY update OK | "
                    f"profile={profile} variant={idx} res_id={reservation_id} "
                    f"payload={json.dumps(_payment_payload_log_view(minimal_payload), ensure_ascii=False)} "
                    f"resp={json.dumps(up_resp, ensure_ascii=False)[:220]}"
                )
                record_metric(
                    event="payment_update_ok",
                    category="bookingapi_try_fields_minimal",
                    meta={
                        "hotel_id": int(hotel_id),
                        "reservation_id": str(reservation_id),
                        "profile": profile,
                        "variant": int(idx),
                    },
                )
                return True
            except Exception as minimal_exc:
                print(
                    "[PAYMENT] WARN: bookingapi minimal TRY update failed | "
                    f"profile={profile} variant={idx} err={minimal_exc}"
                )
        if not (_allow_legacy_hoteladvisor_payment_fallback() or _allow_auto_try_hoteladvisor_fallback(profile)):
            print(
                "[PAYMENT] bookingapi TRY update failed for all variants; "
                "legacy HOTEL_RES fallback is disabled (bookingapi-only mode)."
            )
            return False

        # 0) HAR'daki manuel akış ile birebir:
        #    a) once DEPOSITPERCENT=0
        #    b) sonra DEPOSITPRICE + DEPOSITCURRENCY(TRY)
        percent_row = {
            "ID": str(reservation_id),
            "HOTELID": int(hotel_id),
            "DEPOSITPERCENT": "0",
        }
        amount_row = {
            "ID": str(reservation_id),
            "HOTELID": int(hotel_id),
            "DEPOSITPRICE": str(int(try_amount)),
            "DEPOSITCURRENCYID": "142",   # TRY
            "DEPOSITCURRENCYCODE": "TRY",
        }
        try:
            percent_resp = await hoteladvisor_update(
                "HOTEL_RES",
                payload={"Row": percent_row, "SelectAfterUpdate": ["ID"]},
                timeout_sec=20,
            )
            amount_resp = await hoteladvisor_update(
                "HOTEL_RES",
                payload={"Row": amount_row, "SelectAfterUpdate": ["ID"]},
                timeout_sec=20,
            )
            print(
                "[PAYMENT] HOTEL_RES direct TRY update OK | "
                f"res_id={reservation_id} percent_row={json.dumps(percent_row, ensure_ascii=False)} "
                f"amount_row={json.dumps(amount_row, ensure_ascii=False)} "
                f"percent_resp={json.dumps(percent_resp, ensure_ascii=False)[:180]} "
                f"amount_resp={json.dumps(amount_resp, ensure_ascii=False)[:180]}"
            )
            return True
        except Exception as direct_exc:
            print(f"[PAYMENT] WARN: HOTEL_RES direct TRY update failed: {direct_exc}")

        # 1) Hesap kodu (KISINO/HESAPKODU) bul
        hesap_req = {
            "Select": ["KISINO", "SATIR", "KALANODEME"],
            "Paging": {"Current": 1, "ItemsPerPage": 100},
            "Where": [{"Column": "FOLYONO", "Operator": "=", "Value": int(reservation_id)}],
        }
        hesap_raw = await hoteladvisor_select("QWEB_FOLYO_HESAP", payload=hesap_req, timeout_sec=20)
        hesap_rows = _extract_rows_from_hoteladvisor(hesap_raw)
        hesap_candidates = [r for r in hesap_rows if str(r.get("KISINO") or "").strip()]
        hesap_code = ""
        if hesap_candidates:
            # Pozitif bakiyeli satiri tercih et, yoksa ilk satir.
            def _bal(r: Dict[str, Any]) -> float:
                try:
                    return float(r.get("KALANODEME") or 0)
                except Exception:
                    return 0.0
            hesap_candidates.sort(key=_bal, reverse=True)
            hesap_code = str(hesap_candidates[0].get("KISINO") or "").strip()
        if not hesap_code:
            raise RuntimeError("HESAPKODU bulunamadi (QWEB_FOLYO_HESAP)")

        # 2) Departman kodu (DEPKODU) bul
        dep_req = {
            "Select": ["CODE", "NAME", "ID"],
            "Paging": {"Current": 1, "ItemsPerPage": 200},
        }
        dep_raw = await hoteladvisor_select("QA_HOTEL_DEPARTMENT", payload=dep_req, timeout_sec=20)
        dep_rows = _extract_rows_from_hoteladvisor(dep_raw)
        dep_code = ""
        for r in dep_rows:
            code = str(r.get("CODE") or r.get("DEPKODU") or "").strip()
            if code:
                dep_code = code
                break
        if not dep_code:
            # Bazı tenantlarda kod yerine ID ile de kabul edilebilir.
            for r in dep_rows:
                rid = r.get("ID")
                if rid is not None:
                    dep_code = str(rid)
                    break
        if not dep_code:
            raise RuntimeError("DEPKODU bulunamadi (QA_HOTEL_DEPARTMENT)")

        # 3) SP_WEB_PAYMENT ile TRY tutarini supplier tarafina yaz
        # Taktik: rezervasyon yuzdesini 0 kabul ettir, tutari TRY olarak zorla.
        payment_params: Dict[str, Any] = {
            "KNO": int(reservation_id),
            "TLTUTAR": float(try_amount),
            "DOVIZTUTAR": float(try_amount),
            "DOVIZKODU": "TRY",
            "DEPKODU": dep_code,
            "HESAPKODU": hesap_code,
            "RECTYPE": 1,
            # Tenantlar arasi olasi alan adlari
            "RESPRICEPERCENT": 0,
            "RESPRICE_PERCENT": 0,
            "RESPRICEPERCENT": 0,
            "RESERVATIONPRICEPERCENT": 0,
            "REZERVASYON_FIYAT_YUZDE": 0,
            "HOTELID": int(hotel_id),
            "TENNANTID": int(hotel_id),
        }
        sp_resp = await hoteladvisor_execute("SP_WEB_PAYMENT", payload=payment_params, timeout_sec=30)
        print(
            "[PAYMENT] SP_WEB_PAYMENT prepared TRY amount | "
            f"res_id={reservation_id} try_amount={try_amount} "
            f"dep={dep_code} hesap={hesap_code} resp={json.dumps(sp_resp, ensure_ascii=False)[:300]}"
        )
        return True
    except Exception as e:
        print(f"[PAYMENT] WARN: SP_WEB_PAYMENT TRY prepare failed: {e}")
        return False


async def _prepare_non_try_payment_on_supplier(
    *,
    reservation_id: str,
    hotel_id: int,
    amount: int,
    currency_code: str,
    booking: Optional[Dict[str, Any]] = None,
) -> bool:
    cur = str(currency_code or "").strip().upper()
    if amount <= 0 or cur in {"", "TRY"}:
        return False
    try:
        profile = _payment_update_profile(hotel_id, booking)
        base_update: Dict[str, Any] = {}
        if isinstance(booking, dict):
            base_update = {
                "room-type-id": int(booking.get("room_type_id") or 0),
                "board-type-id": int(booking.get("board_type_id") or 0),
                "rate-type-id": int(booking.get("rate_type_id") or 0),
                "rate-code-id": int(booking.get("rate_code_id") or 0),
                "price-agency-id": int(booking.get("price_agency_id") or 0),
                "currency-code": str(booking.get("currency") or "EUR").strip().upper(),
                "total-price": float(booking.get("discounted_price") or booking.get("total_price") or 0.0),
                "adult-count": int(booking.get("adult_count") or 1),
                "check-in": str(booking.get("check_in") or ""),
                "check-out": str(booking.get("check_out") or ""),
                "room-count": 1,
                "contact-first-name": str(booking.get("guest_first_name") or ""),
                "contact-last-name": str(booking.get("guest_last_name") or ""),
                "contact-phone": str(booking.get("guest_phone") or ""),
                "contact-email": str(booking.get("guest_email") or ""),
                "nationality": "TR",
            }
            if profile in {"tenant_21966", "legacy_ota"}:
                if int(booking.get("room_type_id") or 0) > 0:
                    base_update["ROOMID"] = int(booking.get("room_type_id"))
                if int(booking.get("board_type_id") or 0) > 0:
                    base_update["BOARDID"] = int(booking.get("board_type_id"))
                if int(booking.get("rate_type_id") or 0) > 0:
                    base_update["RATETYPEID"] = int(booking.get("rate_type_id"))
                if int(booking.get("rate_code_id") or 0) > 0:
                    base_update["RATECODEID"] = int(booking.get("rate_code_id"))
            guest_list = _build_update_guest_list_from_booking(booking)
            if guest_list:
                base_update["guest-list"] = guest_list
            base_update = {
                k: v for k, v in base_update.items()
                if v not in ("", None, 0, 0.0)
            }
            base_update = _attach_ota_required_alias_fields(base_update, booking)

        payloads: List[Dict[str, Any]] = [
            {
                **base_update,
                "DEPOSITPERCENT": 0,
                "deposit-percent": 0,
                "DEPOSITPRICE": int(amount),
                "deposit-amount": int(amount),
                "payment-amount": int(amount),
                "prepayment-amount": int(amount),
                "DEPOSITCURRENCYCODE": cur,
                "deposit-currency": cur,
                "CurrencyCode": cur,
                "currencyCode": cur,
                "CurCode": cur,
                "curcode": cur,
            },
            {
                **base_update,
                "DEPOSITPRICE": int(amount),
                "DEPOSITCURRENCYCODE": cur,
                "CurrencyCode": cur,
                "currencyCode": cur,
            },
            {
                "DEPOSITPRICE": int(amount),
                "DEPOSITCURRENCYCODE": cur,
                "CurrencyCode": cur,
                "currencyCode": cur,
            },
        ]
        for idx, update_payload in enumerate(payloads, start=1):
            try:
                up_resp = await update_elektraweb_reservation(
                    hotel_id=int(hotel_id),
                    reservation_id=str(reservation_id).strip(),
                    updates=update_payload,
                    timeout_sec=20,
                )
                print(
                    "[PAYMENT] bookingapi updateReservation FX fields OK | "
                    f"profile={profile} currency={cur} variant={idx} res_id={reservation_id} "
                    f"payload={json.dumps(_payment_payload_log_view(update_payload), ensure_ascii=False)} "
                    f"resp={json.dumps(up_resp, ensure_ascii=False)[:220]}"
                )
                record_metric(
                    event="payment_update_ok",
                    category="bookingapi_fx_fields",
                    meta={
                        "hotel_id": int(hotel_id),
                        "reservation_id": str(reservation_id),
                        "profile": profile,
                        "currency": cur,
                        "variant": int(idx),
                    },
                )
                return True
            except Exception as bookingapi_exc:
                print(
                    "[PAYMENT] WARN: bookingapi updateReservation FX fields failed | "
                    f"profile={profile} currency={cur} variant={idx} "
                    f"payload={json.dumps(_payment_payload_log_view(update_payload), ensure_ascii=False)} "
                    f"err={bookingapi_exc}"
                )
        return False
    except Exception as e:
        print(f"[PAYMENT] WARN: non-TRY payment prepare failed ({cur}): {e}")
        return False


async def _force_deposit_percent_zero_on_supplier(
    *,
    reservation_id: str,
    hotel_id: int,
    booking: Optional[Dict[str, Any]] = None,
) -> bool:
    if not str(reservation_id or "").strip():
        return False
    try:
        profile = _payment_update_profile(hotel_id, booking)
        last_supplier_pax: Optional[Dict[str, int]] = None
        # 0) bookingapi updateReservation ile DEPOSITPERCENT=0 varyantlarini dene.
        base_update: Dict[str, Any] = {}
        if isinstance(booking, dict):
            base_update = {
                "room-type-id": int(booking.get("room_type_id") or 0),
                "board-type-id": int(booking.get("board_type_id") or 0),
                "rate-type-id": int(booking.get("rate_type_id") or 0),
                "rate-code-id": int(booking.get("rate_code_id") or 0),
                "price-agency-id": int(booking.get("price_agency_id") or 0),
                "currency-code": str(booking.get("currency") or "EUR").strip().upper(),
                "total-price": float(booking.get("discounted_price") or booking.get("total_price") or 0.0),
                "adult-count": int(booking.get("adult_count") or 1),
                "check-in": str(booking.get("check_in") or ""),
                "check-out": str(booking.get("check_out") or ""),
                "room-count": 1,
                "contact-first-name": str(booking.get("guest_first_name") or ""),
                "contact-last-name": str(booking.get("guest_last_name") or ""),
                "contact-phone": str(booking.get("guest_phone") or ""),
                "contact-email": str(booking.get("guest_email") or ""),
                "nationality": "TR",
            }
            if profile in {"tenant_21966", "legacy_ota"}:
                if int(booking.get("room_type_id") or 0) > 0:
                    base_update["ROOMID"] = int(booking.get("room_type_id"))
                if int(booking.get("board_type_id") or 0) > 0:
                    base_update["BOARDID"] = int(booking.get("board_type_id"))
                if int(booking.get("rate_type_id") or 0) > 0:
                    base_update["RATETYPEID"] = int(booking.get("rate_type_id"))
                if int(booking.get("rate_code_id") or 0) > 0:
                    base_update["RATECODEID"] = int(booking.get("rate_code_id"))
            guest_list = _build_update_guest_list_from_booking(booking)
            if guest_list:
                base_update["guest-list"] = guest_list
            base_update = {
                k: v for k, v in base_update.items()
                if v not in ("", None, 0, 0.0)
            }
            base_update = _attach_ota_required_alias_fields(base_update, booking)

        bookingapi_payloads: List[Dict[str, Any]] = [
            {**base_update, "DEPOSITPERCENT": 0, "deposit-percent": 0},
            {**base_update, "DEPOSITPERCENT": "0"},
            {**base_update, "DEPOSITPERCENT": ""},
        ]
        for idx, update_payload in enumerate(bookingapi_payloads, start=1):
            try:
                up_resp = await update_elektraweb_reservation(
                    hotel_id=int(hotel_id),
                    reservation_id=str(reservation_id).strip(),
                    updates=update_payload,
                    timeout_sec=20,
                )
                print(
                    "[PAYMENT] bookingapi updateReservation DEPOSITPERCENT=0 OK | "
                    f"profile={profile} variant={idx} res_id={reservation_id} "
                    f"payload={json.dumps(_payment_payload_log_view(update_payload), ensure_ascii=False)} "
                    f"resp={json.dumps(up_resp, ensure_ascii=False)[:220]}"
                )
                record_metric(
                    event="payment_update_ok",
                    category="bookingapi_deposit_percent",
                    meta={
                        "hotel_id": int(hotel_id),
                        "reservation_id": str(reservation_id),
                        "profile": profile,
                        "variant": int(idx),
                    },
                )
                return True
            except Exception as bookingapi_exc:
                pax = _extract_supplier_pax_from_error(str(bookingapi_exc))
                if pax:
                    last_supplier_pax = pax
                    retry_payload = dict(update_payload)
                    retry_payload.update(
                        {
                            "adult-count": int(pax["adult"]),
                            "elder-child-count": int(pax["elder"]),
                            "younger-child-count": int(pax["younger"]),
                            "baby-count": int(pax["baby"]),
                            "child-count": int(pax["elder"] + pax["younger"] + pax["baby"]),
                            "children-count": int(pax["elder"] + pax["younger"] + pax["baby"]),
                            "CHD1": int(pax["elder"]),
                            "CHD2": int(pax["younger"]),
                            "BABY": int(pax["baby"]),
                        }
                    )
                    retry_guest_list = _build_guest_list_for_supplier_pax(booking, pax)
                    if retry_guest_list:
                        retry_payload["guest-list"] = retry_guest_list
                    try:
                        up_resp = await update_elektraweb_reservation(
                            hotel_id=int(hotel_id),
                            reservation_id=str(reservation_id).strip(),
                            updates=retry_payload,
                            timeout_sec=20,
                        )
                        print(
                            "[PAYMENT] bookingapi updateReservation DEPOSITPERCENT=0 OK after pax remap | "
                            f"profile={profile} variant={idx} pax={pax} res_id={reservation_id} "
                            f"resp={json.dumps(up_resp, ensure_ascii=False)[:220]}"
                        )
                        record_metric(
                            event="payment_pax_remap_ok",
                            category="bookingapi_deposit_percent",
                            meta={
                                "hotel_id": int(hotel_id),
                                "reservation_id": str(reservation_id),
                                "profile": profile,
                                "variant": int(idx),
                                "pax": pax,
                            },
                        )
                        return True
                    except Exception as retry_exc:
                        print(
                            "[PAYMENT] WARN: bookingapi DEPOSITPERCENT pax-remap retry failed | "
                            f"profile={profile} variant={idx} pax={pax} err={retry_exc}"
                        )
                print(
                    "[PAYMENT] WARN: bookingapi updateReservation DEPOSITPERCENT=0 failed | "
                    f"profile={profile} variant={idx} "
                    f"payload={json.dumps(_payment_payload_log_view(update_payload), ensure_ascii=False)} "
                    f"err={bookingapi_exc}"
                )

        # 0b) Fallback: zorunlu fiyat/oda alanlari olmadan sadece deposit percent guncelle.
        minimal_percent_payloads: List[Dict[str, Any]] = [
            {"DEPOSITPERCENT": 0, "deposit-percent": 0},
            {"DEPOSITPERCENT": "0"},
            {"DEPOSITPERCENT": "", "deposit-percent": 0},
        ]
        for idx, minimal_payload in enumerate(minimal_percent_payloads, start=1):
            if last_supplier_pax:
                minimal_payload.update(
                    {
                        "adult-count": int(last_supplier_pax["adult"]),
                        "elder-child-count": int(last_supplier_pax["elder"]),
                        "younger-child-count": int(last_supplier_pax["younger"]),
                        "baby-count": int(last_supplier_pax["baby"]),
                    }
                )
            try:
                up_resp = await update_elektraweb_reservation(
                    hotel_id=int(hotel_id),
                    reservation_id=str(reservation_id).strip(),
                    updates=minimal_payload,
                    timeout_sec=20,
                )
                print(
                    "[PAYMENT] bookingapi minimal DEPOSITPERCENT=0 update OK | "
                    f"profile={profile} variant={idx} res_id={reservation_id} "
                    f"payload={json.dumps(_payment_payload_log_view(minimal_payload), ensure_ascii=False)} "
                    f"resp={json.dumps(up_resp, ensure_ascii=False)[:220]}"
                )
                record_metric(
                    event="payment_update_ok",
                    category="bookingapi_deposit_percent_minimal",
                    meta={
                        "hotel_id": int(hotel_id),
                        "reservation_id": str(reservation_id),
                        "profile": profile,
                        "variant": int(idx),
                    },
                )
                return True
            except Exception as minimal_exc:
                print(
                    "[PAYMENT] WARN: bookingapi minimal DEPOSITPERCENT=0 update failed | "
                    f"profile={profile} variant={idx} err={minimal_exc}"
                )
        if not (_allow_legacy_hoteladvisor_payment_fallback() or _allow_auto_try_hoteladvisor_fallback(profile)):
            print(
                "[PAYMENT] bookingapi DEPOSITPERCENT update failed for all variants; "
                "legacy HOTEL_RES fallback is disabled (bookingapi-only mode)."
            )
            return False

        row = {
            "ID": str(reservation_id).strip(),
            "HOTELID": int(hotel_id),
            "DEPOSITPERCENT": "0",
        }
        resp = await hoteladvisor_update(
            "HOTEL_RES",
            payload={"Row": row, "SelectAfterUpdate": ["ID"]},
            timeout_sec=20,
        )
        print(
            "[PAYMENT] HOTEL_RES DEPOSITPERCENT forced to 0 | "
            f"res_id={reservation_id} row={json.dumps(row, ensure_ascii=False)} "
            f"resp={json.dumps(resp, ensure_ascii=False)[:220]}"
        )
        return True
    except Exception as e:
        print(f"[PAYMENT] WARN: DEPOSITPERCENT=0 update failed: {e}")
        return False


async def _handle_payment_link_handoff(
    *,
    phone: str,
    message: str,
    lang: str,
    booking: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    booking_ctx = ""
    booking_id = ""
    if isinstance(booking, dict):
        booking_ctx = str(booking.get("booking_context_id") or "").strip()
        booking_id = str(booking.get("id") or "").strip()
    try:
        activate_human_takeover(phone, reason="payment_link_request")
    except Exception:
        pass
    try:
        await notify_admin_handoff(
            category="canli_destek",
            priority="high",
            customer_phone=phone or "Bilinmiyor",
            customer_message=f"Ödeme linki / ön ödeme talebi: {message}",
            source="booking_flow_handler.payment_link",
            detected_intent="PAYMENT_LINK_REQUEST",
            confidence=0.95,
            conversation_summary=(
                f"payment_link_requested booking_id={booking_id or '-'} booking_ctx={booking_ctx or '-'}"
            ),
            attempted_actions=["payment_link_blocked", "human_takeover_activated"],
            suggested_reply="Ödeme linki paylaşılmadı; müşteri canlı temsilciye aktarıldı.",
            tags=["payment_link", "prepayment", "handoff"],
        )
    except Exception:
        pass
    record_metric("handoff")
    clear_payment_context(phone)
    if lang == "en":
        return {
            "reply": (
                "For payment link and prepayment requests, our live representative will assist you directly. "
                "I am connecting you now."
            ),
            "status": "handoff",
            "log": None,
        }
    return {
        "reply": (
            "Ödeme linki ve ön ödeme taleplerinizi canlı müşteri temsilcimiz yönetmektedir. "
            "Sizi şimdi temsilcimize bağlıyorum."
        ),
        "status": "handoff",
        "log": None,
    }


async def _handle_payment_intent(phone: str, message: str, lang: str) -> Optional[Dict[str, Any]]:
    """Odeme yontemi ve konfirmasyon formu taleplerini yonet."""
    low = _turkish_lower(message or "").strip()
    is_short = len(low) <= 3
    has_explicit_link_word = bool(re.search(r"\blink(?:i)?\b", low))

    # Genel bilgi sorulari booking odeme akisini tetiklememeli.
    if _is_generic_payment_method_question(message):
        return {
            "reply": _build_payment_method_info_reply(lang),
            "status": "payment_method_info",
            "log": None,
        }

    wants_link = False
    wants_transfer = False
    wants_confirmation_form = any(kw in low for kw in CONFIRMATION_FORM_KEYWORDS)

    pending_ctx = get_payment_context(phone) or {}
    pending_method = pending_ctx.get("method", "")
    currency_hint = _extract_currency_from_text(message)
    currency_followup_hint = bool(currency_hint) and any(
        kw in low for kw in ["gonder", "gönder", "odeme", "ödeme", "pay", "link", "para birimi", "lira"]
    )

    include_test = _is_test_phone(phone)
    recent_booking_probe = get_latest_booking_by_phone(phone, include_test=include_test)
    if not recent_booking_probe and not include_test:
        # Bazi kayitlar test bayragi ile gelebiliyor; bulamazsak test kayitlarini da dene.
        recent_booking_probe = get_latest_booking_by_phone(phone, include_test=True)

    if is_short and low in ("1", "bir"):
        # "1" ana menu secimi de olabilecegi icin yalnizca odeme baglami varsa yorumla.
        if pending_ctx or (
            recent_booking_probe
            and recent_booking_probe.get("status") in {"pending_approval", "elektra_created"}
            and _is_recent_booking_for_payment(recent_booking_probe, max_hours=48)
        ):
            wants_link = True
    elif is_short and low in ("2", "iki"):
        if pending_ctx or (
            recent_booking_probe
            and recent_booking_probe.get("status") in {"pending_approval", "elektra_created"}
            and _is_recent_booking_for_payment(recent_booking_probe, max_hours=48)
        ):
            wants_transfer = True
    else:
        if has_explicit_link_word:
            wants_link = True
        for kw in PAYMENT_LINK_KEYWORDS:
            if kw in low and kw not in ("1",):
                wants_link = True
                break
        if not wants_link:
            for kw in BANK_TRANSFER_KEYWORDS:
                if kw in low and kw not in ("2",):
                    wants_transfer = True
                    break
    # Mesaj hem link hem havale anahtar kelimesi icerirse link akisini onceliklendir.
    if wants_link and wants_transfer:
        wants_transfer = False

    # Devam adimi: sadece para birimi/tutar mesaji geldiyse onceki secimi devam ettir
    if not wants_link and not wants_transfer and pending_method:
        if pending_method == "link":
            wants_link = True
        elif pending_method == "transfer":
            wants_transfer = True

    # Kisa "1/2" secimlerinde son rezervasyon probe'u gecersizse, aktif rezervasyon varsa
    # odeme akisina girmeye izin ver.
    if is_short and low in ("1", "bir", "2", "iki") and not wants_link and not wants_transfer:
        recent_candidates = get_active_bookings_by_phone(phone, max_hours=48, include_test=include_test, limit=2)
        if not recent_candidates and not include_test:
            recent_candidates = get_active_bookings_by_phone(phone, max_hours=48, include_test=True, limit=2)
        if recent_candidates:
            wants_link = low in ("1", "bir")
            wants_transfer = low in ("2", "iki")

    if not wants_link and not wants_transfer and not wants_confirmation_form:
        # Kullanici sadece para birimi degistirmek istiyor olabilir (orn: "TRY", "TL olarak gonder")
        # Son rezervasyon Elektra'da olusturulmussa bunu odeme-link follow-up olarak ele al.
        booking_probe = recent_booking_probe
        if booking_probe and booking_probe.get("status") == "elektra_created" and currency_followup_hint:
            wants_link = True
        else:
            return None

    context_id = _extract_context_id(message)
    alias_idx = _extract_booking_alias_index(message)

    booking: Optional[Dict[str, Any]] = None
    pending_booking_id = pending_ctx.get("booking_id")
    if pending_booking_id:
        try:
            booking = get_hotel_booking(int(pending_booking_id))
        except Exception:
            booking = None
    if context_id:
        booking = get_booking_by_context_id(context_id)
    if not booking:
        candidates = get_active_bookings_by_phone(phone, max_hours=48, include_test=include_test, limit=10)
        if not candidates and not include_test:
            candidates = get_active_bookings_by_phone(phone, max_hours=48, include_test=True, limit=10)
        if alias_idx > 0 and alias_idx <= len(candidates):
            booking = candidates[alias_idx - 1]
        elif len(candidates) == 1:
            booking = candidates[0]
        elif len(candidates) > 1:
            # Genel sorularda seçim zorunlu: belirsizliği kaldır.
            if wants_link:
                save_payment_context(phone, {"method": "link"})
            return {"reply": _format_booking_selection_list(candidates, lang), "status": "booking_context_required", "log": None}
        else:
            booking = get_latest_booking_by_phone(phone, include_test=include_test)
            if not booking and not include_test:
                booking = get_latest_booking_by_phone(phone, include_test=True)

    if not booking:
        if wants_link:
            return await _handle_payment_link_handoff(
                phone=phone,
                message=message,
                lang=lang,
                booking=None,
            )
        clear_payment_context(phone)
        if wants_transfer or wants_confirmation_form:
            if lang == "en":
                return {
                    "reply": "I couldn't find an active reservation for payment. Please share your reservation reference (CTX-XXXXXXX) or create a reservation first.",
                    "status": "payment_booking_not_found",
                    "log": None,
                }
            return {
                "reply": "Ödeme için aktif bir rezervasyon bulamadım. Lütfen rezervasyon referansınızı (CTX-XXXXXXX) paylaşın veya önce rezervasyon oluşturun.",
                "status": "payment_booking_not_found",
                "log": None,
            }
        return None

    # Aktif payment context yoksa, booking odeme akisini sadece yakin tarihli ve
    # acik odeme eylem niyeti olan mesajlarda calistir.
    has_active_payment_ctx = bool(pending_ctx)
    has_explicit_action = is_short or any(kw in low for kw in PAYMENT_ACTION_KEYWORDS)
    if not has_active_payment_ctx:
        if not (_is_recent_booking_for_payment(booking, max_hours=24) and has_explicit_action):
            return None

    b_status = str(booking.get("status", "") or "").strip().lower()
    if b_status in {"pending_approval", "approved"}:
        if lang == "en":
            reply = (
                "Your reservation request is currently under review by our team. "
                "Once it is created in ElektraWeb, we will immediately send payment details."
            )
        else:
            reply = (
                "Rezervasyon talebiniz şu anda ekibimiz tarafından inceleniyor. "
                "ElektraWeb üzerinde oluşturulduktan hemen sonra ödeme bilgilerini paylaşacağız."
            )
        return {"reply": reply, "status": "payment_pending_approval", "log": None}

    if b_status != "elektra_created":
        clear_payment_context(phone)
        if lang == "en":
            return {
                "reply": "Payment link cannot be generated for this reservation yet. Please try again shortly.",
                "status": "payment_link_unavailable",
                "log": None,
            }
        return {
            "reply": "Bu rezervasyon için ödeme linki henüz üretilemiyor. Lütfen kısa süre sonra tekrar deneyin.",
            "status": "payment_link_unavailable",
            "log": None,
        }

    pending_booking_id = str(pending_ctx.get("booking_id") or "").strip()
    current_booking_id = str(booking.get("id") or "").strip()
    is_followup_for_same_booking = (
        str(pending_ctx.get("method") or "").strip().lower() == "link"
        and pending_booking_id
        and current_booking_id
        and pending_booking_id == current_booking_id
    )
    if wants_link and not _should_allow_automated_payment_link(message, booking):
        if not is_followup_for_same_booking:
            return await _handle_payment_link_handoff(
                phone=phone,
                message=message,
                lang=lang,
                booking=booking,
            )

    voucher_no = ""
    booking_ctx = str(booking.get("booking_context_id", "") or "").strip()
    last_name = booking.get("guest_last_name", "")
    check_in = booking.get("check_in", "")
    room_type_id = booking.get("room_type_id", "")
    guest_name = f"{booking.get('guest_first_name', '')} {booking.get('guest_last_name', '')}".strip()
    reservation_id = str(booking.get("elektra_reservation_id", "")).strip()
    hotel_id = int(booking.get("hotel_id") or int(os.getenv("ELEKTRA_HOTEL_ID", "21966")))

    confirmation_url = ""
    elektra_response_raw = booking.get("elektra_response")
    if elektra_response_raw:
        try:
            elektra_response = json.loads(elektra_response_raw)
            if isinstance(elektra_response, dict):
                voucher_no = (
                    str(
                        elektra_response.get("voucher-no")
                        or elektra_response.get("voucherno")
                        or ""
                    )
                    .strip()
                )
                reservation_id = (
                    str(
                        elektra_response.get("reservation-id")
                        or elektra_response.get("id")
                        or reservation_id
                    )
                    .strip()
                )
                confirmation_url = (
                    elektra_response.get("confirmation-url")
                    or elektra_response.get("confirmationUrl")
                    or ""
                )
        except Exception:
            confirmation_url = ""

    if wants_confirmation_form and not wants_link and not wants_transfer:
        if confirmation_url:
            if lang == "en":
                reply = f"Your reservation confirmation form:\n{confirmation_url}"
            else:
                reply = f"Rezervasyon onay formunuz:\n{confirmation_url}"
            return {"reply": reply, "status": "confirmation_form_sent", "log": None}
        if lang == "en":
            reply = "Your reservation form link is not available yet. I can share it as soon as it is generated."
        else:
            reply = "Rezervasyon onay formu bağlantısı henüz oluşmadı. Oluşur oluşmaz sizinle paylaşabilirim."
        return {"reply": reply, "status": "confirmation_form_unavailable", "log": None}

    if wants_link:
        if not voucher_no and reservation_id:
            voucher_no = reservation_id
            print(
                "[PAYMENT] voucher-no missing, fallback to reservation-id | "
                f"booking_id={booking.get('id')} reservation_id={reservation_id}"
            )

        if confirmation_url:
            clear_payment_context(phone)
            if lang == "en":
                return {
                    "reply": (
                        f"Dear {guest_name},\n\n"
                        f"Your secure payment/confirmation link is ready:\n"
                        f"{confirmation_url}\n\n"
                        f"Kind regards,\nKassandra Ölüdeniz"
                    ),
                    "status": "payment_link_sent",
                    "log": None,
                }
            return {
                "reply": (
                    f"Sayın {guest_name},\n\n"
                    f"Güvenli ödeme/onay bağlantınız hazır:\n"
                    f"{confirmation_url}\n\n"
                    f"Saygılarımızla,\nKassandra Ölüdeniz"
                ),
                "status": "payment_link_sent",
                "log": None,
            }

        if not voucher_no:
            clear_payment_context(phone)
            print(
                "[PAYMENT] link not generated: missing voucher-no | "
                f"booking_id={booking.get('id')} reservation_id={reservation_id}"
            )
            if lang == "en":
                return {
                    "reply": (
                        "Payment link is not available yet for this reservation. "
                        "Our team will share it shortly."
                    ),
                    "status": "payment_link_unavailable",
                    "log": None,
                }
            return {
                "reply": (
                    "Bu rezervasyon için ödeme bağlantısı henüz oluşmadı. "
                    "Ekibimiz kısa süre içinde sizinle paylaşacaktır."
                ),
                "status": "payment_link_unavailable",
                "log": None,
            }

        requested_currency = _extract_currency_from_text(message) or pending_ctx.get("currency", "")
        explicit_amount_in_msg = _extract_amount_from_text(message)
        requested_amount = explicit_amount_in_msg or float(pending_ctx.get("amount") or 0)

        if not requested_currency:
            save_payment_context(phone, {"method": "link", "booking_id": booking.get("id")})
            if lang == "en":
                reply = "Which currency would you like to pay in? (EUR / USD / TRY / GBP)"
            else:
                reply = "Ödemeyi hangi para birimi ile yapmak istersiniz? (EUR / USD / TRY / GBP)"
            return {"reply": reply, "status": "payment_currency_requested", "log": None}

        # Odeme linki gondermeden hemen once supplier tarafinda yuzdeyi sifirla.
        if reservation_id:
            percent_zero_ok = await _force_deposit_percent_zero_on_supplier(
                reservation_id=reservation_id,
                hotel_id=hotel_id,
                booking=booking,
            )
            if not percent_zero_ok:
                # Akisi durdurma: supplier update yetkisi/path'i olmasa bile linki gonder.
                print(
                    "[PAYMENT] WARN: DEPOSITPERCENT=0 could not be updated; continuing with link generation | "
                    f"booking_id={booking.get('id')} reservation_id={reservation_id}"
                )

        nights = int(booking.get("nights") or 1)
        if nights <= 0:
            nights = 1
        total_price = float(booking.get("discounted_price") or booking.get("total_price") or 0)
        one_night_amount = int(round(total_price / nights)) if total_price > 0 else 0

        if requested_amount <= 0:
            requested_amount = float(one_night_amount)

        booking_currency = str(booking.get("currency") or "EUR").strip().upper() or "EUR"
        rate_date = str(check_in or datetime.now().strftime("%Y-%m-%d"))
        effective_currency = requested_currency
        conversion_note_tr = ""
        conversion_note_en = ""
        if explicit_amount_in_msg > 0:
            # Kullanici "14000 TRY" gibi net tutar verdiyse bu tutar hedef para birimindedir.
            payment_amount = int(round(float(requested_amount)))
        else:
            try:
                converted_amount = await _convert_amount_by_exchange_rate(
                    amount=float(requested_amount),
                    from_currency=booking_currency,
                    to_currency=requested_currency,
                    hotel_id=hotel_id,
                    rate_date=rate_date,
                )
                payment_amount = int(round(converted_amount))
            except Exception as e:
                # Yanlis para birimi etiketiyle tutar gondermeyelim.
                # Kullanici hangi para birimini istediyse o para biriminde devam et.
                print(f"[PAYMENT] WARN: exchange rate conversion failed ({booking_currency}->{requested_currency}): {e}")
                effective_currency = requested_currency
                payment_amount = int(round(float(requested_amount)))

        if str(reservation_id or "").strip() and effective_currency != booking_currency:
            supplier_currency_ok = False
            if effective_currency == "TRY":
                supplier_currency_ok = await _prepare_try_payment_on_supplier(
                    reservation_id=str(reservation_id).strip(),
                    hotel_id=hotel_id,
                    try_amount=payment_amount,
                    booking=booking,
                )
            else:
                supplier_currency_ok = await _prepare_non_try_payment_on_supplier(
                    reservation_id=str(reservation_id).strip(),
                    hotel_id=hotel_id,
                    amount=payment_amount,
                    currency_code=effective_currency,
                    booking=booking,
                )
            if not supplier_currency_ok:
                print(
                    "[PAYMENT] WARN: supplier currency update failed; blocking mismatched currency link | "
                    f"booking_id={booking.get('id')} reservation_id={reservation_id} "
                    f"requested_currency={effective_currency} booking_currency={booking_currency}"
                )
                save_payment_context(phone, {"method": "link", "booking_id": booking.get("id")})
                if lang == "en":
                    return {
                        "reply": (
                            f"I could not prepare a {effective_currency} payment link for this reservation right now.\n"
                            f"Please choose {booking_currency} or TRY, or contact us at +905332503277."
                        ),
                        "status": "payment_currency_unavailable",
                        "log": None,
                    }
                return {
                    "reply": (
                        f"Bu rezervasyon için şu anda {effective_currency} para biriminde ödeme linki hazırlayamadım.\n"
                        f"Lütfen {booking_currency} veya TRY seçin, ya da +905332503277 numarasından bizimle iletişime geçin."
                    ),
                    "status": "payment_currency_unavailable",
                    "log": None,
                }

        payment_link = _build_payment_link(
            voucher_no=voucher_no,
            last_name=last_name,
            check_in=check_in,
            room_type_id=room_type_id,
            currency=effective_currency,
            amount=payment_amount,
        )
        print(
            "[PAYMENT] link generated | "
            f"booking_id={booking.get('id')} voucher={voucher_no} "
            f"checkin={check_in} room_type_id={room_type_id} "
            f"currency={effective_currency} amount={payment_amount} "
            "url_mode=currency_params"
        )
        clear_payment_context(phone)

        currency_label = _currency_display_label(effective_currency)
        if lang == "en":
            reply = (
                f"Dear {guest_name},\n\n"
                f"Your secure payment link is ready.\n"
                f"Reference: {booking_ctx}\n"
                f"{conversion_note_en}"
                f"Deposit amount: {payment_amount} {currency_label}\n\n"
                f"{payment_link}\n\n"
                f"You can complete your payment securely via this link.\n"
                f"If you need support, please contact us at +905332503277.\n\n"
                f"Kind regards,\nKassandra Ölüdeniz"
            )
        else:
            reply = (
                f"Sayın {guest_name},\n\n"
                f"Güvenli ödeme bağlantınız hazır.\n"
                f"Referans: {booking_ctx}\n"
                f"{conversion_note_tr}"
                f"Ön ödeme tutarı: {payment_amount} {currency_label}\n\n"
                f"{payment_link}\n\n"
                f"Ödemenizi bu bağlantı üzerinden güvenli şekilde tamamlayabilirsiniz.\n"
                f"Destek için bize +905332503277 numarasından ulaşabilirsiniz.\n\n"
                f"Saygılarımızla,\nKassandra Ölüdeniz"
            )
        if confirmation_url:
            if lang == "en":
                reply += f"\n\nYour reservation confirmation form:\n{confirmation_url}"
            else:
                reply += f"\n\nRezervasyon onay formunuz:\n{confirmation_url}"
        return {"reply": reply, "status": "payment_link_sent", "log": None}

    if wants_transfer:
        clear_payment_context(phone)
        if lang == "en":
            reply = (
                f"Dear {guest_name},\n\n"
                f"Reference: {booking_ctx}\n"
                f"For bank transfer payments, please contact us at +905332503277.\n"
                f"Please include your reservation number ({voucher_no}) in the transfer description.\n\n"
                f"Kind regards,\nKassandra Ölüdeniz"
            )
        else:
            reply = (
                f"Sayın {guest_name},\n\n"
                f"Referans: {booking_ctx}\n"
                f"Havale/EFT ile ödeme için lütfen +905332503277 numarasından bizimle iletişime geçin.\n"
                f"Transfer açıklamasına rezervasyon numaranızı ({voucher_no}) eklemeyi unutmayın.\n\n"
                f"Saygılarımızla,\nKassandra Ölüdeniz"
            )
        return {"reply": reply, "status": "payment_transfer_sent", "log": None}

    return None


# ============================
# Main Entry Point
# ============================

def _has_guest_info(message: str) -> bool:
    """Mesajda isim/soyisim bilgisi var mi? Etiketli veya etiketsiz."""
    low = _turkish_lower(message or "")
    # 1) Etiket var mi?
    name_indicators = [
        "isim", "\u0131sim", "ismim", "\u0131smim",
        "adim", "ad\u0131m", "ad soyad", "adsoyad",
        "soyisim", "soy\u0131sim", "soyad", "name", "my name",
        "isim:", "\u0131sim:", "soyisim:", "soy\u0131sim:", "ad:", "soyad:",
    ]
    if any(kw in low for kw in name_indicators):
        return True
    # 2) Etiketsiz: Satirlardan birinde sadece 2-3 kelimelik isim var mi?
    #    (telefon/email/tarih/sayi icermeyen satirlar)
    for line in message.strip().split("\n"):
        line = line.strip()
        if not line or len(line) < 3:
            continue
        # Sayi, @, +, tarih iceren satirlari atla
        if re.search(r'[\d@+]', line):
            continue
        # Oda adi iceren satirlari atla
        room_names = ["deluxe", "superior", "exclusive", "penthouse land", "penthouse", "premium"]
        if any(rn in line.lower() for rn in room_names):
            continue
        # 2-4 kelime, sadece harflerden olusan → isim olabilir
        words = line.split()
        if 2 <= len(words) <= 4 and all(re.match(r'^[a-zA-ZçğıöşüÇĞİÖŞÜ\-]+$', w) for w in words):
            return True
    return False


def _has_room_selection(message: str) -> bool:
    """Mesajda oda adi (penthouse, superior vb.) var mi?"""
    low = _turkish_lower(message or "")
    return any(rn in low for rn in ["deluxe", "superior", "exclusive", "penthouse land", "penthouse", "premium"])


def _looks_like_room_stock_question(message: str) -> bool:
    """Stok/adet sorgusunu booking flow yerine fiyat flow'a birak."""
    low = _turkish_lower(message or "")
    room_markers = ["deluxe", "superior", "exclusive", "penthouse", "premium"]
    stock_markers = ["kac adet", "kaç adet", "kac oda", "kaç oda", "musait", "müsait", "available", "left", "remaining"]
    return any(r in low for r in room_markers) and any(s in low for s in stock_markers)


def _detect_full_booking_message(message: str) -> bool:
    """Musteri tek mesajda tum rez bilgilerini gonderdi mi?
    Yeterli kosul: (tarih + kisi) + (isim VEYA oda adi)
    Orn: 'Giris 1 Eylul Cikis 5 Eylul 2 yetiskin Penthouse Halim Hal'
    """
    low = _turkish_lower(message or "")
    has_dates = any(kw in low for kw in [
        "giris", "giriş", "cikis", "çıkış", "check-in", "check in",
        "check-out", "check out", "eylul", "eylül", "agustos", "ağustos",
        "haziran", "temmuz", "mayis", "mayıs", "nisan", "ekim", "kasim",
    ])
    has_name = _has_guest_info(message)
    has_person = any(kw in low for kw in [
        "yetiskin", "yetişkin", "kisi", "kişi", "adult", "people",
    ])
    has_room = _has_room_selection(message)
    # Tam bilgi: tarih + kisi + (isim veya oda adi)
    return has_dates and has_person and (has_name or has_room)


async def handle_booking_flow(
    phone: str,
    message: str,
    history: Optional[List[Dict[str, Any]]] = None,
    lang: str = "tr",
) -> Optional[Dict[str, Any]]:
    """
    Otel booking konusma handler'i.
    Returns None eger mesaj booking ile ilgili degilse.
    Returns dict: {"reply": str, "status": str, "log": str}
    """
    if not phone or not message:
        return None

    low = _turkish_lower(message)

    # Oda adedi/musaitlik sorgulari booking'e degil, price flow'a gitmeli.
    if _looks_like_room_stock_question(message):
        return None

    # 1) Aktif booking flow var mi?
    flow = get_booking_flow(phone)
    if flow and flow.get("state") and flow["state"] != BookingFlowState.IDLE:
        # Iptal kontrolu
        if _is_cancel(message):
            clear_booking_flow(phone)
            if lang == "en":
                return {"reply": "Reservation request cancelled. How can I help you?", "status": "booking_cancelled", "log": None}
            return {"reply": "Rezervasyon talebi iptal edildi. Size nasıl yardımcı olabilirim?", "status": "booking_cancelled", "log": None}

        # Aktif flow'u isle
        return await _process_active_flow(phone, message, flow, lang)

    # 1.5) Odeme intent'i var mi? (Onaylanan booking sonrasi odeme yontemi secimi)
    payment_result = await _handle_payment_intent(phone, message, lang)
    if payment_result:
        return payment_result

    # 2) Yeni booking intent var mi?
    has_intent = detect_booking_intent(message)
    multi = _extract_multi_room_request(message)

    # 3) Cache'de offer var mi?
    cached = get_price_offers(phone)
    has_cache = bool(cached and cached.get("offers"))

    # Rezervasyon detay listesi soruluyorsa:
    # - Uygun fiyat/oda cache'i varsa booking flow'u gercekten baslat.
    # - Yoksa bilgi mesaji ver (fiyat adimina donulecek).
    if has_intent and _is_booking_requirements_question(message):
        if has_cache:
            started = await _start_booking_flow(phone, message, cached, lang)
            if started is not None:
                started["status"] = "booking_requirements_info"
                return started
        return {
            "reply": _build_booking_requirements_reply(lang),
            "status": "booking_requirements_info",
            "log": None,
        }

    # 3.5) Çoklu oda/grup taleplerinde önce slot-filling ile temel bilgileri topla.
    if _is_group_quote_request(message) and (
        has_intent
        or multi.get("room_count", 0) >= 2
        or multi.get("family_count", 0) >= 2
    ):
        group_code = f"GRP-{datetime.now().strftime('%Y%m%d%H%M')}"
        save_booking_flow(
            phone,
            BookingFlowState.GROUP_COLLECT_TEMPLATE,
            {"group_code": group_code, "lang": lang},
        )
        if lang == "en":
            return {
                "reply": (
                    f"Absolutely, I can help with {multi.get('room_count') or multi.get('family_count') or 'multiple'} rooms/families for {multi.get('guest_count') or 'your group'} guests.\n\n"
                    + _build_group_stage1_template("en")
                ),
                "status": "booking_group_slot_fill",
                "log": None,
            }
        return {
            "reply": (
                f"Elbette, {multi.get('room_count') or multi.get('family_count') or 'birden fazla'} oda/aile ve {multi.get('guest_count') or 'grubunuz'} kişi için yardımcı olurum.\n\n"
                + _build_group_stage1_template("tr")
            ),
            "status": "booking_group_slot_fill",
            "log": None,
        }

    # 4) Intent yoksa ama musteri tek mesajda TUM bilgileri gonderdiyse
    #    ve offer cache varsa → booking flow baslat (akilli algilama)
    if not has_intent and has_cache:
        if _detect_full_booking_message(message):
            has_intent = True
            print(f"[BOOKING] Akilli algilama: Musteri tek mesajda tum bilgileri verdi → booking flow")

    if not has_intent:
        return None

    # 5) Cache yoksa → once fiyat sorgula mesaji
    if not has_cache:
        if lang == "en":
            return {
                "reply": "Please first ask for prices so I can show you available rooms. For example: 'Price for June 5-10, 2 people'",
                "status": "booking_no_offers",
                "log": None,
            }
        return {
            "reply": "Lütfen önce fiyat sorgulayınız, böylece mevcut odaları görebilirsiniz. Örnek: '5-10 Haziran 2 kişi fiyat'",
            "status": "booking_no_offers",
            "log": None,
        }

    # 6) Booking flow baslat
    return await _start_booking_flow(phone, message, cached, lang)


def _extract_name_from_structured_message(message: str) -> Optional[Dict[str, str]]:
    """Yapisal mesajdan (Isim: X, Soyisim: Y) isim cikar."""
    low = _turkish_lower(message or "")
    first_name = None
    last_name = None

    # "İsim: Ömer Alperen" veya "İsim Ömer Alperen"
    m = re.search(r"(?:isim|ad|first\s*name)\s*[:=]?\s*([a-zA-ZçğıöşüÇĞİÖŞÜ\s\-]+?)(?:\n|soyisim|soyad|last|tel|telefon|kisi|$)", message, re.IGNORECASE)
    if m:
        first_name = m.group(1).strip().title()

    # "Soyisim: Gönen" veya "Soyisim Gönen"
    m = re.search(r"(?:soyisim|soyad|last\s*name)\s*[:=]?\s*([a-zA-ZçğıöşüÇĞİÖŞÜ\s\-]+?)(?:\n|tel|telefon|kisi|$)", message, re.IGNORECASE)
    if m:
        last_name = m.group(1).strip().title()

    if first_name:
        return {"first_name": first_name, "last_name": last_name or ""}
    return None


async def _start_booking_flow(
    phone: str, message: str,
    cached: Dict[str, Any], lang: str,
) -> Dict[str, Any]:
    """Yeni booking flow baslat — oda secimi goster."""
    offers = cached.get("offers", [])
    query = cached.get("query_params", {})

    rooms = get_available_rooms_from_offers(offers, lang)
    if not rooms:
        if lang == "en":
            return {"reply": "Sorry, no rooms available for your dates. Please try different dates.", "status": "booking_no_rooms", "log": None}
        return {"reply": "Maalesef seçtiğiniz tarihler için müsait oda bulunamadı. Farklı tarihler deneyebilirsiniz.", "status": "booking_no_rooms", "log": None}

    # Mesajdan direkt oda secimi deneyebilir mi?
    selected = _parse_room_selection(message, rooms)
    if selected:
        if query.get("quiet_mode") and selected.get("room_key") in _quiet_handoff_room_keys():
            return await _handle_quiet_room_handoff(phone, lang)
        # --- Fiyat tipi secimi gerekiyor mu? (refundable vs non-refundable) ---
        low = _turkish_lower(message or "")
        explicit_refundable = any(kw in low for kw in ["ucretsiz iptal", "free cancel", "refundable"])
        explicit_nonrefundable = any(kw in low for kw in ["iade yapilmaz", "non refundable", "non-refundable", "iptal edilemez"])
        explicit_choice = explicit_refundable or explicit_nonrefundable
        alt = _find_price_type_alternatives(selected, rooms)

        if alt and not explicit_choice:
            # Iki fiyat secenegi var, musteri acikca belirtmedi → ASK_PRICE_TYPE
            pt_data = {
                "room_key": selected["room_key"],
                "room_display": selected["room_display"],
                "from_date": query.get("from_date", ""),
                "to_date": query.get("to_date", ""),
                "adult_count": query.get("adult_count", 2),
                "child_ages": query.get("child_ages", []),
                "hotel_id": query.get("hotel_id", "21966"),
                "lang": lang,
            }
            if selected["is_refundable"]:
                ref_opt, nonref_opt = selected, alt
            else:
                ref_opt, nonref_opt = alt, selected

            pt_data["refundable_price"] = ref_opt["price"]
            pt_data["nonrefundable_price"] = nonref_opt["price"]
            pt_data["refundable_offer_json"] = {k: v for k, v in ref_opt.items() if k != "offer"}
            pt_data["nonrefundable_offer_json"] = {k: v for k, v in nonref_opt.items() if k != "offer"}
            pt_data["refundable_offer_raw"] = ref_opt.get("offer", {})
            pt_data["nonrefundable_offer_raw"] = nonref_opt.get("offer", {})
            pt_data["currency"] = selected.get("currency", "EUR")

            save_booking_flow(phone, BookingFlowState.ASK_PRICE_TYPE, pt_data)

            if lang == "en":
                reply = (
                    f"Great choice! {selected['room_display']}\n\n"
                    f"There are two price options available:\n"
                    f"1) Free Cancellation: {ref_opt['price']} {ref_opt['currency']}\n"
                    f"2) Non-refundable: {nonref_opt['price']} {nonref_opt['currency']}\n\n"
                    f"Which one do you prefer? (1 or 2)"
                )
            else:
                reply = (
                    f"Harika seçim! {selected['room_display']}\n\n"
                    f"İki fiyat seçeneği mevcuttur:\n"
                    f"1) Ücretsiz İptal: {ref_opt['price']} {ref_opt['currency']}\n"
                    f"2) İptal Edilemez: {nonref_opt['price']} {nonref_opt['currency']}\n\n"
                    f"Hangisini tercih edersiniz? (1 veya 2)"
                )
            return {"reply": reply, "status": "booking_flow", "log": None}

        # --- Fiyat tipi acikca belirtildi veya tek secenek var ---
        flow_data = _build_flow_data_from_selection(selected, query, phone)

        # Misafir bilgilerini zorunlu olarak adim adim topla: Isim -> Telefon -> E-posta
        # Bu nedenle ilk secim mesajindan telefon/e-posta otomatik doldurulmaz.

        next_state = _next_guest_info_state(flow_data)
        save_booking_flow(phone, next_state, flow_data)

        if lang == "en":
            refund = "Free Cancellation" if selected["is_refundable"] else "Non-refundable"
            reply = (
                f"Great choice! {selected['room_display']} - {refund}: {selected['price']} {selected['currency']}\n\n"
                f"{_guest_info_step_prompt(next_state, lang)}"
            )
        else:
            refund = "Ücretsiz İptal" if selected["is_refundable"] else "İade yapılmaz"
            reply = (
                f"Harika seçim! {selected['room_display']} - {refund}: {selected['price']} {selected['currency']}\n\n"
                f"{_guest_info_step_prompt(next_state, lang)}"
            )

        return {"reply": reply, "status": "booking_flow", "log": None}

    # Oda secimi yapilmadi → Oda listesini goster
    flow_data = {
        "booking_context_id": _generate_booking_context_id(phone),
        "from_date": query.get("from_date", ""),
        "to_date": query.get("to_date", ""),
        "adult_count": query.get("adult_count", 2),
        "child_ages": query.get("child_ages", []),
        "currency": query.get("currency", "EUR"),
        "hotel_id": query.get("hotel_id", "21966"),
        "lang": lang,
        "rooms_json": [
            {k: v for k, v in r.items() if k != "offer"}
            for r in rooms
        ],
    }

    save_booking_flow(phone, BookingFlowState.SELECT_ROOM, flow_data)

    reply = _build_room_selection_message(rooms, lang)
    return {"reply": reply, "status": "booking_flow", "log": None}


def _build_flow_data_from_selection(selected: Dict, query: Dict, phone: str = "") -> Dict[str, Any]:
    """Secilen oda + query parametrelerinden flow data olustur."""
    offer = selected.get("offer", {})
    from_date = query.get("from_date", "")
    to_date = query.get("to_date", "")

    # Gece sayisi hesapla
    nights = 0
    try:
        d1 = datetime.strptime(from_date, "%Y-%m-%d")
        d2 = datetime.strptime(to_date, "%Y-%m-%d")
        nights = (d2 - d1).days
    except Exception:
        pass

    return {
        "booking_context_id": _generate_booking_context_id(phone),
        "from_date": from_date,
        "to_date": to_date,
        "check_in": from_date,
        "check_out": to_date,
        "nights": nights,
        "adult_count": query.get("adult_count", 2),
        "child_ages": query.get("child_ages", []),
        "hotel_id": query.get("hotel_id", "21966"),
        "lang": query.get("lang", "tr"),
        "currency": selected.get("currency", "EUR"),
        # Oda bilgileri
        "room_type": selected.get("room_type", ""),
        "room_type_display": selected.get("room_display", ""),
        "room_key": selected.get("room_key", ""),
        "is_refundable": selected.get("is_refundable", False),
        # Musteriye gosterilen fiyat ile rezervasyona giden fiyat birebir ayni kalmali.
        "total_price": selected.get("price", offer.get("price", 0)),
        "discounted_price": selected.get("price", offer.get("discounted-price") or offer.get("price", 0)),
        # ElektraWeb ID'leri
        "room_type_id": offer.get("room-type-id", 0),
        "board_type_id": offer.get("board-type-id", 0),
        "rate_type_id": offer.get("rate-type-id", 0),
        "rate_code_id": offer.get("rate-code-id", 0),
        "price_agency_id": offer.get("price-agency-id", 0),
        "currency_id": offer.get("currency-id", 0),
    }


async def _handle_quiet_room_handoff(phone: str, lang: str) -> Dict[str, Any]:
    try:
        activate_human_takeover(phone, reason="quiet_room_live_required")
    except Exception:
        pass

    try:
        await notify_admin_handoff(
            category="quiet_room_live_required",
            priority="medium",
            customer_phone=phone or "Bilinmiyor",
            customer_message="Sessiz oda talebinde bu oda tipi canlı temsilci üzerinden yönetilir.",
            source="booking_flow_handler.quiet_room",
            detected_intent="HOTEL_BOOKING_CREATE",
            confidence=0.9,
            conversation_summary="quiet room policy requires live representative",
            attempted_actions=["quiet_room_policy_check"],
            suggested_reply=(
                "Bu sessiz oda tipi için rezervasyonlar canlı müşteri temsilcisi üzerinden yapılmaktadır."
            ),
            tags=["hotel_booking", "quiet_room_handoff"],
        )
    except Exception:
        pass

    clear_booking_flow(phone)
    if lang == "en":
        return {
            "reply": "This quiet room type is handled by our live representative for booking. I am connecting you now.",
            "status": "handoff",
            "log": None,
        }
    return {
        "reply": "Bu sessiz oda tipi için rezervasyonlar canlı müşteri temsilcisi üzerinden yapılmaktadır. Sizi şimdi temsilcimize bağlıyorum.",
        "status": "handoff",
        "log": None,
    }


def _quiet_handoff_room_keys() -> set[str]:
    policy = get_quiet_room_policy()
    return set(policy.get("quiet_handoff_room_keys", []))


# ============================
# Active Flow Processing
# ============================

async def _process_active_flow(
    phone: str, message: str,
    flow: Dict[str, Any], lang: str,
) -> Optional[Dict[str, Any]]:
    """Aktif flow'daki state'e gore islem yap."""
    state = flow.get("state", "")
    data = flow.get("data", {})
    lang = data.get("lang", lang)

    if state == BookingFlowState.SELECT_ROOM:
        return await _handle_select_room(phone, message, data, lang)

    elif state == BookingFlowState.ASK_PRICE_TYPE:
        return await _handle_ask_price_type(phone, message, data, lang)

    elif state == BookingFlowState.ASK_NAME:
        return await _handle_ask_name(phone, message, data, lang)

    elif state == BookingFlowState.ASK_PHONE:
        return await _handle_ask_phone(phone, message, data, lang)

    elif state == BookingFlowState.ASK_EMAIL:
        return await _handle_ask_email(phone, message, data, lang)

    elif state == BookingFlowState.ASK_SPECIAL:
        return await _handle_ask_special(phone, message, data, lang)

    elif state == BookingFlowState.CONFIRM:
        return await _handle_confirm(phone, message, data, lang)
    elif state == BookingFlowState.GROUP_COLLECT_TEMPLATE:
        return await _handle_group_collect_template(phone, message, data, lang)
    elif state == BookingFlowState.GROUP_SELECT_TEMPLATE:
        return await _handle_group_select_template(phone, message, data, lang)

    # Bilinmeyen state — temizle
    clear_booking_flow(phone)
    return None


async def _handle_group_collect_template(phone: str, message: str, data: Dict, lang: str) -> Dict[str, Any]:
    parsed = _extract_group_stage1_data(message)
    families = parsed.get("families", [])
    if not parsed.get("check_in") or not parsed.get("check_out") or not families:
        if lang == "en":
            return {
                "reply": "I need check-in/check-out and at least one family row (A1|...). Please fill the template completely.",
                "status": "booking_group_slot_fill",
                "log": None,
            }
        return {
            "reply": "Giriş-çıkış ve en az bir aile satırı (A1|...) gerekli. Lütfen şablonu tam doldurun.",
            "status": "booking_group_slot_fill",
            "log": None,
        }

    group_code = data.get("group_code") or f"GRP-{datetime.now().strftime('%Y%m%d%H%M')}"
    group_data = {
        **parsed,
        "group_code": group_code,
        "lang": lang,
    }
    save_booking_flow(phone, BookingFlowState.GROUP_SELECT_TEMPLATE, group_data)

    intro = (
        f"Grup talebinizi aldım ({group_code}). Şimdi her aile için oda seçimini belirtin:\n\n"
        if lang != "en"
        else f"I received your group request ({group_code}). Now please provide room selections per family:\n\n"
    )
    return {"reply": intro + _build_group_stage2_template(group_data, lang), "status": "booking_group_select_template", "log": None}


async def _handle_group_select_template(phone: str, message: str, data: Dict, lang: str) -> Dict[str, Any]:
    selections = _extract_group_stage2_selections(message)
    families = data.get("families", [])
    expected_aliases = {str(f.get("alias", "")).upper() for f in families}
    if not expected_aliases:
        clear_booking_flow(phone)
        if lang == "en":
            return {"reply": "Group flow expired. Please start again.", "status": "booking_group_expired", "log": None}
        return {"reply": "Grup akışı süresi doldu. Lütfen tekrar başlatın.", "status": "booking_group_expired", "log": None}

    missing = [a for a in sorted(expected_aliases) if a not in selections]
    if missing:
        miss_txt = ", ".join(missing)
        if lang == "en":
            return {
                "reply": f"Missing selections for: {miss_txt}. Please complete all families with 'A# -> Selection: ...'",
                "status": "booking_group_select_template",
                "log": None,
            }
        return {
            "reply": f"Şu aileler için seçim eksik: {miss_txt}. Lütfen 'A# -> Seçim: ...' formatında tamamlayın.",
            "status": "booking_group_select_template",
            "log": None,
        }

    hotel_id = str(data.get("hotel_id") or os.getenv("ELEKTRA_HOTEL_ID", "21966"))
    check_in = str(data.get("check_in") or "")
    check_out = str(data.get("check_out") or "")
    quote_lines: List[str] = []
    total_amount = 0.0
    quote_currency = "EUR"

    for fam in families:
        alias = str(fam.get("alias", "")).upper()
        try:
            quote = await _build_group_family_quote(
                alias=alias,
                selection_text=selections.get(alias, ""),
                fam=fam,
                check_in=check_in,
                check_out=check_out,
                hotel_id=hotel_id,
                lang=lang,
            )
        except Exception:
            quote = {"alias": alias, "ok": False, "error": "price_fetch_failed"}

        if not quote.get("ok"):
            if lang == "en":
                quote_lines.append(f"{alias}: Could not price this selection right now.")
            else:
                quote_lines.append(f"{alias}: Bu seçim için şu an fiyat hesaplanamadı.")
            continue

        subtotal = float(quote.get("subtotal") or 0)
        total_amount += subtotal
        quote_currency = str(quote.get("currency") or quote_currency)
        child_count = len(quote.get("child_ages", []))
        if lang == "en":
            quote_lines.append(
                f"{alias}: {quote.get('room_display')} | {_format_rate_label(bool(quote.get('is_refundable')), 'en')} | "
                f"{quote.get('adults',0)} adults + {child_count} children | "
                f"{quote.get('room_count',1)} room x {_format_money(quote.get('unit_price',0))} {quote_currency} = {_format_money(subtotal)} {quote_currency}"
            )
        else:
            quote_lines.append(
                f"{alias}: {quote.get('room_display')} | {_format_rate_label(bool(quote.get('is_refundable')), 'tr')} | "
                f"{quote.get('adults',0)} yetişkin + {child_count} çocuk | "
                f"{quote.get('room_count',1)} oda x {_format_money(quote.get('unit_price',0))} {quote_currency} = {_format_money(subtotal)} {quote_currency}"
            )

    summary = "\n".join(quote_lines) if quote_lines else ("Fiyat bulunamadı" if lang != "en" else "No price available")
    clear_booking_flow(phone)
    if lang == "en":
        return {
            "reply": (
                f"Great, selections received for {data.get('group_code','group')}.\n\n"
                f"{summary}\n\n"
                f"Total estimated amount: {_format_money(total_amount)} {quote_currency}\n\n"
                "If this looks good, please confirm and share guest names per family."
            ),
            "status": "booking_group_selections_received",
            "log": None,
        }
    return {
        "reply": (
            f"Harika, {data.get('group_code','grup')} için seçimleri aldım.\n\n"
            f"{summary}\n\n"
            f"Tahmini toplam tutar: {_format_money(total_amount)} {quote_currency}\n\n"
            "Uygunsa onay verin; ardından aile bazlı misafir isimlerini alarak devam edelim."
        ),
        "status": "booking_group_selections_received",
        "log": None,
    }


def _find_price_type_alternatives(selected: Dict, rooms: List[Dict]) -> Optional[Dict]:
    """Secilen odanin diger fiyat tipini (refundable/non-refundable) bul.
    Returns: diger secenek dict veya None."""
    room_key = selected.get("room_key", "")
    is_ref = selected.get("is_refundable", False)
    for r in rooms:
        if r["room_key"] == room_key and r["is_refundable"] != is_ref:
            return r
    return None


async def _handle_select_room(
    phone: str, message: str,
    data: Dict, lang: str,
) -> Optional[Dict[str, Any]]:
    """Oda secimi isle."""
    cached = get_price_offers(phone)
    if not cached or not cached.get("offers"):
        clear_booking_flow(phone)
        # Stale SELECT_ROOM state can remain from prior runs/sessions.
        # Do not hard-stop with booking_expired; release flow so router can continue.
        return None

    rooms = get_available_rooms_from_offers(cached["offers"], lang)
    selected = _parse_room_selection(message, rooms)

    if not selected:
        if lang == "en":
            reply = "I couldn't understand your selection. Please enter the room number or name.\n\n"
        else:
            reply = "Seçiminizi anlayamadım. Lütfen oda numarasını veya adını yazın.\n\n"
        reply += _build_room_selection_message(rooms, lang)
        return {"reply": reply, "status": "booking_flow", "log": None}

    # Secim basarili — fiyat tipi secimi gerekiyor mu kontrol et
    query = cached.get("query_params", {})
    if query.get("quiet_mode") and selected.get("room_key") in _quiet_handoff_room_keys():
        return await _handle_quiet_room_handoff(phone, lang)

    # Musteri mesajinda acikca fiyat tipi belirtmis mi? (orn: "superior ucretsiz iptal")
    low = _turkish_lower(message or "")
    explicit_refundable = any(kw in low for kw in ["ucretsiz iptal", "free cancel", "refundable"])
    explicit_nonrefundable = any(kw in low for kw in ["iade yapilmaz", "non refundable", "non-refundable", "iptal edilemez"])
    explicit_choice = explicit_refundable or explicit_nonrefundable

    # Ayni room_key icin diger fiyat tipi var mi?
    alt = _find_price_type_alternatives(selected, rooms)

    # Eger musteri acikca fiyat tipi belirtmediyse VE iki secenek varsa → ASK_PRICE_TYPE
    # Not: Kullanici numarali listeden belirli satiri (orn: "8") sectiyse, o satir zaten
    # belirli bir fiyat tipini temsil eder; tekrar fiyat tipi sorma.
    numeric_row_choice = bool(re.match(r"^\s*\d+\s*$", message or ""))
    if alt and not explicit_choice and not numeric_row_choice:
        # Iki secenegi goster, fiyat tipi sorsun
        # Daha once kaydedilmis isim bilgisini koru
        flow_data = {
            "room_key": selected["room_key"],
            "room_display": selected["room_display"],
            "from_date": query.get("from_date", ""),
            "to_date": query.get("to_date", ""),
            "adult_count": query.get("adult_count", 2),
            "child_ages": query.get("child_ages", []),
            "hotel_id": query.get("hotel_id", "21966"),
            "lang": lang,
        }
        if data.get("guest_first_name"):
            flow_data["guest_first_name"] = data["guest_first_name"]
            flow_data["guest_last_name"] = data.get("guest_last_name", "")

        # Hangisi refundable hangisi non-refundable?
        if selected["is_refundable"]:
            ref_opt, nonref_opt = selected, alt
        else:
            ref_opt, nonref_opt = alt, selected

        flow_data["refundable_price"] = ref_opt["price"]
        flow_data["nonrefundable_price"] = nonref_opt["price"]
        flow_data["refundable_offer_json"] = {k: v for k, v in ref_opt.items() if k != "offer"}
        flow_data["nonrefundable_offer_json"] = {k: v for k, v in nonref_opt.items() if k != "offer"}
        # Tam offer objeleri de lazim (ID'ler icin)
        flow_data["refundable_offer_raw"] = ref_opt.get("offer", {})
        flow_data["nonrefundable_offer_raw"] = nonref_opt.get("offer", {})
        flow_data["currency"] = selected.get("currency", "EUR")

        save_booking_flow(phone, BookingFlowState.ASK_PRICE_TYPE, flow_data)

        if lang == "en":
            reply = (
                f"Great choice! {selected['room_display']}\n\n"
                f"There are two price options available:\n"
                f"1) Free Cancellation: {ref_opt['price']} {ref_opt['currency']}\n"
                f"2) Non-refundable: {nonref_opt['price']} {nonref_opt['currency']}\n\n"
                f"Which one do you prefer? (1 or 2)"
            )
        else:
            reply = (
                f"Harika seçim! {selected['room_display']}\n\n"
                f"İki fiyat seçeneği mevcuttur:\n"
                f"1) Ücretsiz İptal: {ref_opt['price']} {ref_opt['currency']}\n"
                f"2) İptal Edilemez: {nonref_opt['price']} {nonref_opt['currency']}\n\n"
                f"Hangisini tercih edersiniz? (1 veya 2)"
            )
        return {"reply": reply, "status": "booking_flow", "log": None}

    # Fiyat tipi acikca belirtildi veya tek secenek var → dogrudan devam
    flow_data = _build_flow_data_from_selection(selected, query, phone)

    # Daha once kaydedilmis misafir bilgilerini koru (adim adim toplanir)
    if data.get("guest_first_name"):
        flow_data["guest_first_name"] = data["guest_first_name"]
        flow_data["guest_last_name"] = data.get("guest_last_name", "")
        flow_data["guest_phone"] = data.get("guest_phone", "")
        flow_data["guest_email"] = data.get("guest_email", "")
    next_state = _next_guest_info_state(flow_data)
    save_booking_flow(phone, next_state, flow_data)

    if lang == "en":
        refund = "Free Cancellation" if selected["is_refundable"] else "Non-refundable"
        reply = (
            f"Selected: {selected['room_display']} - {refund}: {selected['price']} {selected['currency']}\n\n"
            f"{_guest_info_step_prompt(next_state, lang)}"
        )
    else:
        refund = "Ücretsiz İptal" if selected["is_refundable"] else "İade yapılmaz"
        reply = (
            f"Seçildi: {selected['room_display']} - {refund}: {selected['price']} {selected['currency']}\n\n"
            f"{_guest_info_step_prompt(next_state, lang)}"
        )

    return {"reply": reply, "status": "booking_flow", "log": None}


async def _handle_ask_price_type(
    phone: str, message: str,
    data: Dict, lang: str,
) -> Dict[str, Any]:
    """Fiyat tipi secimi: Ücretsiz İptal vs İptal Edilemez."""
    low = _turkish_lower(message or "").strip()

    chosen_refundable = None

    # Numara ile secim
    if low in ("1", "bir"):
        chosen_refundable = True
    elif low in ("2", "iki"):
        chosen_refundable = False
    else:
        # Metin ile secim
        ref_kws = ["ucretsiz iptal", "free cancel", "ucretsiz", "refundable"]
        nonref_kws = ["iptal edilemez", "iade yapilmaz", "non refundable", "non-refundable", "iade yok"]
        for kw in ref_kws:
            if kw in low:
                chosen_refundable = True
                break
        if chosen_refundable is None:
            for kw in nonref_kws:
                if kw in low:
                    chosen_refundable = False
                    break

    if chosen_refundable is None:
        # Anlasilamadi, tekrar sor
        if lang == "en":
            reply = "I couldn't understand your choice. Please type 1 for Free Cancellation or 2 for Non-refundable."
        else:
            reply = "Seçiminizi anlayamadım. Lütfen 1 (Ücretsiz İptal) veya 2 (İptal Edilemez) yazın."
        return {"reply": reply, "status": "booking_flow", "log": None}

    # Secim yapildi — dogru offer'i al
    if chosen_refundable:
        chosen_offer_json = data.get("refundable_offer_json", {})
        chosen_offer_raw = data.get("refundable_offer_raw", {})
    else:
        chosen_offer_json = data.get("nonrefundable_offer_json", {})
        chosen_offer_raw = data.get("nonrefundable_offer_raw", {})

    # Offer objesini reconstruct et
    selected = dict(chosen_offer_json)
    selected["offer"] = chosen_offer_raw

    cached = get_price_offers(phone)
    query = cached.get("query_params", {}) if cached else {}
    # Cache expired olsa bile flow data'da saklanan bilgileri koru
    if not query.get("child_ages") and data.get("child_ages"):
        query["child_ages"] = data["child_ages"]
    if not query.get("adult_count") and data.get("adult_count"):
        query["adult_count"] = data["adult_count"]
    if not query.get("from_date") and data.get("from_date"):
        query["from_date"] = data["from_date"]
    if not query.get("to_date") and data.get("to_date"):
        query["to_date"] = data["to_date"]
    if not query.get("hotel_id") and data.get("hotel_id"):
        query["hotel_id"] = data["hotel_id"]
    flow_data = _build_flow_data_from_selection(selected, query, phone)

    # Onceki asamadan gelen isim bilgisini koru
    if data.get("guest_first_name"):
        flow_data["guest_first_name"] = data["guest_first_name"]
        flow_data["guest_last_name"] = data.get("guest_last_name", "")
    flow_data["guest_phone"] = data.get("guest_phone", "")
    flow_data["guest_email"] = data.get("guest_email", "")

    refund_tr = "Ücretsiz İptal" if chosen_refundable else "İptal Edilemez"
    refund_en = "Free Cancellation" if chosen_refundable else "Non-refundable"
    price = selected.get("price", 0)
    currency = selected.get("currency", "EUR")
    room_display = selected.get("room_display", data.get("room_display", ""))

    next_state = _next_guest_info_state(flow_data)
    save_booking_flow(phone, next_state, flow_data)

    if lang == "en":
        reply = (
            f"Selected: {room_display} - {refund_en}: {price} {currency}\n\n"
            f"{_guest_info_step_prompt(next_state, lang)}"
        )
    else:
        reply = (
            f"Seçildi: {room_display} - {refund_tr}: {price} {currency}\n\n"
            f"{_guest_info_step_prompt(next_state, lang)}"
        )
    return {"reply": reply, "status": "booking_flow", "log": None}


def _extract_phone_from_message(text: str) -> str:
    """Mesajdan telefon numarasi cikar."""
    # +90 530 449 84 53 veya 05304498453 veya 530 449 84 53 formatlari
    m = re.search(r'(\+?\d[\d\s\-\(\)]{7,18}\d)', text or "")
    if m:
        raw = re.sub(r'[\s\-\(\)]', '', m.group(1))
        if len(raw) >= 8:
            return raw
    return ""


def _extract_email_from_message(text: str) -> str:
    """Mesajdan e-posta adresi cikar."""
    m = re.search(r'[\w\.\-\+]+@[\w\.\-]+\.\w{2,}', text or "")
    return m.group(0) if m else ""


def _extract_name_from_contact_message(text: str) -> Optional[Dict[str, str]]:
    """Mesajdan ad-soyad cikar. Telefon/email kisimlarini temizle."""
    def _normalize_name_candidate(candidate: str) -> str:
        c = (candidate or "").strip()
        if not c:
            return ""
        # "Ömer Alperen Gönen, ...", "Ömer ... ve bu telefon ..." gibi dogal metinlerde
        # isim disi kuyrugu temizle.
        c = re.split(r",|;|\s+ve\s+|\sand\s+", c, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        c = re.sub(
            r"\b(?:bu|this|telefon|phone|numara|numarası|numarasını|number|kayıt|kayit|sistem|sisteme|edebilirsiniz|kullan(?:abilirsiniz)?)\b.*$",
            "",
            c,
            flags=re.IGNORECASE,
        ).strip(" ,-/")
        return c

    lines = text.strip().split("\n")
    name_candidates = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Label'i cikar: "Ad Soyad: Omer Alperen GONEN" veya "Isim: ..."
        for label in ["ad soyad", "adsoyad", "isim", "ad:", "soyad:", "name:", "isim:", "ad soyad:"]:
            if line.lower().startswith(label):
                line = line[len(label):].strip().lstrip(":").strip()
                break
        # Label iceren ama deger olmayan satirlari atla
        low = line.lower()
        if any(kw == low for kw in ["telefon", "phone", "email", "e-posta", "eposta", "tel", "gsm"]):
            continue
        # Oda adlari, tarihler, kisi bilgisi iceren satirlari atla
        _skip_words = [
            "deluxe", "superior", "exclusive", "penthouse land", "penthouse", "premium",
            "giris", "giriş", "cikis", "çıkış", "check-in", "check-out",
            "yetiskin", "yetişkin", "cocuk", "çocuk", "kisi", "kişi",
            "adult", "child", "people",
            "rezervasyon", "rezerve", "book", "reservation",
            "oda", "room", "fiyat", "price", "olustur", "oluştur",
        ]
        if any(sw in low for sw in _skip_words):
            continue
        # Tarih iceren satirlari atla (orn: 01.09.2026, 2026-09-01)
        if re.search(r'\d{2}[./\-]\d{2}[./\-]\d{4}|\d{4}[./\-]\d{2}[./\-]\d{2}', line):
            continue
        # Sadece telefon veya sadece email iceren satiri atla
        cleaned = line
        # Email'i cikar
        cleaned = re.sub(r'[\w.\-]+@[\w.\-]+\.\w+', '', cleaned)
        # Telefon numarasini cikar
        cleaned = re.sub(r'\+?\d[\d\s\-]{7,}\d', '', cleaned)
        # Label etiketlerini cikar
        for lbl in ["telefon:", "tel:", "phone:", "email:", "e-posta:", "eposta:", "gsm:"]:
            cleaned = re.sub(re.escape(lbl), '', cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.strip(" ,-/")
        cleaned = _normalize_name_candidate(cleaned)
        if cleaned and len(cleaned) >= 2:
            name_candidates.append(cleaned)

    # Ilk uygun satiri isim olarak dene
    for candidate in name_candidates:
        parsed = _parse_guest_name(_normalize_name_candidate(candidate))
        if parsed:
            return parsed

    # Hic bulunamadiysa tum mesaji temizle ve dene
    fallback = text
    fallback = re.sub(r'[\w.\-]+@[\w.\-]+\.\w+', '', fallback)
    fallback = re.sub(r'\+?\d[\d\s\-]{7,}\d', '', fallback)
    for lbl in ["telefon:", "tel:", "phone:", "email:", "e-posta:", "eposta:", "gsm:",
                 "ad soyad:", "isim:", "name:", "ad:", "soyad:"]:
        fallback = re.sub(re.escape(lbl), '', fallback, flags=re.IGNORECASE)
    fallback = _normalize_name_candidate(fallback.strip())
    if fallback and not _message_looks_like_booking_intent(fallback):
        return _parse_guest_name(fallback)
    return None


def _wants_use_current_phone(text: str) -> bool:
    low = _turkish_lower(text or "")
    hints = [
        "bu telefon numaras",
        "bu numaray",
        "mevcut numara",
        "sistemdeki numara",
        "this phone number",
        "use my number",
        "use this number",
        "current phone number",
    ]
    return any(h in low for h in hints)


async def _handle_ask_name(
    phone: str, message: str,
    data: Dict, lang: str,
) -> Dict[str, Any]:
    """Ad-soyad bilgisi topla (ilk adim)."""
    parsed = _extract_name_from_contact_message(message)

    if not parsed:
        low = _turkish_lower(message or "")
        force_tr = bool(re.search(r"[çğıöşü]", low)) or any(
            k in low for k in ("yazdim", "yazdım", "zaten", "adim", "adım", "soyad")
        )
        if lang == "en":
            if force_tr:
                return {
                    "reply": "Ad soyad bilgisini anlayamadım. Lütfen ad ve soyadınızı net şekilde yazın (örn: Ahmet Yılmaz).",
                    "status": "booking_flow", "log": None,
                }
            return {
                "reply": "I couldn't understand the full name. Please share first and last name (e.g., John Smith).",
                "status": "booking_flow", "log": None,
            }
        return {
            "reply": "Ad soyad bilgisini anlayamadım. Lütfen ad ve soyadınızı yazın (örn: Ahmet Yılmaz).",
            "status": "booking_flow", "log": None,
        }

    data["guest_first_name"] = parsed["first_name"]
    data["guest_last_name"] = parsed["last_name"]

    next_state = _next_guest_info_state(data)
    save_booking_flow(phone, next_state, data)

    if next_state == BookingFlowState.ASK_SPECIAL:
        if lang == "en":
            return {"reply": f"Thank you, {parsed['first_name']}! Do you have any special requests? (Type 'no' to skip)", "status": "booking_flow", "log": None}
        return {"reply": f"Teşekkürler! {parsed['first_name']}, özel bir isteğiniz var mı? (Yoksa 'yok' yazabilirsiniz)", "status": "booking_flow", "log": None}

    if lang == "en":
        return {"reply": f"Thank you! {parsed['first_name']}, {_guest_info_step_prompt(next_state, lang)}", "status": "booking_flow", "log": None}
    return {"reply": f"Teşekkürler! {parsed['first_name']}, {_guest_info_step_prompt(next_state, lang)}", "status": "booking_flow", "log": None}


async def _handle_ask_phone(
    phone: str, message: str,
    data: Dict, lang: str,
) -> Dict[str, Any]:
    guest_phone = _extract_phone_from_message(message)
    if not guest_phone and _wants_use_current_phone(message):
        guest_phone = (phone or "").strip()

    if not guest_phone:
        return {"reply": _guest_info_step_prompt(BookingFlowState.ASK_PHONE, lang), "status": "booking_flow", "log": None}

    data["guest_phone"] = guest_phone
    next_state = _next_guest_info_state(data)
    save_booking_flow(phone, next_state, data)
    return {"reply": _guest_info_step_prompt(next_state, lang), "status": "booking_flow", "log": None}


async def _handle_ask_email(
    phone: str, message: str,
    data: Dict, lang: str,
) -> Dict[str, Any]:
    low = _turkish_lower((message or "").strip())
    skip_keywords = {"gec", "geç", "atla", "skip", "no", "yok", "none", "-"}
    if low in skip_keywords:
        data["guest_email"] = data.get("guest_email", "")
    else:
        guest_email = _extract_email_from_message(message)
        if guest_email:
            data["guest_email"] = guest_email
        else:
            return {"reply": _guest_info_step_prompt(BookingFlowState.ASK_EMAIL, lang), "status": "booking_flow", "log": None}

    save_booking_flow(phone, BookingFlowState.ASK_SPECIAL, data)
    if lang == "en":
        return {"reply": "Thank you. Do you have any special requests? (Type 'no' to skip)", "status": "booking_flow", "log": None}
    return {"reply": "Teşekkürler. Özel bir isteğiniz var mı? (Yoksa 'yok' yazabilirsiniz)", "status": "booking_flow", "log": None}


async def _handle_ask_special(
    phone: str, message: str,
    data: Dict, lang: str,
) -> Dict[str, Any]:
    """Ozel istek topla (opsiyonel)."""
    low = _turkish_lower(message).strip()

    skip_keywords = ["yok", "hayir", "no", "none", "nothing", "bos", "-"]
    if low in skip_keywords or len(low) <= 2:
        data["special_requests"] = ""
    else:
        data["special_requests"] = message.strip()

    save_booking_flow(phone, BookingFlowState.CONFIRM, data)

    summary = _build_booking_summary(data, lang)
    return {"reply": summary, "status": "booking_flow", "log": None}


async def _handle_confirm(
    phone: str, message: str,
    data: Dict, lang: str,
) -> Dict[str, Any]:
    """Onay / red isle."""
    low = _turkish_lower(message).strip()

    yes_keywords = ["evet", "yes", "onay", "onayla", "onayliyorum", "tamam", "ok", "olur"]
    no_keywords = ["hayir", "no", "iptal", "vazgec", "istemiyorum", "red"]

    if any(kw in low for kw in no_keywords):
        clear_booking_flow(phone)
        if lang == "en":
            return {"reply": "Reservation request cancelled. How can I help you?", "status": "booking_cancelled", "log": None}
        return {"reply": "Rezervasyon talebi iptal edildi. Size nasıl yardımcı olabilirim?", "status": "booking_cancelled", "log": None}

    if not any(kw in low for kw in yes_keywords):
        if lang == "en":
            return {"reply": "Please confirm with 'Yes' or cancel with 'No'.", "status": "booking_flow", "log": None}
        return {"reply": "Lütfen 'Evet' ile onaylayın veya 'Hayır' ile iptal edin.", "status": "booking_flow", "log": None}

    # ONAY — SQLite'a kaydet, admin'e bildir
    booking_data = {
        "customer_phone": phone,
        "guest_first_name": data.get("guest_first_name", ""),
        "guest_last_name": data.get("guest_last_name", ""),
        "guest_title_id": 0,  # 0=MR (default), 1=MS, 2=CHILD, 3=BABY
        "hotel_id": int(data.get("hotel_id", 21966)),
        "check_in": data.get("check_in", ""),
        "check_out": data.get("check_out", ""),
        "nights": data.get("nights", 0),
        "adult_count": data.get("adult_count", 2),
        "child_ages": data.get("child_ages", []),
        "room_type": data.get("room_type", ""),
        "room_type_display": data.get("room_type_display", ""),
        "room_type_id": data.get("room_type_id", 0),
        "board_type_id": data.get("board_type_id", 0),
        "rate_type_id": data.get("rate_type_id", 0),
        "rate_code_id": data.get("rate_code_id", 0),
        "price_agency_id": data.get("price_agency_id", 0),
        "currency_id": data.get("currency_id", 0),
        "currency": data.get("currency", "EUR"),
        "total_price": data.get("total_price", 0),
        "discounted_price": data.get("discounted_price"),
        "is_refundable": data.get("is_refundable", False),
        "special_requests": data.get("special_requests", ""),
        "guest_phone": data.get("guest_phone", ""),
        "guest_email": data.get("guest_email", ""),
        "lang": lang,
        "booking_context_id": data.get("booking_context_id", ""),
        "is_test": _is_test_phone(phone),
    }

    try:
        booking = create_hotel_booking(booking_data)
        booking_id = booking.get("id", "?")
        booking_ctx = booking.get("booking_context_id", "")
    except Exception as e:
        print(f"[BOOKING] DB error: {e}")
        clear_booking_flow(phone)
        if lang == "en":
            return {"reply": "An error occurred. Our team will contact you shortly.", "status": "booking_error", "log": str(e)}
        return {"reply": "Bir hata olustu. Ekibimiz en kisa surede sizinle iletisime gececektir.", "status": "booking_error", "log": str(e)}

    # Flow'u temizle
    clear_booking_flow(phone)

    # Admin bildirimi (WhatsApp) — asenkron olarak ana bot tarafindan yapilacak
    # Burada sadece booking_id'yi donduruyoruz, bot admin'e haber verecek
    guest_name = f"{data.get('guest_first_name', '')} {data.get('guest_last_name', '')}".strip()
    price = data.get("discounted_price") or data.get("total_price", 0)

    reply = _build_booking_pending_reply(
        lang=lang,
        booking_id=booking_id,
        booking_ctx=booking_ctx,
        room_display=data.get("room_type_display", ""),
        check_in=data.get("check_in", ""),
        check_out=data.get("check_out", ""),
        price=price,
        currency=data.get("currency", "EUR"),
    )

    return {
        "reply": reply,
        "status": "booking_pending_approval",
        "log": f"booking_id={booking_id}",
        "booking_id": booking_id,
        "booking_data": booking_data,
    }
