from __future__ import annotations

import json
import os
from datetime import datetime


class QAAgentService:
    """Bot cevap kalitesini OpenAI ile değerlendiren servis."""

    def __init__(self, openai_client, model: str, log_file: str):
        self._client = openai_client
        self._model = model
        self._log_file = log_file
        self.evaluations = []
        self._load_evaluations()

    def _load_evaluations(self):
        try:
            if os.path.exists(self._log_file):
                with open(self._log_file, "r", encoding="utf-8") as f:
                    self.evaluations = json.load(f)
        except Exception as e:
            print(f"QA log yükleme hatası: {e}")
            self.evaluations = []

    def _save_evaluations(self):
        try:
            os.makedirs(os.path.dirname(self._log_file), exist_ok=True)
            recent = self.evaluations[-500:] if len(self.evaluations) > 500 else self.evaluations
            with open(self._log_file, "w", encoding="utf-8") as f:
                json.dump(recent, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"QA log kaydetme hatası: {e}")

    async def evaluate(self, user_message: str, bot_reply: str, phone: str = None) -> dict:
        eval_prompt = f"""Sen bir otel chatbot'unun cevap kalitesini değerlendiren QA uzmanısın.

KULLANICI MESAJI:
{user_message}

BOT CEVABI:
{bot_reply}

OTEL BİLGİLERİ (Doğrulama için):
- Otel: Kassandra Ölüdeniz, Fethiye
- Havuz: Var, ısıtmalı değil
- Kahvaltı: Açık büfe, 08:00-10:30
- Check-in: 14:00, Check-out: 12:00
- Transfer: Dalaman havalimanı 60km, ücretli
- Restoran: Akşam yemeği ayrı ücret

DEĞERLENDİRME KRİTERLERİ:
1. groundedness (0-5): Cevap gerçek bilgilere mi dayanıyor?
2. correctness (0-5): Bilgiler doğru mu?
3. completeness (0-5): Soru tam cevaplandı mı?
4. clarity (0-5): Cevap anlaşılır mı?

SADECE JSON FORMATINDA CEVAP VER, başka hiçbir şey yazma:
{{
    "scores": {{
        "groundedness": <0-5>,
        "correctness": <0-5>,
        "completeness": <0-5>,
        "clarity": <0-5>
    }},
    "overall_score": <0-5 ortalama>,
    "issues": ["tespit edilen sorunlar"],
    "suggestions": ["iyileştirme önerileri"],
    "hallucinations": ["uydurma/yanlış bilgiler varsa"],
    "decision": "<PASS|REVIEW|FAIL>"
}}

Karar kriterleri:
- PASS: overall >= 4
- REVIEW: overall 2.5-4 arası
- FAIL: overall < 2.5"""

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": eval_prompt}],
                temperature=0.1,
                max_tokens=500,
            )

            result_text = response.choices[0].message.content.strip()
            if result_text.startswith("```"):
                result_text = result_text.split("```")[1]
                if result_text.startswith("json"):
                    result_text = result_text[4:]

            evaluation = json.loads(result_text)
            record = {
                "timestamp": datetime.now().isoformat(),
                "phone": phone[:6] + "***" if phone else None,
                "user_message": user_message[:200],
                "bot_reply": bot_reply[:500],
                "evaluation": evaluation,
            }
            self.evaluations.append(record)
            self._save_evaluations()
            print(f"🔍 QA: {evaluation['decision']} (Skor: {evaluation['overall_score']})")
            return evaluation
        except Exception as e:
            print(f"❌ QA değerlendirme hatası: {e}")
            return {
                "scores": {"groundedness": 0, "correctness": 0, "completeness": 0, "clarity": 0},
                "overall_score": 0,
                "issues": [f"Değerlendirme hatası: {str(e)}"],
                "suggestions": [],
                "hallucinations": [],
                "decision": "ERROR",
            }

    def get_stats(self) -> dict:
        if not self.evaluations:
            return {"total": 0, "pass": 0, "review": 0, "fail": 0, "avg_score": 0}
        decisions = [e["evaluation"]["decision"] for e in self.evaluations if "evaluation" in e]
        scores = [
            e["evaluation"]["overall_score"]
            for e in self.evaluations
            if "evaluation" in e and "overall_score" in e["evaluation"]
        ]
        return {
            "total": len(self.evaluations),
            "pass": decisions.count("PASS"),
            "review": decisions.count("REVIEW"),
            "fail": decisions.count("FAIL"),
            "error": decisions.count("ERROR"),
            "avg_score": round(sum(scores) / len(scores), 2) if scores else 0,
        }

    def get_recent(self, limit: int = 20) -> list:
        return self.evaluations[-limit:][::-1]

    def get_failures(self, limit: int = 10) -> list:
        failures = [e for e in self.evaluations if e.get("evaluation", {}).get("decision") == "FAIL"]
        return failures[-limit:][::-1]
