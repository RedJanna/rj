"""
Admin Reminder Page - Hatırlatma Yönetim Sayfası
================================================
"""

REMINDER_PAGE_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hatırlatma Yönetimi - Kassandra Admin</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', system-ui, sans-serif; 
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #e0e0e0;
        }
        
        /* Top Navigation */
        .top-nav {
            background: rgba(0,0,0,0.3);
            padding: 15px 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .top-nav h1 {
            font-size: 1.5rem;
            color: #fff;
        }
        .home-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            text-decoration: none;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .home-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
        }
        
        .container { 
            max-width: 1400px; 
            margin: 0 auto; 
            padding: 20px;
        }
        
        /* Stats Cards */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: rgba(255,255,255,0.05);
            border-radius: 16px;
            padding: 20px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .stat-card h3 {
            font-size: 0.9rem;
            color: #888;
            margin-bottom: 10px;
        }
        .stat-card .value {
            font-size: 2rem;
            font-weight: 700;
            color: #fff;
        }
        .stat-card.success .value { color: #4ade80; }
        .stat-card.warning .value { color: #fbbf24; }
        .stat-card.danger .value { color: #f87171; }
        .stat-card.info .value { color: #60a5fa; }
        
        /* Tabs */
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            padding-bottom: 10px;
        }
        .tab-btn {
            background: transparent;
            border: none;
            color: #888;
            padding: 10px 20px;
            cursor: pointer;
            font-size: 14px;
            border-radius: 8px 8px 0 0;
            transition: all 0.2s;
        }
        .tab-btn:hover { color: #fff; background: rgba(255,255,255,0.05); }
        .tab-btn.active { 
            color: #fff; 
            background: rgba(102, 126, 234, 0.3);
            border-bottom: 2px solid #667eea;
        }
        
        /* Sections */
        .section {
            background: rgba(255,255,255,0.05);
            border-radius: 16px;
            padding: 25px;
            margin-bottom: 20px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .section h2 {
            font-size: 1.2rem;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        /* Settings Grid */
        .settings-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .setting-card {
            background: rgba(0,0,0,0.2);
            border-radius: 12px;
            padding: 20px;
        }
        .setting-card h4 {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 15px;
        }
        .setting-card .icon {
            font-size: 1.5rem;
        }
        .setting-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        .setting-row:last-child { border-bottom: none; }
        .setting-row label { color: #aaa; font-size: 0.9rem; }
        
        /* Toggle Switch */
        .toggle {
            position: relative;
            width: 50px;
            height: 26px;
        }
        .toggle input { opacity: 0; width: 0; height: 0; }
        .toggle .slider {
            position: absolute;
            cursor: pointer;
            top: 0; left: 0; right: 0; bottom: 0;
            background: #444;
            border-radius: 26px;
            transition: 0.3s;
        }
        .toggle .slider:before {
            content: "";
            position: absolute;
            height: 20px;
            width: 20px;
            left: 3px;
            bottom: 3px;
            background: white;
            border-radius: 50%;
            transition: 0.3s;
        }
        .toggle input:checked + .slider { background: #4ade80; }
        .toggle input:checked + .slider:before { transform: translateX(24px); }
        
        /* Table */
        .table-container {
            overflow-x: auto;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        th {
            background: rgba(0,0,0,0.2);
            color: #888;
            font-weight: 500;
            font-size: 0.85rem;
            text-transform: uppercase;
        }
        td { font-size: 0.9rem; }
        tr:hover { background: rgba(255,255,255,0.02); }
        
        /* Status Badge */
        .badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 500;
        }
        .badge.pending { background: rgba(251, 191, 36, 0.2); color: #fbbf24; }
        .badge.sent { background: rgba(74, 222, 128, 0.2); color: #4ade80; }
        .badge.failed { background: rgba(248, 113, 113, 0.2); color: #f87171; }
        .badge.restaurant { background: rgba(251, 146, 60, 0.2); color: #fb923c; }
        .badge.hotel { background: rgba(96, 165, 250, 0.2); color: #60a5fa; }
        
        /* Buttons */
        .btn {
            padding: 8px 16px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.85rem;
            transition: all 0.2s;
        }
        .btn-danger {
            background: rgba(248, 113, 113, 0.2);
            color: #f87171;
        }
        .btn-danger:hover { background: rgba(248, 113, 113, 0.4); }
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .btn-primary:hover { transform: translateY(-1px); }
        
        /* Hidden tabs */
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        
        /* Empty State */
        .empty-state {
            text-align: center;
            padding: 40px;
            color: #666;
        }
        .empty-state .icon { font-size: 3rem; margin-bottom: 15px; }
        
        /* Loading */
        .loading {
            display: flex;
            justify-content: center;
            padding: 40px;
        }
        .spinner {
            width: 40px;
            height: 40px;
            border: 3px solid rgba(255,255,255,0.1);
            border-top-color: #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <nav class="top-nav">
        <h1>📅 Hatırlatma Yönetimi</h1>
        <a href="/admin" class="home-btn">
            🏠 Ana Sayfa
        </a>
    </nav>
    
    <div class="container">
        <!-- Stats -->
        <div class="stats-grid" id="statsGrid">
            <div class="stat-card info">
                <h3>Bekleyen Hatırlatmalar</h3>
                <div class="value" id="statPending">-</div>
            </div>
            <div class="stat-card success">
                <h3>Bugün Gönderilen</h3>
                <div class="value" id="statSent">-</div>
            </div>
            <div class="stat-card danger">
                <h3>Başarısız</h3>
                <div class="value" id="statFailed">-</div>
            </div>
            <div class="stat-card warning">
                <h3>Restoran</h3>
                <div class="value" id="statRestaurant">-</div>
            </div>
            <div class="stat-card">
                <h3>Otel</h3>
                <div class="value" id="statHotel">-</div>
            </div>
        </div>
        
        <!-- Tabs -->
        <div class="tabs">
            <button class="tab-btn active" data-tab="settings">⚙️ Ayarlar</button>
            <button class="tab-btn" data-tab="pending">⏳ Bekleyenler</button>
            <button class="tab-btn" data-tab="logs">📋 Loglar</button>
        </div>
        
        <!-- Settings Tab -->
        <div id="settings" class="tab-content active">
            <div class="section">
                <h2>🍽️ Restoran Hatırlatmaları</h2>
                <div class="settings-grid">
                    <div class="setting-card">
                        <h4><span class="icon">🍽️</span> 15 Dakika Önce Hatırlatma</h4>
                        <div class="setting-row">
                            <label>Aktif</label>
                            <label class="toggle">
                                <input type="checkbox" id="toggle_restaurant_15min" onchange="toggleReminder('restaurant_15min', this.checked)">
                                <span class="slider"></span>
                            </label>
                        </div>
                        <div class="setting-row">
                            <label>Dakika Önce</label>
                            <span>15</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="section">
                <h2>🏨 Otel Hatırlatmaları</h2>
                <div class="settings-grid">
                    <div class="setting-card">
                        <h4><span class="icon">🔒</span> İptal Edilemez Rezervasyon</h4>
                        <div class="setting-row">
                            <label>Aktif</label>
                            <label class="toggle">
                                <input type="checkbox" id="toggle_hotel_7days" onchange="toggleReminder('hotel_7days', this.checked)">
                                <span class="slider"></span>
                            </label>
                        </div>
                        <div class="setting-row">
                            <label>Gün Önce</label>
                            <span>7</span>
                        </div>
                    </div>
                    <div class="setting-card">
                        <h4><span class="icon">✅</span> Ücretsiz İptal Rezervasyon</h4>
                        <div class="setting-row">
                            <label>Aktif</label>
                            <label class="toggle">
                                <input type="checkbox" id="toggle_hotel_5days" onchange="toggleReminder('hotel_5days', this.checked)">
                                <span class="slider"></span>
                            </label>
                        </div>
                        <div class="setting-row">
                            <label>Gün Önce</label>
                            <span>5</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="section">
                <h2>⏳ Yarım Kalan İşlemler</h2>
                <div class="settings-grid">
                    <div class="setting-card">
                        <h4><span class="icon">⏳</span> Akış Hatırlatması</h4>
                        <div class="setting-row">
                            <label>Aktif</label>
                            <label class="toggle">
                                <input type="checkbox" id="toggle_flow_incomplete" onchange="toggleReminder('flow_incomplete', this.checked)">
                                <span class="slider"></span>
                            </label>
                        </div>
                        <div class="setting-row">
                            <label>Dakika Sonra</label>
                            <span>5</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Pending Tab -->
        <div id="pending" class="tab-content">
            <div class="section">
                <h2>⏳ Bekleyen Hatırlatmalar</h2>
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Tür</th>
                                <th>Telefon</th>
                                <th>Rezervasyon</th>
                                <th>Planlanan Zaman</th>
                                <th>İşlem</th>
                            </tr>
                        </thead>
                        <tbody id="pendingTable">
                            <tr><td colspan="5" class="loading"><div class="spinner"></div></td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        
        <!-- Logs Tab -->
        <div id="logs" class="tab-content">
            <div class="section">
                <h2>📋 Gönderim Logları</h2>
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Zaman</th>
                                <th>Tür</th>
                                <th>Telefon</th>
                                <th>Durum</th>
                                <th>Mesaj</th>
                            </tr>
                        </thead>
                        <tbody id="logsTable">
                            <tr><td colspan="5" class="loading"><div class="spinner"></div></td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // Tab switching
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                btn.classList.add('active');
                document.getElementById(btn.dataset.tab).classList.add('active');
                
                if (btn.dataset.tab === 'pending') loadPending();
                if (btn.dataset.tab === 'logs') loadLogs();
            });
        });
        
        // Load stats
        async function loadStats() {
            try {
                const res = await fetch('/admin/reminders/stats');
                const data = await res.json();
                
                document.getElementById('statPending').textContent = data.pending_total || 0;
                document.getElementById('statSent').textContent = data.last_24h?.sent || 0;
                document.getElementById('statFailed').textContent = data.last_24h?.failed || 0;
                document.getElementById('statRestaurant').textContent = data.pending_by_type?.restaurant_15min || 0;
                document.getElementById('statHotel').textContent = 
                    (data.pending_by_type?.hotel_7days || 0) + (data.pending_by_type?.hotel_5days || 0);
                
                // Update toggles
                const settings = data.settings || {};
                document.getElementById('toggle_restaurant_15min').checked = settings.restaurant_15min?.enabled ?? true;
                document.getElementById('toggle_hotel_7days').checked = settings.hotel_7days?.enabled ?? true;
                document.getElementById('toggle_hotel_5days').checked = settings.hotel_5days?.enabled ?? true;
                document.getElementById('toggle_flow_incomplete').checked = settings.flow_incomplete?.enabled ?? true;
            } catch (e) {
                console.error('Stats yüklenemedi:', e);
            }
        }
        
        // Load pending reminders
        async function loadPending() {
            try {
                const res = await fetch('/admin/reminders/pending');
                const data = await res.json();
                
                const tbody = document.getElementById('pendingTable');
                
                if (!data.reminders || data.reminders.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="5" class="empty-state"><div class="icon">✅</div><p>Bekleyen hatırlatma yok</p></td></tr>';
                    return;
                }
                
                tbody.innerHTML = data.reminders.map(r => {
                    const typeClass = r.reminder_type.includes('restaurant') ? 'restaurant' : 'hotel';
                    const typeLabel = getTypeLabel(r.reminder_type);
                    const time = new Date(r.scheduled_time).toLocaleString('tr-TR');
                    const phone = r.phone.substring(0, 6) + '***';
                    
                    return `<tr>
                        <td><span class="badge ${typeClass}">${typeLabel}</span></td>
                        <td>${phone}</td>
                        <td>${r.reservation_id}</td>
                        <td>${time}</td>
                        <td><button class="btn btn-danger" onclick="cancelReminder('${r.reservation_id}')">İptal</button></td>
                    </tr>`;
                }).join('');
            } catch (e) {
                console.error('Pending yüklenemedi:', e);
            }
        }
        
        // Load logs
        async function loadLogs() {
            try {
                const res = await fetch('/admin/reminders/logs?limit=50');
                const data = await res.json();
                
                const tbody = document.getElementById('logsTable');
                
                if (!data.logs || data.logs.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="5" class="empty-state"><div class="icon">📭</div><p>Henüz log yok</p></td></tr>';
                    return;
                }
                
                tbody.innerHTML = data.logs.map(l => {
                    const time = new Date(l.sent_at).toLocaleString('tr-TR');
                    const phone = l.phone.substring(0, 6) + '***';
                    const statusClass = l.status === 'sent' ? 'sent' : 'failed';
                    const typeLabel = getTypeLabel(l.reminder_type);
                    
                    return `<tr>
                        <td>${time}</td>
                        <td>${typeLabel}</td>
                        <td>${phone}</td>
                        <td><span class="badge ${statusClass}">${l.status}</span></td>
                        <td>${l.message}</td>
                    </tr>`;
                }).join('');
            } catch (e) {
                console.error('Logs yüklenemedi:', e);
            }
        }
        
        // Toggle reminder
        async function toggleReminder(type, enabled) {
            try {
                await fetch('/admin/reminders/toggle', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({reminder_type: type, enabled: enabled})
                });
                loadStats();
            } catch (e) {
                console.error('Toggle hatası:', e);
            }
        }
        
        // Cancel reminder
        async function cancelReminder(reservationId) {
            if (!confirm('Bu hatırlatmayı iptal etmek istiyor musunuz?')) return;
            
            try {
                await fetch(`/admin/reminders/cancel/${reservationId}`, {method: 'DELETE'});
                loadPending();
                loadStats();
            } catch (e) {
                console.error('İptal hatası:', e);
            }
        }
        
        // Helper
        function getTypeLabel(type) {
            const labels = {
                'restaurant_15min': '🍽️ Restoran',
                'hotel_7days': '🏨 Otel (7g)',
                'hotel_5days': '🏨 Otel (5g)',
                'flow_incomplete': '⏳ Akış'
            };
            return labels[type] || type;
        }
        
        // Initial load
        loadStats();
        setInterval(loadStats, 30000); // 30 saniyede bir güncelle
    </script>
</body>
</html>
"""
