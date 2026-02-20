"""Admin statistics routes extracted from the legacy monolith."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Dict, Any

from fastapi import APIRouter


def build_admin_stats_router(
    reservations_db: Path,
    get_metrics_summary_fn: Callable[[], Dict[str, Any]],
) -> APIRouter:
    router = APIRouter(tags=["admin-stats"])

    @router.get("/admin/reservation-stats")
    async def get_reservation_stats(days: int = 7):
        try:
            conn = sqlite3.connect(str(reservations_db))
            cursor = conn.cursor()

            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            end_date = datetime.now().strftime("%Y-%m-%d")

            cursor.execute(
                """
                SELECT COUNT(*) FROM reservations
                WHERE date >= ? AND date <= ?
                """,
                (start_date, end_date),
            )
            total = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT status, COUNT(*) FROM reservations
                WHERE date >= ? AND date <= ?
                GROUP BY status
                """,
                (start_date, end_date),
            )
            status_dist = dict(cursor.fetchall())

            cursor.execute(
                """
                SELECT meal_type, COUNT(*) FROM reservations
                WHERE date >= ? AND date <= ?
                GROUP BY meal_type
                """,
                (start_date, end_date),
            )
            meal_dist = dict(cursor.fetchall())

            cursor.execute(
                """
                SELECT AVG(guest_count) FROM reservations
                WHERE date >= ? AND date <= ?
                """,
                (start_date, end_date),
            )
            avg_guests = cursor.fetchone()[0] or 0

            future_start = datetime.now().strftime("%Y-%m-%d")
            future_end = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
            cursor.execute(
                """
                SELECT date, COUNT(*) FROM reservations
                WHERE date >= ? AND date <= ? AND status NOT IN ('cancelled', 'no_show')
                GROUP BY date
                """,
                (future_start, future_end),
            )
            upcoming = dict(cursor.fetchall())
            conn.close()

            cancel_rate = round((status_dist.get("cancelled", 0) / max(total, 1)) * 100, 2)
            noshow_rate = round((status_dist.get("no_show", 0) / max(total, 1)) * 100, 2)

            return {
                "period_days": days,
                "total_reservations": total,
                "status_distribution": status_dist,
                "meal_distribution": meal_dist,
                "average_guests": round(avg_guests, 1),
                "cancel_rate_percent": cancel_rate,
                "noshow_rate_percent": noshow_rate,
                "upcoming_7_days": upcoming,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    @router.get("/admin/handoff-stats")
    async def get_handoff_stats(days: int = 7):
        metrics = get_metrics_summary_fn()
        handoff_categories = metrics.get(
            "handoff_categories",
            {
                "complaint": 0,
                "cancellation": 0,
                "live_support": 0,
                "price_negotiation": 0,
                "special_request": 0,
                "group_reservation": 0,
                "bot_confused": 0,
                "other": 0,
            },
        )
        total_handoffs = sum(handoff_categories.values())
        total_messages = metrics.get("total", 1)

        return {
            "period_days": days,
            "total_handoffs": total_handoffs,
            "total_messages": total_messages,
            "handoff_rate_percent": round((total_handoffs / max(total_messages, 1)) * 100, 2),
            "category_distribution": handoff_categories,
            "category_percentages": {
                k: round((v / max(total_handoffs, 1)) * 100, 2)
                for k, v in handoff_categories.items()
            },
            "timestamp": datetime.now().isoformat(),
        }

    return router
