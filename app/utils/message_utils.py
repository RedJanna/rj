from __future__ import annotations

from typing import Tuple
import re
from app.content.local_faq_data import (
    LOCAL_FAQ,
    LOCAL_MAX_WORDS,
    check_local_faq,
)


# ======================================================
# 9. MESAJ TESPİT FONKSİYONLARI
# ======================================================

def is_conversation_ending(text: str) -> bool:
    t = text.lower().strip()
    ending_phrases = [
        "teşekkürler", "teşekkür ederim", "sağol", "sağolun", "eyvallah",
        "thanks", "thank you", "bye", "goodbye", "görüşürüz", "hoşçakal",
        "iyi günler", "iyi akşamlar", "iyi geceler", "tamam bu kadar",
        "şimdilik bu kadar", "yeterli", "anladım teşekkürler",
        # Rusça
        "спасибо", "благодарю", "до свидания", "пока", "всего доброго",
        "хорошего дня", "доброй ночи", "добрый вечер",
    ]
    return any(phrase in t for phrase in ending_phrases)

def get_closing_message(lang: str = "tr") -> str:
    if lang == "en":
        return "You're welcome! Feel free to reach out anytime. We look forward to hosting you at Kassandra Ölüdeniz. Have a great day! 🌟"
    if lang == "ru":
        return "Пожалуйста! Если у вас возникнут вопросы, пишите нам в любое время. Будем рады видеть вас в Kassandra Ölüdeniz. Хорошего дня! 🌟"
    return "Rica ederim! Başka sorularınız olursa her zaman yazabilirsiniz. Kassandra Ölüdeniz'de sizleri ağırlamaktan mutluluk duyarız. İyi günler dileriz! 🌟"

def is_greeting(text: str) -> Tuple[bool, str]:
    """
    Selamlama kontrolü - dil ile birlikte döndürür.
    Returns: (is_greeting: bool, language: str)
    """
    t = text.lower().strip()
    
    # Türkçe selamlamalar
    turkish_greetings = [
        "merhaba", "selam", "selamlar", "merhabalar", "slm",
        "günaydın", "iyi akşamlar", "iyi günler", "hayırlı günler",
        "nasılsınız", "naber", "nbr"
    ]

    # İngilizce selamlamalar
    english_greetings = [
        "hi", "hello", "hey", "hii", "hiii",
        "good morning", "good afternoon", "good evening", "good night",
        "greetings", "howdy", "yo", "hiya",
        "what's up", "whats up", "wassup", "sup"
    ]

    # Rusça selamlamalar
    russian_greetings = [
        "привет", "здравствуйте", "здравствуй", "приветик",
        "доброе утро", "добрый день", "добрый вечер", "доброй ночи",
        "приветствую", "хай", "хей",
    ]

    # Türkçe selamlama mı?
    if t in turkish_greetings or any(t.startswith(g + " ") for g in turkish_greetings):
        return True, "tr"

    # İngilizce selamlama mı?
    if t in english_greetings or any(t.startswith(g + " ") for g in english_greetings):
        return True, "en"

    # Rusça selamlama mı?
    if t in russian_greetings or any(t.startswith(g + " ") for g in russian_greetings):
        return True, "ru"

    return False, "tr"

def get_welcome_message(lang: str = "tr") -> str:
    """Karşılama mesajı - dil destekli"""
    if lang == "en":
        return """Hello! 👋

Welcome to Kassandra Ölüdeniz. 🌊
I'm here to help you with a special accommodation experience.

How can I assist you today?
1. Reservation / Room information
2. Transfer & Transportation
3. Restaurant & Breakfast
4. Special requests (surprise, celebration, etc.)

You can type a number or ask your question directly 😊"""

    if lang == "ru":
        return """Здравствуйте! 👋

Добро пожаловать в Kassandra Ölüdeniz. 🌊
Я здесь, чтобы помочь вам организовать незабываемый отдых.

Чем могу помочь?
1. Бронирование / Информация о номерах
2. Трансфер и транспорт
3. Ресторан и завтрак
4. Особые пожелания (сюрприз, праздник и т.д.)

Вы можете выбрать номер или задать вопрос напрямую 😊"""

    return """Merhaba,

Kassandra Ölüdeniz'e hoş geldiniz. 🌊
Size özel bir konaklama deneyimi hazırlamak için buradayım.

Size nasıl yardımcı olabilirim?
1. Rezervasyon / Oda bilgisi
2. Transfer & Ulaşım
3. Restoran & kahvaltı
4. Özel istekler (sürpriz, kutlama, vb.)

Seçiminizi numara ile belirtebilir veya doğrudan sorunuzu yazabilirsiniz 😊"""

def is_menu_selection(text: str) -> Tuple[bool, int]:
    t = text.strip()
    if t in ["1", "2", "3", "4"]:
        return True, int(t)
    return False, 0

def get_menu_response(selection: int, lang: str = "tr") -> str:
    """Menü seçimi cevabı - dil destekli"""
    responses_tr = {
        1: "Rezervasyon veya oda bilgisi için size yardımcı olabilirim. Hangi tarihler için ve kaç kişilik konaklama düşünüyorsunuz?",
        2: "Transfer hizmetimiz hakkında bilgi almak istiyorsunuz. Dalaman ve Antalya havalimanlarından transfer hizmetimiz mevcuttur. Tek yön transfer ücreti 75€'dur. Hangi havalimanından ve ne zaman geleceksiniz?",
        3: "Restoran ve kahvaltı hakkında bilgi vermek isterim:\n\n☕ Kahvaltı: 08:00 - 10:30 (dahil)\n🍽️ Restoran: 11:00 - 22:00\n\nMenümüzü incelemek için: https://www.kassandrarestaurant.com/menuler",
        4: "Özel isteklerinizi memnuniyetle karşılarız! Lütfen sürpriz, kutlama veya başka taleplerinizi detaylandırabilir misiniz?"
    }
    
    responses_en = {
        1: "I can help you with reservation or room information. What dates are you considering and for how many guests?",
        2: "You want information about our transfer service. We provide transfers from Dalaman and Antalya airports. One-way transfer is 75€. Which airport and when will you arrive?",
        3: "Let me tell you about our restaurant and breakfast:\n\n☕ Breakfast: 08:00 - 10:30 (included)\n🍽️ Restaurant: 11:00 - 22:00\n\nView our menu: https://www.kassandrarestaurant.com/menuler",
        4: "We would be happy to accommodate your special requests! Please provide details about your surprise, celebration, or other requests."
    }

    responses_ru = {
        1: "Я могу помочь вам с бронированием или информацией о номерах. На какие даты и на сколько гостей вы планируете проживание?",
        2: "Мы предоставляем трансфер из аэропортов Даламан и Анталья. Стоимость трансфера в одну сторону — 75€. Из какого аэропорта и когда вы прибываете?",
        3: "Расскажу о нашем ресторане и завтраке:\n\n☕ Завтрак: 08:00 - 10:30 (включён в стоимость)\n🍽️ Ресторан: 11:00 - 22:00\n\nНаше меню: https://www.kassandrarestaurant.com/menuler",
        4: "Мы будем рады выполнить ваши особые пожелания! Пожалуйста, расскажите подробнее о вашем сюрпризе, празднике или других просьбах."
    }

    if lang == "ru":
        responses = responses_ru
        default = "Чем могу помочь?"
    elif lang == "en":
        responses = responses_en
        default = "How can I help you?"
    else:
        responses = responses_tr
        default = "Size nasıl yardımcı olabilirim?"
    return responses.get(selection, default)


# ======================================================
# 10. DİL & FİYAT FONKSİYONLARI
# ======================================================

MONTHS_TR = ["ocak", "şubat", "mart", "nisan", "mayıs", "haziran", "temmuz", "ağustos", "eylül", "ekim", "kasım", "aralık"]
MONTHS_EN = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
MONTHS_RU = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"]

def detect_language(text: str) -> str:
    """
    Mesaj dilini algıla.

    MANTIK:
    1. Rusça (Kiril) karakter varsa → RUSÇA
    2. İngilizce cümle yapısı varsa → İNGİLİZCE (klavye hatası tolere edilir)
    3. Türkçe karakter varsa VE İngilizce değilse → TÜRKÇE
    4. İngilizce kelime sayısı > 0 → İNGİLİZCE
    5. Türkçe kelime varsa → TÜRKÇE
    6. Varsayılan → TÜRKÇE
    """
    t = text.lower().strip()
    original_text = text.lower().strip()

    # 0. RUSÇA KONTROLÜ (Kiril alfabesi varsa → Rusça)
    # Kiril harfleri: а-яёА-ЯЁ
    russian_char_count = len(re.findall(r'[а-яёА-ЯЁ]', t))
    if russian_char_count >= 2:
        return "ru"

    # Kısa Rusça selamlamalar (tek kelime bile olsa)
    russian_short_words = [
        "привет", "здравствуйте", "добрый", "доброе", "добрая",
        "спасибо", "да", "нет", "хорошо", "пожалуйста",
    ]
    if t in russian_short_words:
        return "ru"

    # "ı" harfini "i" ile değiştir (klavye hatası düzeltmesi)
    # Bu sayede "can ı book" → "can i book" olarak algılanır
    t_normalized = t.replace("ı", "i")

    # 1. İngilizce cümle yapısı kontrolü (ÖNCELİKLİ - normalleştirilmiş metin üzerinde)
    english_patterns = [
        r'^good\s+(?:morning|afternoon|evening|night)\b',  # "good morning..."
        r'^can\s+i\b',           # "can i book..."
        r'^can\s+you\b',         # "can you help..."
        r'^could\s+i\b',         # "could i..."
        r'^could\s+you\b',       # "could you..."
        r'^i\s+want\b',          # "i want to..."
        r'^i\s+need\b',          # "i need..."
        r'^i\s+would\b',         # "i would like..."
        r'^i\'d\s+like\b',       # "i'd like..."
        r'^i\'m\b',              # "i'm looking..."
        r'^do\s+you\b',          # "do you have..."
        r'^is\s+there\b',        # "is there..."
        r'^are\s+there\b',       # "are there..."
        r'^how\s+much\b',        # "how much..."
        r'^how\s+many\b',        # "how many..."
        r'^what\s+is\b',         # "what is..."
        r'^what\s+are\b',        # "what are..."
        r'^when\s+is\b',         # "when is..."
        r'^where\s+is\b',        # "where is..."
        r'\bfor\s+\d+\s+person',  # "for 2 person"
        r'\bfor\s+\d+\s+people',  # "for 2 people"
        r'\bbook\s+a\s+table\b', # "book a table"
        r'\breserve\s+a\s+table\b', # "reserve a table"
        r'\btable\s+for\s+\d+\b', # "table for 4"
        r'\bas\s+i\s+said\b',    # "as i said"
    ]

    # Hem orijinal hem normalize edilmiş metni kontrol et
    for pattern in english_patterns:
        if re.search(pattern, t_normalized) or re.search(pattern, t):
            return "en"

    # 2. Türkçe karakterler - AMA İngilizce kelimelerle birlikte değilse
    turkish_chars = ["ş", "ğ", "ç", "ö", "ü"]  # "ı" çıkarıldı - klavye hatası olabilir
    has_strong_turkish = any(char in t for char in turkish_chars)

    # "ı" harfi varsa ama İngilizce kelimeler de varsa, İngilizce olabilir
    has_i_nodot = "ı" in t

    # 3. İngilizce kelimeler (SADECE İNGİLİZCE OLANLAR)
    english_only_words = [
        # Zamirler
        " i ", "i'm", "i'd", "i've", "i'll", " me ", " my ", " you ", " your ",
        " we ", " our ", " he ", " she ", " they ", " their ",
        # Yardımcı fiiller
        "can ", "could ", "would ", "should ", "will ",
        "don't", "didn't", "doesn't", "won't", "wouldn't", "couldn't",
        # Soru kelimeleri
        "what ", "where ", "when ", "how ", "why ", "which ",
        # Fiiller
        " book ", " reserve ", " want ", " need ", " like ",
        " said ", " told ",
        # Otel kelimeleri (İNGİLİZCE ÖZGÜ)
        " table ", " room ", " person ", " people ", " guest ",
        " night ", " stay ", " breakfast ", " dinner ", " lunch ",
        # Kibarlık
        "please", "thank", "thanks",
        # Article'lar (Türkçe'de yok)
        " the ", " a ", " an ",
    ]

    # Türkçe kelimeler (SADECE TÜRKÇE OLANLAR - "restaurant" YOK!)
    turkish_only_words = [
        "merhaba", "selam", "evet", "hayir", "tamam", "peki",
        "tesekkur", "lutfen", "rica",
        "fiyat", "ucret", "kac para", "ne kadar",
        "kisi", "kisilik", "yetiskin", "cocuk",
        "oda", "otel", "konaklama", "gece",
        "rezervasyon", "restoran",  # Türkçe yazım
        "masa", "giris", "cikis",
        "kahvalti", "yemek", "havuz", "plaj",
        "istiyorum", "isterim", "yapabilir",
        "var mi", "yok mu", "nerede", "nasil",
        "ben", "biz", "siz", "bu",
    ]

    # Sayım (normalize edilmiş metin üzerinde)
    english_count = sum(1 for word in english_only_words if word in t_normalized)
    turkish_count = sum(1 for word in turkish_only_words if word in t)

    # Karar
    # Eğer İngilizce kelime varsa ve güçlü Türkçe karakter yoksa → İngilizce
    if english_count > 0 and not has_strong_turkish:
        return "en"

    # Güçlü Türkçe karakter varsa → Türkçe
    if has_strong_turkish:
        return "tr"

    # Sadece "ı" varsa ama İngilizce kelimeler de varsa → İngilizce (klavye hatası)
    if has_i_nodot and english_count > 0:
        return "en"

    if turkish_count > 0:
        return "tr"

    # Kısa ASCII mesajlar - selamlama kontrolü
    if t in ["hello", "hi", "hey", "yes", "no", "ok", "okay"]:
        return "en"

    # Varsayılan
    return "tr"

def detect_hotel(text: str) -> str:
    t = text.lower()
    if any(m in t for m in ["heritage", "villa", "daphne", "iris", "adonis", "flora", "gaia", "gardenia", "calla"]):
        return "heritage"
    return "boutique"

def detect_price_request(text: str, history: List[dict] = None) -> bool:
    t = text.lower().strip()
    
    short_price_questions = ["fiyat", "fiyat?", "fiyatı?", "fiyatı ne", "ne kadar", "kaç para", "price", "price?", "how much", "цена", "цена?", "сколько стоит", "стоимость"]
    
    if any(t == q or t == q + "?" for q in short_price_questions):
        if history:
            recent_text = " ".join([m.get("content", "").lower() for m in history[-4:]])
            if any(kw in recent_text for kw in ["transfer", "dalaman", "antalya", "havalimanı", "airport"]):
                return False
    
    price_words = ["fiyat", "ücret", "gecelik", "price", "how much", "rate", "цена", "стоимость", "сколько", "тариф"]
    date_words = MONTHS_TR + MONTHS_EN + MONTHS_RU
    guest_words = ["yetişkin", "çocuk", "kişi", "adult", "kid", "person", "взрослый", "взрослых", "ребёнок", "детей", "человек"]

    score = 0
    if any(w in t for w in price_words):
        score += 1
    if any(w in t for w in date_words):
        score += 1
    if any(w in t for w in guest_words) or re.search(r"\d+\s*(kişi|yetişkin|çocuk|adult|kid|person)", t):
        score += 1

    return score >= 2

def parse_guests(text: str):
    t = text.lower()
    adults, children = None, None

    m = re.search(r"(\d+)\s*yetişkin", t)
    if m: adults = int(m.group(1))
    m = re.search(r"(\d+)\s*çocuk", t)
    if m: children = int(m.group(1))
    m = re.search(r"(\d+)\s*adults?", t)
    if m and adults is None: adults = int(m.group(1))
    m = re.search(r"(\d+)\s*(kids?|children)", t)
    if m and children is None: children = int(m.group(1))
    # Rusça
    m = re.search(r"(\d+)\s*взрослы[хй]?", t)
    if m and adults is None: adults = int(m.group(1))
    m = re.search(r"(\d+)\s*(детей|ребёнок|ребенок|дет[иь])", t)
    if m and children is None: children = int(m.group(1))

    if adults is None and children is None:
        m = re.search(r"(\d+)\s*(kişi|person|people|человек|человека|гост[ейяь])", t)
        if m:
            adults = int(m.group(1))
            children = 0

    return adults, children

def extract_date_phrase(text: str) -> str:
    t = text.lower()
    for m in MONTHS_TR + MONTHS_EN + MONTHS_RU:
        idx = t.find(m)
        if idx != -1:
            return text[max(0, idx-20):min(len(text), idx+25)].strip()
    return "belirttiğiniz tarihler"


# ======================================================
# 11. FİYAT ŞABLONLARI
# ======================================================

TEMPLATE_BOUTIQUE_TR = """
Sayın {{müşteri ismi}},

Otelimize göstermiş olduğunuz ilgi için teşekkür ederiz. 

{{gecis_tarihi}} tarihleri arasında {{gece_sayisi}} gece kahvaltı dahil {{yetişkin}} yetişkin {{çocuk}} çocuk fiyatlarımız:

Deluxe (25m2): İade yapılmaz: {{deluxe_iade}} | Ücretsiz İptal: {{deluxe_ucretsiz}}
Superior (30m2): İade yapılmaz: {{superior_iade}} | Ücretsiz İptal: {{superior_ucretsiz}}
Exclusive Sokak (40m2): İade yapılmaz: {{exclusiveLand_iade}} | Ücretsiz İptal: {{exclusiveLand_ucretsiz}}
Penthouse Land Jakuzili (25m2): İade yapılmaz: {{penthouseLand_iade}} | Ücretsiz İptal: {{penthouseLand_ucretsiz}}
Exclusive Havuz (40m2): İade yapılmaz: {{exclusivePool_iade}} | Ücretsiz İptal: {{exclusivePool_ucretsiz}}
Penthouse Jakuzili (45m2): İade yapılmaz: {{penthouse_iade}} | Ücretsiz İptal: {{penthouse_ucretsiz}}
Premium Jakuzili (45m2): İade yapılmaz: {{premium_iade}} | Ücretsiz İptal: {{premium_ucretsiz}}

Giriş: 14:00 | Çıkış: 12:00
Ücretsiz iptal: Girişten 5 gün öncesine kadar %100 iade.
Rezervasyon onayı için 1 gecelik ödeme alınır.
"""

TEMPLATE_BOUTIQUE_EN = """
Dear {{müşteri ismi}},

Thank you for your interest in our hotel.

Prices for {{gecis_tarihi}}, {{gece_sayisi}} nights, {{yetişkin}} adults {{çocuk}} children (breakfast included):

Deluxe (25m2): Non-refundable: {{deluxe_iade}} | Free Cancel: {{deluxe_ucretsiz}}
Superior (30m2): Non-refundable: {{superior_iade}} | Free Cancel: {{superior_ucretsiz}}
Exclusive Street (40m2): Non-refundable: {{exclusiveLand_iade}} | Free Cancel: {{exclusiveLand_ucretsiz}}
Penthouse Land Jacuzzi (25m2): Non-refundable: {{penthouseLand_iade}} | Free Cancel: {{penthouseLand_ucretsiz}}
Exclusive Pool (40m2): Non-refundable: {{exclusivePool_iade}} | Free Cancel: {{exclusivePool_ucretsiz}}
Penthouse Jacuzzi (45m2): Non-refundable: {{penthouse_iade}} | Free Cancel: {{penthouse_ucretsiz}}
Premium Jacuzzi (45m2): Non-refundable: {{premium_iade}} | Free Cancel: {{premium_ucretsiz}}

Check-in: 2:00 PM | Check-out: 12:00 PM
Free cancellation: 100% refund up to 5 days before arrival.
"""

TEMPLATE_BOUTIQUE_RU = """
Уважаемый(ая) {{müşteri ismi}},

Благодарим вас за интерес к нашему отелю.

Цены на {{gecis_tarihi}}, {{gece_sayisi}} ночей, {{yetişkin}} взрослых {{çocuk}} детей (завтрак включён):

Deluxe (25м2): Без возврата: {{deluxe_iade}} | Бесплатная отмена: {{deluxe_ucretsiz}}
Superior (30м2): Без возврата: {{superior_iade}} | Бесплатная отмена: {{superior_ucretsiz}}
Exclusive Street (40м2): Без возврата: {{exclusiveLand_iade}} | Бесплатная отмена: {{exclusiveLand_ucretsiz}}
Penthouse Land Джакузи (25м2): Без возврата: {{penthouseLand_iade}} | Бесплатная отмена: {{penthouseLand_ucretsiz}}
Exclusive Pool (40м2): Без возврата: {{exclusivePool_iade}} | Бесплатная отмена: {{exclusivePool_ucretsiz}}
Penthouse Джакузи (45м2): Без возврата: {{penthouse_iade}} | Бесплатная отмена: {{penthouse_ucretsiz}}
Premium Джакузи (45м2): Без возврата: {{premium_iade}} | Бесплатная отмена: {{premium_ucretsiz}}

Заезд: 14:00 | Выезд: 12:00
Бесплатная отмена: 100% возврат до 5 дней до заезда.
"""

PRICE_PLACEHOLDERS = [
    "deluxe_iade", "deluxe_ucretsiz", "superior_iade", "superior_ucretsiz",
    "exclusiveLand_iade", "exclusiveLand_ucretsiz", "exclusivePool_iade", "exclusivePool_ucretsiz",
    "penthouseLand_iade", "penthouseLand_ucretsiz",
    "penthouse_iade", "penthouse_ucretsiz", "premium_iade", "premium_ucretsiz",
]

def build_price_reply(user_message: str) -> Tuple[str, str]:
    lang = detect_language(user_message)
    hotel = detect_hotel(user_message)
    adults, children = parse_guests(user_message)
    
    if lang == "ru":
        template = TEMPLATE_BOUTIQUE_RU
    elif lang == "en":
        template = TEMPLATE_BOUTIQUE_EN
    else:
        template = TEMPLATE_BOUTIQUE_TR
    
    reply = template
    reply = reply.replace("{{müşteri ismi}}", "{{müşteri ismi}}")
    reply = reply.replace("{{gecis_tarihi}}", extract_date_phrase(user_message))
    reply = reply.replace("{{gece_sayisi}}", "{{gece_sayisi}}")
    reply = reply.replace("{{yetişkin}}", str(adults) if adults else "{{yetişkin}}")
    reply = reply.replace("{{çocuk}}", str(children) if children else "{{çocuk}}")
    
    for key in PRICE_PLACEHOLDERS:
        reply = reply.replace("{{" + key + "}}", "___ €")
    
    reservation_log = f"PRICE_REQUEST: adults={adults}; children={children}; lang={lang}"
    return reply.strip(), reservation_log


# NOTE:
# Local FAQ data/functions are centralized in app/content/local_faq_data.py.
