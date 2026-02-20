"""
Sistem Test Routes
==================
Admin panelden sistem testlerini başlatma ve sonuçları görüntüleme endpoint'leri.

Endpoint'ler:
- GET  /admin/system-test/status     → Test durumu / son sonuçlar
- POST /admin/system-test/start      → Test başlat
- GET  /admin/system-test/results    → Test sonuçları listesi
- GET  /admin/system-test/report/{id}→ Belirli raporu getir
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime
from pathlib import Path
import json
import asyncio
import httpx
import time

router = APIRouter(prefix="/admin/system-test", tags=["System Test"])

# Konfigürasyon
BASE_URL = "http://localhost:8000"
TEST_ENDPOINT = "/admin/test-chat"
REPORTS_DIR = Path("tests/system_test/reports")
QUESTIONS_FILE = Path("tests/system_test/test_questions.json")

# Test durumu (in-memory)
test_state = {
    "is_running": False,
    "progress": 0,
    "total": 0,
    "current_category": "",
    "current_question": "",
    "started_at": None,
    "completed_at": None,
    "last_result_id": None
}


class TestStartRequest(BaseModel):
    categories: Optional[List[str]] = None  # None = tümü


class TestProgress(BaseModel):
    is_running: bool
    progress: int
    total: int
    percentage: float
    current_category: str
    current_question: str
    started_at: Optional[str]
    elapsed_seconds: Optional[float]


# === YARDIMCI FONKSİYONLAR ===

def load_questions() -> Dict:
    """Test sorularını yükle"""
    if not QUESTIONS_FILE.exists():
        raise HTTPException(status_code=404, detail="Test soruları dosyası bulunamadı")
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate_response(question: str, response: str) -> Dict:
    """Yanıtı değerlendir"""
    response_lower = response.lower()
    flags = []
    score = 50
    
    quality_keywords = {
        "positive": ["evet", "tabii", "mümkün", "var", "yapabiliriz"],
        "error": ["hata", "error", "üzgünüm", "anlayamadım"]
    }
    
    if len(response) < 20:
        flags.append("TOO_SHORT")
        score -= 20
    elif len(response) > 100:
        score += 10
    
    for kw in quality_keywords["positive"]:
        if kw in response_lower:
            flags.append("POSITIVE_TONE")
            score += 5
            break
    
    for kw in quality_keywords["error"]:
        if kw in response_lower:
            flags.append("ERROR_INDICATOR")
            score -= 15
            break
    
    if "?" in response:
        flags.append("ASKS_FOLLOWUP")
        score += 5
    
    turkish_chars = set("çğıöşüÇĞİÖŞÜ")
    if any(c in response for c in turkish_chars):
        flags.append("TURKISH_OK")
        score += 5
    
    score = max(0, min(100, score))
    return {"score": score, "flags": flags}


async def run_single_test(client: httpx.AsyncClient, phone: str, question: str, category: str) -> Dict:
    """Tek test çalıştır"""
    start_time = time.time()
    
    try:
        response = await client.post(
            f"{BASE_URL}{TEST_ENDPOINT}",
            params={"phone": phone, "message": question},
            timeout=30.0
        )
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            bot_response = data.get("response", "")
            response_source = data.get("response_source", "UNKNOWN")
            quality = evaluate_response(question, bot_response)
            
            return {
                "status": "success",
                "question": question,
                "category": category,
                "response": bot_response,
                "response_source": response_source,
                "response_time": round(elapsed, 3),
                "response_length": len(bot_response),
                "quality_score": quality["score"],
                "quality_flags": quality["flags"],
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "http_error",
                "question": question,
                "category": category,
                "response": f"HTTP {response.status_code}",
                "response_source": "ERROR",
                "response_time": round(elapsed, 3),
                "response_length": 0,
                "quality_score": 0,
                "quality_flags": ["HTTP_ERROR"],
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "status": "exception",
            "question": question,
            "category": category,
            "response": str(e),
            "response_source": "ERROR",
            "response_time": round(elapsed, 3),
            "response_length": 0,
            "quality_score": 0,
            "quality_flags": ["EXCEPTION"],
            "timestamp": datetime.now().isoformat()
        }


async def run_tests_background(categories: Optional[List[str]] = None):
    """Arka planda test çalıştır"""
    global test_state
    
    test_state["is_running"] = True
    test_state["started_at"] = datetime.now().isoformat()
    test_state["progress"] = 0
    
    try:
        questions_data = load_questions()
        
        # Kategori filtresi
        if categories:
            filtered_cats = {k: v for k, v in questions_data["categories"].items() if k in categories}
        else:
            filtered_cats = questions_data["categories"]
        
        # Toplam soru sayısı
        total_questions = sum(len(cat["questions"]) for cat in filtered_cats.values())
        test_state["total"] = total_questions
        
        results = {
            "metadata": {
                "test_date": datetime.now().isoformat(),
                "base_url": BASE_URL,
                "total_categories": len(filtered_cats),
                "total_questions": 0,
                "total_success": 0,
                "total_errors": 0,
                "avg_response_time": 0,
                "avg_quality_score": 0
            },
            "categories": {},
            "all_results": []
        }
        
        total_time = 0
        total_score = 0
        question_count = 0
        
        async with httpx.AsyncClient() as client:
            for cat_key, cat_data in filtered_cats.items():
                cat_results = []
                cat_name = cat_data["name_tr"]
                questions = cat_data["questions"]
                
                test_state["current_category"] = cat_name
                
                for i, question in enumerate(questions):
                    question_count += 1
                    test_state["progress"] = question_count
                    test_state["current_question"] = question[:50]
                    
                    phone = f"TEST_{cat_key.upper()}_{i:03d}"
                    result = await run_single_test(client, phone, question, cat_key)
                    
                    cat_results.append(result)
                    results["all_results"].append(result)
                    
                    if result["status"] == "success":
                        results["metadata"]["total_success"] += 1
                    else:
                        results["metadata"]["total_errors"] += 1
                    
                    total_time += result["response_time"]
                    total_score += result["quality_score"]
                    
                    await asyncio.sleep(0.1)
                
                results["categories"][cat_key] = {
                    "name": cat_name,
                    "total": len(questions),
                    "success": sum(1 for r in cat_results if r["status"] == "success"),
                    "avg_time": round(sum(r["response_time"] for r in cat_results) / len(cat_results), 3),
                    "avg_score": round(sum(r["quality_score"] for r in cat_results) / len(cat_results), 1),
                    "results": cat_results
                }
        
        # Metrikler
        results["metadata"]["total_questions"] = question_count
        results["metadata"]["avg_response_time"] = round(total_time / question_count, 3) if question_count > 0 else 0
        results["metadata"]["avg_quality_score"] = round(total_score / question_count, 1) if question_count > 0 else 0
        
        # Kaydet
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_file = REPORTS_DIR / f"test_results_{timestamp}.json"
        
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        test_state["last_result_id"] = timestamp
        test_state["completed_at"] = datetime.now().isoformat()
        
    except Exception as e:
        print(f"❌ Test hatası: {e}")
    finally:
        test_state["is_running"] = False
        test_state["current_category"] = ""
        test_state["current_question"] = ""


# === ENDPOINT'LER ===

@router.get("/status")
async def get_test_status():
    """Test durumunu getir"""
    elapsed = None
    if test_state["started_at"] and test_state["is_running"]:
        start = datetime.fromisoformat(test_state["started_at"])
        elapsed = (datetime.now() - start).total_seconds()
    
    percentage = 0
    if test_state["total"] > 0:
        percentage = round(test_state["progress"] / test_state["total"] * 100, 1)
    
    return {
        "is_running": test_state["is_running"],
        "progress": test_state["progress"],
        "total": test_state["total"],
        "percentage": percentage,
        "current_category": test_state["current_category"],
        "current_question": test_state["current_question"],
        "started_at": test_state["started_at"],
        "elapsed_seconds": elapsed,
        "last_result_id": test_state["last_result_id"]
    }


@router.post("/start")
async def start_test(request: TestStartRequest, background_tasks: BackgroundTasks):
    """Test başlat"""
    if test_state["is_running"]:
        raise HTTPException(status_code=409, detail="Test zaten çalışıyor")
    
    background_tasks.add_task(run_tests_background, request.categories)
    
    return {
        "status": "started",
        "message": "Test arka planda başlatıldı",
        "categories": request.categories or "all"
    }


@router.get("/results")
async def list_results():
    """Mevcut test sonuçlarını listele"""
    if not REPORTS_DIR.exists():
        return {"results": []}
    
    results = []
    for f in sorted(REPORTS_DIR.glob("test_results_*.json"), reverse=True):
        try:
            with open(f, "r", encoding="utf-8") as file:
                data = json.load(file)
                results.append({
                    "id": f.stem.replace("test_results_", ""),
                    "date": data["metadata"]["test_date"],
                    "total_questions": data["metadata"]["total_questions"],
                    "success": data["metadata"]["total_success"],
                    "errors": data["metadata"]["total_errors"],
                    "avg_score": data["metadata"]["avg_quality_score"]
                })
        except:
            continue
    
    return {"results": results[:20]}  # Son 20 sonuç


@router.get("/report/{result_id}")
async def get_report(result_id: str, format: str = "json"):
    """Belirli bir test raporunu getir"""
    result_file = REPORTS_DIR / f"test_results_{result_id}.json"
    
    if not result_file.exists():
        raise HTTPException(status_code=404, detail="Rapor bulunamadı")
    
    if format == "file":
        return FileResponse(result_file, filename=f"test_results_{result_id}.json")
    
    with open(result_file, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/categories")
async def list_categories():
    """Mevcut test kategorilerini listele"""
    questions_data = load_questions()
    
    categories = []
    for key, data in questions_data["categories"].items():
        categories.append({
            "key": key,
            "name": data["name_tr"],
            "question_count": len(data["questions"])
        })
    
    return {"categories": categories}
