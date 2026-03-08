"""app/handlers/price_flow_handler.py

Akilli Fiyat Akisi Handler'i.
Musterinin dogal dildeki fiyat sorularini anlar, eksik bilgileri
adim adim toplar, Elektraweb'e sorgu atar.

Elektraweb'in cevaplayamayacagi sorulari insana devir (handoff) yapar.

v1 — 2026-02-12
v1.1 — 2026-02-12: Currency re-query (dolar/euro/TL cevir) destegi
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Optional, Tuple

from app.services.price_flow_service import (
    PriceFlowState,
    get_price_flow,
    save_price_flow,
    clear_price_flow,
    is_price_flow_active,
    save_last_query,
    get_last_query,
    save_last_seen_context,
    get_last_seen_context,
)
from app.services.elektraweb_booking_service import (
    handle_elektra_price_request,
    fetch_room_stock_by_type_from_availability,
    ElektrawebConfigError,
    _extract_all_dates,
    _extract_adult_count,
    _extract_child_ages,
    _normalize_turkish_chars,
    _infer_currency,
)
from app.core.settings_service import get_currency_policy
from app.services.hotel_runtime_info_service import get_hotel_runtime_info

# ===========================================================
# 0) SEZON KONTROLÜ (Sezon dışı taleplerde Elektra'ya gitme)
# ===========================================================

_MONTH_TR = {
    1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran",
    7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"
}
_MONTH_EN = {
    1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
    7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December"
}


def _season_mmdd() -> Tuple[str, str]:
    info = get_hotel_runtime_info()
    start_mmdd = str(info.get("hotel_opening_mmdd") or "04-01")
    end_mmdd = str(info.get("hotel_closing_mmdd") or "11-30")
    return start_mmdd, end_mmdd


def _parse_mmdd(mmdd: str) -> Tuple[int, int]:
    try:
        m, d = mmdd.split("-", 1)
        return int(m), int(d)
    except Exception:
        return (4, 1)

def _fmt_mmdd(mmdd: str, lang: str) -> str:
    m, d = _parse_mmdd(mmdd)
    if lang == "en":
        return f"{_MONTH_EN.get(m, str(m))} {d}"
    return f"{d} {_MONTH_TR.get(m, str(m))}"

def _fmt_iso_date(iso_date: str, lang: str) -> str:
    try:
        d = datetime.strptime(iso_date, "%Y-%m-%d")
        if lang == "en":
            return f"{_MONTH_EN.get(d.month, str(d.month))} {d.day} {d.year}"
        return f"{d.day} {_MONTH_TR.get(d.month, str(d.month))} {d.year}"
    except Exception:
        return iso_date

def _is_out_of_season(from_date: str, to_date: str) -> bool:
    try:
        d1 = datetime.strptime(from_date, "%Y-%m-%d").date()
        d2 = datetime.strptime(to_date, "%Y-%m-%d").date()
    except Exception:
        return False

    if d1.year != d2.year:
        return True

    season_start_mmdd, season_end_mmdd = _season_mmdd()
    sm, sd = _parse_mmdd(season_start_mmdd)
    em, ed = _parse_mmdd(season_end_mmdd)
    season_start = date(d1.year, sm, sd)
    season_end = date(d1.year, em, ed)

    allowed_checkout = season_end + timedelta(days=1)
    return not (d1 >= season_start and d2 <= allowed_checkout)

def _build_out_of_season_reply(lang: str, from_date: str, to_date: str) -> str:
    season_start_mmdd, season_end_mmdd = _season_mmdd()
    season_str = f"{_fmt_mmdd(season_start_mmdd, lang)} - {_fmt_mmdd(season_end_mmdd, lang)}"
    req_str = f"{_fmt_iso_date(from_date, lang)} - {_fmt_iso_date(to_date, lang)}"
    if lang == "en":
        return (
            f"Our hotel operates between {season_str}. "
            f"Your requested dates ({req_str}) are outside our season. "
            f"If you share an alternative date range within the season, I can check availability and prices right away."
        )
    return (
        f"Otelimiz {season_str} tarihleri arasında hizmet vermektedir. "
        f"Paylaştığınız tarihler ({req_str}) sezon dışındadır. "
        f"Sezon içinden alternatif tarih paylaşırsanız hemen müsaitlik ve fiyat kontrol edebilirim."
    )

# ===========================================================
# 1) HANDOFF KEYWORD LISTESI (Elektraweb cevaplayamaz)
# ===========================================================
# GÜNCELLEME 2026-02-14: Liste sadeleştirildi.
# Sadece uzun kalış ve grup fiyatı konularında insana devir.
# Diğer konular (otopark, spa, pansiyon tipi, erken giriş, vb.)
# artık OpenAI tarafından system prompt bilgisiyle cevaplanır.

HANDOFF_PRICE_KEYWORDS_TR = [
    # Uzun kalış / özel fiyat
    "uzun kalış", "uzun kalis", "uzun konaklama",
    "uzun süre kalacağız", "uzun sure kalacagiz",
    # Grup fiyatı
    "grup fiyat", "grup indirimi", "toplu rezervasyon",
    "grup konaklama", "grup teklif",
]

_ROOM_KEY_BY_HINT = {
    "deluxe": "deluxe",
    "superior": "superior",
    "exclusive pool": "exclusivePool",
    "havuz manzar": "exclusivePool",
    "exclusive land": "exclusiveLand",
    "sokak manzar": "exclusiveLand",
    "penthouse land": "penthouseLand",
    "penthouse": "penthouse",
    "premium": "premium",
}

_ROOM_LABEL_TR = {
    "deluxe": "Deluxe",
    "superior": "Superior",
    "exclusiveLand": "Exclusive Sokak Manzaralı",
    "exclusivePool": "Exclusive Havuz Manzaralı",
    "penthouseLand": "Penthouse Land - Jakuzili",
    "penthouse": "Penthouse - Jakuzili",
    "premium": "Premium - Jakuzili",
}


def _is_technical_handoff_error(error_type: str) -> bool:
    return (error_type or "").strip().upper() in {"API_ERROR", "AVAILABILITY_ERROR", "FORMAT_ERROR"}


def _technical_price_error_reply(lang: str) -> str:
    if lang == "en":
        return "I have forwarded your request to our team. We will contact you shortly with price and availability details."
    return "Talebinizi ekibimize ilettim. Fiyat ve müsaitlik detayları için en kısa sürede sizinle iletişime geçeceğiz."


_DISABLED_CURRENCY_REPLY = (
    "Fiyat talebinde bulunduğunuz para birimi ile fiyat bilgisi veremiyorum "
    "daha detaylı bilgi için lütfen canlı müşteri temsilcisini bekleyiniz"
)


def _is_currency_enabled(code: Optional[str]) -> bool:
    cur = str(code or "").strip().upper()
    if not cur:
        return True
    policy = get_currency_policy()
    # Bilinmeyen para birimlerinde mevcut davranisi koru (engelleme yok).
    if cur not in policy:
        return True
    return bool(policy.get(cur))


def _extract_stock_from_cached_offers(cached_offers: List[Dict[str, Any]], room_key: str) -> Optional[int]:
    """
    Son fiyat sorgusunda gelen offer listesinden oda adedi cikarmayi dener.
    Bu, fiyat mesaji ile stok mesaji arasinda tutarlilik saglar.
    """
    candidates: List[int] = []
    try:
        from app.services.elektraweb_booking_service import _normalize_room_type
    except Exception:
        _normalize_room_type = None

    for offer in cached_offers or []:
        room_type_raw = str(offer.get("room-type", "") or "")
        if not room_type_raw:
            continue
        key = ""
        if _normalize_room_type:
            info = _normalize_room_type(room_type_raw)
            if info and info.get("key"):
                key = str(info["key"])
        if key != room_key:
            continue

        arr = offer.get("availability-arr")
        if isinstance(arr, list) and arr:
            nums = []
            for v in arr:
                try:
                    nums.append(int(v))
                except Exception:
                    pass
            if nums:
                candidates.append(max(0, min(nums)))
                continue

        for count_key in ("room-to-sell", "room_to_sell", "room-count", "room_count", "remaining", "availability"):
            try:
                iv = int(offer.get(count_key))
            except Exception:
                iv = None
            if iv is not None:
                candidates.append(max(0, iv))
                break

    if not candidates:
        return None
    return max(candidates)


def _extract_room_key_for_stock_query(message: str) -> Optional[str]:
    low = _normalize_turkish_chars((message or "").lower())
    for hint, room_key in _ROOM_KEY_BY_HINT.items():
        if hint in low:
            return room_key
    return None


def _is_room_stock_query(message: str) -> bool:
    low = _normalize_turkish_chars((message or "").lower())
    stock_markers = [
        "kac adet", "kaç adet", "kac oda", "kaç oda", "oda kaldi", "oda kaldi",
        "musait", "müsait", "available", "left", "remaining",
    ]
    return any(k in low for k in stock_markers) and _extract_room_key_for_stock_query(low) is not None


def _extract_multi_room_guest_groups(message: str) -> List[Dict[str, Any]]:
    """
    Ornek:
    - "1. Aile 2 yetişkin. 2. aile 2 yetişkin + 2 çocuk 3 ve 10 yaşındalar."
    - "1. Oda: 2 yetişkin | 2. Oda: 2 yetişkin + 2 çocuk (3 ve 10 yaş)"
    """
    raw = (message or "").strip()
    if not raw:
        return []
    segments = re.split(r"\s*(?:\||\n|(?=\d+\s*[\.\)]\s*(?:aile|oda)))\s*", raw, flags=re.IGNORECASE)
    groups: List[Dict[str, Any]] = []
    for seg in segments:
        txt = (seg or "").strip()
        if not txt:
            continue
        adult, child_ages = _extract_guests_smart(txt)
        if adult:
            groups.append({"adult_count": int(adult), "child_ages": child_ages or []})
    return groups

HANDOFF_PRICE_KEYWORDS_EN = [
    # Long stay / special pricing
    "long stay", "extended stay", "long term",
    # Group pricing
    "group rate", "group price", "group discount",
    "group booking", "group reservation",
]


# ===========================================================
# 2) PARA BIRIMI DEGISIKLIGI ALGILAMA
# ===========================================================

CURRENCY_CHANGE_PATTERNS = [
    # Turkce
    (r"(?:fiyat|ücret|ucret|fiyatlar).*(?:dolar|dollar|\$|usd)", "USD"),
    (r"(?:dolar|dollar|\$|usd).*(?:fiyat|ücret|ucret|olarak|cinsinden|ile)", "USD"),
    (r"(?:fiyat|ücret|ucret|fiyatlar).*(?:euro|€|eur)", "EUR"),
    (r"(?:euro|€|eur).*(?:fiyat|ücret|ucret|olarak|cinsinden|ile)", "EUR"),
    (r"(?:fiyat|ücret|ucret|fiyatlar).*(?:\btl\b|₺|türk lirası|turk lirasi)", "TRY"),
    (r"(?:\btl\b|₺|türk lirası|turk lirasi).*(?:fiyat|ücret|ucret|olarak|cinsinden|ile)", "TRY"),
    (r"(?:fiyat|ücret|ucret|fiyatlar).*(?:sterlin|pound|gbp|£)", "GBP"),
    (r"(?:sterlin|pound|gbp|£).*(?:fiyat|ücret|ucret|olarak|cinsinden|ile)", "GBP"),
    # Kisa kaliplar: "$  olarak", "dolara çevir"
    (r"(?:dolar|dollar|\$|usd)\s*(?:olarak|cinsinden|ile|verir|paylas|yazar|goster|cevir|çevir)", "USD"),
    (r"(?:euro|€|eur)\s*(?:olarak|cinsinden|ile|verir|paylas|yazar|goster|cevir|çevir)", "EUR"),
    (r"(?:\btl\b|₺)\s*(?:olarak|cinsinden|ile|verir|paylas|yazar|goster|cevir|çevir)", "TRY"),
    (r"(?:sterlin|pound|gbp|£)\s*(?:olarak|cinsinden|ile|verir|paylas|yazar|goster|cevir|çevir)", "GBP"),
    # Ingilizce
    (r"(?:price|prices|cost).*(?:in\s+(?:usd|dollars?|eur|euros?|gbp|pounds?|try|tl))", None),
    (r"(?:in\s+(?:usd|dollars?|eur|euros?|gbp|pounds?|try|tl)).*(?:price|cost|rate)", None),
    (r"(?:show|give|convert|change).*(?:usd|dollars?|\$)", "USD"),
    (r"(?:show|give|convert|change).*(?:euros?|€|eur)", "EUR"),
    (r"(?:show|give|convert|change).*(?:pounds?|sterlin|gbp|£)", "GBP"),
    (r"(?:show|give|convert|change).*(?:\btl\b|₺|lira)", "TRY"),
]


def detect_currency_change(message: str) -> Optional[str]:
    """
    Mesajda para birimi degisikligi istegi var mi?
    Returns: 'USD', 'EUR', 'TRY', 'GBP' veya None
    """
    if not message:
        return None
    low = _normalize_turkish_chars(message.lower())
    low_orig = message.lower()

    for pattern, currency in CURRENCY_CHANGE_PATTERNS:
        pattern_norm = _normalize_turkish_chars(pattern)
        if re.search(pattern_norm, low):
            if currency:
                return currency
            # currency None ise mesajdan cikar
            return _infer_currency(message)

    # Fallback: sadece para birimi kelimesi + soru isareti
    if "?" in message or "misin" in low or "mısın" in low_orig:
        inferred = _infer_currency(message)
        if inferred:
            # Mesajda fiyat/ücret kelimesi de varsa currency change
            if any(kw in low for kw in ["fiyat", "ucret", "price", "cost"]):
                return inferred

    return None


# ===========================================================
# 3) FIYAT NIYETI ALGILAMA
# ===========================================================

PRICE_INTENT_KEYWORDS = [
    "fiyat", "ücret", "ucret", "kaç para", "kac para", "ne kadar",
    "konaklama ücreti", "konaklama ucreti",
    "gecelik", "gecelik fiyat",
    "oda fiyat", "oda ücreti", "oda ucreti",
    "en uygun", "teklif",
    "müsait", "musait", "müsaitlik", "musaitlik",
    "uygun oda", "boş oda", "bos oda",
    "price", "cost", "rate", "how much",
    "available", "availability", "vacancy",
    "cheapest", "affordable", "quote",
    # multi-language smoke support
    "цена", "стоимость", "тариф",
    "preis", "kosten", "verfügbarkeit", "verfugbarkeit",
    "precio", "coste", "tarifa", "disponibilidad",
    "prix", "coût", "cout", "tarif", "disponibilité", "disponibilite",
    "preço", "preco", "custo", "disponibilidade",
    "سعر", "الأسعار", "الاسعار", "التكلفة", "التوفر",
    "价格", "价钱", "费用", "房价", "可订", "可用", "多少钱",
    "कीमत", "मूल्य", "दर", "उपलब्धता",
]

# Karsilastirma / bilgi / varlik sorulari — fiyat akisina sokma, OpenAI'ye yonlendir
# NOT: Oda tipi isimleri (deluxe, superior, standart) tek basina exclusion
#      degildir; sadece karsilastirma kaliplariyla birlikte engellenir.
PRICE_EXCLUSION_PATTERNS_TR = [
    # Karsilastirma kaliplari
    "fiyat farkı", "fiyat farki", "fark nedir", "fark ne kadar",
    "fiyat karşılaştır", "fiyat karsilastir",
    "arasında fark", "arasindaki fark",
    "odalar arasında fiyat", "tipler arasında fiyat", "tipleri arasında fiyat",
    "hangisi daha", "hangisi ucuz", "hangisi pahalı", "hangisi pahali",
    "ne fark var", "farkı ne", "farki ne", "farkı nedir", "farki nedir",
    "oda tipleri", "oda tipi", "oda çeşit", "oda cesit",
    "oda karşılaştır", "oda karsilastir",
    "odalar arasında", "odalar arasindaki",
    # Varlik sorulari — "X var mi / varsa fiyati" kaliplari
    "varsa fiyat", "varsa ücret", "varsa ucret",
    "var mı fiyat", "var mi fiyat",
    # Otelde bulunmayan oda tipleri / ozellikler
    "aile odası", "aile odasi", "family room", "family suite",
    "bağlantılı oda", "baglantili oda", "connecting room", "adjoining room",
    "deniz manzaralı", "deniz manzarali", "sea view", "ocean view",
    "göl manzaralı", "gol manzarali", "lake view",
    "jakuzili oda", "jacuzzi room",
    # Ek ucret / dahil mi sorulari
    "ek ücret", "ek ucret", "extra charge", "additional charge",
    "dahil mi", "dahil mı", "included",
    "fiyata dahil", "fiyata dahil mi",
    # ── ODA DIŞI HİZMET SORULARI ──
    # Bu konular Elektraweb fiyat akışına girmemeli, OpenAI system prompt ile cevaplar
    "otopark", "park yeri", "vale",
    "transfer", "havalimanı", "havaalani", "shuttle",
    "spa", "masaj", "massage", "hamam", "sauna",
    "restoran", "yemek", "kahvaltı", "kahvalti",
    "minibar", "mini bar",
    "çamaşırhane", "camasirhane", "kuru temizleme", "laundry",
    "ek yatak", "extra bed", "bebek beşiği", "bebek besigi", "bebek yatağı", "cot", "crib",
    "yarım pansiyon", "yarim pansiyon", "tam pansiyon",
    "herşey dahil", "hersey dahil", "all inclusive",
    "sadece oda", "room only", "half board", "full board",
    "kapora", "depozito", "deposit",
    "erken rezervasyon", "early bird",
    "erken giriş", "erken giris", "early check-in", "early check in", "early checkin",
    "geç çıkış", "gec cikis", "late check-out", "late check out", "late checkout",
    "son dakika", "last minute",
    "peşin ödeme", "pesin odeme", "peşin indirim",
    "tekne", "boat", "aktivite", "activity",
    "pasta", "süsleme", "dekorasyon",
    "surpriz", "sürpriz", "balayi", "balayı",
    "romantik", "romantik masa", "cicek", "çiçek", "el yazisi not",
    "şarap", "şampanya", "wine", "champagne",
    "bayram", "özel gün", "ozel gun",
    "havuz", "pool", "plaj", "beach",
    "bisiklet", "bicycle", "bike",
    "wifi", "internet",
    # ── POLİTİKA / KURAL / BİLGİ SORULARI ──
    # "Fiyat" kelimesi içerse bile bunlar ODA FİYATI SORGUSU değil!
    # İptal / iade politikası
    "iptal politika", "iptal koşul", "iptal kosul", "iptal şart", "iptal sart",
    "iptal kural", "iptal hakkı", "iptal hakki",
    "ücretsiz iptal", "ucretsiz iptal", "free cancel",
    "iade politika", "iade koşul", "iade kosul", "iade kural",
    "non-refundable", "nonrefundable", "refundable",
    "esnek fiyat", "esnek tarife",
    # Ödeme politikası
    "ödeme koşul", "odeme kosul", "ödeme şekli", "odeme sekli",
    "ödeme yöntemi", "odeme yontemi", "taksit",
    "kredi kartı", "kredi karti", "nakit",
    # Vergi / KDV
    "kdv", "vergi", "tax", "vat",
    # Genel politika / kural soruları
    "politika", "policy", "koşul", "kosul", "şart", "sart",
    "kural", "rule", "terms",
    # Çocuk / bebek politikası — sadece POLİTİKA soruları, fiyat sorguları değil!
    # NOT: "2 yetişkin 1 çocuk fiyat" gibi sorgular engellenmemeli!
    "çocuk politika", "cocuk politika", "çocuk kural", "cocuk kural",
    "çocuk kabul", "cocuk kabul", "çocuk yaş", "cocuk yas",
    "bebek politika", "bebek kural",
    "child policy", "infant policy", "kids policy",
    "yaş sınırı", "yas siniri", "age limit",
    # Evcil hayvan
    "evcil hayvan", "pet", "kedi", "köpek", "kopek",
    # Sigara
    "sigara", "smoking",
    # Genel bilgi soruları (fiyat kelimesi içerebilir ama oda fiyatı değil)
    "fiyat değişir mi", "fiyat degisir mi", "fiyat değişiyor mu", "fiyat degisiyor mu",
    "fiyat artış", "fiyat artis", "fiyat garantisi", "fiyat garanti",
]

PRICE_EXCLUSION_PATTERNS_EN = [
    # Comparison patterns
    "price difference", "cost difference", "rate difference",
    "difference between", "compare", "comparison",
    "which is cheaper", "which is more expensive",
    "what's the difference", "what is the difference",
    "room types", "room type", "room categories",
    # Existence queries
    "do you have", "is there", "are there",
    # Extra charge / included queries
    "extra charge", "additional cost", "additional fee",
    "is it included", "included in the price",
    # Non-room service queries — OpenAI answers these
    "parking", "car park", "valet",
    "transfer", "airport", "shuttle",
    "spa", "massage", "sauna", "hammam",
    "restaurant", "dining", "breakfast",
    "minibar", "mini bar",
    "laundry", "dry cleaning",
    "extra bed", "cot", "crib", "baby bed",
    "half board", "full board", "all inclusive", "room only",
    "deposit", "prepay",
    "early bird", "last minute",
    "early check-in", "early check in", "early checkin",
    "late check-out", "late check out", "late checkout",
    "boat", "tour", "activity",
    "cake", "decoration", "wine", "champagne",
    "surprise", "honeymoon", "romantic", "romantic table",
    "flower", "flowers", "note card", "welcome note",
    "pool", "beach", "bicycle", "bike",
    "wifi", "internet",
    # Policy / rules / information queries
    "cancellation policy", "cancel policy", "free cancellation",
    "refund policy", "refundable", "non-refundable",
    "flexible rate", "flexible price",
    "payment method", "payment option", "installment",
    "credit card", "cash", "debit",
    "tax", "vat",
    "policy", "terms", "conditions", "rules",
    "child", "children", "infant", "kids", "age limit",
    "pet", "pets", "dog", "cat",
    "smoking", "non-smoking",
    "price change", "price guarantee", "price match",
]


def detect_price_intent(message: str) -> bool:
    """Mesajda fiyat/musaitlik niyeti var mi?

    Karşılaştırma/bilgi soruları (ör: 'fiyat farkı nedir?') hariç tutulur
    ve OpenAI'ye yönlendirilir.
    """
    if not message:
        return False
    raw_low = message.lower()
    multilingual_raw_markers = (
        "价格", "价钱", "房价", "多少钱", "总价", "总价格", "可用", "可订",
        "цена", "стоимость", "тариф",
        "سعر", "الأسعار", "الاسعار", "التكلفة",
        "कीमत", "मूल्य", "दर",
    )
    if any(k in raw_low for k in multilingual_raw_markers):
        return True
    low = _normalize_turkish_chars(message.lower())
    normalized_keywords = [_normalize_turkish_chars(k) for k in PRICE_INTENT_KEYWORDS]

    # Oda ozelligi + fiyat/musaitlik sorgularini exclusion oncesi kabul et.
    # Ornek: "14-18 Agustos 2 yetiskin havuz manzarali oda fiyati nedir?"
    if _is_single_room_feature_price_query(message):
        return True

    # Güçlü oda+fiyat/müsaitlik sorgusu: exclusion listesi bunu engellememeli.
    # Örn: "deniz manzaralı vs standart fiyat nasıl değişir?", "balkonlu oda ek ücret var mı?"
    strong_room_comparison = any(
        k in low
        for k in (
            "fiyat fark",
            "fark ne kadar",
            "fark nedir",
            "price difference",
            "fiyat nasil degisir",
            "fiyat nasıl değişir",
            "fiyat degisir",
            "değişir",
            "degisir",
            "ek ucret",
            "ek ücret",
            "extra fee",
            "additional charge",
        )
    )
    room_or_view_markers = (
        "oda", "room", "deluxe", "superior", "exclusive", "penthouse", "premium",
        "manzara", "view", "sea", "deniz", "balkon", "balcony",
    )
    availability_markers = ("musait", "müsait", "availability", "available", "var mi", "var mı")
    has_room_context = any(k in low for k in room_or_view_markers)
    has_availability_or_price = any(k in low for k in availability_markers) or any(k in low for k in normalized_keywords)
    if strong_room_comparison and has_room_context and has_availability_or_price:
        return True

    # Önce exclusion kontrolü — karşılaştırma soruları fiyat akışına girmemeli
    all_exclusions = PRICE_EXCLUSION_PATTERNS_TR + PRICE_EXCLUSION_PATTERNS_EN
    for pattern in all_exclusions:
        if _normalize_turkish_chars(pattern.lower()) in low:
            print(f"[SKIP] Fiyat akisi engellendi (karsilastirma sorusu): '{pattern}' bulundu")
            return False

    return any(kw in low for kw in normalized_keywords)


def _looks_like_price_slot_followup(message: str, history: Optional[List[Dict[str, Any]]] = None) -> bool:
    """
    Fiyat anahtar kelimesi olmasa bile, fiyat akışı içinde slot tamamlama
    mesajlarını (örn. "2 yetişkin 2 çocuk", "7 ve 8") yakalar.
    """
    if not message:
        return False
    text = message.strip()
    if not text:
        return False
    low = _normalize_turkish_chars(text.lower())
    slot_markers = (
        "yetişkin",
        "yetiskin",
        "adult",
        "çocuk",
        "cocuk",
        "child",
        "kids",
        "kisi",
        "kişi",
        "age",
        "yas",
        "yaş",
        "gece",
        "night",
        "check-in",
        "check in",
        "check-out",
        "check out",
    )
    has_slot_signal = bool(re.search(r"\d", low)) or any(m in low for m in slot_markers)
    if not has_slot_signal:
        return False

    recent_user_price_context = False
    recent_assistant_slot_prompt = False
    for item in reversed(history or []):
        role = (item.get("role") or "").lower()
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        norm_content = _normalize_turkish_chars(content.lower())
        if role == "user" and detect_price_intent(content):
            recent_user_price_context = True
            break
        if role == "assistant" and (
            "eksik" in norm_content
            or "cocuk yasi" in norm_content
            or "çocuk yaşı" in content.lower()
            or "giris-cikis" in norm_content
            or "giriş-çıkış" in content.lower()
            or "kisi sayisi" in norm_content
            or "kişi sayısı" in content.lower()
            or "check-in" in norm_content
            or "check-out" in norm_content
        ):
            recent_assistant_slot_prompt = True
    return recent_user_price_context or recent_assistant_slot_prompt


def detect_handoff_price(message: str) -> Tuple[bool, str]:
    """Elektraweb'in cevaplayamayacagi fiyat sorusu mu?"""
    if not message:
        return False, ""
    low = _normalize_turkish_chars(message.lower())
    room_count = _extract_room_count_from_message(message)
    for kw in HANDOFF_PRICE_KEYWORDS_TR + HANDOFF_PRICE_KEYWORDS_EN:
        kw_norm = _normalize_turkish_chars(kw.lower())
        if kw_norm in low:
            # 2-3 odali normal talepleri handoff'a atma.
            if room_count in (2, 3):
                continue
            return True, kw.strip()
    return False, ""

_MONTH_TR = {1:"Ocak",2:"Şubat",3:"Mart",4:"Nisan",5:"Mayıs",6:"Haziran",7:"Temmuz",8:"Ağustos",9:"Eylül",10:"Ekim",11:"Kasım",12:"Aralık"}
_MONTH_EN = {1:"January",2:"February",3:"March",4:"April",5:"May",6:"June",7:"July",8:"August",9:"September",10:"October",11:"November",12:"December"}

def _parse_mmdd(mmdd: str) -> Tuple[int, int]:
    try:
        m, d = mmdd.split("-", 1)
        return int(m), int(d)
    except Exception:
        # fallback: April 1
        return (4, 1)

def _fmt_mmdd(mmdd: str, lang: str) -> str:
    m, d = _parse_mmdd(mmdd)
    if lang == "en":
        return f"{_MONTH_EN.get(m, str(m))} {d}"
    return f"{d} {_MONTH_TR.get(m, str(m))}"

def _fmt_iso_date(iso_date: str, lang: str) -> str:
    try:
        d = datetime.strptime(iso_date, "%Y-%m-%d")
        if lang == "en":
            return f"{_MONTH_EN.get(d.month, str(d.month))} {d.day} {d.year}"
        return f"{d.day} {_MONTH_TR.get(d.month, str(d.month))} {d.year}"
    except Exception:
        return iso_date

def _is_out_of_season(from_date: str, to_date: str) -> bool:
    try:
        d1 = datetime.strptime(from_date, "%Y-%m-%d").date()
        d2 = datetime.strptime(to_date, "%Y-%m-%d").date()
    except Exception:
        return False

    # yıl aşan aralıkları güvenli tarafta sezon dışı kabul edelim
    if d1.year != d2.year:
        return True

    season_start_mmdd, season_end_mmdd = _season_mmdd()
    sm, sd = _parse_mmdd(season_start_mmdd)
    em, ed = _parse_mmdd(season_end_mmdd)
    season_start = date(d1.year, sm, sd)
    season_end   = date(d1.year, em, ed)

    # check-out günü sabahı da kabul edilebilir diye +1 gün tolerans
    allowed_checkout = season_end + timedelta(days=1)

    return not (d1 >= season_start and d2 <= allowed_checkout)

def _build_out_of_season_reply(lang: str, from_date: str, to_date: str) -> str:
    season_start_mmdd, season_end_mmdd = _season_mmdd()
    season_str = f"{_fmt_mmdd(season_start_mmdd, lang)} - {_fmt_mmdd(season_end_mmdd, lang)}"
    req_str = f"{_fmt_iso_date(from_date, lang)} - {_fmt_iso_date(to_date, lang)}"
    if lang == "en":
        return (
            f"Our hotel operates between {season_str}. "
            f"Your requested dates ({req_str}) are outside our season. "
            f"If you share an alternative date range within the season, I can check availability and prices right away."
        )
    return (
        f"Otelimiz {season_str} tarihleri arasında hizmet vermektedir. "
        f"Paylaştığınız tarihler ({req_str}) sezon dışındadır. "
        f"Sezon içinden alternatif tarih paylaşırsanız hemen müsaitlik ve fiyat kontrol edebilirim."
    )

# ===========================================================
# 4) DOGAL DIL BILGI CIKARMA
# ===========================================================

def _extract_night_count(message: str) -> Optional[int]:
    low = _normalize_turkish_chars(message.lower())
    m = re.search(r"(\d+)\s*(?:gece|night)", low)
    if m:
        return int(m.group(1))
    return None


def _extract_dates_smart(message: str) -> Tuple[Optional[str], Optional[str]]:
    if not message:
        return None, None

    dates = _extract_all_dates(message)
    if len(dates) >= 2:
        return dates[0], dates[1]

    low = message.lower()
    low_norm = _normalize_turkish_chars(low)
    today = datetime.now()

    bugun_words = ["bugun", "bugün", "today"]
    yarin_words = ["yarin", "yarın", "tomorrow"]

    has_bugun = any(w in low for w in bugun_words)
    has_yarin = any(w in low for w in yarin_words)

    if has_bugun and has_yarin:
        return today.strftime("%Y-%m-%d"), (today + timedelta(days=1)).strftime("%Y-%m-%d")

    night_count = _extract_night_count(message)
    if has_bugun and night_count:
        return today.strftime("%Y-%m-%d"), (today + timedelta(days=night_count)).strftime("%Y-%m-%d")

    if has_yarin and night_count:
        yarin = today + timedelta(days=1)
        return yarin.strftime("%Y-%m-%d"), (yarin + timedelta(days=night_count)).strftime("%Y-%m-%d")

    if has_bugun and ("giris" in low_norm or "check" in low_norm):
        return today.strftime("%Y-%m-%d"), (today + timedelta(days=1)).strftime("%Y-%m-%d")

    if has_yarin and ("giris" in low_norm or "check" in low_norm):
        yarin = today + timedelta(days=1)
        return yarin.strftime("%Y-%m-%d"), (yarin + timedelta(days=1)).strftime("%Y-%m-%d")

    if len(dates) == 1 and night_count:
        try:
            d = datetime.strptime(dates[0], "%Y-%m-%d")
            return dates[0], (d + timedelta(days=night_count)).strftime("%Y-%m-%d")
        except Exception:
            pass

    if len(dates) == 1:
        return dates[0], None

    return None, None


def _extract_guests_smart(message: str) -> Tuple[Optional[int], List[int]]:
    if not message:
        return None, []

    adult = _extract_adult_count(message)
    child_ages = _extract_child_ages(message)
    low = _normalize_turkish_chars(message.lower())

    if adult is None:
        if any(kw in low for kw in ["cift kisilik", "cift kisi", "double room", "double"]):
            adult = 2
        elif any(kw in low for kw in ["tek kisi", "tek kisilik", "single"]):
            adult = 1
        elif "aile" in low or "family" in low:
            adult = 2
        else:
            m = re.search(r"^(\d{1,2})$", message.strip())
            if m:
                val = int(m.group(1))
                if 1 <= val <= 10:
                    adult = val

    return adult, child_ages


def _extract_child_count(message: str, child_ages: Optional[List[int]] = None) -> Optional[int]:
    if not message:
        inferred = len(child_ages or [])
        return inferred or None

    low = _normalize_turkish_chars(message.lower())
    m = re.search(r"\b(\d+)\s*(?:cocuk|child|children|kid|kids|bebek|baby|infant)\b", low)
    if m:
        try:
            cnt = int(m.group(1))
            if 0 <= cnt <= 10:
                return cnt
        except Exception:
            pass

    if any(w in low for w in ["cocuk", "child", "children", "kid", "kids", "bebek", "baby", "infant"]):
        ages_len = len(child_ages or [])
        if ages_len > 0:
            return ages_len
        return None

    inferred = len(child_ages or [])
    return inferred or None


def _has_child_mention(message: str) -> bool:
    low = _normalize_turkish_chars(message.lower())
    child_words = ["cocuk", "child", "children", "kid", "baby", "bebek", "infant"]
    return any(w in low for w in child_words)


def _looks_like_guest_count_payload(message: str) -> bool:
    """Mesaj kişi sayısı payload'ı mı? (örn: '2 yetişkin 2 çocuk')"""
    low = _normalize_turkish_chars((message or "").lower())
    return bool(
        re.search(r"\b\d+\s*(?:yetiskin|adult|adults)\b", low)
        or re.search(r"\b\d+\s*(?:cocuk|child|children|kid|kids|bebek|baby|infant)\b", low)
    )


# ===========================================================
# 5) FLOW MESAJ URETME
# ===========================================================

def _build_ack_message(flow_data: dict, lang: str) -> str:
    parts = []
    if flow_data.get("from_date") and flow_data.get("to_date"):
        from app.services.elektraweb_booking_service import (
            _format_date_range_tr, _format_date_range_en, _calculate_nights,
        )
        nights = _calculate_nights(flow_data["from_date"], flow_data["to_date"])
        if lang == "en":
            dr = _format_date_range_en(flow_data["from_date"], flow_data["to_date"])
            parts.append(f"{dr} ({nights} night{'s' if nights > 1 else ''})")
        else:
            dr = _format_date_range_tr(flow_data["from_date"], flow_data["to_date"])
            parts.append(f"{dr} ({nights} gece)")

    if flow_data.get("adult_count"):
        if lang == "en":
            parts.append(f"{flow_data['adult_count']} adult{'s' if flow_data['adult_count'] > 1 else ''}")
        else:
            parts.append(f"{flow_data['adult_count']} yetişkin")

    if flow_data.get("child_ages"):
        ages_str = ", ".join(str(a) for a in flow_data["child_ages"])
        if lang == "en":
            parts.append(f"children (ages: {ages_str})")
        else:
            parts.append(f"çocuk (yaş: {ages_str})")

    if not parts:
        return ""
    joined = ", ".join(parts)
    return f"✅ {joined} — not ettim.\n\n" if lang == "tr" else f"✅ Noted: {joined}.\n\n"


def _ask_dates_message(lang: str, ack: str = "") -> str:
    if lang == "en":
        return (
            f"{ack}"
            "To check prices, please share your check-in and check-out dates.\n"
            '(e.g., "June 4-9", "tomorrow for 3 nights", "July 15 to July 20")'
        )
    return (
        f"{ack}"
        "Fiyat bilgisi için giriş ve çıkış tarihlerinizi paylaşır mısınız?\n"
        '(Örn: "4-9 Haziran", "yarın giriş 3 gece", "15 Temmuz - 20 Temmuz")'
    )


def _extract_room_count_from_message(message: str) -> int:
    low = _normalize_turkish_chars((message or "").lower())
    m = re.search(r"\b(\d+)\s*(?:oda|room|rooms)\b", low)
    if m:
        try:
            return max(1, int(m.group(1)))
        except Exception:
            return 1
    if "iki oda" in low or "2 oda" in low:
        return 2
    if "uc oda" in low or "3 oda" in low:
        return 3
    return 1


def _ask_guests_message(lang: str, ack: str = "", room_count: int = 1) -> str:
    if room_count > 1:
        if lang == "en":
            return (
                f"{ack}"
                f"Great, I can prepare pricing for {room_count} rooms.\n"
                "Could you share guest details separately for each room/family?\n"
                '(e.g., "Room 1: 2 adults | Room 2: 2 adults + 2 children (ages 3 and 10)")'
            )
        return (
            f"{ack}"
            f"Memnuniyetle, {room_count} oda için fiyat hazırlayabilirim.\n"
            "Lütfen her oda/aile için kişi bilgilerini ayrı ayrı paylaşır mısınız?\n"
            '(Örn: "1. Oda: 2 yetişkin | 2. Oda: 2 yetişkin + 2 çocuk (3 ve 10 yaş)")'
        )
    if lang == "en":
        return (
            f"{ack}"
            "How many guests will be staying?\n"
            '(e.g., "2 adults", "2 adults + 1 child age 6")'
        )
    return (
        f"{ack}"
        "Kaç kişi konaklayacak?\n"
        '(Örn: "2 yetişkin", "2 yetişkin + 1 çocuk 6 yaş")'
    )


def _ask_child_ages_message(lang: str, child_count: int, ack: str = "") -> str:
    if lang == "en":
        return (
            f"{ack}"
            f"You mentioned {child_count} child(ren). Could you share their age(s)?\n"
            '(e.g., "6 years old", "3 and 8 years old")'
        )
    return (
        f"{ack}"
        f"{child_count} çocuk belirttiniz. Yaşlarını paylaşır mısınız?\n"
        '(Örn: "6 yaşında", "3 ve 8 yaşında")'
    )


def _ask_child_count_message(lang: str, ack: str = "") -> str:
    if lang == "en":
        return (
            f"{ack}"
            "You mentioned children. Could you share how many children will stay?\n"
            '(e.g., "1 child", "2 children")'
        )
    return (
        f"{ack}"
        "Çocuk belirttiniz. Kaç çocuk konaklayacak paylaşır mısınız?\n"
        '(Örn: "1 çocuk", "2 çocuk")'
    )


def _ask_checkout_message(lang: str, from_date: str, ack: str = "") -> str:
    from app.services.elektraweb_booking_service import MONTHS_TR_REVERSE, MONTHS_EN_REVERSE
    try:
        d = datetime.strptime(from_date, "%Y-%m-%d")
        if lang == "en":
            date_str = f"{MONTHS_EN_REVERSE[d.month]} {d.day}"
        else:
            date_str = f"{d.day} {MONTHS_TR_REVERSE[d.month]}"
    except Exception:
        date_str = from_date
    if lang == "en":
        return f"{ack}Check-in: {date_str}. What is your check-out date?\n(e.g., \"June 9\", \"3 nights\")"
    return f"{ack}Giriş: {date_str}. Çıkış tarihiniz ne olacak?\n(Örn: \"9 Haziran\", \"3 gece\")"


# ===========================================================
# 6) ANA HANDLER
# ===========================================================
def _is_quiet_room_request(text: str) -> bool:
    low = _normalize_turkish_chars((text or "").lower())
    return any(k in low for k in ("sessiz", "sakin", "quiet", "no noise", "less noise"))


def _is_breakfast_fee_policy_question(text: str) -> bool:
    low = _normalize_turkish_chars((text or "").lower())
    has_breakfast = ("kahvalt" in low) or ("breakfast" in low)
    has_policy_probe = any(
        k in low
        for k in (
            "dahil mi",
            "dahil",
            "included",
            "ek ucret",
            "ek ücret",
            "extra charge",
            "additional charge",
            "kisi basi",
            "kişi başı",
            "per person",
        )
    )
    return has_breakfast and has_policy_probe


def _is_policy_interruption_question(text: str) -> bool:
    """
    Aktif fiyat slot-filling sırasında gelen politika/bilgi sorularını tespit et.
    Bu sorular fiyat akışını override etmemeli; genel bilgi katmanına paslanmalı.
    """
    low = _normalize_turkish_chars((text or "").lower())
    if not low:
        return False

    if _is_breakfast_fee_policy_question(text):
        return True

    markers = (
        "child policy", "kids policy", "infant policy",
        "cocuk politika", "çocuk politika", "cocuk kural", "çocuk kural",
        "does the child pay", "discounted rate", "full price",
        "extra bed", "ek yatak", "nightly fee", "gecelik ucret", "gecelik ücret",
        "check-in", "check in", "check-out", "check out",
        "gece gec", "gece geç", "late check-in", "late check in",
        "erken giris", "erken giriş", "gec cikis", "geç çıkış",
        "payment method", "odeme yontemi", "ödeme yöntemi",
        "odeme linki", "ödeme linki", "payment link",
        "deposit", "depozito", "kapora",
        "otopark", "parking", "wifi", "wi-fi", "kahvalti", "kahvaltı",
        "rezervasyonu baslatalim", "rezervasyonu başlatalım", "rezervasyon baslatalim", "rezervasyon başlatalım",
        "book now", "start reservation", "start booking",
        "surpriz", "sürpriz", "balayi", "balayı",
        "romantik", "romantic", "special arrangement",
        "cicek", "çiçek", "flower", "note card", "welcome note",
        "gluten", "glutensiz", "gluten-free", "gluten free",
    )
    return any(k in low for k in markers)


def _is_single_room_feature_price_query(text: str) -> bool:
    """
    Tek oda oda-ozelligi/fiyat sorgusu:
    Ornek: "havuz manzarali oda fiyati", "pool view room price"
    """
    low = _normalize_turkish_chars((text or "").lower())
    if not low:
        return False

    feature_markers = (
        "havuz manzara",
        "pool view",
        "deniz manzara",
        "sea view",
        "sokak manzara",
        "street view",
        "city view",
        "standart oda",
        "standard room",
        "jakuzi",
        "jacuzzi",
    )
    price_or_availability_markers = (
        "fiyat",
        "price",
        "ucret",
        "ücret",
        "musait",
        "müsait",
        "availability",
        "available",
        "fark",
        "difference",
    )
    multi_room_markers = (
        "2 oda",
        "iki oda",
        "3 oda",
        "uc oda",
        "üç oda",
        "room 1",
        "room 2",
        "1. oda",
        "2. oda",
        "biri",
        "digeri",
        "diğeri",
        "one room",
        "other room",
        "two rooms",
        "three rooms",
    )

    has_feature = any(k in low for k in feature_markers)
    has_price_or_availability = any(k in low for k in price_or_availability_markers)
    has_room_word = ("oda" in low) or ("room" in low)
    has_multi_room = any(k in low for k in multi_room_markers)
    return has_feature and has_price_or_availability and has_room_word and not has_multi_room


def _has_room_preference_hint(text: str) -> bool:
    low = _normalize_turkish_chars((text or "").lower())
    if not low:
        return False
    markers = (
        "havuz manzara",
        "pool view",
        "deniz manzara",
        "sea view",
        "sokak manzara",
        "street view",
        "city view",
        "standart oda",
        "standard room",
        "jakuzi",
        "jacuzzi",
        "sessiz oda",
        "quiet room",
    )
    return any(k in low for k in markers)


def _build_breakfast_fee_policy_reply(lang: str) -> str:
    if lang == "en":
        return (
            "Our concept includes breakfast. We also have a restaurant for lunch and dinner, "
            "but lunch and dinner are not included in accommodation price. "
            "Our pricing is room-based, not per person. "
            "If you are asking room pricing, please share your date range and guest count and I will provide a quote."
        )
    return (
        "Konseptimiz kahvaltı dahildir ayrıca akşam ve öğlen yemeği hizmeti veren restoranımız mevcuttur fakat akşam ve öğlen yemeği konaklama ücretine dahil değildir. "
        "Fiyatlarımız kişi başı değil, oda bazlıdır. "
        "Kişi başı ek ücret fiyatını eğer oda için sorduysanız, öğrenmek istediğiniz tarih aralığı ve kişi sayısını söyleyiniz ve sizlere fiyat paylaşımı yapalım."
    )


def _append_context_hint(flow_data: Dict[str, Any], message: str) -> None:
    """
    Fiyat akışında kullanıcı niyetini (örn. standart oda, TL vb.) adım adım koru.
    Böylece tarih/kişi tamamlayıcı mesajlarında gelen tercihler kaybolmaz.
    """
    txt = (message or "").strip()
    if not txt:
        return
    existing = str(flow_data.get("context_hint") or "").strip()
    if not existing:
        flow_data["context_hint"] = txt[:1200]
        return
    low_existing = _normalize_turkish_chars(existing.lower())
    low_txt = _normalize_turkish_chars(txt.lower())
    if low_txt and low_txt in low_existing:
        return
    merged = f"{existing} | {txt}"
    flow_data["context_hint"] = merged[-1200:]


async def handle_price_flow(
    phone: str,
    message: str,
    history: Optional[List[Dict[str, Any]]] = None,
    lang: str = "tr",
) -> Optional[Dict[str, Any]]:
    """
    Akilli fiyat akisi handler'i.
    Returns None → mesaj fiyat akisina ait degil.
    Returns dict → {"reply", "status", "log", "is_price_template"}
    """
    if not phone or not message:
        return None

    hotel_id = (os.getenv("ELEKTRA_HOTEL_ID") or "21966").strip()

    # Kahvalti dahil mi / kisi basi ek ucret gibi politika sorulari fiyat sorgusuna dusmemeli.
    if _is_breakfast_fee_policy_question(message):
        return {
            "reply": _build_breakfast_fee_policy_reply(lang),
            "status": "price_policy_info",
            "log": "breakfast_policy_info",
            "is_price_template": False,
        }

    # ----- A) PARA BIRIMI DEGISIKLIGI KONTROLU (EN YUKSEK ONCELIK) -----
    requested_currency = detect_currency_change(message)
    if requested_currency:
        if not _is_currency_enabled(requested_currency):
            return {
                "reply": _DISABLED_CURRENCY_REPLY,
                "status": "handoff",
                "log": f"currency_disabled:{requested_currency}",
                "is_price_template": False,
                "handoff_reason": "price_currency_disabled",
            }
        last_q = get_last_query(phone)
        if last_q and last_q.get("from_date") and last_q.get("adult_count"):
            # Son sorgu var — sadece currency degistirip tekrar sor
            print(f"💱 Currency re-query: {phone} → {requested_currency}")
            last_q["currency"] = requested_currency
            return await _query_elektraweb(phone, last_q, hotel_id, currency_override=requested_currency)
        # Son sorgu yok — normal akisa dus (tarih/kisi soracak)

    # ----- A.1) Oda adedi/musaitlik sorusu (Elektra availability'den adet) -----
    if _is_room_stock_query(message):
        stock_reply = await _handle_room_stock_query(phone=phone, message=message, lang=lang, hotel_id=hotel_id)
        if stock_reply is not None:
            return stock_reply

    # ----- B) Aktif flow var mi? -----
    flow = get_price_flow(phone)
    if flow and flow.get("state") and flow["state"] != PriceFlowState.IDLE:
        return await _process_active_flow(phone, message, flow, lang, hotel_id)

    # ----- C) Yeni fiyat niyeti var mi? -----
    if not detect_price_intent(message):
        if not _looks_like_price_slot_followup(message, history):
            return None

    # ----- D) Handoff gerektiren sorusu mu? -----
    is_handoff, handoff_reason = detect_handoff_price(message)
    if is_handoff:
        return {
            "reply": "",
            "status": "handoff",
            "log": f"price_handoff: {handoff_reason}",
            "is_price_template": False,
            "handoff_reason": handoff_reason,
        }

    # ----- E) Yeni flow baslat -----
    return await _start_new_flow(phone, message, lang, hotel_id, history=history)


async def _handle_room_stock_query(phone: str, message: str, lang: str, hotel_id: str) -> Optional[Dict[str, Any]]:
    room_key = _extract_room_key_for_stock_query(message)
    if not room_key:
        return None

    from_date, to_date = _extract_dates_smart(message)
    adult, child_ages = _extract_guests_smart(message)
    child_count = _extract_child_count(message, child_ages)
    last_q = get_last_query(phone) or {}

    if not from_date:
        from_date = last_q.get("from_date")
    if not to_date:
        to_date = last_q.get("to_date")
    if adult is None:
        adult = last_q.get("adult_count")
    if not child_ages:
        lq_ages = last_q.get("child_ages")
        if isinstance(lq_ages, list):
            child_ages = lq_ages

    if not from_date or not to_date:
        reply = (
            "Oda adedini net kontrol edebilmem için giriş ve çıkış tarihini paylaşır mısınız?"
            if lang == "tr"
            else "To check exact room count, could you share check-in and check-out dates?"
        )
        return {"reply": reply, "status": "price_flow", "log": "room_stock_missing_dates", "is_price_template": False}

    if not adult:
        reply = (
            "Oda adedini net kontrol edebilmem için yetişkin sayısını da paylaşır mısınız?"
            if lang == "tr"
            else "Could you also share the number of adults so I can check exact room count?"
        )
        return {"reply": reply, "status": "price_flow", "log": "room_stock_missing_guests", "is_price_template": False}

    room_type_id_to_key: Dict[int, str] = {}
    cached_offers: List[Dict[str, Any]] = []
    try:
        from app.services.booking_flow_service import get_price_offers
        cached = get_price_offers(phone) or {}
        cached_offers = list(cached.get("offers") or [])
        for offer in cached_offers:
            try:
                rid = int(offer.get("room-type-id") or 0)
            except Exception:
                rid = 0
            if rid <= 0:
                continue
            room_info = None
            try:
                from app.services.elektraweb_booking_service import _normalize_room_type
                room_info = _normalize_room_type(offer.get("room-type", "") or "")
            except Exception:
                room_info = None
            if room_info and room_info.get("key"):
                room_type_id_to_key[rid] = room_info["key"]
    except Exception:
        room_type_id_to_key = {}

    # 1) Once son fiyat cevap cache'indeki offer'lardan oda adedi cikarmayi dene.
    cached_count = _extract_stock_from_cached_offers(cached_offers, room_key=room_key)
    if cached_count is not None:
        room_label = _ROOM_LABEL_TR.get(room_key, room_key)
        if lang == "tr":
            reply = (
                f"{from_date} - {to_date} tarihleri arasında "
                f"{room_label} için {int(cached_count)} adet müsait oda görünmektedir."
            )
        else:
            reply = (
                f"For {from_date} - {to_date}, there are currently {int(cached_count)} {room_label} room(s) available."
            )
        return {"reply": reply, "status": "price_room_stock_result", "log": "room_stock_ok_cached_offers", "is_price_template": False}

    # 2) Cache'ten bulunamazsa bookingapi /availability ile canlı stok hesapla.
    try:
        stocks = await fetch_room_stock_by_type_from_availability(
            hotel_id=hotel_id,
            from_date=from_date,
            to_date=to_date,
            adult=int(adult),
            currency=(last_q.get("currency") or "EUR"),
            child_ages=child_ages or None,
            room_type_id_to_key=room_type_id_to_key,
            timeout_sec=20,
        )
    except Exception as e:
        log = f"room_stock_query_failed: {type(e).__name__}: {str(e)[:250]}"
        return {
            "reply": _technical_price_error_reply(lang),
            "status": "handoff",
            "log": log,
            "is_price_template": False,
            "handoff_reason": "fiyat_sistemi_hatasi",
        }

    count = int(stocks.get(room_key, 0))
    room_label = _ROOM_LABEL_TR.get(room_key, room_key)
    if lang == "tr":
        reply = (
            f"{from_date} - {to_date} tarihleri arasında "
            f"{room_label} için {count} adet müsait oda görünmektedir."
        )
    else:
        reply = (
            f"For {from_date} - {to_date}, there are currently {count} {room_label} room(s) available."
        )
    return {"reply": reply, "status": "price_room_stock_result", "log": "room_stock_ok", "is_price_template": False}


async def _start_new_flow(
    phone: str,
    message: str,
    lang: str,
    hotel_id: str,
    history: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    from_date, to_date = _extract_dates_smart(message)
    adult, child_ages = _extract_guests_smart(message)
    child_count = _extract_child_count(message, child_ages)
    room_count = _extract_room_count_from_message(message)
    room_groups = _extract_multi_room_guest_groups(message) if room_count > 1 else []
    has_child = _has_child_mention(message)
    currency = _infer_currency(message)
    has_user_slot_payload = bool(from_date and to_date and adult is not None)

    # 0) Aynı konuşmada kullanıcı "fiyat verir misin?" dediğinde, son bilinen parametrelerden tamamla
    last_q = get_last_query(phone)
    allow_last_query_backfill = bool(
        detect_price_intent(message)
        or detect_currency_change(message)
        or _looks_like_price_slot_followup(message, history)
    )
    if last_q and allow_last_query_backfill:
        if not from_date:
            from_date = last_q.get("from_date")
        if not to_date:
            to_date = last_q.get("to_date")
        if adult is None:
            adult = last_q.get("adult_count")
        if not child_ages:
            lq_ages = last_q.get("child_ages")
            if isinstance(lq_ages, list):
                child_ages = lq_ages
        if not child_count:
            lq_child_count = last_q.get("child_count")
            if isinstance(lq_child_count, int):
                child_count = lq_child_count
        if not currency:
            currency = last_q.get("currency")
        if not room_count:
            room_count = int(last_q.get("room_count") or 1)

    # Kisa takip sorularinda ("fiyat bilgisini verir misiniz") onceki oda tercihlerini
    # koru; ancak yeni mesajda acik tercih varsa onu esas al.
    context_hint_seed = message[:1200]
    if last_q and not _has_room_preference_hint(message) and not has_user_slot_payload:
        prev_pref_hint = str(last_q.get("request_context_hint") or "").strip()
        if prev_pref_hint and _has_room_preference_hint(prev_pref_hint):
            context_hint_seed = f"{prev_pref_hint} | {message}"[-1200:]

    if room_count > 1 and room_groups:
        child_ages = []
        has_child = False
        child_count = 0
    elif child_ages:
        has_child = True
        if not child_count:
            child_count = len(child_ages)

    # 1) Flow persistence kaçarsa bile, son 10 USER mesajından tarih/kişi bilgisini geri doldur
    if history and (not from_date or not to_date or adult is None or (has_child and not child_ages)):
        for h in reversed(history[-10:]):
            if (h.get("role") or "").lower() != "user":
                continue
            txt = h.get("content") or ""
            if not txt:
                continue

            if not from_date or not to_date:
                fd, td = _extract_dates_smart(txt)
                if fd and not from_date:
                    from_date = fd
                if td and not to_date:
                    to_date = td

            if adult is None or (has_child and not child_ages):
                a, ages = _extract_guests_smart(txt)
                if adult is None and a:
                    adult = a
                if ages and not child_ages:
                    child_ages = ages
                if not child_count:
                    cc = _extract_child_count(txt, ages)
                    if cc:
                        child_count = cc

            if _has_child_mention(txt):
                has_child = True
            if child_ages:
                has_child = True
                if not child_count:
                    child_count = len(child_ages)

            if from_date and to_date and adult is not None and (not (has_child and not child_ages)):
                break

    # Aktif child baglami varken kullanici sadece "7 ve 8" gibi sayi yazarsa
    # bu sayilari yas olarak kabul et; aksi halde ayni soruyu tekrar sorup loop olusuyor.
    if (
        has_child
        and not child_ages
        and not _has_child_mention(message)
        and not _looks_like_guest_count_payload(message)
    ):
        inline_ages = [int(n) for n in re.findall(r"\d+", message) if 0 <= int(n) <= 17]
        if inline_ages:
            child_ages = inline_ages[:4]
            if not child_count:
                child_count = len(child_ages)

    flow_data: Dict[str, Any] = {
        "lang": lang,
        "original_question": message[:500],
        "context_hint": context_hint_seed,
        "from_date": from_date,
        "to_date": to_date,
        "adult_count": adult,
        "room_count": room_count,
        "room_groups": room_groups,
        "child_ages": child_ages if child_ages else [],
        "child_mentioned": has_child,
        "child_count": int(child_count or 0),
    }
    if currency:
        flow_data["currency"] = currency
        if not _is_currency_enabled(currency):
            clear_price_flow(phone)
            return {
                "reply": _DISABLED_CURRENCY_REPLY,
                "status": "handoff",
                "log": f"currency_disabled:{currency}",
                "is_price_template": False,
                "handoff_reason": "price_currency_disabled",
            }

    missing = _get_missing_fields(flow_data)
    if not missing:
        return await _query_elektraweb(phone, flow_data, hotel_id)

    return _ask_next_missing(phone, flow_data, missing, lang)

async def _process_active_flow(
    phone: str, message: str, flow: Dict[str, Any], lang: str, hotel_id: str,
) -> Dict[str, Any]:
    state = flow.get("state", PriceFlowState.IDLE)
    flow_data = flow.get("data", {})
    incoming_lang = (lang or "").strip().lower()
    flow_lang = str(flow_data.get("lang") or "").strip().lower()
    if incoming_lang:
        lang = incoming_lang
        if flow_lang != incoming_lang:
            flow_data["lang"] = incoming_lang
            try:
                save_price_flow(phone, state, flow_data)
            except Exception:
                pass
    else:
        lang = flow_lang or "tr"

    msg_lower = message.lower().strip()

    if msg_lower in ["iptal", "vazgeç", "vazgec", "cancel", "stop", "dur"]:
        clear_price_flow(phone)
        reply = "Fiyat sorgusu iptal edildi. Size nasıl yardımcı olabilirim?" if lang == "tr" else "Price inquiry cancelled. How can I help you?"
        return {"reply": reply, "status": "price_flow_cancelled", "log": None, "is_price_template": False}

    # Tek oda ozellik/fiyat sorusu geldiyse (örn. havuz manzarali oda),
    # multi-room loop'a sapmadan mevcut tarih/kisi baglamiyla direkt fiyatla.
    if state == PriceFlowState.ASK_GUESTS and _is_single_room_feature_price_query(message):
        flow_data["room_count"] = 1
        flow_data["room_groups"] = []
        missing = _get_missing_fields(flow_data)
        if not missing:
            return await _query_elektraweb(phone, flow_data, hotel_id)
        ack = _build_ack_message(flow_data, lang)
        return _ask_next_missing(phone, flow_data, missing, lang, ack=ack)

    # Aktif flow sırasında politika/bilgi sorusunu slot-filling'e zorlamadan
    # bir sonraki katmanlara bırak (local/openai). Flow state korunur.
    if _is_policy_interruption_question(message):
        return None

    if state == PriceFlowState.ASK_DATES:
        return await _handle_dates_response(phone, message, flow_data, lang, hotel_id)
    elif state == PriceFlowState.ASK_GUESTS:
        return await _handle_guests_response(phone, message, flow_data, lang, hotel_id)
    elif state == PriceFlowState.ASK_CHILD_AGES:
        return await _handle_child_ages_response(phone, message, flow_data, lang, hotel_id)

    clear_price_flow(phone)
    return None


async def _handle_dates_response(
    phone: str, message: str, flow_data: Dict[str, Any], lang: str, hotel_id: str,
) -> Dict[str, Any]:
    _append_context_hint(flow_data, message)
    currency_new = _infer_currency(message)
    if currency_new:
        flow_data["currency"] = currency_new

    from_date, to_date = _extract_dates_smart(message)
    night_count = _extract_night_count(message)

    if from_date and not to_date and night_count:
        try:
            d = datetime.strptime(from_date, "%Y-%m-%d")
            to_date = (d + timedelta(days=night_count)).strftime("%Y-%m-%d")
        except Exception:
            pass

    if not from_date and flow_data.get("from_date"):
        from_date = flow_data["from_date"]
        if not to_date and night_count:
            try:
                d = datetime.strptime(from_date, "%Y-%m-%d")
                to_date = (d + timedelta(days=night_count)).strftime("%Y-%m-%d")
            except Exception:
                pass

    # Ayni mesajda kisi bilgisi de olabilir
    adult_new, child_ages_new = _extract_guests_smart(message)
    child_count_new = _extract_child_count(message, child_ages_new)
    if adult_new:
        flow_data["adult_count"] = adult_new
    if child_ages_new:
        flow_data["child_ages"] = child_ages_new
    if child_count_new is not None:
        flow_data["child_count"] = int(child_count_new)
    if _has_child_mention(message):
        flow_data["child_mentioned"] = True

    if from_date:
        flow_data["from_date"] = from_date
    if to_date:
        flow_data["to_date"] = to_date
            # ✅ Sezon dışıysa akışı kes
    if flow_data.get("from_date") and flow_data.get("to_date") and _is_out_of_season(flow_data["from_date"], flow_data["to_date"]):
        clear_price_flow(phone)
        reply = _build_out_of_season_reply(lang, flow_data["from_date"], flow_data["to_date"])
        return {"reply": reply, "status": "info_out_of_season", "log": "out_of_season", "is_price_template": False}


    if not flow_data.get("from_date") or not flow_data.get("to_date"):
        if flow_data.get("from_date") and not flow_data.get("to_date"):
            save_price_flow(phone, PriceFlowState.ASK_DATES, flow_data)
            reply = _ask_checkout_message(lang, flow_data["from_date"])
            return {"reply": reply, "status": "price_flow", "log": None, "is_price_template": False}

        save_price_flow(phone, PriceFlowState.ASK_DATES, flow_data)
        prefix = "Tarihleri anlayamadım. " if lang == "tr" else "I couldn't understand the dates. "
        reply = prefix + _ask_dates_message(lang)
        return {"reply": reply, "status": "price_flow", "log": None, "is_price_template": False}

    missing = _get_missing_fields(flow_data)
    if not missing:
        return await _query_elektraweb(phone, flow_data, hotel_id)

    ack = _build_ack_message(flow_data, lang)
    return _ask_next_missing(phone, flow_data, missing, lang, ack=ack)


async def _handle_guests_response(
    phone: str, message: str, flow_data: Dict[str, Any], lang: str, hotel_id: str,
) -> Dict[str, Any]:
    _append_context_hint(flow_data, message)
    currency_new = _infer_currency(message)
    if currency_new:
        flow_data["currency"] = currency_new

    room_count = int(flow_data.get("room_count") or 1)

    if room_count > 1:
        groups = _extract_multi_room_guest_groups(message)
        if groups:
            flow_data["room_groups"] = groups
        if groups and len(groups) < room_count:
            save_price_flow(phone, PriceFlowState.ASK_GUESTS, flow_data)
            reply = (
                f"{room_count} oda için her oda/aile bilgisini ayrı ayrı yazabilir misiniz?\n"
                '(Örn: "1. Oda: 2 yetişkin | 2. Oda: 2 yetişkin + 2 çocuk (3 ve 10 yaş)")'
                if lang == "tr"
                else (
                    f"Could you share guest details separately for all {room_count} rooms/families?\n"
                    '(e.g., "Room 1: 2 adults | Room 2: 2 adults + 2 children (ages 3 and 10)")'
                )
            )
            return {"reply": reply, "status": "price_flow", "log": None, "is_price_template": False}

        if len(groups) >= room_count and flow_data.get("from_date") and flow_data.get("to_date"):
            return await _query_multi_room_quotes(
                phone=phone,
                flow_data=flow_data,
                groups=groups[:room_count],
                hotel_id=hotel_id,
                lang=lang,
            )

    adult, child_ages = _extract_guests_smart(message)
    child_count = _extract_child_count(message, child_ages)

    from_date, to_date = _extract_dates_smart(message)
    if from_date:
        flow_data["from_date"] = from_date
    if to_date:
        flow_data["to_date"] = to_date

    if adult:
        flow_data["adult_count"] = adult
    if child_ages:
        flow_data["child_ages"] = child_ages
    if child_count is not None:
        flow_data["child_count"] = int(child_count)
    if _has_child_mention(message):
        flow_data["child_mentioned"] = True

    if not flow_data.get("adult_count"):
        save_price_flow(phone, PriceFlowState.ASK_GUESTS, flow_data)
        reply = "Kişi sayısını anlayamadım. Kaç yetişkin? (Örn: '2 yetişkin')" if lang == "tr" else "I couldn't understand the guest count. How many adults? (e.g., '2 adults')"
        return {"reply": reply, "status": "price_flow", "log": None, "is_price_template": False}

    missing = _get_missing_fields(flow_data)
    if not missing:
        return await _query_elektraweb(phone, flow_data, hotel_id)

    ack = _build_ack_message(flow_data, lang)
    return _ask_next_missing(phone, flow_data, missing, lang, ack=ack)


async def _query_multi_room_quotes(
    *,
    phone: str,
    flow_data: Dict[str, Any],
    groups: List[Dict[str, Any]],
    hotel_id: str,
    lang: str,
) -> Dict[str, Any]:
    from_date = flow_data.get("from_date", "")
    to_date = flow_data.get("to_date", "")
    if not from_date or not to_date:
        save_price_flow(phone, PriceFlowState.ASK_DATES, flow_data)
        return {"reply": _ask_dates_message(lang), "status": "price_flow", "log": None, "is_price_template": False}

    family_blocks: List[str] = []
    for i, group in enumerate(groups, start=1):
        adults = int(group.get("adult_count") or 0)
        child_ages = list(group.get("child_ages") or [])
        if adults <= 0:
            continue
        parts = [from_date, to_date, f"{adults} yetişkin" if lang == "tr" else f"{adults} adults"]
        if child_ages:
            if lang == "tr":
                parts.append(f"{len(child_ages)} çocuk " + " ".join(f"{a} yaş" for a in child_ages))
            else:
                parts.append(f"{len(child_ages)} children " + " ".join(str(a) for a in child_ages))
        query_text = " ".join(parts)
        reply_i, log_i, _offers_i = await handle_elektra_price_request(
            query_text,
            hotel_id=hotel_id,
            lang=lang,
        )
        if (reply_i or "").startswith("HANDOFF:"):
            error_type = (reply_i or "").replace("HANDOFF:", "", 1).strip() or "UNKNOWN"
            clear_price_flow(phone)
            if _is_technical_handoff_error(error_type):
                return {
                    "reply": _technical_price_error_reply(lang),
                    "status": "handoff",
                    "log": log_i,
                    "is_price_template": False,
                    "handoff_reason": "fiyat_sistemi_hatasi",
                }
            return {
                "reply": "",
                "status": "handoff",
                "log": log_i,
                "is_price_template": False,
                "handoff_reason": "multi_room_quote_failed",
            }
        title = f"{i}. Aile:" if lang == "tr" else f"Family {i}:"
        family_blocks.append(f"{title}\n\n{reply_i}")

    clear_price_flow(phone)
    if not family_blocks:
        return {
            "reply": "Çok odalı fiyat hesaplaması için aile/oda bazlı kişi bilgilerini tekrar paylaşır mısınız?",
            "status": "price_flow",
            "log": "multi_room_empty_groups",
            "is_price_template": False,
        }
    if lang == "tr":
        header = "Sizlere aşağıda her aile için fiyat paylaşımı yaptım:\n\n"
    else:
        header = "Please find pricing below for each family:\n\n"
    return {
        "reply": header + "\n\n".join(family_blocks),
        "status": "price_result_multi_room",
        "log": "multi_room_quote_ok",
        "is_price_template": False,
    }


async def _handle_child_ages_response(
    phone: str, message: str, flow_data: Dict[str, Any], lang: str, hotel_id: str,
) -> Dict[str, Any]:
    _append_context_hint(flow_data, message)
    currency_new = _infer_currency(message)
    if currency_new:
        flow_data["currency"] = currency_new

    child_ages = _extract_child_ages(message)
    child_count = _extract_child_count(message, child_ages)

    if not child_ages:
        numbers = re.findall(r"\d+", message)
        if not _looks_like_guest_count_payload(message):
            child_ages = [int(n) for n in numbers if 0 <= int(n) <= 17]

    if child_ages:
        flow_data["child_ages"] = child_ages[:4]
        if not flow_data.get("child_count"):
            flow_data["child_count"] = len(flow_data["child_ages"])
    if child_count is not None:
        flow_data["child_count"] = int(child_count)

    if not flow_data.get("child_ages"):
        if any(w in message.lower() for w in ["yok", "hayır", "hayir", "no", "none", "0"]):
            flow_data["child_mentioned"] = False
            flow_data["child_count"] = 0
            flow_data["child_ages"] = []
        else:
            save_price_flow(phone, PriceFlowState.ASK_CHILD_AGES, flow_data)
            reply = "Çocuk yaşlarını paylaşır mısınız? (Örn: '6 yaşında') Çocuk yoksa 'yok' yazın." if lang == "tr" else "Please share the children's ages. (e.g., '6 years old') Or type 'none' if no children."
            return {"reply": reply, "status": "price_flow", "log": None, "is_price_template": False}

    missing = _get_missing_fields(flow_data)
    if not missing:
        return await _query_elektraweb(phone, flow_data, hotel_id)

    ack = _build_ack_message(flow_data, lang)
    return _ask_next_missing(phone, flow_data, missing, lang, ack=ack)


# ===========================================================
# 7) YARDIMCI
# ===========================================================

def _get_missing_fields(flow_data: Dict[str, Any]) -> List[str]:
    missing = []
    if not flow_data.get("from_date") or not flow_data.get("to_date"):
        missing.append("dates")
    room_count = int(flow_data.get("room_count") or 1)
    if room_count > 1:
        groups = flow_data.get("room_groups") or []
        if not isinstance(groups, list) or len(groups) < room_count:
            missing.append("guests")
    else:
        if not flow_data.get("adult_count"):
            missing.append("guests")
    if flow_data.get("child_mentioned") and int(flow_data.get("child_count") or 0) <= 0:
        missing.append("child_count")
    if flow_data.get("child_mentioned") and not flow_data.get("child_ages"):
        missing.append("child_ages")
    return missing


def _ask_next_missing(
    phone: str, flow_data: Dict[str, Any], missing: List[str], lang: str, ack: str = "",
) -> Dict[str, Any]:
    next_field = missing[0]

    if next_field == "dates":
        if flow_data.get("from_date") and not flow_data.get("to_date"):
            save_price_flow(phone, PriceFlowState.ASK_DATES, flow_data)
            reply = _ask_checkout_message(lang, flow_data["from_date"], ack=ack)
        else:
            save_price_flow(phone, PriceFlowState.ASK_DATES, flow_data)
            reply = _ask_dates_message(lang, ack=ack)
    elif next_field == "guests":
        save_price_flow(phone, PriceFlowState.ASK_GUESTS, flow_data)
        reply = _ask_guests_message(lang, ack=ack, room_count=int(flow_data.get("room_count") or 1))
    elif next_field == "child_ages":
        child_count = int(flow_data.get("child_count") or 1)
        save_price_flow(phone, PriceFlowState.ASK_CHILD_AGES, flow_data)
        reply = _ask_child_ages_message(lang, child_count, ack=ack)
    elif next_field == "child_count":
        save_price_flow(phone, PriceFlowState.ASK_GUESTS, flow_data)
        reply = _ask_child_count_message(lang, ack=ack)
    else:
        clear_price_flow(phone)
        return None

    return {"reply": reply, "status": "price_flow", "log": None, "is_price_template": False}


async def _query_elektraweb(
    phone: str,
    flow_data: Dict[str, Any],
    hotel_id: str,
    currency_override: Optional[str] = None,
) -> Dict[str, Any]:
    """Tum bilgi tamam — Elektraweb'e sorgu at."""
    lang = flow_data.get("lang", "tr")
    currency = currency_override or flow_data.get("currency", "EUR")
    if not _is_currency_enabled(currency):
        clear_price_flow(phone)
        return {
            "reply": _DISABLED_CURRENCY_REPLY,
            "status": "handoff",
            "log": f"currency_disabled:{currency}",
            "is_price_template": False,
            "handoff_reason": "price_currency_disabled",
        }

    # Elektraweb icin mesaj olustur (ISO format)
    parts = [
        flow_data["from_date"],
        flow_data["to_date"],
        f"{flow_data['adult_count']} yetişkin" if lang == "tr" else f"{flow_data['adult_count']} adults",
    ]

    # Para birimi ipucu ekle
    currency_word = {"USD": "dolar", "EUR": "euro", "TRY": "TL", "GBP": "sterlin"}.get(currency, "")
    if currency_word:
        parts.append(currency_word)

    if flow_data.get("child_ages"):
        ages_str = " ".join(f"{a} yaş" for a in flow_data["child_ages"])
        child_count = len(flow_data["child_ages"])
        if lang == "tr":
            parts.append(f"{child_count} çocuk {ages_str}")
        else:
            parts.append(f"{child_count} child {ages_str}")

    # Oda tercihi / para birimi gibi ilk niyet bilgilerini kaybetmemek için bağlamı taşı.
    context_hint = str(
        flow_data.get("context_hint")
        or flow_data.get("request_context_hint")
        or flow_data.get("original_question")
        or ""
    ).strip()
    if context_hint:
        parts.append(context_hint[:500])

    constructed_message = " ".join(parts)

    try:
        reply, log, raw_offers = await handle_elektra_price_request(
            constructed_message,
            hotel_id=hotel_id,
            lang=lang,
        )

        if reply.startswith("HANDOFF:"):
            clear_price_flow(phone)
            error_type = reply.replace("HANDOFF:", "", 1).strip() or "UNKNOWN"
            if _is_technical_handoff_error(error_type):
                return {
                    "reply": _technical_price_error_reply(lang),
                    "status": "handoff",
                    "log": log,
                    "is_price_template": False,
                    "handoff_reason": "fiyat_sistemi_hatasi",
                }
            return {
                "reply": "",  # ham HANDOFF:* geri donme
                "status": "handoff",
                "log": log,
                "is_price_template": False,
                "handoff_reason": "fiyat_sistemi_hatasi",
                "handoff_error_type": error_type,
            }


        # BASARILI — Son sorgu parametrelerini kaydet (currency re-query icin)
        save_last_query(phone, {
            "from_date": flow_data["from_date"],
            "to_date": flow_data["to_date"],
            "adult_count": flow_data["adult_count"],
            "child_count": int(flow_data.get("child_count") or 0),
            "child_ages": flow_data.get("child_ages", []),
            "child_mentioned": flow_data.get("child_mentioned", False),
            "lang": lang,
            "currency": currency,
            "request_context_hint": context_hint[:500],
        })

        # Ham offer'lari cache'le (booking flow icin)
        if raw_offers:
            try:
                from app.services.booking_flow_service import save_price_offers
                save_price_offers(phone, raw_offers, {
                    "from_date": flow_data["from_date"],
                    "to_date": flow_data["to_date"],
                    "adult_count": flow_data["adult_count"],
                    "child_ages": flow_data.get("child_ages", []),
                    "currency": currency,
                    "hotel_id": hotel_id,
                    "lang": lang,
                    "quiet_mode": _is_quiet_room_request(constructed_message),
                })
            except Exception as e:
                print(f"[BOOKING] Offer cache error: {e}")

        clear_price_flow(phone)
        return {
            "reply": reply, "status": "price_result",
            "log": log, "is_price_template": True,
        }

    except ElektrawebConfigError as e:
        clear_price_flow(phone)
        log = f"Elektra config error: {str(e)[:2000]}"
        reply = "Şu anda fiyat sistemine bağlanamıyorum (eksik ayar). Lütfen biraz sonra tekrar deneyin." if lang == "tr" else "Cannot connect to pricing system right now. Please try again shortly."
        return {"reply": reply, "status": "error", "log": log, "is_price_template": False}

    except Exception as e:
        clear_price_flow(phone)
        log = f"Elektra runtime error: {type(e).__name__}: {str(e)[:2000]}"
        reply = "Şu anda fiyat bilgisine erişemedim. Lütfen tekrar deneyin." if lang == "tr" else "Could not retrieve pricing info. Please try again."
        return {"reply": reply, "status": "error", "log": log, "is_price_template": False}
