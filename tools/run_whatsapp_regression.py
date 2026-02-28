#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error, request


def _configure_console_encoding() -> None:
    """Make console output resilient on Windows cp1254/cp1252 terminals."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _clean_phone(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


def _load_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _reset_state(root: Path, phone: str, disable_welcome: bool) -> None:
    conversations = root / "conversations"
    conversations.mkdir(parents=True, exist_ok=True)
    for fp in conversations.glob("*.json"):
        if fp.name.endswith(".lock"):
            continue
        fp.unlink(missing_ok=True)

    _save_json(root / "data" / "price_flows.json", {})
    _save_json(root / "data" / "booking_flows.json", {})
    _save_json(root / "data" / "routing_states.json", {})
    _save_json(
        root / "data" / "followups.json",
        {"pending": {}, "settings": {"minutes": 10}, "last_cycle": {}},
    )
    _save_json(root / "data" / "message_ids.json", {})
    _save_json(root / "rate_limits.json", {"limits": {}, "blocked": {}})
    _save_json(root / "paused_conversations.json", {"paused": {}})
    _save_json(
        root / "blacklist.json",
        {"blacklist": [], "updated_at": datetime.now().isoformat()},
    )

    if disable_welcome:
        seed = {
            "phone": phone,
            "messages": [
                {
                    "timestamp": datetime.now().isoformat(),
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "user_message": "seed",
                    "bot_reply": "ack",
                    "is_price_template": False,
                }
            ],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        _save_json(conversations / f"{_clean_phone(phone)}.json", seed)


def _sanitize_access_controls(root: Path, phone: str) -> None:
    clean = _clean_phone(phone)

    rate_limits_path = root / "rate_limits.json"
    rate_limits = _load_json(rate_limits_path, {"limits": {}, "blocked": {}})
    if not isinstance(rate_limits, dict):
        rate_limits = {"limits": {}, "blocked": {}}
    rate_limits.setdefault("limits", {})
    rate_limits.setdefault("blocked", {})
    rate_limits["limits"].pop(clean, None)
    rate_limits["blocked"].pop(clean, None)
    _save_json(rate_limits_path, rate_limits)

    blacklist_path = root / "blacklist.json"
    blacklist = _load_json(blacklist_path, {"blacklist": []})
    if not isinstance(blacklist, dict):
        blacklist = {"blacklist": []}
    items = blacklist.get("blacklist")
    if not isinstance(items, list):
        items = []
    blacklist["blacklist"] = [_clean_phone(x) for x in items if _clean_phone(x) and _clean_phone(x) != clean]
    blacklist["updated_at"] = datetime.now().isoformat()
    _save_json(blacklist_path, blacklist)

    paused_path = root / "paused_conversations.json"
    paused = _load_json(paused_path, {"paused": {}})
    if not isinstance(paused, dict):
        paused = {"paused": {}}
    paused_map = paused.get("paused")
    if not isinstance(paused_map, dict):
        paused_map = {}
    paused_map.pop(clean, None)
    paused["paused"] = paused_map
    _save_json(paused_path, paused)


def _post_chat(base_url: str, phone: str, message: str, timeout_sec: int = 30) -> dict[str, Any]:
    payload = {
        "phone": phone,
        "message": message,
        "message_id": f"reg-{uuid.uuid4()}",
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url=f"{base_url.rstrip('/')}/chat",
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with request.urlopen(req, timeout=timeout_sec) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return json.loads(raw)


def _send(root: Path, base_url: str, phone: str, message: str) -> dict[str, Any]:
    try:
        out = _post_chat(base_url=base_url, phone=phone, message=message)
        _sanitize_access_controls(root, phone)
        return {
            "ok": True,
            "status": out.get("status", ""),
            "reply": str(out.get("reply", "")),
            "reason_code": out.get("reason_code", ""),
        }
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return {"ok": False, "status": f"http_{exc.code}", "reply": body, "reason_code": ""}
    except Exception as exc:
        return {"ok": False, "status": "request_error", "reply": str(exc), "reason_code": ""}


def _date_parse_check(root: Path, base_url: str, phone: str) -> tuple[bool, str]:
    _reset_state(root, phone, disable_welcome=True)
    _send(root, base_url, phone, "Ağustos için fiyat alabilir miyim?")
    second = _send(root, base_url, phone, "23–26 Ağustos (3 gece) için toplam 4 yetişkin olacağız.")
    low = second["reply"].lower()
    failed = ("tarihleri anlayamad" in low) or ("couldn't understand the dates" in low)
    return (not failed, f"status={second['status']} reply={second['reply'][:200]}")


def _late_checkin_check(root: Path, base_url: str, phone: str) -> tuple[bool, str]:
    _reset_state(root, phone, disable_welcome=True)
    result = _send(root, base_url, phone, "Gece geç saatte (01:00 gibi) giriş yaparsak sorun olur mu?")
    low = result["reply"].lower()
    passed = ("14:00" in result["reply"]) and ("musaitlik" not in low) and ("availability" not in low)
    return (passed, f"status={result['status']} reply={result['reply'][:200]}")


def _booking_start_check(root: Path, base_url: str, phone: str) -> tuple[bool, str]:
    _reset_state(root, phone, disable_welcome=True)
    result = _send(
        root,
        base_url,
        phone,
        "Tamam, rezervasyonu başlatalım: isim-soyisim ve telefonumu göndereyim mi?",
    )
    is_booking_path = str(result["status"]).startswith("booking_")
    not_contact_faq = result["status"] != "intent_semantic_faq_telefon"
    return (is_booking_path and not_contact_faq, f"status={result['status']} reply={result['reply'][:200]}")


def _run_full_flow(root: Path, base_url: str, phone: str) -> list[dict[str, Any]]:
    _reset_state(root, phone, disable_welcome=True)
    scenario = [
        "Merhaba, Ağustos’ta Kassandra Boutique Hotel için arkadaş grubuyla konaklama planlıyoruz, fiyat alabilir miyim?",
        "23–26 Ağustos (3 gece) için toplam 4 yetişkin olacağız.",
        "Bu tarihlerde 2 ayrı oda ayarlayabilir misiniz? (tercihen yan yana)",
        "2 oda için toplam fiyat kaç TL olur?",
        "Kahvaltı dahil mi, değilse 4 kişi için günlük toplam ne kadar eklenir?",
        "Odalardan biri deniz manzaralı, diğeri standart olursa fiyat nasıl değişir?",
        "İadesiz ve esnek iptal seçeneklerinin fiyatlarını ayrı ayrı yazar mısınız?",
        "Odaların balkonlu olma ihtimali var mı, varsa ek ücret oluyor mu?",
        "Check-in/check-out saatleriniz nedir?",
        "Gece geç saatte (01:00 gibi) giriş yaparsak sorun olur mu?",
        "Otoparkınız var mı, varsa ücretli mi?",
        "Ödeme için kredi kartı geçiyor mu? Link gönderebiliyor musunuz?",
        "Rezervasyonu tutmak için kapora gerekiyorsa ne kadar ve ne zamana kadar yatırmalıyız?",
        "Tamam, rezervasyonu başlatalım: isim-soyisim ve telefonumu göndereyim mi?",
        "Rezervasyon oluşunca WhatsApp’tan teyit mesajı + rezervasyon kodu paylaşır mısınız?",
    ]

    rows: list[dict[str, Any]] = []
    for idx, msg in enumerate(scenario, start=1):
        out = _send(root, base_url, phone, msg)
        rows.append(
            {
                "step": f"S{idx:02d}",
                "message": msg,
                "status": out["status"],
                "reply": out["reply"],
            }
        )
        if idx == 6:
            x1 = _send(root, base_url, phone, "Do you have a room suitable for 2 adults + 1 child (7 years old)?")
            rows.append({"step": "X01", "message": "Do you have a room suitable for 2 adults + 1 child (7 years old)?", "status": x1["status"], "reply": x1["reply"]})
            if re.search(r"tarih|date|which dates|between", x1["reply"].lower()):
                x2 = _send(root, base_url, phone, "18-22 August 2026")
                rows.append({"step": "X02", "message": "18-22 August 2026", "status": x2["status"], "reply": x2["reply"]})
    return rows


def main() -> int:
    _configure_console_encoding()

    parser = argparse.ArgumentParser(description="WhatsApp hotel flow regression (live /chat).")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Backend base URL")
    parser.add_argument("--phone", default="905399977701", help="Test phone number")
    parser.add_argument("--full-flow", action="store_true", help="Run end-to-end conversation flow too")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    phone = _clean_phone(args.phone)

    checks = [
        ("date_parse", _date_parse_check(root, args.base_url, phone)),
        ("late_checkin", _late_checkin_check(root, args.base_url, phone)),
        ("booking_start", _booking_start_check(root, args.base_url, phone)),
    ]

    failed = False
    for name, (ok, detail) in checks:
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name}: {detail}")
        if not ok:
            failed = True

    if args.full_flow:
        rows = _run_full_flow(root, args.base_url, phone)
        print("\n[FLOW] Transcript")
        for row in rows:
            line = (row["reply"] or "").replace("\r", " ").replace("\n", " | ")
            if len(line) > 220:
                line = line[:220] + "..."
            print(f"{row['step']} status={row['status']} reply={line}")

    _sanitize_access_controls(root, phone)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
