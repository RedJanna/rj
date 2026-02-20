"""Initial admin bootstrap helpers."""

from __future__ import annotations

import os
from typing import Callable

from app.core.auth_service import load_users


def ensure_initial_admin_user(
    initialize_admin_user_fn: Callable[[str, str], str],
) -> None:
    """
    Ensure at least one admin exists.
    Username/password are read from env for safer bootstrapping:
    - INITIAL_ADMIN_USERNAME (default: admin)
    - INITIAL_ADMIN_PASSWORD (required if no users exist)
    """
    try:
        existing_users = load_users()
        if existing_users:
            print(f"✅ {len(existing_users)} kullanıcı mevcut")
            return

        username = os.getenv("INITIAL_ADMIN_USERNAME", "admin").strip() or "admin"
        password = os.getenv("INITIAL_ADMIN_PASSWORD", "").strip()
        if not password:
            print("⚠️ İlk admin oluşturulmadı: INITIAL_ADMIN_PASSWORD ayarlanmamış")
            return

        print("🔐 İlk admin kullanıcısı oluşturuluyor...")
        totp_secret = initialize_admin_user_fn(username=username, password=password)
        if totp_secret:
            print("✅ Admin kullanıcısı oluşturuldu!")
            print(f"📱 Google Authenticator kodu: {totp_secret}")
    except Exception as e:
        print(f"⚠️ Auth servisi başlatılamadı: {e}")
