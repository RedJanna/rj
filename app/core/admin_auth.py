# Dosya Adı: app/core/admin_auth.py
"""
Admin Auth - Session Bazlı Kimlik Doğrulama
============================================
Admin paneli için authentication middleware.

Kural:
1. Session cookie varsa ve geçerliyse → İzin ver
2. X-Admin-Token header'ı varsa ve doğruysa → İzin ver (API erişimi için)
3. Aksi halde → 401 Unauthorized
"""

import os
import hmac
import time
import threading
from fastapi import HTTPException, Request
from typing import Optional
from app.services.structured_log_service import log_event

# Session yönetimi için import
try:
    from app.core.auth_service import get_session, get_user
except ImportError:
    # Henüz auth_service yüklenmemişse fallback
    get_session = None
    get_user = None

COOKIE_NAME = "kassandra_session"

# ======================================================
# Merkezi Rol/İzin Modeli
# ======================================================

ROLE_PERMISSIONS = {
    "operator": {
        "admin.panel.read",
    },
    "admin": {
        "admin.panel.read",
        "admin.users.manage",
        "access_control.manage",
        "system.settings.manage",
        "system.monitoring.manage",
    },
}


def user_has_permission(user, permission: str) -> bool:
    if user is None:
        return False
    role = getattr(user, "role", "") or ""
    granted = ROLE_PERMISSIONS.get(role, set())
    return permission in granted


def require_permission(permission: str):
    """Belirli izin gerektiren dependency üretir."""
    def _dependency(request: Request):
        require_admin(request)

        # ADMIN_TOKEN ile gelen API çağrılarını geriye dönük uyumluluk için yetkili kabul et.
        if getattr(request.state, "auth_via_token", False):
            user = getattr(request.state, "user", None)
            if user is None:
                class _TokenUser:
                    username = "token_admin"
                    role = "admin"
                    display_name = "Admin Token"
                    totp_enabled = False

                user = _TokenUser()
            return user

        user = getattr(request.state, "user", None)
        if not user_has_permission(user, permission):
            correlation_id = getattr(request.state, "correlation_id", None)
            client_ip = getattr(getattr(request, "client", None), "host", None) or ""
            log_event(
                "security.permission.denied",
                level="WARNING",
                correlation_id=correlation_id,
                path=str(getattr(getattr(request, "url", None), "path", "")),
                method=getattr(request, "method", ""),
                ip=client_ip,
                username=getattr(user, "username", None),
                role=getattr(user, "role", None),
                permission=permission,
                auth_via_token=bool(getattr(request.state, "auth_via_token", False)),
            )
            try:
                from app.services.metrics_service import record_metric

                record_metric(
                    event="security.permission.denied",
                    category="security",
                    meta={
                        "correlation_id": correlation_id,
                        "path": str(getattr(getattr(request, "url", None), "path", "")),
                        "method": getattr(request, "method", ""),
                        "ip": client_ip,
                        "username": getattr(user, "username", None),
                        "role": getattr(user, "role", None),
                        "permission": permission,
                        "auth_via_token": bool(getattr(request.state, "auth_via_token", False)),
                    },
                )
            except Exception:
                pass
            raise HTTPException(
                status_code=403,
                detail=f"Bu işlem için '{permission}' yetkisi gerekli",
            )
        return user

    return _dependency


# ======================================================
# Basit Brute-force Koruması (Login)
# ======================================================

_AUTH_RATE_LOCK = threading.Lock()
_AUTH_RATE_STATE: dict[str, dict[str, float | int]] = {}


def _auth_limit_config() -> tuple[int, int, int]:
    max_attempts = int((os.getenv("AUTH_MAX_FAILED_ATTEMPTS") or "5").strip() or "5")
    window_sec = int((os.getenv("AUTH_ATTEMPT_WINDOW_SEC") or "300").strip() or "300")
    lock_sec = int((os.getenv("AUTH_LOCKOUT_SEC") or "900").strip() or "900")
    return max(1, max_attempts), max(1, window_sec), max(1, lock_sec)


def _auth_key(username: str, ip_address: str) -> str:
    return f"{(username or '').strip().lower()}|{(ip_address or '').strip()}"


def get_auth_lockout_status(username: str, ip_address: str) -> tuple[bool, int]:
    key = _auth_key(username, ip_address)
    now = time.time()
    with _AUTH_RATE_LOCK:
        row = _AUTH_RATE_STATE.get(key)
        if not row:
            return False, 0
        lock_until = float(row.get("lock_until", 0.0) or 0.0)
        if lock_until > now:
            return True, int(lock_until - now)
        # lock geçmişse temizle
        if lock_until:
            row["lock_until"] = 0.0
            row["fails"] = 0
            row["first_fail_at"] = 0.0
        return False, 0


def record_auth_failure(username: str, ip_address: str) -> tuple[bool, int]:
    key = _auth_key(username, ip_address)
    now = time.time()
    max_attempts, window_sec, lock_sec = _auth_limit_config()
    with _AUTH_RATE_LOCK:
        row = _AUTH_RATE_STATE.get(key) or {"fails": 0, "first_fail_at": 0.0, "lock_until": 0.0}
        first_fail_at = float(row.get("first_fail_at", 0.0) or 0.0)
        if first_fail_at <= 0 or (now - first_fail_at) > window_sec:
            row["fails"] = 0
            row["first_fail_at"] = now
            row["lock_until"] = 0.0

        row["fails"] = int(row.get("fails", 0) or 0) + 1
        if int(row["fails"]) >= max_attempts:
            row["lock_until"] = now + lock_sec
            _AUTH_RATE_STATE[key] = row
            return True, lock_sec

        _AUTH_RATE_STATE[key] = row
        return False, 0


def record_auth_success(username: str, ip_address: str) -> None:
    key = _auth_key(username, ip_address)
    with _AUTH_RATE_LOCK:
        _AUTH_RATE_STATE.pop(key, None)


def clear_auth_rate_limits() -> None:
    with _AUTH_RATE_LOCK:
        _AUTH_RATE_STATE.clear()


def require_admin(
    request: Request,
    x_admin_token: Optional[str] = None,
):
    """
    Admin authentication middleware.
    
    Öncelik sırası:
    1. Session cookie (web tarayıcı)
    2. X-Admin-Token header (API client)
    3. Localhost erişimi (development)
    """
    
    # =====================
    # 1. SESSION COOKIE KONTROLÜ
    # =====================
    if get_session is not None:
        session_token = request.cookies.get(COOKIE_NAME)
        if session_token:
            session = get_session(session_token)
            if session:
                # Session geçerli
                user = get_user(session.username) if get_user else None
                if not user:
                    raise HTTPException(
                        status_code=401,
                        detail="Oturum geçersiz, lütfen tekrar giriş yapın",
                        headers={"X-Redirect": "/admin/login"},
                    )
                
                # 2FA kontrolü
                if user and user.totp_enabled:
                    if not session.is_2fa_verified:
                        raise HTTPException(
                            status_code=401, 
                            detail="2FA doğrulaması gerekli",
                            headers={"X-Redirect": "/admin/verify-2fa"}
                        )
                
                # Session geçerli, kullanıcıyı request'e ekle
                request.state.user = user
                request.state.session = session
                request.state.auth_via_token = False
                return
    
    # =====================
    # 2. X-ADMIN-TOKEN HEADER KONTROLÜ
    # =====================
    admin_token = os.getenv("ADMIN_TOKEN", "").strip()
    if x_admin_token is None:
        x_admin_token = request.headers.get("X-Admin-Token")
    
    if admin_token:
        # Token ayarlanmış, header'ı kontrol et
        if isinstance(x_admin_token, str) and hmac.compare_digest(x_admin_token.strip(), admin_token):
            request.state.auth_via_token = True
            return
    
    # =====================
    # 3. LOCALHOST KONTROLÜ (Development)
    # =====================
    client_ip = getattr(getattr(request, "client", None), "host", None) or ""
    
    # Token ayarlanmamışsa sadece localhost erişebilir
    if not admin_token:
        if client_ip in ("127.0.0.1", "::1", "localhost"):
            return
        raise HTTPException(
            status_code=403, 
            detail="ADMIN_TOKEN not set (local access only)"
        )
    
    # =====================
    # 4. YETKİSİZ ERİŞİM
    # =====================
    raise HTTPException(
        status_code=401, 
        detail="Oturum açmanız gerekiyor",
        headers={"X-Redirect": "/admin/login"}
    )


def require_admin_role(request: Request):
    """
    Admin rolü gerektiren endpoint'ler için.
    Önce require_admin çağrılmalı.
    """
    return require_permission("admin.users.manage")(request)


def get_current_user_from_request(request: Request):
    """
    Request'ten mevcut kullanıcıyı al.
    require_admin middleware'i çalıştıktan sonra kullanılabilir.
    """
    return getattr(request.state, "user", None)


def get_current_session_from_request(request: Request):
    """
    Request'ten mevcut session'ı al.
    require_admin middleware'i çalıştıktan sonra kullanılabilir.
    """
    return getattr(request.state, "session", None)
