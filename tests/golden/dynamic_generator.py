"""
Dynamic Question Generator
==========================

ChatGPT kullanarak dinamik test soruları üretir.
Golden test kapsamını genişletmek için kullanılır.
"""

import json
import random
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from openai import OpenAI


# Soru üretme kategorileri
QUESTION_PROMPTS = {
    "bilgi": """Sen bir otel müşterisisin. Kassandra Hotel Ölüdeniz hakkında bilgi almak istiyorsun.
Aşağıdaki konulardan BİRİ hakkında doğal, gerçekçi bir soru sor:
- Kahvaltı saatleri ve içeriği
- Check-in/check-out saatleri
- Havuz ve plaj bilgisi
- WiFi ve internet
- Otopark
- Çocuk olanakları
- Restoran saatleri

KURALLAR:
- Sadece 1 soru sor
- Türkçe veya İngilizce olabilir
- Gerçek bir müşteri gibi yaz (kısa, doğal)
- Sadece soruyu yaz, başka bir şey yazma.""",

    "fiyat": """Sen bir otel müşterisisin. Kassandra Hotel Ölüdeniz'de fiyatlar hakkında bilgi almak istiyorsun.
Aşağıdaki konulardan BİRİ hakkında doğal bir soru sor:
- Oda fiyatları
- Kahvaltı dahil mi
- İndirim var mı
- Çocuk ücreti
- Transfer ücreti

KURALLAR:
- Sadece 1 soru sor
- Gerçek bir müşteri gibi yaz
- Sadece soruyu yaz.""",

    "rezervasyon": """Sen bir otel veya restoran rezervasyonu yapmak isteyen müşterisin.
Kassandra Hotel'de rezervasyon yapmak istiyorsun. Doğal bir şekilde rezervasyon talebi yaz.

ÖRNEKLER:
- "4 kişilik oda var mı 15 Temmuz için"
- "Yarın akşam restoranda masa ayırtmak istiyorum"
- "3 gece kalacağız, müsait oda var mı"

KURALLAR:
- Sadece 1 mesaj yaz
- Farklı kişi sayıları, tarihler kullan
- Sadece mesajı yaz.""",

    "transfer": """Sen Kassandra Hotel'e gelmek isteyen bir müşterisin.
Havalimanı transferi hakkında soru sor.

KONULAR:
- Transfer ücreti
- Dalaman havalimanı mesafesi
- Transfer nasıl ayarlanır

Sadece soruyu yaz."""
}


# Müşteri tonları
CUSTOMER_TONES = [
    "resmi ve kibar",
    "samimi ve arkadaşça",
    "kısa ve öz",
    "detaylı soran",
    "acele eden"
]


class DynamicQuestionGenerator:
    """Dinamik soru üretici"""
    
    def __init__(self, openai_client: OpenAI = None):
        self.client = openai_client
        self.generated_questions = []
    
    def generate(self, category: str = None, count: int = 3) -> List[Dict]:
        """
        Dinamik sorular üret.
        
        Args:
            category: Soru kategorisi (None ise rastgele)
            count: Üretilecek soru sayısı
            
        Returns:
            Soru listesi
        """
        if not self.client:
            print("⚠️ OpenAI client yok, dinamik soru üretilemedi")
            return []
        
        questions = []
        categories = list(QUESTION_PROMPTS.keys())
        
        for i in range(count):
            try:
                cat = category or random.choice(categories)
                tone = random.choice(CUSTOMER_TONES)
                
                prompt = QUESTION_PROMPTS.get(cat, QUESTION_PROMPTS["bilgi"])
                prompt += f"\n\nMüşteri tonu: {tone}"
                
                completion = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "Sen bir otel müşterisi simülatörüsün."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=100,
                    temperature=0.9
                )
                
                question_text = completion.choices[0].message.content.strip()
                
                # Soru objesi oluştur
                question = {
                    "id": f"dynamic_{cat}_{i}_{datetime.now().strftime('%H%M%S')}",
                    "category": cat,
                    "question": question_text,
                    "expected_keywords": self._get_expected_keywords(cat),
                    "forbidden_keywords": [],
                    "description": f"Dinamik soru - {cat} - {tone}",
                    "is_core": False,
                    "generated_at": datetime.now().isoformat(),
                    "tone": tone
                }
                
                questions.append(question)
                
            except Exception as e:
                print(f"❌ Soru üretme hatası: {e}")
        
        self.generated_questions.extend(questions)
        return questions
    
    def _get_expected_keywords(self, category: str) -> List[str]:
        """Kategoriye göre beklenen keyword'ler"""
        keywords_map = {
            "bilgi": ["Kassandra", "Ölüdeniz", "otel"],
            "fiyat": ["€", "fiyat", "ücret", "euro"],
            "rezervasyon": ["tarih", "kişi", "saat", "rezervasyon"],
            "transfer": ["transfer", "€", "havalimanı", "Dalaman"]
        }
        return keywords_map.get(category, [])
    
    def save(self, file_path: Path = None):
        """Üretilen soruları kaydet"""
        if file_path is None:
            file_path = Path(__file__).parent / "scenarios" / "dynamic_questions.json"
        
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        existing = []
        if file_path.exists():
            try:
                existing = json.loads(file_path.read_text(encoding="utf-8"))
            except:
                pass
        
        # Yeni soruları ekle (max 100 tut)
        all_questions = existing + self.generated_questions
        all_questions = all_questions[-100:]
        
        file_path.write_text(
            json.dumps(all_questions, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        
        print(f"✅ {len(self.generated_questions)} dinamik soru kaydedildi")
    
    def load(self, file_path: Path = None) -> List[Dict]:
        """Kaydedilmiş dinamik soruları yükle"""
        if file_path is None:
            file_path = Path(__file__).parent / "scenarios" / "dynamic_questions.json"
        
        if not file_path.exists():
            return []
        
        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except:
            return []