#!/usr/bin/env python3
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _ok(msg: str) -> None:
    print(f"[OK] {msg}")


def _warn(msg: str) -> None:
    print(f"[WARN] {msg}")


def _err(msg: str) -> None:
    print(f"[ERROR] {msg}")


def _check_required_env(errors: List[str]) -> None:
    required = ["OPENAI_API_KEY"]
    optional = ["WHATSAPP_TOKEN", "WHATSAPP_PHONE_ID", "KASSANDRA_ENV"]

    for key in required:
        if os.getenv(key, "").strip():
            _ok(f"{key} is set")
        else:
            errors.append(f"Missing required env: {key}")
            _err(f"{key} is not set")

    for key in optional:
        if os.getenv(key, "").strip():
            _ok(f"{key} is set")
        else:
            _warn(f"{key} is not set")


def _check_imports(errors: List[str]) -> None:
    for module_name in ("fastapi", "openai"):
        try:
            importlib.import_module(module_name)
            _ok(f"Import check passed: {module_name}")
        except Exception as exc:  # pragma: no cover
            errors.append(f"Cannot import {module_name}: {exc}")
            _err(f"Import check failed: {module_name} ({exc})")


def _check_app(errors: List[str]) -> None:
    try:
        from app.main import app
    except Exception as exc:
        errors.append(f"Cannot import app.main: {exc}")
        _err(f"Cannot import app.main ({exc})")
        return

    title = getattr(app, "title", "")
    if title:
        _ok(f"App title: {title}")
    else:
        _warn("App title is empty")

    if "degraded" in title.lower():
        errors.append("App is running in degraded mode")
        _err("App imported in degraded mode")

    has_health = False
    for route in getattr(app, "routes", []):
        methods = getattr(route, "methods", set()) or set()
        path = getattr(route, "path", "")
        if path == "/health" and "GET" in methods:
            has_health = True
            break

    if has_health:
        _ok("Route check passed: GET /health")
    else:
        errors.append("Missing GET /health route")
        _err("Route check failed: GET /health is missing")


def main() -> int:
    print("[INFO] Running backend preflight checks...")
    print(f"[INFO] Python: {sys.version.split()[0]}")
    print(f"[INFO] CWD: {os.getcwd()}")

    errors: List[str] = []
    _check_required_env(errors)
    _check_imports(errors)
    _check_app(errors)

    if errors:
        print("\n[FAIL] Preflight checks failed:")
        for item in errors:
            print(f" - {item}")
        return 1

    print("\n[PASS] Preflight checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
