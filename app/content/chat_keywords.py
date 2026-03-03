PRICE_NATURAL_DATE_KEYWORDS = [
    "ocak", "subat", "şubat", "mart", "nisan", "mayis", "mayıs",
    "haziran", "temmuz", "agustos", "ağustos", "eylul", "eylül",
    "ekim", "kasim", "kasım", "aralik", "aralık",
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
    # Rusça aylar
    "январь", "февраль", "март", "апрель", "май", "июнь",
    "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
    # Almanca aylar
    "januar", "februar", "marz", "märz", "april", "mai", "juni",
    "juli", "august", "september", "oktober", "november", "dezember",
    # İspanyolca aylar
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    # Fransızca aylar
    "janvier", "fevrier", "février", "mars", "avril", "mai", "juin",
    "juillet", "aout", "août", "septembre", "octobre", "novembre", "decembre", "décembre",
    # Portekizce aylar
    "janeiro", "fevereiro", "marco", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
    # Arapça aylar
    "يناير", "فبراير", "مارس", "أبريل", "ابريل", "مايو", "يونيو",
    "يوليو", "أغسطس", "اغسطس", "سبتمبر", "أكتوبر", "اكتوبر", "نوفمبر", "ديسمبر",
    # Hintçe aylar
    "जनवरी", "फ़रवरी", "फरवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई",
    "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर",
    # Çince tarih sinyalleri
    "年", "月", "日",
]

PRICE_INQUIRY_KEYWORDS = [
    "müsait", "musait", "müsaitlik", "musaitlik", "uygun", "boş", "bos",
    "fiyat", "ücret", "ucret", "price", "cost", "available", "availability",
    "kaç para", "kac para", "ne kadar", "giriş", "giris", "çıkış", "cikis",
    # Rusça
    "цена", "стоимость", "сколько стоит", "свободно", "наличие", "заезд", "выезд",
    # Almanca
    "preis", "kosten", "verfugbar", "verfügbar", "verfugbarkeit", "verfügbarkeit", "anreise", "abreise",
    # İspanyolca
    "precio", "coste", "disponible", "disponibilidad", "entrada", "salida",
    # Fransızca
    "prix", "disponible", "disponibilite", "disponibilité", "arrivee", "arrivée", "depart", "départ",
    # Portekizce
    "preco", "preço", "disponivel", "disponível", "disponibilidade", "entrada", "saida", "saída",
    # Arapça
    "السعر", "تكلفة", "الاجمالي", "الإجمالي", "المجموع", "متاح", "التوفر", "حجز", "دخول", "خروج",
    # Hintçe
    "कीमत", "कुल", "कुल कीमत", "मूल्य", "दर", "उपलब्ध", "उपलब्धता", "चेक-इन", "चेक-आउट",
    # Çince
    "价格", "总价", "费用", "多少钱", "可用", "空房", "入住", "退房",
]

PRICE_GUEST_KEYWORDS = [
    "kişi", "kisi", "yetişkin", "yetiskin", "adult", "people", "guest", "çocuk", "cocuk", "child",
    # Rusça
    "человек", "взрослый", "взрослых", "гость", "гостей", "ребёнок", "детей",
    # Almanca
    "gast", "gaste", "gäste", "erwachsene", "kind", "kinder",
    # İspanyolca
    "huesped", "huésped", "huespedes", "huéspedes", "adulto", "adultos", "nino", "niño", "ninos", "niños",
    # Fransızca
    "client", "clients", "adulte", "adultes", "enfant", "enfants",
    # Portekizce
    "hospede", "hóspede", "hospedes", "hóspedes", "adulto", "adultos", "crianca", "criança", "criancas", "crianças",
    # Arapça
    "شخص", "أشخاص", "اشخاص", "بالغ", "بالغين", "ضيف", "ضيوف", "طفل", "أطفال", "اطفال",
    # Hintçe
    "वयस्क", "वयस्कों", "मेहमान", "अतिथि", "बच्चा", "बच्चों", "व्यक्ति",
    # Çince
    "成人", "大人", "儿童", "小孩", "位",
]

CANONICAL_GREETING_KEYWORDS = [
    "merhaba", "merhabalar", "selam", "selamlar", "hello", "hi", "hey", "slm", "mrb", "hii", "hiii",
    # Rusça
    "привет", "здравствуйте", "здравствуй", "приветик",
]

KANONIK_FIYAT_EXCLUSIONS = [
    "fiyat farkı", "fiyat farki", "fark nedir", "fark ne kadar",
    "arasında fark", "arasindaki fark", "arasında fiyat",
    "hangisi daha", "hangisi ucuz", "hangisi pahalı", "hangisi pahali",
    "ne fark var", "farkı ne", "farki ne",
    "oda tipleri", "oda tipi", "oda çeşit", "oda cesit",
    "odalar arasında", "odalar arasindaki",
    "varsa fiyat", "varsa ücret", "varsa ucret",
    "var mı fiyat", "var mi fiyat",
    "aile odası", "aile odasi", "family room", "family suite",
    "bağlantılı oda", "baglantili oda", "connecting room", "adjoining room",
    "deniz manzaralı", "deniz manzarali", "sea view", "ocean view",
    "jakuzili oda", "jacuzzi room",
    "ek ücret", "ek ucret", "extra charge",
    "dahil mi", "dahil mı", "included", "fiyata dahil",
    "price difference", "cost difference", "difference between",
    "compare", "comparison", "which is cheaper", "which is more expensive",
    "do you have", "is there", "are there",
    "otopark", "park yeri", "vale", "parking",
    "transfer", "havalimanı", "havaalani", "shuttle",
    "spa", "masaj", "massage", "hamam", "sauna",
    "restoran", "yemek", "kahvaltı", "kahvalti",
    "minibar", "çamaşırhane", "laundry",
    "ek yatak", "extra bed", "bebek beşiği", "bebek yatağı", "cot", "crib",
    "yarım pansiyon", "tam pansiyon", "half board", "full board", "all inclusive",
    "havuz", "pool", "plaj", "beach",
    "tekne", "boat", "aktivite", "bisiklet",
    "wifi", "internet",
    "iptal", "iade", "cancel", "refund",
    "politika", "policy", "koşul", "şart", "kural",
    "kdv", "vergi", "tax",
    "ödeme", "taksit", "kredi kartı", "nakit",
    "çocuk", "bebek", "child", "infant",
    "evcil hayvan", "pet",
    "sigara", "smoking",
    "fiyat değişir", "fiyat değişiyor", "fiyat artış", "fiyat garanti",
]

ERKEN_GIRIS_KEYWORDS = [
    "erken giriş", "erken giris", "erken check-in", "erken check in", "early check-in", "early check in", "early checkin",
]

GEC_CIKIS_KEYWORDS = [
    "geç çıkış", "gec cikis", "geç check-out", "geç check out", "late check-out", "late check out", "late checkout",
]
