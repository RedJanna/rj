from __future__ import annotations

import uuid
from typing import Mapping


CORRELATION_HEADER = "X-Correlation-Id"
REQUEST_ID_HEADER = "X-Request-Id"


def _sanitize(value: str) -> str:
    clean = (value or "").strip()
    if not clean:
        return ""
    # Keep logs and headers compact and printable.
    clean = "".join(ch for ch in clean if ch.isprintable() and ch not in "\r\n\t")
    return clean[:128]


def resolve_correlation_id(headers: Mapping[str, str] | None = None) -> str:
    headers = headers or {}
    cid = _sanitize(headers.get(CORRELATION_HEADER, ""))
    if cid:
        return cid
    req_id = _sanitize(headers.get(REQUEST_ID_HEADER, ""))
    if req_id:
        return req_id
    return str(uuid.uuid4())

