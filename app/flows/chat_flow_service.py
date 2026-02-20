"""Chat flow service with optional LangChain backend."""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, List

from openai import OpenAI

from app.flows.langchain_adapter import LangChainAdapter


class ChatFlowService:
    def __init__(
        self,
        api_key: str,
        model_getter: Callable[[], str],
        system_prompt_getter: Callable[[], str],
        detect_language_fn: Callable[[str], str],
        check_local_faq_fn: Callable[[str], Any],
    ) -> None:
        self._api_key = api_key
        self._model_getter = model_getter
        self._system_prompt_getter = system_prompt_getter
        self._detect_language = detect_language_fn
        self._check_local_faq = check_local_faq_fn

        self._openai_client = OpenAI(api_key=api_key)
        self._use_langchain = os.getenv("USE_LANGCHAIN_FLOW", "0").strip() == "1"
        self._langchain = LangChainAdapter(api_key=api_key, model=model_getter())

    def status(self) -> Dict[str, Any]:
        return {
            "use_langchain_flow": self._use_langchain,
            "langchain_ready": self._langchain.is_ready,
            "langchain_error": self._langchain.init_error,
            "model": self._model_getter(),
        }

    def generate(self, phone: str, message: str, history: List[Dict[str, str]] | None = None) -> Dict[str, Any]:
        faq_found, faq_answer_tr, faq_answer_en, faq_category, faq_answer_ru = self._check_local_faq(message)
        lang = self._detect_language(message) or "tr"
        if faq_found:
            if lang == "ru":
                response = faq_answer_ru
            elif lang == "en":
                response = faq_answer_en
            else:
                response = faq_answer_tr
            return {
                "response": response,
                "source": "LOCAL_FAQ",
                "lang": lang,
                "faq_category": faq_category,
            }

        model = self._model_getter()
        system_prompt = self._system_prompt_getter()
        history = history or []

        if self._use_langchain and self._langchain.is_ready:
            try:
                response = self._langchain.invoke(
                    system_prompt=system_prompt,
                    history=history,
                    user_message=message,
                    model=model,
                )
                return {
                    "response": response.strip(),
                    "source": "LANGCHAIN",
                    "lang": lang,
                    "faq_category": None,
                }
            except Exception as e:
                # fallback to direct OpenAI
                fallback_err = str(e)
            else:
                fallback_err = None
        else:
            fallback_err = None

        msgs = [{"role": "system", "content": system_prompt}]
        msgs.extend(history)
        msgs.append({"role": "user", "content": message})
        completion = self._openai_client.chat.completions.create(
            model=model,
            messages=msgs,
            max_tokens=500,
            temperature=0.7,
        )
        text = (completion.choices[0].message.content or "").strip()
        payload = {
            "response": text,
            "source": "OPENAI_DIRECT",
            "lang": lang,
            "faq_category": None,
        }
        if fallback_err:
            payload["langchain_fallback_error"] = fallback_err
        return payload

