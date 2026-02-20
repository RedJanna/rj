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
from fastapi import HTTPException, Request
from typing import Optional

# Session yönetimi için import
try:
    from app.core.auth_service import get_session, get_user
except ImportError:
    # Henüz auth_service yüklenmemişse fallback
    get_session = None
    get_user = None

COOKIE_NAME = "kassandra_session"


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
                return
    
    # =====================
    # 2. X-ADMIN-TOKEN HEADER KONTROLÜ
    # =====================
    admin_token = os.getenv("ADMIN_TOKEN", "").strip()
    if x_admin_token is None:
        x_admin_token = request.headers.get("X-Admin-Token")
    
    if admin_token:
        # Token ayarlanmış, header'ı kontrol et
        if isinstance(x_admin_token, str) and x_admin_token.strip() == admin_token:
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
    require_admin(request)
    
    user = getattr(request.state, "user", None)
    if not user or user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Bu işlem için admin yetkisi gerekli"
        )
    
    return user


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
