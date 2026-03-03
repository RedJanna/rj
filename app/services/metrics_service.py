# app/services/metrics_service.py
from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.services.request_context_service import get_current_correlation_id

# ------------------------------------------------------
# SQLite storage (single table: events)
# ------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # .../app/services -> .../app -> project root
DEFAULT_DB_PATH = PROJECT_ROOT / "metrics.db"
DB_PATH = Path(os.getenv("METRICS_DB_PATH", str(DEFAULT_DB_PATH)))

_TABLE_NEW = "events"
_TABLE_OLD = "metrics_events"


@dataclass(frozen=True)
class MetricsEvent:
    id: int
    ts: str
    event: str
    category: str
    response_time: Optional[float]
    meta: Dict[str, Any]


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    # safer defaults for concurrent reads/writes
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return bool(row)


def _count_rows(conn: sqlite3.Connection, table: str) -> int:
    row = conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()
    return int(row["c"]) if row and row["c"] is not None else 0


def init_metrics_db() -> None:
    with _connect() as conn:
        # 1) Create new table
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {_TABLE_NEW} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                event TEXT NOT NULL,
                category TEXT NOT NULL,
                response_time REAL,
                meta_json TEXT NOT NULL
            )
            """
        )
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{_TABLE_NEW}_ts ON {_TABLE_NEW}(ts);")
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{_TABLE_NEW}_event ON {_TABLE_NEW}(event);")
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{_TABLE_NEW}_category ON {_TABLE_NEW}(category);")

        # 2) One-time migrate old table -> new table (if old exists, new empty)
        if _table_exists(conn, _TABLE_OLD) and _count_rows(conn, _TABLE_NEW) == 0:
            # Try best-effort copy; keep ids auto-generated to avoid conflicts.
            conn.execute(
                f"""
                INSERT INTO {_TABLE_NEW} (ts, event, category, response_time, meta_json)
                SELECT ts, event, category, response_time, meta_json
                FROM {_TABLE_OLD}
                """
            )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _since_iso(days: int) -> str:
    if days <= 0:
        return "0001-01-01T00:00:00+00:00"
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def record_metric(
    event: str,
    category: str = "general",
    response_time: Optional[float] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> int:
    init_metrics_db()

    event = (event or "").strip()
    if not event:
        event = "unknown"

    category = (category or "general").strip() or "general"

    meta_obj: Dict[str, Any] = dict(meta) if isinstance(meta, dict) else ({"_raw": meta} if meta is not None else {})
    correlation_id = get_current_correlation_id()
    if correlation_id and "correlation_id" not in meta_obj:
        meta_obj["correlation_id"] = correlation_id
    meta_json = json.dumps(meta_obj, ensure_ascii=False)

    with _connect() as conn:
        cur = conn.execute(
            f"""
            INSERT INTO {_TABLE_NEW} (ts, event, category, response_time, meta_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (_utc_now_iso(), event, category, response_time, meta_json),
        )
        return int(cur.lastrowid)


def fetch_events(
    days: int = 7,
    limit: int = 100,
    offset: int = 0,
    event_prefix: Optional[str] = None,
) -> List[MetricsEvent]:
    init_metrics_db()
    since = _since_iso(int(days))
    prefix = (event_prefix or "").strip()
    filter_by_prefix = bool(prefix)
    if filter_by_prefix:
        prefix = f"{prefix}%"

    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT id, ts, event, category, response_time, meta_json
            FROM {_TABLE_NEW}
            WHERE ts >= ?
              AND (? = 0 OR event LIKE ?)
            ORDER BY ts DESC
            LIMIT ?
            OFFSET ?
            """,
            (since, int(filter_by_prefix), prefix, int(limit), int(offset)),
        ).fetchall()

    events: List[MetricsEvent] = []
    for r in rows:
        try:
            meta = json.loads(r["meta_json"]) if r["meta_json"] else {}
        except Exception:
            meta = {"_bad_meta_json": True, "_raw": r["meta_json"]}
        events.append(
            MetricsEvent(
                id=int(r["id"]),
                ts=str(r["ts"]),
                event=str(r["event"]),
                category=str(r["category"]),
                response_time=(float(r["response_time"]) if r["response_time"] is not None else None),
                meta=meta,
            )
        )
    return events


def count_events(days: int = 7, event_prefix: Optional[str] = None) -> int:
    init_metrics_db()
    since = _since_iso(int(days))
    prefix = (event_prefix or "").strip()
    filter_by_prefix = bool(prefix)
    if filter_by_prefix:
        prefix = f"{prefix}%"
    with _connect() as conn:
        row = conn.execute(
            f"""
            SELECT COUNT(*) AS c
            FROM {_TABLE_NEW}
            WHERE ts >= ?
              AND (? = 0 OR event LIKE ?)
            """,
            (since, int(filter_by_prefix), prefix),
        ).fetchone()
    return int(row["c"]) if row and row["c"] is not None else 0


def list_events(
    days: int = 7,
    limit: int = 50,
    offset: int = 0,
    event_prefix: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Canonical API for routes:
    returns (items, total)
    """
    evs = fetch_events(days=days, limit=limit, offset=offset, event_prefix=event_prefix)
    total = count_events(days=days, event_prefix=event_prefix)
    items = [
        {
            "id": e.id,
            "ts": e.ts,
            "event": e.event,
            "category": e.category,
            "response_time": e.response_time,
            "meta": e.meta,
        }
        for e in evs
    ]
    return items, total


def metrics_summary(days: int = 7) -> Dict[str, Any]:
    """
    Lightweight summary (generic).
    """
    init_metrics_db()
    since = _since_iso(int(days))

    with _connect() as conn:
        row = conn.execute(
            f"""
            SELECT
                COUNT(*) AS total,
                AVG(response_time) AS avg_rt
            FROM {_TABLE_NEW}
            WHERE ts >= ?
            """,
            (since,),
        ).fetchone()

        top_rows = conn.execute(
            f"""
            SELECT event, COUNT(*) AS c
            FROM {_TABLE_NEW}
            WHERE ts >= ?
            GROUP BY event
            ORDER BY c DESC
            LIMIT 10
            """,
            (since,),
        ).fetchall()

    return {
        "days": int(days),
        "total": int(row["total"] if row and row["total"] is not None else 0),
        "avg_response_time": float(row["avg_rt"]) if row and row["avg_rt"] is not None else None,
        "top_events": [{"event": str(r["event"]), "count": int(r["c"])} for r in top_rows],
        "db_path": str(DB_PATH),
        "table": _TABLE_NEW,
    }


def reset_metrics(event_prefix: Optional[str] = None) -> int:
    """
    Delete metrics rows and return affected row count.
    If event_prefix is provided, only matching events are deleted.
    """
    init_metrics_db()
    prefix = (event_prefix or "").strip()
    filter_by_prefix = bool(prefix)
    if filter_by_prefix:
        prefix = f"{prefix}%"

    with _connect() as conn:
        cur = conn.execute(
            f"""
            DELETE FROM {_TABLE_NEW}
            WHERE (? = 0 OR event LIKE ?)
            """,
            (int(filter_by_prefix), prefix),
        )
        deleted = int(cur.rowcount or 0)
    return deleted


# ------------------------------------------------------
# Backward-compatible aliases (so old imports don't crash)
# ------------------------------------------------------

def save_metrics(*args: Any, **kwargs: Any) -> None:
    # Legacy no-op (old JSON metrics approach)
    return None


def create_empty_metrics() -> Dict[str, Any]:
    # Legacy helper (some older code may import it)
    return {}


def load_metrics(days: int = 7, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Legacy name that returns a list of dicts (raw list) for compatibility.
    """
    items, _total = list_events(days=days, limit=limit, offset=offset)
    return items


def get_metrics_summary(days: int = 1) -> Dict[str, Any]:
    """
    Legacy daily-report shape used in kassandra_openai_bot.py.
    It is computed from recorded events.
    """
    items, total = list_events(days=days, limit=10_000, offset=0)  # daily report can be larger
    if total <= 0:
        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total_messages": 0,
            "success_rate": 0,
            "local_responses": 0,
            "openai_responses": 0,
            "local_percent": 0,
            "openai_percent": 0,
            "handoff_count": 0,
            "suspicious_count": 0,
            "error_count": 0,
            "avg_response_time": None,
        }

    def _count(event_name: str) -> int:
        return sum(1 for it in items if str(it.get("event")) == event_name)

    local_cnt = _count("local")
    openai_cnt = _count("openai")
    handoff_cnt = _count("handoff")
    suspicious_cnt = _count("suspicious")
    error_cnt = _count("error")

    success_cnt = local_cnt + openai_cnt
    success_rate = int(round((success_cnt / total) * 100))

    local_percent = int(round((local_cnt / total) * 100))
    openai_percent = int(round((openai_cnt / total) * 100))

    # average response_time over non-null
    rts = [it.get("response_time") for it in items if isinstance(it.get("response_time"), (int, float))]
    avg_rt = (sum(float(x) for x in rts) / len(rts)) if rts else None
    avg_rt = round(avg_rt, 3) if avg_rt is not None else None

    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "total_messages": int(total),
        "success_rate": int(success_rate),
        "local_responses": int(local_cnt),
        "openai_responses": int(openai_cnt),
        "local_percent": int(local_percent),
        "openai_percent": int(openai_percent),
        "handoff_count": int(handoff_cnt),
        "suspicious_count": int(suspicious_cnt),
        "error_count": int(error_cnt),
        "avg_response_time": avg_rt,
    }
