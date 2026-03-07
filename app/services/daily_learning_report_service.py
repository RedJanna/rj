from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from app.services.active_learning_service import ACTIVE_LEARNING_FILE


SCENARIO_TEMPLATE_PATH = Path("templates/Senaryo template.txt")
SCENARIO_DRAFT_TEMPLATE_PATH = Path("templates/senaryo_template_ornek.txt")
TOPIC_REVIEW_FILE = Path("data/scenario_review_queue.json")
EXTERNAL_SCENARIOS_FILE = Path("tests/golden/scenarios/external_scenarios.json")
INTENT_EXAMPLES_FILE = Path("app/content/scenario_intent_examples.json")
NEW_SCENARIOS_DIR = Path("yenı_senaryolar")
SCENARIO_INGEST_STATE_FILE = Path("data/scenario_draft_ingest_state.json")
SCENARIO_DRAFT_MODEL = "gpt-5.2"
DEFAULT_NOVELTY_REASONS = ("low_confidence", "unresolved", "unknown", "fallback", "ambiguous")
VALID_TOPIC_STATUSES = {"pending", "draft_ready", "approved", "rejected"}
DEFAULT_SAMPLE_FALLBACK = "Yeni konu ornegi bulunamadi."
SLOT_SECTION_RE = re.compile(
    r"(?ms)^📥 Gerekli Bilgiler \(Slotlar - En Fazla 5\):\n(?:.*?\n)*?(?=^\s*⚙️ Karar Kuralı \(Business Logic\):)"
)

SLOT_LABELS: dict[str, str] = {
    "check_in_date": "Giriş Tarihi",
    "check_out_date": "Çıkış Tarihi",
    "adult_count": "Yetişkin Sayısı",
    "child_count": "Çocuk Sayısı",
    "child_ages": "Çocuk Yaşları",
    "room_type": "Oda Tipi",
    "board_type": "Pansiyon Tipi",
    "budget": "Bütçe Aralığı",
    "customer_name": "Misafir Ad Soyad",
    "customer_phone": "Telefon Numarası",
    "customer_email": "E-posta",
    "booking_ref_or_match_key": "Rezervasyon Referansı",
    "change_fields": "Değişiklik Alanları",
    "new_check_in_date": "Yeni Giriş Tarihi",
    "new_check_out_date": "Yeni Çıkış Tarihi",
    "new_adult_count": "Yeni Yetişkin Sayısı",
    "new_child_count": "Yeni Çocuk Sayısı",
    "new_child_ages": "Yeni Çocuk Yaşları",
    "new_room_type": "Yeni Oda Tipi",
    "new_special_requests": "Yeni Özel Not",
    "cancel_reason": "İptal Nedeni",
    "reservation_date": "Rezervasyon Tarihi",
    "reservation_time": "Rezervasyon Saati",
    "guest_count": "Kişi Sayısı",
    "reservation_name": "Rezervasyon Adı",
    "phone": "Telefon Numarası",
    "restaurant_booking_ref_or_match_key": "Restoran Referansı",
    "transfer_date": "Transfer Tarihi",
    "transfer_time": "Transfer Saati",
    "flight_no": "Uçuş Numarası",
    "route": "Transfer Rotası",
    "luggage_count": "Bagaj Sayısı",
    "baby_seat": "Bebek Koltuğu",
    "booking_ref": "Rezervasyon Kodu",
    "faq_topic": "Bilgi Konusu",
    "complaint_text": "Şikayet Metni",
    "target_product_or_booking_context": "İndirim Konusu",
    "event_type": "Etkinlik Türü",
    "event_date": "Etkinlik Tarihi",
    "urgent_reason": "Aciliyet Nedeni",
    "contact_phone": "İletişim Telefonu",
    "risk_text": "Riskli İçerik",
    "risk_type": "Risk Türü",
}

SLOT_FORMAT_HINTS: dict[str, str] = {
    "check_in_date": "gg/aa/yyyy (sistem normalize eder)",
    "check_out_date": "gg/aa/yyyy (sistem normalize eder)",
    "adult_count": "Tam sayı, en az 1",
    "child_count": "Tam sayı (yoksa 0)",
    "child_ages": "Örn: 4, 7",
    "customer_phone": "Ülke kodu dahil yazılabilir; sistem normalize eder",
    "phone": "Ülke kodu dahil yazılabilir; sistem normalize eder",
    "reservation_date": "gg/aa/yyyy (sistem normalize eder)",
    "reservation_time": "ss:dd (24 saat)",
    "guest_count": "Tam sayı, en az 1",
    "transfer_date": "gg/aa/yyyy (sistem normalize eder)",
    "transfer_time": "ss:dd (24 saat)",
    "flight_no": "Örn: TK1234",
    "booking_ref_or_match_key": "CTX-... veya telefon+isim",
    "booking_ref": "CTX-... formatı",
    "route": "Örn: Dalaman Havalimanı -> Kassandra",
}


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


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _topic_key(row: dict[str, Any]) -> str:
    predicted = str(row.get("predicted_intent") or "OUT_OF_SCOPE_OTHER").strip().upper()
    text = _normalize_text(str(row.get("message") or ""))
    # Same intent + first semantic chunk => same topic cluster for daily report.
    return f"{predicted}|{text[:80]}"


def _candidate_id(*, predicted_intent: str, message: str) -> str:
    base = f"{(predicted_intent or '').strip().upper()}|{_normalize_text(message)[:120]}"
    digest = hashlib.sha256(base.encode("utf-8", errors="ignore")).hexdigest()
    return f"al-{digest[:12]}"


def _topic_to_candidate_id(topic: TopicCandidate) -> str:
    return _candidate_id(predicted_intent=topic.predicted_intent, message=topic.message)


def _now_iso(now: datetime | None = None) -> str:
    return (now or datetime.now()).isoformat(timespec="seconds")


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def _sha256_text(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8", errors="ignore")).hexdigest()


def _load_topic_review_items() -> list[dict[str, Any]]:
    payload = _load_json(TOPIC_REVIEW_FILE, {"items": []})
    if not isinstance(payload, dict):
        return []
    items = payload.get("items", [])
    if not isinstance(items, list):
        return []
    clean_items: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict) and str(item.get("candidate_id") or "").strip():
            clean_items.append(item)
    return clean_items


def _save_topic_review_items(items: list[dict[str, Any]]) -> None:
    _atomic_write_json(TOPIC_REVIEW_FILE, {"items": items})


def _load_ingest_state() -> dict[str, Any]:
    payload = _load_json(SCENARIO_INGEST_STATE_FILE, {"processed_files": {}, "processed_hashes": []})
    if not isinstance(payload, dict):
        return {"processed_files": {}, "processed_hashes": []}
    processed_files = payload.get("processed_files")
    if not isinstance(processed_files, dict):
        processed_files = {}
    processed_hashes = payload.get("processed_hashes")
    if not isinstance(processed_hashes, list):
        processed_hashes = []
    return {"processed_files": processed_files, "processed_hashes": processed_hashes}


def _save_ingest_state(state: dict[str, Any]) -> None:
    _atomic_write_json(SCENARIO_INGEST_STATE_FILE, state)


def _sanitize_language(lang: str) -> str:
    value = (lang or "").strip().lower()
    if value in {"tr", "en", "ru"}:
        return value
    return "tr"


def _intent_to_category(intent: str) -> str:
    mapping = {
        "HOTEL_BOOKING_CREATE": "hotel_booking",
        "HOTEL_BOOKING_MODIFY": "hotel_booking",
        "HOTEL_BOOKING_CANCEL": "hotel_booking",
        "PRICE_QUERY": "hotel_pricing",
        "AVAILABILITY_QUERY": "hotel_pricing",
        "LOCAL_FAQ_INFO": "info",
        "PAYMENT_METHOD_QUERY": "payment",
        "PAYMENT_LINK_REQUEST": "payment",
        "DISCOUNT_NEGOTIATION": "payment",
        "HUMAN_AGENT_REQUEST": "handoff",
        "COMPLAINT": "handoff",
        "URGENT_CASE": "handoff",
        "RISK_ABUSE": "handoff",
        "RESTAURANT_BOOKING_CREATE": "restaurant",
        "RESTAURANT_BOOKING_MODIFY": "restaurant",
        "RESTAURANT_BOOKING_CANCEL": "restaurant",
        "TRANSFER_INFO": "transfer",
        "TRANSFER_BOOKING_REQUEST": "transfer",
        "SPECIAL_REQUEST_EVENT": "special_request",
        "OUT_OF_SCOPE_OTHER": "learning",
    }
    return mapping.get((intent or "").strip().upper(), "learning")


def _scenario_id_for_candidate(candidate_id: str, existing_ids: set[str]) -> str:
    suffix = "".join(ch for ch in candidate_id.lower() if ch.isalnum())[-12:] or "candidate"
    base = f"al_{suffix}"
    if base not in existing_ids:
        return base
    index = 2
    while f"{base}_{index}" in existing_ids:
        index += 1
    return f"{base}_{index}"


def sync_daily_topic_candidates(*, now: datetime | None = None) -> list[dict[str, Any]]:
    current = now or datetime.now()
    now_iso = _now_iso(current)
    topics = collect_daily_novel_topics(now=current)
    items = _load_topic_review_items()
    by_id = {str(item.get("candidate_id")): item for item in items}

    for topic in topics:
        candidate_id = _topic_to_candidate_id(topic)
        existing = by_id.get(candidate_id)
        if existing:
            existing["predicted_intent"] = topic.predicted_intent
            existing["sample_message"] = topic.message or existing.get("sample_message") or DEFAULT_SAMPLE_FALLBACK
            existing["language"] = _sanitize_language(topic.language)
            existing["confidence"] = topic.confidence
            existing["reason"] = topic.reason
            existing["sample_count"] = int(topic.sample_count)
            existing["last_seen_at"] = now_iso
            existing["updated_at"] = now_iso
            status = str(existing.get("status") or "").strip().lower()
            if status not in VALID_TOPIC_STATUSES:
                existing["status"] = "pending"
            continue

        new_item = {
            "candidate_id": candidate_id,
            "status": "pending",
            "predicted_intent": topic.predicted_intent,
            "sample_message": topic.message or DEFAULT_SAMPLE_FALLBACK,
            "language": _sanitize_language(topic.language),
            "confidence": topic.confidence,
            "reason": topic.reason,
            "sample_count": int(topic.sample_count),
            "created_at": now_iso,
            "first_seen_at": now_iso,
            "last_seen_at": now_iso,
            "updated_at": now_iso,
        }
        items.append(new_item)
        by_id[candidate_id] = new_item

    _save_topic_review_items(items)
    return items


def list_topic_candidates(*, status: str | None = "pending", limit: int = 50) -> list[dict[str, Any]]:
    normalized_status = (status or "").strip().lower()
    items = _load_topic_review_items()
    if normalized_status and normalized_status in VALID_TOPIC_STATUSES:
        items = [item for item in items if str(item.get("status") or "").strip().lower() == normalized_status]
    items.sort(key=lambda row: str(row.get("updated_at") or ""), reverse=True)
    return items[: max(1, int(limit))]


def _upsert_external_scenario(*, candidate: dict[str, Any], now: datetime) -> tuple[str, bool]:
    payload = _load_json(EXTERNAL_SCENARIOS_FILE, {"scenarios": []})
    scenarios = payload.get("scenarios", [])
    if not isinstance(scenarios, list):
        scenarios = []
    payload["scenarios"] = scenarios

    intent = str(candidate.get("predicted_intent") or "OUT_OF_SCOPE_OTHER").strip().upper() or "OUT_OF_SCOPE_OTHER"
    question = str(candidate.get("sample_message") or "").strip()
    question_norm = _normalize_text(question)
    for existing in scenarios:
        if not isinstance(existing, dict):
            continue
        existing_intent = str(existing.get("intent") or "").strip().upper()
        existing_question = _normalize_text(str(existing.get("question") or ""))
        if existing_intent == intent and existing_question and existing_question == question_norm:
            return str(existing.get("id") or ""), False

    existing_ids = {
        str(item.get("id") or "").strip().lower()
        for item in scenarios
        if isinstance(item, dict)
    }
    scenario_id = _scenario_id_for_candidate(str(candidate.get("candidate_id") or ""), existing_ids)
    scenario = {
        "id": scenario_id,
        "source_id": f"AL-{scenario_id.upper()}",
        "category": _intent_to_category(intent),
        "intent": intent,
        "question": question,
        "description": f"Active learning onayi ({now.date().isoformat()})",
        "is_core": False,
        "smoke": False,
        "language": _sanitize_language(str(candidate.get("language") or "tr")),
    }
    scenarios.append(scenario)
    _atomic_write_json(EXTERNAL_SCENARIOS_FILE, payload)
    return scenario_id, True


def _upsert_intent_example(*, candidate: dict[str, Any]) -> bool:
    payload = _load_json(INTENT_EXAMPLES_FILE, {"intent_examples": {}})
    raw = payload.get("intent_examples")
    if not isinstance(raw, dict):
        raw = {}
    payload["intent_examples"] = raw

    intent = str(candidate.get("predicted_intent") or "OUT_OF_SCOPE_OTHER").strip().upper() or "OUT_OF_SCOPE_OTHER"
    question = str(candidate.get("sample_message") or "").strip()
    if not question:
        return False

    examples = raw.get(intent)
    if not isinstance(examples, list):
        examples = []
        raw[intent] = examples

    question_norm = _normalize_text(question)
    for item in examples:
        if _normalize_text(str(item)) == question_norm:
            return False

    examples.append(question)
    _atomic_write_json(INTENT_EXAMPLES_FILE, payload)
    return True


def _refresh_intent_examples_cache() -> None:
    try:
        from app.services.intent_semantic_service import clear_intent_examples_cache

        clear_intent_examples_cache()
    except Exception:
        return


def _slot_label(slot_name: str) -> str:
    slot = (slot_name or "").strip()
    if slot in SLOT_LABELS:
        return SLOT_LABELS[slot]
    return slot.replace("_", " ").strip().title()


def _slot_hint(slot_name: str) -> str:
    slot = (slot_name or "").strip()
    return SLOT_FORMAT_HINTS.get(slot, "Sistem doğrulama/normalizasyon kurallarına göre")


def _render_required_slots_section(intent_name: str, max_slots: int = 5) -> str:
    from app.content.intent_slot_contract import INTENT_SLOT_CONTRACT

    contract = INTENT_SLOT_CONTRACT.get((intent_name or "").strip().upper(), {})
    required_slots = [str(s).strip() for s in (contract.get("required_slots") or []) if str(s).strip()]
    optional_slots = [str(s).strip() for s in (contract.get("optional_slots") or []) if str(s).strip()]

    ordered_slots: list[str] = []
    for slot in required_slots + optional_slots:
        if slot not in ordered_slots:
            ordered_slots.append(slot)

    selected = ordered_slots[: max(1, int(max_slots))]
    if not selected:
        selected = ["free_text_topic"]

    lines = ["📥 Gerekli Bilgiler (Slotlar - En Fazla 5):"]
    for idx, slot in enumerate(selected, start=1):
        lines.append(f"{idx}) {_slot_label(slot)}: ({_slot_hint(slot)})")
    return "\n".join(lines)


def _build_hotel_grounding_context(intent_name: str) -> str:
    from app.content.automation_info import AUTOMATION_RUNTIME_RULES
    from app.content.intent_slot_contract import INTENT_SLOT_CONTRACT
    from app.services.intent_policy_service import INTENT_SLOT_TOOL_MATRIX

    intent = (intent_name or "").strip().upper() or "OUT_OF_SCOPE_OTHER"
    contract = INTENT_SLOT_CONTRACT.get(intent, {})
    policy = INTENT_SLOT_TOOL_MATRIX.get(intent, {})

    required_slots = [str(s).strip() for s in (contract.get("required_slots") or []) if str(s).strip()]
    optional_slots = [str(s).strip() for s in (contract.get("optional_slots") or []) if str(s).strip()]
    validation_rules = [str(s).strip() for s in (contract.get("validation_rules") or []) if str(s).strip()]
    allowed_tools = [str(s).strip() for s in (policy.get("allowed_tools") or []) if str(s).strip()]
    clarify_prompt = str(contract.get("clarify_prompt_tr") or "").strip()

    handoff_rules = AUTOMATION_RUNTIME_RULES.get("handoff", {}) if isinstance(AUTOMATION_RUNTIME_RULES, dict) else {}
    supported_langs = (
        AUTOMATION_RUNTIME_RULES.get("language_policy", {}).get("supported", [])
        if isinstance(AUTOMATION_RUNTIME_RULES, dict)
        else []
    )

    stable_rules = [
        "SEZON: 10 Nisan - 10 Kasım (sezon dışı rezervasyon/transfer/restoran işlemi yok).",
        "GEC GIRIS: 14:00 sonrası girişte 'müsaitlik kontrolü' söylemi kullanılmaz.",
        "TRANSFER-DALAMAN: tek yön 75 EUR, nakit; zorunlu transfer alanları eksiksiz toplanır.",
        "TRANSFER-ANTALYA: fiyat/detay için canlı müşteri temsilcisine devir.",
    ]

    return (
        "SISTEM DOGRU KAYNAK OZETI:\n"
        f"- intent: {intent}\n"
        f"- required_slots: {required_slots}\n"
        f"- optional_slots: {optional_slots}\n"
        f"- validation_rules: {validation_rules}\n"
        f"- clarify_prompt_tr: {clarify_prompt}\n"
        f"- allowed_tools: {allowed_tools}\n"
        f"- language_policy.supported: {supported_langs}\n"
        f"- handoff_keywords: {handoff_rules.get('special_request_hard_handoff_keywords', [])}\n"
        + "\n".join(f"- {rule}" for rule in stable_rules)
    )


def _enforce_required_slots_section(text: str, intent_name: str) -> str:
    draft = str(text or "").strip()
    section = _render_required_slots_section(intent_name)
    marker = "⚙️ Karar Kuralı (Business Logic):"

    if SLOT_SECTION_RE.search(draft):
        patched = SLOT_SECTION_RE.sub(section + "\n\n", draft, count=1)
        return patched.strip()

    if marker in draft:
        return draft.replace(marker, section + "\n\n" + marker, 1).strip()

    return (draft + "\n\n" + section).strip()


def _generate_scenario_text_with_gpt52(*, candidate: dict[str, Any], template_text: str) -> str:
    api_key = (os.getenv("OPENAI_API_KEY", "") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY tanimli degil.")

    try:
        from openai import OpenAI
    except Exception as exc:
        raise RuntimeError(f"OpenAI SDK yuklenemedi: {exc}") from exc

    client = OpenAI(api_key=api_key)
    sample_message = str(candidate.get("sample_message") or "").strip() or DEFAULT_SAMPLE_FALLBACK
    intent_name = str(candidate.get("predicted_intent") or "OUT_OF_SCOPE_OTHER").strip().upper() or "OUT_OF_SCOPE_OTHER"
    language = _sanitize_language(str(candidate.get("language") or "tr"))
    reason = str(candidate.get("reason") or "").strip()
    sample_count = int(candidate.get("sample_count") or 1)
    confidence = candidate.get("confidence")
    confidence_text = "n/a" if confidence is None else f"{float(confidence):.2f}"
    required_slot_section = _render_required_slots_section(intent_name)
    grounding_context = _build_hotel_grounding_context(intent_name)

    system_prompt = (
        "Sen Kassandra oteli icin operasyon senaryosu yazan bir uzmansin. "
        "Her zaman girdi sablonunu koru. Cikti duz metin olsun. "
        "Bosluk birakma, doldurulamayan yerleri makul varsayimla tamamla."
    )
    user_prompt = (
        "Asagidaki template'i baz alarak yeni bir senaryo metni uret.\n\n"
        f"TEMPLATE:\n{template_text}\n\n"
        f"INTENTE GORE ZORUNLU SLOT BLOKU (aynen kullan):\n{required_slot_section}\n\n"
        f"HOTEL VERISI VE KURAL BAGLAMI:\n{grounding_context}\n\n"
        "ADAY BILGILERI:\n"
        f"- candidate_id: {candidate.get('candidate_id')}\n"
        f"- ornek_mesaj: {sample_message}\n"
        f"- tahmini_intent: {intent_name}\n"
        f"- dil: {language}\n"
        f"- guven: {confidence_text}\n"
        f"- neden: {reason}\n"
        f"- tekrar_sayisi: {sample_count}\n\n"
        "Kurallar:\n"
        "- Cikti sadece senaryo metni olsun, aciklama ekleme.\n"
        "- Kanal WhatsApp kabul et.\n"
        "- '📥 Gerekli Bilgiler' bolumunde yukaridaki zorunlu slot blogunu AYNI YAPIYLA kullan.\n"
        "- Slot adlari/formatlari sistem kontratlariyla CELISEMEZ.\n"
        "- Maksimum 5 slot yaz.\n"
        "- Turkce yaz.\n"
    )
    completion = client.chat.completions.create(
        model=SCENARIO_DRAFT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_completion_tokens=1800,
    )
    content = completion.choices[0].message.content if completion and completion.choices else ""
    text = str(content or "").strip()
    if not text:
        raise RuntimeError("GPT-5.2 bos senaryo dondu.")
    return _enforce_required_slots_section(text, intent_name)


def _candidate_draft_filename(candidate: dict[str, Any], revision: int) -> str:
    candidate_id = str(candidate.get("candidate_id") or "candidate").strip() or "candidate"
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", candidate_id)
    return f"{safe}_rev{max(1, int(revision))}.txt"


def request_topic_candidate_draft(
    candidate_id: str,
    *,
    requested_by: str = "admin",
    note: str = "",
    force_regenerate: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or datetime.now()
    now_iso = _now_iso(current)
    target_id = (candidate_id or "").strip()
    if not target_id:
        return {"success": False, "error": "candidate_id_required"}

    items = _load_topic_review_items()
    target = next((item for item in items if str(item.get("candidate_id")) == target_id), None)
    if target is None:
        return {"success": False, "error": "candidate_not_found", "candidate_id": target_id}

    status = str(target.get("status") or "").strip().lower()
    if status == "approved":
        return {"success": False, "error": "candidate_already_approved", "candidate_id": target_id}
    if status == "rejected":
        return {"success": False, "error": "candidate_rejected", "candidate_id": target_id}

    existing_draft_path = str(target.get("draft_file_path") or "").strip()
    if status == "draft_ready" and existing_draft_path and not force_regenerate:
        return {
            "success": True,
            "candidate_id": target_id,
            "already_generated": True,
            "draft_file_path": existing_draft_path,
            "draft_model": target.get("draft_model"),
            "draft_revision": int(target.get("draft_revision") or 1),
        }

    sample_message = str(target.get("sample_message") or "").strip()
    if not sample_message:
        return {"success": False, "error": "candidate_message_empty", "candidate_id": target_id}

    template_text = _load_template(SCENARIO_DRAFT_TEMPLATE_PATH)
    try:
        draft_text = _generate_scenario_text_with_gpt52(candidate=target, template_text=template_text)
    except Exception as exc:
        return {
            "success": False,
            "error": "draft_generation_failed",
            "message": str(exc),
            "candidate_id": target_id,
            "draft_model": SCENARIO_DRAFT_MODEL,
        }
    revision = int(target.get("draft_revision") or 0) + 1
    draft_filename = _candidate_draft_filename(target, revision=revision)
    NEW_SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)
    draft_path = NEW_SCENARIOS_DIR / draft_filename
    draft_path.write_text(draft_text.strip() + "\n", encoding="utf-8")

    target["status"] = "draft_ready"
    target["draft_file_path"] = str(draft_path)
    target["draft_generated_at"] = now_iso
    target["draft_model"] = SCENARIO_DRAFT_MODEL
    target["draft_revision"] = revision
    target["draft_requested_by"] = (requested_by or "admin").strip() or "admin"
    target["draft_note"] = (note or "").strip()
    target["updated_at"] = now_iso
    _save_topic_review_items(items)

    return {
        "success": True,
        "candidate_id": target_id,
        "draft_file_path": str(draft_path),
        "draft_model": SCENARIO_DRAFT_MODEL,
        "draft_revision": revision,
    }


def finalize_topic_candidate_approval(
    candidate_id: str,
    *,
    approved_by: str = "admin",
    note: str = "",
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or datetime.now()
    now_iso = _now_iso(current)
    target_id = (candidate_id or "").strip()
    if not target_id:
        return {"success": False, "error": "candidate_id_required"}

    items = _load_topic_review_items()
    target = next((item for item in items if str(item.get("candidate_id")) == target_id), None)
    if target is None:
        return {"success": False, "error": "candidate_not_found", "candidate_id": target_id}

    status = str(target.get("status") or "").strip().lower()
    if status == "approved":
        return {
            "success": True,
            "candidate_id": target_id,
            "already_approved": True,
            "external_scenario_id": target.get("external_scenario_id"),
            "intent_examples_updated": False,
        }
    if status != "draft_ready":
        return {"success": False, "error": "draft_required_before_final_approval", "candidate_id": target_id}

    scenario_id, scenario_created = _upsert_external_scenario(candidate=target, now=current)
    intent_example_added = _upsert_intent_example(candidate=target)

    target["status"] = "approved"
    target["approved_at"] = now_iso
    target["approved_by"] = (approved_by or "admin").strip() or "admin"
    target["approval_note"] = (note or "").strip()
    target["external_scenario_id"] = scenario_id
    target["updated_at"] = now_iso
    _save_topic_review_items(items)
    _refresh_intent_examples_cache()

    return {
        "success": True,
        "candidate_id": target_id,
        "external_scenario_id": scenario_id,
        "external_scenario_created": bool(scenario_created),
        "intent_examples_updated": bool(intent_example_added),
    }


def ingest_new_scenario_drafts(
    *,
    approved_by: str = "admin",
    note: str = "",
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or datetime.now()
    now_iso = _now_iso(current)
    NEW_SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)
    draft_files = sorted(NEW_SCENARIOS_DIR.glob("*.txt"))
    ingest_state = _load_ingest_state()
    processed_files = ingest_state.get("processed_files", {})
    processed_hashes = set(str(x) for x in ingest_state.get("processed_hashes", []))
    results: list[dict[str, Any]] = []
    integrated = 0
    skipped = 0
    pattern = re.compile(r"(al-[a-f0-9]{12})_rev\d+\.txt$", re.IGNORECASE)

    for fp in draft_files:
        rel_key = str(fp).replace("\\", "/")
        if rel_key in processed_files:
            skipped += 1
            results.append({"file": rel_key, "status": "skipped_already_processed"})
            continue

        try:
            text = fp.read_text(encoding="utf-8")
        except Exception as exc:
            skipped += 1
            results.append({"file": rel_key, "status": "read_error", "error": str(exc)})
            continue

        content_hash = _sha256_text(text)
        if content_hash in processed_hashes:
            skipped += 1
            processed_files[rel_key] = {
                "processed_at": now_iso,
                "status": "skipped_duplicate_content",
                "sha256": content_hash,
            }
            results.append({"file": rel_key, "status": "skipped_duplicate_content"})
            continue

        m = pattern.search(fp.name)
        if not m:
            skipped += 1
            results.append({"file": rel_key, "status": "skipped_unrecognized_filename"})
            continue

        candidate_id = m.group(1).lower()
        final_note = f"{note.strip()} | source_file={fp.name}".strip(" |")
        final = finalize_topic_candidate_approval(
            candidate_id,
            approved_by=approved_by,
            note=final_note,
            now=current,
        )
        if not final.get("success"):
            skipped += 1
            results.append(
                {
                    "file": rel_key,
                    "candidate_id": candidate_id,
                    "status": "skipped_finalize_error",
                    "error": final.get("error") or final.get("message") or "unknown_error",
                }
            )
            continue

        integrated += 1
        processed_hashes.add(content_hash)
        processed_files[rel_key] = {
            "processed_at": now_iso,
            "status": "integrated",
            "candidate_id": candidate_id,
            "external_scenario_id": final.get("external_scenario_id"),
            "sha256": content_hash,
        }
        results.append(
            {
                "file": rel_key,
                "candidate_id": candidate_id,
                "status": "integrated",
                "external_scenario_id": final.get("external_scenario_id"),
            }
        )

    ingest_state["processed_files"] = processed_files
    ingest_state["processed_hashes"] = sorted(processed_hashes)
    _save_ingest_state(ingest_state)

    return {
        "success": True,
        "integrated_count": integrated,
        "skipped_count": skipped,
        "total_files": len(draft_files),
        "results": results,
    }


def reject_topic_candidate(
    candidate_id: str,
    *,
    rejected_by: str = "admin",
    reason: str = "",
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or datetime.now()
    now_iso = _now_iso(current)
    target_id = (candidate_id or "").strip()
    if not target_id:
        return {"success": False, "error": "candidate_id_required"}

    items = _load_topic_review_items()
    target = next((item for item in items if str(item.get("candidate_id")) == target_id), None)
    if target is None:
        return {"success": False, "error": "candidate_not_found", "candidate_id": target_id}

    target["status"] = "rejected"
    target["rejected_at"] = now_iso
    target["rejected_by"] = (rejected_by or "admin").strip() or "admin"
    target["rejection_reason"] = (reason or "").strip()
    target["updated_at"] = now_iso
    _save_topic_review_items(items)

    return {"success": True, "candidate_id": target_id, "status": "rejected"}


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
    sync_daily_topic_candidates(now=current)
    topics = collect_daily_novel_topics(now=current)
    date_str = current.strftime("%Y-%m-%d")
    template_text = _load_template(SCENARIO_TEMPLATE_PATH)
    pending_by_id = {
        str(item.get("candidate_id")): item
        for item in list_topic_candidates(status="pending", limit=1000)
    }

    if not topics:
        return (
            f"📘 Günlük Öğrenme Raporu ({date_str})\n"
            "Yeni/farklı konu algılanmadı.\n"
            "Active learning kuyruğu incelendi, admin aksiyonu gerekmiyor."
        )

    blocks = []
    for topic in topics:
        candidate_id = _topic_to_candidate_id(topic)
        if candidate_id not in pending_by_id:
            continue
        blocks.append(
            "\n"
            f"[{len(blocks) + 1}] Aday ID: {candidate_id}\n"
            f"{_format_scenario_block(template_text, topic)}"
        )

    if not blocks:
        return (
            f"📘 Günlük Öğrenme Raporu ({date_str})\n"
            "Yeni konu sinyali var ancak hepsi daha once islenmis/onaylanmis.\n"
            "Admin aksiyonu gerekmiyor."
        )

    header = (
        f"📘 Günlük Öğrenme Raporu ({date_str})\n"
        f"Onay Bekleyen Yeni/Farklı Konu Sayısı: {len(blocks)}\n"
        "Aşağıdaki kayıtlar `Senaryo template.txt` formatında admin onayına sunulmalıdır.\n"
        "Onay endpointi (taslak üretir): POST /admin/reports/daily-learning/{aday_id}/approve\n"
    )
    return header + "\n".join(blocks)
