"""Local FAQ admin routes."""

from __future__ import annotations

from typing import Any, Callable, Dict

from fastapi import APIRouter


def build_local_faq_router(
    local_faq: Dict[str, Dict[str, Any]],
    local_max_words: int,
    check_local_faq_fn: Callable[[str], Any],
) -> APIRouter:
    router = APIRouter(tags=["local-faq"])

    @router.get("/admin/local-faq")
    async def get_local_faq():
        faq_list = []
        for category, data in local_faq.items():
            faq_list.append(
                {
                    "category": category,
                    "keywords": data["keywords"],
                    "answer_tr": data["answer_tr"],
                    "answer_en": data["answer_en"],
                    "answer_ru": data.get("answer_ru", ""),
                }
            )
        return {
            "faq_count": len(local_faq),
            "max_words": local_max_words,
            "faq_list": faq_list,
        }

    @router.get("/admin/local-faq/test/{message}")
    async def test_local_faq(message: str):
        faq_found, faq_answer_tr, faq_answer_en, faq_category, faq_answer_ru = check_local_faq_fn(message)
        return {
            "message": message,
            "word_count": len(message.split()),
            "max_words": local_max_words,
            "found": faq_found,
            "category": faq_category if faq_found else None,
            "answer_tr": faq_answer_tr if faq_found else None,
            "answer_en": faq_answer_en if faq_found else None,
            "answer_ru": faq_answer_ru if faq_found else None,
            "would_use_openai": not faq_found,
        }

    return router

