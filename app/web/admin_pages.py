# Extracted UI templates from kassandra_openai_bot.py

ADMIN_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kassandra Bot Admin Panel</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, sans-serif; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); min-height: 100vh; color: #fff; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        h1 { text-align: center; margin-bottom: 30px; font-size: 2rem; }
        h1 span { color: #00d4ff; }
        
        .status-card { background: rgba(255,255,255,0.1); border-radius: 20px; padding: 30px; margin-bottom: 20px; backdrop-filter: blur(10px); }
        .status-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .status-indicator { display: flex; align-items: center; gap: 10px; font-size: 1.5rem; }
        .dot { width: 20px; height: 20px; border-radius: 50%; animation: pulse 2s infinite; }
        .dot.green { background: #00ff88; box-shadow: 0 0 20px #00ff88; }
        .dot.red { background: #ff4757; box-shadow: 0 0 20px #ff4757; }
        
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        
        .btn { padding: 15px 40px; border: none; border-radius: 10px; font-size: 1.1rem; cursor: pointer; transition: all 0.3s; font-weight: bold; }
        .btn-start { background: linear-gradient(135deg, #00ff88, #00d4ff); color: #1a1a2e; }
        .btn-stop { background: linear-gradient(135deg, #ff4757, #ff6b81); color: #fff; }
        .btn:hover { transform: scale(1.05); box-shadow: 0 10px 30px rgba(0,0,0,0.3); }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
        
        .settings-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-top: 20px; }
        .setting-item { background: rgba(255,255,255,0.05); padding: 20px; border-radius: 15px; }
        .setting-item label { display: block; margin-bottom: 10px; color: #aaa; }
        .setting-item input[type="number"] { width: 100%; padding: 10px; border-radius: 8px; border: 1px solid #444; background: #2a2a4a; color: #fff; font-size: 1rem; }
        
        .toggle { position: relative; width: 60px; height: 30px; }
        .toggle input { opacity: 0; width: 0; height: 0; }
        .toggle-slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background: #444; border-radius: 30px; transition: 0.3s; }
        .toggle-slider:before { position: absolute; content: ""; height: 24px; width: 24px; left: 3px; bottom: 3px; background: #fff; border-radius: 50%; transition: 0.3s; }
        .toggle input:checked + .toggle-slider { background: #00ff88; }
        .toggle input:checked + .toggle-slider:before { transform: translateX(30px); }
        
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-top: 20px; }
        .stat-box { background: rgba(255,255,255,0.05); padding: 20px; border-radius: 15px; text-align: center; }
        .stat-number { font-size: 2rem; font-weight: bold; color: #00d4ff; }
        .stat-label { color: #888; margin-top: 5px; }
        
        .blacklist-section { margin-top: 20px; }
        .blacklist-input { display: flex; gap: 10px; margin-bottom: 15px; }
        .blacklist-input input { flex: 1; padding: 12px; border-radius: 8px; border: 1px solid #444; background: #2a2a4a; color: #fff; }
        .blacklist-list { max-height: 200px; overflow-y: auto; }
        .blacklist-item { display: flex; justify-content: space-between; align-items: center; padding: 10px; background: rgba(255,255,255,0.05); border-radius: 8px; margin-bottom: 5px; }
        .blacklist-item button { background: #ff4757; border: none; color: #fff; padding: 5px 15px; border-radius: 5px; cursor: pointer; }

        .purge-input { display: flex; gap: 10px; margin-bottom: 15px; }
        .purge-input input { flex: 1; padding: 12px; border-radius: 8px; border: 1px solid #444; background: #2a2a4a; color: #fff; }
        .purge-preview { max-height: 250px; overflow-y: auto; margin-bottom: 15px; }
        .purge-item { display: flex; justify-content: space-between; align-items: center; padding: 10px; background: rgba(255,255,255,0.05); border-radius: 8px; margin-bottom: 5px; }
        .purge-item .item-name { color: #ffa502; font-weight: bold; }
        .purge-item .item-detail { color: #888; font-size: 0.85rem; }
        .purge-result { padding: 15px; border-radius: 10px; margin-top: 10px; display: none; }
        .purge-result.success { background: rgba(0,255,136,0.1); border: 1px solid #00ff88; }
        .purge-result.empty { background: rgba(255,165,2,0.1); border: 1px solid #ffa502; }

        .footer { text-align: center; margin-top: 30px; color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <div class="nav-links" style="text-align: center; margin-bottom: 20px; background: rgba(0,0,0,0.3); padding: 15px; border-radius: 10px;">
            <a href="/admin" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; text-decoration: none; margin: 0 10px; padding: 10px 20px; border: none; border-radius: 5px; display: inline-block; margin-bottom: 5px; font-weight: bold;">🏠 Ana Sayfa</a>
            <a href="/admin/dashboard" style="color: #00d4ff; text-decoration: none; margin: 0 10px; padding: 10px 20px; border: 1px solid #00d4ff; border-radius: 5px; display: inline-block; margin-bottom: 5px;">📊 Dashboard</a>
            <a href="/admin/reservations-page" style="color: #00d4ff; text-decoration: none; margin: 0 10px; padding: 10px 20px; border: 1px solid #00d4ff; border-radius: 5px; display: inline-block; margin-bottom: 5px;">🍽️ Rezervasyonlar</a>
            <a href="/admin/hotel-bookings-page" style="color: #00d4ff; text-decoration: none; margin: 0 10px; padding: 10px 20px; border: 1px solid #00d4ff; border-radius: 5px; display: inline-block; margin-bottom: 5px;">🏨 Otel Rez.</a>
            <a href="/admin/transfer-reservations-page" style="color: #00d4ff; text-decoration: none; margin: 0 10px; padding: 10px 20px; border: 1px solid #00d4ff; border-radius: 5px; display: inline-block; margin-bottom: 5px;">🚐 Transfer Rez.</a>
            <a href="/admin/restaurant-plan" style="color: #00d4ff; text-decoration: none; margin: 0 10px; padding: 10px 20px; border: 1px solid #00d4ff; border-radius: 5px; display: inline-block; margin-bottom: 5px;">🗺️ Restoran Planı</a>
            <a href="/admin/reminders-page" style="color: #00d4ff; text-decoration: none; margin: 0 10px; padding: 10px 20px; border: 1px solid #00d4ff; border-radius: 5px; display: inline-block; margin-bottom: 5px;">📅 Hatırlatmalar</a>
            <a href="/admin/qa/stats" style="color: #00d4ff; text-decoration: none; margin: 0 10px; padding: 10px 20px; border: 1px solid #00d4ff; border-radius: 5px; display: inline-block; margin-bottom: 5px;">🔍 QA Stats</a>
            <a href="/admin/tools" style="color: #00d4ff; text-decoration: none; margin: 0 10px; padding: 10px 20px; border: 1px solid #00d4ff; border-radius: 5px; display: inline-block; margin-bottom: 5px;">⚙️ Araçlar</a>
            <a href="/admin/users-page" style="color: #ffa502; text-decoration: none; margin: 0 10px; padding: 10px 20px; border: 1px solid #ffa502; border-radius: 5px; display: inline-block; margin-bottom: 5px;">👥 Kullanıcılar</a>
            <a href="/admin/logout" style="color: #ff4757; text-decoration: none; margin: 0 10px; padding: 10px 20px; border: 1px solid #ff4757; border-radius: 5px; display: inline-block; margin-bottom: 5px;">🚪 Çıkış</a>
        </div>
        <h1>🏨 Kassandra <span>Bot Admin</span></h1>
        
        <!-- Ana Kontrol -->
        <div class="status-card">
            <div class="status-header">
                <div class="status-indicator">
                    <div class="dot" id="statusDot"></div>
                    <span id="statusText">Yükleniyor...</span>
                </div>
                <button class="btn" id="mainBtn" onclick="toggleAutomation()">Yükleniyor...</button>
            </div>
            
            <div class="stats">
                <div class="stat-box">
                    <div class="stat-number" id="convCount">-</div>
                    <div class="stat-label">Toplam Konuşma</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number" id="blacklistCount">-</div>
                    <div class="stat-label">Kara Liste</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number" id="followupMin">-</div>
                    <div class="stat-label">Follow-up (dk)</div>
                </div>
            </div>
        </div>
        
        <!-- 📊 Günlük Metrikler -->
        <div class="status-card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <h2>📊 Günlük Metrikler</h2>
                <span id="metricsDate" style="color: #888;">-</span>
            </div>
            <div class="stats">
                <div class="stat-box">
                    <div class="stat-number" id="totalMessages">-</div>
                    <div class="stat-label">Toplam Mesaj</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number" style="color: #00ff88;" id="localResponses">-</div>
                    <div class="stat-label">LOCAL (%<span id="localPct">0</span>)</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number" style="color: #00d4ff;" id="openaiResponses">-</div>
                    <div class="stat-label">OpenAI (%<span id="openaiPct">0</span>)</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number" style="color: #ffa502;" id="handoffCount">-</div>
                    <div class="stat-label">İnsana Devir</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number" style="color: #ff4757;" id="errorCount">-</div>
                    <div class="stat-label">Hata</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number" id="avgTime">-</div>
                    <div class="stat-label">Ort. Süre (sn)</div>
                </div>
            </div>
            <div style="margin-top: 15px; text-align: center;">
                <button class="btn btn-start" onclick="sendDailyReport()" style="padding: 10px 20px; font-size: 0.9rem;">📤 Raporu Gönder</button>
            </div>
        </div>
        
        <!-- 🧪 Pytest Test Sistemi -->
        <div class="status-card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <h2>🧪 Test Sistemi (pytest)</h2>
                <span id="lastTestTime" style="color: #888;">Son test: -</span>
            </div>
            <div style="display: flex; gap: 10px; align-items: center; margin-bottom: 15px;">
                <div id="testStatusIcon" style="font-size: 2rem;">⏳</div>
                <div>
                    <div id="testStatusText" style="font-size: 1.2rem; font-weight: bold;">Henüz test yapılmadı</div>
                    <div id="testSummary" style="color: #888; font-size: 0.9rem;">-</div>
                </div>
            </div>
            
            <!-- Test Sonuçları -->
            <div id="testResults" style="max-height: 200px; overflow-y: auto; margin-bottom: 15px; background: rgba(0,0,0,0.2); border-radius: 10px; padding: 10px;"></div>
            
            <!-- Test Butonları -->
            <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 15px;">
                <button class="btn btn-start" onclick="runPytest('all')" style="padding: 10px 20px; font-size: 0.9rem;">▶️ Tüm Testler</button>
                <button class="btn" onclick="runPytest('unit')" style="padding: 10px 20px; font-size: 0.9rem; background: #5352ed;">📦 Unit</button>
                <button class="btn" onclick="runPytest('integration')" style="padding: 10px 20px; font-size: 0.9rem; background: #ffa502; color: #000;">🔗 Integration</button>
                <button class="btn" onclick="runPytest('e2e')" style="padding: 10px 20px; font-size: 0.9rem; background: #ff6b81;">🎯 E2E</button>
            </div>
            
            <!-- Test Çıktısı -->
            <details style="background: rgba(0,0,0,0.2); border-radius: 10px; padding: 10px;">
                <summary style="cursor: pointer; color: #888;">📋 Detaylı Çıktı</summary>
                <pre id="testOutput" style="max-height: 300px; overflow: auto; font-size: 0.8rem; margin-top: 10px; white-space: pre-wrap; color: #aaa;"></pre>
            </details>
        </div>
        
        <!-- Ayarlar -->
        <div class="status-card">
            <h2 style="margin-bottom: 20px;">⚙️ Ayarlar</h2>
            <div class="settings-grid">
                <div class="setting-item">
                    <label>Follow-up Mesajı</label>
                    <div style="display: flex; align-items: center; justify-content: space-between;">
                        <span id="followupStatus">Açık</span>
                        <label class="toggle">
                            <input type="checkbox" id="followupToggle" onchange="toggleFollowup()">
                            <span class="toggle-slider"></span>
                        </label>
                    </div>
                </div>
                <div class="setting-item">
                    <label>Operasyon Kural Motoru</label>
                    <div style="display: flex; align-items: center; justify-content: space-between;">
                        <span id="operationalRulesStatus">Açık</span>
                        <label class="toggle">
                            <input type="checkbox" id="operationalRulesToggle" onchange="toggleOperationalRules()">
                            <span class="toggle-slider"></span>
                        </label>
                    </div>
                    <div id="operationalRulesHint" style="margin-top:8px; color:#9aa3b2; font-size:0.85rem;">
                        Açıksa: Standart operasyon sorularına hızlı/prosedürel yanıt verir. Kapalıysa: Normal AI akışı kullanılır.
                    </div>
                </div>
                <div class="setting-item">
                    <label>Follow-up Süresi (dakika)</label>
                    <input type="number" id="followupMinutes" value="10" min="1" max="60" onchange="updateFollowupMinutes()">
                </div>
                <div class="setting-item">
                    <label>Oturum Süresi (saat)</label>
                    <input type="number" id="sessionDurationHours" value="24" min="1" max="720" onchange="updateSessionDurationHours()">
                </div>
                <div class="setting-item">
                    <label>Son Follow-up Döngüsü</label>
                    <div style="font-size: 0.95rem; color: #ddd; line-height: 1.8;">
                        <div>Uyarı gönderildi: <strong id="followupLastSent">0</strong></div>
                        <div>Otomatik kapatıldı: <strong id="followupLastClosed">0</strong></div>
                    </div>
                </div>
                <div class="setting-item">
                    <label>Sessiz Oda (Bot Otomatik)</label>
                    <select id="quietAutoRoomKeys" multiple size="7" style="width:100%; padding:8px; border-radius:8px; border:1px solid #444; background:#2a2a4a; color:#fff;">
                        <option value="deluxe">deluxe</option>
                        <option value="superior">superior</option>
                        <option value="exclusiveLand">exclusiveLand</option>
                        <option value="exclusivePool">exclusivePool</option>
                        <option value="penthouseLand">penthouseLand</option>
                        <option value="penthouse">penthouse</option>
                        <option value="premium">premium</option>
                    </select>
                </div>
                <div class="setting-item">
                    <label>Sessiz Oda (Canlı Temsilci)</label>
                    <select id="quietHandoffRoomKeys" multiple size="7" style="width:100%; padding:8px; border-radius:8px; border:1px solid #444; background:#2a2a4a; color:#fff;">
                        <option value="deluxe">deluxe</option>
                        <option value="superior">superior</option>
                        <option value="exclusiveLand">exclusiveLand</option>
                        <option value="exclusivePool">exclusivePool</option>
                        <option value="penthouseLand">penthouseLand</option>
                        <option value="penthouse">penthouse</option>
                        <option value="premium">premium</option>
                    </select>
                </div>
                <div class="setting-item">
                    <label>Standart Oda (Fiyat Filtre)</label>
                    <select id="standardRoomKeys" multiple size="7" style="width:100%; padding:8px; border-radius:8px; border:1px solid #444; background:#2a2a4a; color:#fff;">
                        <option value="deluxe">deluxe</option>
                        <option value="superior">superior</option>
                        <option value="exclusiveLand">exclusiveLand</option>
                        <option value="exclusivePool">exclusivePool</option>
                        <option value="penthouseLand">penthouseLand</option>
                        <option value="penthouse">penthouse</option>
                        <option value="premium">premium</option>
                    </select>
                </div>
                <div class="setting-item">
                    <label>Oda Kuralı Güncelle</label>
                    <button class="btn" onclick="updateQuietRoomPolicy()" style="padding: 10px 18px; background: #5352ed;">Kaydet</button>
                </div>
                <div class="setting-item">
                    <label>Fiyat Para Birimleri (Aktif/Pasif)</label>
                    <div style="display:grid; grid-template-columns: repeat(2,minmax(90px,1fr)); gap:8px; margin-bottom:10px;">
                        <label style="display:flex;align-items:center;gap:8px;"><input type="checkbox" id="currencyToggleEUR" checked> EUR</label>
                        <label style="display:flex;align-items:center;gap:8px;"><input type="checkbox" id="currencyToggleUSD" checked> USD</label>
                        <label style="display:flex;align-items:center;gap:8px;"><input type="checkbox" id="currencyToggleTRY" checked> TRY</label>
                        <label style="display:flex;align-items:center;gap:8px;"><input type="checkbox" id="currencyToggleGBP" checked> GBP</label>
                    </div>
                    <button class="btn" onclick="updateCurrencyPolicy()" style="padding: 10px 18px; background: #00a8ff;">Para Birimlerini Kaydet</button>
                </div>
            </div>
        </div>
        
        <!-- 🤖 OpenAI Model Seçimi -->
        <div class="status-card">
            <h2 style="margin-bottom: 20px;">🤖 OpenAI Model Seçimi</h2>
            <p style="color: #888; margin-bottom: 15px; font-size: 0.9rem;">Botun kullandığı OpenAI modelini buradan değiştirebilirsiniz. Değişiklik anında uygulanır.</p>

            <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 20px; flex-wrap: wrap;">
                <div style="flex: 1; min-width: 250px;">
                    <label style="display: block; margin-bottom: 8px; color: #aaa; font-size: 0.9rem;">Aktif Model</label>
                    <select id="modelSelect" style="width: 100%; padding: 12px; border-radius: 8px; border: 1px solid #444; background: #2a2a4a; color: #fff; font-size: 1rem;">
                        <optgroup label="GPT-4o Serisi">
                            <option value="gpt-4o-mini">gpt-4o-mini (Hızlı & Ekonomik)</option>
                            <option value="gpt-4o">gpt-4o (Güçlü)</option>
                        </optgroup>
                        <optgroup label="GPT-4.1 Serisi">
                            <option value="gpt-4.1-nano">gpt-4.1-nano (En Hızlı)</option>
                            <option value="gpt-4.1-mini">gpt-4.1-mini (Dengeli)</option>
                            <option value="gpt-4.1">gpt-4.1 (En Güçlü 4.1)</option>
                        </optgroup>
                        <optgroup label="GPT-5.1 Serisi">
                            <option value="gpt-5.1-nano">gpt-5.1-nano (Ekonomik)</option>
                            <option value="gpt-5.1-mini">gpt-5.1-mini (Dengeli)</option>
                            <option value="gpt-5.1">gpt-5.1 (Güçlü)</option>
                        </optgroup>
                        <optgroup label="GPT-5.2 Serisi">
                            <option value="gpt-5.2-nano">gpt-5.2-nano (Ekonomik)</option>
                            <option value="gpt-5.2-mini">gpt-5.2-mini (Dengeli)</option>
                            <option value="gpt-5.2">gpt-5.2 (En Güçlü)</option>
                        </optgroup>
                        <optgroup label="o3 Serisi">
                            <option value="o3-mini">o3-mini (Akıl Yürütme)</option>
                        </optgroup>
                    </select>
                </div>
                <button class="btn btn-start" onclick="changeModel()" style="padding: 12px 30px; margin-top: 20px;" id="modelBtn">Değiştir</button>
            </div>

            <div id="modelInfo" style="display: flex; gap: 15px; flex-wrap: wrap;">
                <div style="flex: 1; min-width: 200px; background: rgba(255,255,255,0.05); padding: 15px; border-radius: 10px;">
                    <div style="color: #888; font-size: 0.85rem;">Aktif Model</div>
                    <div id="currentModelName" style="font-size: 1.3rem; font-weight: bold; color: #00d4ff; margin-top: 5px;">Yükleniyor...</div>
                </div>
                <div style="flex: 1; min-width: 200px; background: rgba(255,255,255,0.05); padding: 15px; border-radius: 10px;">
                    <div style="color: #888; font-size: 0.85rem;">Son Değişiklik</div>
                    <div id="modelChangedAt" style="font-size: 1rem; color: #ffa502; margin-top: 5px;">-</div>
                </div>
                <div style="flex: 1; min-width: 200px; background: rgba(255,255,255,0.05); padding: 15px; border-radius: 10px;">
                    <div style="color: #888; font-size: 0.85rem;">Değiştiren</div>
                    <div id="modelChangedBy" style="font-size: 1rem; color: #aaa; margin-top: 5px;">-</div>
                </div>
            </div>

            <div id="modelResult" class="purge-result" style="display: none; margin-top: 15px;"></div>
        </div>

        <!-- Kara Liste -->
        <div class="status-card">
            <h2 style="margin-bottom: 20px;">🚫 Kara Liste</h2>
            <div class="blacklist-input">
                <input type="text" id="blacklistPhone" placeholder="Telefon numarası (örn: 905551234567)">
                <button class="btn btn-stop" onclick="addBlacklist()" style="padding: 12px 25px;">Ekle</button>
            </div>
            <div class="blacklist-list" id="blacklistList"></div>
        </div>

        <!-- Aktif Konuşmalar -->
        <div class="status-card">
            <h2 style="margin-bottom: 20px;">💬 Aktif Konuşmalar (Son 30 dk)</h2>
            <div style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom: 15px;">
                <button class="btn btn-start" onclick="loadActiveConversations()" style="padding: 10px 16px;">🔄 Yenile</button>
                <button class="btn btn-warning" onclick="purgeAllActiveConversationsHome()" style="padding: 10px 16px;">🧹 Tüm Konuşmaları Sıfırla</button>
                <button class="btn btn-warning" onclick="purgeSelectedActiveConversationsHome()" style="padding: 10px 16px;">🧹 Seçili Konuşmalara Sıfırla</button>
                <button class="btn btn-stop" onclick="blacklistAllActiveConversationsHome()" style="padding: 10px 16px;">🚫 Tüm Konuşmaları KARA LİSTEYE EKLE</button>
                <button class="btn btn-stop" onclick="blacklistSelectedActiveConversationsHome()" style="padding: 10px 16px;">🚫 Seçili Konuşmaları Kara Listeye</button>
                <button class="btn" onclick="selectAllActiveConversationsHome()" style="padding: 10px 16px;">☑️ Tümünü Seç</button>
                <button class="btn" onclick="clearActiveSelectionHome()" style="padding: 10px 16px;">⬜ Seçimi Temizle</button>
            </div>
            <div id="activeSelectionInfoHome" style="color:#aab; font-size:0.9rem; margin-bottom:10px;">Seçili: 0</div>
            <div id="activeConversationsHome">Yükleniyor...</div>
        </div>

        <!-- Konuşma Sıfırlama -->
        <div class="status-card">
            <h2 style="margin-bottom: 20px;">🧹 Konuşma Sıfırlama</h2>
            <p style="color: #888; margin-bottom: 15px; font-size: 0.9rem;">Telefon numarasına ait tüm verileri (konuşma, fiyat akışı, rezervasyon akışı, follow-up, hatırlatma vb.) temizleyerek sıfırdan konuşma başlatır.</p>
            <div class="purge-input">
                <input type="text" id="purgePhone" placeholder="Telefon numarası (örn: 905551234567)">
                <button class="btn" onclick="purgePreview()" style="padding: 12px 25px; background: linear-gradient(135deg, #ffa502, #ff6348);">Önizle</button>
                <button class="btn btn-stop" onclick="purgeExecute()" style="padding: 12px 25px;" id="purgeBtn" disabled>Sıfırla</button>
            </div>
            <div class="purge-preview" id="purgePreview"></div>
            <div class="purge-result" id="purgeResult"></div>
        </div>

        <!-- Gelişmiş Ayarlar & Rezervasyonlar Butonları -->
        <div style="text-align: center; margin: 30px 0; display: flex; gap: 15px; justify-content: center; flex-wrap: wrap;">
            <a href="/admin/tools" class="btn" style="background: linear-gradient(135deg, #5352ed, #3742fa); padding: 15px 40px; text-decoration: none; display: inline-block;">
                🔧 Gelişmiş Ayarlar & Araçlar
            </a>
            <a href="/admin/reservations-page" class="btn" style="background: linear-gradient(135deg, #ff6b6b, #ee5a24); padding: 15px 40px; text-decoration: none; display: inline-block;">
                🍽️ Restoran Rezervasyonları
            <a href="/admin/restaurant-plan" class="btn" style="background: linear-gradient(135deg, #2ed573, #1e90ff); padding: 15px 40px; text-decoration: none; display: inline-block;">
                🗺️ Masa Planı (Sürükle-Bırak)
            </a>
            </a>
        </div>
        
        <div class="footer">
            <p>Kassandra Ölüdeniz © 2024</p>
            <p style="font-size: 0.8rem; margin-top: 5px;">Otomasyon Yöneticisi: Ömer Alperen Gönen</p>
        </div>
    </div>
    
    <script>
        const API = '';
        
        async function loadStatus() {
            try {
                const res = await fetch(API + '/automation/status');
                const data = await res.json();
                updateUI(data.automation_enabled, data.followup_enabled);
            } catch(e) {
                console.error(e);
            }
        }
        
        async function loadSettings() {
            try {
                const res = await fetch(API + '/settings');
                const data = await res.json();
                document.getElementById('followupMinutes').value = data.followup_minutes || 10;
                document.getElementById('followupMin').textContent = data.followup_minutes || 10;
                document.getElementById('sessionDurationHours').value = data.session_duration_hours || 24;
                document.getElementById('followupToggle').checked = data.followup_enabled;
                document.getElementById('operationalRulesToggle').checked = data.operational_rules_enabled !== false;
                document.getElementById('operationalRulesStatus').textContent = (data.operational_rules_enabled !== false) ? 'Açık' : 'Kapalı';
                updateOperationalRulesHint(data.operational_rules_enabled !== false);
                setMultiSelectValues('quietAutoRoomKeys', data.quiet_auto_room_keys || ['deluxe','premium']);
                setMultiSelectValues('quietHandoffRoomKeys', data.quiet_handoff_room_keys || ['superior']);
                setMultiSelectValues('standardRoomKeys', data.standard_room_keys || ['deluxe','superior']);
                setCurrencyToggleValues(data.currency_enabled || { EUR: true, USD: true, TRY: true, GBP: true });

                const fr = await fetch(API + '/admin/followups/pending');
                const fd = await fr.json();
                const cycle = fd.last_cycle || {};
                document.getElementById('followupLastSent').textContent = cycle.sent || 0;
                document.getElementById('followupLastClosed').textContent = cycle.closed || 0;
            } catch(e) {}
        }
        
        async function loadStats() {
            try {
                const convRes = await fetch(API + '/conversations');
                const convData = await convRes.json();
                document.getElementById('convCount').textContent = convData.conversations?.length || 0;
                
                const blRes = await fetch(API + '/blacklist');
                const blData = await blRes.json();
                document.getElementById('blacklistCount').textContent = blData.blacklist?.length || 0;
                renderBlacklist(blData.blacklist || []);
            } catch(e) {}
        }
        
        function updateUI(enabled, followupEnabled) {
            const dot = document.getElementById('statusDot');
            const text = document.getElementById('statusText');
            const btn = document.getElementById('mainBtn');
            
            if (enabled) {
                dot.className = 'dot green';
                text.textContent = 'Otomasyon Açık';
                btn.textContent = 'DURDUR';
                btn.className = 'btn btn-stop';
            } else {
                dot.className = 'dot red';
                text.textContent = 'Otomasyon Kapalı';
                btn.textContent = 'BAŞLAT';
                btn.className = 'btn btn-start';
            }
            
            document.getElementById('followupToggle').checked = followupEnabled;
            document.getElementById('followupStatus').textContent = followupEnabled ? 'Açık' : 'Kapalı';
        }
        
        async function toggleAutomation() {
            const btn = document.getElementById('mainBtn');
            const isRunning = btn.textContent === 'DURDUR';
            
            btn.disabled = true;
            try {
                const endpoint = isRunning ? '/automation/stop' : '/automation/start';
                await fetch(API + endpoint, { method: 'POST' });
                await loadStatus();
            } catch(e) {
                alert('Hata: ' + e.message);
            }
            btn.disabled = false;
        }
        
        async function toggleFollowup() {
            const enabled = document.getElementById('followupToggle').checked;
            await fetch(API + '/settings?followup_enabled=' + enabled, { method: 'POST' });
            document.getElementById('followupStatus').textContent = enabled ? 'Açık' : 'Kapalı';
        }

        async function toggleOperationalRules() {
            const enabled = document.getElementById('operationalRulesToggle').checked;
            await fetch(API + '/settings?operational_rules_enabled=' + enabled, { method: 'POST' });
            document.getElementById('operationalRulesStatus').textContent = enabled ? 'Açık' : 'Kapalı';
            updateOperationalRulesHint(enabled);
        }

        function updateOperationalRulesHint(enabled) {
            const el = document.getElementById('operationalRulesHint');
            if (!el) return;
            if (enabled) {
                el.textContent = 'Açık: Bazı rezervasyon/iptal/değişiklik sorularını bekletmeden, standart prosedürle otomatik yönetir.';
            } else {
                el.textContent = 'Kapalı: Bu özel operasyon kuralları devre dışıdır; mesajlar normal AI akışıyla yanıtlanır.';
            }
        }
        
        async function updateFollowupMinutes() {
            const mins = document.getElementById('followupMinutes').value;
            await fetch(API + '/settings?followup_minutes=' + mins, { method: 'POST' });
            document.getElementById('followupMin').textContent = mins;
        }

        async function updateSessionDurationHours() {
            const hours = document.getElementById('sessionDurationHours').value;
            const res = await fetch(API + '/settings?session_duration_hours=' + hours, { method: 'POST' });
            const data = await res.json();
            if (data && data.success === false) {
                alert('Oturum süresi güncellenemedi: ' + (data.error || 'Bilinmeyen hata'));
                await loadSettings();
            }
        }

        async function updateQuietRoomPolicy() {
            const autoKeys = encodeURIComponent(getMultiSelectValues('quietAutoRoomKeys').join(','));
            const handoffKeys = encodeURIComponent(getMultiSelectValues('quietHandoffRoomKeys').join(','));
            const standardKeys = encodeURIComponent(getMultiSelectValues('standardRoomKeys').join(','));
            const res = await fetch(
                API + '/settings?quiet_auto_room_keys=' + autoKeys + '&quiet_handoff_room_keys=' + handoffKeys + '&standard_room_keys=' + standardKeys,
                { method: 'POST' }
            );
            const data = await res.json();
            if (data && data.success === false) {
                alert('Kural kaydedilemedi: ' + (data.error || 'Bilinmeyen hata'));
                return;
            }
            alert('Oda politikaları güncellendi');
        }

        function setCurrencyToggleValues(policy) {
            const p = policy || {};
            document.getElementById('currencyToggleEUR').checked = (p.EUR !== false);
            document.getElementById('currencyToggleUSD').checked = (p.USD !== false);
            document.getElementById('currencyToggleTRY').checked = (p.TRY !== false);
            document.getElementById('currencyToggleGBP').checked = (p.GBP !== false);
        }

        async function updateCurrencyPolicy() {
            const policy = {
                EUR: !!document.getElementById('currencyToggleEUR').checked,
                USD: !!document.getElementById('currencyToggleUSD').checked,
                TRY: !!document.getElementById('currencyToggleTRY').checked,
                GBP: !!document.getElementById('currencyToggleGBP').checked,
            };
            const payload = encodeURIComponent(JSON.stringify(policy));
            const res = await fetch(API + '/settings?currency_enabled_json=' + payload, { method: 'POST' });
            const data = await res.json();
            if (data && data.success === false) {
                alert('Para birimi politikası kaydedilemedi: ' + (data.error || 'Bilinmeyen hata'));
                return;
            }
            alert('Para birimi politikası güncellendi');
        }

        function getMultiSelectValues(id) {
            const el = document.getElementById(id);
            return Array.from(el.selectedOptions || []).map(o => o.value);
        }

        function setMultiSelectValues(id, values) {
            const valSet = new Set(values || []);
            const el = document.getElementById(id);
            Array.from(el.options || []).forEach(opt => {
                opt.selected = valSet.has(opt.value);
            });
        }
        
        async function addBlacklist() {
            const phone = document.getElementById('blacklistPhone').value.trim();
            if (!phone) return alert('Telefon numarası girin');
            await fetch(API + '/blacklist/add/' + phone, { method: 'POST' });
            document.getElementById('blacklistPhone').value = '';
            loadStats();
        }
        
        async function removeBlacklist(phone) {
            await fetch(API + '/blacklist/remove/' + phone, { method: 'POST' });
            loadStats();
        }

        async function addConversationToBlacklist(phone) {
            if (!phone) return;
            if (!confirm(phone + ' numarası kara listeye eklensin mi?')) return;
            await fetch(API + '/blacklist/add/' + phone, { method: 'POST' });
            await loadStats();
            await loadActiveConversations();
        }
        
        function renderBlacklist(list) {
            const container = document.getElementById('blacklistList');
            container.innerHTML = list.map(phone => `
                <div class="blacklist-item">
                    <span>${phone}</span>
                    <button onclick="removeBlacklist('${phone}')">Kaldır</button>
                </div>
            `).join('');
        }

        let activeConversationPhonesHome = [];
        const selectedActivePhonesHome = new Set();

        function updateActiveSelectionInfoHome() {
            const el = document.getElementById('activeSelectionInfoHome');
            if (el) el.textContent = 'Seçili: ' + selectedActivePhonesHome.size;
        }

        function toggleActiveConversationSelectionHome(phone, checked) {
            const key = String(phone || '').trim();
            if (!key) return;
            if (checked) selectedActivePhonesHome.add(key);
            else selectedActivePhonesHome.delete(key);
            updateActiveSelectionInfoHome();
        }

        function selectAllActiveConversationsHome() {
            activeConversationPhonesHome.forEach(phone => selectedActivePhonesHome.add(phone));
            updateActiveSelectionInfoHome();
            loadActiveConversations();
        }

        function clearActiveSelectionHome() {
            selectedActivePhonesHome.clear();
            updateActiveSelectionInfoHome();
            loadActiveConversations();
        }

        async function runBulkActionOnConversationsHome(phones, action) {
            const actionLabel = action === 'purge' ? 'konuşma sıfırlama' : 'kara listeye ekleme';
            const endpointBase = action === 'purge' ? '/purge/' : '/blacklist/add/';
            const uniquePhones = Array.from(new Set((phones || []).map(p => String(p || '').trim()).filter(Boolean)));
            if (!uniquePhones.length) {
                alert('İşlem yapılacak konuşma yok.');
                return;
            }
            if (!confirm(uniquePhones.length + ' konuşma için ' + actionLabel + ' işlemi yapılsın mı?')) return;

            const failed = [];
            await Promise.all(uniquePhones.map(async (phone) => {
                try {
                    const res = await fetch(API + endpointBase + phone, { method: 'POST' });
                    if (action === 'purge') {
                        const data = await res.json();
                        if (!(res.ok && data && data.success)) {
                            failed.push(phone);
                        }
                        return;
                    }
                    if (!res.ok) failed.push(phone);
                } catch (e) {
                    failed.push(phone);
                }
            }));

            const okCount = uniquePhones.length - failed.length;
            if (failed.length) {
                alert('İşlem tamamlandı. Başarılı: ' + okCount + ', Başarısız: ' + failed.length + '\\nBaşarısız numaralar: ' + failed.join(', '));
            } else {
                alert('İşlem tamamlandı. Toplam: ' + okCount);
            }

            failed.forEach(phone => selectedActivePhonesHome.delete(phone));
            await loadStats();
            await loadActiveConversations();
        }

        async function purgeAllActiveConversationsHome() {
            await runBulkActionOnConversationsHome(activeConversationPhonesHome, 'purge');
        }

        async function purgeSelectedActiveConversationsHome() {
            await runBulkActionOnConversationsHome(Array.from(selectedActivePhonesHome), 'purge');
        }

        async function blacklistAllActiveConversationsHome() {
            await runBulkActionOnConversationsHome(activeConversationPhonesHome, 'blacklist');
        }

        async function blacklistSelectedActiveConversationsHome() {
            await runBulkActionOnConversationsHome(Array.from(selectedActivePhonesHome), 'blacklist');
        }

        async function loadActiveConversations() {
            const container = document.getElementById('activeConversationsHome');
            if (!container) return;
            container.innerHTML = 'Yükleniyor...';
            try {
                const res = await fetch(API + '/admin/active-conversations');
                const data = await res.json();
                const items = Array.isArray(data.conversations) ? data.conversations : [];
                activeConversationPhonesHome = items
                    .map(c => String((c && c.phone) || '').trim())
                    .filter(Boolean);
                const currentPhones = new Set(activeConversationPhonesHome);
                Array.from(selectedActivePhonesHome).forEach((phone) => {
                    if (!currentPhones.has(phone)) selectedActivePhonesHome.delete(phone);
                });
                updateActiveSelectionInfoHome();
                if (!items.length) {
                    container.innerHTML = '<p style="color:#888;">Son 30 dakikada aktif konuşma yok.</p>';
                    return;
                }
                container.innerHTML = items.map(c => {
                    const phone = String((c && c.phone) || '').trim();
                    const selected = selectedActivePhonesHome.has(phone);
                    const pauseReason = String((c && c.paused_reason) || '').trim();
                    const pausedMinutes = Number.isFinite(Number(c && c.paused_minutes)) ? Number(c.paused_minutes) : null;
                    const pauseMeta = c.is_paused
                        ? `<div style="margin-top:6px;color:#ffb4b4;font-size:0.82rem;">Pause nedeni: ${pauseReason || 'belirtilmedi'}${pausedMinutes !== null ? ` • ${pausedMinutes} dk` : ''}</div>`
                        : '';
                    const pauseAlert = c.is_paused
                        ? `<div style="margin-top:10px;padding:8px 10px;border:1px solid #ff6b6b;background:rgba(255,107,107,0.12);border-radius:8px;color:#ffdede;font-size:0.84rem;">
                                Bu sohbet duraklatılmış. Bot cevap vermez.
                                <button class="btn btn-success" onclick="togglePause('${phone}', true)" style="margin-left:8px;padding:4px 8px;">▶️ Resume</button>
                           </div>`
                        : '';
                    return `
                        <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;padding:12px;background:rgba(255,255,255,0.05);border-radius:10px;margin-bottom:8px;">
                            <div style="min-width:0;">
                                <div style="display:flex;align-items:center;gap:8px;">
                                    <label style="display:flex;align-items:center;gap:6px;color:#aab;font-size:0.85rem;cursor:pointer;">
                                        <input type="checkbox" ${selected ? 'checked' : ''} onchange="toggleActiveConversationSelectionHome('${phone}', this.checked)">
                                        Seç
                                    </label>
                                    <div style="font-weight:700;color:#00d4ff;">${phone || '-'}</div>
                                </div>
                                <div style="color:#aab; font-size:0.9rem; margin-top:4px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${c.last_message || 'Mesaj yok'}</div>
                                <div style="color:#778; font-size:0.8rem; margin-top:4px;">${c.minutes_ago || 0} dk önce • ${c.message_count || 0} mesaj • Dil: ${(c.language_lock || 'en').toUpperCase()}</div>
                                ${pauseMeta}
                                ${pauseAlert}
                            </div>
                            <div style="display:flex;gap:8px;flex-shrink:0;">
                                <span class="status-badge ${c.is_paused ? 'paused' : 'active'}">${c.is_paused ? 'Durduruldu' : 'Aktif'}</span>
                                <button class="btn btn-warning" onclick="purgeConversationByPhone('${phone}')" style="padding:8px 12px;">🧹 Konuşmayı Sıfırla</button>
                                <button class="btn btn-stop" onclick="addConversationToBlacklist('${phone}')" style="padding:8px 12px;">🚫 Kara Listeye Ekle</button>
                            </div>
                        </div>
                    `;
                }).join('');
            } catch (e) {
                container.innerHTML = 'Hata: ' + e.message;
            }
        }

        async function purgeConversationByPhone(phone) {
            if (!phone) return;
            if (!confirm(phone + ' numarasının konuşması sıfırlansın mı?')) return;
            try {
                const res = await fetch(API + '/purge/' + phone, { method: 'POST' });
                const data = await res.json();
                if (data && data.success) {
                    alert('Konuşma sıfırlandı: ' + phone);
                } else {
                    alert('Sıfırlama başarısız: ' + ((data && (data.error || data.detail)) || 'Bilinmeyen hata'));
                }
            } catch (e) {
                alert('Sıfırlama hatası: ' + e.message);
            }
            await loadActiveConversations();
        }

        // 🤖 OpenAI Model Değiştirme fonksiyonları
        async function loadCurrentModel() {
            try {
                const res = await fetch(API + '/admin/model');
                const data = await res.json();
                document.getElementById('currentModelName').textContent = data.current_model || '-';
                document.getElementById('modelSelect').value = data.current_model || '';
                if (data.changed_at) {
                    document.getElementById('modelChangedAt').textContent = data.changed_at;
                }
                if (data.changed_by) {
                    document.getElementById('modelChangedBy').textContent = data.changed_by;
                }
            } catch(e) {
                document.getElementById('currentModelName').textContent = 'Hata!';
                console.error('Model yükleme hatası:', e);
            }
        }

        async function changeModel() {
            const select = document.getElementById('modelSelect');
            const newModel = select.value;
            const currentModel = document.getElementById('currentModelName').textContent;

            if (newModel === currentModel) {
                alert('Seçilen model zaten aktif!');
                return;
            }

            if (!confirm('Model "' + currentModel + '" → "' + newModel + '" olarak değiştirilecek.\\n\\nEmin misiniz?')) return;

            const btn = document.getElementById('modelBtn');
            const result = document.getElementById('modelResult');
            btn.disabled = true;
            btn.textContent = 'Değiştiriliyor...';

            try {
                const res = await fetch(API + '/admin/model', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ model: newModel })
                });
                const data = await res.json();

                if (data.success) {
                    result.className = 'purge-result success';
                    result.innerHTML = '✅ Model değiştirildi: <strong>' + data.old_model + '</strong> → <strong>' + data.new_model + '</strong>';
                    result.style.display = 'block';
                    loadCurrentModel();
                } else {
                    result.className = 'purge-result empty';
                    result.innerHTML = '❌ Hata: ' + (data.error || 'Bilinmeyen hata');
                    result.style.display = 'block';
                }
            } catch(e) {
                result.className = 'purge-result empty';
                result.innerHTML = '❌ Hata: ' + e.message;
                result.style.display = 'block';
            }

            btn.disabled = false;
            btn.textContent = 'Değiştir';
            setTimeout(() => { result.style.display = 'none'; }, 5000);
        }

        // 🧹 Konuşma Sıfırlama fonksiyonları
        let purgePhoneReady = '';

        const purgeLabels = {
            conversation: 'Konuşma Geçmişi',
            ram_cache: 'RAM Önbellek',
            price_flow: 'Fiyat Akışı',
            reservation_flow: 'Rezervasyon Akışı',
            followup: 'Follow-up',
            rate_limit: 'Rate Limit',
            paused: 'Duraklatılmış',
            reminders: 'Hatırlatmalar'
        };

        async function purgePreview() {
            const phone = document.getElementById('purgePhone').value.trim();
            if (!phone) return alert('Telefon numarası girin');

            const preview = document.getElementById('purgePreview');
            const result = document.getElementById('purgeResult');
            const btn = document.getElementById('purgeBtn');
            result.style.display = 'none';
            preview.innerHTML = '<p style="color:#888;">Yükleniyor...</p>';

            try {
                const res = await fetch(API + '/purge/preview/' + phone);
                const data = await res.json();

                if (data.error) {
                    preview.innerHTML = '<p style="color:#ff4757;">' + data.error + '</p>';
                    btn.disabled = true;
                    return;
                }

                const items = data.items || {};
                if (Object.keys(items).length === 0) {
                    preview.innerHTML = '<p style="color:#ffa502;">Bu numaraya ait veri bulunamadı.</p>';
                    btn.disabled = true;
                    purgePhoneReady = '';
                    return;
                }

                let html = '';
                for (const [key, info] of Object.entries(items)) {
                    const label = purgeLabels[key] || key;
                    let detail = '';
                    if (info.message_count) detail = info.message_count + ' mesaj';
                    else if (info.entries) detail = info.entries + ' kayıt';
                    else if (info.state) detail = 'Durum: ' + info.state;
                    else if (info.count) detail = info.count + ' adet';
                    else if (info.blocked) detail = 'Bloklu';
                    else detail = 'Mevcut';

                    html += '<div class="purge-item"><span class="item-name">' + label + '</span><span class="item-detail">' + detail + '</span></div>';
                }

                preview.innerHTML = html;
                purgePhoneReady = data.phone;
                btn.disabled = false;
            } catch(e) {
                preview.innerHTML = '<p style="color:#ff4757;">Hata: ' + e.message + '</p>';
                btn.disabled = true;
            }
        }

        async function purgeExecute() {
            if (!purgePhoneReady) return alert('Önce önizleme yapın');
            if (!confirm(purgePhoneReady + ' numarasına ait TÜM veriler silinecek. Emin misiniz?')) return;

            const btn = document.getElementById('purgeBtn');
            const result = document.getElementById('purgeResult');
            const preview = document.getElementById('purgePreview');
            btn.disabled = true;
            btn.textContent = 'Temizleniyor...';

            try {
                const res = await fetch(API + '/purge/' + purgePhoneReady, { method: 'POST' });
                const data = await res.json();

                if (data.success) {
                    const cleared = (data.cleared || []).map(k => purgeLabels[k] || k).join(', ');
                    result.className = 'purge-result success';
                    result.innerHTML = '✅ <strong>' + data.phone + '</strong> sıfırlandı!<br><span style="color:#888;">Temizlenen: ' + cleared + '</span>';
                    result.style.display = 'block';
                    preview.innerHTML = '';
                    purgePhoneReady = '';
                    document.getElementById('purgePhone').value = '';
                } else {
                    result.className = 'purge-result empty';
                    result.innerHTML = '⚠️ ' + (data.error || 'Bilinmeyen hata');
                    result.style.display = 'block';
                }
            } catch(e) {
                result.className = 'purge-result empty';
                result.innerHTML = '❌ Hata: ' + e.message;
                result.style.display = 'block';
            }

            btn.textContent = 'Sıfırla';
            btn.disabled = true;
        }

        // 📊 Metrik fonksiyonları
        async function loadMetrics() {
            try {
                const res = await fetch(API + '/admin/metrics');
                const data = await res.json();
                
                document.getElementById('metricsDate').textContent = data.date || '-';
                document.getElementById('totalMessages').textContent = data.total_messages || 0;
                document.getElementById('localResponses').textContent = data.local_responses || 0;
                document.getElementById('localPct').textContent = data.local_percent || 0;
                document.getElementById('openaiResponses').textContent = data.openai_responses || 0;
                document.getElementById('openaiPct').textContent = data.openai_percent || 0;
                document.getElementById('handoffCount').textContent = data.handoff_count || 0;
                document.getElementById('errorCount').textContent = data.error_count || 0;
                document.getElementById('avgTime').textContent = data.avg_response_time || 0;
            } catch(e) {
                console.error('Metrik yükleme hatası:', e);
            }
        }
        
        async function sendDailyReport() {
            try {
                const res = await fetch(API + '/admin/daily-report/send', { method: 'POST' });
                const data = await res.json();
                alert('✅ Günlük rapor gönderildi!');
            } catch(e) {
                alert('❌ Rapor gönderilemedi: ' + e.message);
            }
        }
        
        // 🧪 Pytest Test Sistemi
        let pytestInterval = null;
        
        async function loadPytestStatus() {
            try {
                const res = await fetch(API + '/admin/pytest/status');
                const data = await res.json();
                
                const icon = document.getElementById('testStatusIcon');
                const status = document.getElementById('testStatusText');
                const summary = document.getElementById('testSummary');
                const lastTime = document.getElementById('lastTestTime');
                
                if (data.running) {
                    icon.textContent = '⏳';
                    status.textContent = 'Test çalışıyor...';
                    status.style.color = '#ffa502';
                    summary.textContent = 'Lütfen bekleyin...';
                    
                    // Çalışırken daha sık kontrol et
                    if (!pytestInterval) {
                        pytestInterval = setInterval(loadPytestStatus, 2000);
                    }
                } else {
                    // Çalışma bittiğinde interval'i durdur
                    if (pytestInterval) {
                        clearInterval(pytestInterval);
                        pytestInterval = null;
                    }
                    
                    if (data.last_run) {
                        const lastRun = new Date(data.last_run);
                        lastTime.textContent = 'Son test: ' + lastRun.toLocaleString('tr-TR');
                        
                        if (data.success) {
                            icon.textContent = '✅';
                            status.textContent = 'Tüm Testler Başarılı';
                            status.style.color = '#00ff88';
                        } else {
                            icon.textContent = data.failed > 0 ? '❌' : '⏳';
                            status.textContent = data.failed > 0 ? 'Bazı Testler Başarısız' : 'Henüz test yapılmadı';
                            status.style.color = data.failed > 0 ? '#ff4757' : '#888';
                        }
                        
                        summary.textContent = data.summary || '-';
                        
                        // Test sonuçlarını göster
                        const resultsContainer = document.getElementById('testResults');
                        if (data.tests && data.tests.length > 0) {
                            resultsContainer.innerHTML = data.tests.map(t => `
                                <div style="display: flex; justify-content: space-between; padding: 8px; background: rgba(255,255,255,0.03); border-radius: 5px; margin-bottom: 5px;">
                                    <span>${t.icon} ${t.name}</span>
                                    <span style="color: ${t.status === 'passed' ? '#00ff88' : '#ff4757'};">${t.status}</span>
                                </div>
                            `).join('');
                        } else {
                            resultsContainer.innerHTML = '<p style="color:#888; text-align:center;">Test sonucu yok</p>';
                        }
                    }
                }
            } catch(e) {
                console.error('Pytest status hatası:', e);
            }
        }
        
        async function loadPytestOutput() {
            try {
                const res = await fetch(API + '/admin/pytest/output');
                const data = await res.json();
                document.getElementById('testOutput').textContent = data.output || 'Çıktı yok';
            } catch(e) {
                console.error('Pytest output hatası:', e);
            }
        }
        
        async function runPytest(type) {
            document.getElementById('testStatusIcon').textContent = '⏳';
            document.getElementById('testStatusText').textContent = 'Test başlatılıyor...';
            
            try {
                let endpoint = '/admin/pytest/run';
                if (type === 'unit') endpoint = '/admin/pytest/run/unit';
                else if (type === 'integration') endpoint = '/admin/pytest/run/integration';
                else if (type === 'e2e') endpoint = '/admin/pytest/run/e2e';
                
                const res = await fetch(API + endpoint, { method: 'POST' });
                const data = await res.json();
                
                if (data.error) {
                    alert('⚠️ ' + data.error);
                } else {
                    // Hemen durumu güncelle
                    setTimeout(loadPytestStatus, 500);
                    setTimeout(loadPytestOutput, 1000);
                }
            } catch(e) {
                alert('❌ Test başlatılamadı: ' + e.message);
            }
        }
        
        // Sayfa yüklendiğinde
        loadStatus();
        loadSettings();
        loadStats();
        loadActiveConversations();
        loadMetrics();
        loadCurrentModel();
        loadPytestStatus();
        loadPytestOutput();
        
        // Periyodik güncelleme
        setInterval(loadStatus, 5000);
        setInterval(loadActiveConversations, 15000);
        setInterval(loadMetrics, 10000);
        setInterval(loadPytestStatus, 30000);  // Her 30 saniyede test durumu
    </script>
</body>
</html>
"""

RESERVATIONS_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🍽️ Restoran Rezervasyonları - Kassandra</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: #fff; min-height: 100vh; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { text-align: center; margin-bottom: 30px; font-size: 2rem; }
        h1 span { color: #ff6b6b; }
        
        .nav-links { text-align: center; margin-bottom: 20px; background: rgba(0,0,0,0.3); padding: 15px; border-radius: 10px; }
        .nav-links a { color: #00d4ff; text-decoration: none; margin: 0 10px; padding: 8px 15px; border: 1px solid #00d4ff; border-radius: 5px; display: inline-block; margin-bottom: 5px; }
        .nav-links a:hover { background: #00d4ff; color: #000; }
        .nav-links a.active { background: #00d4ff; color: #000; }
        
        .stats-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-bottom: 30px; }
        .stat-card { background: rgba(255,255,255,0.05); padding: 20px; border-radius: 15px; text-align: center; }
        .stat-number { font-size: 2rem; font-weight: bold; }
        .stat-label { color: #888; font-size: 0.9rem; margin-top: 5px; }
        
        .section { background: rgba(255,255,255,0.05); border-radius: 15px; padding: 20px; margin-bottom: 20px; }
        .section h2 { margin-bottom: 15px; display: flex; align-items: center; gap: 10px; }
        
        .reservation-card { background: rgba(255,255,255,0.03); border-radius: 10px; padding: 15px; margin-bottom: 10px; border-left: 4px solid #00d4ff; }
        .reservation-card.pending { border-left-color: #ffa502; }
        .reservation-card.confirmed { border-left-color: #00ff88; }
        .reservation-card.completed { border-left-color: #5352ed; }
        .reservation-card.cancelled { border-left-color: #ff4757; opacity: 0.6; }
        .reservation-card.no_show { border-left-color: #ff4757; opacity: 0.6; }
        
        .res-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
        .res-id { font-size: 0.8rem; color: #888; }
        .res-status { padding: 3px 10px; border-radius: 20px; font-size: 0.75rem; }
        .res-status.pending { background: #ffa502; color: #000; }
        .res-status.confirmed { background: #00ff88; color: #000; }
        .res-status.completed { background: #5352ed; color: #fff; }
        .res-status.cancelled { background: #ff4757; color: #fff; }
        .res-status.no_show { background: #ff4757; color: #fff; }
        
        .res-details { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 10px; margin-bottom: 10px; }
        .res-detail { font-size: 0.9rem; }
        .res-detail-label { color: #888; font-size: 0.75rem; }
        
        .res-actions { display: flex; gap: 10px; flex-wrap: wrap; }
        .res-actions button { padding: 5px 12px; border: none; border-radius: 5px; cursor: pointer; font-size: 0.8rem; }
        .btn-confirm { background: #00ff88; color: #000; }
        .btn-complete { background: #5352ed; color: #fff; }
        .btn-noshow { background: #ffa502; color: #000; }
        .btn-cancel { background: #ff4757; color: #fff; }
        .btn-edit { background: #00d4ff; color: #000; }
        
        .meal-icon { font-size: 1.5rem; }
        
        .empty-state { text-align: center; color: #666; padding: 40px; }
        
        .filter-row { display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }
        .filter-row input, .filter-row select { padding: 10px; border-radius: 8px; border: 1px solid #444; background: #2a2a4a; color: #fff; }
        .filter-row button { padding: 10px 20px; border: none; border-radius: 8px; background: #00d4ff; color: #000; cursor: pointer; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🍽️ Restoran <span>Rezervasyonları</span></h1>
        <div style="text-align:center; margin: 10px 0 25px;">
            <a href="/admin/restaurant-plan" class="btn" style="display:inline-block; padding:12px 18px; border-radius:12px; border:1px solid rgba(255,255,255,0.2); text-decoration:none; color:#fff; background:rgba(0,0,0,0.25);">🗺️ Masa Planı (Sürükle‑Bırak)</a>
        </div>
        
        <div class="nav-links">
            <a href="/admin" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; font-weight: bold;">🏠 Ana Sayfa</a>
            <a href="/admin/dashboard">📊 Dashboard</a>
            <a href="/admin/reservations-page" class="active">🍽️ Rezervasyonlar</a>
            <a href="/admin/hotel-bookings-page">🏨 Otel Rez.</a>
            <a href="/admin/transfer-reservations-page">🚐 Transfer Rez.</a>
            <a href="/admin/reminders-page">📅 Hatırlatmalar</a>
            <a href="/admin/qa/stats">🔍 QA Stats</a>
            <a href="/admin/tools">⚙️ Araçlar</a>
        </div>

        <!-- İstatistikler -->
        <div class="stats-row">
            <div class="stat-card">
                <div class="stat-number" id="todayCount" style="color: #00d4ff;">-</div>
                <div class="stat-label">Bugün</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="pendingCount" style="color: #ffa502;">-</div>
                <div class="stat-label">Bekleyen</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="confirmedCount" style="color: #00ff88;">-</div>
                <div class="stat-label">Onaylı</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="weekCount" style="color: #5352ed;">-</div>
                <div class="stat-label">Bu Hafta</div>
            </div>
        </div>
        
        <!-- Filtreler -->
        <div class="section">
            <div class="filter-row">
                <input type="text" id="filterName" placeholder="İsim ara..." onkeyup="debounceSearch()" style="min-width: 150px;">
                <input type="text" id="filterPhone" placeholder="Telefon ara..." onkeyup="debounceSearch()" style="min-width: 130px;">
                <input type="date" id="filterDate" onchange="loadReservations()">
                <select id="filterStatus" onchange="loadReservations()">
                    <option value="">Tüm Durumlar</option>
                    <option value="pending">Bekleyen</option>
                    <option value="confirmed">Onaylı</option>
                    <option value="completed">Tamamlandı</option>
                    <option value="cancelled">İptal</option>
                    <option value="no_show">No-show</option>
                </select>
                <button onclick="loadReservations()">🔄 Yenile</button>
                <button onclick="clearFilters()" style="background: #666;">Temizle</button>
            </div>
        </div>
        
        <!-- Bugünün Rezervasyonları -->
        <div class="section">
            <h2>📅 Bugünün Rezervasyonları</h2>
            <div id="todayReservations">
                <div class="empty-state">Yükleniyor...</div>
            </div>
        </div>
        
        <!-- Tüm Gelecek Rezervasyonlar -->
        <div class="section">
            <h2>📆 Tüm Gelecek Rezervasyonlar</h2>
            <div id="upcomingReservations">
                <div class="empty-state">Yükleniyor...</div>
            </div>
        </div>
    </div>
    
    <script>
        const API = '';
        
        function getMealIcon(mealType) {
            const icons = { breakfast: '☕', lunch: '🍽️', dinner: '🌙' };
            return icons[mealType] || '🍽️';
        }
        
        function getMealName(mealType) {
            const names = { breakfast: 'Kahvaltı', lunch: 'Öğle', dinner: 'Akşam' };
            return names[mealType] || mealType;
        }
        
        function getStatusName(status) {
            const names = { pending: 'Bekliyor', confirmed: 'Onaylı', completed: 'Tamamlandı', cancelled: 'İptal', no_show: 'Gelmedi' };
            return names[status] || status;
        }
        
        function formatDate(dateStr) {
            const months = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'];
            const parts = dateStr.split('-');
            return `${parseInt(parts[2])} ${months[parseInt(parts[1])-1]} ${parts[0]}`;
        }
        
        function renderReservation(res) {
            const status = (res.status || '').toLowerCase();
            const showActions = (status === 'pending' || status === 'confirmed');
            console.log('Rez:', res.id, 'Status:', status, 'Actions:', showActions);
            return `
                <div class="reservation-card ${status}">
                    <div class="res-header">
                        <div>
                            <span class="meal-icon">${getMealIcon(res.meal_type)}</span>
                            <strong>${res.customer_name}</strong>
                        </div>
                        <div>
                            <span class="res-id">#${res.id}</span>
                            <span class="res-status ${status}">${getStatusName(status)}</span>
                        </div>
                    </div>
                    <div class="res-details">
                        <div class="res-detail">
                            <div class="res-detail-label">📅 Tarih</div>
                            <div>${formatDate(res.date)}</div>
                        </div>
                        <div class="res-detail">
                            <div class="res-detail-label">🕐 Saat</div>
                            <div>${res.time}</div>
                        </div>
                        <div class="res-detail">
                            <div class="res-detail-label">👥 Kişi</div>
                            <div>${res.guest_count}</div>
                        </div>
                        <div class="res-detail">
                            <div class="res-detail-label">📱 Telefon</div>
                            <div>${res.customer_phone}</div>
                        </div>
                    </div>
                    ${res.special_requests ? `<div style="color: #ffa502; font-size: 0.85rem; margin-bottom: 10px;">📝 ${res.special_requests}</div>` : ''}
                    ${showActions ? `
                    <div class="res-actions">
                        ${status === 'pending' ? `<button class="btn-confirm" onclick="updateStatus(${res.id}, 'confirm')">✓ Onayla</button>` : ''}
                        ${status === 'confirmed' ? `<button class="btn-complete" onclick="updateStatus(${res.id}, 'complete')">✓ Geldi</button>` : ''}
                        ${status === 'confirmed' ? `<button class="btn-noshow" onclick="updateStatus(${res.id}, 'noshow')">✗ Gelmedi</button>` : ''}
                        <button class="btn-cancel" onclick="updateStatus(${res.id}, 'cancel')">İptal</button>
                        <button class="btn-edit" onclick="editReservation(${res.id}, '${res.time}', '${res.date}', ${res.guest_count})">✏️ Düzenle</button>
                    </div>
                    ` : ''}
                </div>
            `;
        }
        
        // Rezervasyon düzenleme fonksiyonu
        async function editReservation(id, currentTime, currentDate, currentGuests) {
            const newTime = prompt('Yeni saat girin (şu an: ' + currentTime + '):', currentTime);
            if (newTime === null) return; // İptal
            
            const newDate = prompt('Yeni tarih girin YYYY-MM-DD (şu an: ' + currentDate + '):', currentDate);
            if (newDate === null) return; // İptal
            
            const newGuests = prompt('Kişi sayısı (şu an: ' + currentGuests + '):', currentGuests);
            if (newGuests === null) return; // İptal
            
            // En az bir değişiklik var mı kontrol et
            if (newTime === currentTime && newDate === currentDate && parseInt(newGuests) === currentGuests) {
                alert('Herhangi bir değişiklik yapılmadı.');
                return;
            }
            
            // Müşteriye bildirim gönderilsin mi?
            const notifyCustomer = confirm('Müşteriye WhatsApp bildirimi gönderilsin mi?');
            
            try {
                let url = `/admin/reservations/${id}/update?notify_customer=${notifyCustomer}`;
                if (newTime !== currentTime) url += `&time=${encodeURIComponent(newTime)}`;
                if (newDate !== currentDate) url += `&date=${encodeURIComponent(newDate)}`;
                if (parseInt(newGuests) !== currentGuests) url += `&guest_count=${newGuests}`;
                
                const response = await fetch(url, { method: 'POST' });
                const result = await response.json();
                
                if (result.status === 'ok') {
                    alert('✅ Rezervasyon güncellendi!\\n\\nDeğişiklikler:\\n' + result.changes.join('\\n'));
                    loadReservations();
                } else {
                    alert('❌ Hata: ' + (result.message || 'Bilinmeyen hata'));
                }
            } catch(e) {
                alert('❌ Hata: ' + e.message);
            }
        }
        
        let searchTimeout = null;
        
        function debounceSearch() {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(loadReservations, 300);
        }
        
        function clearFilters() {
            document.getElementById('filterName').value = '';
            document.getElementById('filterPhone').value = '';
            document.getElementById('filterDate').value = '';
            document.getElementById('filterStatus').value = '';
            loadReservations();
        }
        
        async function loadReservations() {
            try {
                // Filtre değerlerini al
                const filterName = document.getElementById('filterName')?.value || '';
                const filterPhone = document.getElementById('filterPhone')?.value || '';
                const filterDate = document.getElementById('filterDate')?.value || '';
                const filterStatus = document.getElementById('filterStatus')?.value || '';
                
                // Bugün
                const todayRes = await fetch(API + '/admin/reservations/today');
                const todayData = await todayRes.json();
                
                const todayContainer = document.getElementById('todayReservations');
                if (todayData.reservations.length === 0) {
                    todayContainer.innerHTML = '<div class="empty-state">Bugün için rezervasyon yok</div>';
                } else {
                    todayContainer.innerHTML = todayData.reservations.map(renderReservation).join('');
                }
                document.getElementById('todayCount').textContent = todayData.count;
                
                // API URL oluştur (filtrelerle)
                let apiUrl = API + '/admin/reservations?days=365';
                if (filterDate) apiUrl += `&date=${filterDate}`;
                if (filterStatus) apiUrl += `&status=${filterStatus}`;
                if (filterName) apiUrl += `&name=${encodeURIComponent(filterName)}`;
                if (filterPhone) apiUrl += `&phone=${encodeURIComponent(filterPhone)}`;
                
                // Filtrelenmiş rezervasyonlar
                const upcomingRes = await fetch(apiUrl);
                const upcomingData = await upcomingRes.json();
                
                const upcomingContainer = document.getElementById('upcomingReservations');
                
                // Filtre varsa tüm sonuçları göster, yoksa bugünü hariç tut
                let displayReservations = upcomingData.reservations || [];
                if (!filterDate && !filterName && !filterPhone && !filterStatus) {
                    displayReservations = displayReservations.filter(r => r.date !== todayData.date);
                }
                
                if (displayReservations.length === 0) {
                    if (filterName || filterPhone || filterDate || filterStatus) {
                        upcomingContainer.innerHTML = '<div class="empty-state">Arama kriterlerine uygun rezervasyon bulunamadı</div>';
                    } else {
                        upcomingContainer.innerHTML = '<div class="empty-state">Gelecek rezervasyon yok</div>';
                    }
                } else {
                    upcomingContainer.innerHTML = displayReservations.map(renderReservation).join('');
                }
                document.getElementById('weekCount').textContent = upcomingData.count || 0;
                
                // İstatistikler
                const allRes = upcomingData.reservations || [];
                document.getElementById('pendingCount').textContent = allRes.filter(r => r.status === 'pending').length;
                document.getElementById('confirmedCount').textContent = allRes.filter(r => r.status === 'confirmed').length;
                
            } catch(e) {
                console.error('Rezervasyon yükleme hatası:', e);
            }
        }
        
        async function updateStatus(id, action) {
            const confirmMsg = {
                confirm: 'Rezervasyonu onaylamak istiyor musunuz?',
                complete: 'Müşteri geldi olarak işaretlensin mi?',
                noshow: 'Müşteri gelmedi olarak işaretlensin mi?',
                cancel: 'Rezervasyonu iptal etmek istiyor musunuz?'
            };
            
            if (!confirm(confirmMsg[action])) return;
            
            try {
                await fetch(API + `/admin/reservations/${id}/${action}`, { method: 'POST' });
                loadReservations();
            } catch(e) {
                alert('Hata: ' + e.message);
            }
        }
        
        // Sayfa yüklendiğinde
        loadReservations();
        
        // Her 30 saniyede güncelle
        setInterval(loadReservations, 30000);
    </script>
</body>
</html>
"""

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Kassandra Dashboard</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', sans-serif; 
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #fff;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { text-align: center; margin-bottom: 30px; color: #00d4ff; }
        h1 span { color: #ffa502; }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 20px;
            text-align: center;
        }
        .stat-card .value { font-size: 2.5rem; font-weight: bold; color: #00d4ff; }
        .stat-card .label { color: #aaa; margin-top: 5px; }
        .stat-card.success .value { color: #00ff88; }
        .stat-card.warning .value { color: #ffa502; }
        .stat-card.danger .value { color: #ff4757; }
        
        .charts-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .chart-card {
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 20px;
        }
        .chart-card h3 { margin-bottom: 15px; color: #00d4ff; }
        
        .recent-section {
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 30px;
        }
        .recent-section h3 { margin-bottom: 15px; color: #00d4ff; }
        
        .recent-list { list-style: none; }
        .recent-list li {
            padding: 10px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .recent-list li:last-child { border-bottom: none; }
        
        .status-badge {
            padding: 3px 10px;
            border-radius: 20px;
            font-size: 0.8rem;
        }
        .status-badge.pending { background: #ffa502; color: #000; }
        .status-badge.confirmed { background: #00ff88; color: #000; }
        .status-badge.completed { background: #5352ed; color: #fff; }
        .status-badge.cancelled { background: #ff4757; color: #fff; }
        
        .nav-links {
            text-align: center;
            margin-bottom: 20px;
            background: rgba(0,0,0,0.3);
            padding: 15px;
            border-radius: 10px;
        }
        .nav-links a {
            color: #00d4ff;
            text-decoration: none;
            margin: 0 10px;
            padding: 10px 20px;
            border: 1px solid #00d4ff;
            border-radius: 5px;
            display: inline-block;
            margin-bottom: 5px;
        }
        .nav-links a:hover { background: #00d4ff; color: #000; }
        .nav-links a.active { background: #00d4ff; color: #000; }
        
        .refresh-btn {
            background: #00d4ff;
            color: #000;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            margin-bottom: 20px;
        }
        .scorecard-card {
            background: rgba(255,255,255,0.08);
            border-radius: 15px;
            padding: 18px;
            margin-bottom: 20px;
        }
        .scorecard-head { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 10px; }
        .scorecard-head input { width: 90px; padding: 6px 8px; border-radius: 6px; border: 1px solid #444; background: #2a2a4a; color: #fff; }
        .score-pill { display:inline-block; padding: 2px 8px; border-radius: 999px; font-size: 0.75rem; font-weight: bold; }
        .score-pill.good { background: rgba(0, 255, 136, 0.18); color: #79ffbf; border: 1px solid rgba(0, 255, 136, 0.3); }
        .score-pill.bad { background: rgba(255, 82, 82, 0.18); color: #ff8d8d; border: 1px solid rgba(255, 82, 82, 0.3); }
        .score-meta { color: #9aa3b2; font-size: 0.82rem; margin-top: 4px; }
        .score-grid { display:grid; grid-template-columns: repeat(2, minmax(220px, 1fr)); gap:10px; margin-top: 10px; }
        .score-item { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 10px; }
        .score-item .name { font-weight: 700; font-size: 0.86rem; margin-bottom: 6px; }
        .score-item .note { color: #9aa3b2; font-size: 0.78rem; margin-top: 4px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Kassandra <span>Dashboard</span></h1>
        
        <div class="nav-links">
            <a href="/admin" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; font-weight: bold;">🏠 Ana Sayfa</a>
            <a href="/admin/dashboard" class="active">📊 Dashboard</a>
            <a href="/admin/reservations-page">🍽️ Rezervasyonlar</a>
            <a href="/admin/hotel-bookings-page">🏨 Otel Rez.</a>
            <a href="/admin/transfer-reservations-page">🚐 Transfer Rez.</a>
            <a href="/admin/reminders-page">📅 Hatırlatmalar</a>
            <a href="/admin/qa/stats">🔍 QA Stats</a>
            <a href="/admin/tools">⚙️ Araçlar</a>
        </div>
        
        <button class="refresh-btn" onclick="loadDashboard()">🔄 Yenile</button>
        
        <div class="stats-grid" id="statsGrid">
            <div class="stat-card">
                <div class="value" id="todayCount">-</div>
                <div class="label">Bugünkü Rezervasyon</div>
            </div>
            <div class="stat-card success">
                <div class="value" id="confirmedCount">-</div>
                <div class="label">Onaylanan</div>
            </div>
            <div class="stat-card warning">
                <div class="value" id="pendingCount">-</div>
                <div class="label">Bekleyen</div>
            </div>
            <div class="stat-card danger">
                <div class="value" id="cancelledCount">-</div>
                <div class="label">İptal</div>
            </div>
            <div class="stat-card">
                <div class="value" id="totalGuests">-</div>
                <div class="label">Toplam Misafir</div>
            </div>
            <div class="stat-card">
                <div class="value" id="qaScore">-</div>
                <div class="label">QA Skoru</div>
            </div>
        </div>

        <div class="scorecard-card">
            <h3>🎯 Başarı Metrikleri ve Hedef Eşikler</h3>
            <div class="scorecard-head">
                <label for="dashboardScoreDays">Gün:</label>
                <input id="dashboardScoreDays" type="number" value="7" min="1" max="90">
                <button class="refresh-btn" style="margin-bottom:0;" onclick="loadSuccessScorecardDashboard()">Yükle</button>
                <span id="dashboardScoreBadge" class="score-pill">-</span>
            </div>
            <div id="dashboardScoreMeta" class="score-meta"></div>
            <div id="dashboardScoreGrid" class="score-grid">
                <div class="score-item">Henüz yüklenmedi.</div>
            </div>
        </div>
        
        <div class="charts-grid">
            <div class="chart-card">
                <h3>📅 Haftalık Rezervasyonlar</h3>
                <canvas id="weeklyChart"></canvas>
            </div>
            <div class="chart-card">
                <h3>🍽️ Öğün Dağılımı</h3>
                <canvas id="mealChart"></canvas>
            </div>
        </div>
        
        <div class="recent-section">
            <h3>🕐 Son Rezervasyonlar</h3>
            <ul class="recent-list" id="recentList">
                <li>Yükleniyor...</li>
            </ul>
        </div>
    </div>
    
    <script>
        let weeklyChart, mealChart;
        
        async function loadDashboard() {
            try {
                // Rezervasyonları al
                const resResponse = await fetch('/admin/reservations?days=30');
                const resData = await resResponse.json();
                const reservations = resData.reservations || [];
                
                // İstatistikleri hesapla
                const today = new Date().toISOString().split('T')[0];
                const todayRes = reservations.filter(r => r.date === today);
                
                document.getElementById('todayCount').textContent = todayRes.length;
                document.getElementById('confirmedCount').textContent = reservations.filter(r => r.status === 'confirmed').length;
                document.getElementById('pendingCount').textContent = reservations.filter(r => r.status === 'pending').length;
                document.getElementById('cancelledCount').textContent = reservations.filter(r => r.status === 'cancelled').length;
                document.getElementById('totalGuests').textContent = reservations.reduce((sum, r) => sum + (r.guest_count || 0), 0);
                
                // QA Stats
                try {
                    const qaResponse = await fetch('/admin/qa/stats');
                    const qaData = await qaResponse.json();
                    document.getElementById('qaScore').textContent = qaData.avg_score ? qaData.avg_score.toFixed(1) : '-';
                } catch(e) {
                    document.getElementById('qaScore').textContent = '-';
                }
                
                // Haftalık grafik
                const weekData = {};
                const days = ['Paz', 'Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt'];
                for (let i = 6; i >= 0; i--) {
                    const d = new Date();
                    d.setDate(d.getDate() - i);
                    const dateStr = d.toISOString().split('T')[0];
                    const dayName = days[d.getDay()];
                    weekData[dayName] = reservations.filter(r => r.date === dateStr).length;
                }
                
                if (weeklyChart) weeklyChart.destroy();
                weeklyChart = new Chart(document.getElementById('weeklyChart'), {
                    type: 'bar',
                    data: {
                        labels: Object.keys(weekData),
                        datasets: [{
                            label: 'Rezervasyon',
                            data: Object.values(weekData),
                            backgroundColor: '#00d4ff'
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: { legend: { display: false } },
                        scales: {
                            y: { beginAtZero: true, ticks: { color: '#fff' } },
                            x: { ticks: { color: '#fff' } }
                        }
                    }
                });
                
                // Öğün grafiği
                const mealCounts = {
                    'Kahvaltı': reservations.filter(r => r.meal_type === 'breakfast').length,
                    'Öğle': reservations.filter(r => r.meal_type === 'lunch').length,
                    'Akşam': reservations.filter(r => r.meal_type === 'dinner').length
                };
                
                if (mealChart) mealChart.destroy();
                mealChart = new Chart(document.getElementById('mealChart'), {
                    type: 'doughnut',
                    data: {
                        labels: Object.keys(mealCounts),
                        datasets: [{
                            data: Object.values(mealCounts),
                            backgroundColor: ['#ffa502', '#00d4ff', '#ff4757']
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: { legend: { labels: { color: '#fff' } } }
                    }
                });
                
                // Son rezervasyonlar
                const recent = reservations.slice(0, 10);
                const listHtml = recent.map(r => `
                    <li>
                        <div>
                            <strong>${r.customer_name}</strong> - ${r.guest_count} kişi
                            <br><small>${r.date} ${r.time}</small>
                        </div>
                        <span class="status-badge ${r.status}">${r.status}</span>
                    </li>
                `).join('');
                document.getElementById('recentList').innerHTML = listHtml || '<li>Rezervasyon yok</li>';
                
            } catch(e) {
                console.error('Dashboard yükleme hatası:', e);
            }
        }

        function _fmtScoreValue(v) {
            if (v === null || v === undefined) return 'n/a';
            const n = Number(v);
            if (Number.isNaN(n)) return String(v);
            if (n <= 1) return (n * 100).toFixed(1) + '%';
            return n.toFixed(2);
        }

        async function loadSuccessScorecardDashboard() {
            const days = Number(document.getElementById('dashboardScoreDays').value || 7);
            const badge = document.getElementById('dashboardScoreBadge');
            const meta = document.getElementById('dashboardScoreMeta');
            const grid = document.getElementById('dashboardScoreGrid');

            badge.textContent = '...';
            badge.className = 'score-pill';
            meta.textContent = '';
            grid.innerHTML = '<div class="score-item">Yükleniyor...</div>';

            try {
                const res = await fetch(`/admin/metrics/success-scorecard?days=${encodeURIComponent(days)}`);
                const data = await res.json();
                const metrics = data.metrics || {};
                const keys = Object.keys(metrics);
                if (!keys.length) {
                    badge.textContent = 'NO_DATA';
                    grid.innerHTML = '<div class="score-item">Metrik verisi bulunamadı.</div>';
                    return;
                }

                let pass = 0, fail = 0, nodata = 0;
                grid.innerHTML = keys.map((key) => {
                    const m = metrics[key] || {};
                    const status = String(m.status || 'no_data');
                    if (status === 'pass') pass += 1;
                    else if (status === 'fail') fail += 1;
                    else nodata += 1;
                    const cls = status === 'pass' ? 'good' : (status === 'fail' ? 'bad' : '');
                    const lbl = status === 'pass' ? 'PASS' : (status === 'fail' ? 'FAIL' : 'NO_DATA');
                    return `
                        <div class="score-item">
                            <div class="name">${m.label || key}</div>
                            <span class="score-pill ${cls}">${lbl}</span>
                            <div class="note">Hedef: <b>${_fmtScoreValue(m.target)}</b> | Gerçek: <b>${_fmtScoreValue(m.actual)}</b></div>
                            <div class="note">${m.description || ''}</div>
                        </div>
                    `;
                }).join('');

                badge.textContent = `PASS:${pass} FAIL:${fail} NODATA:${nodata}`;
                badge.className = fail > 0 ? 'score-pill bad' : 'score-pill good';
                meta.textContent = `Toplam event: ${data.event_total || 0} • Auto: ${(data.counts || {}).auto || 0} • Handoff: ${(data.counts || {}).handoff || 0}`;
            } catch (e) {
                badge.textContent = 'HATA';
                badge.className = 'score-pill bad';
                grid.innerHTML = `<div class="score-item" style="color:#ff8d8d;">${String(e.message || e)}</div>`;
            }
        }
        
        // Sayfa yüklendiğinde
        loadDashboard();
        loadSuccessScorecardDashboard();
        
        // Her 30 saniyede güncelle
        setInterval(loadDashboard, 30000);
    </script>
</body>
</html>
"""

ADMIN_TOOLS_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kassandra Bot - Gelişmiş Araçlar</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, sans-serif; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); min-height: 100vh; color: #fff; }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        h1 { text-align: center; margin-bottom: 30px; font-size: 2rem; }
        h1 span { color: #5352ed; }
        
        .back-btn { display: inline-block; margin-bottom: 20px; padding: 10px 20px; background: rgba(255,255,255,0.1); border-radius: 8px; color: #fff; text-decoration: none; }
        .back-btn:hover { background: rgba(255,255,255,0.2); }
        
        .card { background: rgba(255,255,255,0.1); border-radius: 20px; padding: 25px; margin-bottom: 20px; backdrop-filter: blur(10px); }
        .card h2 { margin-bottom: 20px; display: flex; align-items: center; gap: 10px; }
        
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 8px; color: #aaa; }
        .form-group input, .form-group textarea, .form-group select { 
            width: 100%; padding: 12px; border-radius: 8px; border: 1px solid #444; 
            background: #2a2a4a; color: #fff; font-size: 1rem; 
        }
        .form-group textarea { min-height: 100px; resize: vertical; }
        
        .btn { padding: 12px 25px; border: none; border-radius: 8px; font-size: 1rem; cursor: pointer; transition: all 0.3s; font-weight: bold; }
        .btn-primary { background: linear-gradient(135deg, #5352ed, #3742fa); color: #fff; }
        .btn-success { background: linear-gradient(135deg, #00ff88, #00d4ff); color: #1a1a2e; }
        .btn-danger { background: linear-gradient(135deg, #ff4757, #ff6b81); color: #fff; }
        .btn-warning { background: linear-gradient(135deg, #ffa502, #ff7f50); color: #1a1a2e; }
        .btn:hover { transform: scale(1.02); box-shadow: 0 5px 20px rgba(0,0,0,0.3); }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        
        .grid-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; }
        
        .conversation-item { 
            display: flex; justify-content: space-between; align-items: center; 
            padding: 15px; background: rgba(255,255,255,0.05); border-radius: 10px; margin-bottom: 10px; 
        }
        .conversation-item .info { flex: 1; }
        .conversation-item .phone { font-weight: bold; color: #00d4ff; }
        .conversation-item .msg { color: #888; font-size: 0.9rem; margin-top: 5px; }
        .conversation-item .time { color: #666; font-size: 0.8rem; }
        .conversation-item .actions { display: flex; gap: 10px; }
        
        .person-card { padding: 15px; background: rgba(255,255,255,0.05); border-radius: 10px; margin-bottom: 10px; }
        .person-card .name { font-weight: bold; font-size: 1.1rem; }
        .person-card .role { color: #ffa502; font-size: 0.9rem; }
        .person-card .phone { color: #888; font-size: 0.9rem; margin-top: 5px; }
        
        .endpoint-group { margin-bottom: 20px; }
        .endpoint-group h3 { color: #5352ed; margin-bottom: 10px; text-transform: uppercase; }
        .endpoint-item { 
            display: flex; align-items: center; gap: 10px; padding: 10px; 
            background: rgba(255,255,255,0.03); border-radius: 5px; margin-bottom: 5px; 
            cursor: pointer; transition: background 0.2s;
        }
        .endpoint-item:hover { background: rgba(255,255,255,0.08); }
        .method { padding: 3px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; }
        .method.GET { background: #00ff88; color: #000; }
        .method.POST { background: #ffa502; color: #000; }
        .method.DELETE { background: #ff4757; color: #fff; }
        .path { font-family: monospace; }
        
        .result-box { 
            margin-top: 15px; padding: 15px; background: #1a1a2e; border-radius: 8px; 
            font-family: monospace; font-size: 0.9rem; max-height: 300px; overflow: auto;
            white-space: pre-wrap; word-break: break-all;
        }
        
        .status-badge { padding: 5px 10px; border-radius: 20px; font-size: 0.8rem; }
        .status-badge.active { background: #00ff88; color: #000; }
        .status-badge.paused { background: #ffa502; color: #000; }
        
        .tabs { display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }
        .tab { padding: 10px 20px; background: rgba(255,255,255,0.1); border-radius: 8px; cursor: pointer; }
        .tab.active { background: #5352ed; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .mini-note { color: #9aa3b2; font-size: 0.85rem; margin-top: 8px; }
        .packet-table-wrap { margin-top: 12px; max-height: 280px; overflow: auto; border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; }
        .packet-table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
        .packet-table th, .packet-table td { padding: 8px; border-bottom: 1px solid rgba(255,255,255,0.06); text-align: left; vertical-align: top; }
        .packet-table th { position: sticky; top: 0; background: #181e2d; z-index: 1; }
        .pill { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 0.75rem; font-weight: bold; }
        .pill.bad { background: rgba(255, 82, 82, 0.18); color: #ff8d8d; border: 1px solid rgba(255, 82, 82, 0.3); }
        .pill.good { background: rgba(0, 255, 136, 0.18); color: #79ffbf; border: 1px solid rgba(0, 255, 136, 0.3); }
        .metric-grid { display:grid; grid-template-columns: repeat(2, minmax(220px, 1fr)); gap:10px; margin-top: 12px; }
        .metric-item { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 10px; }
        .metric-name { font-weight: 700; font-size: 0.86rem; margin-bottom: 6px; }
        .metric-note { color: #9aa3b2; font-size: 0.78rem; margin-top: 4px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="nav-links" style="text-align: center; margin-bottom: 20px; background: rgba(0,0,0,0.3); padding: 15px; border-radius: 10px;">
            <a href="/admin" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; text-decoration: none; margin: 0 10px; padding: 10px 20px; border: none; border-radius: 5px; display: inline-block; margin-bottom: 5px; font-weight: bold;">🏠 Ana Sayfa</a>
            <a href="/admin/dashboard" style="color: #00d4ff; text-decoration: none; margin: 0 10px; padding: 10px 20px; border: 1px solid #00d4ff; border-radius: 5px; display: inline-block; margin-bottom: 5px;">📊 Dashboard</a>
            <a href="/admin/reservations-page" style="color: #00d4ff; text-decoration: none; margin: 0 10px; padding: 10px 20px; border: 1px solid #00d4ff; border-radius: 5px; display: inline-block; margin-bottom: 5px;">🍽️ Rezervasyonlar</a>
            <a href="/admin/hotel-bookings-page" style="color: #00d4ff; text-decoration: none; margin: 0 10px; padding: 10px 20px; border: 1px solid #00d4ff; border-radius: 5px; display: inline-block; margin-bottom: 5px;">🏨 Otel Rez.</a>
            <a href="/admin/reminders-page" style="color: #00d4ff; text-decoration: none; margin: 0 10px; padding: 10px 20px; border: 1px solid #00d4ff; border-radius: 5px; display: inline-block; margin-bottom: 5px;">📅 Hatırlatmalar</a>
            <a href="/admin/qa/stats" style="color: #00d4ff; text-decoration: none; margin: 0 10px; padding: 10px 20px; border: 1px solid #00d4ff; border-radius: 5px; display: inline-block; margin-bottom: 5px;">🔍 QA Stats</a>
            <a href="/admin/tools" style="color: #000; background: #00d4ff; text-decoration: none; margin: 0 10px; padding: 10px 20px; border: 1px solid #00d4ff; border-radius: 5px; display: inline-block; margin-bottom: 5px;">⚙️ Araçlar</a>
        </div>
        <h1>🔧 Gelişmiş <span>Araçlar</span></h1>
        
        <div class="grid-2">
            <!-- Sol Kolon -->
            <div>
                <!-- Manuel Mesaj Gönderme -->
                <div class="card">
                    <h2>📤 Manuel Mesaj Gönder</h2>
                    <div class="form-group">
                        <label>Telefon Numarası</label>
                        <input type="text" id="msgPhone" placeholder="905551234567">
                    </div>
                    <div class="form-group">
                        <label>Mesaj</label>
                        <textarea id="msgText" placeholder="Göndermek istediğiniz mesajı yazın..."></textarea>
                    </div>
                    <button class="btn btn-primary" onclick="sendMessage()">📨 Gönder</button>
                    <div id="msgResult" class="result-box" style="display:none;"></div>
                </div>
                
                <!-- Aktif Konuşmalar -->
                <div class="card">
                    <h2>💬 Aktif Konuşmalar (Son 30 dk)</h2>
                    <div style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom: 15px;">
                        <button class="btn btn-success" onclick="loadActiveConversations()">🔄 Yenile</button>
                        <button class="btn btn-warning" onclick="purgeAllActiveConversationsTools()">🧹 Tüm Konuşmaları Sıfırla</button>
                        <button class="btn btn-warning" onclick="purgeSelectedActiveConversationsTools()">🧹 Seçili Konuşmalara Sıfırla</button>
                        <button class="btn btn-danger" onclick="blacklistAllActiveConversationsTools()">🚫 Tüm Konuşmaları KARA LİSTEYE EKLE</button>
                        <button class="btn btn-danger" onclick="blacklistSelectedActiveConversationsTools()">🚫 Seçili Konuşmaları Kara Listeye</button>
                        <button class="btn btn-primary" onclick="selectAllActiveConversationsTools()">☑️ Tümünü Seç</button>
                        <button class="btn btn-primary" onclick="clearActiveSelectionTools()">⬜ Seçimi Temizle</button>
                    </div>
                    <div id="activeSelectionInfoTools" class="mini-note" style="margin-bottom:10px;">Seçili: 0</div>
                    <div id="activeConversations">Yükleniyor...</div>
                </div>
                
                <!-- Yetkili Kişiler -->
                <div class="card">
                    <h2>👤 Yetkili Kişiler</h2>
                    <div id="authorizedPersons">Yükleniyor...</div>
                </div>
            </div>
            
            <!-- Sağ Kolon -->
            <div>
                <div class="card">
                    <h2>🖥️ Backend Kontrol</h2>
                    <p class="mini-note">`start_backend.bat` dosyasını admin panelden başlatıp durdurur.</p>
                    <div style="display:flex; gap:10px; flex-wrap:wrap; margin-top:10px;">
                        <button class="btn btn-success" onclick="startBackendBat()">▶️ Backend Başlat</button>
                        <button class="btn btn-danger" onclick="stopBackendBat()">⏹️ Backend Durdur</button>
                        <button class="btn btn-warning" onclick="loadBackendStatus()">🔄 Durum Yenile</button>
                    </div>
                    <div id="backendStatusText" class="mini-note" style="margin-top:10px;">Durum: Yükleniyor...</div>
                    <div id="backendControlResult" class="result-box" style="display:none; margin-top:12px;"></div>
                </div>

                <!-- Endpoint Tester -->
                <div class="card">
                    <h2>🔌 API Endpoint Tester</h2>
                    <div class="form-group">
                        <label>Endpoint Seçin veya Yazın</label>
                        <select id="endpointSelect" onchange="selectEndpoint()">
                            <option value="">-- Endpoint Seçin --</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Method</label>
                        <select id="endpointMethod">
                            <option value="GET">GET</option>
                            <option value="POST">POST</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>URL</label>
                        <input type="text" id="endpointUrl" placeholder="/admin/metrics">
                    </div>
                    <div class="form-group">
                        <label>Query Params (opsiyonel, örn: phone=905551234567)</label>
                        <input type="text" id="endpointParams" placeholder="key=value&key2=value2">
                    </div>
                    <button class="btn btn-warning" onclick="testEndpoint()">▶️ Çalıştır</button>
                    <div id="endpointResult" class="result-box" style="display:none;"></div>
                </div>
                
                <!-- Hızlı Aksiyonlar -->
                <div class="card">
                    <h2>⚡ Hızlı Aksiyonlar</h2>
                    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px;">
                        <button class="btn btn-success" onclick="quickAction('/admin/metrics', 'GET')">📊 Metrikler</button>
                        <button class="btn btn-success" onclick="quickAction('/admin/selftest/run', 'POST')">🧪 Self-Test</button>
                        <button class="btn btn-success" onclick="quickAction('/admin/followups/pending', 'GET')">⏰ Follow-up'lar</button>
                        <button class="btn btn-success" onclick="quickAction('/admin/errors', 'GET')">❌ Hatalar</button>
                        <button class="btn btn-warning" onclick="quickAction('/admin/daily-report/send', 'POST')">📤 Rapor Gönder</button>
                        <button class="btn btn-warning" onclick="quickAction('/test/check-config', 'GET')">⚙️ Yapılandırma</button>
                        <button class="btn btn-warning" onclick="loadInvalidHandoffPackets()">🚨 Sorunlu Packetler</button>
                        <button class="btn btn-warning" onclick="loadSuccessScorecard()">🎯 Başarı Skorları</button>
                        <button class="btn btn-danger" onclick="quickAction('/admin/metrics/reset', 'POST')">🗑️ Metrik Sıfırla</button>
                        <button class="btn btn-danger" onclick="quickAction('/admin/followups/clear-all', 'POST')">🗑️ Follow-up Temizle</button>
                    </div>
                    <div id="quickResult" class="result-box" style="display:none; margin-top:15px;"></div>
                </div>

                <div class="card">
                    <h2>🎯 Başarı Metrikleri ve Hedef Eşikler</h2>
                    <p class="mini-note">Containment, loop rate, false handoff/auto ve P95 response time metriklerini hedeflerle karşılaştırır.</p>
                    <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-top:10px;">
                        <label for="scorecardDays">Gün:</label>
                        <input id="scorecardDays" type="number" value="7" min="1" max="90" style="width:90px;">
                        <button class="btn btn-warning" onclick="loadSuccessScorecard()">Yükle</button>
                        <span id="scorecardPassFail" class="pill">-</span>
                    </div>
                    <div id="scorecardMeta" class="mini-note"></div>
                    <div id="scorecardGrid" class="metric-grid">
                        <div class="metric-item">Henüz yüklenmedi.</div>
                    </div>
                </div>

                <div class="card">
                    <h2>🚨 Sorunlu Handoff Packetler</h2>
                    <p class="mini-note">Sadece invalid packet kayıtlarını getirir ve eksik alanları gösterir.</p>
                    <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-top:10px;">
                        <label for="handoffPacketDays">Gün:</label>
                        <input id="handoffPacketDays" type="number" value="7" min="1" max="30" style="width:90px;">
                        <label for="handoffAfterDeploy" style="display:flex; align-items:center; gap:6px;">
                            <input id="handoffAfterDeploy" type="checkbox" checked>
                            Sadece deploy sonrası
                        </label>
                        <button class="btn btn-warning" onclick="loadInvalidHandoffPackets()">Yükle</button>
                        <span id="handoffInvalidCount" class="pill bad">-</span>
                    </div>
                    <div id="handoffAfterTsInfo" class="mini-note"></div>
                    <div class="packet-table-wrap">
                        <table class="packet-table">
                            <thead>
                                <tr>
                                    <th>Zaman</th>
                                    <th>Kategori</th>
                                    <th>Eksik</th>
                                    <th>Kaynak</th>
                                    <th>Intent</th>
                                    <th>Dil</th>
                                    <th>CorrId</th>
                                </tr>
                            </thead>
                            <tbody id="handoffInvalidRows">
                                <tr><td colspan="7" style="color:#888;">Henüz yüklenmedi.</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
                
                <!-- 🏨 ElektraWeb Raw Price Test -->
                <div class="card">
                    <h2>🏨 ElektraWeb Price API Test</h2>
                    <p style="color: #888; margin-bottom: 15px; font-size: 0.85rem;">Fiyat sorgusunun ham (raw) response'unu gosterir. createReservation icin gereken ID alanlarini kontrol edin.</p>
                    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 15px;">
                        <div class="form-group">
                            <label>Giris Tarihi</label>
                            <input type="date" id="ewFromDate" value="2025-07-01">
                        </div>
                        <div class="form-group">
                            <label>Cikis Tarihi</label>
                            <input type="date" id="ewToDate" value="2025-07-05">
                        </div>
                        <div class="form-group">
                            <label>Yetiskin</label>
                            <input type="number" id="ewAdult" value="2" min="1" max="6">
                        </div>
                        <div class="form-group">
                            <label>Para Birimi</label>
                            <select id="ewCurrency">
                                <option value="EUR">EUR</option>
                                <option value="USD">USD</option>
                                <option value="TRY">TRY</option>
                                <option value="GBP">GBP</option>
                            </select>
                        </div>
                    </div>
                    <button class="btn btn-primary" onclick="testElektraRawPrice()">🔍 Raw Price Sorgula</button>

                    <div id="ewIdCheck" style="margin-top: 15px; display: none;">
                        <h3 style="color: #ffa502; margin-bottom: 10px;">createReservation ID Kontrolu</h3>
                        <div id="ewIdList" style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 5px;"></div>
                    </div>

                    <details style="margin-top: 15px; background: rgba(0,0,0,0.2); border-radius: 10px; padding: 10px;">
                        <summary style="cursor: pointer; color: #888;">📋 Ham Response (JSON)</summary>
                        <pre id="ewRawResult" style="max-height: 400px; overflow: auto; font-size: 0.8rem; margin-top: 10px; white-space: pre-wrap; color: #aaa;"></pre>
                    </details>
                </div>

                <!-- Sistem Bilgisi -->
                <div class="card">
                    <h2>ℹ️ Sistem Bilgisi</h2>
                    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px;">
                        <div class="person-card">
                            <div class="name">Bot Versiyonu</div>
                            <div class="role">v11 - Monitoring</div>
                        </div>
                        <div class="person-card">
                            <div class="name">Admin Telefon</div>
                            <div class="role" id="sysAdminPhone">-</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        const API = '';
        let activeConversationPhonesTools = [];
        const selectedActivePhonesTools = new Set();

        function updateActiveSelectionInfoTools() {
            const el = document.getElementById('activeSelectionInfoTools');
            if (el) el.textContent = 'Seçili: ' + selectedActivePhonesTools.size;
        }

        function toggleActiveConversationSelectionTools(phone, checked) {
            const key = String(phone || '').trim();
            if (!key) return;
            if (checked) selectedActivePhonesTools.add(key);
            else selectedActivePhonesTools.delete(key);
            updateActiveSelectionInfoTools();
        }

        function selectAllActiveConversationsTools() {
            activeConversationPhonesTools.forEach(phone => selectedActivePhonesTools.add(phone));
            updateActiveSelectionInfoTools();
            loadActiveConversations();
        }

        function clearActiveSelectionTools() {
            selectedActivePhonesTools.clear();
            updateActiveSelectionInfoTools();
            loadActiveConversations();
        }

        async function runBulkActionOnConversationsTools(phones, action) {
            const actionLabel = action === 'purge' ? 'konuşma sıfırlama' : 'kara listeye ekleme';
            const endpointBase = action === 'purge' ? '/purge/' : '/blacklist/add/';
            const uniquePhones = Array.from(new Set((phones || []).map(p => String(p || '').trim()).filter(Boolean)));
            if (!uniquePhones.length) {
                alert('İşlem yapılacak konuşma yok.');
                return;
            }
            if (!confirm(uniquePhones.length + ' konuşma için ' + actionLabel + ' işlemi yapılsın mı?')) return;

            const failed = [];
            await Promise.all(uniquePhones.map(async (phone) => {
                try {
                    const res = await fetch(API + endpointBase + phone, { method: 'POST' });
                    if (action === 'purge') {
                        const data = await res.json();
                        if (!(res.ok && data && data.success)) failed.push(phone);
                        return;
                    }
                    if (!res.ok) failed.push(phone);
                } catch (e) {
                    failed.push(phone);
                }
            }));

            const okCount = uniquePhones.length - failed.length;
            if (failed.length) {
                alert('İşlem tamamlandı. Başarılı: ' + okCount + ', Başarısız: ' + failed.length + '\\nBaşarısız numaralar: ' + failed.join(', '));
            } else {
                alert('İşlem tamamlandı. Toplam: ' + okCount);
            }

            failed.forEach(phone => selectedActivePhonesTools.delete(phone));
            await loadActiveConversations();
        }

        async function purgeAllActiveConversationsTools() {
            await runBulkActionOnConversationsTools(activeConversationPhonesTools, 'purge');
        }

        async function purgeSelectedActiveConversationsTools() {
            await runBulkActionOnConversationsTools(Array.from(selectedActivePhonesTools), 'purge');
        }

        async function blacklistAllActiveConversationsTools() {
            await runBulkActionOnConversationsTools(activeConversationPhonesTools, 'blacklist');
        }

        async function blacklistSelectedActiveConversationsTools() {
            await runBulkActionOnConversationsTools(Array.from(selectedActivePhonesTools), 'blacklist');
        }
        
        // Manuel mesaj gönder
        async function sendMessage() {
            const phone = document.getElementById('msgPhone').value.trim();
            const message = document.getElementById('msgText').value.trim();
            
            if (!phone || !message) {
                alert('Telefon ve mesaj alanları zorunludur!');
                return;
            }
            
            const resultBox = document.getElementById('msgResult');
            resultBox.style.display = 'block';
            resultBox.textContent = 'Gönderiliyor...';
            
            try {
                const res = await fetch(`${API}/admin/send-message?phone=${phone}&message=${encodeURIComponent(message)}`, {
                    method: 'POST'
                });
                const data = await res.json();
                resultBox.textContent = JSON.stringify(data, null, 2);
                
                if (data.status === 'sent') {
                    document.getElementById('msgText').value = '';
                    alert('✅ Mesaj gönderildi!');
                }
            } catch(e) {
                resultBox.textContent = 'Hata: ' + e.message;
            }
        }
        
        // Aktif konuşmaları yükle
        async function loadActiveConversations() {
            const container = document.getElementById('activeConversations');
            container.innerHTML = 'Yükleniyor...';
            
            try {
                const res = await fetch(API + '/admin/active-conversations');
                const data = await res.json();
                const items = Array.isArray(data.conversations) ? data.conversations : [];
                activeConversationPhonesTools = items
                    .map(c => String((c && c.phone) || '').trim())
                    .filter(Boolean);
                const currentPhones = new Set(activeConversationPhonesTools);
                Array.from(selectedActivePhonesTools).forEach((phone) => {
                    if (!currentPhones.has(phone)) selectedActivePhonesTools.delete(phone);
                });
                updateActiveSelectionInfoTools();
                
                if (items.length === 0) {
                    container.innerHTML = '<p style="color:#888;">Son 30 dakikada aktif konuşma yok.</p>';
                    return;
                }
                
                container.innerHTML = items.map(c => {
                    const phone = String((c && c.phone) || '').trim();
                    const selected = selectedActivePhonesTools.has(phone);
                    const pauseReason = String((c && c.paused_reason) || '').trim();
                    const pausedMinutes = Number.isFinite(Number(c && c.paused_minutes)) ? Number(c.paused_minutes) : null;
                    const pauseMeta = c.is_paused
                        ? `<div style="margin-top:6px;color:#ffb4b4;font-size:0.82rem;">Pause nedeni: ${pauseReason || 'belirtilmedi'}${pausedMinutes !== null ? ` • ${pausedMinutes} dk` : ''}</div>`
                        : '';
                    const pauseAlert = c.is_paused
                        ? `<div style="margin-top:8px;padding:8px 10px;border:1px solid #ff6b6b;background:rgba(255,107,107,0.12);border-radius:8px;color:#ffdede;font-size:0.83rem;">
                                Bu sohbet duraklatılmış. Bot cevap vermez.
                                <button class="btn btn-success" onclick="togglePause('${phone}', true)" style="margin-left:8px;padding:4px 8px;">▶️ Resume</button>
                           </div>`
                        : '';
                    return `
                        <div class="conversation-item">
                            <div class="info">
                                <div style="display:flex; align-items:center; gap:8px;">
                                    <label style="display:flex;align-items:center;gap:6px;color:#aaa;font-size:0.85rem;cursor:pointer;">
                                        <input type="checkbox" ${selected ? 'checked' : ''} onchange="toggleActiveConversationSelectionTools('${phone}', this.checked)">
                                        Seç
                                    </label>
                                    <div class="phone">${phone}</div>
                                </div>
                                <div class="msg">${c.last_message || 'Mesaj yok'}</div>
                                <div class="time">${c.minutes_ago} dk önce • ${c.message_count} mesaj • Dil kilidi: ${(c.language_lock || 'en').toUpperCase()}</div>
                                ${pauseMeta}
                                ${pauseAlert}
                            </div>
                            <div class="actions">
                                <span class="status-badge ${c.is_paused ? 'paused' : 'active'}">${c.is_paused ? 'Durduruldu' : 'Aktif'}</span>
                                <button class="btn btn-warning" onclick="purgeConversationByPhone('${phone}')" style="padding:8px 12px;">🧹</button>
                                <button class="btn btn-stop" onclick="addConversationToBlacklist('${phone}')" style="padding:8px 12px;">🚫</button>
                                <button class="btn ${c.is_paused ? 'btn-success' : 'btn-warning'}" onclick="togglePause('${phone}', ${c.is_paused})" style="padding:8px 15px;">
                                    ${c.is_paused ? '▶️' : '⏸️'}
                                </button>
                            </div>
                        </div>
                    `;
                }).join('');
            } catch(e) {
                container.innerHTML = 'Hata: ' + e.message;
            }
        }
        
        // Konuşmayı durdur/devam ettir
        async function togglePause(phone, isPaused) {
            const endpoint = isPaused ? `/resume/${phone}` : `/pause/${phone}`;
            await fetch(API + endpoint, { method: 'POST' });
            loadActiveConversations();
        }

        async function addConversationToBlacklist(phone) {
            if (!phone) return;
            if (!confirm(phone + ' numarası kara listeye eklensin mi?')) return;
            await fetch(API + '/blacklist/add/' + phone, { method: 'POST' });
            loadActiveConversations();
        }

        async function purgeConversationByPhone(phone) {
            if (!phone) return;
            if (!confirm(phone + ' numarasının konuşması sıfırlansın mı?')) return;
            try {
                const res = await fetch(API + '/purge/' + phone, { method: 'POST' });
                const data = await res.json();
                if (!(data && data.success)) {
                    alert('Sıfırlama başarısız: ' + ((data && (data.error || data.detail)) || 'Bilinmeyen hata'));
                }
            } catch (e) {
                alert('Sıfırlama hatası: ' + e.message);
            }
            loadActiveConversations();
        }
        
        // Yetkili kişileri yükle
        async function loadAuthorizedPersons() {
            const container = document.getElementById('authorizedPersons');
            
            try {
                const res = await fetch(API + '/admin/authorized-persons');
                const data = await res.json();
                
                container.innerHTML = Object.values(data.persons).map(p => `
                    <div class="person-card">
                        <div class="name">${p.name}</div>
                        <div class="role">${p.role}</div>
                        <div class="phone">📱 ${p.phone || 'Telefon eklenmedi'}</div>
                    </div>
                `).join('');
            } catch(e) {
                container.innerHTML = 'Hata: ' + e.message;
            }
        }
        
        // Endpoint'leri yükle
        async function loadEndpoints() {
            try {
                const res = await fetch(API + '/admin/all-endpoints');
                const data = await res.json();
                
                const select = document.getElementById('endpointSelect');
                data.endpoints.forEach(ep => {
                    const opt = document.createElement('option');
                    opt.value = JSON.stringify(ep);
                    opt.textContent = `[${ep.method}] ${ep.path}`;
                    select.appendChild(opt);
                });
            } catch(e) {
                console.error(e);
            }
        }
        
        // Endpoint seç
        function selectEndpoint() {
            const select = document.getElementById('endpointSelect');
            if (!select.value) return;
            
            const ep = JSON.parse(select.value);
            document.getElementById('endpointMethod').value = ep.method;
            document.getElementById('endpointUrl').value = ep.path;
        }
        
        // Endpoint test et
        async function testEndpoint() {
            const method = document.getElementById('endpointMethod').value;
            const url = document.getElementById('endpointUrl').value;
            const params = document.getElementById('endpointParams').value;
            
            if (!url) {
                alert('URL gerekli!');
                return;
            }
            
            const resultBox = document.getElementById('endpointResult');
            resultBox.style.display = 'block';
            resultBox.textContent = 'Çalıştırılıyor...';
            
            try {
                const fullUrl = params ? `${API}${url}?${params}` : `${API}${url}`;
                const res = await fetch(fullUrl, { method });
                const data = await res.json();
                resultBox.textContent = JSON.stringify(data, null, 2);
            } catch(e) {
                resultBox.textContent = 'Hata: ' + e.message;
            }
        }
        
        // Hızlı aksiyon
        async function quickAction(url, method) {
            const resultBox = document.getElementById('quickResult');
            resultBox.style.display = 'block';
            resultBox.textContent = 'Çalıştırılıyor...';
            
            try {
                const res = await fetch(API + url, { method });
                const data = await res.json();
                resultBox.textContent = JSON.stringify(data, null, 2);
            } catch(e) {
                resultBox.textContent = 'Hata: ' + e.message;
            }
        }

        async function loadBackendStatus() {
            const statusEl = document.getElementById('backendStatusText');
            try {
                const res = await fetch(API + '/admin/backend/status');
                const data = await res.json();
                const running = !!data.running;
                const pid = data.pid ? ` PID=${data.pid}` : '';
                const started = data.started_at ? ` | baslangic=${data.started_at}` : '';
                statusEl.textContent = running ? `Durum: Calisiyor.${pid}${started}` : 'Durum: Kapali';
            } catch (e) {
                statusEl.textContent = 'Durum sorgulama hatasi: ' + e.message;
            }
        }

        async function startBackendBat() {
            const resultBox = document.getElementById('backendControlResult');
            resultBox.style.display = 'block';
            resultBox.textContent = 'Baslatiliyor...';
            try {
                const res = await fetch(API + '/admin/backend/start', { method: 'POST' });
                const data = await res.json();
                resultBox.textContent = JSON.stringify(data, null, 2);
            } catch (e) {
                resultBox.textContent = 'Hata: ' + e.message;
            }
            loadBackendStatus();
        }

        async function stopBackendBat() {
            const resultBox = document.getElementById('backendControlResult');
            resultBox.style.display = 'block';
            resultBox.textContent = 'Durduruluyor...';
            try {
                const res = await fetch(API + '/admin/backend/stop', { method: 'POST' });
                const data = await res.json();
                resultBox.textContent = JSON.stringify(data, null, 2);
            } catch (e) {
                resultBox.textContent = 'Hata: ' + e.message;
            }
            loadBackendStatus();
        }

        function shortText(v, len = 48) {
            const s = String(v || '').trim();
            if (!s) return '-';
            return s.length > len ? s.slice(0, len) + '…' : s;
        }

        async function loadInvalidHandoffPackets() {
            const countEl = document.getElementById('handoffInvalidCount');
            const rowsEl = document.getElementById('handoffInvalidRows');
            const afterTsInfoEl = document.getElementById('handoffAfterTsInfo');
            const days = Number(document.getElementById('handoffPacketDays').value || 7);
            const afterDeploy = !!document.getElementById('handoffAfterDeploy').checked;

            rowsEl.innerHTML = '<tr><td colspan="7" style="color:#888;">Yükleniyor...</td></tr>';
            countEl.textContent = '...';
            afterTsInfoEl.textContent = '';

            try {
                const res = await fetch(
                    `${API}/admin/handoff/packets?only_invalid=true&days=${encodeURIComponent(days)}&limit=100&after_deploy=${afterDeploy}`
                );
                const data = await res.json();
                const items = Array.isArray(data.items) ? data.items : [];
                countEl.textContent = `Invalid: ${items.length}`;
                if (data.effective_after_ts) {
                    afterTsInfoEl.textContent = `Filtre başlangıcı: ${data.effective_after_ts}`;
                } else if (afterDeploy) {
                    afterTsInfoEl.textContent = 'Deploy zamanı env tanımlı değil (APP_DEPLOYED_AT / DEPLOYED_AT / RELEASE_TS).';
                }

                if (!items.length) {
                    rowsEl.innerHTML = '<tr><td colspan="7" style="color:#00ff88;">Sorunlu packet yok.</td></tr>';
                    return;
                }

                rowsEl.innerHTML = items.map(it => {
                    const dbg = it.debug || {};
                    const missing = Array.isArray(it.missing) ? it.missing.join(', ') : '-';
                    return `
                        <tr>
                            <td>${shortText(it.ts, 22)}</td>
                            <td>${shortText(it.category, 24)}</td>
                            <td style="color:#ff8d8d;">${shortText(missing, 60)}</td>
                            <td>${shortText(dbg.source, 28)}</td>
                            <td>${shortText(dbg.detected_intent, 24)}</td>
                            <td>${shortText((it.packet && it.packet.language_lock) || dbg.language_lock || '-', 8).toUpperCase()}</td>
                            <td title="${String(dbg.correlation_id || '')}">${shortText(dbg.correlation_id, 18)}</td>
                        </tr>
                    `;
                }).join('');
            } catch (e) {
                countEl.textContent = 'Hata';
                rowsEl.innerHTML = `<tr><td colspan="7" style="color:#ff8d8d;">${shortText(e.message, 120)}</td></tr>`;
            }
        }

        function formatMetricValue(v) {
            if (v === null || v === undefined) return 'n/a';
            const n = Number(v);
            if (Number.isNaN(n)) return String(v);
            if (n <= 1) return (n * 100).toFixed(1) + '%';
            return n.toFixed(2);
        }

        async function loadSuccessScorecard() {
            const days = Number(document.getElementById('scorecardDays').value || 7);
            const passFail = document.getElementById('scorecardPassFail');
            const meta = document.getElementById('scorecardMeta');
            const grid = document.getElementById('scorecardGrid');

            passFail.textContent = '...';
            passFail.className = 'pill';
            meta.textContent = '';
            grid.innerHTML = '<div class="metric-item">Yükleniyor...</div>';

            try {
                const res = await fetch(`${API}/admin/metrics/success-scorecard?days=${encodeURIComponent(days)}`);
                const data = await res.json();
                const metrics = data.metrics || {};
                const keys = Object.keys(metrics);
                if (!keys.length) {
                    passFail.textContent = 'No data';
                    grid.innerHTML = '<div class="metric-item">Metrik verisi bulunamadı.</div>';
                    return;
                }

                let passCount = 0;
                let failCount = 0;
                let noDataCount = 0;
                grid.innerHTML = keys.map((key) => {
                    const m = metrics[key] || {};
                    const status = String(m.status || 'no_data');
                    if (status === 'pass') passCount += 1;
                    else if (status === 'fail') failCount += 1;
                    else noDataCount += 1;

                    const badgeClass = status === 'pass' ? 'good' : (status === 'fail' ? 'bad' : '');
                    const statusLabel = status === 'pass' ? 'PASS' : (status === 'fail' ? 'FAIL' : 'NO_DATA');
                    const target = formatMetricValue(m.target);
                    const actual = formatMetricValue(m.actual);
                    return `
                        <div class="metric-item">
                            <div class="metric-name">${shortText(m.label || key, 64)}</div>
                            <div><span class="pill ${badgeClass}">${statusLabel}</span></div>
                            <div class="metric-note">Hedef: <b>${target}</b> | Gerçek: <b>${actual}</b></div>
                            <div class="metric-note">${shortText(m.description || '', 120)}</div>
                        </div>
                    `;
                }).join('');

                passFail.textContent = `PASS:${passCount} FAIL:${failCount} NODATA:${noDataCount}`;
                passFail.className = failCount > 0 ? 'pill bad' : 'pill good';
                meta.textContent = `Toplam event: ${data.event_total || 0} • Auto: ${(data.counts || {}).auto || 0} • Handoff: ${(data.counts || {}).handoff || 0}`;
            } catch (e) {
                passFail.textContent = 'Hata';
                passFail.className = 'pill bad';
                grid.innerHTML = `<div class="metric-item" style="color:#ff8d8d;">${shortText(e.message, 140)}</div>`;
            }
        }
        
        // 🏨 ElektraWeb Raw Price Test
        async function testElektraRawPrice() {
            const fromDate = document.getElementById('ewFromDate').value;
            const toDate = document.getElementById('ewToDate').value;
            const adult = document.getElementById('ewAdult').value;
            const currency = document.getElementById('ewCurrency').value;

            const rawBox = document.getElementById('ewRawResult');
            const idCheck = document.getElementById('ewIdCheck');
            const idList = document.getElementById('ewIdList');

            rawBox.textContent = 'Sorgulanıyor...';
            idCheck.style.display = 'none';

            try {
                const url = `${API}/admin/elektraweb/raw-price?from_date=${fromDate}&to_date=${toDate}&adult=${adult}&currency=${currency}`;
                const res = await fetch(url);
                const data = await res.json();

                rawBox.textContent = JSON.stringify(data, null, 2);

                if (data.success && data.needed_ids_for_booking) {
                    idCheck.style.display = 'block';
                    let html = '';
                    for (const [key, found] of Object.entries(data.needed_ids_for_booking)) {
                        const icon = found ? '✅' : '❌';
                        const color = found ? '#00ff88' : '#ff4757';
                        html += `<div style="padding: 8px; background: rgba(255,255,255,0.05); border-radius: 5px;">
                            <span style="color: ${color}; font-weight: bold;">${icon} ${key}</span>
                        </div>`;
                    }

                    if (data.all_ids_present) {
                        html += `<div style="grid-column: span 2; padding: 10px; background: rgba(0,255,136,0.1); border: 1px solid #00ff88; border-radius: 8px; text-align: center; margin-top: 5px;">
                            ✅ Tum ID'ler mevcut — createReservation entegrasyonu yapilabilir!
                        </div>`;
                    } else {
                        html += `<div style="grid-column: span 2; padding: 10px; background: rgba(255,71,87,0.1); border: 1px solid #ff4757; border-radius: 8px; text-align: center; margin-top: 5px;">
                            ⚠️ Bazi ID'ler eksik — ElektraWeb destek ile iletisime gecin
                        </div>`;
                    }

                    idList.innerHTML = html;
                }
            } catch(e) {
                rawBox.textContent = 'Hata: ' + e.message;
            }
        }

        // Sistem bilgisi yükle
        async function loadSystemInfo() {
            try {
                const res = await fetch(API + '/test/check-config');
                const data = await res.json();
                document.getElementById('sysAdminPhone').textContent = data.admin_phone || '-';
            } catch(e) {}
        }
        
        // Sayfa yüklendiğinde
        loadActiveConversations();
        loadAuthorizedPersons();
        loadEndpoints();
        loadSystemInfo();
        loadBackendStatus();
        loadInvalidHandoffPackets();
        loadSuccessScorecard();
        
        // Otomatik yenile
        setInterval(loadActiveConversations, 30000);
    </script>
</body>
</html>
"""

HOTEL_BOOKINGS_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Otel Rezervasyon Talepleri - Kassandra Admin</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, sans-serif; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); min-height: 100vh; color: #fff; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        h1 { text-align: center; margin-bottom: 25px; font-size: 2rem; }
        h1 span { color: #00d4ff; }

        .nav-links { text-align: center; margin-bottom: 20px; background: rgba(0,0,0,0.3); padding: 15px; border-radius: 10px; }
        .nav-links a { color: #00d4ff; text-decoration: none; margin: 0 8px; padding: 10px 18px; border: 1px solid #00d4ff; border-radius: 5px; display: inline-block; margin-bottom: 5px; font-size: 0.9rem; }
        .nav-links a:hover { background: #00d4ff; color: #000; }
        .nav-links a.active { background: #00d4ff; color: #000; font-weight: bold; }

        /* Stats Row */
        .stats-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 15px; margin-bottom: 25px; }
        .stat-card { background: rgba(255,255,255,0.08); border-radius: 15px; padding: 20px; text-align: center; backdrop-filter: blur(10px); }
        .stat-number { font-size: 2.2rem; font-weight: bold; }
        .stat-label { color: #aaa; margin-top: 5px; font-size: 0.85rem; }
        .stat-pending { color: #ffa502; }
        .stat-approved { color: #00ff88; }
        .stat-rejected { color: #ff4757; }
        .stat-total { color: #00d4ff; }

        /* Section */
        .section { margin-bottom: 30px; }
        .section-title { font-size: 1.3rem; margin-bottom: 15px; padding-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.1); }

        /* Booking Card */
        .booking-card { background: rgba(255,255,255,0.08); border-radius: 15px; padding: 20px; margin-bottom: 15px; backdrop-filter: blur(10px); border-left: 4px solid #ffa502; transition: transform 0.2s; }
        .booking-card:hover { transform: translateY(-2px); }
        .booking-card.status-approved, .booking-card.status-elektra_created { border-left-color: #00ff88; }
        .booking-card.status-rejected { border-left-color: #ff4757; }
        .booking-card.status-elektra_failed { border-left-color: #ff6348; }

        .booking-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; flex-wrap: wrap; gap: 10px; }
        .booking-id { font-size: 1.1rem; font-weight: bold; color: #00d4ff; }
        .booking-date { color: #888; font-size: 0.85rem; }
        .badge { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 0.75rem; font-weight: bold; text-transform: uppercase; }
        .badge-pending { background: rgba(255,165,2,0.2); color: #ffa502; border: 1px solid #ffa502; }
        .badge-approved { background: rgba(0,255,136,0.2); color: #00ff88; border: 1px solid #00ff88; }
        .badge-rejected { background: rgba(255,71,87,0.2); color: #ff4757; border: 1px solid #ff4757; }
        .badge-elektra_created { background: rgba(0,212,255,0.2); color: #00d4ff; border: 1px solid #00d4ff; }
        .badge-elektra_failed { background: rgba(255,99,72,0.2); color: #ff6348; border: 1px solid #ff6348; }
        .badge-cancelled { background: rgba(255,255,255,0.15); color: #ddd; border: 1px solid #bbb; }

        .booking-details { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; margin-bottom: 15px; }
        .detail-item { }
        .detail-label { color: #888; font-size: 0.8rem; margin-bottom: 2px; }
        .detail-value { font-size: 0.95rem; }

        .booking-actions { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.1); }
        .btn { padding: 10px 25px; border: none; border-radius: 8px; font-size: 0.9rem; cursor: pointer; font-weight: bold; transition: all 0.3s; }
        .btn:hover { transform: scale(1.05); }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
        .btn-approve { background: linear-gradient(135deg, #00ff88, #00d4ff); color: #1a1a2e; }
        .btn-reject { background: linear-gradient(135deg, #ff4757, #ff6b81); color: #fff; }
        .btn-retry { background: linear-gradient(135deg, #ffa502, #ff6348); color: #fff; }
        .btn-create { background: linear-gradient(135deg, #2ed573, #1e90ff); color: #fff; }
        .btn-update { background: linear-gradient(135deg, #70a1ff, #00d4ff); color: #fff; }
        .btn-cancel { background: linear-gradient(135deg, #ff6b81, #ff4757); color: #fff; }
        .btn-detail { background: rgba(255,255,255,0.1); color: #00d4ff; border: 1px solid #00d4ff; }
        .btn-refresh { background: rgba(0,212,255,0.15); color: #00d4ff; border: 1px solid #00d4ff; padding: 8px 20px; border-radius: 8px; cursor: pointer; font-size: 0.9rem; margin-bottom: 15px; }
        .btn-refresh:hover { background: #00d4ff; color: #000; }
        .manual-form { display:grid; grid-template-columns: repeat(auto-fit,minmax(180px,1fr)); gap:10px; background: rgba(255,255,255,0.06); border-radius:12px; padding:14px; margin-bottom:15px; }
        .manual-form input, .manual-form select { width:100%; padding:10px; border-radius:8px; border:1px solid #444; background:#2a2a4a; color:#fff; font-size:0.9rem; }
        .manual-form .full { grid-column: 1/-1; }

        /* Reject Modal */
        .modal-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); z-index: 1000; justify-content: center; align-items: center; }
        .modal-overlay.active { display: flex; }
        .modal { background: #1e2a3a; border-radius: 15px; padding: 30px; width: 90%; max-width: 500px; }
        .modal h3 { margin-bottom: 15px; }
        .modal textarea { width: 100%; padding: 12px; border-radius: 8px; border: 1px solid #444; background: #2a2a4a; color: #fff; font-size: 0.95rem; min-height: 100px; resize: vertical; margin-bottom: 15px; }
        .modal input[type="date"] { width: 100%; padding: 12px; border-radius: 8px; border: 1px solid #444; background: #2a2a4a; color: #fff; font-size: 0.95rem; margin-bottom: 12px; }
        .modal-actions { display: flex; gap: 10px; justify-content: flex-end; }

        /* Empty State */
        .empty-state { text-align: center; padding: 60px 20px; color: #666; }
        .empty-state .icon { font-size: 3rem; margin-bottom: 15px; }
        .empty-state p { font-size: 1.1rem; }

        /* Loading */
        .loading { text-align: center; padding: 40px; color: #888; }

        /* Toast */
        .toast { position: fixed; bottom: 30px; right: 30px; padding: 15px 25px; border-radius: 10px; color: #fff; font-weight: bold; z-index: 2000; display: none; animation: slideIn 0.3s ease; }
        .toast.success { background: rgba(0,255,136,0.9); color: #1a1a2e; }
        .toast.error { background: rgba(255,71,87,0.9); }
        @keyframes slideIn { from { transform: translateX(100px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }

        /* History filter */
        .filter-bar { display: flex; gap: 10px; margin-bottom: 15px; flex-wrap: wrap; align-items: center; }
        .filter-bar select { padding: 8px 15px; border-radius: 8px; border: 1px solid #444; background: #2a2a4a; color: #fff; font-size: 0.85rem; }
    </style>
</head>
<body>
    <div class="container">
        <div class="nav-links">
            <a href="/admin" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; font-weight: bold;">&#127968; Ana Sayfa</a>
            <a href="/admin/dashboard">&#128202; Dashboard</a>
            <a href="/admin/reservations-page">&#127861; Rezervasyonlar</a>
            <a href="/admin/hotel-bookings-page" class="active">&#127976; Otel Rez.</a>
            <a href="/admin/transfer-reservations-page">&#128652; Transfer Rez.</a>
            <a href="/admin/reminders-page">&#128197; Hat&#305;rlatmalar</a>
            <a href="/admin/qa/stats">&#128270; QA Stats</a>
            <a href="/admin/tools">&#9881; Ara&#231;lar</a>
        </div>

        <h1>&#127976; Otel <span>Rezervasyon Talepleri</span></h1>

        <!-- Stats -->
        <div class="stats-row">
            <div class="stat-card">
                <div class="stat-number stat-pending" id="statPending">-</div>
                <div class="stat-label">Onay Bekleyen</div>
            </div>
            <div class="stat-card">
                <div class="stat-number stat-approved" id="statApproved">-</div>
                <div class="stat-label">Onayland&#305;</div>
            </div>
            <div class="stat-card">
                <div class="stat-number stat-rejected" id="statRejected">-</div>
                <div class="stat-label">Reddedildi</div>
            </div>
            <div class="stat-card">
                <div class="stat-number stat-total" id="statTotal">-</div>
                <div class="stat-label">Toplam</div>
            </div>
        </div>

        <!-- Manual Test Create -->
        <div class="section">
            <div class="section-title">&#129514; Manual Test Rezervasyonu</div>
            <div class="manual-form">
                <input id="mcSourceBookingId" placeholder="Kaynak Booking ID (opsiyonel)">
                <button class="btn btn-detail" onclick="fillFromSourceBooking()" type="button">Kaynak ID'den Doldur</button>
                <input id="mcCustomerPhone" placeholder="Musteri Telefonu (905...)">
                <button class="btn btn-detail" onclick="fillFromPhoneTemplate()" type="button">Telefondan Otomatik Doldur</button>
                <input id="mcGuestFirstName" placeholder="Ad">
                <input id="mcGuestLastName" placeholder="Soyad">
                <input id="mcCheckIn" type="date" placeholder="Giris">
                <input id="mcCheckOut" type="date" placeholder="Cikis">
                <input id="mcAdultCount" type="number" min="1" value="2" placeholder="Yetiskin">
                <input id="mcChildAges" placeholder="Cocuk Yaslari (orn: 12,6)">
                <input id="mcRoomTypeDisplay" placeholder="Oda Adi (orn: Premium - Jakuzili)">
                <input id="mcRoomTypeId" placeholder="room_type_id">
                <input id="mcBoardTypeId" placeholder="board_type_id">
                <input id="mcRateTypeId" placeholder="rate_type_id">
                <input id="mcRateCodeId" placeholder="rate_code_id">
                <input id="mcPriceAgencyId" placeholder="price_agency_id">
                <input id="mcTotalPrice" placeholder="Toplam Fiyat">
                <button class="btn btn-update full" onclick="fillFromLiveQuote()" type="button">Elektra'dan Canli Fiyat/ID Doldur</button>
                <button class="btn btn-create full" onclick="createManualBooking()">+ Test Rezervasyonu Olustur</button>
            </div>
        </div>

        <!-- Pending Section -->
        <div class="section">
            <div class="section-title">&#9200; Onay Bekleyen Talepler</div>
            <button class="btn-refresh" onclick="loadAll()">&#128260; Yenile</button>
            <div id="pendingList"><div class="loading">Y&#252;kleniyor...</div></div>
        </div>

        <!-- History Section -->
        <div class="section">
            <div class="section-title">&#128218; Ge&#231;mi&#351;</div>
            <div class="filter-bar">
                <select id="statusFilter" onchange="loadHistory()">
                    <option value="">T&#252;m&#252;</option>
                    <option value="pending_approval">Bekleyen</option>
                    <option value="approved">Onayl&#305;</option>
                    <option value="elektra_created">ElektraWeb Olu&#351;turuldu</option>
                    <option value="rejected">Reddedildi</option>
                    <option value="elektra_failed">Hata</option>
                    <option value="cancelled">Iptal</option>
                </select>
            </div>
            <div id="historyList"><div class="loading">Y&#252;kleniyor...</div></div>
        </div>
    </div>

    <!-- Reject Modal -->
    <div class="modal-overlay" id="rejectModal">
        <div class="modal">
            <h3>&#10060; Rezervasyon Reddi</h3>
            <p style="color:#aaa; margin-bottom:15px;">Booking #<span id="rejectBookingId"></span></p>
            <textarea id="rejectReason" placeholder="Red nedeni (opsiyonel)..."></textarea>
            <div class="modal-actions">
                <button class="btn btn-detail" onclick="closeRejectModal()">&#304;ptal</button>
                <button class="btn btn-reject" onclick="confirmReject()">Reddet</button>
            </div>
        </div>
    </div>

    <!-- Update Modal -->
    <div class="modal-overlay" id="updateModal">
        <div class="modal">
            <h3>&#9998; Elektra Rezervasyon Guncelle</h3>
            <p style="color:#aaa; margin-bottom:15px;">Booking #<span id="updateBookingId"></span></p>
            <label class="detail-label">Yeni Giris Tarihi (opsiyonel)</label>
            <input type="date" id="updateCheckIn" />
            <label class="detail-label">Yeni Cikis Tarihi (opsiyonel)</label>
            <input type="date" id="updateCheckOut" />
            <label class="detail-label">Not / Ozel Istek (opsiyonel)</label>
            <textarea id="updateNote" placeholder="Orn: Erken check-in talebi"></textarea>
            <div class="modal-actions">
                <button class="btn btn-detail" onclick="closeUpdateModal()">Iptal</button>
                <button class="btn btn-update" onclick="confirmUpdateModal()">Guncelle</button>
            </div>
        </div>
    </div>

    <!-- Toast -->
    <div class="toast" id="toast"></div>

    <script>
        let currentRejectId = null;
        let currentUpdateId = null;

        // ---- HELPERS ----
        function showToast(msg, type) {
            const t = document.getElementById('toast');
            t.textContent = msg;
            t.className = 'toast ' + type;
            t.style.display = 'block';
            setTimeout(() => { t.style.display = 'none'; }, 4000);
        }

        function formatDate(d) {
            if (!d) return '-';
            try { return new Date(d).toLocaleDateString('tr-TR', {day:'2-digit', month:'2-digit', year:'numeric'}); } catch(e) { return d; }
        }
        function formatDateTime(d) {
            if (!d) return '-';
            try { return new Date(d).toLocaleString('tr-TR', {day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit'}); } catch(e) { return d; }
        }

        function badgeClass(status) {
            const map = {
                'pending_approval': 'badge-pending',
                'approved': 'badge-approved',
                'rejected': 'badge-rejected',
                'elektra_created': 'badge-elektra_created',
                'elektra_failed': 'badge-elektra_failed',
                'cancelled': 'badge-cancelled'
            };
            return map[status] || 'badge-pending';
        }

        function statusLabel(status) {
            const map = {
                'pending_approval': 'Onay Bekliyor',
                'approved': 'Onaylandi',
                'rejected': 'Reddedildi',
                'elektra_created': 'ElektraWeb Olusturuldu',
                'elektra_failed': 'ElektraWeb Hatasi',
                'cancelled': 'Iptal'
            };
            return map[status] || status;
        }

        function parseChildAges(raw) {
            if (!raw) return [];
            if (Array.isArray(raw)) {
                return raw.map(x => parseInt(x, 10)).filter(x => Number.isInteger(x) && x > 0 && x <= 17);
            }
            if (typeof raw === 'string') {
                const t = raw.trim();
                if (!t || t === '[]') return [];
                try {
                    const arr = JSON.parse(t);
                    if (Array.isArray(arr)) {
                        return arr.map(x => parseInt(x, 10)).filter(x => Number.isInteger(x) && x > 0 && x <= 17);
                    }
                } catch (e) {
                    const nums = t.match(/\\d+/g) || [];
                    return nums.map(x => parseInt(x, 10)).filter(x => Number.isInteger(x) && x > 0 && x <= 17);
                }
            }
            return [];
        }

        // ---- RENDER ----
        function renderBookingCard(b, isPending) {
            const price = b.discounted_price || b.total_price || 0;
            const refund = b.is_refundable ? 'Iade Edilebilir' : 'Iade Edilemez';
            const guestName = ((b.guest_first_name || '') + ' ' + (b.guest_last_name || '')).trim() || '-';
            const specialReq = b.special_requests || '-';
            const nights = b.nights || '-';
            const childAges = parseChildAges(b.child_ages);
            const childCount = childAges.length;
            const guestSummary = `${b.adult_count || 0} Yeti&#351;kin${childCount > 0 ? ' + ' + childCount + ' &#199;ocuk' : ''}`;
            const childAgesText = childCount > 0 ? childAges.join(', ') + ' ya&#351;' : '-';

            let actionsHtml = '';
            if (isPending) {
                actionsHtml = `
                    <button class="btn btn-approve" onclick="approveBooking(${b.id})">&#10004; ONAYLA</button>
                    <button class="btn btn-reject" onclick="openRejectModal(${b.id})">&#10006; REDDET</button>
                `;
            } else if (b.status === 'elektra_failed') {
                actionsHtml = `
                    <button class="btn btn-retry" onclick="retryBooking(${b.id})">&#128260; Tekrar Dene</button>
                    <button class="btn btn-create" onclick="recreateBooking(${b.id})">+ Yeniden Olustur</button>
                `;
            } else if (b.status === 'cancelled' || b.status === 'rejected') {
                actionsHtml = `
                    <button class="btn btn-create" onclick="recreateBooking(${b.id})">+ Yeniden Olustur</button>
                `;
            }
            if (!isPending && (b.status === 'approved' || b.status === 'elektra_created' || b.status === 'elektra_failed')) {
                actionsHtml += `
                    <button class="btn btn-detail" onclick="syncElektraBooking(${b.id})">&#128260; Elektra Senkron</button>
                    <button class="btn btn-update" onclick="forceDepositZero(${b.id})">&#37; Depozito 0</button>
                    <button class="btn btn-detail" onclick="runPaymentTryTest(${b.id})">&#129514; TRY Test</button>
                `;
            }
            if (!isPending && (b.status === 'approved' || b.status === 'elektra_created')) {
                actionsHtml += `
                    <button class="btn btn-update" onclick="openUpdateModal(${b.id})">&#9998; Elektra Guncelle</button>
                    <button class="btn btn-cancel" onclick="cancelElektraBooking(${b.id})">&#9940; Elektra Iptal</button>
                `;
            }

            let extraInfo = '';
            if (b.elektra_reservation_id) {
                extraInfo += `<div class="detail-item"><div class="detail-label">ElektraWeb Rez. ID</div><div class="detail-value" style="color:#00d4ff;">${b.elektra_reservation_id}</div></div>`;
            }
            if (b.rejection_reason) {
                extraInfo += `<div class="detail-item"><div class="detail-label">Red Nedeni</div><div class="detail-value" style="color:#ff4757;">${b.rejection_reason}</div></div>`;
            }
            if (b.admin_notes) {
                extraInfo += `<div class="detail-item"><div class="detail-label">Admin Notu</div><div class="detail-value">${b.admin_notes}</div></div>`;
            }

            return `
                <div class="booking-card status-${b.status || 'pending_approval'}">
                    <div class="booking-header">
                        <div>
                            <span class="booking-id">Talep #${b.id}</span>
                            <span class="badge ${badgeClass(b.status)}">${statusLabel(b.status)}</span>
                        </div>
                        <div class="booking-date">${formatDateTime(b.created_at)}</div>
                    </div>
                    <div class="booking-details">
                        <div class="detail-item">
                            <div class="detail-label">&#128100; Misafir</div>
                            <div class="detail-value">${guestName}</div>
                        </div>
                        <div class="detail-item">
                            <div class="detail-label">&#128222; Telefon</div>
                            <div class="detail-value">${b.customer_phone || '-'}</div>
                        </div>
                        <div class="detail-item">
                            <div class="detail-label">&#128719; Oda Tipi</div>
                            <div class="detail-value">${b.room_type_display || b.room_type || '-'}</div>
                        </div>
                        <div class="detail-item">
                            <div class="detail-label">&#128197; Giri&#351; - &#199;&#305;k&#305;&#351;</div>
                            <div class="detail-value">${formatDate(b.check_in)} &#8594; ${formatDate(b.check_out)} (${nights} gece)</div>
                        </div>
                        <div class="detail-item">
                            <div class="detail-label">&#128176; Fiyat</div>
                            <div class="detail-value" style="color:#00ff88; font-weight:bold;">${price} ${b.currency || 'EUR'}</div>
                        </div>
                        <div class="detail-item">
                            <div class="detail-label">&#128260; &#304;ade</div>
                            <div class="detail-value">${refund}</div>
                        </div>
                        <div class="detail-item">
                            <div class="detail-label">&#128101; Ki&#351;i</div>
                            <div class="detail-value">${guestSummary}</div>
                        </div>
                        <div class="detail-item">
                            <div class="detail-label">&#129490; &#199;ocuk Ya&#351;lar&#305;</div>
                            <div class="detail-value">${childAgesText}</div>
                        </div>
                        <div class="detail-item">
                            <div class="detail-label">&#128221; &#214;zel &#304;stek</div>
                            <div class="detail-value">${specialReq}</div>
                        </div>
                        ${extraInfo}
                    </div>
                    ${actionsHtml ? '<div class="booking-actions">' + actionsHtml + '</div>' : ''}
                </div>
            `;
        }

        // ---- API CALLS ----
        async function loadStats() {
            try {
                const res = await fetch('/admin/hotel-bookings/stats');
                const data = await res.json();
                document.getElementById('statPending').textContent = data.pending || 0;
                document.getElementById('statApproved').textContent = (data.approved || 0) + (data.elektra_created || 0);
                document.getElementById('statRejected').textContent = data.rejected || 0;
                document.getElementById('statTotal').textContent = data.total || 0;
            } catch(e) {
                console.error('Stats error:', e);
            }
        }

        async function loadPending() {
            const container = document.getElementById('pendingList');
            try {
                const res = await fetch('/admin/hotel-bookings/pending');
                const data = await res.json();
                const bookings = data.bookings || [];
                if (bookings.length === 0) {
                    container.innerHTML = '<div class="empty-state"><div class="icon">&#9989;</div><p>Onay bekleyen talep yok</p></div>';
                } else {
                    container.innerHTML = bookings.map(b => renderBookingCard(b, true)).join('');
                }
            } catch(e) {
                container.innerHTML = '<div class="empty-state"><div class="icon">&#9888;</div><p>Y&#252;klenemedi</p></div>';
            }
        }

        async function loadHistory() {
            const container = document.getElementById('historyList');
            try {
                const res = await fetch('/admin/hotel-bookings/all?limit=50');
                const data = await res.json();
                let bookings = data.bookings || [];

                const filter = document.getElementById('statusFilter').value;
                if (filter) {
                    bookings = bookings.filter(b => b.status === filter);
                }

                // Pending olanlar zaten ustte gorunuyor, burada sadece history
                bookings = bookings.filter(b => b.status !== 'pending_approval');

                if (bookings.length === 0) {
                    container.innerHTML = '<div class="empty-state"><div class="icon">&#128218;</div><p>Kay&#305;t bulunamad&#305;</p></div>';
                } else {
                    container.innerHTML = bookings.map(b => renderBookingCard(b, false)).join('');
                }
            } catch(e) {
                container.innerHTML = '<div class="empty-state"><div class="icon">&#9888;</div><p>Y&#252;klenemedi</p></div>';
            }
        }

        async function loadAll() {
            await Promise.all([loadStats(), loadPending(), loadHistory()]);
        }

        // ---- ACTIONS ----
        async function approveBooking(id) {
            if (!confirm('Bu rezervasyonu onaylamak istediginize emin misiniz?\\n\\nOnay sonrasi ElektraWeb\\'de olusturulacak ve musteriye bildirilecektir.')) return;
            try {
                const btn = event.target;
                btn.disabled = true;
                btn.textContent = 'Isleniyor...';
                const res = await fetch(`/admin/hotel-bookings/${id}/approve`, {method: 'POST'});
                const data = await res.json();
                if (data.success) {
                    showToast('Rezervasyon onaylandi! ElektraWeb ID: ' + (data.elektra_reservation_id || '-'), 'success');
                    loadAll();
                } else {
                    if (data.error_code === 'ELEKTRA_CONFIG_MISSING_WALKIN') {
                        showToast('Elektra ayari eksik: WALKIN acenta ID (ELEKTRA_WALKIN_AGENCY_ID) tanimlanmali.', 'error');
                    } else {
                        showToast('Hata: ' + (data.error || 'Bilinmeyen hata'), 'error');
                    }
                    btn.disabled = false;
                    btn.textContent = '\\u2714 ONAYLA';
                }
            } catch(e) {
                showToast('Baglanti hatasi', 'error');
            }
        }

        function openRejectModal(id) {
            currentRejectId = id;
            document.getElementById('rejectBookingId').textContent = id;
            document.getElementById('rejectReason').value = '';
            document.getElementById('rejectModal').classList.add('active');
        }
        function closeRejectModal() {
            document.getElementById('rejectModal').classList.remove('active');
            currentRejectId = null;
        }
        async function confirmReject() {
            if (!currentRejectId) return;
            const reason = document.getElementById('rejectReason').value.trim();
            try {
                const res = await fetch(`/admin/hotel-bookings/${currentRejectId}/reject?reason=${encodeURIComponent(reason)}`, {method: 'POST'});
                const data = await res.json();
                if (data.success) {
                    showToast('Talep reddedildi, musteri bilgilendirildi', 'success');
                    closeRejectModal();
                    loadAll();
                } else {
                    showToast('Hata: ' + (data.error || 'Bilinmeyen hata'), 'error');
                }
            } catch(e) {
                showToast('Baglanti hatasi', 'error');
            }
        }

        async function retryBooking(id) {
            if (!confirm('ElektraWeb olusturma tekrar denenecek. Devam?')) return;
            try {
                const btn = event.target;
                btn.disabled = true;
                btn.textContent = 'Deneniyor...';
                const res = await fetch(`/admin/hotel-bookings/${id}/retry`, {method: 'POST'});
                const data = await res.json();
                if (data.success) {
                    showToast('Basarili! ElektraWeb ID: ' + (data.elektra_reservation_id || '-'), 'success');
                    loadAll();
                } else {
                    showToast('Hata: ' + (data.error || 'Bilinmeyen hata'), 'error');
                    btn.disabled = false;
                    btn.textContent = '\\u{1F504} Tekrar Dene';
                }
            } catch(e) {
                showToast('Baglanti hatasi', 'error');
            }
        }

        async function recreateBooking(id) {
            if (!confirm('Bu kaydin kopyasi pending olarak yeniden olusturulsun mu?')) return;
            try {
                const res = await fetch(`/admin/hotel-bookings/${id}/recreate`, {method: 'POST'});
                const data = await res.json();
                if (data.success) {
                    showToast(`Yeni talep olusturuldu (#${data.new_booking_id || '-'})`, 'success');
                    loadAll();
                } else {
                    showToast('Yeniden olusturma hatasi: ' + (data.error || 'Bilinmeyen hata'), 'error');
                }
            } catch (e) {
                showToast('Baglanti hatasi', 'error');
            }
        }

        async function createManualBooking() {
            const sourceBookingId = (document.getElementById('mcSourceBookingId').value || '').trim();
            const payload = {
                source_booking_id: sourceBookingId ? parseInt(sourceBookingId, 10) : undefined,
                customer_phone: (document.getElementById('mcCustomerPhone').value || '').trim(),
                guest_first_name: (document.getElementById('mcGuestFirstName').value || '').trim(),
                guest_last_name: (document.getElementById('mcGuestLastName').value || '').trim(),
                check_in: (document.getElementById('mcCheckIn').value || '').trim(),
                check_out: (document.getElementById('mcCheckOut').value || '').trim(),
                adult_count: parseInt((document.getElementById('mcAdultCount').value || '1').trim(), 10) || 1,
                child_ages: (document.getElementById('mcChildAges').value || '').trim(),
                room_type_display: (document.getElementById('mcRoomTypeDisplay').value || '').trim(),
                room_type_id: parseInt((document.getElementById('mcRoomTypeId').value || '0').trim(), 10) || 0,
                board_type_id: parseInt((document.getElementById('mcBoardTypeId').value || '0').trim(), 10) || 0,
                rate_type_id: parseInt((document.getElementById('mcRateTypeId').value || '0').trim(), 10) || 0,
                rate_code_id: parseInt((document.getElementById('mcRateCodeId').value || '0').trim(), 10) || 0,
                price_agency_id: parseInt((document.getElementById('mcPriceAgencyId').value || '0').trim(), 10) || 0,
                total_price: parseFloat((document.getElementById('mcTotalPrice').value || '0').trim()) || 0
            };
            try {
                const res = await fetch('/admin/hotel-bookings/manual-create', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload),
                });
                const data = await res.json();
                if (data.success) {
                    showToast(`Manual test talebi olustu (#${data.booking_id || '-'})`, 'success');
                    loadAll();
                } else {
                    showToast('Manual olusturma hatasi: ' + (data.error || 'Bilinmeyen hata'), 'error');
                }
            } catch (e) {
                showToast('Baglanti hatasi', 'error');
            }
        }

        function fillManualFormFromBooking(b) {
            if (!b) return;
            const childAges = parseChildAges(b.child_ages);
            document.getElementById('mcCustomerPhone').value = (b.customer_phone || b.guest_phone || '');
            document.getElementById('mcGuestFirstName').value = (b.guest_first_name || '');
            document.getElementById('mcGuestLastName').value = (b.guest_last_name || '');
            document.getElementById('mcCheckIn').value = ((b.check_in || '').slice(0, 10));
            document.getElementById('mcCheckOut').value = ((b.check_out || '').slice(0, 10));
            document.getElementById('mcAdultCount').value = (b.adult_count || 1);
            document.getElementById('mcChildAges').value = childAges.join(',');
            document.getElementById('mcRoomTypeDisplay').value = (b.room_type_display || b.room_type || '');
            document.getElementById('mcRoomTypeId').value = (b.room_type_id || '');
            document.getElementById('mcBoardTypeId').value = (b.board_type_id || '');
            document.getElementById('mcRateTypeId').value = (b.rate_type_id || '');
            document.getElementById('mcRateCodeId').value = (b.rate_code_id || '');
            document.getElementById('mcPriceAgencyId').value = (b.price_agency_id || '');
            document.getElementById('mcTotalPrice').value = (b.discounted_price || b.total_price || '');
        }

        async function fillFromSourceBooking() {
            const id = (document.getElementById('mcSourceBookingId').value || '').trim();
            if (!id) {
                showToast('Kaynak booking ID girin', 'error');
                return;
            }
            try {
                const res = await fetch(`/admin/hotel-bookings/${id}`);
                const data = await res.json();
                if (data && !data.error) {
                    fillManualFormFromBooking(data);
                    showToast('Form kaynak booking ile dolduruldu', 'success');
                } else {
                    showToast('Kaynak booking bulunamadi', 'error');
                }
            } catch (e) {
                showToast('Baglanti hatasi', 'error');
            }
        }

        async function fillFromPhoneTemplate() {
            const phone = (document.getElementById('mcCustomerPhone').value || '').trim();
            if (!phone) {
                showToast('Telefon girin', 'error');
                return;
            }
            try {
                const res = await fetch(`/admin/hotel-bookings/template/by-phone?phone=${encodeURIComponent(phone)}`);
                const data = await res.json();
                if (data.success && data.template) {
                    fillManualFormFromBooking(data.template);
                    document.getElementById('mcSourceBookingId').value = data.template.id || '';
                    showToast(`Template bulundu (#${data.template.id || '-'})`, 'success');
                } else {
                    showToast(data.error || 'Uygun template bulunamadi', 'error');
                }
            } catch (e) {
                showToast('Baglanti hatasi', 'error');
            }
        }

        async function fillFromLiveQuote() {
            const payload = {
                check_in: (document.getElementById('mcCheckIn').value || '').trim(),
                check_out: (document.getElementById('mcCheckOut').value || '').trim(),
                adult_count: parseInt((document.getElementById('mcAdultCount').value || '1').trim(), 10) || 1,
                child_ages: (document.getElementById('mcChildAges').value || '').trim(),
                room_type_display: (document.getElementById('mcRoomTypeDisplay').value || '').trim(),
                currency: 'EUR',
            };
            if (!payload.check_in || !payload.check_out) {
                showToast('Canli quote icin check-in/check-out zorunlu', 'error');
                return;
            }
            try {
                const res = await fetch('/admin/hotel-bookings/manual-quote-fill', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload),
                });
                const data = await res.json();
                if (data.success && data.fill) {
                    const f = data.fill;
                    document.getElementById('mcRoomTypeId').value = f.room_type_id || '';
                    document.getElementById('mcBoardTypeId').value = f.board_type_id || '';
                    document.getElementById('mcRateTypeId').value = f.rate_type_id || '';
                    document.getElementById('mcRateCodeId').value = f.rate_code_id || '';
                    document.getElementById('mcPriceAgencyId').value = f.price_agency_id || '';
                    document.getElementById('mcTotalPrice').value = f.total_price || '';
                    if (!document.getElementById('mcRoomTypeDisplay').value && f.room_type_display) {
                        document.getElementById('mcRoomTypeDisplay').value = f.room_type_display;
                    }
                    showToast('Canli quote bulundu: teknik ID alanlari dolduruldu', 'success');
                } else {
                    if (Array.isArray(data.suggestions) && data.suggestions.length > 0) {
                        const paxVal = (pax, key) => {
                            if (!pax || typeof pax !== 'object') return '-';
                            const v = pax[key];
                            return (v === undefined || v === null || v === '') ? '-' : String(v);
                        };
                        const reqVal = (obj, key) => {
                            if (!obj || typeof obj !== 'object') return '-';
                            const v = obj[key];
                            return (v === undefined || v === null || v === '') ? '-' : String(v);
                        };
                        const lines = data.suggestions.map((s, i) =>
                            `${i+1}) ${s.room || '-'} | pax a/e/y/b=${paxVal(s.pax, 'adult')} / ${paxVal(s.pax, 'elder-child-count')} / ${paxVal(s.pax, 'younger-child-count')} / ${paxVal(s.pax, 'baby-count')} | fiyat=${(s.price === undefined || s.price === null || s.price === '') ? '-' : s.price}`
                        );
                        const pick = window.prompt(
                            `Birebir quote yok.\nIstenen pax: a/e/y/b=${reqVal(data.requested, 'adult')} / ${reqVal(data.requested, 'elder-child-count')} / ${reqVal(data.requested, 'younger-child-count')} / ${reqVal(data.requested, 'baby-count')}\n\nAdaylar:\n${lines.join('\\n')}\n\nDoldurmak icin aday numarasi gir (1-${data.suggestions.length}), iptal icin bos birak:`,
                            ''
                        );
                        const idx = parseInt((pick || '').trim(), 10);
                        if (Number.isInteger(idx) && idx >= 1 && idx <= data.suggestions.length) {
                            const s = data.suggestions[idx - 1];
                            document.getElementById('mcRoomTypeId').value = s.room_type_id || '';
                            document.getElementById('mcBoardTypeId').value = s.board_type_id || '';
                            document.getElementById('mcRateTypeId').value = s.rate_type_id || '';
                            document.getElementById('mcRateCodeId').value = s.rate_code_id || '';
                            document.getElementById('mcPriceAgencyId').value = s.price_agency_id || '';
                            document.getElementById('mcTotalPrice').value = s.price || '';
                            if (s.room) document.getElementById('mcRoomTypeDisplay').value = s.room;
                            showToast('Aday quote forma yazildi. Onaylamadan once pax uyumunu kontrol et.', 'success');
                        } else {
                            showToast(data.error || 'Canli quote bulunamadi', 'error');
                        }
                    } else {
                        showToast(data.error || 'Canli quote bulunamadi', 'error');
                    }
                }
            } catch (e) {
                showToast('Baglanti hatasi', 'error');
            }
        }

        async function syncElektraBooking(id) {
            try {
                const btn = event.target;
                btn.disabled = true;
                btn.textContent = 'Senkron...';
                const res = await fetch(`/admin/hotel-bookings/${id}/elektra/sync`, {method: 'POST'});
                const data = await res.json();
                if (data.success) {
                    showToast('Elektra bilgisi guncellendi', 'success');
                    loadAll();
                } else {
                    showToast('Senkron hatasi: ' + (data.error || 'Bilinmeyen hata'), 'error');
                    btn.disabled = false;
                    btn.textContent = 'Elektra Senkron';
                }
            } catch (e) {
                showToast('Baglanti hatasi', 'error');
            }
        }

        async function runPaymentTryTest(id) {
            try {
                const res = await fetch(`/admin/hotel-bookings/${id}/payment-try-test`, {method: 'POST'});
                const data = await res.json();
                if (data.success) {
                    showToast('TRY test basarili', 'success');
                } else {
                    showToast('TRY testte hata adimi var', 'error');
                }
                const pretty = JSON.stringify(data, null, 2);
                alert(`TRY Test Sonucu (#${id})\\n\\n${pretty}`);
            } catch (e) {
                showToast('TRY test baglanti hatasi', 'error');
            }
        }

        async function forceDepositZero(id) {
            if (!confirm('Bu booking icin DEPOSITPERCENT alanini 0 yapmak istiyor musunuz?')) return;
            try {
                const res = await fetch(`/admin/hotel-bookings/${id}/force-deposit-zero`, {method: 'POST'});
                const data = await res.json();
                if (data.success) {
                    showToast('DEPOSITPERCENT 0 olarak guncellendi', 'success');
                    loadAll();
                } else {
                    showToast('Depozito sifirlama hatasi: ' + (data.error || 'Bilinmeyen hata'), 'error');
                }
            } catch (e) {
                showToast('Depozito sifirlama baglanti hatasi', 'error');
            }
        }

        async function openUpdateModal(id) {
            currentUpdateId = id;
            document.getElementById('updateBookingId').textContent = id;
            document.getElementById('updateCheckIn').value = '';
            document.getElementById('updateCheckOut').value = '';
            document.getElementById('updateNote').value = '';
            document.getElementById('updateModal').classList.add('active');
            try {
                const res = await fetch(`/admin/hotel-bookings/${id}`);
                const data = await res.json();
                if (data && !data.error) {
                    document.getElementById('updateCheckIn').value = (data.check_in || '').slice(0, 10);
                    document.getElementById('updateCheckOut').value = (data.check_out || '').slice(0, 10);
                    document.getElementById('updateNote').value = data.special_requests || '';
                }
            } catch (e) {
                showToast('On doldurma alinamadi, alanlari manuel girebilirsiniz', 'error');
            }
        }

        function closeUpdateModal() {
            document.getElementById('updateModal').classList.remove('active');
            currentUpdateId = null;
        }

        async function confirmUpdateModal() {
            if (!currentUpdateId) return;
            const checkIn = document.getElementById('updateCheckIn').value || '';
            const checkOut = document.getElementById('updateCheckOut').value || '';
            const note = (document.getElementById('updateNote').value || '').trim();

            const payload = {};
            if (checkIn) payload['check-in'] = checkIn;
            if (checkOut) payload['check-out'] = checkOut;
            if (note) payload['note'] = note;

            if (Object.keys(payload).length === 0) {
                showToast('Guncelleme icin en az 1 alan giriniz', 'error');
                return;
            }

            try {
                const res = await fetch(`/admin/hotel-bookings/${currentUpdateId}/elektra/update`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if (data.success) {
                    showToast('Elektra rezervasyon guncellendi', 'success');
                    closeUpdateModal();
                    loadAll();
                } else {
                    showToast('Guncelleme hatasi: ' + (data.error || 'Bilinmeyen hata'), 'error');
                }
            } catch (e) {
                showToast('Baglanti hatasi', 'error');
            }
        }

        async function cancelElektraBooking(id) {
            const reason = prompt('Iptal nedeni:', 'Admin panel') || 'Admin panel';
            if (!confirm('Elektra rezervasyonu iptal edilsin mi?')) return;
            try {
                const res = await fetch(`/admin/hotel-bookings/${id}/elektra/cancel?reason=${encodeURIComponent(reason)}`, {method: 'POST'});
                const data = await res.json();
                if (data.success) {
                    showToast('Elektra rezervasyon iptal edildi', 'success');
                    loadAll();
                } else {
                    showToast('Iptal hatasi: ' + (data.error || 'Bilinmeyen hata'), 'error');
                }
            } catch (e) {
                showToast('Baglanti hatasi', 'error');
            }
        }

        // ---- INIT ----
        loadAll();
        setInterval(loadAll, 30000);
    </script>
</body>
</html>
"""

from pathlib import Path

try:
    RESTAURANT_PLAN_HTML = Path("static/restaurant_plan_page.html").read_text(encoding="utf-8")
except Exception as _e:
    RESTAURANT_PLAN_HTML = f"<h1>restaurant_plan_page.html okunamadı</h1><pre>{_e}</pre>"
