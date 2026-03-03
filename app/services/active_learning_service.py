from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


ACTIVE_LEARNING_FILE = Path("data/active_learning_queue.jsonl")


def _sample_id(*, phone: str, message: str, stage: str) -> str:
    raw = f"{phone}|{stage}|{message}".encode("utf-8", errors="ignore")
    return hashlib.sha256(raw).hexdigest()[:20]


def capture_active_learning_sample(
    *,
    phone: str,
    message: str,
    stage: str,
    lang: str = "tr",
    predicted_intent: Optional[str] = None,
    confidence: Optional[float] = None,
    reason: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Capture uncertain/edge messages for later labeling."""
    try:
        msg = (message or "").strip()
        if not msg:
            return
        ACTIVE_LEARNING_FILE.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": datetime.now().isoformat(),
            "id": _sample_id(phone=phone or "", message=msg, stage=stage or ""),
            "phone": phone or "",
            "lang": lang or "tr",
            "message": msg,
            "stage": stage or "",
            "predicted_intent": predicted_intent,
            "confidence": confidence,
            "reason": reason or "",
            "metadata": metadata or {},
            "label_status": "pending",
        }
        with open(ACTIVE_LEARNING_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        # Active learning never blocks runtime.
        return
