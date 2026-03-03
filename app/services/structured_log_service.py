from __future__ import annotations

import gzip
import json
import logging
import os
import shutil
import threading
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any, Dict

from app.services.error_code_service import derive_error_code
from app.services.request_context_service import get_current_correlation_id


_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}
_LOGGER_LOCK = threading.Lock()
_LOGGER: logging.Logger | None = None


class _TimedSizedGzipRotatingFileHandler(TimedRotatingFileHandler):
    """Rotate daily and also when file exceeds max_bytes; gzip archives."""

    def __init__(self, filename: str, *, max_bytes: int = 0, **kwargs: Any) -> None:
        super().__init__(filename, **kwargs)
        self.max_bytes = max(0, int(max_bytes or 0))
        self.namer = self._namer
        self.rotator = self._rotator

    @staticmethod
    def _namer(default_name: str) -> str:
        return f"{default_name}.gz"

    @staticmethod
    def _rotator(source: str, dest: str) -> None:
        with open(source, "rb") as src, gzip.open(dest, "wb") as dst:
            shutil.copyfileobj(src, dst)
        os.remove(source)

    def shouldRollover(self, record: logging.LogRecord) -> int:
        if super().shouldRollover(record):
            return 1
        if self.max_bytes <= 0:
            return 0
        if self.stream is None:
            self.stream = self._open()
        try:
            message = f"{self.format(record)}\n"
            estimate = len(message.encode(self.encoding or "utf-8", errors="replace"))
            return 1 if (self.stream.tell() + estimate) >= self.max_bytes else 0
        except Exception:
            return 0


def _resolve_threshold_level() -> int:
    raw = str(os.getenv("BACKEND_LOG_LEVEL", "INFO") or "INFO").strip().upper()
    return _LEVELS.get(raw, logging.INFO)


def _get_logger() -> logging.Logger:
    global _LOGGER
    if _LOGGER is not None:
        return _LOGGER
    with _LOGGER_LOCK:
        if _LOGGER is not None:
            return _LOGGER
        logger = logging.getLogger("kassandra.structured")
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        if not logger.handlers:
            formatter = logging.Formatter("%(message)s")
            stream_handler = logging.StreamHandler()
            stream_handler.setLevel(logging.DEBUG)
            stream_handler.setFormatter(formatter)
            logger.addHandler(stream_handler)

            file_enabled = str(os.getenv("STRUCTURED_LOG_FILE_ENABLED", "1")).strip().lower() in {"1", "true", "yes", "on"}
            if file_enabled:
                log_dir = Path(os.getenv("STRUCTURED_LOG_DIR", "logs"))
                log_dir.mkdir(parents=True, exist_ok=True)
                file_name = str(os.getenv("STRUCTURED_LOG_FILE", "backend_events.log") or "backend_events.log").strip()
                backup_days = max(1, int(os.getenv("STRUCTURED_LOG_BACKUP_DAYS", "14")))
                max_mb = max(1, int(os.getenv("STRUCTURED_LOG_MAX_MB", "25")))
                file_handler = _TimedSizedGzipRotatingFileHandler(
                    str(log_dir / file_name),
                    when="midnight",
                    interval=1,
                    backupCount=backup_days,
                    encoding="utf-8",
                    utc=False,
                    max_bytes=max_mb * 1024 * 1024,
                )
                file_handler.setLevel(logging.DEBUG)
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)
        _LOGGER = logger
        return logger


def _normalize_level(level: str) -> str:
    level_name = str(level or "INFO").strip().upper()
    return level_name if level_name in _LEVELS else "INFO"


def log_event(event: str, *, level: str = "INFO", **fields: Any) -> None:
    try:
        level_name = _normalize_level(level)
        threshold = _resolve_threshold_level()
        level_value = _LEVELS[level_name]
        if level_value < threshold:
            return
        correlation_id = (
            str(fields.get("correlation_id") or "").strip()
            or str(get_current_correlation_id() or "").strip()
            or "n/a"
        )
        payload_fields = {k: v for k, v in (fields or {}).items() if v is not None and k != "correlation_id"}
        payload: Dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": level_name,
            "event": event,
            "correlation_id": correlation_id,
            **payload_fields,
        }
        if level_name in {"ERROR", "CRITICAL"} and not payload.get("error_code"):
            payload["error_code"] = derive_error_code(
                event=event,
                error_type=str(payload.get("error_type") or ""),
                message=str(payload.get("error_message") or payload.get("message") or ""),
            )
        _get_logger().log(level_value, json.dumps(payload, ensure_ascii=False, default=str))
    except Exception:
        # Logging must never affect runtime flow.
        return
