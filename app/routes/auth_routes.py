"""
Auth Routes - Kimlik Doğrulama Endpoint'leri
============================================
- Login/Logout
- 2FA doğrulama ve kurulum
- Kullanıcı yönetimi (CRUD)
"""

from fastapi import APIRouter, Request, Response, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional
import urllib.parse
import os

from app.core.auth_service import (
    authenticate, verify_2fa_code, get_user,
    create_session, get_session, delete_session, update_session_2fa,
    create_user, delete_user, list_users, update_user_password,
    enable_2fa, disable_2fa, get_totp_uri,
    AdminUser, Session
)
from app.web.login_page import (
    LOGIN_PAGE_HTML, VERIFY_2FA_PAGE_HTML, 
    SETUP_2FA_PAGE_HTML, USER_MANAGEMENT_PAGE_HTML
)

router = APIRouter(tags=["auth"])

COOKIE_NAME = "kassandra_session"
COOKIE_MAX_AGE = 24 * 60 * 60  # 24 saat
APP_ENV = os.getenv("KASSANDRA_ENV", "production").strip().lower()
COOKIE_SECURE = os.getenv(
    "COOKIE_SECURE",
    "false" if APP_ENV in {"dev", "development", "test", "local"} else "true",
).strip().lower() == "true"


# ======================================================
# PYDANTIC MODELS
# ======================================================

class LoginRequest(BaseModel):
    username: str
    password: str


class Verify2FARequest(BaseModel):
    code: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    display_name: Optional[str] = None
    role: str = "operator"


class UpdatePasswordRequest(BaseModel):
    password: str


# ======================================================
# HELPER FONKSİYONLAR
# ======================================================

def get_session_from_cookie(request: Request) -> Optional[Session]:
    """Cookie'den session al"""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    return get_session(token)


def get_current_user(request: Request) -> Optional[AdminUser]:
    """Mevcut oturumdaki kullanıcıyı al"""
    session = get_session_from_cookie(request)
    if not session:
        return None
    
    # 2FA doğrulanmamışsa None döndür
    user = get_user(session.username)
    if user and user.totp_enabled and not session.is_2fa_verified:
        return None
    
    return user


def require_auth(request: Request) -> AdminUser:
    """Oturum gerekli - 2FA dahil tam doğrulama"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Oturum gerekli")
    return user


def require_admin_role(request: Request) -> AdminUser:
    """Admin rolü gerekli"""
    user = require_auth(request)
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin yetkisi gerekli")
    return user


def generate_qr_url(username: str, secret: str) -> str:
    """Google Charts API ile QR kod URL'si oluştur"""
    uri = get_totp_uri(username, secret)
    encoded_uri = urllib.parse.quote(uri)
    return f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={encoded_uri}"


# ======================================================
# HTML SAYFALARI
# ======================================================

@router.get("/admin/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login sayfası"""
    # Zaten giriş yapmışsa admin'e yönlendir
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/admin", status_code=302)
    return HTMLResponse(content=LOGIN_PAGE_HTML)


@router.get("/admin/verify-2fa", response_class=HTMLResponse)
async def verify_2fa_page(request: Request):
    """2FA doğrulama sayfası"""
    session = get_session_from_cookie(request)
    if not session:
        return RedirectResponse(url="/admin/login", status_code=302)
    
    # Zaten doğrulanmışsa admin'e yönlendir
    if session.is_2fa_verified:
        return RedirectResponse(url="/admin", status_code=302)
    
    return HTMLResponse(content=VERIFY_2FA_PAGE_HTML)


@router.get("/admin/setup-2fa", response_class=HTMLResponse)
async def setup_2fa_page(request: Request):
    """2FA kurulum sayfası"""
    session = get_session_from_cookie(request)
    if not session:
        return RedirectResponse(url="/admin/login", status_code=302)
    
    user = get_user(session.username)
    if not user:
        return RedirectResponse(url="/admin/login", status_code=302)
    
    # 2FA zaten aktifse admin'e yönlendir
    if user.totp_enabled:
        return RedirectResponse(url="/admin", status_code=302)
    
    return HTMLResponse(content=SETUP_2FA_PAGE_HTML)


@router.get("/admin/users-page", response_class=HTMLResponse)
async def users_management_page(request: Request, user: AdminUser = Depends(require_admin_role)):
    """Kullanıcı yönetim sayfası (sadece admin)"""
    return HTMLResponse(content=USER_MANAGEMENT_PAGE_HTML)


@router.get("/admin/logout")
async def logout(request: Request, response: Response):
    """Çıkış yap"""
    token = request.cookies.get(COOKIE_NAME)
    if token:
        delete_session(token)
    
    response = RedirectResponse(url="/admin/login", status_code=302)
    response.delete_cookie(COOKIE_NAME)
    return response


# ======================================================
# API ENDPOINT'LERİ
# ======================================================

@router.post("/auth/login")
async def login(request: Request, data: LoginRequest, response: Response):
    """Giriş yap"""
    # Authenticate
    success, user, message = authenticate(data.username, data.password)
    
    if not success:
        return JSONResponse(
            status_code=401,
            content={"success": False, "message": message}
        )
    
    # Session oluştur
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    
    token = create_session(
        username=user.username,
        ip_address=client_ip,
        user_agent=user_agent,
        is_2fa_verified=False  # Henüz 2FA doğrulanmadı
    )
    
    # Cookie ayarla
    response = JSONResponse(content={
        "success": True,
        "requires_2fa": user.totp_enabled,
        "setup_2fa": not user.totp_enabled  # 2FA kurulmamışsa kurulum sayfasına yönlendir
    })
    
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax"
    )
    
    return response


@router.post("/auth/verify-2fa")
async def verify_2fa(request: Request, data: Verify2FARequest):
    """2FA kodunu doğrula"""
    session = get_session_from_cookie(request)
    if not session:
        return JSONResponse(
            status_code=401,
            content={"success": False, "message": "Oturum bulunamadı"}
        )
    
    # Kodu doğrula
    if not verify_2fa_code(session.username, data.code):
        return JSONResponse(
            status_code=401,
            content={"success": False, "message": "Geçersiz kod"}
        )
    
    # Session'ı güncelle
    token = request.cookies.get(COOKIE_NAME)
    update_session_2fa(token, True)
    
    return {"success": True}


@router.get("/auth/setup-2fa-data")
async def get_setup_2fa_data(request: Request):
    """2FA kurulum verilerini al (QR kod ve secret)"""
    session = get_session_from_cookie(request)
    if not session:
        return JSONResponse(
            status_code=401,
            content={"success": False, "message": "Oturum bulunamadı"}
        )
    
    user = get_user(session.username)
    if not user:
        return JSONResponse(
            status_code=404,
            content={"success": False, "message": "Kullanıcı bulunamadı"}
        )
    
    qr_url = generate_qr_url(user.username, user.totp_secret)
    
    return {
        "success": True,
        "secret": user.totp_secret,
        "qr_url": qr_url
    }


@router.post("/auth/enable-2fa")
async def enable_2fa_endpoint(request: Request, data: Verify2FARequest):
    """2FA'yı etkinleştir (ilk kurulum)"""
    session = get_session_from_cookie(request)
    if not session:
        return JSONResponse(
            status_code=401,
            content={"success": False, "message": "Oturum bulunamadı"}
        )
    
    # Kodu doğrula
    if not verify_2fa_code(session.username, data.code):
        return JSONResponse(
            status_code=401,
            content={"success": False, "message": "Geçersiz kod. Lütfen tekrar deneyin."}
        )
    
    # 2FA'yı aktif et
    enable_2fa(session.username)
    
    # Session'ı güncelle
    token = request.cookies.get(COOKIE_NAME)
    update_session_2fa(token, True)
    
    return {"success": True, "message": "2FA etkinleştirildi"}


# ======================================================
# KULLANICI YÖNETİMİ (SADECE ADMİN)
# ======================================================

@router.get("/auth/users")
async def get_users(request: Request, user: AdminUser = Depends(require_admin_role)):
    """Tüm kullanıcıları listele"""
    users = list_users()
    return {"success": True, "users": users}


@router.post("/auth/users")
async def add_user(request: Request, data: CreateUserRequest, user: AdminUser = Depends(require_admin_role)):
    """Yeni kullanıcı oluştur"""
    success, message, totp_secret = create_user(
        username=data.username,
        password=data.password,
        role=data.role,
        display_name=data.display_name
    )
    
    if not success:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": message}
        )
    
    qr_url = generate_qr_url(data.username, totp_secret)
    
    return {
        "success": True,
        "message": message,
        "totp_secret": totp_secret,
        "qr_url": qr_url
    }


@router.delete("/auth/users/{username}")
async def remove_user(username: str, request: Request, user: AdminUser = Depends(require_admin_role)):
    """Kullanıcı sil"""
    if username == user.username:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Kendinizi silemezsiniz"}
        )
    
    success = delete_user(username)
    
    if not success:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Kullanıcı silinemedi (son admin olabilir)"}
        )
    
    return {"success": True, "message": "Kullanıcı silindi"}


@router.put("/auth/users/{username}/password")
async def reset_user_password(username: str, data: UpdatePasswordRequest, request: Request, user: AdminUser = Depends(require_admin_role)):
    """Kullanıcı şifresini sıfırla"""
    if len(data.password) < 8:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Şifre en az 8 karakter olmalı"}
        )
    
    success = update_user_password(username, data.password)
    
    if not success:
        return JSONResponse(
            status_code=404,
            content={"success": False, "message": "Kullanıcı bulunamadı"}
        )
    
    return {"success": True, "message": "Şifre güncellendi"}


# ======================================================
# SESSION BİLGİSİ
# ======================================================

@router.get("/auth/me")
async def get_current_user_info(request: Request):
    """Mevcut kullanıcı bilgilerini al"""
    user = get_current_user(request)
    
    if not user:
        return JSONResponse(
            status_code=401,
            content={"success": False, "authenticated": False}
        )
    
    return {
        "success": True,
        "authenticated": True,
        "user": {
            "username": user.username,
            "role": user.role,
            "display_name": user.display_name,
            "totp_enabled": user.totp_enabled
        }
    }
