from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from app.services.active_learning_service import ACTIVE_LEARNING_FILE


SCENARIO_TEMPLATE_PATH = Path("templates/Senaryo template.txt")
DEFAULT_NOVELTY_REASONS = ("low_confidence", "unresolved", "unknown", "fallback", "ambiguous")


@dataclass
class TopicCandidate:
    predicted_intent: str
    message: str
    language: str
    confidence: float | None
    reason: str
    sample_count: int = 1


def _load_template(path: Path) -> str:
    try:
        raw = path.read_text(encoding="utf-8").strip()
        if raw:
            return raw
    except Exception:
        pass
    return (
        "Senaryo Başlığı: {topic_title}\n"
        "Örnek Mesaj: {sample_message}\n"
        "Tahmini Intent: {predicted_intent}\n"
        "Dil: {language}\n"
        "Güven: {confidence}\n"
        "Neden Yeni Konu?: {reason}\n"
        "Önerilen Aksiyon: {suggested_action}\n"
    )


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
        except Exception:
            continue
    return rows


def _is_today(ts_value: str, now: datetime) -> bool:
    raw = (ts_value or "").strip()
    if not raw:
        return False
    try:
        return datetime.fromisoformat(raw).date() == now.date()
    except Exception:
        return False


def _is_novel_candidate(row: dict[str, Any]) -> bool:
    predicted = str(row.get("predicted_intent") or "").strip().upper()
    reason = str(row.get("reason") or "").strip().lower()
    confidence = _safe_float(row.get("confidence"))
    if predicted in {"OUT_OF_SCOPE_OTHER", ""}:
        return True
    if confidence is not None and confidence < 0.55:
        return True
    return any(marker in reason for marker in DEFAULT_NOVELTY_REASONS)


def _topic_key(row: dict[str, Any]) -> str:
    predicted = str(row.get("predicted_intent") or "OUT_OF_SCOPE_OTHER").strip().upper()
    text = " ".join(str(row.get("message") or "").strip().lower().split())
    # Same intent + first semantic chunk => same topic cluster for daily report.
    return f"{predicted}|{text[:80]}"


def collect_daily_novel_topics(*, now: datetime | None = None) -> list[TopicCandidate]:
    current = now or datetime.now()
    grouped: dict[str, TopicCandidate] = {}
    for row in _iter_jsonl(ACTIVE_LEARNING_FILE):
        if not _is_today(str(row.get("ts") or ""), current):
            continue
        if not _is_novel_candidate(row):
            continue
        key = _topic_key(row)
        if key in grouped:
            grouped[key].sample_count += 1
            continue
        grouped[key] = TopicCandidate(
            predicted_intent=str(row.get("predicted_intent") or "OUT_OF_SCOPE_OTHER").strip().upper() or "OUT_OF_SCOPE_OTHER",
            message=str(row.get("message") or "").strip(),
            language=str(row.get("lang") or "tr").strip().lower() or "tr",
            confidence=_safe_float(row.get("confidence")),
            reason=str(row.get("reason") or "belirsiz_sinyal").strip() or "belirsiz_sinyal",
            sample_count=1,
        )
    return sorted(grouped.values(), key=lambda x: x.sample_count, reverse=True)


def _format_scenario_block(template_text: str, topic: TopicCandidate) -> str:
    confidence = "n/a" if topic.confidence is None else f"{topic.confidence:.2f}"
    intent_name = topic.predicted_intent if topic.predicted_intent != "OUT_OF_SCOPE_OTHER" else "YENI_INTENT_ADAYI"
    action = "Intent taxonomy'ye yeni senaryo ekle, test verisi üret ve edge-case regresyonuna dahil et."
    title = f"{intent_name} | tekrar={topic.sample_count}"
    return template_text.format(
        topic_title=title,
        sample_message=topic.message,
        predicted_intent=topic.predicted_intent,
        language=topic.language,
        confidence=confidence,
        reason=topic.reason,
        suggested_action=action,
    ).strip()


def build_daily_learning_report(*, now: datetime | None = None) -> str:
    current = now or datetime.now()
    topics = collect_daily_novel_topics(now=current)
    date_str = current.strftime("%Y-%m-%d")
    template_text = _load_template(SCENARIO_TEMPLATE_PATH)

    if not topics:
        return (
            f"📘 Günlük Öğrenme Raporu ({date_str})\n"
            "Yeni/farklı konu algılanmadı.\n"
            "Active learning kuyruğu incelendi, admin aksiyonu gerekmiyor."
        )

    header = (
        f"📘 Günlük Öğrenme Raporu ({date_str})\n"
        f"Yeni/Farklı Konu Sayısı: {len(topics)}\n"
        "Aşağıdaki senaryolar `Senaryo template.txt` formatında admin onayına sunulmalıdır.\n"
    )
    blocks = []
    for i, topic in enumerate(topics, start=1):
        blocks.append(f"\n[{i}] {_format_scenario_block(template_text, topic)}")
    return header + "\n".join(blocks)
