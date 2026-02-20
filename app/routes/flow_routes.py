"""Flow experimentation routes (LangChain + flow orchestration)."""

from __future__ import annotations

from typing import Callable, Dict, Any, List

from fastapi import APIRouter
from pydantic import BaseModel


class FlowChatPreviewRequest(BaseModel):
    message: str
    phone: str = "FLOW_TEST_001"


def build_flow_router(
    flow_service: Any,
    get_conversation_history_fn: Callable[[str], List[Dict[str, str]]],
) -> APIRouter:
    router = APIRouter(prefix="/admin/flows", tags=["flows"])

    @router.get("/status")
    async def flow_status():
        return flow_service.status()

    @router.post("/chat-preview")
    async def flow_chat_preview(payload: FlowChatPreviewRequest):
        history = get_conversation_history_fn(payload.phone) if payload.phone else []
        result = flow_service.generate(
            phone=payload.phone,
            message=payload.message,
            history=history,
        )
        return {
            "status": "ok",
            "phone": payload.phone,
            "message": payload.message,
            "response": result.get("response"),
            "source": result.get("source"),
            "lang": result.get("lang"),
            "meta": {
                "faq_category": result.get("faq_category"),
                "langchain_fallback_error": result.get("langchain_fallback_error"),
            },
        }

    return router

