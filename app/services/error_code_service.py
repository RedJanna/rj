from __future__ import annotations

import re


def derive_error_code(*, event: str = "", error_type: str = "", message: str = "") -> str:
    """Normalize runtime errors to stable dashboard-friendly error codes."""
    haystack = " ".join([event or "", error_type or "", message or ""]).strip().lower()

    if not haystack:
        return "E_UNKNOWN"

    if any(token in haystack for token in ("timeout", "timed out", "time out", "deadline exceeded")):
        return "E_CHAT_TIMEOUT"

    if any(token in haystack for token in ("rate limit", "too many requests", "429")):
        return "E_RATE_LIMIT"

    if any(token in haystack for token in ("openai", "chatcompletion", "completion", "apiconnectionerror", "apistatuserror")):
        return "E_OPENAI_FAIL"

    if re.search(r"\bhttp[_\s-]?\d{3}\b", haystack):
        return "E_HTTP_FAIL"

    if any(token in haystack for token in ("connection refused", "connection reset", "network", "dns")):
        return "E_NETWORK_FAIL"

    return "E_UNKNOWN"
