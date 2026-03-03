TRANSFER_RESERVATIONS_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Transfer Rezervasyonları - Kassandra Admin</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #111; color: #f1f1f1; margin: 0; padding: 20px; }
        .wrap { max-width: 1200px; margin: 0 auto; }
        .nav a { color: #00d4ff; text-decoration: none; margin-right: 12px; border: 1px solid #00d4ff; border-radius: 8px; padding: 8px 12px; display: inline-block; }
        .nav a.active { background: #00d4ff; color: #00161d; }
        .row { display: flex; gap: 12px; align-items: center; margin: 16px 0; }
        select, button, input { background: #1f1f1f; color: #f1f1f1; border: 1px solid #333; border-radius: 8px; padding: 8px 10px; }
        button { cursor: pointer; }
        .list { display: grid; gap: 12px; }
        .card { background: #1a1a1a; border: 1px solid #2e2e2e; border-radius: 12px; padding: 14px; }
        .top { display: flex; justify-content: space-between; gap: 8px; flex-wrap: wrap; }
        .status { font-weight: 700; text-transform: uppercase; font-size: 12px; }
        .status.pending { color: #ffcc00; }
        .status.confirmed { color: #00e676; }
        .status.cancelled { color: #ff5252; }
        .status.updated { color: #4fc3f7; }
        .meta { color: #b0b0b0; font-size: 13px; margin-top: 6px; }
        .actions { display: flex; gap: 8px; margin-top: 12px; flex-wrap: wrap; }
        .btn-ok { border-color: #00e676; color: #00e676; }
        .btn-cancel { border-color: #ff5252; color: #ff5252; }
        .btn-edit { border-color: #4fc3f7; color: #4fc3f7; }
        .empty { color: #9a9a9a; padding: 20px; border: 1px dashed #333; border-radius: 10px; text-align: center; }
    </style>
</head>
<body>
    <div class="wrap">
        <h1>🚐 Transfer Rezervasyonları</h1>
        <div class="nav">
            <a href="/admin">Ana Panel</a>
            <a href="/admin/reservations-page">🍽️ Rezervasyonlar</a>
            <a href="/admin/hotel-bookings-page">🏨 Otel Rez.</a>
            <a href="/admin/transfer-reservations-page" class="active">🚐 Transfer Rez.</a>
            <a href="/admin/reminders-page">📅 Hatırlatmalar</a>
        </div>

        <div class="row">
            <label for="status">Durum:</label>
            <select id="status">
                <option value="pending">Bekleyen</option>
                <option value="confirmed">Onaylı</option>
                <option value="updated">Güncellenmiş</option>
                <option value="cancelled">İptal</option>
                <option value="all">Tümü</option>
            </select>
            <label for="dateFilter">Tarih:</label>
            <input id="dateFilter" type="date" />
            <label for="notifyCustomer" style="display:flex; gap:6px; align-items:center;">
                <input id="notifyCustomer" type="checkbox" checked />
                Müşteriye mesaj gönder
            </label>
            <button onclick="loadData()">Yenile</button>
        </div>

        <div id="list" class="list"></div>
    </div>

    <script>
        async function api(path, opts = {}) {
            const res = await fetch(path, opts);
            return await res.json();
        }

        function esc(v) {
            const s = String(v || "");
            return s.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
        }

        async function confirmReservation(id) {
            if (!confirm("Transfer rezervasyonunu onayla? (Müşteriye WhatsApp bildirimi gönderilecek)")) return;
            const notifyCustomer = document.getElementById("notifyCustomer").checked;
            const data = await api(`/admin/transfer-reservations/${id}/confirm`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ note: "Admin panel onayı", notify_customer: notifyCustomer })
            });
            alert(data.message || data.error || "İşlem tamamlandı");
            loadData();
        }

        async function cancelReservation(id) {
            const reason = prompt("İptal nedeni (opsiyonel):", "") || "";
            if (!confirm("Transfer rezervasyonunu iptal et?")) return;
            const notifyCustomer = document.getElementById("notifyCustomer").checked;
            const data = await api(`/admin/transfer-reservations/${id}/cancel`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ reason, notify_customer: notifyCustomer })
            });
            alert(data.message || data.error || "İşlem tamamlandı");
            loadData();
        }

        async function editReservation(id) {
            const current = await api(`/admin/transfer-reservations/${id}`);
            if (!current.success) {
                alert(current.error || "Kayıt bulunamadı");
                return;
            }
            const r = current.reservation;
            const transfer_date = prompt("Tarih", r.transfer_date || "");
            if (transfer_date === null) return;
            const transfer_time = prompt("Saat", r.transfer_time || "");
            if (transfer_time === null) return;
            const flight_no = prompt("Uçuş No", r.flight_no || "");
            if (flight_no === null) return;
            const guest_text = prompt("Kişi", r.guest_text || "");
            if (guest_text === null) return;
            const luggage_text = prompt("Bagaj", r.luggage_text || "");
            if (luggage_text === null) return;
            const baby_seat = prompt("Bebek Koltuğu", r.baby_seat || "");
            if (baby_seat === null) return;
            const admin_note = prompt("Admin Notu", r.admin_note || "Admin güncellemesi");
            if (admin_note === null) return;
            const notifyCustomer = document.getElementById("notifyCustomer").checked;

            const data = await api(`/admin/transfer-reservations/${id}/update`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    transfer_date, transfer_time, flight_no, guest_text, luggage_text, baby_seat, admin_note, notify_customer: notifyCustomer
                })
            });
            alert(data.message || data.error || "İşlem tamamlandı");
            loadData();
        }

        async function loadData() {
            const status = document.getElementById("status").value;
            const date = (document.getElementById("dateFilter").value || "").trim();
            const list = document.getElementById("list");
            list.innerHTML = "Yükleniyor...";
            const data = await api(`/admin/transfer-reservations?status=${encodeURIComponent(status)}&date=${encodeURIComponent(date)}`);
            const items = data.reservations || [];
            if (!items.length) {
                list.innerHTML = '<div class="empty">Kayıt bulunamadı.</div>';
                return;
            }
            list.innerHTML = items.map(r => `
                <div class="card">
                    <div class="top">
                        <div><b>#${r.id}</b> - ${esc(r.customer_phone)}</div>
                        <div class="status ${esc(r.status)}">${esc(r.status)}</div>
                    </div>
                    <div class="meta">İsim: ${esc(r.customer_name || "-")} | Rota: ${esc(r.transfer_route)} | Tarih: ${esc(r.transfer_date)} | Saat: ${esc(r.transfer_time)} | Uçuş: ${esc(r.flight_no)}</div>
                    <div class="meta">Kişi: ${esc(r.guest_text)} | Bagaj: ${esc(r.luggage_text)} | Bebek koltuğu: ${esc(r.baby_seat)} | Ücret: ${esc(r.price_text)}</div>
                    <div class="meta">Oluşturulma: ${esc(r.created_at)} | Güncelleme: ${esc(r.updated_at)}</div>
                    <div class="actions">
                        <button class="btn-ok" onclick="confirmReservation(${r.id})">Onayla</button>
                        <button class="btn-cancel" onclick="cancelReservation(${r.id})">İptal Et</button>
                        <button class="btn-edit" onclick="editReservation(${r.id})">Değişiklik Yap</button>
                    </div>
                </div>
            `).join("");
        }

        loadData();
        setInterval(loadData, 30000);
    </script>
</body>
</html>
"""
