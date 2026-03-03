from __future__ import annotations

from contextvars import ContextVar, Token


_correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def set_current_correlation_id(correlation_id: str | None) -> Token:
    return _correlation_id_var.set((correlation_id or "").strip() or None)


def get_current_correlation_id() -> str | None:
    return _correlation_id_var.get()


def reset_current_correlation_id(token: Token) -> None:
    _correlation_id_var.reset(token)

