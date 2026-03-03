from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_data_file(default_name: str, *, env_var: str) -> Path:
    raw = (os.getenv(env_var) or "").strip()
    if raw:
        return Path(raw).expanduser()
    return get_project_root() / "data" / default_name


_THREAD_LOCKS: Dict[str, threading.RLock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


def _get_thread_lock(path: Path) -> threading.RLock:
    key = str(path.resolve())
    with _THREAD_LOCKS_GUARD:
        lock = _THREAD_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _THREAD_LOCKS[key] = lock
        return lock


@contextmanager
def _advisory_file_lock(lock_path: Path):
    """
    Best-effort process-level lock.
    Falls back to thread lock only if OS lock APIs are not available.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+b") as lock_file:
        locked = False
        try:
            if os.name == "nt":
                import msvcrt  # type: ignore

                lock_file.seek(0)
                if lock_file.tell() == 0:
                    lock_file.write(b"0")
                    lock_file.flush()
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
                locked = True
            else:
                import fcntl  # type: ignore

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                locked = True
        except Exception:
            locked = False

        try:
            yield
        finally:
            if not locked:
                return
            try:
                if os.name == "nt":
                    import msvcrt  # type: ignore

                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl  # type: ignore

                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass


class JsonStateRepository:
    def __init__(self, path: Path):
        self.path = path
        self._thread_lock = _get_thread_lock(path)
        self._lock_path = path.with_suffix(path.suffix + ".lock")

    def load_json(self, *, default: Any) -> Any:
        if not self.path.exists():
            return default
        try:
            with self.path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default

    def save_json(self, data: Any) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._thread_lock:
            with _advisory_file_lock(self._lock_path):
                with tempfile.NamedTemporaryFile(
                    "w",
                    encoding="utf-8",
                    dir=str(self.path.parent),
                    delete=False,
                ) as tf:
                    json.dump(data, tf, indent=2, ensure_ascii=False)
                    tf.flush()
                    os.fsync(tf.fileno())
                    tmp_name = tf.name
                retries = 6
                for attempt in range(retries):
                    try:
                        os.replace(tmp_name, self.path)
                        break
                    except PermissionError:
                        # Windows'ta AV/indexer veya kısa süreli dosya lock'larında
                        # atomik replace ilk denemede başarısız olabiliyor.
                        if attempt >= retries - 1:
                            try:
                                with open(tmp_name, "r", encoding="utf-8") as src:
                                    payload = src.read()
                                with open(self.path, "w", encoding="utf-8") as dst:
                                    dst.write(payload)
                                break
                            except Exception:
                                raise
                        time.sleep(0.02 * (attempt + 1))
                try:
                    if os.path.exists(tmp_name):
                        os.remove(tmp_name)
                except Exception:
                    pass

    def load_dict(self) -> Dict[str, Any]:
        data = self.load_json(default={})
        return data if isinstance(data, dict) else {}

    def save_dict(self, data: Dict[str, Any]) -> None:
        payload = data if isinstance(data, dict) else {}
        self.save_json(payload)
