"""Operational admin routes extracted from legacy monolith."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict

from fastapi import APIRouter
from fastapi import Request
from app.core.settings_service import (
    append_settings_audit_entry,
    DEFAULT_CURRENCY_POLICY,
    DEFAULT_LANGUAGE_POLICY,
    get_settings_audit,
    normalize_language_policy,
    get_valid_room_keys,
)
from app.services.handoff_packet_service import validate_handoff_packet
from app.services.metrics_service import list_events
from app.services.daily_learning_report_service import (
    build_daily_learning_report,
    finalize_topic_candidate_approval,
    ingest_new_scenario_drafts,
    list_topic_candidates,
    reject_topic_candidate,
    request_topic_candidate_draft,
)

_backend_proc_lock = threading.Lock()
_backend_proc: subprocess.Popen | None = None
_backend_proc_started_at: str = ""

OPS_SKILL_CASES: dict[str, dict[str, Any]] = {
    "price_handoff_guard": {
        "skill": "elektra-endpoint-ops",
        "title": "Price handoff guard",
        "kind": "pytest",
        "args": [
            "-m",
            "pytest",
            "-q",
            "tests/unit/test_chat_pipeline_routes.py",
            "-k",
            "price_intent_without_elektra_result or low_confidence_known_intent",
        ],
        "timeout_sec": 180,
    },
    "booking_vs_price_guard": {
        "skill": "intent-ops-triage",
        "title": "Booking vs price guard",
        "kind": "pytest",
        # Keep this guard aligned with current expected assertions in selected tests.
        "env_overrides": {"NEW_PIPELINE_ENABLED": "0"},
        "args": [
            "-m",
            "pytest",
            "-q",
            "tests/unit/test_chat_pipeline_routes.py",
            "-k",
            "explicit_booking or booking_flow_chain or price_flow_chain",
        ],
        "timeout_sec": 180,
    },
    "handoff_quality_guard": {
        "skill": "live-handoff-quality-check",
        "title": "Handoff quality guard",
        "kind": "pytest",
        "args": [
            "-m",
            "pytest",
            "-q",
            "tests/unit/test_chat_pipeline_routes.py",
            "tests/unit/test_chat_precheck_handler.py",
            "-k",
            "handoff or unknown_guard or policy_guard",
        ],
        "timeout_sec": 180,
    },
    "intent_release_guard": {
        "skill": "intent-regression-guard",
        "title": "Intent release guard",
        "kind": "pytest",
        # Keep guard deterministic across environments for current assertions.
        "env_overrides": {"NEW_PIPELINE_ENABLED": "0"},
        "args": [
            "-m",
            "pytest",
            "-q",
            "tests/unit/test_intent_router_service.py",
            "tests/unit/test_intent_policy_service.py",
            "tests/unit/test_chat_pipeline_routes.py",
            "-k",
            "price or booking or unknown_guard",
        ],
        "timeout_sec": 240,
    },
}
OPS_SKILL_RUN_ORDER: list[str] = [
    "price_handoff_guard",
    "booking_vs_price_guard",
    "handoff_quality_guard",
    "intent_release_guard",
]
_ops_skill_last_run: dict[str, Any] = {}


def _parse_iso_ts(value: str) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        # Normalize trailing Z for fromisoformat compatibility.
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        return datetime.fromisoformat(raw)
    except Exception:
        return None


def _resolve_deploy_after_ts() -> str:
    for key in ("APP_DEPLOYED_AT", "DEPLOYED_AT", "RELEASE_TS"):
        v = (os.getenv(key, "") or "").strip()
        if v:
            return v
    return ""


def _repo_root_from_this_file() -> Path:
    return Path(__file__).resolve().parents[2]


def _run_ops_case_command(
    args: list[str],
    timeout_sec: int,
    env_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    repo_root = _repo_root_from_this_file()
    cmd = [sys.executable, *args]
    env = dict(os.environ)
    cur_py_path = str(env.get("PYTHONPATH") or "").strip()
    env["PYTHONPATH"] = "." if not cur_py_path else f".{os.pathsep}{cur_py_path}"
    if env_overrides:
        for k, v in env_overrides.items():
            env[str(k)] = str(v)
    started = datetime.now().isoformat()
    try:
        cp = subprocess.run(
            cmd,
            cwd=str(repo_root),
            env=env,
            capture_output=True,
            text=True,
            timeout=max(30, int(timeout_sec)),
            check=False,
        )
        stdout_tail = (cp.stdout or "")[-6000:]
        stderr_tail = (cp.stderr or "")[-3000:]
        return {
            "success": cp.returncode == 0,
            "return_code": int(cp.returncode),
            "command": cmd,
            "started_at": started,
            "finished_at": datetime.now().isoformat(),
            "stdout_tail": stdout_tail,
            "stderr_tail": stderr_tail,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "success": False,
            "return_code": None,
            "command": cmd,
            "started_at": started,
            "finished_at": datetime.now().isoformat(),
            "stdout_tail": str((exc.stdout or "")[-6000:]),
            "stderr_tail": str((exc.stderr or "")[-3000:]),
            "error": f"timeout ({timeout_sec}s)",
        }


def _is_backend_proc_alive() -> bool:
    global _backend_proc
    with _backend_proc_lock:
        if _backend_proc is None:
            return False
        return _backend_proc.poll() is None


def _backend_status_payload() -> Dict[str, Any]:
    with _backend_proc_lock:
        proc = _backend_proc
        if proc is None:
            return {"running": False, "pid": None, "started_at": _backend_proc_started_at}
        running = proc.poll() is None
        return {"running": running, "pid": proc.pid, "started_at": _backend_proc_started_at}


def build_admin_ops_router(
    load_settings_fn: Callable[[], Dict[str, Any]],
    save_settings_fn: Callable[[Dict[str, Any]], Any],
    is_automation_enabled_fn: Callable[[], bool],
    is_followup_enabled_fn: Callable[[], bool],
    notify_critical_action_fn: Callable[[str, str], Awaitable[Any]],
    conversations_dir: Path,
    load_conversation_fn: Callable[[str], Dict[str, Any]],
    send_whatsapp_message_fn: Callable[[str, str], Awaitable[Any]],
    admin_phone: str,
    whatsapp_phone_id: str,
    whatsapp_token: str,
) -> APIRouter:
    router = APIRouter(tags=["admin-ops"])

    def _parse_room_keys_csv(raw: str) -> list[str]:
        return [x.strip() for x in (raw or "").split(",") if x.strip()]

    def _validate_room_keys(keys: list[str]) -> tuple[list[str], list[str]]:
        valid_map = {k.lower(): k for k in get_valid_room_keys()}
        normalized: list[str] = []
        invalid: list[str] = []
        for key in keys:
            raw = (key or "").strip().lower()
            if not raw:
                continue
            if raw not in valid_map:
                invalid.append(key)
                continue
            v = valid_map[raw]
            if v not in normalized:
                normalized.append(v)
        return normalized, invalid

    @router.get("/admin/ops/health")
    async def ops_health():
        return {"status": "ok", "automation": is_automation_enabled_fn()}

    @router.get("/admin/ops/skills/cases")
    async def list_ops_skill_cases():
        items = []
        for case_id, meta in OPS_SKILL_CASES.items():
            items.append(
                {
                    "id": case_id,
                    "skill": meta.get("skill"),
                    "title": meta.get("title"),
                    "kind": meta.get("kind"),
                    "timeout_sec": int(meta.get("timeout_sec") or 0),
                }
            )
        return {"success": True, "count": len(items), "items": items}

    @router.get("/admin/ops/skills/readiness")
    async def get_ops_readiness_snapshot():
        tracked_env = [
            "OPENAI_API_KEY",
            "WHATSAPP_TOKEN",
            "WHATSAPP_PHONE_ID",
            "Elektra_Booking",
            "ELEKTRA_API_BASE_URL",
            "ELEKTRA_HOTEL_ID",
        ]
        env_status = {k: ("SET" if str(os.getenv(k) or "").strip() else "NOT_SET") for k in tracked_env}
        backend_status = _backend_status_payload()
        # NOTE:
        # backend_status here reflects only the process managed by /admin/backend/start.
        # If the API is serving this response, the runtime itself is already alive.
        backend_status["tracking_scope"] = "managed_by_admin_panel_only"
        backend_status["api_reachable"] = True
        settings = load_settings_fn()
        return {
            "success": True,
            "backend": backend_status,
            "env_status": env_status,
            "automation_enabled": is_automation_enabled_fn(),
            "followup_enabled": is_followup_enabled_fn(),
            "operational_rules_enabled": settings.get("operational_rules_enabled", True),
            "at": datetime.now().isoformat(),
        }

    @router.get("/admin/ops/skills/last-run")
    async def get_last_ops_skill_run():
        if not _ops_skill_last_run:
            return {"success": True, "exists": False}
        return {"success": True, "exists": True, "last_run": _ops_skill_last_run}

    @router.post("/admin/ops/skills/run/{case_id}")
    async def run_ops_skill_case(case_id: str):
        key = str(case_id or "").strip().lower()
        meta = OPS_SKILL_CASES.get(key)
        if not meta:
            return {"success": False, "error": f"Unknown case_id: {case_id}"}
        if str(meta.get("kind")) != "pytest":
            return {"success": False, "error": f"Unsupported case kind: {meta.get('kind')}"}
        result = _run_ops_case_command(
            args=list(meta.get("args") or []),
            timeout_sec=int(meta.get("timeout_sec") or 180),
            env_overrides=dict(meta.get("env_overrides") or {}),
        )
        return {
            "success": bool(result.get("success")),
            "case_id": key,
            "skill": meta.get("skill"),
            "title": meta.get("title"),
            **result,
        }

    @router.post("/admin/ops/skills/run-all")
    async def run_all_ops_skill_cases():
        global _ops_skill_last_run
        started_at = datetime.now().isoformat()
        cases_in_order: list[str] = [cid for cid in OPS_SKILL_RUN_ORDER if cid in OPS_SKILL_CASES]
        # Fallback for newly added cases not listed in explicit order yet.
        for cid in OPS_SKILL_CASES.keys():
            if cid not in cases_in_order:
                cases_in_order.append(cid)

        results: list[dict[str, Any]] = []
        passed = 0
        failed = 0

        for case_id in cases_in_order:
            meta = OPS_SKILL_CASES.get(case_id) or {}
            if str(meta.get("kind")) != "pytest":
                failed += 1
                results.append(
                    {
                        "success": False,
                        "case_id": case_id,
                        "skill": meta.get("skill"),
                        "title": meta.get("title"),
                        "error": f"Unsupported case kind: {meta.get('kind')}",
                    }
                )
                continue

            run_result = _run_ops_case_command(
                args=list(meta.get("args") or []),
                timeout_sec=int(meta.get("timeout_sec") or 180),
                env_overrides=dict(meta.get("env_overrides") or {}),
            )
            case_success = bool(run_result.get("success"))
            if case_success:
                passed += 1
            else:
                failed += 1

            results.append(
                {
                    "success": case_success,
                    "case_id": case_id,
                    "skill": meta.get("skill"),
                    "title": meta.get("title"),
                    **run_result,
                }
            )

        total = len(results)
        payload = {
            "success": failed == 0 and total > 0,
            "title": "Ops Skill Release Readiness",
            "started_at": started_at,
            "finished_at": datetime.now().isoformat(),
            "summary": {
                "total": total,
                "passed": passed,
                "failed": failed,
            },
            "results": results,
        }
        _ops_skill_last_run = payload
        return payload

    @router.get("/settings")
    async def get_settings():
        return load_settings_fn()

    @router.post("/settings")
    async def update_settings(
        request: Request,
        automation_enabled: bool = None,
        followup_enabled: bool = None,
        operational_rules_enabled: bool = None,
        followup_minutes: int = None,
        session_duration_hours: int = None,
        quiet_auto_room_keys: str = None,
        quiet_handoff_room_keys: str = None,
        standard_room_keys: str = None,
        currency_enabled_json: str = None,
        language_enabled_json: str = None,
    ):
        settings = load_settings_fn()
        old_settings = dict(settings)
        user = getattr(request.state, "user", None)
        updated_by = getattr(user, "username", None) or "token_admin"

        if automation_enabled is not None:
            settings["automation_enabled"] = automation_enabled
        if followup_enabled is not None:
            settings["followup_enabled"] = followup_enabled
        if operational_rules_enabled is not None:
            settings["operational_rules_enabled"] = operational_rules_enabled
        if followup_minutes is not None:
            settings["followup_minutes"] = followup_minutes
        if session_duration_hours is not None:
            if session_duration_hours < 1 or session_duration_hours > 720:
                return {
                    "success": False,
                    "error": "Oturum süresi 1 ile 720 saat arasında olmalıdır.",
                }
            settings["session_duration_hours"] = session_duration_hours
        if quiet_auto_room_keys is not None:
            parsed = _parse_room_keys_csv(quiet_auto_room_keys)
            normalized, invalid = _validate_room_keys(parsed)
            if invalid:
                return {
                    "success": False,
                    "error": f"Geçersiz oda anahtarı: {', '.join(invalid)}",
                    "valid_room_keys": get_valid_room_keys(),
                }
            settings["quiet_auto_room_keys"] = normalized
        if quiet_handoff_room_keys is not None:
            parsed = _parse_room_keys_csv(quiet_handoff_room_keys)
            normalized, invalid = _validate_room_keys(parsed)
            if invalid:
                return {
                    "success": False,
                    "error": f"Geçersiz oda anahtarı: {', '.join(invalid)}",
                    "valid_room_keys": get_valid_room_keys(),
                }
            settings["quiet_handoff_room_keys"] = normalized
        if standard_room_keys is not None:
            parsed = _parse_room_keys_csv(standard_room_keys)
            normalized, invalid = _validate_room_keys(parsed)
            if invalid:
                return {
                    "success": False,
                    "error": f"Geçersiz oda anahtarı: {', '.join(invalid)}",
                    "valid_room_keys": get_valid_room_keys(),
                }
            settings["standard_room_keys"] = normalized
        if currency_enabled_json is not None:
            try:
                parsed = json.loads(currency_enabled_json)
            except Exception:
                return {
                    "success": False,
                    "error": "currency_enabled_json gecersiz JSON formatinda.",
                }
            if not isinstance(parsed, dict):
                return {
                    "success": False,
                    "error": "currency_enabled_json bir obje olmalidir.",
                }
            merged = dict(DEFAULT_CURRENCY_POLICY)
            for code in merged.keys():
                if code in parsed:
                    merged[code] = bool(parsed.get(code))
            settings["currency_enabled"] = merged
        if language_enabled_json is not None:
            try:
                parsed = json.loads(language_enabled_json)
            except Exception:
                return {
                    "success": False,
                    "error": "language_enabled_json gecersiz JSON formatinda.",
                }
            if not isinstance(parsed, dict):
                return {
                    "success": False,
                    "error": "language_enabled_json bir obje olmalidir.",
                }
            settings["language_enabled"] = normalize_language_policy(parsed)

        if "quiet_auto_room_keys" in settings and "quiet_handoff_room_keys" in settings:
            overlap = sorted(set(settings.get("quiet_auto_room_keys", [])) & set(settings.get("quiet_handoff_room_keys", [])))
            if overlap:
                return {
                    "success": False,
                    "error": f"Aynı oda hem otomatik hem handoff olamaz: {', '.join(overlap)}",
                    "valid_room_keys": get_valid_room_keys(),
                }

        save_settings_fn(settings)

        if old_settings.get("quiet_auto_room_keys") != settings.get("quiet_auto_room_keys"):
            append_settings_audit_entry(
                key="quiet_auto_room_keys",
                old_value=old_settings.get("quiet_auto_room_keys"),
                new_value=settings.get("quiet_auto_room_keys"),
                updated_by=updated_by,
            )
        if old_settings.get("quiet_handoff_room_keys") != settings.get("quiet_handoff_room_keys"):
            append_settings_audit_entry(
                key="quiet_handoff_room_keys",
                old_value=old_settings.get("quiet_handoff_room_keys"),
                new_value=settings.get("quiet_handoff_room_keys"),
                updated_by=updated_by,
            )
        if old_settings.get("standard_room_keys") != settings.get("standard_room_keys"):
            append_settings_audit_entry(
                key="standard_room_keys",
                old_value=old_settings.get("standard_room_keys"),
                new_value=settings.get("standard_room_keys"),
                updated_by=updated_by,
            )
        if old_settings.get("operational_rules_enabled") != settings.get("operational_rules_enabled"):
            append_settings_audit_entry(
                key="operational_rules_enabled",
                old_value=old_settings.get("operational_rules_enabled"),
                new_value=settings.get("operational_rules_enabled"),
                updated_by=updated_by,
            )
        if old_settings.get("session_duration_hours") != settings.get("session_duration_hours"):
            append_settings_audit_entry(
                key="session_duration_hours",
                old_value=old_settings.get("session_duration_hours"),
                new_value=settings.get("session_duration_hours"),
                updated_by=updated_by,
            )
        if old_settings.get("currency_enabled") != settings.get("currency_enabled"):
            append_settings_audit_entry(
                key="currency_enabled",
                old_value=old_settings.get("currency_enabled"),
                new_value=settings.get("currency_enabled"),
                updated_by=updated_by,
            )
        if old_settings.get("language_enabled") != settings.get("language_enabled"):
            append_settings_audit_entry(
                key="language_enabled",
                old_value=old_settings.get("language_enabled", dict(DEFAULT_LANGUAGE_POLICY)),
                new_value=settings.get("language_enabled", dict(DEFAULT_LANGUAGE_POLICY)),
                updated_by=updated_by,
            )

        return settings

    @router.get("/settings/audit")
    async def get_settings_audit_api(limit: int = 100):
        return {"items": get_settings_audit(limit=limit)}

    @router.post("/automation/start")
    async def start_automation():
        settings = load_settings_fn()
        settings["automation_enabled"] = True
        save_settings_fn(settings)
        return {"status": "started", "automation_enabled": True}

    @router.post("/automation/stop")
    async def stop_automation():
        settings = load_settings_fn()
        settings["automation_enabled"] = False
        save_settings_fn(settings)
        await notify_critical_action_fn(
            "OTOMASYON KAPATILDI",
            "Bot artık müşterilere cevap vermiyor!",
        )
        return {"status": "stopped", "automation_enabled": False}

    @router.get("/automation/status")
    async def automation_status():
        settings = load_settings_fn()
        return {
            "automation_enabled": is_automation_enabled_fn(),
            "followup_enabled": is_followup_enabled_fn(),
            "operational_rules_enabled": settings.get("operational_rules_enabled", True),
        }

    @router.get("/admin/backend/status")
    async def backend_process_status():
        status = _backend_status_payload()
        return {"success": True, **status}

    @router.post("/admin/backend/start")
    async def start_backend_bat():
        global _backend_proc, _backend_proc_started_at
        if os.name != "nt":
            return {
                "success": False,
                "message": "Bu endpoint sadece Windows ortaminda desteklenir.",
            }

        with _backend_proc_lock:
            if _backend_proc is not None and _backend_proc.poll() is None:
                return {
                    "success": True,
                    "message": "Backend zaten calisiyor.",
                    "running": True,
                    "pid": _backend_proc.pid,
                    "started_at": _backend_proc_started_at,
                }

            repo_root = _repo_root_from_this_file()
            bat_path = repo_root / "start_backend.bat"
            if not bat_path.exists():
                return {
                    "success": False,
                    "message": f"Dosya bulunamadi: {bat_path}",
                }

            proc = subprocess.Popen(
                ["cmd.exe", "/c", str(bat_path)],
                cwd=str(repo_root),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
            _backend_proc = proc
            _backend_proc_started_at = datetime.now().isoformat()
            return {
                "success": True,
                "message": "start_backend.bat baslatildi.",
                "running": True,
                "pid": proc.pid,
                "started_at": _backend_proc_started_at,
            }

    @router.post("/admin/backend/stop")
    async def stop_backend_bat():
        global _backend_proc
        no_proc = False
        with _backend_proc_lock:
            proc = _backend_proc
            if proc is None or proc.poll() is not None:
                _backend_proc = None
                no_proc = True
                pid = None
            else:
                pid = proc.pid

        if no_proc:
            status = _backend_status_payload()
            return {
                "success": True,
                "message": "Calisan backend process bulunamadi.",
                **status,
            }

        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                proc.terminate()
                proc.wait(timeout=8)
        except Exception:
            pass
        finally:
            with _backend_proc_lock:
                if _backend_proc is not None and _backend_proc.poll() is not None:
                    _backend_proc = None

        status = _backend_status_payload()
        return {
            "success": True,
            "message": "Backend durdurma komutu gonderildi.",
            **status,
        }

    @router.get("/conversations")
    async def list_conversations():
        files = list(conversations_dir.glob("*.json"))
        convs = []
        for f in files:
            try:
                with open(f, "r", encoding="utf-8") as file:
                    data = json.load(file)
                    convs.append(
                        {
                            "phone": data.get("phone"),
                            "messages": len(data.get("messages", [])),
                            "updated": data.get("updated_at"),
                        }
                    )
            except Exception:
                pass
        return {"conversations": convs}

    @router.get("/conversations/{phone}")
    async def get_conversation_api(phone: str):
        return load_conversation_fn(phone)

    @router.get("/test/admin-notification")
    async def test_admin_notification():
        test_message = (
            "TEST MESAJI - SISTEM CALISIYOR!\n\n"
            "Bu mesaji goruyorsan bildirim sistemi duzgun calisiyor.\n\n"
            f"Zaman: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Admin: {admin_phone}\n"
            f"WHATSAPP_PHONE_ID: {whatsapp_phone_id[:5]}... (gizli)\n\n"
            "Kassandra Bot Bildirim Sistemi"
        )
        success = await send_whatsapp_message_fn(admin_phone, test_message)
        return {
            "status": "sent" if success else "failed",
            "admin_phone": admin_phone,
            "whatsapp_phone_id_set": bool(whatsapp_phone_id),
            "whatsapp_token_set": bool(whatsapp_token),
            "message": "Telefonunu kontrol et!" if success else "Gonderim basarisiz - ayarlari kontrol et",
        }

    @router.get("/admin/handoff/packets")
    async def get_handoff_packets(
        days: int = 7,
        limit: int = 50,
        only_invalid: bool = False,
        after_deploy: bool = False,
        after_ts: str = "",
    ):
        items, total = list_events(days=days, limit=limit, offset=0, event_prefix="handoff.packet")
        rows = []
        deploy_after_ts = _resolve_deploy_after_ts()
        effective_after_ts = (after_ts or "").strip() or (deploy_after_ts if after_deploy else "")
        effective_after_dt = _parse_iso_ts(effective_after_ts)
        required_fields = [
            "packet_id",
            "source",
            "category",
            "priority",
            "customer_phone",
            "customer_message",
            "detected_intent",
            "trigger_type",
            "sla_target_minutes",
            "within_business_hours",
            "language_lock",
        ]
        for it in items:
            event_name = str(it.get("event") or "").strip()
            item_ts = str(it.get("ts") or "").strip()
            if effective_after_dt is not None:
                item_dt = _parse_iso_ts(item_ts)
                if item_dt is None or item_dt < effective_after_dt:
                    continue
            meta = it.get("meta") if isinstance(it.get("meta"), dict) else {}
            packet = meta.get("packet") if isinstance(meta.get("packet"), dict) else None
            if packet:
                valid, missing = validate_handoff_packet(packet)
                row = {
                    "ts": it.get("ts"),
                    "event": event_name,
                    "category": it.get("category"),
                    "valid": valid,
                    "missing": missing,
                    "packet": packet,
                }
            else:
                # reject event or unknown shape
                missing = meta.get("missing") if isinstance(meta.get("missing"), list) else required_fields
                row = {
                    "ts": it.get("ts"),
                    "event": event_name,
                    "category": it.get("category"),
                    "valid": False,
                    "missing": missing,
                    "packet": {},
                    "debug": {
                        "source": meta.get("source"),
                        "detected_intent": meta.get("detected_intent"),
                        "confidence": meta.get("confidence"),
                        "correlation_id": meta.get("correlation_id"),
                        "language_lock": meta.get("language_lock"),
                    },
                }
            if only_invalid and row["valid"]:
                continue
            rows.append(row)

        return {
            "items": rows,
            "total": total,
            "days": int(days),
            "limit": int(limit),
            "required_fields": required_fields,
            "only_invalid": bool(only_invalid),
            "after_deploy": bool(after_deploy),
            "effective_after_ts": effective_after_ts,
            "deploy_after_ts": deploy_after_ts,
        }

    @router.post("/admin/reports/daily-learning/run")
    async def run_daily_learning_report_now():
        report_text = build_daily_learning_report()
        send_limit = 3800
        success = await send_whatsapp_message_fn(admin_phone, report_text[:send_limit])
        return {
            "success": bool(success),
            "sent_to": admin_phone,
            "report_preview": report_text[:1200],
            "truncated": len(report_text) > send_limit,
        }

    @router.get("/admin/reports/daily-learning/pending")
    async def list_daily_learning_candidates(status: str = "pending", limit: int = 50):
        normalized = (status or "").strip().lower()
        if normalized in {"", "all", "*"}:
            normalized = None
        items = list_topic_candidates(status=normalized, limit=limit)
        return {
            "success": True,
            "status_filter": normalized or "all",
            "count": len(items),
            "items": items,
        }

    @router.post("/admin/reports/daily-learning/{candidate_id}/approve")
    async def approve_daily_learning_candidate(candidate_id: str, request: Request, note: str = ""):
        user = getattr(request.state, "user", None)
        requested_by = getattr(user, "username", None) or "token_admin"
        result = request_topic_candidate_draft(candidate_id, requested_by=requested_by, note=note)
        return result

    @router.post("/admin/reports/daily-learning/{candidate_id}/redraft")
    async def redraft_daily_learning_candidate(candidate_id: str, request: Request, note: str = ""):
        user = getattr(request.state, "user", None)
        requested_by = getattr(user, "username", None) or "token_admin"
        result = request_topic_candidate_draft(
            candidate_id,
            requested_by=requested_by,
            note=note,
            force_regenerate=True,
        )
        return result

    @router.post("/admin/reports/daily-learning/{candidate_id}/final-approve")
    async def final_approve_daily_learning_candidate(candidate_id: str, request: Request, note: str = ""):
        user = getattr(request.state, "user", None)
        approved_by = getattr(user, "username", None) or "token_admin"
        result = finalize_topic_candidate_approval(candidate_id, approved_by=approved_by, note=note)
        return result

    @router.post("/admin/reports/daily-learning/ingest-drafts")
    async def ingest_daily_learning_drafts(request: Request, note: str = ""):
        user = getattr(request.state, "user", None)
        approved_by = getattr(user, "username", None) or "token_admin"
        result = ingest_new_scenario_drafts(approved_by=approved_by, note=note)
        return result

    @router.post("/admin/reports/daily-learning/{candidate_id}/reject")
    async def reject_daily_learning_candidate(candidate_id: str, request: Request, reason: str = ""):
        user = getattr(request.state, "user", None)
        rejected_by = getattr(user, "username", None) or "token_admin"
        result = reject_topic_candidate(candidate_id, rejected_by=rejected_by, reason=reason)
        return result

    return router
