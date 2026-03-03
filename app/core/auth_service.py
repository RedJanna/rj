"""
Auth Service - Kimlik Doğrulama Servisi
=======================================
- Kullanıcı yönetimi (CRUD)
- Şifre hashleme (bcrypt)
- 2FA (Google Authenticator / TOTP)
- Session yönetimi
"""

import os
import json
import secrets
import hashlib
import base64
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, asdict
import hmac
import struct

# ======================================================
# YAPILANDIRMA
# ======================================================

DATA_DIR = Path("data")
USERS_FILE = DATA_DIR / "admin_users.json"
SESSIONS_FILE = DATA_DIR / "admin_sessions.json"

SESSION_DURATION_HOURS = 24  # 24 saat
TOTP_ISSUER = "KassandraAdmin"  # Google Authenticator'da görünecek isim
PBKDF2_ALGORITHM = "sha256"
PBKDF2_ITERATIONS = int(os.getenv("PASSWORD_PBKDF2_ITERATIONS", "210000"))


def _get_session_duration_hours() -> int:
    """Oturum süresini admin ayarlarından oku; yoksa varsayılanı kullan."""
    try:
        from app.core.settings_service import load_settings

        raw_value = load_settings().get("session_duration_hours", SESSION_DURATION_HOURS)
        hours = int(raw_value)
        if 1 <= hours <= 720:
            return hours
    except Exception:
        pass
    return SESSION_DURATION_HOURS


# ======================================================
# TOTP (Google Authenticator) - Pure Python
# ======================================================

def generate_totp_secret() -> str:
    """Yeni TOTP secret oluştur (base32)"""
    random_bytes = secrets.token_bytes(20)
    return base64.b32encode(random_bytes).decode('utf-8').rstrip('=')


def get_totp_code(secret: str, time_step: int = 30) -> str:
    """TOTP kodu hesapla"""
    # Secret'ı decode et
    secret = secret.upper()
    # Padding ekle
    padding = 8 - (len(secret) % 8)
    if padding != 8:
        secret += '=' * padding
    
    try:
        key = base64.b32decode(secret)
    except:
        return ""
    
    # Zaman sayacı
    counter = int(time.time()) // time_step
    
    # HMAC-SHA1
    counter_bytes = struct.pack('>Q', counter)
    hmac_hash = hmac.new(key, counter_bytes, hashlib.sha1).digest()
    
    # Dynamic truncation
    offset = hmac_hash[-1] & 0x0F
    code = struct.unpack('>I', hmac_hash[offset:offset+4])[0]
    code = (code & 0x7FFFFFFF) % 1000000
    
    return str(code).zfill(6)


def verify_totp(secret: str, code: str, window: int = 1) -> bool:
    """TOTP kodunu doğrula (±window time step tolerans)"""
    if not secret or not code:
        return False
    
    code = code.strip()
    
    for i in range(-window, window + 1):
        # Her time window için kontrol
        counter = (int(time.time()) // 30) + i
        
        secret_padded = secret.upper()
        padding = 8 - (len(secret_padded) % 8)
        if padding != 8:
            secret_padded += '=' * padding
        
        try:
            key = base64.b32decode(secret_padded)
        except:
            continue
        
        counter_bytes = struct.pack('>Q', counter)
        hmac_hash = hmac.new(key, counter_bytes, hashlib.sha1).digest()
        
        offset = hmac_hash[-1] & 0x0F
        generated = struct.unpack('>I', hmac_hash[offset:offset+4])[0]
        generated = (generated & 0x7FFFFFFF) % 1000000
        generated_str = str(generated).zfill(6)
        
        if hmac.compare_digest(generated_str, code):
            return True
    
    return False


def get_totp_uri(username: str, secret: str) -> str:
    """Google Authenticator için QR kod URI'si"""
    return f"otpauth://totp/{TOTP_ISSUER}:{username}?secret={secret}&issuer={TOTP_ISSUER}"


# ======================================================
# ŞİFRE HASHLEME (bcrypt benzeri - pure Python)
# ======================================================

def hash_password(password: str) -> str:
    """Şifreyi hashle (PBKDF2-SHA256 + salt)"""
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM,
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    salt_b64 = base64.b64encode(salt).decode("ascii")
    hash_b64 = base64.b64encode(derived).decode("ascii")
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt_b64}${hash_b64}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Şifreyi doğrula"""
    try:
        parts = stored_hash.split("$")
        # Yeni format: pbkdf2_sha256$iterations$salt_b64$hash_b64
        if len(parts) == 4 and parts[0] == "pbkdf2_sha256":
            iterations = int(parts[1])
            salt = base64.b64decode(parts[2].encode("ascii"))
            expected = base64.b64decode(parts[3].encode("ascii"))
            derived = hashlib.pbkdf2_hmac(
                PBKDF2_ALGORITHM,
                password.encode("utf-8"),
                salt,
                iterations,
            )
            return hmac.compare_digest(derived, expected)

        # Geriye uyumluluk: legacy salt$sha256 formatı
        if len(parts) == 2:
            salt, password_hash = parts
            hash_input = f"{salt}{password}".encode("utf-8")
            computed_hash = hashlib.sha256(hash_input).hexdigest()
            return hmac.compare_digest(computed_hash, password_hash)
    except Exception:
        return False
    return False


# ======================================================
# KULLANICI MODELİ
# ======================================================

@dataclass
class AdminUser:
    username: str
    password_hash: str
    role: str  # "admin" veya "operator"
    totp_secret: str
    totp_enabled: bool
    created_at: str
    last_login: Optional[str] = None
    display_name: Optional[str] = None
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'AdminUser':
        return cls(**data)


# ======================================================
# KULLANICI YÖNETİMİ
# ======================================================

def _ensure_data_dir():
    """Data dizinini oluştur"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_users() -> Dict[str, AdminUser]:
    """Kullanıcıları yükle"""
    _ensure_data_dir()
    
    if not USERS_FILE.exists():
        return {}
    
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return {k: AdminUser.from_dict(v) for k, v in data.items()}
    except:
        return {}


def save_users(users: Dict[str, AdminUser]):
    """Kullanıcıları kaydet"""
    _ensure_data_dir()
    
    data = {k: v.to_dict() for k, v in users.items()}
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_user(username: str) -> Optional[AdminUser]:
    """Kullanıcı getir"""
    users = load_users()
    return users.get(username)


def create_user(
    username: str,
    password: str,
    role: str = "operator",
    display_name: str = None
) -> Tuple[bool, str, Optional[str]]:
    """
    Yeni kullanıcı oluştur
    Returns: (success, message, totp_secret)
    """
    users = load_users()
    
    if username in users:
        return False, "Kullanıcı zaten mevcut", None
    
    if len(password) < 8:
        return False, "Şifre en az 8 karakter olmalı", None
    
    totp_secret = generate_totp_secret()
    
    user = AdminUser(
        username=username,
        password_hash=hash_password(password),
        role=role,
        totp_secret=totp_secret,
        totp_enabled=False,  # 2FA kurulumu tamamlanınca True olacak
        created_at=datetime.now().isoformat(),
        display_name=display_name or username
    )
    
    users[username] = user
    save_users(users)
    
    return True, "Kullanıcı oluşturuldu", totp_secret


def update_user_password(username: str, new_password: str) -> bool:
    """Kullanıcı şifresini güncelle"""
    users = load_users()
    
    if username not in users:
        return False
    
    users[username].password_hash = hash_password(new_password)
    save_users(users)
    return True


def enable_2fa(username: str) -> bool:
    """2FA'yı aktif et"""
    users = load_users()
    
    if username not in users:
        return False
    
    users[username].totp_enabled = True
    save_users(users)
    return True


def disable_2fa(username: str) -> Tuple[bool, str]:
    """2FA'yı devre dışı bırak ve yeni secret oluştur"""
    users = load_users()
    
    if username not in users:
        return False, ""
    
    new_secret = generate_totp_secret()
    users[username].totp_secret = new_secret
    users[username].totp_enabled = False
    save_users(users)
    return True, new_secret


def delete_user(username: str) -> bool:
    """Kullanıcı sil"""
    users = load_users()
    
    if username not in users:
        return False
    
    # Admin kullanıcısını silmeye izin verme (en az 1 admin olmalı)
    admin_count = sum(1 for u in users.values() if u.role == "admin")
    if users[username].role == "admin" and admin_count <= 1:
        return False
    
    del users[username]
    save_users(users)
    return True


def list_users() -> List[dict]:
    """Tüm kullanıcıları listele (şifre hariç)"""
    users = load_users()
    
    result = []
    for username, user in users.items():
        result.append({
            "username": username,
            "role": user.role,
            "display_name": user.display_name,
            "totp_enabled": user.totp_enabled,
            "created_at": user.created_at,
            "last_login": user.last_login
        })
    
    return result


def authenticate(username: str, password: str) -> Tuple[bool, Optional[AdminUser], str]:
    """
    Kullanıcı doğrula (şifre kontrolü)
    Returns: (success, user, message)
    """
    user = get_user(username)
    
    if not user:
        return False, None, "Kullanıcı bulunamadı"
    
    if not verify_password(password, user.password_hash):
        return False, None, "Hatalı şifre"

    # Legacy hash formatından yeni PBKDF2 formatına otomatik yükselt.
    if not user.password_hash.startswith("pbkdf2_sha256$"):
        users = load_users()
        if username in users:
            users[username].password_hash = hash_password(password)
            save_users(users)
            user = users[username]
    
    return True, user, "OK"


def verify_2fa_code(username: str, code: str) -> bool:
    """2FA kodunu doğrula"""
    user = get_user(username)
    
    if not user:
        return False
    
    return verify_totp(user.totp_secret, code)


# ======================================================
# SESSION YÖNETİMİ
# ======================================================

@dataclass
class Session:
    token: str
    username: str
    created_at: str
    expires_at: str
    ip_address: str
    user_agent: str
    is_2fa_verified: bool = False
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Session':
        return cls(**data)
    
    def is_expired(self) -> bool:
        return datetime.fromisoformat(self.expires_at) < datetime.now()


def load_sessions() -> Dict[str, Session]:
    """Session'ları yükle"""
    _ensure_data_dir()
    
    if not SESSIONS_FILE.exists():
        return {}
    
    try:
        with open(SESSIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return {k: Session.from_dict(v) for k, v in data.items()}
    except:
        return {}


def save_sessions(sessions: Dict[str, Session]):
    """Session'ları kaydet"""
    _ensure_data_dir()
    
    data = {k: v.to_dict() for k, v in sessions.items()}
    with open(SESSIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def create_session(
    username: str,
    ip_address: str,
    user_agent: str,
    is_2fa_verified: bool = False
) -> str:
    """Yeni session oluştur, token döndür"""
    sessions = load_sessions()
    
    # Eski session'ları temizle
    cleanup_expired_sessions()
    
    token = secrets.token_urlsafe(32)
    now = datetime.now()
    expires = now + timedelta(hours=_get_session_duration_hours())
    
    session = Session(
        token=token,
        username=username,
        created_at=now.isoformat(),
        expires_at=expires.isoformat(),
        ip_address=ip_address,
        user_agent=user_agent[:200] if user_agent else "",
        is_2fa_verified=is_2fa_verified
    )
    
    sessions[token] = session
    save_sessions(sessions)
    
    # Last login güncelle
    users = load_users()
    if username in users:
        users[username].last_login = now.isoformat()
        save_users(users)
    
    return token


def get_session(token: str) -> Optional[Session]:
    """Session getir"""
    if not token:
        return None
    
    sessions = load_sessions()
    session = sessions.get(token)
    
    if not session:
        return None
    
    if session.is_expired():
        delete_session(token)
        return None
    
    return session


def update_session_2fa(token: str, is_verified: bool) -> bool:
    """Session'ın 2FA durumunu güncelle"""
    sessions = load_sessions()
    
    if token not in sessions:
        return False
    
    sessions[token].is_2fa_verified = is_verified
    save_sessions(sessions)
    return True


def delete_session(token: str) -> bool:
    """Session sil (logout)"""
    sessions = load_sessions()
    
    if token not in sessions:
        return False
    
    del sessions[token]
    save_sessions(sessions)
    return True


def cleanup_expired_sessions():
    """Süresi dolmuş session'ları temizle"""
    sessions = load_sessions()
    
    now = datetime.now()
    expired_tokens = [
        token for token, session in sessions.items()
        if datetime.fromisoformat(session.expires_at) < now
    ]
    
    for token in expired_tokens:
        del sessions[token]
    
    if expired_tokens:
        save_sessions(sessions)


def get_user_sessions(username: str) -> List[Session]:
    """Kullanıcının tüm session'larını getir"""
    sessions = load_sessions()
    return [s for s in sessions.values() if s.username == username]


def delete_user_sessions(username: str):
    """Kullanıcının tüm session'larını sil"""
    sessions = load_sessions()
    
    tokens_to_delete = [
        token for token, session in sessions.items()
        if session.username == username
    ]
    
    for token in tokens_to_delete:
        del sessions[token]
    
    if tokens_to_delete:
        save_sessions(sessions)


# ======================================================
# İLK KURULUM
# ======================================================

def initialize_admin_user(username: str, password: str) -> str:
    """İlk admin kullanıcısını oluştur, TOTP secret döndür"""
    users = load_users()
    
    # Zaten kullanıcı varsa atla
    if users:
        print("⚠️ Kullanıcılar zaten mevcut, ilk kurulum atlandı")
        return ""
    
    success, message, totp_secret = create_user(
        username=username,
        password=password,
        role="admin",
        display_name="Sistem Admini"
    )
    
    if success:
        print(f"✅ İlk admin kullanıcısı oluşturuldu: {username}")
        print(f"🔐 2FA Secret: {totp_secret}")
        print(f"📱 Google Authenticator URI: {get_totp_uri(username, totp_secret)}")
        return totp_secret
    else:
        print(f"❌ Admin oluşturulamadı: {message}")
        return ""


# ======================================================
# EXPORT
# ======================================================

__all__ = [
    # User management
    'get_user', 'create_user', 'update_user_password', 'delete_user', 'list_users',
    'authenticate', 'enable_2fa', 'disable_2fa', 'verify_2fa_code',
    
    # Session management
    'create_session', 'get_session', 'delete_session', 'update_session_2fa',
    'get_user_sessions', 'delete_user_sessions', 'cleanup_expired_sessions',
    
    # TOTP helpers
    'get_totp_uri', 'verify_totp', 'generate_totp_secret',
    
    # Setup
    'initialize_admin_user',
    
    # Models
    'AdminUser', 'Session'
]
