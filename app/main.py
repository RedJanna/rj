"""Application entrypoint with a safe health endpoint."""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI

from app.core.settings_service import validate_startup_environment


def _has_get_route(app: FastAPI, path: str) -> bool:
    for route in app.router.routes:
        methods = getattr(route, "methods", set()) or set()
        if getattr(route, "path", None) == path and "GET" in methods:
            return True
    return False


def _attach_fallback_health(app: FastAPI, startup_error: Exception | None = None) -> None:
    if _has_get_route(app, "/health"):
        return

    @app.get("/health")
    async def health() -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": "ok" if startup_error is None else "degraded",
            "env": os.getenv("KASSANDRA_ENV", "production").strip().lower(),
        }
        if startup_error is not None:
            payload["startup_error"] = startup_error.__class__.__name__
            payload["startup_error_message"] = str(startup_error)
        return payload


def create_app() -> FastAPI:
    try:
        validate_startup_environment()
        from app.legacy.kassandra_app_legacy import app as legacy_app

        app = legacy_app
        _attach_fallback_health(app)
        return app
    except Exception as exc:
        print(f"[STARTUP] Degraded mode: {exc}")
        # Keep process alive with a minimal app so health checks always respond.
        app = FastAPI(title="Kassandra WhatsApp Bot (degraded)")
        # Do not mount system router in degraded mode; it defines /health="ok"
        # and would hide the startup error signal.
        _attach_fallback_health(app, startup_error=exc)
        return app


app = create_app()
