"""
Pytest Routes - Test API Endpoint'leri
======================================
Admin paneli için pytest test yönetimi.
"""

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import subprocess
import json
import os
import asyncio
from pathlib import Path

router = APIRouter(prefix="/admin/pytest", tags=["pytest"])

# Test sonuçları cache
_last_test_result = {
    "timestamp": None,
    "running": False,
    "summary": None,
    "tests": [],
    "passed": 0,
    "failed": 0,
    "total": 0,
    "duration": 0,
    "output": ""
}

TESTS_DIR = Path("tests")


def parse_pytest_output(output: str) -> dict:
    """pytest çıktısını parse et"""
    lines = output.split("\n")
    tests = []
    passed = 0
    failed = 0
    
    for line in lines:
        if "PASSED" in line:
            passed += 1
            # test_file.py::test_name PASSED
            parts = line.split(" ")
            if parts:
                test_name = parts[0].split("::")[-1] if "::" in parts[0] else parts[0]
                tests.append({"name": test_name, "status": "passed", "icon": "✅"})
        elif "FAILED" in line:
            failed += 1
            parts = line.split(" ")
            if parts:
                test_name = parts[0].split("::")[-1] if "::" in parts[0] else parts[0]
                tests.append({"name": test_name, "status": "failed", "icon": "❌"})
    
    return {
        "tests": tests[-20:],  # Son 20 test
        "passed": passed,
        "failed": failed,
        "total": passed + failed
    }


async def run_pytest_async(test_path: str = None, verbose: bool = True):
    """pytest'i async olarak çalıştır"""
    global _last_test_result
    
    _last_test_result["running"] = True
    _last_test_result["timestamp"] = datetime.now().isoformat()
    
    try:
        cmd = ["python", "-m", "pytest"]
        
        if test_path:
            cmd.append(test_path)
        else:
            cmd.append("tests/")
        
        if verbose:
            cmd.append("-v")
        
        cmd.append("--tb=short")  # Kısa traceback
        cmd.append("-q")  # Quiet mode
        
        # Subprocess çalıştır
        start_time = datetime.now()
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=os.getcwd()
        )
        
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=120)
        output = stdout.decode("utf-8", errors="ignore")
        
        duration = (datetime.now() - start_time).total_seconds()
        
        # Parse et
        parsed = parse_pytest_output(output)
        
        _last_test_result.update({
            "running": False,
            "output": output[-5000:],  # Son 5000 karakter
            "tests": parsed["tests"],
            "passed": parsed["passed"],
            "failed": parsed["failed"],
            "total": parsed["total"],
            "duration": round(duration, 2),
            "summary": f"{parsed['passed']}/{parsed['total']} test başarılı ({duration:.1f}s)",
            "success": parsed["failed"] == 0
        })
        
        print(f"🧪 Pytest tamamlandı: {parsed['passed']}/{parsed['total']} başarılı")
        
    except asyncio.TimeoutError:
        _last_test_result.update({
            "running": False,
            "output": "Test zaman aşımına uğradı (120s)",
            "summary": "Zaman aşımı",
            "success": False
        })
    except Exception as e:
        _last_test_result.update({
            "running": False,
            "output": str(e),
            "summary": f"Hata: {str(e)[:100]}",
            "success": False
        })


@router.get("/status")
async def pytest_status():
    """Test durumunu döndür"""
    return {
        "running": _last_test_result["running"],
        "last_run": _last_test_result["timestamp"],
        "summary": _last_test_result["summary"],
        "passed": _last_test_result["passed"],
        "failed": _last_test_result["failed"],
        "total": _last_test_result["total"],
        "duration": _last_test_result["duration"],
        "success": _last_test_result.get("success", False),
        "tests": _last_test_result["tests"][:15]  # İlk 15 test
    }


@router.get("/output")
async def pytest_output():
    """Son test çıktısını döndür"""
    return {
        "output": _last_test_result["output"],
        "timestamp": _last_test_result["timestamp"]
    }


@router.post("/run")
async def run_pytest(background_tasks: BackgroundTasks, path: Optional[str] = None):
    """pytest çalıştır"""
    if _last_test_result["running"]:
        return {"error": "Test zaten çalışıyor", "running": True}
    
    background_tasks.add_task(run_pytest_async, path)
    
    return {
        "message": "Test başlatıldı",
        "running": True,
        "path": path or "tests/"
    }


@router.post("/run/unit")
async def run_unit_tests(background_tasks: BackgroundTasks):
    """Sadece unit testleri çalıştır"""
    if _last_test_result["running"]:
        return {"error": "Test zaten çalışıyor", "running": True}
    
    background_tasks.add_task(run_pytest_async, "tests/unit/")
    return {"message": "Unit testler başlatıldı", "running": True}


@router.post("/run/integration")
async def run_integration_tests(background_tasks: BackgroundTasks):
    """Sadece integration testleri çalıştır"""
    if _last_test_result["running"]:
        return {"error": "Test zaten çalışıyor", "running": True}
    
    background_tasks.add_task(run_pytest_async, "tests/integration/")
    return {"message": "Integration testler başlatıldı", "running": True}


@router.post("/run/e2e")
async def run_e2e_tests(background_tasks: BackgroundTasks):
    """Sadece e2e testleri çalıştır"""
    if _last_test_result["running"]:
        return {"error": "Test zaten çalışıyor", "running": True}
    
    background_tasks.add_task(run_pytest_async, "tests/e2e/")
    return {"message": "E2E testler başlatıldı", "running": True}


@router.get("/categories")
async def test_categories():
    """Test kategorilerini listele"""
    categories = []
    
    if TESTS_DIR.exists():
        for item in TESTS_DIR.iterdir():
            if item.is_dir() and not item.name.startswith("_") and not item.name.startswith("."):
                test_count = len(list(item.glob("test_*.py")))
                categories.append({
                    "name": item.name,
                    "path": str(item),
                    "test_files": test_count
                })
    
    return {"categories": categories}
