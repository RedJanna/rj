"""
Golden Test Evaluator
=====================

Senaryo bazlı test değerlendirme yardımcıları.
Keyword matching, scoring ve raporlama.
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Any, Tuple
from datetime import datetime


class GoldenEvaluator:
    """Golden test değerlendirici"""
    
    # Keyword alias'ları (eşanlamlılar)
    KEYWORD_ALIASES = {
        "var": ["var", "mevcut", "mevcuttur", "bulunur", "bulunmaktadır", "evet"],
        "euro": ["euro", "eur", "€"],
        "€": ["€", "euro", "eur"],
        "dahil": ["dahil", "included", "içinde", "içerir"],
        "ücretsiz": ["ücretsiz", "free", "bedava", "parasız"],
    }
    
    def __init__(self):
        self.results = []
    
    def normalize_text(self, text: str) -> str:
        """Metni normalize et (küçük harf, fazla boşluk temizle)"""
        if not text:
            return ""
        
        # Türkçe büyük harfleri özel olarak küçük harfe çevir
        # İ → i (Türkçe büyük İ)
        # I → ı (Türkçe büyük I, ASCII I değil)
        text = text.replace('İ', 'i').replace('I', 'ı')
        
        # Küçük harf (geri kalan karakterler için)
        text = text.lower()
        
        # Fazla boşlukları temizle
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def check_keyword(self, response: str, keyword: str) -> bool:
        """
        Keyword'ün response içinde olup olmadığını kontrol et.
        Alias'ları da kontrol eder.
        """
        response_norm = self.normalize_text(response)
        keyword_norm = self.normalize_text(keyword)
        
        # Direkt kontrol
        if keyword_norm in response_norm:
            return True
        
        # Alias kontrolü
        aliases = self.KEYWORD_ALIASES.get(keyword_norm, [keyword_norm])
        for alias in aliases:
            if self.normalize_text(alias) in response_norm:
                return True
        
        return False
    
    def evaluate(self, response: str, scenario: Dict[str, Any]) -> Dict[str, Any]:
        """
        Bir senaryoyu değerlendir.
        
        Args:
            response: Bot'un cevabı
            scenario: Test senaryosu
            
        Returns:
            {
                "scenario_id": str,
                "decision": "PASS" | "FAIL" | "REVIEW",
                "score": float (0-1),
                "found_expected": list,
                "missing_expected": list,
                "found_forbidden": list,
                "description": str,
                "response_preview": str
            }
        """
        expected = scenario.get("expected_keywords", [])
        forbidden = scenario.get("forbidden_keywords", [])
        
        # Expected keyword'leri kontrol et
        found_expected = []
        missing_expected = []
        
        for kw in expected:
            if self.check_keyword(response, kw):
                found_expected.append(kw)
            else:
                missing_expected.append(kw)
        
        # Forbidden keyword'leri kontrol et
        found_forbidden = []
        for kw in forbidden:
            if self.check_keyword(response, kw):
                found_forbidden.append(kw)
        
        # Skor hesapla
        expected_count = len(expected)
        if expected_count > 0:
            expected_score = len(found_expected) / expected_count
        else:
            expected_score = 1.0
        
        # Forbidden penalty
        forbidden_penalty = len(found_forbidden) * 0.3
        final_score = max(0, expected_score - forbidden_penalty)
        
        # Karar
        if final_score >= 0.7 and len(found_forbidden) == 0:
            decision = "PASS"
        elif final_score >= 0.4:
            decision = "REVIEW"
        else:
            decision = "FAIL"
        
        return {
            "scenario_id": scenario.get("id", "unknown"),
            "category": scenario.get("category", ""),
            "question": scenario.get("question", ""),
            "decision": decision,
            "score": round(final_score, 2),
            "found_expected": found_expected,
            "missing_expected": missing_expected,
            "found_forbidden": found_forbidden,
            "description": scenario.get("description", ""),
            "is_core": scenario.get("is_core", True),
            "language": scenario.get("language", "tr"),
            "response_preview": response[:200] if response else ""
        }
    
    def evaluate_batch(self, responses: Dict[str, str], scenarios: List[Dict]) -> Dict[str, Any]:
        """
        Birden fazla senaryoyu değerlendir.
        
        Args:
            responses: {scenario_id: response} dict
            scenarios: Senaryo listesi
            
        Returns:
            Test sonuç raporu
        """
        results = []
        passed = 0
        failed = 0
        review = 0
        
        for scenario in scenarios:
            scenario_id = scenario.get("id")
            response = responses.get(scenario_id, "")
            
            result = self.evaluate(response, scenario)
            results.append(result)
            
            if result["decision"] == "PASS":
                passed += 1
            elif result["decision"] == "FAIL":
                failed += 1
            else:
                review += 1
        
        total = len(scenarios)
        pass_rate = round((passed / total) * 100, 1) if total > 0 else 0
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total": total,
            "passed": passed,
            "failed": failed,
            "review": review,
            "pass_rate": pass_rate,
            "results": results
        }
    
    def format_report(self, test_result: Dict[str, Any]) -> str:
        """Test sonucunu okunabilir rapor formatına çevir"""
        
        report = f"""
═══════════════════════════════════════════════════════════
                    GOLDEN TEST RAPORU
═══════════════════════════════════════════════════════════
📅 Tarih: {test_result.get('timestamp', 'N/A')}

📊 ÖZET
───────────────────────────────────────────────────────────
✅ Başarılı  : {test_result.get('passed', 0)}/{test_result.get('total', 0)}
❌ Başarısız : {test_result.get('failed', 0)}/{test_result.get('total', 0)}
🔍 İnceleme  : {test_result.get('review', 0)}/{test_result.get('total', 0)}
📈 Başarı    : %{test_result.get('pass_rate', 0)}
───────────────────────────────────────────────────────────

"""
        # Başarısız ve Review olanları listele
        problem_results = [r for r in test_result.get("results", []) 
                          if r.get("decision") in ["FAIL", "REVIEW"]]
        
        if problem_results:
            report += "❌ SORUNLU TESTLER\n"
            report += "───────────────────────────────────────────────────────────\n"
            
            for r in problem_results:
                emoji = "❌" if r["decision"] == "FAIL" else "🔍"
                core_badge = "🔒" if r.get("is_core") else "🔓"
                
                report += f"""
{emoji} {core_badge} {r['scenario_id']} [{r['decision']}]
   📝 {r.get('description', '')}
   ❓ Soru: {r.get('question', '')[:50]}
   💬 Cevap: {r.get('response_preview', '')[:80]}...
"""
                if r.get("missing_expected"):
                    report += f"   ⚠️ Eksik: {', '.join(r['missing_expected'][:5])}\n"
                if r.get("found_forbidden"):
                    report += f"   🚫 Yasak: {', '.join(r['found_forbidden'])}\n"
        
        report += "\n═══════════════════════════════════════════════════════════\n"
        
        return report


def load_scenarios(file_path: Path = None) -> List[Dict]:
    """Senaryo dosyasını yükle"""
    if file_path is None:
        file_path = Path(__file__).parent / "scenarios" / "core_scenarios.json"
    
    if not file_path.exists():
        return []
    
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return data.get("scenarios", [])
    except Exception as e:
        print(f"Senaryo yükleme hatası: {e}")
        return []


def save_results(results: Dict[str, Any], file_path: Path = None):
    """Test sonuçlarını kaydet"""
    if file_path is None:
        file_path = Path(__file__).parent.parent / "reports" / "golden_results.json"
    
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
