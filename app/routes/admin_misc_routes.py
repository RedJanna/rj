"""Admin UI/tools/model routes extracted from legacy monolith."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from app.services.access_control_service import load_paused
from app.utils.message_utils import detect_language
from app.services.conversation_store import is_recovered_active_phone


SUPPORTED_LANGS = {"en", "tr", "ru", "de", "ar", "es", "fr", "zh", "hi", "pt"}
LANGUAGE_NAME_ALIASES = {
    "en": ["english", "ingilizce"],
    "tr": ["turkish", "türkçe", "turkce"],
    "ru": ["russian", "rusça", "rusca", "русский", "по-русски"],
    "de": ["german", "almanca", "deutsch"],
    "ar": ["arabic", "arapça", "arapca", "العربية", "عربي"],
    "es": ["spanish", "ispanyolca", "español", "espanol"],
    "fr": ["french", "fransızca", "fransizca", "français", "francais"],
    "zh": ["chinese", "çince", "cince", "中文", "汉语", "漢語"],
    "hi": ["hindi", "hintçe", "hintce", "हिंदी"],
    "pt": ["portuguese", "portekizce", "português", "portugues"],
}
LANGUAGE_SWITCH_MARKERS = [
    "speak", "talk", "continue in", "write in",
    "konuş", "konusalim", "konuşalım", "devam edelim", "yaz",
]
UNSUPPORTED_LANGUAGE_HINTS = [
    "japanese", "japonca", "日本語",
    "italian", "italyanca", "italiano",
    "korean", "korece", "한국어",
]

HOTEL_RUNTIME_PAGE_HTML = """<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Otel Bilgi Yönetimi</title>
  <style>
    *{box-sizing:border-box}body{margin:0;font-family:Segoe UI,Tahoma,sans-serif;background:linear-gradient(135deg,#0f2027,#203a43,#2c5364);color:#eaf2f8}
    .wrap{max-width:1100px;margin:0 auto;padding:24px}
    .nav{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:20px}
    .nav a{text-decoration:none;color:#8fd3ff;border:1px solid #3b6e89;padding:8px 12px;border-radius:10px}
    .nav a.active{background:#8fd3ff;color:#0f2027;font-weight:700}
    .card{background:rgba(8,24,32,.68);border:1px solid rgba(143,211,255,.18);border-radius:14px;padding:18px;margin-bottom:14px}
    h1{margin:0 0 18px;font-size:28px}h2{margin:0 0 12px;font-size:18px;color:#9fe6b8}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}
    label{display:block;font-size:13px;color:#bdd5df;margin-bottom:6px}
    input,textarea{width:100%;padding:10px;border-radius:10px;border:1px solid #375c6f;background:#102733;color:#f2fbff}
    textarea{min-height:150px;resize:vertical}
    .row{display:flex;gap:10px;flex-wrap:wrap}
    .btn{padding:11px 16px;border:0;border-radius:10px;cursor:pointer;font-weight:700}
    .save{background:#32d68a;color:#07381f}.reload{background:#82c7ff;color:#0f2b3e}
    .note{font-size:12px;color:#9cb8c6;margin-top:8px}
    .ok{color:#86efac}.err{color:#fda4af}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Otel Bilgi Yönetimi</h1>
    <div class="nav">
      <a href="/admin">🏠 Ana Sayfa</a>
      <a href="/admin/dashboard">📊 Dashboard</a>
      <a href="/admin/hotel-runtime-page" class="active">🏨 Otel Bilgi Yönetimi</a>
      <a href="/admin/tools">⚙️ Araçlar</a>
    </div>

    <div class="card">
      <h2>Dinamik Otel Verileri</h2>
      <div class="grid">
        <div><label>Dalaman transfer ücreti (EUR)</label><input id="dalaman_fee" type="number" min="0" max="5000"></div>
        <div><label>Antalya transfer ücreti (EUR)</label><input id="antalya_fee" type="number" min="0" max="5000"></div>
        <div><label>Otel açılış (MM-DD)</label><input id="opening_mmdd" placeholder="04-10"></div>
        <div><label>Otel kapanış (MM-DD)</label><input id="closing_mmdd" placeholder="11-10"></div>
        <div><label>Ücretsiz iptal (gün)</label><input id="free_cancel_days" type="number" min="0" max="30"></div>
        <div><label>Satış birimi iletişim (gün)</label><input id="sales_followup_days" type="number" min="0" max="30"></div>
        <div><label>Restoran-Bar kapanış</label><input id="restaurant_close" placeholder="22:00"></div>
        <div><label>Havuz-Bar kapanış</label><input id="pool_close" placeholder="22:00"></div>
        <div><label>Mesaj delay (saniye)</label><input id="delay_seconds" type="number" min="0" max="12"></div>
        <div><label>Admin numarası</label><input id="admin_phone" placeholder="905xxxxxxxxx"></div>
        <div><label>Chef numarası</label><input id="chef_phone" placeholder="905xxxxxxxxx"></div>
      </div>
    </div>

    <div class="card">
      <h2>Karşılama Mesajı (TR)</h2>
      <label>Türkçe metni girin, sistem diğer dillere otomatik çeviri üretmeye çalışır.</label>
      <textarea id="welcome_tr"></textarea>
      <div class="note">Not: Çeviri için OpenAI anahtarı yoksa mevcut çeviriler korunur.</div>
    </div>

    <div class="card">
      <h2>Ek Runtime Alanları (JSON)</h2>
      <label>Yeni bir runtime key eklemek isterseniz JSON obje olarak girin. Bu alanlar sistemde korunur ve prompt/runtime katmanına taşınır.</label>
      <textarea id="extra_runtime_json" placeholder='{"hotel_restaurant_last_order_time":"21:30"}'></textarea>
    </div>

    <div class="row">
      <button class="btn reload" onclick="loadData()">Yenile</button>
      <button class="btn save" onclick="saveData()">Kaydet</button>
      <div id="status"></div>
    </div>
  </div>

  <script>
    const API = '';
    const KNOWN_KEYS = [
      'dalaman_transfer_fee_eur',
      'antalya_transfer_fee_eur',
      'hotel_opening_mmdd',
      'hotel_closing_mmdd',
      'free_cancellation_days_before_checkin',
      'free_cancel_sales_followup_days_before_checkin',
      'restaurant_bar_closing_time',
      'pool_bar_closing_time',
      'message_delay_seconds',
      'admin_phone',
      'chef_phone',
      'welcome_message_tr',
      'welcome_message_i18n',
    ];
    function byId(id){ return document.getElementById(id); }
    function setStatus(msg, ok=true){
      const el = byId('status');
      el.textContent = msg || '';
      el.className = ok ? 'ok' : 'err';
    }
    function readPayload(){
      const base = {
        dalaman_transfer_fee_eur: Number(byId('dalaman_fee').value || 0),
        antalya_transfer_fee_eur: Number(byId('antalya_fee').value || 0),
        hotel_opening_mmdd: (byId('opening_mmdd').value || '').trim(),
        hotel_closing_mmdd: (byId('closing_mmdd').value || '').trim(),
        free_cancellation_days_before_checkin: Number(byId('free_cancel_days').value || 0),
        free_cancel_sales_followup_days_before_checkin: Number(byId('sales_followup_days').value || 0),
        restaurant_bar_closing_time: (byId('restaurant_close').value || '').trim(),
        pool_bar_closing_time: (byId('pool_close').value || '').trim(),
        message_delay_seconds: Number(byId('delay_seconds').value || 0),
        admin_phone: (byId('admin_phone').value || '').trim(),
        chef_phone: (byId('chef_phone').value || '').trim(),
        welcome_message_tr: (byId('welcome_tr').value || '').trim(),
      };
      const extraText = (byId('extra_runtime_json').value || '').trim();
      if (!extraText) return base;
      let extraObj = {};
      try {
        extraObj = JSON.parse(extraText);
      } catch (_err) {
        throw new Error('Ek Runtime JSON geçersiz.');
      }
      if (!extraObj || typeof extraObj !== 'object' || Array.isArray(extraObj)) {
        throw new Error('Ek Runtime JSON bir obje olmalı.');
      }
      return Object.assign({}, base, extraObj);
    }
    function fill(payload){
      const p = payload || {};
      byId('dalaman_fee').value = p.dalaman_transfer_fee_eur ?? 75;
      byId('antalya_fee').value = p.antalya_transfer_fee_eur ?? 140;
      byId('opening_mmdd').value = p.hotel_opening_mmdd ?? '04-10';
      byId('closing_mmdd').value = p.hotel_closing_mmdd ?? '11-10';
      byId('free_cancel_days').value = p.free_cancellation_days_before_checkin ?? 5;
      byId('sales_followup_days').value = p.free_cancel_sales_followup_days_before_checkin ?? 5;
      byId('restaurant_close').value = p.restaurant_bar_closing_time ?? '22:00';
      byId('pool_close').value = p.pool_bar_closing_time ?? '22:00';
      byId('delay_seconds').value = p.message_delay_seconds ?? 0;
      byId('admin_phone').value = p.admin_phone ?? '';
      byId('chef_phone').value = p.chef_phone ?? '';
      byId('welcome_tr').value = p.welcome_message_tr ?? '';
      const extra = {};
      for (const [k, v] of Object.entries(p)) {
        if (!KNOWN_KEYS.includes(k)) extra[k] = v;
      }
      byId('extra_runtime_json').value = Object.keys(extra).length
        ? JSON.stringify(extra, null, 2)
        : '';
    }
    async function loadData(){
      setStatus('Yukleniyor...');
      try{
        const res = await fetch(API + '/settings');
        const data = await res.json();
        fill((data && data.hotel_runtime_info) || {});
        setStatus('Yuklendi', true);
      }catch(e){
        setStatus('Yukleme hatasi: ' + e.message, false);
      }
    }
    async function saveData(){
      setStatus('Kaydediliyor...');
      try{
        const payload = encodeURIComponent(JSON.stringify(readPayload()));
        const res = await fetch(API + '/settings?hotel_runtime_info_json=' + payload, { method: 'POST' });
        const data = await res.json();
        if (data && data.success === false){
          setStatus('Kayit hatasi: ' + (data.error || 'Bilinmeyen hata'), false);
          return;
        }
        fill((data && data.hotel_runtime_info) || {});
        setStatus('Kaydedildi', true);
      }catch(e){
        setStatus('Kayit hatasi: ' + e.message, false);
      }
    }
    loadData();
  </script>
</body>
</html>
"""


def _normalize_lang(code: str) -> str:
    c = (code or "").strip().lower()
    return c if c in SUPPORTED_LANGS else "en"


def _extract_language_switch_request(text: str) -> tuple[str, bool]:
    low = (text or "").strip().lower()
    if not low:
        return "", False
    has_marker = any(marker in low for marker in LANGUAGE_SWITCH_MARKERS) or "?" in low
    target = ""
    for lang, aliases in LANGUAGE_NAME_ALIASES.items():
        if any(alias in low for alias in aliases):
            target = lang
            break
    if target and has_marker:
        return target, True
    if has_marker and any(x in low for x in UNSUPPORTED_LANGUAGE_HINTS):
        return "en", False
    return "", False


def _infer_language_lock(messages: list[dict]) -> str:
    msgs = messages or []
    # latest explicit switch wins
    for item in reversed(msgs):
        txt = (item.get("user_message") or "").strip()
        if not txt:
            continue
        target, _supported = _extract_language_switch_request(txt)
        if target:
            return target
    # else first user message decides
    for item in msgs:
        txt = (item.get("user_message") or "").strip()
        if txt:
            return _normalize_lang(detect_language(txt))
    return "en"


def build_admin_misc_router(
    app_ref: Any,
    get_session_fn: Callable[[str], Any],
    get_user_fn: Callable[[str], Any],
    get_openai_model_fn: Callable[[], str],
    set_openai_model_fn: Callable[[str], None],
    allowed_models: List[str],
    model_change_info: Dict[str, Any],
    send_whatsapp_message_fn: Callable[[str, str], Awaitable[Any]],
    admin_phone: str,
    whatsapp_phone_id: str,
    whatsapp_token: str,
    conversations_dir: Path,
    is_paused_fn: Callable[[str], bool],
    authorized_persons: Dict[str, str],
    admin_html: str,
    reminder_page_html: str,
    reservations_html: str,
    transfer_reservations_html: str,
    restaurant_plan_html: str,
    dashboard_html: str,
    admin_tools_html: str,
) -> APIRouter:
    router = APIRouter(tags=["admin-misc"])

    @router.get("/admin", response_class=HTMLResponse)
    async def admin_panel(request: Request):
        session_token = request.cookies.get("kassandra_session")
        if not session_token:
            return RedirectResponse(url="/admin/login", status_code=302)
        session = get_session_fn(session_token)
        if not session:
            return RedirectResponse(url="/admin/login", status_code=302)
        user = get_user_fn(session.username)
        if user and user.totp_enabled and not session.is_2fa_verified:
            return RedirectResponse(url="/admin/verify-2fa", status_code=302)
        if user and not user.totp_enabled:
            return RedirectResponse(url="/admin/setup-2fa", status_code=302)
        return admin_html

    @router.get("/admin/root-redirect", response_class=HTMLResponse)
    async def root_redirect():
        return """<html><head><meta http-equiv="refresh" content="0; url=/admin"></head></html>"""

    @router.get("/admin/reminders-page", response_class=HTMLResponse)
    async def reminders_page(request: Request):
        session_token = request.cookies.get("kassandra_session")
        if not session_token:
            return RedirectResponse(url="/admin/login", status_code=302)
        session = get_session_fn(session_token)
        if not session or (get_user_fn(session.username) and get_user_fn(session.username).totp_enabled and not session.is_2fa_verified):
            return RedirectResponse(url="/admin/login", status_code=302)
        return reminder_page_html

    @router.get("/admin/reservations-page", response_class=HTMLResponse)
    async def reservations_page(request: Request):
        session_token = request.cookies.get("kassandra_session")
        if not session_token:
            return RedirectResponse(url="/admin/login", status_code=302)
        session = get_session_fn(session_token)
        if not session or (get_user_fn(session.username) and get_user_fn(session.username).totp_enabled and not session.is_2fa_verified):
            return RedirectResponse(url="/admin/login", status_code=302)
        return reservations_html

    @router.get("/admin/transfer-reservations-page", response_class=HTMLResponse)
    async def transfer_reservations_page():
        return transfer_reservations_html

    @router.get("/admin/restaurant-plan", response_class=HTMLResponse)
    async def restaurant_plan_page(request: Request):
        session_token = request.cookies.get("kassandra_session")
        if not session_token:
            return RedirectResponse(url="/admin/login", status_code=302)
        session = get_session_fn(session_token)
        if not session or (get_user_fn(session.username) and get_user_fn(session.username).totp_enabled and not session.is_2fa_verified):
            return RedirectResponse(url="/admin/login", status_code=302)
        return HTMLResponse(restaurant_plan_html, headers={"Content-Type": "text/html; charset=utf-8"})

    @router.get("/admin/dashboard", response_class=HTMLResponse)
    async def dashboard_page():
        return dashboard_html

    @router.get("/admin/hotel-runtime-page", response_class=HTMLResponse)
    async def hotel_runtime_page(request: Request):
        session_token = request.cookies.get("kassandra_session")
        if not session_token:
            return RedirectResponse(url="/admin/login", status_code=302)
        session = get_session_fn(session_token)
        if not session or (get_user_fn(session.username) and get_user_fn(session.username).totp_enabled and not session.is_2fa_verified):
            return RedirectResponse(url="/admin/login", status_code=302)
        return HOTEL_RUNTIME_PAGE_HTML

    @router.post("/admin/send-message")
    async def send_manual_message(phone: str, message: str):
        clean_phone = re.sub(r"[^\d]", "", phone)
        success = await send_whatsapp_message_fn(clean_phone, message)
        return {
            "status": "sent" if success else "failed",
            "phone": clean_phone,
            "message_preview": message[:50] + "..." if len(message) > 50 else message,
        }

    @router.get("/admin/active-conversations")
    async def get_active_conversations():
        files = list(conversations_dir.glob("*.json"))
        active = []
        now = datetime.now()
        paused_payload = load_paused()
        paused_map = paused_payload.get("paused", {}) if isinstance(paused_payload, dict) else {}
        if not isinstance(paused_map, dict):
            paused_map = {}
        for f in files:
            try:
                with open(f, "r", encoding="utf-8") as file:
                    data = json.load(file)
                    updated = datetime.fromisoformat(data.get("updated_at", "2000-01-01"))
                    phone = str(data.get("phone") or "")
                    clean_phone = re.sub(r"[^\d]", "", phone)
                    paused_entry = paused_map.get(clean_phone) or {}
                    paused_at_raw = ""
                    paused_reason = ""
                    paused_minutes = None
                    if isinstance(paused_entry, dict):
                        paused_at_raw = str(paused_entry.get("paused_at") or "")
                        paused_reason = str(paused_entry.get("reason") or "")
                        try:
                            if paused_at_raw:
                                paused_at_dt = datetime.fromisoformat(paused_at_raw)
                                paused_minutes = max(0, int((now - paused_at_dt).total_seconds() / 60))
                        except Exception:
                            paused_minutes = None
                    is_paused = bool(paused_entry) or is_paused_fn(phone)
                    has_messages = bool(data.get("messages", []))
                    recently_active = (now - updated).total_seconds() < 1800
                    recovered_active = bool(has_messages and is_recovered_active_phone(phone))
                    if recently_active or recovered_active:
                        messages = data.get("messages", [])
                        last_msg = messages[-1] if messages else {}
                        active.append(
                            {
                                "phone": phone,
                                "last_message": last_msg.get("user_message", "")[:50],
                                "last_time": data.get("updated_at"),
                                "message_count": len(messages),
                                "is_paused": is_paused,
                                "paused_reason": paused_reason,
                                "paused_at": paused_at_raw,
                                "paused_minutes": paused_minutes,
                                "minutes_ago": int((now - updated).total_seconds() / 60),
                                "language_lock": _infer_language_lock(messages),
                                "recovered_from_startup": recovered_active and not recently_active,
                            }
                        )
            except Exception:
                pass
        active.sort(key=lambda x: x.get("last_time", ""), reverse=True)
        return {"active_count": len(active), "conversations": active}

    @router.get("/admin/authorized-persons")
    async def get_authorized_persons_api():
        return {"persons": authorized_persons}

    @router.get("/admin/all-endpoints")
    async def get_all_endpoints():
        endpoints = []
        for route in app_ref.routes:
            if hasattr(route, "methods") and hasattr(route, "path"):
                for method in route.methods:
                    if method != "HEAD":
                        endpoints.append({"method": method, "path": route.path, "name": route.name or ""})
        grouped = {}
        for ep in endpoints:
            prefix = ep["path"].split("/")[1] if "/" in ep["path"] else "root"
            grouped.setdefault(prefix, []).append(ep)
        return {"total": len(endpoints), "endpoints": endpoints, "grouped": grouped}

    @router.get("/admin/tools", response_class=HTMLResponse)
    async def admin_tools():
        return admin_tools_html

    @router.get("/admin/model")
    async def get_current_model():
        return {
            "current_model": get_openai_model_fn(),
            "allowed_models": allowed_models,
            "changed_at": model_change_info.get("changed_at"),
            "changed_by": model_change_info.get("changed_by"),
            "previous_model": model_change_info.get("previous_model"),
        }

    @router.post("/admin/model")
    async def change_model(request: Request):
        try:
            body = await request.json()
            new_model = body.get("model", "").strip()
        except Exception:
            return {"success": False, "error": "Geçersiz JSON body"}
        if not new_model:
            return {"success": False, "error": "Model adı boş olamaz"}
        if new_model not in allowed_models:
            return {"success": False, "error": f"Geçersiz model: {new_model}. İzin verilen: {', '.join(allowed_models)}"}

        old_model = get_openai_model_fn()
        if new_model == old_model:
            return {"success": False, "error": "Seçilen model zaten aktif"}

        set_openai_model_fn(new_model)
        now_str = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        model_change_info["changed_at"] = now_str
        model_change_info["changed_by"] = "Admin Panel"
        model_change_info["previous_model"] = old_model
        try:
            notify_msg = (
                f"Model Degisikligi\n"
                f"Eski: {old_model}\n"
                f"Yeni: {new_model}\n"
                f"Zaman: {now_str}\n"
                f"Degistiren: Admin Panel"
            )
            await send_whatsapp_message_fn(admin_phone, notify_msg)
        except Exception as e:
            print(f"[MODEL] Admin bildirim hatası: {e}")
        return {"success": True, "old_model": old_model, "new_model": new_model, "changed_at": now_str}

    @router.get("/test/check-config")
    async def check_config():
        return {
            "admin_phone": admin_phone,
            "whatsapp_phone_id": whatsapp_phone_id[:10] + "..." if whatsapp_phone_id else "BOŞ!",
            "whatsapp_token": "Ayarlanmış ✅" if whatsapp_token else "BOŞ! ❌",
            "status": "OK" if (whatsapp_phone_id and whatsapp_token) else "HATA - Ayarlar eksik!",
        }

    return router
