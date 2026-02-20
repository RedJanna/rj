from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


TRACE_FILE = Path("logs/decision_trace.jsonl")


def trace_decision(payload: Dict[str, Any]) -> None:
    try:
        TRACE_FILE.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": datetime.now().isoformat(),
            **(payload or {}),
        }
        with open(TRACE_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        # Trace never blocks runtime.
        return

