"""Admin UI/tools/model routes extracted from legacy monolith."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List
from uuid import uuid4

import httpx

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from app.services.access_control_service import load_paused
from app.services.admin_chat_lab_service import (
    append_chat_lab_event,
    build_chat_lab_snapshot,
)
from app.services.conversation_store import is_recovered_active_phone, purge_phone_data
from app.services.correlation_service import CORRELATION_HEADER
from app.utils.message_utils import detect_language


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

ADMIN_CHAT_LAB_HTML = """<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Admin Chat Laboratuvarı</title>
  <style>
    :root{
      --bg:#f3efe7;
      --ink:#1e2331;
      --muted:#6f7486;
      --panel:#151b2f;
      --panel-2:#1d2540;
      --line:rgba(255,255,255,.08);
      --hero:#d3a85f;
      --hero-2:#f05e4a;
      --user:#1aa6a6;
      --bot:#ffffff;
      --ok:#93e6ae;
      --warn:#f7cb6b;
      --danger:#ff8d8d;
      --debug:#0f1425;
      --chip:#24304f;
      --shadow:0 20px 50px rgba(9,14,28,.18);
    }
    *{box-sizing:border-box}
    body{
      margin:0;
      min-height:100vh;
      font-family:"Trebuchet MS","Segoe UI",sans-serif;
      color:var(--ink);
      background:
        radial-gradient(circle at top left, rgba(240,94,74,.12), transparent 28%),
        radial-gradient(circle at top right, rgba(211,168,95,.18), transparent 22%),
        linear-gradient(180deg, #efe7d8 0%, var(--bg) 32%, #e8edf4 100%);
    }
    .shell{min-height:100vh;display:grid;grid-template-rows:auto 1fr}
    .topbar{
      background:linear-gradient(120deg,#131a31,#1b2443 60%,#202b50);
      color:#eef3ff;
      padding:18px 22px;
      box-shadow:0 10px 35px rgba(10,16,32,.25);
      position:sticky;top:0;z-index:20;
    }
    .topbar-inner{display:flex;justify-content:space-between;gap:16px;align-items:center;flex-wrap:wrap}
    .brand{display:flex;align-items:center;gap:14px}
    .brand-mark{
      width:44px;height:44px;border-radius:14px;
      background:linear-gradient(135deg,var(--hero),var(--hero-2));
      display:grid;place-items:center;font-size:20px;color:#161922;font-weight:900;
      box-shadow:0 12px 22px rgba(240,94,74,.25);
    }
    .brand h1{
      margin:0;
      font-family:"Palatino Linotype","Book Antiqua",serif;
      font-size:28px;
      letter-spacing:.01em;
    }
    .brand p{margin:4px 0 0;color:#b9c1d8;font-size:13px}
    .controls{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
    .controls label{font-size:12px;color:#a9b2cf;margin-bottom:4px;display:block}
    .control{min-width:170px}
    .topbar select,.topbar input{
      width:100%;padding:10px 12px;border-radius:12px;border:1px solid rgba(255,255,255,.12);
      background:rgba(255,255,255,.07);color:#fff;outline:none;
    }
    .btn{
      border:0;border-radius:12px;padding:11px 15px;font-weight:700;cursor:pointer;
      transition:transform .18s ease,box-shadow .18s ease,opacity .18s ease;
    }
    .btn:hover{transform:translateY(-1px)}
    .btn-primary{background:linear-gradient(135deg,var(--hero),var(--hero-2));color:#13161f;box-shadow:0 10px 24px rgba(240,94,74,.24)}
    .btn-subtle{background:rgba(255,255,255,.08);color:#fff;border:1px solid rgba(255,255,255,.1)}
    .btn-danger{background:#f54d57;color:#fff}
    .main{
      display:grid;
      grid-template-columns:minmax(0,1.3fr) minmax(330px,.7fr);
      gap:18px;
      padding:18px;
      align-items:start;
    }
    .panel{
      background:rgba(255,255,255,.58);
      backdrop-filter:blur(16px);
      border:1px solid rgba(18,28,48,.07);
      border-radius:22px;
      box-shadow:var(--shadow);
      overflow:hidden;
    }
    .chat-shell{
      min-height:calc(100vh - 132px);
      display:grid;
      grid-template-rows:auto 1fr auto auto;
      background:
        linear-gradient(180deg, rgba(255,255,255,.7), rgba(245,244,239,.84)),
        radial-gradient(circle at 20% 0%, rgba(26,166,166,.08), transparent 26%);
    }
    .toolbar{
      padding:18px 20px 10px;
      display:flex;justify-content:space-between;gap:14px;align-items:flex-start;flex-wrap:wrap;
    }
    .toolbar h2{margin:0;font-size:21px;font-family:"Palatino Linotype","Book Antiqua",serif}
    .toolbar p{margin:6px 0 0;color:var(--muted);font-size:13px}
    .chips{display:flex;gap:8px;flex-wrap:wrap;padding:0 20px 14px}
    .chip{
      background:rgba(36,48,79,.08);color:#27304f;border:1px solid rgba(39,48,79,.08);
      padding:8px 12px;border-radius:999px;font-size:12px;cursor:pointer;
    }
    .chip:hover{background:rgba(36,48,79,.14)}
    .chat-window{
      padding:6px 20px 18px;
      overflow:auto;
      display:flex;flex-direction:column;gap:14px;
      min-height:420px;max-height:56vh;
    }
    .msg{display:flex;flex-direction:column;max-width:min(82%,720px)}
    .msg.user{align-self:flex-end}
    .msg.bot{align-self:flex-start}
    .bubble{
      padding:16px 18px;
      border-radius:18px;
      line-height:1.52;
      white-space:pre-wrap;
      word-break:break-word;
      box-shadow:0 10px 24px rgba(22,28,40,.08);
    }
    .user .bubble{
      background:linear-gradient(135deg,#1ca8a3,#198390);
      color:#f7ffff;border-bottom-right-radius:6px;
    }
    .bot .bubble{
      background:rgba(255,255,255,.92);
      color:#1d2434;border:1px solid rgba(20,26,40,.08);border-bottom-left-radius:6px;
    }
    .meta{
      margin-top:6px;font-size:11px;color:var(--muted);padding:0 4px;
      display:flex;gap:8px;flex-wrap:wrap;
    }
    .composer{padding:14px 18px;border-top:1px solid rgba(25,31,48,.07)}
    .composer-inner{display:grid;grid-template-columns:1fr auto;gap:12px;align-items:end}
    .composer textarea{
      width:100%;min-height:82px;max-height:220px;resize:vertical;border-radius:18px;
      border:1px solid rgba(27,35,59,.12);padding:15px 16px;background:rgba(255,255,255,.82);color:#1e2331;
      font:inherit;box-shadow:inset 0 1px 0 rgba(255,255,255,.5);
    }
    .composer-actions{display:flex;gap:10px;align-items:center}
    .mini-note{font-size:12px;color:var(--muted);padding:0 2px;margin-top:8px}
    .debug{
      background:linear-gradient(180deg,#151b2f 0%, #101528 100%);
      color:#eef3ff;
      min-height:calc(100vh - 132px);
      display:grid;
      grid-template-rows:auto auto auto 1fr;
    }
    .debug-head{padding:18px 18px 10px;border-bottom:1px solid var(--line)}
    .debug-head h3{margin:0;font-size:18px;font-family:"Palatino Linotype","Book Antiqua",serif}
    .debug-head p{margin:6px 0 0;color:#aab4d7;font-size:12px}
    .debug-grid{
      padding:14px 14px 10px;
      display:grid;grid-template-columns:1fr;gap:10px;
    }
    .debug-card{
      background:rgba(255,255,255,.04);
      border:1px solid var(--line);
      border-radius:16px;
      padding:12px 12px 10px;
    }
    .debug-label{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#93a1ca;margin-bottom:7px}
    .badge{
      display:inline-flex;align-items:center;padding:4px 10px;border-radius:999px;
      font-size:12px;font-weight:700;
    }
    .badge.good{background:rgba(147,230,174,.14);color:var(--ok)}
    .badge.warn{background:rgba(247,203,107,.14);color:var(--warn)}
    .badge.danger{background:rgba(255,141,141,.14);color:var(--danger)}
    .json-block,.trace-list,.event-list{
      font-family:"Consolas","SFMono-Regular",monospace;
      font-size:12px;line-height:1.5;
      background:rgba(0,0,0,.24);border-radius:14px;border:1px solid rgba(255,255,255,.05);
      padding:12px;max-height:240px;overflow:auto;white-space:pre-wrap;word-break:break-word;
    }
    .trace-wrap{padding:0 14px 14px}
    .trace-wrap h4{margin:2px 0 10px;color:#dbe5ff;font-size:13px}
    .trace-item,.event-item{
      padding:10px 0;border-bottom:1px solid rgba(255,255,255,.06)
    }
    .trace-item:last-child,.event-item:last-child{border-bottom:0}
    .trace-stage{color:#f0c97d;font-weight:700}
    .trace-meta{color:#aab4d7;font-size:11px;margin-top:4px}
    .status-bar{
      display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap;
      padding:10px 18px 16px;color:var(--muted);font-size:12px
    }
    .pulse{
      width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:8px;
      background:#42d392;box-shadow:0 0 0 rgba(66,211,146,.45);animation:pulse 1.8s infinite;
    }
    @keyframes pulse {
      0%{box-shadow:0 0 0 0 rgba(66,211,146,.35)}
      70%{box-shadow:0 0 0 12px rgba(66,211,146,0)}
      100%{box-shadow:0 0 0 0 rgba(66,211,146,0)}
    }
    @media (max-width: 1100px){
      .main{grid-template-columns:1fr}
      .chat-shell,.debug{min-height:auto}
      .chat-window{max-height:none}
    }
    @media (max-width: 720px){
      .topbar{padding:16px}
      .main{padding:12px}
      .toolbar,.chips,.composer,.debug-head,.debug-grid,.trace-wrap{padding-left:14px;padding-right:14px}
      .msg{max-width:92%}
      .composer-inner{grid-template-columns:1fr}
      .composer-actions{justify-content:space-between}
      .controls{width:100%}
      .control{min-width:0;flex:1 1 100%}
    }
  </style>
</head>
<body>
  <div class="shell">
    <div class="topbar">
      <div class="topbar-inner">
        <div class="brand">
          <div class="brand-mark">◎</div>
          <div>
            <h1>Chat Laboratuvarı</h1>
            <p>WhatsApp pipeline ile aynı çekirdek, Meta olmadan canlı debug çalışma alanı.</p>
          </div>
        </div>
        <div class="controls">
          <div class="control">
            <label>Model</label>
            <select id="modelSelect"></select>
          </div>
          <div class="control">
            <label>Test Telefonu</label>
            <input id="phoneInput" value="905599991234" />
          </div>
          <button class="btn btn-subtle" onclick="resetConversation()">Reset</button>
          <a href="/admin/tools" class="btn btn-subtle" style="text-decoration:none;display:inline-flex;align-items:center;">Araçlara Dön</a>
        </div>
      </div>
    </div>

    <div class="main">
      <section class="panel chat-shell">
        <div class="toolbar">
          <div>
            <h2>Admin Sohbet Simülatörü</h2>
            <p>Buradan gönderilen her mesaj gerçek `/chat` akışına gider. Sağ panel correlation trace ve flow state'i anlık gösterir.</p>
          </div>
          <button class="btn btn-primary" onclick="refreshSnapshot()">Debug Yenile</button>
        </div>

        <div class="chips">
          <button class="chip" onclick="usePrompt('Bana 21 Nisan ile 23 Nisan arasında fiyat bilgisi verir misin')">Konaklama fiyatı</button>
          <button class="chip" onclick="usePrompt('Dalaman transfer ücreti kaç euro?')">Transfer ücreti</button>
          <button class="chip" onclick="usePrompt('22 Nisan akşamı için restoranda 2 kişilik masa ayırtmak istiyorum')">Restoran rezervasyonu</button>
          <button class="chip" onclick="usePrompt('Otel ne zaman açılıyor?')">Operasyon bilgisi</button>
        </div>

        <div id="chatWindow" class="chat-window">
          <div class="msg bot">
            <div class="bubble">Hazır. Mesaj gönderdiğinde hem bot cevabı hem de backend iç trace burada izlenir.</div>
            <div class="meta"><span>system</span></div>
          </div>
        </div>

        <div class="composer">
          <div class="composer-inner">
            <div>
              <textarea id="messageInput" placeholder="Mesajınızı yazın. Örn: 21 Nisan ile 23 Nisan arasında 2 yetişkin için fiyat nedir?"></textarea>
              <div class="mini-note">Enter + Shift yeni satır. Sadece Enter gönderir.</div>
            </div>
            <div class="composer-actions">
              <button class="btn btn-subtle" onclick="insertGreeting()">Merhaba</button>
              <button class="btn btn-primary" onclick="sendMessage()">Gönder</button>
            </div>
          </div>
        </div>

        <div class="status-bar">
          <div><span class="pulse"></span><span id="statusText">Hazır</span></div>
          <div id="correlationText">correlation: -</div>
        </div>
      </section>

      <aside class="panel debug">
        <div class="debug-head">
          <h3>Debug Panel</h3>
          <p>Trace, flow state, backend olayları ve tam iç snapshot burada tutulur.</p>
        </div>

        <div class="debug-grid">
          <div class="debug-card"><div class="debug-label">Conversation State</div><div id="stateBadge" class="badge warn">GREETING</div></div>
          <div class="debug-card"><div class="debug-label">Intent</div><div id="intentBadge" class="badge warn">other</div></div>
          <div class="debug-card"><div class="debug-label">Language</div><div id="languageBadge" class="badge good">tr</div></div>
          <div class="debug-card"><div class="debug-label">Risk Flags</div><div id="riskFlags" class="json-block">[]</div></div>
          <div class="debug-card"><div class="debug-label">Escalation</div><div id="escalationBlock" class="json-block">{}</div></div>
          <div class="debug-card"><div class="debug-label">Entities</div><div id="entitiesBlock" class="json-block">{}</div></div>
          <div class="debug-card"><div class="debug-label">Next Step</div><div id="nextStepBlock" class="badge good">await_user_intent</div></div>
          <div class="debug-card"><div class="debug-label">Full Internal JSON</div><div id="fullJson" class="json-block">{}</div></div>
        </div>

        <div class="trace-wrap">
          <h4>Decision Trace</h4>
          <div id="traceList" class="trace-list">Henüz trace yok.</div>
        </div>

        <div class="trace-wrap">
          <h4>Backend Events</h4>
          <div id="backendEvents" class="event-list">Henüz backend olayı yok.</div>
        </div>
      </aside>
    </div>
  </div>

  <script>
    const state = {
      phone: '',
      correlationId: '',
      autoRefreshHandle: null,
      messages: [],
    };

    function byId(id){ return document.getElementById(id); }

    function setStatus(text){
      byId('statusText').textContent = text || 'Hazır';
    }

    function safeJson(value){
      return JSON.stringify(value ?? {}, null, 2);
    }

    function usePrompt(text){
      byId('messageInput').value = text;
      byId('messageInput').focus();
    }

    function insertGreeting(){
      byId('messageInput').value = 'Merhaba';
      byId('messageInput').focus();
    }

    function currentPhone(){
      return (byId('phoneInput').value || '').trim();
    }

    function setBadge(id, value, variant){
      const el = byId(id);
      el.textContent = value || '-';
      el.className = 'badge ' + (variant || 'warn');
    }

    function renderMessages(messages){
      const items = [];
      (messages || []).forEach((row) => {
        const user = (row.user_message || '').trim();
        const bot = (row.bot_reply || '').trim();
        if (user){
          items.push({ role: 'user', text: user, meta: row.date || row.timestamp || row.time || '' });
        }
        if (bot){
          items.push({ role: 'bot', text: bot, meta: row.date || row.timestamp || row.time || row.status || '' });
        }
      });

      const html = items.length ? items.map((item) => `
        <div class="msg ${item.role}">
          <div class="bubble">${escapeHtml(item.text)}</div>
          <div class="meta"><span>${item.role}</span><span>${escapeHtml(item.meta || '')}</span></div>
        </div>
      `).join('') : `
        <div class="msg bot">
          <div class="bubble">Bu telefon için henüz kayıtlı mesaj yok.</div>
          <div class="meta"><span>system</span></div>
        </div>
      `;
      byId('chatWindow').innerHTML = html;
      byId('chatWindow').scrollTop = byId('chatWindow').scrollHeight;
    }

    function renderTrace(list){
      if (!list || !list.length){
        byId('traceList').textContent = 'Henüz trace yok.';
        return;
      }
      byId('traceList').innerHTML = list.map((row) => {
        const main = row.event || row.primary_intent || row.stage || 'trace';
        return `
          <div class="trace-item">
            <div><span class="trace-stage">${escapeHtml(row.stage || 'stage')}</span> · ${escapeHtml(String(main))}</div>
            <div class="trace-meta">${escapeHtml(safeSummary(row))}</div>
          </div>
        `;
      }).join('');
    }

    function renderEvents(targetId, list, emptyText){
      if (!list || !list.length){
        byId(targetId).textContent = emptyText;
        return;
      }
      byId(targetId).innerHTML = list.map((row) => `
        <div class="event-item">${escapeHtml(safeSummary(row))}</div>
      `).join('');
    }

    function safeSummary(row){
      const slim = Object.assign({}, row);
      delete slim.flow_states;
      delete slim.full_internal_json;
      return JSON.stringify(slim);
    }

    function escapeHtml(text){
      return String(text || '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;');
    }

    async function loadModels(){
      const res = await fetch('/admin/model');
      const data = await res.json();
      const select = byId('modelSelect');
      select.innerHTML = (data.allowed_models || []).map((model) => `
        <option value="${escapeHtml(model)}" ${model === data.current_model ? 'selected' : ''}>${escapeHtml(model)}</option>
      `).join('');
    }

    async function changeModel(){
      const model = byId('modelSelect').value;
      const res = await fetch('/admin/model', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model }),
      });
      const data = await res.json();
      if (data && data.success){
        setStatus('Model güncellendi: ' + model);
        return;
      }
      setStatus('Model güncellenemedi: ' + (data.error || 'bilinmeyen hata'));
    }

    async function refreshSnapshot(){
      state.phone = currentPhone();
      if (!state.phone){
        setStatus('Telefon numarası gerekli.');
        return;
      }
      const url = new URL('/admin/chat-lab/inspect', window.location.origin);
      url.searchParams.set('phone', state.phone);
      if (state.correlationId){
        url.searchParams.set('correlation_id', state.correlationId);
      }
      const res = await fetch(url.toString());
      const data = await res.json();
      applySnapshot(data);
      setStatus('Debug yenilendi');
    }

    function applySnapshot(payload){
      const debug = (payload && payload.debug) || {};
      state.correlationId = (payload && payload.correlation_id) || state.correlationId || '';
      byId('correlationText').textContent = 'correlation: ' + (state.correlationId || '-');
      renderMessages(((payload && payload.conversation) || {}).messages || []);
      setBadge('stateBadge', debug.conversation_state || 'GREETING', 'warn');
      setBadge('intentBadge', debug.intent || 'other', debug.intent && debug.intent !== 'other' ? 'good' : 'warn');
      setBadge('languageBadge', debug.language || 'en', 'good');
      byId('riskFlags').textContent = safeJson(debug.risk_flags || []);
      byId('escalationBlock').textContent = safeJson(debug.escalation || {});
      byId('entitiesBlock').textContent = safeJson(debug.entities || {});
      setBadge('nextStepBlock', debug.next_step || 'await_user_intent', 'good');
      byId('fullJson').textContent = safeJson(debug.full_internal_json || {});
      renderTrace((payload && payload.traces) || []);
      renderEvents('backendEvents', (payload && payload.backend_events) || [], 'Henüz backend olayı yok.');
    }

    async function sendMessage(){
      const phone = currentPhone();
      const message = (byId('messageInput').value || '').trim();
      if (!phone || !message){
        setStatus('Telefon ve mesaj gerekli.');
        return;
      }
      state.phone = phone;
      setStatus('Mesaj gönderiliyor...');
      const res = await fetch('/admin/chat-lab/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone, message }),
      });
      const data = await res.json();
      if (!res.ok || data.success === false){
        setStatus('Gönderim hatası: ' + (data.error || 'bilinmeyen hata'));
        return;
      }
      state.correlationId = data.correlation_id || '';
      byId('messageInput').value = '';
      applySnapshot(data.snapshot || {});
      setStatus('Cevap alındı: ' + ((data.chat && data.chat.status) || 'ok'));
    }

    async function resetConversation(){
      const phone = currentPhone();
      if (!phone){
        setStatus('Reset için telefon gerekli.');
        return;
      }
      state.phone = phone;
      setStatus('Konuşma sıfırlanıyor...');
      const res = await fetch('/admin/chat-lab/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone }),
      });
      const data = await res.json();
      state.correlationId = data.correlation_id || '';
      applySnapshot(data.snapshot || {});
      setStatus('Konuşma sıfırlandı');
    }

    function startAutoRefresh(){
      if (state.autoRefreshHandle){
        clearInterval(state.autoRefreshHandle);
      }
      state.autoRefreshHandle = window.setInterval(() => {
        if (!currentPhone()) return;
        refreshSnapshot().catch(() => {});
      }, 4000);
    }

    byId('messageInput').addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey){
        event.preventDefault();
        sendMessage().catch(() => {});
      }
    });

    byId('modelSelect').addEventListener('change', () => {
      changeModel().catch(() => {});
    });

    loadModels()
      .then(() => refreshSnapshot())
      .then(() => startAutoRefresh())
      .catch((error) => setStatus('Panel yükleme hatası: ' + error.message));
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


def _inject_chat_lab_link(html: str, *, active: bool = False) -> str:
    if not html or "/admin/chat-lab" in html:
        return html
    if 'class="nav-links"' not in html and 'class="nav"' not in html:
        return html
    link_style = (
        "color: #000; background: #f6c667; text-decoration: none; margin: 0 10px; "
        "padding: 10px 20px; border: 1px solid #f6c667; border-radius: 5px; "
        "display: inline-block; margin-bottom: 5px; font-weight: bold;"
        if active
        else
        "color: #f6c667; text-decoration: none; margin: 0 10px; "
        "padding: 10px 20px; border: 1px solid #f6c667; border-radius: 5px; "
        "display: inline-block; margin-bottom: 5px;"
    )
    link_html = f'<a href="/admin/chat-lab" style="{link_style}">🧪 Chat Lab</a>'

    for nav_class in ("nav-links", "nav"):
        pattern = rf'(<div class="{nav_class}"[^>]*>)(.*?)(</div>)'
        replaced, count = re.subn(
            pattern,
            lambda m: f"{m.group(1)}{m.group(2)}{link_html}{m.group(3)}",
            html,
            count=1,
            flags=re.S,
        )
        if count:
            return replaced
    return html


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

    def _session_redirect_if_needed(request: Request):
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
        return None

    @router.get("/admin", response_class=HTMLResponse)
    async def admin_panel(request: Request):
        redirect = _session_redirect_if_needed(request)
        if redirect:
            return redirect
        return HTMLResponse(_inject_chat_lab_link(admin_html), headers={"Content-Type": "text/html; charset=utf-8"})

    @router.get("/admin/root-redirect", response_class=HTMLResponse)
    async def root_redirect():
        return """<html><head><meta http-equiv="refresh" content="0; url=/admin"></head></html>"""

    @router.get("/admin/reminders-page", response_class=HTMLResponse)
    async def reminders_page(request: Request):
        redirect = _session_redirect_if_needed(request)
        if redirect:
            return redirect
        return HTMLResponse(_inject_chat_lab_link(reminder_page_html), headers={"Content-Type": "text/html; charset=utf-8"})

    @router.get("/admin/reservations-page", response_class=HTMLResponse)
    async def reservations_page(request: Request):
        redirect = _session_redirect_if_needed(request)
        if redirect:
            return redirect
        return HTMLResponse(_inject_chat_lab_link(reservations_html), headers={"Content-Type": "text/html; charset=utf-8"})

    @router.get("/admin/transfer-reservations-page", response_class=HTMLResponse)
    async def transfer_reservations_page():
        return transfer_reservations_html

    @router.get("/admin/restaurant-plan", response_class=HTMLResponse)
    async def restaurant_plan_page(request: Request):
        redirect = _session_redirect_if_needed(request)
        if redirect:
            return redirect
        return HTMLResponse(_inject_chat_lab_link(restaurant_plan_html), headers={"Content-Type": "text/html; charset=utf-8"})

    @router.get("/admin/dashboard", response_class=HTMLResponse)
    async def dashboard_page():
        return HTMLResponse(_inject_chat_lab_link(dashboard_html), headers={"Content-Type": "text/html; charset=utf-8"})

    @router.get("/admin/hotel-runtime-page", response_class=HTMLResponse)
    async def hotel_runtime_page(request: Request):
        redirect = _session_redirect_if_needed(request)
        if redirect:
            return redirect
        return HTMLResponse(_inject_chat_lab_link(HOTEL_RUNTIME_PAGE_HTML), headers={"Content-Type": "text/html; charset=utf-8"})

    @router.get("/admin/chat-lab", response_class=HTMLResponse)
    async def chat_lab_page(request: Request):
        redirect = _session_redirect_if_needed(request)
        if redirect:
            return redirect
        return HTMLResponse(ADMIN_CHAT_LAB_HTML, headers={"Content-Type": "text/html; charset=utf-8"})

    @router.get("/admin/chat-lab/inspect")
    async def inspect_chat_lab(phone: str, correlation_id: str = ""):
        clean_phone = re.sub(r"[^\d]", "", phone or "")
        if not clean_phone:
            return {"success": False, "error": "Telefon numarası gerekli."}
        snapshot = build_chat_lab_snapshot(
            conversations_dir=conversations_dir,
            phone=clean_phone,
            correlation_id=(correlation_id or "").strip(),
        )
        return {"success": True, **snapshot}

    @router.post("/admin/chat-lab/send")
    async def send_chat_lab_message(request: Request):
        try:
            body = await request.json()
        except Exception:
            return {"success": False, "error": "Geçersiz JSON body"}

        phone = re.sub(r"[^\d]", "", str(body.get("phone") or ""))
        message = str(body.get("message") or "").strip()
        if not phone:
            return {"success": False, "error": "Telefon numarası gerekli."}
        if not message:
            return {"success": False, "error": "Mesaj boş olamaz."}

        message_id = str(body.get("message_id") or f"admin-lab-{uuid4().hex[:12]}")
        requested_correlation_id = str(body.get("correlation_id") or f"admin-chat-lab-{uuid4().hex}")
        chat_payload = {
            "phone": phone,
            "message": message,
            "message_id": message_id,
        }
        response_payload: Dict[str, Any] = {}
        response_status = 500
        error_text = ""

        try:
            transport = httpx.ASGITransport(app=app_ref)
            async with httpx.AsyncClient(transport=transport, base_url="http://admin-chat-lab") as client:
                chat_resp = await client.post(
                    "/chat",
                    json=chat_payload,
                    headers={CORRELATION_HEADER: requested_correlation_id},
                )
            response_status = chat_resp.status_code
            try:
                response_payload = chat_resp.json()
            except Exception:
                response_payload = {"reply": "", "status": "error"}
                error_text = (chat_resp.text or "")[:300]
            effective_correlation_id = chat_resp.headers.get(CORRELATION_HEADER) or requested_correlation_id
        except Exception as exc:
            effective_correlation_id = requested_correlation_id
            error_text = str(exc)
            response_payload = {"reply": "", "status": "error", "reason_code": "chat_lab_proxy_failed"}

        append_chat_lab_event(
            {
                "phone": phone,
                "correlation_id": effective_correlation_id,
                "message_id": message_id,
                "message": message,
                "reply": response_payload.get("reply") or "",
                "status": response_payload.get("status") or f"http_{response_status}",
                "reason_code": response_payload.get("reason_code"),
                "error": error_text,
            }
        )
        snapshot = build_chat_lab_snapshot(
            conversations_dir=conversations_dir,
            phone=phone,
            correlation_id=effective_correlation_id,
        )
        success = response_status == 200 and not error_text
        return {
            "success": success,
            "correlation_id": effective_correlation_id,
            "chat": response_payload,
            "snapshot": snapshot,
            "error": error_text,
        }

    @router.post("/admin/chat-lab/reset")
    async def reset_chat_lab(request: Request):
        try:
            body = await request.json()
        except Exception:
            return {"success": False, "error": "Geçersiz JSON body"}

        phone = re.sub(r"[^\d]", "", str(body.get("phone") or ""))
        if not phone:
            return {"success": False, "error": "Telefon numarası gerekli."}

        correlation_id = f"admin-chat-lab-reset-{uuid4().hex[:16]}"
        purge_result = purge_phone_data(phone, hard_delete_bookings=False)
        append_chat_lab_event(
            {
                "phone": phone,
                "correlation_id": correlation_id,
                "message_id": "",
                "message": "",
                "reply": "",
                "status": "reset",
                "reason_code": "",
                "purge": purge_result,
            }
        )
        snapshot = build_chat_lab_snapshot(
            conversations_dir=conversations_dir,
            phone=phone,
            correlation_id=correlation_id,
        )
        return {
            "success": True,
            "correlation_id": correlation_id,
            "purge": purge_result,
            "snapshot": snapshot,
        }

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
        return HTMLResponse(_inject_chat_lab_link(admin_tools_html), headers={"Content-Type": "text/html; charset=utf-8"})

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
