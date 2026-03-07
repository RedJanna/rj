from __future__ import annotations

import asyncio
import threading
from datetime import datetime
from typing import Any

from app.services.metrics_service import record_metric
from app.services.structured_log_service import log_event


_QA_NOTIFY_WINDOW_SECONDS = 3600
_QA_NOTIFY_DEDUPE_SECONDS = 600
_QA_NOTIFY_LIMITS = {
    "fail": 5,
    "critical": 8,
    "error": 3,
}
_QA_NOTIFY_LOCK = threading.Lock()


def _normalize_phone(phone: str) -> str:
    return "".join(ch for ch in str(phone or "") if ch.isdigit())


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _resolve_overall_score(evaluation: dict) -> float:
    score = evaluation.get("overall_score")
    if score is not None:
        return max(0.0, min(5.0, _safe_float(score, default=0.0)))

    raw_scores = evaluation.get("scores")
    scores = raw_scores if isinstance(raw_scores, dict) else {}
    values = [_safe_float(scores.get(key), default=-1) for key in ("groundedness", "correctness", "completeness", "clarity")]
    valid_values = [v for v in values if v >= 0]
    if not valid_values:
        return 0.0
    return round(sum(valid_values) / len(valid_values), 2)


def _classify_qa_severity(evaluation: dict) -> str:
    decision = str(evaluation.get("decision", "")).strip().upper()
    overall_score = _resolve_overall_score(evaluation)
    raw_scores = evaluation.get("scores")
    scores = raw_scores if isinstance(raw_scores, dict) else {}
    correctness = _safe_float(scores.get("correctness"), default=overall_score)
    hallucinations = evaluation.get("hallucinations") or []
    has_hallucination = isinstance(hallucinations, list) and bool(hallucinations)

    if decision == "ERROR":
        return "error"
    if decision == "PASS" or overall_score >= 4.0:
        return "pass"
    if decision == "REVIEW" and overall_score >= 2.5 and not has_hallucination and correctness >= 2.5:
        return "review"
    if overall_score < 2.5 or decision == "FAIL":
        if has_hallucination or correctness <= 1.5:
            return "critical"
        return "fail"
    if has_hallucination and correctness <= 2.5:
        return "critical"
    return "fail"


def _cleanup_notification_entries(entries: list, now: datetime) -> list[dict]:
    cleaned: list[dict] = []
    for item in entries:
        # Backward compatibility for old list format: [datetime, ...]
        if isinstance(item, datetime):
            if (now - item).total_seconds() < _QA_NOTIFY_WINDOW_SECONDS:
                cleaned.append({"ts": item, "severity": "fail", "fingerprint": ""})
            continue
        if not isinstance(item, dict):
            continue
        ts = item.get("ts")
        if not isinstance(ts, datetime):
            continue
        if (now - ts).total_seconds() < _QA_NOTIFY_WINDOW_SECONDS:
            cleaned.append(
                {
                    "ts": ts,
                    "severity": str(item.get("severity") or "fail").lower(),
                    "fingerprint": str(item.get("fingerprint") or "").strip(),
                }
            )
    return cleaned


def _allow_notification(entries: list, *, now: datetime, severity: str, fingerprint: str) -> tuple[bool, int]:
    sev = (severity or "fail").lower()
    fp = (fingerprint or "").strip()
    with _QA_NOTIFY_LOCK:
        cleaned = _cleanup_notification_entries(entries, now)
        entries[:] = cleaned

        recent_same = [
            item
            for item in cleaned
            if item["severity"] == sev and item["fingerprint"] == fp and (now - item["ts"]).total_seconds() < _QA_NOTIFY_DEDUPE_SECONDS
        ]
        if recent_same:
            return False, len(cleaned)

        limit = _QA_NOTIFY_LIMITS.get(sev, _QA_NOTIFY_LIMITS["fail"])
        recent_same_severity = [item for item in cleaned if item["severity"] == sev]
        if len(recent_same_severity) >= limit:
            return False, len(cleaned)

        cleaned.append({"ts": now, "severity": sev, "fingerprint": fp})
        entries[:] = cleaned
        return True, len(cleaned)


def maybe_start_qa_background(
    *,
    qa_enabled: bool,
    qa_agent,
    user_message: str,
    reply: str,
    phone: str,
    admin_phone: str,
    send_whatsapp_message_fn,
    qa_fail_notifications: list,
):
    if not (qa_enabled and reply and user_message):
        return

    try:
        def run_qa():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                evaluation = loop.run_until_complete(qa_agent.evaluate(user_message, reply, phone))
                overall_score = _resolve_overall_score(evaluation)
                severity = _classify_qa_severity(evaluation)
                decision = str(evaluation.get("decision", "")).strip().upper() or "UNKNOWN"
                raw_scores = evaluation.get("scores")
                scores = raw_scores if isinstance(raw_scores, dict) else {}
                issues = evaluation.get("issues") if isinstance(evaluation.get("issues"), list) else []
                suggestions = evaluation.get("suggestions") if isinstance(evaluation.get("suggestions"), list) else []
                hallucinations = evaluation.get("hallucinations") if isinstance(evaluation.get("hallucinations"), list) else []

                record_metric(
                    "qa.evaluation",
                    category=severity,
                    meta={
                        "decision": decision,
                        "overall_score": overall_score,
                        "phone_masked": f"{str(phone or '')[:6]}***",
                        "issue_count": len(issues),
                        "hallucination_count": len(hallucinations),
                    },
                )
                log_event(
                    "qa.evaluation.completed",
                    level="WARNING" if severity in {"fail", "critical", "error"} else "INFO",
                    phone=f"{str(phone or '')[:6]}***",
                    decision=decision,
                    severity=severity,
                    overall_score=overall_score,
                    issue_count=len(issues),
                    hallucination_count=len(hallucinations),
                )

                if severity in {"pass", "review"}:
                    return

                now = datetime.now()
                first_issue = issues[0] if issues else ""
                fingerprint = f"{severity}|{decision}|{first_issue[:80]}|{len(reply)}"
                allowed, active_count = _allow_notification(
                    qa_fail_notifications,
                    now=now,
                    severity=severity,
                    fingerprint=fingerprint,
                )
                if not allowed:
                    print(f"⚠️ QA - bildirim atlandı (limit/dupe), seviye={severity}, kayıt={active_count}")
                    return

                if severity == "critical":
                    emoji = "🚨"
                    level = "CRITICAL"
                elif severity == "error":
                    emoji = "⚠️"
                    level = "ENGINE"
                else:
                    emoji = "🔴"
                    level = "FAIL"

                score_line = (
                    f"📊 Skor: {overall_score}/5 | Karar: {decision}\n"
                    f"📐 G:{_safe_float(scores.get('groundedness'), 0):.1f} "
                    f"C:{_safe_float(scores.get('correctness'), 0):.1f} "
                    f"K:{_safe_float(scores.get('completeness'), 0):.1f} "
                    f"A:{_safe_float(scores.get('clarity'), 0):.1f}"
                )
                notify_msg = f"""{emoji} QA {level} UYARISI
{score_line}
📱 Telefon: {str(phone or '')[:6]}***
❓ Müşteri:
{user_message[:150]}
🤖 Bot:
{reply[:200]}
⚠️ Sorunlar:
{chr(10).join(['• ' + str(i) for i in issues[:3]]) if issues else '• Belirtilmedi'}
💡 Öneri:
{str(suggestions[0])[:120] if suggestions else 'Belirtilmedi'}
🧪 Halüsinasyon:
{str(hallucinations[0])[:120] if hallucinations else 'Yok'}"""

                # Admin numarası test edilen müşteri ile aynıysa müşteri sohbetini kirletme.
                if _normalize_phone(admin_phone) and _normalize_phone(admin_phone) == _normalize_phone(phone):
                    print("⚠️ QA bildirimi atlandı: admin_phone müşteri telefonu ile aynı")
                    return
                loop.run_until_complete(send_whatsapp_message_fn(admin_phone, notify_msg))
                print(f"📤 QA {level} bildirimi gönderildi (seviye={severity}, kayıt={active_count})")
            finally:
                loop.close()

        qa_thread = threading.Thread(target=run_qa, daemon=True)
        qa_thread.start()
    except Exception as e:
        print(f"QA thread hatası: {e}")
