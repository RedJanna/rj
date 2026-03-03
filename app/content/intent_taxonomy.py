from __future__ import annotations

# Decision-phase locked targets (reduced baseline dataset size).
INTENT_EXAMPLE_TARGET_POSITIVE = 40
INTENT_EXAMPLE_TARGET_NEGATIVE = 40

# Central routing thresholds (kept explicit for controlled tuning).
INTENT_AUTO_CONFIDENCE_THRESHOLD = 0.55
INTENT_LLM_DISAMBIGUATION_THRESHOLD = 0.65

INTENT_TAXONOMY = {
    "GREETING": {
        "confused_with": ["SMALLTALK_CLOSING", "OUT_OF_SCOPE_OTHER"],
        "min_signals": ["merhaba", "selam", "hello", "hi"],
    },
    "SMALLTALK_CLOSING": {
        "confused_with": ["GREETING", "OUT_OF_SCOPE_OTHER"],
        "min_signals": ["tesekkur", "gorusuruz", "bye"],
    },
    "HOTEL_BOOKING_CREATE": {
        "confused_with": ["PRICE_QUERY", "AVAILABILITY_QUERY", "RESTAURANT_BOOKING_CREATE"],
        "min_signals": ["rezervasyon yap", "book", "reserve", "oda ayirt"],
    },
    "HOTEL_BOOKING_MODIFY": {
        "confused_with": ["HOTEL_BOOKING_CANCEL", "HUMAN_AGENT_REQUEST", "LOCAL_FAQ_INFO"],
        "min_signals": ["degistir", "guncelle", "revize"],
    },
    "HOTEL_BOOKING_CANCEL": {
        "confused_with": ["HOTEL_BOOKING_MODIFY", "COMPLAINT", "HUMAN_AGENT_REQUEST"],
        "min_signals": ["iptal", "cancel booking", "vazgectim"],
    },
    "PRICE_QUERY": {
        "confused_with": ["AVAILABILITY_QUERY", "HOTEL_BOOKING_CREATE", "DISCOUNT_NEGOTIATION"],
        "min_signals": ["fiyat", "ucret", "ne kadar", "price", "rate"],
    },
    "AVAILABILITY_QUERY": {
        "confused_with": ["PRICE_QUERY", "HOTEL_BOOKING_CREATE", "TRANSFER_BOOKING_REQUEST"],
        "min_signals": ["musait", "bos oda", "availability", "vacancy"],
    },
    "RESTAURANT_BOOKING_CREATE": {
        "confused_with": ["HOTEL_BOOKING_CREATE", "LOCAL_FAQ_INFO", "RESTAURANT_BOOKING_MODIFY"],
        "min_signals": ["masa ayirt", "table reservation", "restaurant booking"],
    },
    "RESTAURANT_BOOKING_MODIFY": {
        "confused_with": ["RESTAURANT_BOOKING_CANCEL", "HUMAN_AGENT_REQUEST", "RESTAURANT_BOOKING_CREATE"],
        "min_signals": ["masa degistir", "reschedule", "update table"],
    },
    "RESTAURANT_BOOKING_CANCEL": {
        "confused_with": ["RESTAURANT_BOOKING_MODIFY", "COMPLAINT", "HUMAN_AGENT_REQUEST"],
        "min_signals": ["masa iptal", "cancel table"],
    },
    "TRANSFER_INFO": {
        "confused_with": ["TRANSFER_BOOKING_REQUEST", "LOCAL_FAQ_INFO", "PRICE_QUERY"],
        "min_signals": ["transfer", "airport", "havalimani"],
    },
    "TRANSFER_BOOKING_REQUEST": {
        "confused_with": ["TRANSFER_INFO", "HOTEL_BOOKING_CREATE", "AVAILABILITY_QUERY"],
        "min_signals": ["transfer ayarla", "book pickup", "ucus no", "varis"],
    },
    "PAYMENT_METHOD_QUERY": {
        "confused_with": ["PAYMENT_LINK_REQUEST", "DISCOUNT_NEGOTIATION", "LOCAL_FAQ_INFO"],
        "min_signals": ["odeme yontemi", "payment methods", "how can i pay"],
    },
    "PAYMENT_LINK_REQUEST": {
        "confused_with": ["PAYMENT_METHOD_QUERY", "HOTEL_BOOKING_CREATE", "HUMAN_AGENT_REQUEST"],
        "min_signals": ["odeme linki", "payment link", "pay online"],
    },
    "LOCAL_FAQ_INFO": {
        "confused_with": ["PRICE_QUERY", "TRANSFER_INFO", "AVAILABILITY_QUERY"],
        "min_signals": ["wifi", "kahvalti", "check-in", "check-out", "konum", "sezon", "havuz", "spa"],
    },
    "COMPLAINT": {
        "confused_with": ["HUMAN_AGENT_REQUEST", "DISCOUNT_NEGOTIATION", "URGENT_CASE"],
        "min_signals": ["sikayet", "complaint", "memnun degilim", "unacceptable"],
    },
    "DISCOUNT_NEGOTIATION": {
        "confused_with": ["PRICE_QUERY", "COMPLAINT", "PAYMENT_METHOD_QUERY"],
        "min_signals": ["indirim", "pazarlik", "discount", "lower price"],
    },
    "HUMAN_AGENT_REQUEST": {
        "confused_with": ["COMPLAINT", "URGENT_CASE", "SPECIAL_REQUEST_EVENT"],
        "min_signals": ["canli destek", "yetkili", "human agent", "live support"],
    },
    "SPECIAL_REQUEST_EVENT": {
        "confused_with": ["HUMAN_AGENT_REQUEST", "RESTAURANT_BOOKING_CREATE", "HOTEL_BOOKING_CREATE"],
        "min_signals": ["surpriz", "balayi", "yildonumu", "proposal", "birthday"],
    },
    "URGENT_CASE": {
        "confused_with": ["COMPLAINT", "HUMAN_AGENT_REQUEST", "TRANSFER_BOOKING_REQUEST"],
        "min_signals": ["acil", "urgent", "hemen", "flight delay"],
    },
    "RISK_ABUSE": {
        "confused_with": ["COMPLAINT", "URGENT_CASE", "OUT_OF_SCOPE_OTHER"],
        "min_signals": ["fraud", "tehdit", "abuse", "illegal", "hack"],
    },
    "AI_IDENTITY_QUESTION": {
        "confused_with": ["OUT_OF_SCOPE_OTHER", "GREETING"],
        "min_signals": ["yapay zeka misin", "are you ai", "bot musun"],
    },
    "OUT_OF_SCOPE_OTHER": {
        "confused_with": ["LOCAL_FAQ_INFO", "AI_IDENTITY_QUESTION", "GREETING"],
        "min_signals": ["intent sinyali yok", "konu disi"],
    },
}
