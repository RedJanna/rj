from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CATALOG = PROJECT_ROOT / "app" / "content" / "scenario_catalog.json"
OUT = PROJECT_ROOT / "app" / "content" / "scenario_intent_examples.json"


def _clean(s: str) -> str:
    return " ".join((s or "").strip().split())


def main() -> None:
    if not CATALOG.exists():
        raise SystemExit(f"Missing scenario catalog: {CATALOG}")

    payload = json.loads(CATALOG.read_text(encoding="utf-8"))
    scenarios = payload.get("scenarios", [])

    intent_examples: Dict[str, List[str]] = {}
    for rec in scenarios:
        intent = str(rec.get("intent") or "").strip()
        if not intent:
            continue
        for utt in rec.get("trigger_utterances") or []:
            if not isinstance(utt, str):
                continue
            cleaned = _clean(utt)
            if not cleaned:
                continue
            intent_examples.setdefault(intent, [])
            intent_examples[intent].append(cleaned)

    normalized: Dict[str, List[str]] = {}
    for intent, examples in intent_examples.items():
        seen = set()
        out = []
        for ex in examples:
            key = ex.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(ex)
        normalized[intent] = out

    OUT.write_text(
        json.dumps({"intent_examples": normalized}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(normalized)} intents to {OUT}")


if __name__ == "__main__":
    main()
