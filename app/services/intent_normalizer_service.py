from __future__ import annotations

from typing import Callable
import re
import unicodedata

PRICE_AVAILABILITY_MARKERS = (
    # tr
    "fiyat", "ücret", "ucret", "ne kadar", "müsait", "musait",
    # en
    "price", "rate", "cost", "availability", "available", "how much",
    # ru
    "цена", "стоимость", "тариф", "доступ", "наличие", "сколько",
    # de
    "preis", "kosten", "verfügbarkeit", "verfugbarkeit", "frei",
    # es
    "precio", "coste", "tarifa", "disponibilidad", "disponible", "cuánto", "cuanto",
    # fr
    "prix", "coût", "cout", "tarif", "disponibilité", "disponibilite", "disponible", "combien",
    # pt
    "preço", "preco", "custo", "tarifa", "disponibilidade", "disponível", "disponivel", "quanto",
    # ar
    "سعر", "الاسعار", "الأسعار", "التكلفة", "متاح", "التوفر", "توفر", "كم",
    # zh
    "价格", "价钱", "费用", "房价", "总价", "总价格", "可订", "有房", "空房", "可用", "多少钱",
    # hi
    "कीमत", "मूल्य", "दर", "उपलब्ध", "उपलब्धता", "कितना",
)

ROOM_CONTEXT_MARKERS = (
    "oda", "room", "manzara", "view", "havuz manzara", "pool view", "deniz manzara", "sea view",
    "standart oda", "superior", "deluxe", "exclusive", "penthouse", "premium",
    "номер", "комнат", "вид", "видом",
    "zimmer", "aussicht",
    "habitación", "habitacion", "vista",
    "chambre", "vue",
    "quarto",
    "غرفة", "الغرفة", "إطلالة", "اطلالة",
    "房间", "房型", "景观", "房",
    "कमरा", "दृश्य",
)

RESTAURANT_CONTEXT_MARKERS = (
    "restoran", "restaurant", "masa", "table",
    "yemek", "yemegi", "yemeg", "aksam", "aksam yemegi", "dinner", "ogle", "lunch",
    "kahvalti", "breakfast", "meal",
)

def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(m in text for m in markers)


_CONFUSABLE_CHAR_MAP = str.maketrans(
    {
        "а": "a",  # Cyrillic
        "е": "e",
        "о": "o",
        "р": "p",
        "с": "c",
        "у": "y",
        "х": "x",
        "к": "k",
        "м": "m",
        "т": "t",
        "в": "b",
        "н": "h",
        "і": "i",
        "ї": "i",
        "ӏ": "l",
        "ş": "s",
        "ğ": "g",
        "ı": "i",
        "ö": "o",
        "ü": "u",
        "ç": "c",
    }
)


def _normalize_for_keyword_match(message: str) -> str:
    raw = (message or "").strip().lower()
    if not raw:
        return ""
    folded = unicodedata.normalize("NFKD", raw)
    stripped = "".join(ch for ch in folded if not unicodedata.combining(ch))
    mapped = stripped.translate(_CONFUSABLE_CHAR_MAP)
    mapped = re.sub(r"[^a-z0-9\s]", " ", mapped)
    return re.sub(r"\s+", " ", mapped).strip()


def _has_restaurant_context_without_room_context(message: str) -> bool:
    low = _normalize_for_keyword_match(message)
    if not low:
        return False
    has_restaurant_context = _contains_any(low, RESTAURANT_CONTEXT_MARKERS)
    has_room_context = _contains_any(low, ROOM_CONTEXT_MARKERS)
    return has_restaurant_context and not has_room_context


def looks_like_booking_payment_followup(message: str) -> bool:
    low = (message or "").strip().lower()
    if not low:
        return False
    markers = (
        "odeme link",
        "ödeme link",
        "payment link",
        "pay online",
        "kredi kart",
        "credit card",
        "havale",
        "eft",
        "bank transfer",
        "on odeme",
        "ön ödeme",
        "kapora",
        "depozito",
        "deposit",
        "prepayment",
        "advance payment",
        "odemeyi ne zamana kadar",
        "ödemeyi ne zamana kadar",
        "kapora ne kadar",
    )
    return any(m in low for m in markers)


def looks_like_explicit_room_price_or_availability_query(message: str) -> bool:
    low = (message or "").lower()
    if not low:
        return False
    has_price_or_availability = _contains_any(low, PRICE_AVAILABILITY_MARKERS)
    has_room_context = _contains_any(low, ROOM_CONTEXT_MARKERS)
    return has_price_or_availability and has_room_context


def looks_like_generic_price_or_availability_signal(message: str) -> bool:
    low = (message or "").lower()
    if not low:
        return False
    if _has_restaurant_context_without_room_context(message):
        return False
    return _contains_any(low, PRICE_AVAILABILITY_MARKERS)


def looks_like_general_price_query_with_slots(
    message: str,
    looks_like_price_slot_payload_fn: Callable[[str], bool],
) -> bool:
    low = (message or "").lower()
    if not low:
        return False
    has_price_marker = _contains_any(low, PRICE_AVAILABILITY_MARKERS)
    return has_price_marker and bool(looks_like_price_slot_payload_fn(message))


def looks_like_explicit_booking_create_signal(message: str) -> bool:
    low = _normalize_for_keyword_match(message)
    if not low:
        return False
    explicit_phrase_match = any(
        phrase in low
        for phrase in (
            "rezervasyon olustur",
            "rezervasyon olusturur",
            "rezervasyon yap",
            "rezervasyon ist",
            "room booking",
            "book room",
            "book the",
            "make reservation",
            "make a reservation",
            "reserve room",
            "reserve the",
        )
    )
    if explicit_phrase_match:
        return True
    has_booking = any(k in low for k in ("rezervasyon", "booking", "book", "reserve", "reservation"))
    has_create = any(k in low for k in ("olustur", "yap", "baslat", "start", "create", "make"))
    return has_booking and has_create


def looks_like_restaurant_booking_signal(message: str) -> bool:
    low = _normalize_for_keyword_match(message)
    if not low:
        return False
    has_restaurant_context = _contains_any(low, RESTAURANT_CONTEXT_MARKERS)
    if not has_restaurant_context:
        return False
    has_booking_markers = any(k in low for k in ("rezerv", "booking", "book", "reserve", "reservation"))
    has_room_markers = _contains_any(low, ROOM_CONTEXT_MARKERS)
    return has_booking_markers and not has_room_markers


def force_primary_intent_from_explicit_message(
    message: str,
    current_intent: str,
    *,
    looks_like_price_slot_payload_fn: Callable[[str], bool],
) -> str:
    low = (message or "").lower()
    normalized_low = _normalize_for_keyword_match(message)
    has_booking_markers = looks_like_explicit_booking_create_signal(message)
    has_restaurant_booking_markers = looks_like_restaurant_booking_signal(message)
    has_room_context = _contains_any(normalized_low, ROOM_CONTEXT_MARKERS)
    has_payment_markers = any(
        k in low
        for k in (
            "ödeme",
            "odeme",
            "payment",
            "kredi kart",
            "credit card",
            "payment link",
            "odeme link",
            "ödeme link",
            "kapora",
            "depozito",
            "deposit",
            "prepayment",
        )
    )
    has_price_markers = looks_like_generic_price_or_availability_signal(message)
    has_transfer_context = any(
        k in normalized_low
        for k in ("transfer", "havaliman", "havaalani", "airport", "dalaman", "antalya")
    )
    has_transfer_booking_details = any(
        k in normalized_low
        for k in (
            "ucus",
            "flight",
            "rota",
            "route",
            "bagaj",
            "luggage",
            "baggage",
            "bebek koltugu",
            "baby seat",
            "guest",
            "kisi",
        )
    ) or bool(looks_like_price_slot_payload_fn(message))
    has_local_faq_markers = any(
        k in normalized_low
        for k in (
            "wifi",
            "wi fi",
            "internet",
            "kahvalti",
            "breakfast",
            "check in",
            "check out",
            "checkout",
            "konum",
            "adres",
            "location",
            "sezon",
            "season",
            "havuz",
            "pool",
            "spa",
            "otopark",
            "parking",
        )
    )

    if any(
        k in low
        for k in (
            "rezervasyonu başlatalım",
            "rezervasyonu baslatalim",
            "rezervasyon başlatalım",
            "rezervasyon baslatalim",
            "start reservation",
            "start booking",
            "book now",
        )
    ):
        if has_restaurant_booking_markers and not has_price_markers and not has_payment_markers:
            return "RESTAURANT_BOOKING_CREATE"
        return "HOTEL_BOOKING_CREATE"
    if has_booking_markers and not has_price_markers and not has_payment_markers:
        if has_restaurant_booking_markers:
            return "RESTAURANT_BOOKING_CREATE"
        return "HOTEL_BOOKING_CREATE"
    if has_transfer_context and not has_payment_markers and not has_room_context:
        if has_transfer_booking_details or any(k in normalized_low for k in ("rezerv", "booking", "book", "reserve")):
            return "TRANSFER_BOOKING_REQUEST"
        return "TRANSFER_INFO"
    if has_local_faq_markers and not has_payment_markers and not has_room_context and not has_transfer_context:
        return "LOCAL_FAQ_INFO"

    if has_price_markers and not has_payment_markers:
        return "PRICE_QUERY"
    if any(k in low for k in ("ödeme", "odeme", "payment", "kredi kart", "credit card")):
        if "link" in low:
            return "PAYMENT_LINK_REQUEST"
        return "PAYMENT_METHOD_QUERY"
    if looks_like_booking_payment_followup(message):
        return "PAYMENT_METHOD_QUERY"
    if looks_like_explicit_room_price_or_availability_query(message):
        return "PRICE_QUERY"
    if looks_like_general_price_query_with_slots(message, looks_like_price_slot_payload_fn):
        return "PRICE_QUERY"
    return current_intent
