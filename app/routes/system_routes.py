from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import Response


def build_system_router():
    router = APIRouter()

    @router.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        return Response(status_code=204)

    return router
