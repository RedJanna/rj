#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error, request

DEFAULT_LANGUAGE_SMOKE_MESSAGES: dict[str, list[str]] = {
    "en": [
        "Please share the total price for 2 adults from 14 to 18 August 2026.",
        "Can you share refundable and non-refundable options with cancellation rules?",
    ],
    "tr": [
        "14-18 Ağustos 2026 için 2 yetişkin toplam fiyatı paylaşır mısınız?",
        "İadesiz ve iade edilebilir tarifeleri iptal koşullarıyla paylaşır mısınız?",
    ],
    "ru": [
        "Подскажите общую стоимость для 2 взрослых на 14-18 августа 2026.",
        "Укажите refundable и non-refundable тарифы с правилами отмены.",
    ],
    "de": [
        "Bitte teilen Sie den Gesamtpreis für 2 Erwachsene vom 14. bis 18. August 2026 mit.",
        "Bitte nennen Sie erstattbare und nicht erstattbare Tarife mit Stornierungsregeln.",
    ],
    "ar": [
        "يرجى مشاركة السعر الإجمالي لشخصين بالغين من 14 إلى 18 أغسطس 2026.",
        "هل يمكن توضيح الأسعار القابلة للاسترداد وغير القابلة للاسترداد مع سياسة الإلغاء؟",
    ],
    "es": [
        "¿Puede compartir el precio total para 2 adultos del 14 al 18 de agosto de 2026?",
        "¿Puede indicar tarifas reembolsables y no reembolsables con reglas de cancelación?",
    ],
    "fr": [
        "Pouvez-vous partager le prix total pour 2 adultes du 14 au 18 août 2026 ?",
        "Pouvez-vous indiquer les tarifs remboursables et non remboursables avec les règles d'annulation ?",
    ],
    "zh": [
        "请提供2026年8月14日至18日两位成人的总价。",
        "请说明可退款和不可退款价格以及取消规则。",
    ],
    "hi": [
        "कृपया 14 से 18 अगस्त 2026 तक 2 वयस्कों के लिए कुल कीमत बताएं।",
        "कृपया refundable और non-refundable दरें तथा cancellation नियम साझा करें।",
    ],
    "pt": [
        "Pode informar o preço total para 2 adultos de 14 a 18 de agosto de 2026?",
        "Pode informar tarifas reembolsáveis e não reembolsáveis com regras de cancelamento?",
    ],
}

ERROR_STATUSES = {"request_error"}


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


def _default_test_phone() -> str:
    # Allow override from env; fallback to current Meta test recipient.
    from os import getenv

    return _clean_phone(getenv("WHATSAPP_TEST_PHONE", "")) or "15551659223"


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


def _reset_state(root: Path, phone: str, disable_welcome: bool, clear_all_conversations: bool = True) -> None:
    conversations = root / "conversations"
    conversations.mkdir(parents=True, exist_ok=True)
    if clear_all_conversations:
        for fp in conversations.glob("*.json"):
            if fp.name.endswith(".lock"):
                continue
            try:
                fp.unlink(missing_ok=True)
            except PermissionError:
                # Windows'ta backend dosyayı kısa süreli kilitleyebilir.
                # Bu durumda test akışını kırmadan devam et.
                pass
    else:
        target = conversations / f"{_clean_phone(phone)}.json"
        try:
            target.unlink(missing_ok=True)
        except PermissionError:
            pass

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


def _load_language_smoke_messages(root: Path) -> dict[str, list[str]]:
    path = root / "tools" / "language_smoke_messages.json"
    if not path.exists():
        return DEFAULT_LANGUAGE_SMOKE_MESSAGES
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return DEFAULT_LANGUAGE_SMOKE_MESSAGES
    if not isinstance(payload, dict):
        return DEFAULT_LANGUAGE_SMOKE_MESSAGES
    result: dict[str, list[str]] = {}
    for lang, messages in payload.items():
        if not isinstance(lang, str) or not isinstance(messages, list):
            continue
        valid = [str(m).strip() for m in messages if str(m).strip()]
        if valid:
            result[lang.strip().lower()] = valid
    return result or DEFAULT_LANGUAGE_SMOKE_MESSAGES


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
    retryable_http = {500, 502, 503, 504}
    max_attempts = 2
    for attempt in range(1, max_attempts + 1):
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
            if exc.code in retryable_http and attempt < max_attempts:
                time.sleep(0.6)
                continue
            return {"ok": False, "status": f"http_{exc.code}", "reply": body, "reason_code": ""}
        except Exception as exc:
            if attempt < max_attempts:
                time.sleep(0.6)
                continue
            return {"ok": False, "status": "request_error", "reply": str(exc), "reason_code": ""}


def _send_without_welcome(root: Path, base_url: str, phone: str, message: str) -> dict[str, Any]:
    first = _send(root, base_url, phone, message)
    if first.get("status") != "first_message":
        # No welcome branch fired: greeting is effectively bypassed.
        first["welcome_bypassed"] = True
        first["had_first_message_welcome"] = False
        return first

    second = _send(root, base_url, phone, message)
    # Welcome branch fired on first attempt; not bypassed.
    second["welcome_bypassed"] = False
    second["had_first_message_welcome"] = True
    second["first_message_reply"] = str(first.get("reply", ""))
    return second


def _is_error_status(status: str) -> bool:
    s = str(status or "").strip().lower()
    if s in ERROR_STATUSES:
        return True
    return s.startswith("http_")


def _has_nonempty_reply(payload: dict[str, Any]) -> bool:
    return bool(str(payload.get("reply") or "").strip())


def _reply_matches_expected_script(lang: str, reply: str) -> bool:
    text = str(reply or "")
    code = (lang or "").strip().lower()
    if code == "ru":
        return bool(re.search(r"[а-яёА-ЯЁ]", text))
    if code == "ar":
        return bool(re.search(r"[\u0600-\u06FF]", text))
    if code == "zh":
        return bool(re.search(r"[\u4e00-\u9fff]", text))
    if code == "hi":
        return bool(re.search(r"[\u0900-\u097F]", text))
    return True


def _date_parse_check(root: Path, base_url: str, phone: str) -> tuple[bool, str]:
    _reset_state(root, phone, disable_welcome=True)
    first = _send_without_welcome(root, base_url, phone, "Ağustos için fiyat alabilir miyim?")
    if _is_error_status(first.get("status", "")):
        return (False, f"first_status={first['status']} reply={first['reply'][:200]}")
    second = _send_without_welcome(root, base_url, phone, "23–26 Ağustos (3 gece) için toplam 4 yetişkin olacağız.")
    if _is_error_status(second.get("status", "")):
        return (False, f"second_status={second['status']} reply={second['reply'][:200]}")
    low = second["reply"].lower()
    failed = ("tarihleri anlayamad" in low) or ("couldn't understand the dates" in low)
    forced = bool(second.get("welcome_bypassed"))
    return (not failed and forced, f"status={second['status']} welcome_bypassed={forced} reply={second['reply'][:200]}")


def _late_checkin_check(root: Path, base_url: str, phone: str) -> tuple[bool, str]:
    _reset_state(root, phone, disable_welcome=True)
    result = _send_without_welcome(root, base_url, phone, "Gece geç saatte (01:00 gibi) giriş yaparsak sorun olur mu?")
    if _is_error_status(result.get("status", "")):
        return (False, f"status={result['status']} reply={result['reply'][:200]}")
    low = result["reply"].lower()
    passed = ("14:00" in result["reply"]) and ("musaitlik" not in low) and ("availability" not in low)
    forced = bool(result.get("welcome_bypassed"))
    return (passed, f"status={result['status']} welcome_bypassed={forced} reply={result['reply'][:200]}")


def _booking_start_check(root: Path, base_url: str, phone: str) -> tuple[bool, str]:
    _reset_state(root, phone, disable_welcome=True)
    result = _send_without_welcome(
        root,
        base_url,
        phone,
        "Tamam, rezervasyonu başlatalım: isim-soyisim ve telefonumu göndereyim mi?",
    )
    if _is_error_status(result.get("status", "")):
        return (False, f"status={result['status']} reply={result['reply'][:200]}")
    is_booking_path = str(result["status"]).startswith("booking_")
    asks_booking_slots = bool(
        re.search(
            r"(ad[ıi]n[ıi]z|soyad|telefon|e-?posta|full name|phone|email)",
            str(result.get("reply") or ""),
            flags=re.IGNORECASE,
        )
    )
    not_contact_faq = result["status"] != "intent_semantic_faq_telefon"
    forced = bool(result.get("welcome_bypassed"))
    return (
        (is_booking_path or asks_booking_slots) and not_contact_faq and forced,
        f"status={result['status']} welcome_bypassed={forced} reply={result['reply'][:200]}",
    )


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
        out = _send_without_welcome(root, base_url, phone, msg)
        rows.append(
            {
                "step": f"S{idx:02d}",
                "message": msg,
                "status": out["status"],
                "reply": out["reply"],
                "welcome_bypassed": bool(out.get("welcome_bypassed")),
            }
        )
        if idx == 6:
            x1 = _send_without_welcome(root, base_url, phone, "Do you have a room suitable for 2 adults + 1 child (7 years old)?")
            rows.append(
                {
                    "step": "X01",
                    "message": "Do you have a room suitable for 2 adults + 1 child (7 years old)?",
                    "status": x1["status"],
                    "reply": x1["reply"],
                    "welcome_bypassed": bool(x1.get("welcome_bypassed")),
                }
            )
            if re.search(r"tarih|date|which dates|between", x1["reply"].lower()):
                x2 = _send_without_welcome(root, base_url, phone, "18-22 August 2026")
                rows.append(
                    {
                        "step": "X02",
                        "message": "18-22 August 2026",
                        "status": x2["status"],
                        "reply": x2["reply"],
                        "welcome_bypassed": bool(x2.get("welcome_bypassed")),
                    }
                )
    return rows


def _derive_phone_for_lang(base_phone: str, idx: int) -> str:
    clean = _clean_phone(base_phone)
    if len(clean) < 11:
        clean = (clean + ("0" * 11))[:11]
    suffix = f"{idx % 100:02d}"
    return clean[:-2] + suffix


def _run_language_smoke(root: Path, base_url: str, phone: str) -> list[dict[str, Any]]:
    messages_by_lang = _load_language_smoke_messages(root)
    rows: list[dict[str, Any]] = []

    for idx, (lang, messages) in enumerate(sorted(messages_by_lang.items()), start=1):
        test_phone = _derive_phone_for_lang(phone, idx)
        _reset_state(root, test_phone, disable_welcome=True, clear_all_conversations=False)
        for step_idx, msg in enumerate(messages, start=1):
            out = _send_without_welcome(root, base_url, test_phone, msg)
            rows.append(
                {
                    "lang": lang,
                    "phone": test_phone,
                    "step": f"{lang.upper()}_{step_idx:02d}",
                    "message": msg,
                    "status": out["status"],
                    "reason_code": out.get("reason_code", ""),
                    "reply": out["reply"],
                    "welcome_bypassed": bool(out.get("welcome_bypassed")),
                }
            )
        _sanitize_access_controls(root, test_phone)
    return rows


def _has_price_numbers(reply: str) -> bool:
    txt = str(reply or "").lower()
    if not txt:
        return False
    return bool(re.search(r"\b\d+(?:[.,]\d+)?\s*(?:eur|usd|try|tl|€|₺)\b", txt))


def _run_hard_fail_suite(root: Path, base_url: str, base_phone: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    # HF1: İlk mesajdan sonra welcome zorunlu.
    phone_hf1 = _derive_phone_for_lang(base_phone, 91)
    _reset_state(root, phone_hf1, disable_welcome=False, clear_all_conversations=False)
    out_hf1 = _send(root, base_url, phone_hf1, "merhaba")
    hf1_ok = (
        out_hf1.get("status") == "first_message"
        and _has_nonempty_reply(out_hf1)
        and "kassandra" in str(out_hf1.get("reply") or "").lower()
    )
    rows.append(
        {
            "check": "HF1_WELCOME_FIRST_MESSAGE",
            "phone": phone_hf1,
            "ok": hf1_ok,
            "status": out_hf1.get("status"),
            "reply": str(out_hf1.get("reply") or ""),
            "detail": "First message must return welcome response.",
        }
    )

    # HF2: Cocuk sayisi var, yas yoksa fiyat asla donme; "cocuk yasi" istemi zorunlu.
    phone_hf2 = _derive_phone_for_lang(base_phone, 92)
    _reset_state(root, phone_hf2, disable_welcome=True, clear_all_conversations=False)
    out_hf2 = _send_without_welcome(root, base_url, phone_hf2, "1 Ekim - 3 Ekim 2026, 2 yetişkin 2 çocuk fiyat nedir?")
    reply_hf2 = str(out_hf2.get("reply") or "")
    low_hf2 = reply_hf2.lower()
    asks_child_ages = (
        ("çocuk yaş" in low_hf2)
        or ("cocuk yas" in low_hf2)
        or ("child age" in low_hf2)
        or ("yaşlarını paylaş" in low_hf2)
        or ("yaslarini paylas" in low_hf2)
    )
    hf2_ok = asks_child_ages and (not _has_price_numbers(reply_hf2))
    rows.append(
        {
            "check": "HF2_CHILD_AGES_REQUIRED_NO_PRICE",
            "phone": phone_hf2,
            "ok": hf2_ok,
            "status": out_hf2.get("status"),
            "reply": reply_hf2,
            "detail": "If child ages missing, ask ages and do not output prices.",
        }
    )

    # HF3: Arapca fiyat sorusu handoff/paused olmamali.
    phone_hf3 = _derive_phone_for_lang(base_phone, 93)
    _reset_state(root, phone_hf3, disable_welcome=True, clear_all_conversations=False)
    out_hf3 = _send_without_welcome(
        root,
        base_url,
        phone_hf3,
        "يرجى مشاركة السعر الإجمالي لشخصين بالغين من 14 إلى 18 أغسطس 2026.",
    )
    status_hf3 = str(out_hf3.get("status") or "").lower()
    hf3_ok = (
        status_hf3 not in {"handoff", "paused"}
        and not _is_error_status(status_hf3)
        and _has_nonempty_reply(out_hf3)
    )
    rows.append(
        {
            "check": "HF3_ARABIC_PRICE_NO_HANDOFF",
            "phone": phone_hf3,
            "ok": hf3_ok,
            "status": out_hf3.get("status"),
            "reply": str(out_hf3.get("reply") or ""),
            "detail": "Arabic price query must not drop to handoff/paused.",
        }
    )

    for test_phone in (phone_hf1, phone_hf2, phone_hf3):
        _sanitize_access_controls(root, test_phone)
    return rows


def main() -> int:
    _configure_console_encoding()

    parser = argparse.ArgumentParser(description="WhatsApp hotel flow regression (live /chat).")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Backend base URL")
    parser.add_argument("--phone", default=_default_test_phone(), help="Test phone number")
    parser.add_argument("--full-flow", action="store_true", help="Run end-to-end conversation flow too")
    parser.add_argument("--language-smoke", action="store_true", help="Run multilingual smoke prompts (all supported languages)")
    parser.add_argument("--hard-fail", action="store_true", help="Run strict hard-fail suite for critical scenarios")
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
            bypass = " yes" if row.get("welcome_bypassed") else " no"
            print(f"{row['step']} status={row['status']} welcome_bypassed={bypass} reply={line}")
            if _is_error_status(row["status"]):
                failed = True
            if not row.get("welcome_bypassed"):
                failed = True
            if not _has_nonempty_reply(row):
                failed = True

    if args.language_smoke:
        rows = _run_language_smoke(root, args.base_url, phone)
        report_path = root / "tools" / "tmp_language_smoke_report.json"
        _save_json(
            report_path,
            {
                "generated_at": datetime.now().isoformat(),
                "base_url": args.base_url,
                "base_phone": phone,
                "rows": rows,
            },
        )
        print("\n[LANGUAGE_SMOKE] Transcript")
        for row in rows:
            line = (row["reply"] or "").replace("\r", " ").replace("\n", " | ")
            if len(line) > 220:
                line = line[:220] + "..."
            bypass = "yes" if row.get("welcome_bypassed") else "no"
            print(
                f"{row['step']} lang={row['lang']} status={row['status']} "
                f"welcome_bypassed={bypass} reply={line}"
            )
            if _is_error_status(row["status"]):
                failed = True
            if not row.get("welcome_bypassed"):
                failed = True
            if not _has_nonempty_reply(row):
                failed = True
            if not _reply_matches_expected_script(row["lang"], row["reply"]):
                failed = True
        print(f"[LANGUAGE_SMOKE_REPORT] {report_path}")

    if args.hard_fail:
        rows = _run_hard_fail_suite(root, args.base_url, phone)
        report_path = root / "tools" / "tmp_hard_fail_report.json"
        _save_json(
            report_path,
            {
                "generated_at": datetime.now().isoformat(),
                "base_url": args.base_url,
                "base_phone": phone,
                "rows": rows,
            },
        )
        print("\n[HARD_FAIL] Report")
        for row in rows:
            line = (row.get("reply") or "").replace("\r", " ").replace("\n", " | ")
            if len(line) > 240:
                line = line[:240] + "..."
            status_label = "PASS" if row.get("ok") else "FAIL"
            print(
                f"[{status_label}] {row.get('check')} status={row.get('status')} "
                f"phone={row.get('phone')} reply={line}"
            )
            if not row.get("ok"):
                failed = True
        print(f"[HARD_FAIL_REPORT] {report_path}")

    _sanitize_access_controls(root, phone)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
