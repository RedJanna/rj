#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen


SUPPORTED_LANGS = {"en", "tr", "ru", "de", "ar", "es", "fr", "zh", "hi", "pt"}


@dataclass
class StepResult:
    idx: int
    user: str
    status: str
    reply: str


def _http_json(url: str, payload: dict[str, Any] | None = None, timeout: int = 30) -> dict[str, Any]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = Request(url, data=body, headers=headers, method="POST" if payload is not None else "GET")
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", "ignore")
        return json.loads(raw) if raw else {}


def _detect_lang_heuristic(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return "en"
    if re.search(r"[а-яёА-ЯЁ]", t):
        return "ru"
    if re.search(r"[\u0600-\u06FF]", t):
        return "ar"
    if re.search(r"[\u4E00-\u9FFF]", t):
        return "zh"
    if re.search(r"[\u0900-\u097F]", t):
        return "hi"
    low = t.lower()
    tr_signals = ("ş", "ğ", "ı", "ç", "ö", "ü", "rezervasyon", "fiyat", "müsait", "teşekkür")
    if any(s in low for s in tr_signals):
        return "tr"
    return "en"


def _default_scenario() -> list[str]:
    return [
        "1 ekim ile 3 ekim tarihleri arasında 2 yetişkin ve 7 yaşında 1 çocuk için müsaitlik var mı?",
        "Premium oda için rezervasyon oluşturabilir miyiz ?",
        "2",
        "oomer oomöer",
        "+905304498499",
        "geç",
        "kahve",
    ]


def run_smoke(base_url: str, phone: str, messages: list[str], expected_lang: str | None, timeout: int) -> int:
    health_url = f"{base_url.rstrip('/')}/health"
    chat_url = f"{base_url.rstrip('/')}/chat"

    try:
        health = _http_json(health_url, timeout=timeout)
    except (URLError, HTTPError, TimeoutError, ValueError) as exc:
        print(f"[FAIL] health check failed: {exc}")
        return 2
    print(f"[OK] health: {json.dumps(health, ensure_ascii=False)}")

    results: list[StepResult] = []
    for idx, msg in enumerate(messages, 1):
        payload = {
            "phone": phone,
            "message": msg,
            "message_id": f"smoke-{uuid.uuid4()}",
        }
        try:
            data = _http_json(chat_url, payload=payload, timeout=timeout)
        except (URLError, HTTPError, TimeoutError, ValueError) as exc:
            print(f"[FAIL] step {idx} request failed: {exc}")
            return 3
        reply = str(data.get("reply") or "")
        status = str(data.get("status") or "")
        results.append(StepResult(idx=idx, user=msg, status=status, reply=reply))
        one_line = re.sub(r"\s+", " ", reply).strip()[:280]
        print(f"{idx}) status={status}")
        print(f"   user={msg}")
        print(f"   reply={one_line}")

    if expected_lang:
        expected = expected_lang.strip().lower()
        if expected not in SUPPORTED_LANGS:
            print(f"[FAIL] unsupported --expected-lang: {expected}")
            return 4
        mismatches = []
        for item in results:
            got = _detect_lang_heuristic(item.reply)
            if got != expected:
                mismatches.append((item.idx, got, item.reply[:140]))
        if mismatches:
            print("[FAIL] language drift detected:")
            for idx, got, sample in mismatches:
                print(f" - step={idx} detected={got} sample={sample}")
            return 5
        print(f"[OK] language lock check passed for expected={expected}")

    print("[OK] smoke completed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic smoke chat scenario against local /chat API.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base URL")
    parser.add_argument("--phone", default="905304498499", help="Test phone number")
    parser.add_argument("--timeout", type=int, default=45, help="HTTP timeout seconds")
    parser.add_argument(
        "--expected-lang",
        default="tr",
        help="Expected reply language code. Use empty string to disable language check.",
    )
    parser.add_argument(
        "--messages-json",
        default="",
        help="Optional JSON array of messages. If omitted, built-in scenario is used.",
    )
    args = parser.parse_args()

    if args.messages_json:
        try:
            messages = json.loads(args.messages_json)
            if not isinstance(messages, list) or not all(isinstance(x, str) and x.strip() for x in messages):
                raise ValueError("messages-json must be a JSON array of non-empty strings")
        except Exception as exc:
            print(f"[FAIL] invalid --messages-json: {exc}")
            return 1
    else:
        messages = _default_scenario()

    expected_lang = (args.expected_lang or "").strip().lower() or None
    return run_smoke(
        base_url=args.base_url,
        phone=args.phone.strip(),
        messages=messages,
        expected_lang=expected_lang,
        timeout=max(5, int(args.timeout)),
    )


if __name__ == "__main__":
    sys.exit(main())

