from __future__ import annotations

import json
import re
import os
from pathlib import Path
from typing import Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = PROJECT_ROOT / "docs" / "scenarios" / "raw"
LEGACY_SOURCE_DIR = Path(r"/mnt/c/Users/gonen/Desktop/velox/DİKKAT/Senaryolar/SENARYOLAR")
OUT_CATALOG = PROJECT_ROOT / "app" / "content" / "scenario_catalog.json"
OUT_INTENT_EXAMPLES = PROJECT_ROOT / "app" / "content" / "scenario_intent_examples.json"

SECTION_TRIGGER_RE = re.compile(r"Tetikleyici Niyetler \(Intents\):(.*?)(?:\n\s*📥|\n\s*⚙️|\n\s*🔄|\Z)", re.S)
SECTION_RESPONSE_RE = re.compile(r"Standart Yanıt Mesajları(?: \(TR\))?(.*)$", re.S)
SCENARIO_HEADER_RE = re.compile(r"Senaryo:\s*([^\n]+)")
CODE_RE = re.compile(r"\b(S\d{3}|MOD-\d{3})\b", re.I)


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _extract_header(text: str, fallback_name: str) -> Tuple[str, str]:
    m = SCENARIO_HEADER_RE.search(text)
    header = _clean(m.group(1)) if m else fallback_name
    c = CODE_RE.search(header)
    code = (c.group(1).upper() if c else fallback_name)
    return code, header


def _extract_triggers(text: str) -> List[str]:
    m = SECTION_TRIGGER_RE.search(text)
    if not m:
        return []
    block = m.group(1)
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    out: List[str] = []
    for ln in lines:
        ln = re.sub(r"^[*\-•]+\s*", "", ln).strip()
        ln = re.sub(r"^\(opsiyonel\)\s*", "", ln, flags=re.I)
        ln = ln.strip('"“”')
        ln = ln.strip("'")
        if not ln:
            continue
        if ln.lower().startswith("tetikleyici"):
            continue
        out.append(_clean(ln))
    # dedup preserve order
    seen = set()
    dedup = []
    for item in out:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        dedup.append(item)
    return dedup


def _extract_responses(text: str) -> Dict[str, List[str]]:
    m = SECTION_RESPONSE_RE.search(text)
    if not m:
        return {"tr": [], "en": []}
    block = m.group(1)
    tr_list: List[str] = []
    en_list: List[str] = []

    # quoted lines first
    for q in re.findall(r'"([^"\n]{8,})"', block):
        qn = _clean(q)
        if not qn:
            continue
        if re.search(r"\b(the|and|please|your|for|to|once|thank you|received)\b", qn, re.I):
            en_list.append(qn)
        else:
            tr_list.append(qn)

    # fallback for explicit numbered blocks if quotes missing
    if not tr_list and not en_list:
        for ln in [l.strip() for l in block.splitlines() if l.strip()]:
            if ln.startswith(("1.", "2.", "3.", "4.")):
                continue
            if len(ln) < 8:
                continue
            lnn = _clean(ln)
            if re.search(r"\b(the|and|please|your|for|to|once|thank you|received)\b", lnn, re.I):
                en_list.append(lnn)
            else:
                tr_list.append(lnn)

    return {
        "tr": list(dict.fromkeys(tr_list)),
        "en": list(dict.fromkeys(en_list)),
    }


def _intent_for_code(code: str, title: str) -> str:
    code = code.upper()
    t = (title or "").lower()

    direct = {
        "S001": "HOTEL_BOOKING_CREATE",
        "S002": "HOTEL_BOOKING_CREATE",
        "S003": "PRICE_QUERY",
        "S004": "PRICE_QUERY",
        "S005": "AVAILABILITY_QUERY",
        "S006": "HOTEL_BOOKING_MODIFY",
        "S007": "HOTEL_BOOKING_CANCEL",
        "S008": "HOTEL_BOOKING_CANCEL",
        "S009": "HOTEL_BOOKING_CANCEL",
        "S010": "HOTEL_BOOKING_MODIFY",
        "S011": "HOTEL_BOOKING_MODIFY",
        "S012": "LOCAL_FAQ_INFO",
        "S013": "LOCAL_FAQ_INFO",
        "S014": "PAYMENT_METHOD_QUERY",
        "S015": "PAYMENT_LINK_REQUEST",
        "S016": "DISCOUNT_NEGOTIATION",
        "S017": "HUMAN_AGENT_REQUEST",
        "S018": "COMPLAINT",
        "S019": "URGENT_CASE",
        "S020": "URGENT_CASE",
        "S021": "RISK_ABUSE",
        "S023": "OUT_OF_SCOPE_OTHER",
        "S024": "RESTAURANT_BOOKING_CREATE",
        "S025": "RESTAURANT_BOOKING_CREATE",
        "S026": "RESTAURANT_BOOKING_MODIFY",
        "S027": "RESTAURANT_BOOKING_CANCEL",
        "S028": "SPECIAL_REQUEST_EVENT",
        "S029": "TRANSFER_INFO",
        "S030": "TRANSFER_BOOKING_REQUEST",
        "S031": "TRANSFER_BOOKING_REQUEST",
        "S032": "TRANSFER_BOOKING_REQUEST",
        "S033": "TRANSFER_BOOKING_REQUEST",
        "S034": "LOCAL_FAQ_INFO",
        "S035": "LOCAL_FAQ_INFO",
        "S036": "LOCAL_FAQ_INFO",
        "S037": "LOCAL_FAQ_INFO",
        "S038": "LOCAL_FAQ_INFO",
        "S039": "LOCAL_FAQ_INFO",
        "S040": "SPECIAL_REQUEST_EVENT",
        "S041": "SPECIAL_REQUEST_EVENT",
        "S042": "SPECIAL_REQUEST_EVENT",
        "S043": "SPECIAL_REQUEST_EVENT",
        "S044": "SPECIAL_REQUEST_EVENT",
        "S045": "LOCAL_FAQ_INFO",
        "S046": "LOCAL_FAQ_INFO",
        "MOD-002": "HOTEL_BOOKING_MODIFY",
    }
    if code in direct:
        return direct[code]

    if "restoran" in t:
        return "RESTAURANT_BOOKING_CREATE"
    if "transfer" in t:
        return "TRANSFER_BOOKING_REQUEST"
    if "iptal" in t:
        return "HOTEL_BOOKING_CANCEL"
    if "değiş" in t or "degis" in t:
        return "HOTEL_BOOKING_MODIFY"
    if "ödeme" in t or "odeme" in t:
        return "PAYMENT_METHOD_QUERY"
    if "fiyat" in t:
        return "PRICE_QUERY"
    return "OUT_OF_SCOPE_OTHER"


def main() -> None:
    source_dir_raw = os.getenv("KASSANDRA_SCENARIO_SOURCE_DIR", "").strip()
    source_dir = Path(source_dir_raw) if source_dir_raw else DEFAULT_SOURCE_DIR
    if not source_dir.exists() and LEGACY_SOURCE_DIR.exists():
        source_dir = LEGACY_SOURCE_DIR
    if not source_dir.exists():
        raise SystemExit(
            f"Source directory not found: {source_dir}. "
            f"Set KASSANDRA_SCENARIO_SOURCE_DIR or populate {DEFAULT_SOURCE_DIR}."
        )

    files = sorted(source_dir.glob("*.txt"))
    catalog: List[Dict[str, object]] = []
    intent_examples: Dict[str, List[str]] = {}

    for fp in files:
        raw = fp.read_text(encoding="utf-8", errors="ignore")
        code, title = _extract_header(raw, fp.stem)
        triggers = _extract_triggers(raw)
        responses = _extract_responses(raw)
        intent = _intent_for_code(code, title)

        rec = {
            "id": code,
            "title": title,
            "source_file": fp.name,
            "source_dir": str(source_dir),
            "intent": intent,
            "trigger_utterances": triggers,
            "standard_responses": responses,
        }
        catalog.append(rec)

        if triggers:
            intent_examples.setdefault(intent, [])
            intent_examples[intent].extend(triggers)

    # dedup + deterministic order
    for k, vals in list(intent_examples.items()):
        dedup: List[str] = []
        seen = set()
        for v in vals:
            key = _clean(v).lower()
            if not key or key in seen:
                continue
            seen.add(key)
            dedup.append(_clean(v))
        intent_examples[k] = dedup

    OUT_CATALOG.write_text(
        json.dumps({"scenarios": catalog}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    OUT_INTENT_EXAMPLES.write_text(
        json.dumps({"intent_examples": intent_examples}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Imported {len(catalog)} scenarios")
    print(f"Wrote: {OUT_CATALOG}")
    print(f"Wrote: {OUT_INTENT_EXAMPLES}")


if __name__ == "__main__":
    main()
