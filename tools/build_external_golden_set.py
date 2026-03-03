from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "app" / "content" / "scenario_catalog.json"
OUT = PROJECT_ROOT / "tests" / "golden" / "scenarios" / "external_scenarios.json"


def _cat_from_intent(intent: str) -> str:
    if intent.startswith("RESTAURANT_"):
        return "restaurant"
    if intent.startswith("TRANSFER_"):
        return "transfer"
    if intent.startswith("PAYMENT_"):
        return "payment"
    if intent.startswith("HOTEL_BOOKING"):
        return "hotel_booking"
    if intent in {"PRICE_QUERY", "AVAILABILITY_QUERY"}:
        return "hotel_pricing"
    if intent in {"COMPLAINT", "HUMAN_AGENT_REQUEST", "URGENT_CASE", "RISK_ABUSE"}:
        return "handoff"
    if intent == "SPECIAL_REQUEST_EVENT":
        return "special_request"
    return "info"


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"Missing source catalog: {SRC}")

    payload = json.loads(SRC.read_text(encoding="utf-8"))
    scenarios = payload.get("scenarios", [])

    out_rows: List[Dict[str, object]] = []
    for rec in scenarios:
        sid = str(rec.get("id") or "").strip()
        intent = str(rec.get("intent") or "OUT_OF_SCOPE_OTHER").strip()
        title = str(rec.get("title") or sid)
        utterances = rec.get("trigger_utterances") or []
        if not sid or not utterances:
            continue
        question = str(utterances[0]).strip()
        if not question:
            continue
        out_rows.append(
            {
                "id": sid.lower(),
                "source_id": sid,
                "category": _cat_from_intent(intent),
                "intent": intent,
                "question": question,
                "description": title,
                "is_core": False,
                "smoke": False,
                "language": "tr",
            }
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"scenarios": out_rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(out_rows)} scenarios to {OUT}")


if __name__ == "__main__":
    main()
