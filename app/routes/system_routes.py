from __future__ import annotations

import os

from fastapi import APIRouter
from fastapi.responses import Response


def build_system_router():
    router = APIRouter()

    @router.get("/")
    async def system_status():
        return {
            "status": "ok",
            "service": "kassandra",
            "env": os.getenv("KASSANDRA_ENV", "production").strip().lower(),
        }

    @router.get("/health")
    async def health():
        return {
            "status": "ok",
            "env": os.getenv("KASSANDRA_ENV", "production").strip().lower(),
        }

    @router.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        return Response(status_code=204)

    return router
