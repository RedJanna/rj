"""Central source for local FAQ and canonical local reply texts."""

from __future__ import annotations

import os
import re
from typing import Dict, Tuple


LOCAL_FAQ: Dict[str, Dict[str, object]] = {
    "check_in": {
        "keywords": ["check-in", "check in", "giriş saat", "kaçta giriş", "giriş saati", "saat kaçta giriş", "заезд", "заселение", "во сколько заезд"],
        "answer_tr": "Check-in saatimiz 14:00'tür (öğleden sonra 2). Erken giriş için lütfen bizi arayın.",
        "answer_en": "Check-in time is 2:00 PM. For early check-in, please call us.",
        "answer_ru": "Время заезда — 14:00. Для раннего заезда, пожалуйста, позвоните нам.",
    },
    "check_out": {
        "keywords": ["check-out", "check out", "çıkış saat", "kaçta çıkış", "çıkış saati", "saat kaçta çıkış", "выезд", "во сколько выезд"],
        "answer_tr": "Check-out saatimiz 12:00'dir (öğlen). Geç çıkış için lütfen bizi arayın.",
        "answer_en": "Check-out time is 12:00 PM (noon). For late check-out, please call us.",
        "answer_ru": "Время выезда — 12:00 (полдень). Для позднего выезда, пожалуйста, позвоните нам.",
    },
    "kahvalti": {
        "keywords": ["kahvaltı", "kahvaltı saat", "breakfast", "kahvaltı kaçta", "kahvaltı dahil", "kahvaltı var mı", "завтрак", "когда завтрак"],
        "answer_tr": "Kahvaltımız 08:00-10:30 saatleri arasında servis edilmektedir ve fiyata dahildir.",
        "answer_en": "Breakfast is served between 08:00-10:30 and is included in the price.",
        "answer_ru": "Завтрак подаётся с 08:00 до 10:30 и включён в стоимость проживания.",
    },
    "havuz": {
        "keywords": ["havuz", "pool", "havuz var mı", "yüzme", "swimming", "бассейн", "есть бассейн"],
        "answer_tr": "Evet, açık havuzumuz mevcuttur. Havuz ısıtmasızdır.",
        "answer_en": "Yes, we have an outdoor pool. The pool is not heated.",
        "answer_ru": "Да, у нас есть открытый бассейн. Бассейн без подогрева.",
    },
    "havuz_isitma": {
        "keywords": ["havuz ısıtmalı", "ısıtmalı havuz", "heated pool", "havuz ısıtma", "подогрев бассейна", "бассейн с подогревом"],
        "answer_tr": "Havuzumuz ısıtmasızdır, açık havuzdur.",
        "answer_en": "Our pool is not heated, it's an outdoor pool.",
        "answer_ru": "Наш бассейн без подогрева, это открытый бассейн.",
    },
    "wifi": {
        "keywords": ["wifi", "wi-fi", "internet", "kablosuz", "вай-фай", "вайфай", "интернет"],
        "answer_tr": "Evet, tüm otelimizde ücretsiz Wi-Fi mevcuttur.",
        "answer_en": "Yes, free Wi-Fi is available throughout the hotel.",
        "answer_ru": "Да, бесплатный Wi-Fi доступен на всей территории отеля.",
    },
    "otopark": {
        "keywords": ["otopark", "parking", "park yeri", "araba park", "araç park", "парковка", "стоянка"],
        "answer_tr": "Evet, ücretsiz otopark mevcuttur.",
        "answer_en": "Yes, free parking is available.",
        "answer_ru": "Да, бесплатная парковка доступна.",
    },
    "plaj_tipi": {
        "keywords": [
            "kumlu", "kum mu", "kumlu mu", "taşlı", "tasli", "taş mı", "tas mi",
            "çakıllı", "cakilli", "çakıl", "cakil", "plaj tipi", "kumsal tipi",
            "kumlu bir plaj", "plaj kumlu mu",
        ],
        "answer_tr": "Ölüdeniz bölgesindeki plaj yapısı karma karakterdedir; sahilde kum ve yer yer çakıllı/taşlı alanlar bulunabilir. En konforlu kullanım için deniz ayakkabısı önerilir.",
        "answer_en": "Beach structure in the Ölüdeniz area is mixed; you may find sandy parts as well as pebbly/rocky sections. We recommend sea shoes for comfort.",
        "answer_ru": "Пляжи в районе Олюдениза смешанного типа: есть песчаные участки, а также местами галька/камни. Для комфорта рекомендуем акваобувь.",
    },
    "plaj": {
        "keywords": ["plaj", "beach", "kumsal", "denize uzaklık", "пляж", "до моря", "до пляжа"],
        "answer_tr": "Plaj otelimize yaklaşık 300 metre uzaklıktadır.",
        "answer_en": "The beach is approximately 300 meters from our hotel.",
        "answer_ru": "Пляж находится примерно в 300 метрах от нашего отеля.",
    },
    "transfer": {
        "keywords": [
            "transfer fiyat",
            "transfer ücret",
            "transfer ucret",
            "transfer kaç",
            "transfer kac",
            "havalimanı transfer",
            "havalimani transfer",
            "havalimani transferi",
            "airport transfer",
            "tek yön",
            "tek yon",
            "gidiş-dönüş",
            "gidis-donus",
            "трансфер",
            "трансфер из аэропорта",
        ],
        "answer_tr": "Dalaman Havalimanı'ndan otelimize transfer ücreti tek yön 75€'dur (nakit ödeme). Gidiş-dönüş toplam 150€ olarak hesaplanır. Antalya Havalimanı'ndan da transfer hizmetimiz mevcuttur; detaylı bilgi için sizi müşteri temsilcimize bağlıyoruz.",
        "answer_en": "Transfer from Dalaman Airport to our hotel is 75€ one way (cash payment). Round-trip is 150€ in total. We also provide transfers from Antalya Airport; we are connecting you to our representative for detailed information.",
        "answer_ru": "Трансфер из аэропорта Даламан до нашего отеля — 75€ в одну сторону (оплата наличными). Туда-обратно — 150€ в сумме. Мы также предоставляем трансфер из аэропорта Анталья; для подробной информации мы соединяем вас с нашим представителем.",
    },
    "sezon": {
        "keywords": ["sezon", "açık mısınız", "kapalı mısınız", "ne zaman açık", "açılış", "kapanış", "open", "closed", "сезон", "когда открыт", "когда закрыт"],
        "answer_tr": "Otelimiz genellikle Nisan ortası - Kasım ortası civarında açıktır. Kesin açılış ve kapanış tarihleri için lütfen bizi arayın: +90 533 250 32 77",
        "answer_en": "Our hotel is generally open from mid-April to mid-November. For exact opening and closing dates, please call us: +90 533 250 32 77",
        "answer_ru": "Наш отель обычно работает с середины апреля до середины ноября. Для уточнения дат открытия и закрытия, пожалуйста, позвоните нам: +90 533 250 32 77",
    },
    "telefon": {
        "keywords": [
            "telefon", "numara", "iletişim", "iletişime", "iletisim", "iletisime",
            "resepsiyon", "ressepsiyon", "reception", "whatsapp",
            "arayabilir", "contact", "phone", "call", "телефон", "позвонить", "контакт", "связаться",
        ],
        "answer_tr": "Bize +90 533 250 32 77 numaralı telefondan veya WhatsApp'tan ulaşabilirsiniz.",
        "answer_en": "You can reach us at +90 533 250 32 77 by phone or WhatsApp.",
        "answer_ru": "Вы можете связаться с нами по телефону +90 533 250 32 77 или через WhatsApp.",
    },
    "adres": {
        "keywords": ["adres", "nerede", "konum", "lokasyon", "address", "location", "where", "адрес", "где находится", "расположение"],
        "answer_tr": "Otelimiz Fethiye / Ölüdeniz merkezinde yer almaktadır.",
        "answer_en": "Our hotel is located in the center of Fethiye / Ölüdeniz.",
        "answer_ru": "Наш отель расположен в центре Фетхие / Олюдениз.",
    },
    "restoran": {
        "keywords": ["restoran", "yemek", "restaurant", "food", "akşam yemeği", "öğle yemeği", "ресторан", "еда", "ужин", "обед"],
        "answer_tr": "Restoranımız 11:00-22:00 saatleri arasında hizmet vermektedir.",
        "answer_en": "Our restaurant is open from 11:00 AM to 10:00 PM.",
        "answer_ru": "Наш ресторан работает с 11:00 до 22:00.",
    },
    "sigara": {
        "keywords": ["sigara", "smoking", "sigara içilir", "sigara içilebilir", "курение", "можно курить"],
        "answer_tr": "Odalarımız sigara içilmez odadır. Belirlenmiş açık alanlarda sigara içilebilir.",
        "answer_en": "Our rooms are non-smoking. Smoking is allowed in designated outdoor areas.",
        "answer_ru": "Наши номера — для некурящих. Курение разрешено в специально отведённых открытых зонах.",
    },
    "evcil": {
        "keywords": ["evcil hayvan", "pet", "köpek", "kedi", "dog", "cat", "hayvan", "домашнее животное", "питомец", "собака", "кошка"],
        "answer_tr": "Evcil hayvan politikamız hakkında bilgi almak için lütfen bizi arayın: +90 533 250 32 77",
        "answer_en": "For information about our pet policy, please call us: +90 533 250 32 77",
        "answer_ru": "Для информации о правилах размещения с домашними животными, пожалуйста, позвоните нам: +90 533 250 32 77",
    },
    "dogum_gunu_basit": {
        "keywords": ["doğum günü kutla", "birthday celebration", "день рождения"],
        "answer_tr": "Doğum günü kutlamaları için odada süsleme (balon, pankart), pasta siparişi ve restoranda özel masa hazırlığı yapabiliyoruz. Detayları öğrenebilir miyim - hangi tarih ve kaç kişi için planlıyorsunuz?",
        "answer_en": "For birthday celebrations, we can arrange room decoration (balloons, banner), cake orders, and special table setup at our restaurant. May I know the details - which date and for how many people?",
        "answer_ru": "Для празднования дня рождения мы можем организовать украшение номера (шары, баннер), заказ торта и особую сервировку стола в ресторане. Подскажите, на какую дату и на сколько человек вы планируете?",
    },
    "balayi_basit": {
        "keywords": ["balayı", "honeymoon", "медовый месяц"],
        "answer_tr": "Balayı çiftleri için otelimiz özel oda hazırlığı yapmaktadır. Şarap ve meyve tabağı ikramımız bulunmaktadır. Jakuzili odalarımız olan Penthouse ve Premium odalarımızı öneriyoruz. Hangi tarihler için planlıyorsunuz?",
        "answer_en": "For honeymoon couples, our hotel prepares special room arrangements. We offer complimentary wine and fruit platter. We recommend our jacuzzi rooms - Penthouse and Premium. Which dates are you planning?",
        "answer_ru": "Для молодожёнов наш отель подготавливает особое оформление номера. Мы предлагаем комплиментарное вино и фруктовую тарелку. Рекомендуем номера с джакузи — Penthouse и Premium. На какие даты вы планируете?",
    },
    "yildonumu_basit": {
        "keywords": ["yıldönümü", "anniversary", "годовщина"],
        "answer_tr": "Yıldönümü kutlamaları için otelimiz özel oda hazırlığı yapmaktadır. Şarap ve meyve tabağı ikramımız bulunmaktadır. Restoranda romantik masa hazırlığı da yapabiliyoruz. Hangi tarih için planlıyorsunuz?",
        "answer_en": "For anniversary celebrations, our hotel prepares special room arrangements with complimentary wine and fruit platter. We can also arrange a romantic table at our restaurant. Which date are you planning?",
        "answer_ru": "Для празднования годовщины наш отель подготавливает особое оформление номера с комплиментарным вином и фруктовой тарелкой. Мы также можем организовать романтический столик в ресторане. На какую дату вы планируете?",
    },
    "rezervasyon_degisiklik": {
        "keywords": ["rezervasyon değiştir", "saat değiştir", "tarihi değiştir", "saati değiştirmek", "tarih değişikliği", "rezervasyon iptal", "iptal etmek", "değişiklik yapmak", "изменить бронь", "отменить бронь", "изменить бронирование", "отменить бронирование"],
        "answer_tr": "Rezervasyonunuzu değiştirmek veya iptal etmek için lütfen bize aşağıdaki bilgileri iletin:\n\n📋 Rezervasyon numaranız (varsa)\n📅 Yeni tarih/saat (değişiklik için)\n👤 İsminiz\n\nEn kısa sürede işleminizi gerçekleştireceğiz. Teşekkürler! 😊",
        "answer_en": "To change or cancel your reservation, please provide us with:\n\n📋 Your reservation number (if available)\n📅 New date/time (for changes)\n👤 Your name\n\nWe will process your request as soon as possible. Thank you! 😊",
        "answer_ru": "Для изменения или отмены бронирования, пожалуйста, сообщите нам:\n\n📋 Номер бронирования (если есть)\n📅 Новая дата/время (для изменения)\n👤 Ваше имя\n\nМы обработаем ваш запрос в кратчайшие сроки. Спасибо! 😊",
    },
    "rez_id_bilgisi": {
        "keywords": ["rez id", "rezid", "rez no", "rez numarası", "rezervasyon id", "rezervasyon no", "rez id nedir", "rezervasyon numarası nedir"],
        "answer_tr": "Rezervasyon numarası, konfirmasyon formunda yer alan kimlik bilgisidir. Elektra ekranında aynı bilgi Voucher No olarak da görünebilir.",
        "answer_en": "Your reservation number is shown on your confirmation form. In Elektra, the same reference may appear as Voucher No.",
        "answer_ru": "Номер бронирования указан в форме подтверждения. В системе Elektra этот же номер может отображаться как Voucher No.",
    },
}


def _read_local_max_words() -> int:
    raw = (os.getenv("LOCAL_MAX_WORDS") or "").strip()
    if not raw:
        return 8
    try:
        value = int(raw)
    except Exception:
        return 8
    return max(3, min(10, value))


LOCAL_MAX_WORDS = _read_local_max_words()


CANONICAL_LOCAL_REPLIES_TR: Dict[str, str] = {
    "kanonik_fiyat": "Oda fiyatlarımız sezon ve oda tipine göre değişir. ✅\n\nGüncel fiyat/ücret bilgisi € (euro) cinsinden paylaşılır.\nLütfen tarih aralığını ve kaç kişi olduğunuzu yazın; hemen yardımcı olayım.",
    "kanonik_kahvalti": "Kahvaltımız açık büfe olarak 08:00-10:30 saatleri arasında servis edilir ve fiyata dahildir.",
    "kanonik_wifi": "Evet, tüm otelimizde ücretsiz wifi (internet) var.",
    "kanonik_erken_giris": "Check-in saatimiz 14:00’tür. Odanız hazır olması durumunda daha erken giriş yapmanıza memnuniyetle yardımcı oluruz. Odanız henüz hazır değilse, hazırlanma sürecinde restoran ve havuz alanlarımızdan faydalanabilirsiniz.",
    "kanonik_gec_cikis": "Check-out saatimiz 12:00'dir. Geç çıkış talebi müsaitlik durumuna göre değerlendirilir. Lütfen resepsiyon ile iletişime geçiniz.",
    "kanonik_check": "Check-in saatimiz 14:00, check-out saatimiz 12:00'dir.",
    "kanonik_sezon": "Otelimiz 10 Nisan - 10 Kasım tarihleri arasında açıktır.",
    "kanonik_konum": "Otelimiz Fethiye / Ölüdeniz merkezinde yer almaktadır.",
    "kanonik_transfer": "Dalaman Havalimanı'ndan otelimize transfer ücreti tek yön 75€ (75 euro)'dur (nakit ödeme). Gidiş-dönüş toplam 150€ olarak hesaplanır. Antalya Havalimanı'ndan da transfer hizmetimiz mevcuttur; detaylı bilgi için sizi müşteri temsilcimize bağlıyoruz.",
    "kanonik_havuz": "Evet, açık havuzumuz var. Havuz ısıtmasızdır.",
    "local_otel_rezervasyon": "Elbette oda rezervasyonunuz için yardımcı olabilirim. 🏨\n\nLütfen şu bilgileri paylaşın: giriş-çıkış tarih(leri), kaç kişi (yetişkin/çocuk), varış saati (saat) ve oda tipi.\nNot: Check-in saatimiz 14:00, check-out saatimiz 12:00'dir.",
    "local_olanak_spa": "Otelimizde spa ve masaj hizmeti mevcut değildir. Dilerseniz size yakın öneriler için yardımcı olabilirim.",
}


LOCAL_FAQ_NORMALIZED_TR_BY_CATEGORY: Dict[str, str] = {
    "wifi": CANONICAL_LOCAL_REPLIES_TR["kanonik_wifi"],
    "kahvalti": CANONICAL_LOCAL_REPLIES_TR["kanonik_kahvalti"],
    "check": CANONICAL_LOCAL_REPLIES_TR["kanonik_check"],
    "havuz": CANONICAL_LOCAL_REPLIES_TR["kanonik_havuz"],
    "transfer": CANONICAL_LOCAL_REPLIES_TR["kanonik_transfer"],
    "sezon": CANONICAL_LOCAL_REPLIES_TR["kanonik_sezon"],
}


def normalize_local_faq_reply(reply: str, category: str, lang: str) -> str:
    if lang != "tr":
        return reply
    cat = (category or "").lower()
    for key, val in LOCAL_FAQ_NORMALIZED_TR_BY_CATEGORY.items():
        if key in cat:
            return val
    return reply


def _looks_like_multi_intent_booking_query(text_lower: str) -> bool:
    if not text_lower:
        return False

    has_date = bool(
        re.search(r"\b\d{1,2}\s*[-–—]\s*\d{1,2}\b", text_lower)
        or re.search(r"\b20\d{2}\b", text_lower)
        or re.search(r"\d{4}\s*年\s*\d{1,2}\s*月", text_lower)
        or any(month in text_lower for month in ("august", "ağustos", "август", "agosto", "août", "agosto", "8月"))
    )
    has_guest = bool(
        re.search(
            r"\b\d+\s*(adult|adults|guest|guests|yeti[şs]kin|ki[şs]i|child|children|cocuk|çocuk|взросл|дет|человек|位|成人)\b",
            text_lower,
        )
    )
    has_room_or_price = any(
        marker in text_lower
        for marker in (
            "room",
            "oda",
            "standard room",
            "sea view",
            "deniz manzara",
            "price",
            "total",
            "fiyat",
            "ücret",
            "ucret",
            "стоимость",
            "цена",
            "precio",
            "prix",
            "preço",
            "价格",
        )
    )
    has_booking_action = any(
        marker in text_lower
        for marker in (
            "book",
            "booking",
            "reservation",
            "reserve",
            "rezervasyon",
            "rezerv",
            "брони",
            "бронь",
            "оформить",
            "подтверждение",
        )
    )
    has_operational_detail = any(
        marker in text_lower
        for marker in (
            "check-in",
            "check out",
            "check-out",
            "late check",
            "заезд",
            "выезд",
            "transfer",
            "трансфер",
            "payment",
            "оплат",
            "deposit",
            "depozit",
            "kapora",
            "passport",
            "паспорт",
        )
    )

    signal_count = sum([has_date, has_guest, has_room_or_price, has_booking_action, has_operational_detail])
    return signal_count >= 2


def check_local_faq(text: str) -> Tuple[bool, str, str, str, str]:
    """
    Local FAQ kontrolü.
    Returns: (found, answer_tr, answer_en, category, answer_ru)
    """
    text_lower = (text or "").lower().strip()
    # Raw contact payloads (email/URL-ish) should not trigger FAQ keyword matching.
    # Example: "ivan.petrov@example.com" accidentally contains "pet".
    if re.search(r"\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b", text_lower):
        return False, "", "", "", ""

    # Çok net birleşik soru: check-in + check-out + geç çıkış
    has_checkin_signal = any(k in text_lower for k in ["check-in", "check in", "kaçta giriş", "giriş saati", "giris saati"])
    has_checkout_signal = any(k in text_lower for k in ["check-out", "check out", "kaçta çıkış", "çıkış saati", "cikis saati"])
    if has_checkin_signal and has_checkout_signal:
        return (
            True,
            "Check-in saatimiz 14:00, check-out saatimiz 12:00'dir. Geç çıkış talebi müsaitlik durumuna göre değerlendirilir; lütfen resepsiyon ile iletişime geçiniz.",
            "Check-in is at 14:00 and check-out is at 12:00. Late check-out is subject to availability; please contact reception.",
            "check_in_out",
            "Заезд с 14:00, выезд до 12:00. Поздний выезд возможен при наличии свободных номеров; пожалуйста, свяжитесь с ресепшеном.",
        )

    word_count = len(text_lower.split())
    if word_count > LOCAL_MAX_WORDS:
        # Uzun kahvaltı içerik sorularında (dahil mi/saat) deterministic cevap ver.
        if (
            ("kahvaltı" in text_lower or "kahvalti" in text_lower or "breakfast" in text_lower)
            and any(k in text_lower for k in ["dahil", "included", "saat", "kaçta", "kacta"])
            and not any(k in text_lower for k in ["rezervasyon", "reservation", "book", "ayirt", "ayırt"])
        ):
            data = LOCAL_FAQ.get("kahvalti", {})
            return (
                True,
                str(data.get("answer_tr", "")),
                str(data.get("answer_en", "")),
                "kahvalti",
                str(data.get("answer_ru", data.get("answer_en", ""))),
            )

        # Uzun mesajlarda sadece güçlü, düşük-risk FAQ'ları yakala.
        # Bu sayede fiyat/rezervasyon akışını bölmeden "plaj kumlu mu taşlı mı"
        # gibi sorulara yine de tutarlı cevap verilir.
        # İletişim/resepsiyon soruları da düşük-risk olduğu için yakalanır.
        long_message_has_booking_context = _looks_like_multi_intent_booking_query(text_lower)
        strong_categories = ("plaj_tipi", "plaj") if long_message_has_booking_context else ("telefon", "plaj_tipi", "plaj", "transfer")
        for category in strong_categories:
            data = LOCAL_FAQ.get(category, {})
            for keyword in data.get("keywords", []):
                if str(keyword).lower() in text_lower:
                    return (
                        True,
                        str(data.get("answer_tr", "")),
                        str(data.get("answer_en", "")),
                        category,
                        str(data.get("answer_ru", data.get("answer_en", ""))),
                    )
        return False, "", "", "", ""

    for category, data in LOCAL_FAQ.items():
        for keyword in data.get("keywords", []):
            if str(keyword).lower() in text_lower:
                return (
                    True,
                    str(data.get("answer_tr", "")),
                    str(data.get("answer_en", "")),
                    category,
                    str(data.get("answer_ru", data.get("answer_en", ""))),
                )
    return False, "", "", "", ""
