PRICE_NATURAL_DATE_KEYWORDS = [
    "ocak", "subat", "şubat", "mart", "nisan", "mayis", "mayıs",
    "haziran", "temmuz", "agustos", "ağustos", "eylul", "eylül",
    "ekim", "kasim", "kasım", "aralik", "aralık",
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
    # Rusça aylar
    "январь", "февраль", "март", "апрель", "май", "июнь",
    "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
]

PRICE_INQUIRY_KEYWORDS = [
    "müsait", "musait", "müsaitlik", "musaitlik", "uygun", "boş", "bos",
    "fiyat", "ücret", "ucret", "price", "cost", "available", "availability",
    "kaç para", "kac para", "ne kadar", "giriş", "giris", "çıkış", "cikis",
    # Rusça
    "цена", "стоимость", "сколько стоит", "свободно", "наличие", "заезд", "выезд",
]

PRICE_GUEST_KEYWORDS = [
    "kişi", "kisi", "yetişkin", "yetiskin", "adult", "people", "guest", "çocuk", "cocuk", "child",
    # Rusça
    "человек", "взрослый", "взрослых", "гость", "гостей", "ребёнок", "детей",
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
