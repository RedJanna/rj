import re
from typing import Optional

def extract_time_from_text(text: str) -> Optional[str]:
    msg_lower = (text or "").lower()

    # 1) 19:30 / 19.30 / 19h30
    m = re.search(r'\b(\d{1,2})\s*[:\.h]\s*(\d{2})\b', msg_lower)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"

    # 2) "8 buçuk", "8 buçukta", "8 bucuk", "8 bucukta" -> 08:30 (akşam bağlamı varsa 20:30)
    # FIX: (ta|te)? eklendi - "buçukta" kelimesini de yakala
    m = re.search(r'\b(\d{1,2})\s*(buçuk|bucuk)(ta|te)?\b', msg_lower)
    if m:
        hour = int(m.group(1))
        minute = 30
        if hour < 12 and any(w in msg_lower for w in ['akşam', 'aksam', 'evening', 'dinner', 'yemek', 'gece', 'night']):
            hour += 12
        if 0 <= hour <= 23:
            return f"{hour:02d}:{minute:02d}"

    # 3) "saat 8", "8'de", "akşam 7", "öğlen 1" vb.
    patterns = [
        r'saat\s*(\d{1,2})',
        r"(\d{1,2})\s*['\"′]?\s*(de|da|te|ta)",
        r'(\d{1,2})\s*(pm|am)',
        r'at\s*(\d{1,2})',
        r'akşam\s*(\d{1,2})',
        r'aksam\s*(\d{1,2})',
        r'gece\s*(\d{1,2})',
        r'night\s*(\d{1,2})',
        r'sabah\s*(\d{1,2})',
        r'öğle\s*(\d{1,2})',
        r'ogle\s*(\d{1,2})',
        r'öğlen\s*(\d{1,2})',
        r'oglen\s*(\d{1,2})',
        r'(\d{1,2})\s*gibi',
        r'(\d{1,2})\s*civarı',
        r'(\d{1,2})\s*sularında',
    ]

    for pattern in patterns:
        m = re.search(pattern, msg_lower)
        if not m:
            continue

        hour = int(m.group(1))

        if 'pm' in msg_lower and hour < 12:
            hour += 12
        elif 'am' in msg_lower and hour == 12:
            hour = 0

        if hour < 12 and any(w in msg_lower for w in ['akşam', 'aksam', 'evening', 'dinner', 'yemek', 'gece', 'night']):
            hour += 12

        if any(w in msg_lower for w in ['öğle', 'ogle', 'öğlen', 'oglen', 'lunch']):
            if 1 <= hour <= 11:
                hour += 12

        if 0 <= hour <= 23:
            return f"{hour:02d}:00"

    # 4) Son çare: sadece bağlam var (2 kişi gibi sayıları saat sanmasın)
    time_context = [
        'saat', 'time', 'at',
        'akşam', 'aksam', 'evening', 'dinner', 'yemek', 'gece', 'night',
        'öğle', 'ogle', 'öğlen', 'oglen', 'lunch',
        'sabah', 'morning', 'breakfast', 'kahvaltı'
    ]
    if any(w in msg_lower for w in time_context):
        clean = msg_lower

        clean = re.sub(r'\b\d{1,2}\s*(kişi|kisi|kişilik|people|person|persons|guests?)\b', ' ', clean)

        month_words = [
            'ocak','şubat','mart','nisan','mayıs','haziran','temmuz','ağustos','eylül','ekim','kasım','aralık',
            'january','february','march','april','may','june','july','august','september','october','november','december'
        ]
        clean = re.sub(r'\b(\d{1,2})\s*(' + '|'.join(month_words) + r')\b', ' ', clean)
        clean = re.sub(r'\b(' + '|'.join(month_words) + r')\s*(\d{1,2})\b', ' ', clean)

        nums = re.findall(r'\b(\d{1,2})\b', clean)
        if nums:
            hour = int(nums[-1])
            if 0 <= hour <= 23:
                if hour < 12 and any(w in msg_lower for w in ['akşam', 'aksam', 'evening', 'dinner', 'yemek', 'gece', 'night']):
                    hour += 12
                if any(w in msg_lower for w in ['öğle', 'ogle', 'öğlen', 'oglen', 'lunch']) and 1 <= hour <= 11:
                    hour += 12
                return f"{hour:02d}:00"

        if any(w in msg_lower for w in ['akşam', 'aksam', 'evening', 'dinner', 'yemek', 'gece', 'night']):
            return '19:30'
        if any(w in msg_lower for w in ['öğlen', 'oglen', 'öğle', 'ogle', 'lunch']):
            return '13:00'
        if any(w in msg_lower for w in ['sabah', 'morning', 'kahvaltı', 'breakfast']):
            return '10:00'

    return None
