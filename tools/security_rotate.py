#!/usr/bin/env python3
"""
Security rotation utility for local auth data.

Features:
- Backup auth files before changes
- Invalidate all admin sessions
- Rotate TOTP secrets for selected users or all users
- Optional incident mode (aggressive defaults)
"""

from __future__ import annotations

import argparse
import base64
import json
import secrets
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
USERS_FILE = DATA_DIR / "admin_users.json"
SESSIONS_FILE = DATA_DIR / "admin_sessions.json"
BACKUP_ROOT = DATA_DIR / "security_backups"


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _save_json_atomic(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def _backup_files(paths: Iterable[Path], backup_dir: Path) -> List[Path]:
    backup_dir.mkdir(parents=True, exist_ok=True)
    copied: List[Path] = []
    for src in paths:
        if not src.exists():
            continue
        dst = backup_dir / src.name
        shutil.copy2(src, dst)
        copied.append(dst)
    return copied


def _generate_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("utf-8").rstrip("=")


def _parse_user_selector(selector: str, all_users: Iterable[str]) -> List[str]:
    all_usernames = list(all_users)
    if selector == "all":
        return all_usernames
    picked = [u.strip() for u in selector.split(",") if u.strip()]
    missing = [u for u in picked if u not in all_usernames]
    if missing:
        raise ValueError(f"Unknown username(s): {', '.join(missing)}")
    return picked


def _rotate_totp(
    users: Dict[str, Any],
    usernames: List[str],
    disable_2fa_on_rotate: bool,
) -> Tuple[int, List[str]]:
    rotated = 0
    changed: List[str] = []
    for username in usernames:
        user = users.get(username)
        if not isinstance(user, dict):
            continue
        user["totp_secret"] = _generate_totp_secret()
        if disable_2fa_on_rotate:
            user["totp_enabled"] = False
        rotated += 1
        changed.append(username)
    return rotated, changed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Rotate local auth/session security artifacts safely."
    )
    parser.add_argument(
        "--invalidate-sessions",
        action="store_true",
        help="Invalidate all sessions in data/admin_sessions.json.",
    )
    parser.add_argument(
        "--rotate-totp",
        metavar="USERS",
        help='Rotate TOTP secrets. Use "all" or comma-separated usernames.',
    )
    parser.add_argument(
        "--keep-2fa-enabled",
        action="store_true",
        help="Do not force totp_enabled=False after secret rotation.",
    )
    parser.add_argument(
        "--incident-mode",
        action="store_true",
        help="Equivalent to --invalidate-sessions --rotate-totp all.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing files.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    invalidate_sessions = args.invalidate_sessions
    rotate_totp_selector = args.rotate_totp

    if args.incident_mode:
        invalidate_sessions = True
        rotate_totp_selector = "all"

    if not invalidate_sessions and not rotate_totp_selector:
        parser.error(
            "No action selected. Use --invalidate-sessions and/or --rotate-totp."
        )

    if not USERS_FILE.exists():
        print(f"ERROR: missing users file: {USERS_FILE}")
        return 2

    users = _load_json(USERS_FILE)
    sessions = _load_json(SESSIONS_FILE)

    rotate_targets: List[str] = []
    if rotate_totp_selector:
        rotate_targets = _parse_user_selector(rotate_totp_selector, users.keys())

    backup_dir = BACKUP_ROOT / datetime.now().strftime("%Y%m%d_%H%M%S")

    print("Planned changes:")
    print(f"- Backup dir: {backup_dir}")
    print(f"- Invalidate sessions: {'yes' if invalidate_sessions else 'no'}")
    if rotate_targets:
        print(
            f"- Rotate TOTP: {', '.join(rotate_targets)}"
            f" (disable_2fa={not args.keep_2fa_enabled})"
        )
    else:
        print("- Rotate TOTP: no")
    if args.dry_run:
        print("- Mode: dry-run (no write)")

    if not args.yes and not args.dry_run:
        answer = input("Proceed? [y/N]: ").strip().lower()
        if answer not in {"y", "yes"}:
            print("Aborted.")
            return 1

    backup_targets = [USERS_FILE, SESSIONS_FILE]
    if args.dry_run:
        print("Dry-run complete. No files were modified.")
        return 0

    copied = _backup_files(backup_targets, backup_dir)
    print(f"Backed up {len(copied)} file(s).")

    if invalidate_sessions:
        sessions = {}
        _save_json_atomic(SESSIONS_FILE, sessions)
        print("All sessions invalidated.")

    if rotate_targets:
        rotated, changed = _rotate_totp(
            users=users,
            usernames=rotate_targets,
            disable_2fa_on_rotate=not args.keep_2fa_enabled,
        )
        _save_json_atomic(USERS_FILE, users)
        print(f"Rotated TOTP secrets for {rotated} user(s): {', '.join(changed)}")

    print("Done.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        raise SystemExit(130)
