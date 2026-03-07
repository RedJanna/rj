from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from difflib import SequenceMatcher
from typing import Dict, Tuple


INTENT_EXAMPLE_UTTERANCES: Dict[str, tuple[str, ...]] = {
    "AI_IDENTITY_QUESTION": (
        "sen yapay zeka misin",
        "are you an ai assistant",
        "bot musun yoksa insan mi",
    ),
    "HUMAN_AGENT_REQUEST": (
        "canli destek baglar misiniz",
        "i want to talk to a human agent",
        "yetkili biriyle gorusebilir miyim",
    ),
    "COMPLAINT": (
        "hizmetten memnun degilim sikayetim var",
        "i want to make a complaint",
        "bu deneyim kabul edilemez",
    ),
    "DISCOUNT_NEGOTIATION": (
        "daha dusuk fiyat olur mu",
        "can you give me a discount",
        "fiyatta pazarlik payi var mi",
    ),
    "PAYMENT_LINK_REQUEST": (
        "odeme baglantisi gonderir misiniz",
        "please send me a payment link",
        "online odeme yapmak istiyorum",
    ),
    "PAYMENT_METHOD_QUERY": (
        "hangi odeme yontemlerini kabul ediyorsunuz",
        "what payment methods do you accept",
        "kredi karti ve havale gecerli mi",
    ),
    "TRANSFER_BOOKING_REQUEST": (
        "havaalani transferi ayarlamak istiyorum",
        "book an airport pickup for us",
        "ucus numarami paylasayim transfer olusturalim",
    ),
    "TRANSFER_INFO": (
        "havaalani transfer hizmetiniz var mi",
        "do you provide airport transfer",
        "transfer fiyatlari nedir",
    ),
    "RESTAURANT_BOOKING_CREATE": (
        "restoranda masa ayirtmak istiyorum",
        "i want to make a table reservation",
        "aksam yemegi icin yer ayirabilir misiniz",
    ),
    "RESTAURANT_BOOKING_CANCEL": (
        "restoran rezervasyonumu iptal etmek istiyorum",
        "cancel my table booking",
        "masa ayirtmamizi iptal eder misiniz",
    ),
    "RESTAURANT_BOOKING_MODIFY": (
        "masa rezervasyon saatini degistirebilir miyiz",
        "please modify my table reservation",
        "restoran rezervasyonunu baska saate alalim",
    ),
    "HOTEL_BOOKING_CANCEL": (
        "otel rezervasyonumu iptal etmek istiyorum",
        "cancel my room booking",
        "rezervasyondan vazgectim iptal edin",
    ),
    "HOTEL_BOOKING_MODIFY": (
        "rezervasyon tarihimi guncellemek istiyorum",
        "modify my hotel booking details",
        "oda rezervasyonunu revize edelim",
    ),
    "HOTEL_BOOKING_CREATE": (
        "oda rezervasyonu olusturmak istiyorum",
        "i want to book a room",
        "bu tarihler icin konaklama ayarlayalim",
        "rezervsayon yapmak istiyroum",
    ),
    "AVAILABILITY_QUERY": (
        "bu tarihlerde bos oda var mi",
        "is there any availability for these dates",
        "musaitlik durumunu kontrol eder misiniz",
    ),
    "PRICE_QUERY": (
        "bu tarihler icin toplam fiyat nedir",
        "how much is the room for these dates",
        "ucret bilgisi alabilir miyim",
    ),
    "LOCAL_FAQ_INFO": (
        "kahvalti dahil mi ve check in saati kac",
        "what are your wifi and check out details",
        "otelin konumu ve hizmet bilgilerini paylasir misiniz",
    ),
    "GREETING": (
        "merhaba",
        "hello there",
        "iyi gunler",
    ),
    "SMALLTALK_CLOSING": (
        "tesekkur ederim gorusuruz",
        "thanks bye",
        "iyi calismalar hoscakalin",
    ),
    "SPECIAL_REQUEST_EVENT": (
        "balayi icin ozel hazirlik istiyoruz",
        "we need a birthday surprise setup",
        "yildonumu icin organizasyon yapabilir misiniz",
    ),
    "URGENT_CASE": (
        "acil yardima ihtiyacim var",
        "this is urgent please help now",
        "ucusumuz rötar yapti cok gec gelecegiz",
    ),
    "RISK_ABUSE": (
        "sistemi hacklemeye calisiyorum",
        "i will abuse this platform",
        "tehdit ve zorbalik icerikli bir mesajim var",
    ),
}


_DOMAIN_BY_INTENT = {
    "RESTAURANT_BOOKING_CREATE": "restaurant",
    "RESTAURANT_BOOKING_CANCEL": "restaurant",
    "RESTAURANT_BOOKING_MODIFY": "restaurant",
    "PAYMENT_METHOD_QUERY": "payment",
    "PAYMENT_LINK_REQUEST": "payment",
    "HOTEL_BOOKING_CREATE": "hotel",
    "HOTEL_BOOKING_MODIFY": "hotel",
    "HOTEL_BOOKING_CANCEL": "hotel",
    "PRICE_QUERY": "hotel",
    "AVAILABILITY_QUERY": "hotel",
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


@lru_cache(maxsize=1)
def _load_external_intent_examples() -> Dict[str, tuple[str, ...]]:
    """
    Senaryo katalogundan üretilen ek intent örneklerini yükler.
    Dosya yoksa veya bozuksa sessizce geçer; çekirdek örnekler çalışmaya devam eder.
    """
    path = Path(__file__).resolve().parents[1] / "content" / "scenario_intent_examples.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw = payload.get("intent_examples", {})
        merged: Dict[str, tuple[str, ...]] = {}
        for intent_name, examples in raw.items():
            if not isinstance(intent_name, str) or not isinstance(examples, list):
                continue
            norm_examples = []
            seen = set()
            for item in examples:
                if not isinstance(item, str):
                    continue
                cleaned = _normalize(item)
                if not cleaned or cleaned in seen:
                    continue
                seen.add(cleaned)
                norm_examples.append(item.strip())
            if norm_examples:
                merged[intent_name] = tuple(norm_examples)
        return merged
    except Exception:
        return {}


@lru_cache(maxsize=1)
def _get_intent_examples() -> Dict[str, tuple[str, ...]]:
    merged: Dict[str, list[str]] = {
        intent_name: list(examples) for intent_name, examples in INTENT_EXAMPLE_UTTERANCES.items()
    }
    external = _load_external_intent_examples()
    for intent_name, examples in external.items():
        merged.setdefault(intent_name, [])
        merged[intent_name].extend(examples)
    out: Dict[str, tuple[str, ...]] = {}
    for intent_name, examples in merged.items():
        seen = set()
        deduped = []
        for ex in examples:
            key = _normalize(ex)
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(ex)
        out[intent_name] = tuple(deduped)
    return out


def clear_intent_examples_cache() -> None:
    """Flush in-memory cache so newly approved scenarios are used immediately."""
    _load_external_intent_examples.cache_clear()
    _get_intent_examples.cache_clear()


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9çğıöşüâêîôûа-яё]+", _normalize(text), flags=re.IGNORECASE))


def _char_ngrams(text: str, n: int = 3) -> set[str]:
    t = _normalize(text).replace(" ", "")
    if len(t) < n:
        return {t} if t else set()
    return {t[i : i + n] for i in range(len(t) - n + 1)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, len(a | b))


def _pair_similarity(message: str, example: str) -> float:
    token_score = _jaccard(_tokenize(message), _tokenize(example))
    ngram_score = _jaccard(_char_ngrams(message), _char_ngrams(example))
    seq_score = SequenceMatcher(None, _normalize(message), _normalize(example)).ratio()
    return 0.50 * token_score + 0.30 * ngram_score + 0.20 * seq_score


def infer_intent_semantic(message: str, route_domain: str | None = None) -> Tuple[str, float]:
    text = _normalize(message)
    if not text:
        return "OUT_OF_SCOPE_OTHER", 0.0

    best_intent = "OUT_OF_SCOPE_OTHER"
    best_score = 0.0
    second_best = 0.0
    domain = (route_domain or "").strip().lower()

    for intent_name, examples in _get_intent_examples().items():
        score = max(_pair_similarity(text, ex) for ex in examples)
        if domain and _DOMAIN_BY_INTENT.get(intent_name) == domain:
            score += 0.06
        if score > best_score:
            second_best = best_score
            best_score = score
            best_intent = intent_name
        elif score > second_best:
            second_best = score

    if best_score < 0.22:
        return "OUT_OF_SCOPE_OTHER", best_score
    if (best_score - second_best) < 0.03 and domain == "hotel":
        # Belirsiz "otel" vakalarında varsayılanı fiyat sorusuna çek.
        if best_intent in {"AVAILABILITY_QUERY", "HOTEL_BOOKING_CREATE"}:
            return "PRICE_QUERY", best_score
    return best_intent, min(best_score, 1.0)


def infer_domain_from_message(message: str) -> str:
    intent_name, score = infer_intent_semantic(message, route_domain=None)
    if score < 0.20:
        return "unknown"
    return _DOMAIN_BY_INTENT.get(intent_name, "unknown")
