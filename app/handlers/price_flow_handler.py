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
    ElektrawebConfigError,
    _extract_all_dates,
    _extract_adult_count,
    _extract_child_ages,
    _normalize_turkish_chars,
    _infer_currency,
)

# ===========================================================
# 0) SEZON KONTROLÜ (Sezon dışı taleplerde Elektra'ya gitme)
# ===========================================================

HOTEL_SEASON_START_MMDD = (os.getenv("HOTEL_SEASON_START_MMDD") or "04-10").strip()  # 10 Nisan
HOTEL_SEASON_END_MMDD = (os.getenv("HOTEL_SEASON_END_MMDD") or "11-10").strip()      # 10 Kasım

_MONTH_TR = {
    1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran",
    7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"
}
_MONTH_EN = {
    1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
    7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December"
}

def _parse_mmdd(mmdd: str) -> Tuple[int, int]:
    try:
        m, d = mmdd.split("-", 1)
        return int(m), int(d)
    except Exception:
        return (4, 10)

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

    sm, sd = _parse_mmdd(HOTEL_SEASON_START_MMDD)
    em, ed = _parse_mmdd(HOTEL_SEASON_END_MMDD)
    season_start = date(d1.year, sm, sd)
    season_end = date(d1.year, em, ed)

    allowed_checkout = season_end + timedelta(days=1)
    return not (d1 >= season_start and d2 <= allowed_checkout)

def _build_out_of_season_reply(lang: str, from_date: str, to_date: str) -> str:
    season_str = f"{_fmt_mmdd(HOTEL_SEASON_START_MMDD, lang)} - {_fmt_mmdd(HOTEL_SEASON_END_MMDD, lang)}"
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
    low = _normalize_turkish_chars(message.lower())

    # Önce exclusion kontrolü — karşılaştırma soruları fiyat akışına girmemeli
    all_exclusions = PRICE_EXCLUSION_PATTERNS_TR + PRICE_EXCLUSION_PATTERNS_EN
    for pattern in all_exclusions:
        if _normalize_turkish_chars(pattern.lower()) in low:
            print(f"[SKIP] Fiyat akisi engellendi (karsilastirma sorusu): '{pattern}' bulundu")
            return False

    return any(kw in low for kw in [_normalize_turkish_chars(k) for k in PRICE_INTENT_KEYWORDS])


def detect_handoff_price(message: str) -> Tuple[bool, str]:
    """Elektraweb'in cevaplayamayacagi fiyat sorusu mu?"""
    if not message:
        return False, ""
    low = _normalize_turkish_chars(message.lower())
    for kw in HANDOFF_PRICE_KEYWORDS_TR + HANDOFF_PRICE_KEYWORDS_EN:
        kw_norm = _normalize_turkish_chars(kw.lower())
        if kw_norm in low:
            return True, kw.strip()
    return False, ""

HOTEL_SEASON_START_MMDD = (os.getenv("HOTEL_SEASON_START_MMDD") or "04-10").strip()  # 10 Nisan
HOTEL_SEASON_END_MMDD   = (os.getenv("HOTEL_SEASON_END_MMDD")   or "11-10").strip()  # 10 Kasım

_MONTH_TR = {1:"Ocak",2:"Şubat",3:"Mart",4:"Nisan",5:"Mayıs",6:"Haziran",7:"Temmuz",8:"Ağustos",9:"Eylül",10:"Ekim",11:"Kasım",12:"Aralık"}
_MONTH_EN = {1:"January",2:"February",3:"March",4:"April",5:"May",6:"June",7:"July",8:"August",9:"September",10:"October",11:"November",12:"December"}

def _parse_mmdd(mmdd: str) -> Tuple[int, int]:
    try:
        m, d = mmdd.split("-", 1)
        return int(m), int(d)
    except Exception:
        # fallback: 10 April - 10 November
        return (4, 10)

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

    sm, sd = _parse_mmdd(HOTEL_SEASON_START_MMDD)
    em, ed = _parse_mmdd(HOTEL_SEASON_END_MMDD)
    season_start = date(d1.year, sm, sd)
    season_end   = date(d1.year, em, ed)

    # check-out günü sabahı da kabul edilebilir diye +1 gün tolerans
    allowed_checkout = season_end + timedelta(days=1)

    return not (d1 >= season_start and d2 <= allowed_checkout)

def _build_out_of_season_reply(lang: str, from_date: str, to_date: str) -> str:
    season_str = f"{_fmt_mmdd(HOTEL_SEASON_START_MMDD, lang)} - {_fmt_mmdd(HOTEL_SEASON_END_MMDD, lang)}"
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


def _has_child_mention(message: str) -> bool:
    low = _normalize_turkish_chars(message.lower())
    child_words = ["cocuk", "child", "children", "kid", "baby", "bebek", "infant"]
    return any(w in low for w in child_words)


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


def _ask_guests_message(lang: str, ack: str = "") -> str:
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

    # ----- A) PARA BIRIMI DEGISIKLIGI KONTROLU (EN YUKSEK ONCELIK) -----
    requested_currency = detect_currency_change(message)
    if requested_currency:
        last_q = get_last_query(phone)
        if last_q and last_q.get("from_date") and last_q.get("adult_count"):
            # Son sorgu var — sadece currency degistirip tekrar sor
            print(f"💱 Currency re-query: {phone} → {requested_currency}")
            last_q["currency"] = requested_currency
            return await _query_elektraweb(phone, last_q, hotel_id, currency_override=requested_currency)
        # Son sorgu yok — normal akisa dus (tarih/kisi soracak)

    # ----- B) Aktif flow var mi? -----
    flow = get_price_flow(phone)
    if flow and flow.get("state") and flow["state"] != PriceFlowState.IDLE:
        return await _process_active_flow(phone, message, flow, lang, hotel_id)

    # ----- C) Yeni fiyat niyeti var mi? -----
    if not detect_price_intent(message):
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


async def _start_new_flow(
    phone: str,
    message: str,
    lang: str,
    hotel_id: str,
    history: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    from_date, to_date = _extract_dates_smart(message)
    adult, child_ages = _extract_guests_smart(message)
    has_child = _has_child_mention(message)
    currency = _infer_currency(message)

    # 0) Aynı konuşmada kullanıcı "fiyat verir misin?" dediğinde, son bilinen parametrelerden tamamla
    last_q = get_last_query(phone)
    if last_q:
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
        if not currency:
            currency = last_q.get("currency")

    if child_ages:
        has_child = True

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

            if _has_child_mention(txt):
                has_child = True
            if child_ages:
                has_child = True

            if from_date and to_date and adult is not None and (not (has_child and not child_ages)):
                break

    flow_data: Dict[str, Any] = {
        "lang": lang,
        "original_question": message[:500],
        "from_date": from_date,
        "to_date": to_date,
        "adult_count": adult,
        "child_ages": child_ages if child_ages else [],
        "child_mentioned": has_child,
    }
    if currency:
        flow_data["currency"] = currency

    missing = _get_missing_fields(flow_data)
    if not missing:
        return await _query_elektraweb(phone, flow_data, hotel_id)

    return _ask_next_missing(phone, flow_data, missing, lang)

async def _process_active_flow(
    phone: str, message: str, flow: Dict[str, Any], lang: str, hotel_id: str,
) -> Dict[str, Any]:
    state = flow.get("state", PriceFlowState.IDLE)
    flow_data = flow.get("data", {})
    lang = flow_data.get("lang", lang)

    msg_lower = message.lower().strip()

    if msg_lower in ["iptal", "vazgeç", "vazgec", "cancel", "stop", "dur"]:
        clear_price_flow(phone)
        reply = "Fiyat sorgusu iptal edildi. Size nasıl yardımcı olabilirim?" if lang == "tr" else "Price inquiry cancelled. How can I help you?"
        return {"reply": reply, "status": "price_flow_cancelled", "log": None, "is_price_template": False}

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
    if adult_new:
        flow_data["adult_count"] = adult_new
    if child_ages_new:
        flow_data["child_ages"] = child_ages_new
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
    adult, child_ages = _extract_guests_smart(message)

    from_date, to_date = _extract_dates_smart(message)
    if from_date:
        flow_data["from_date"] = from_date
    if to_date:
        flow_data["to_date"] = to_date

    if adult:
        flow_data["adult_count"] = adult
    if child_ages:
        flow_data["child_ages"] = child_ages
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


async def _handle_child_ages_response(
    phone: str, message: str, flow_data: Dict[str, Any], lang: str, hotel_id: str,
) -> Dict[str, Any]:
    child_ages = _extract_child_ages(message)

    if not child_ages:
        numbers = re.findall(r"\d+", message)
        child_ages = [int(n) for n in numbers if 0 <= int(n) <= 17]

    if child_ages:
        flow_data["child_ages"] = child_ages[:4]

    if not flow_data.get("child_ages"):
        if any(w in message.lower() for w in ["yok", "hayır", "hayir", "no", "none", "0"]):
            flow_data["child_mentioned"] = False
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
    if not flow_data.get("adult_count"):
        missing.append("guests")
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
        reply = _ask_guests_message(lang, ack=ack)
    elif next_field == "child_ages":
        low = _normalize_turkish_chars(flow_data.get("original_question", "").lower())
        m = re.search(r"(\d+)\s*(?:cocuk|child|children|kid)", low)
        child_count = int(m.group(1)) if m else 1
        save_price_flow(phone, PriceFlowState.ASK_CHILD_AGES, flow_data)
        reply = _ask_child_ages_message(lang, child_count, ack=ack)
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
            "child_ages": flow_data.get("child_ages", []),
            "child_mentioned": flow_data.get("child_mentioned", False),
            "lang": lang,
            "currency": currency,
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
