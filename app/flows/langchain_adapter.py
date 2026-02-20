"""Optional LangChain adapter.

This module is safe to import even when LangChain dependencies are missing.
"""

from __future__ import annotations

from typing import List, Dict, Optional


class LangChainAdapter:
    def __init__(self, api_key: str, model: str, temperature: float = 0.4) -> None:
        self._api_key = api_key
        self._model = model
        self._temperature = temperature
        self._ready = False
        self._err: Optional[str] = None
        self._ChatPromptTemplate = None
        self._StrOutputParser = None
        self._ChatOpenAI = None

        try:
            from langchain_core.prompts import ChatPromptTemplate  # type: ignore
            from langchain_core.output_parsers import StrOutputParser  # type: ignore
            from langchain_openai import ChatOpenAI  # type: ignore

            self._ChatPromptTemplate = ChatPromptTemplate
            self._StrOutputParser = StrOutputParser
            self._ChatOpenAI = ChatOpenAI
            self._ready = True
        except Exception as e:
            self._err = str(e)

    @property
    def is_ready(self) -> bool:
        return self._ready

    @property
    def init_error(self) -> Optional[str]:
        return self._err

    def invoke(self, system_prompt: str, history: List[Dict[str, str]], user_message: str, model: Optional[str] = None) -> str:
        if not self._ready:
            raise RuntimeError(self._err or "LangChain is not available")

        messages = [("system", system_prompt)]
        for item in history or []:
            role = item.get("role", "user")
            content = item.get("content", "")
            if role == "assistant":
                messages.append(("ai", content))
            elif role == "system":
                messages.append(("system", content))
            else:
                messages.append(("human", content))
        messages.append(("human", user_message))

        prompt = self._ChatPromptTemplate.from_messages(messages)
        llm = self._ChatOpenAI(
            api_key=self._api_key,
            model=model or self._model,
            temperature=self._temperature,
        )
        chain = prompt | llm | self._StrOutputParser()
        return chain.invoke({})

