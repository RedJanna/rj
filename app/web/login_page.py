"""
Login Pages - Giriş Sayfaları
==============================
- Login sayfası
- 2FA doğrulama sayfası
- 2FA kurulum sayfası
"""

# ======================================================
# LOGIN SAYFASI
# ======================================================

LOGIN_PAGE_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Girişi - Kassandra</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #fff;
        }
        
        .login-container {
            background: rgba(255,255,255,0.05);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 24px;
            padding: 50px 40px;
            width: 100%;
            max-width: 420px;
            box-shadow: 0 25px 50px rgba(0,0,0,0.3);
        }
        
        .logo {
            text-align: center;
            margin-bottom: 30px;
        }
        .logo .icon { font-size: 4rem; }
        .logo h1 { font-size: 1.5rem; margin-top: 10px; font-weight: 600; }
        .logo p { color: #888; font-size: 0.9rem; margin-top: 5px; }
        
        .form-group {
            margin-bottom: 20px;
        }
        .form-group label {
            display: block;
            margin-bottom: 8px;
            color: #aaa;
            font-size: 0.9rem;
        }
        .form-group input {
            width: 100%;
            padding: 15px 20px;
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            background: rgba(0,0,0,0.2);
            color: #fff;
            font-size: 1rem;
            transition: all 0.3s;
        }
        .form-group input:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.2);
        }
        .form-group input::placeholder { color: #666; }
        
        .btn {
            width: 100%;
            padding: 15px;
            border: none;
            border-radius: 12px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #fff;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(102, 126, 234, 0.4);
        }
        .btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        
        .error-msg {
            background: rgba(239, 68, 68, 0.2);
            border: 1px solid rgba(239, 68, 68, 0.3);
            color: #f87171;
            padding: 12px 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            font-size: 0.9rem;
            display: none;
        }
        
        .footer {
            text-align: center;
            margin-top: 30px;
            color: #666;
            font-size: 0.8rem;
        }
        
        .spinner {
            display: none;
            width: 20px;
            height: 20px;
            border: 2px solid rgba(255,255,255,0.3);
            border-top-color: #fff;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin-right: 10px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        
        .btn-content {
            display: flex;
            align-items: center;
            justify-content: center;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">
            <div class="icon">🏨</div>
            <h1>Kassandra Admin</h1>
            <p>Yönetim Paneli Girişi</p>
        </div>
        
        <div class="error-msg" id="errorMsg"></div>
        
        <form id="loginForm" onsubmit="handleLogin(event)">
            <div class="form-group">
                <label for="username">Kullanıcı Adı</label>
                <input type="text" id="username" name="username" placeholder="Kullanıcı adınızı girin" required autocomplete="username">
            </div>
            
            <div class="form-group">
                <label for="password">Şifre</label>
                <input type="password" id="password" name="password" placeholder="Şifrenizi girin" required autocomplete="current-password">
            </div>
            
            <button type="submit" class="btn" id="submitBtn">
                <span class="btn-content">
                    <span class="spinner" id="spinner"></span>
                    <span id="btnText">Giriş Yap</span>
                </span>
            </button>
        </form>
        
        <div class="footer">
            <p>🔒 Güvenli bağlantı</p>
        </div>
    </div>
    
    <script>
        async function handleLogin(e) {
            e.preventDefault();
            
            const username = document.getElementById('username').value.trim();
            const password = document.getElementById('password').value;
            const errorMsg = document.getElementById('errorMsg');
            const submitBtn = document.getElementById('submitBtn');
            const spinner = document.getElementById('spinner');
            const btnText = document.getElementById('btnText');
            
            // UI güncelle
            errorMsg.style.display = 'none';
            submitBtn.disabled = true;
            spinner.style.display = 'block';
            btnText.textContent = 'Giriş yapılıyor...';
            
            try {
                const response = await fetch('/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    if (data.requires_2fa) {
                        // 2FA sayfasına yönlendir
                        window.location.href = '/admin/verify-2fa';
                    } else if (data.setup_2fa) {
                        // 2FA kurulum sayfasına yönlendir
                        window.location.href = '/admin/setup-2fa';
                    } else {
                        // Direkt admin paneline
                        window.location.href = '/admin';
                    }
                } else {
                    errorMsg.textContent = data.message || 'Giriş başarısız';
                    errorMsg.style.display = 'block';
                }
            } catch (err) {
                errorMsg.textContent = 'Bağlantı hatası. Lütfen tekrar deneyin.';
                errorMsg.style.display = 'block';
            } finally {
                submitBtn.disabled = false;
                spinner.style.display = 'none';
                btnText.textContent = 'Giriş Yap';
            }
        }
        
        // Enter tuşu ile giriş
        document.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                document.getElementById('loginForm').dispatchEvent(new Event('submit'));
            }
        });
    </script>
</body>
</html>
"""


# ======================================================
# 2FA DOĞRULAMA SAYFASI
# ======================================================

VERIFY_2FA_PAGE_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>2FA Doğrulama - Kassandra</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #fff;
        }
        
        .verify-container {
            background: rgba(255,255,255,0.05);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 24px;
            padding: 50px 40px;
            width: 100%;
            max-width: 420px;
            text-align: center;
        }
        
        .icon { font-size: 4rem; margin-bottom: 20px; }
        h1 { font-size: 1.5rem; margin-bottom: 10px; }
        p { color: #888; margin-bottom: 30px; }
        
        .code-input {
            display: flex;
            justify-content: center;
            gap: 10px;
            margin-bottom: 30px;
        }
        .code-input input {
            width: 50px;
            height: 60px;
            text-align: center;
            font-size: 1.5rem;
            font-weight: bold;
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            background: rgba(0,0,0,0.2);
            color: #fff;
        }
        .code-input input:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .btn {
            width: 100%;
            padding: 15px;
            border: none;
            border-radius: 12px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #fff;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
        }
        .btn:hover { box-shadow: 0 10px 30px rgba(102, 126, 234, 0.4); }
        .btn:disabled { opacity: 0.6; cursor: not-allowed; }
        
        .error-msg {
            background: rgba(239, 68, 68, 0.2);
            border: 1px solid rgba(239, 68, 68, 0.3);
            color: #f87171;
            padding: 12px;
            border-radius: 10px;
            margin-bottom: 20px;
            display: none;
        }
        
        .back-link {
            display: block;
            margin-top: 20px;
            color: #888;
            text-decoration: none;
        }
        .back-link:hover { color: #fff; }
    </style>
</head>
<body>
    <div class="verify-container">
        <div class="icon">🔐</div>
        <h1>İki Faktörlü Doğrulama</h1>
        <p>Google Authenticator uygulamasındaki<br>6 haneli kodu girin</p>
        
        <div class="error-msg" id="errorMsg"></div>
        
        <form id="verifyForm" onsubmit="handleVerify(event)">
            <div class="code-input">
                <input type="text" maxlength="1" class="code-digit" data-index="0" autofocus>
                <input type="text" maxlength="1" class="code-digit" data-index="1">
                <input type="text" maxlength="1" class="code-digit" data-index="2">
                <input type="text" maxlength="1" class="code-digit" data-index="3">
                <input type="text" maxlength="1" class="code-digit" data-index="4">
                <input type="text" maxlength="1" class="code-digit" data-index="5">
            </div>
            
            <button type="submit" class="btn" id="submitBtn">Doğrula</button>
        </form>
        
        <a href="/admin/logout" class="back-link">← Çıkış yap</a>
    </div>
    
    <script>
        const inputs = document.querySelectorAll('.code-digit');
        
        inputs.forEach((input, index) => {
            input.addEventListener('input', (e) => {
                const value = e.target.value;
                if (value && index < 5) {
                    inputs[index + 1].focus();
                }
                // Otomatik submit
                if (index === 5 && value) {
                    setTimeout(() => document.getElementById('verifyForm').dispatchEvent(new Event('submit')), 100);
                }
            });
            
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Backspace' && !e.target.value && index > 0) {
                    inputs[index - 1].focus();
                }
            });
            
            // Paste desteği
            input.addEventListener('paste', (e) => {
                e.preventDefault();
                const paste = (e.clipboardData || window.clipboardData).getData('text');
                const digits = paste.replace(/\\D/g, '').split('');
                inputs.forEach((inp, i) => {
                    if (digits[i]) inp.value = digits[i];
                });
                if (digits.length >= 6) {
                    setTimeout(() => document.getElementById('verifyForm').dispatchEvent(new Event('submit')), 100);
                }
            });
        });
        
        async function handleVerify(e) {
            e.preventDefault();
            
            const code = Array.from(inputs).map(i => i.value).join('');
            const errorMsg = document.getElementById('errorMsg');
            const submitBtn = document.getElementById('submitBtn');
            
            if (code.length !== 6) {
                errorMsg.textContent = '6 haneli kodu girin';
                errorMsg.style.display = 'block';
                return;
            }
            
            submitBtn.disabled = true;
            submitBtn.textContent = 'Doğrulanıyor...';
            errorMsg.style.display = 'none';
            
            try {
                const response = await fetch('/auth/verify-2fa', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ code })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    window.location.href = '/admin';
                } else {
                    errorMsg.textContent = data.message || 'Geçersiz kod';
                    errorMsg.style.display = 'block';
                    inputs.forEach(i => i.value = '');
                    inputs[0].focus();
                }
            } catch (err) {
                errorMsg.textContent = 'Bağlantı hatası';
                errorMsg.style.display = 'block';
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = 'Doğrula';
            }
        }
    </script>
</body>
</html>
"""


# ======================================================
# 2FA KURULUM SAYFASI
# ======================================================

SETUP_2FA_PAGE_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>2FA Kurulumu - Kassandra</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #fff;
            padding: 20px;
        }
        
        .setup-container {
            background: rgba(255,255,255,0.05);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 24px;
            padding: 40px;
            width: 100%;
            max-width: 500px;
        }
        
        .header { text-align: center; margin-bottom: 30px; }
        .header .icon { font-size: 3rem; margin-bottom: 15px; }
        .header h1 { font-size: 1.5rem; margin-bottom: 10px; }
        .header p { color: #888; }
        
        .steps { margin-bottom: 30px; }
        .step {
            background: rgba(0,0,0,0.2);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 15px;
        }
        .step-number {
            display: inline-block;
            width: 30px;
            height: 30px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 50%;
            text-align: center;
            line-height: 30px;
            font-weight: bold;
            margin-right: 10px;
        }
        .step-title { font-weight: 600; margin-bottom: 10px; }
        .step-content { color: #aaa; font-size: 0.9rem; }
        
        .qr-container {
            text-align: center;
            margin: 20px 0;
        }
        .qr-container img {
            background: #fff;
            padding: 15px;
            border-radius: 12px;
        }
        
        .secret-key {
            background: rgba(0,0,0,0.3);
            padding: 15px;
            border-radius: 8px;
            font-family: monospace;
            font-size: 1rem;
            text-align: center;
            margin: 15px 0;
            word-break: break-all;
            color: #00d4ff;
        }
        
        .code-input {
            display: flex;
            justify-content: center;
            gap: 8px;
            margin: 20px 0;
        }
        .code-input input {
            width: 45px;
            height: 55px;
            text-align: center;
            font-size: 1.3rem;
            font-weight: bold;
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 10px;
            background: rgba(0,0,0,0.2);
            color: #fff;
        }
        .code-input input:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .btn {
            width: 100%;
            padding: 15px;
            border: none;
            border-radius: 12px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #fff;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
        }
        .btn:hover { box-shadow: 0 10px 30px rgba(102, 126, 234, 0.4); }
        .btn:disabled { opacity: 0.6; cursor: not-allowed; }
        
        .error-msg, .success-msg {
            padding: 12px;
            border-radius: 10px;
            margin-bottom: 20px;
            display: none;
        }
        .error-msg {
            background: rgba(239, 68, 68, 0.2);
            border: 1px solid rgba(239, 68, 68, 0.3);
            color: #f87171;
        }
        .success-msg {
            background: rgba(34, 197, 94, 0.2);
            border: 1px solid rgba(34, 197, 94, 0.3);
            color: #4ade80;
        }
    </style>
</head>
<body>
    <div class="setup-container">
        <div class="header">
            <div class="icon">📱</div>
            <h1>2FA Kurulumu</h1>
            <p>Hesabınızı güvence altına alın</p>
        </div>
        
        <div class="error-msg" id="errorMsg"></div>
        <div class="success-msg" id="successMsg"></div>
        
        <div class="steps">
            <div class="step">
                <div class="step-title"><span class="step-number">1</span>Uygulamayı İndirin</div>
                <div class="step-content">
                    Google Authenticator veya Authy uygulamasını telefonunuza indirin.
                </div>
            </div>
            
            <div class="step">
                <div class="step-title"><span class="step-number">2</span>QR Kodu Tarayın</div>
                <div class="step-content">
                    Uygulamada "+" butonuna basın ve aşağıdaki QR kodu tarayın.
                </div>
                <div class="qr-container">
                    <img id="qrCode" src="" alt="QR Kod yükleniyor...">
                </div>
                <div class="step-content" style="text-align: center;">
                    veya bu kodu manuel girin:
                </div>
                <div class="secret-key" id="secretKey">Yükleniyor...</div>
            </div>
            
            <div class="step">
                <div class="step-title"><span class="step-number">3</span>Doğrulama Kodu</div>
                <div class="step-content">
                    Uygulamada görünen 6 haneli kodu girin:
                </div>
                <form id="setupForm" onsubmit="handleSetup(event)">
                    <div class="code-input">
                        <input type="text" maxlength="1" class="code-digit" data-index="0">
                        <input type="text" maxlength="1" class="code-digit" data-index="1">
                        <input type="text" maxlength="1" class="code-digit" data-index="2">
                        <input type="text" maxlength="1" class="code-digit" data-index="3">
                        <input type="text" maxlength="1" class="code-digit" data-index="4">
                        <input type="text" maxlength="1" class="code-digit" data-index="5">
                    </div>
                    <button type="submit" class="btn" id="submitBtn">2FA'yı Etkinleştir</button>
                </form>
            </div>
        </div>
    </div>
    
    <script>
        // QR kod ve secret'ı yükle
        async function loadSetupData() {
            try {
                const response = await fetch('/auth/setup-2fa-data');
                const data = await response.json();
                
                if (data.success) {
                    document.getElementById('secretKey').textContent = data.secret;
                    document.getElementById('qrCode').src = data.qr_url;
                } else {
                    document.getElementById('errorMsg').textContent = data.message;
                    document.getElementById('errorMsg').style.display = 'block';
                }
            } catch (err) {
                document.getElementById('errorMsg').textContent = 'Veri yüklenemedi';
                document.getElementById('errorMsg').style.display = 'block';
            }
        }
        
        loadSetupData();
        
        // Kod input işlemleri
        const inputs = document.querySelectorAll('.code-digit');
        
        inputs.forEach((input, index) => {
            input.addEventListener('input', (e) => {
                if (e.target.value && index < 5) {
                    inputs[index + 1].focus();
                }
            });
            
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Backspace' && !e.target.value && index > 0) {
                    inputs[index - 1].focus();
                }
            });
            
            input.addEventListener('paste', (e) => {
                e.preventDefault();
                const paste = (e.clipboardData || window.clipboardData).getData('text');
                const digits = paste.replace(/\\D/g, '').split('');
                inputs.forEach((inp, i) => {
                    if (digits[i]) inp.value = digits[i];
                });
            });
        });
        
        async function handleSetup(e) {
            e.preventDefault();
            
            const code = Array.from(inputs).map(i => i.value).join('');
            const errorMsg = document.getElementById('errorMsg');
            const successMsg = document.getElementById('successMsg');
            const submitBtn = document.getElementById('submitBtn');
            
            if (code.length !== 6) {
                errorMsg.textContent = '6 haneli kodu girin';
                errorMsg.style.display = 'block';
                return;
            }
            
            submitBtn.disabled = true;
            submitBtn.textContent = 'Doğrulanıyor...';
            errorMsg.style.display = 'none';
            
            try {
                const response = await fetch('/auth/enable-2fa', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ code })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    successMsg.textContent = '✅ 2FA başarıyla etkinleştirildi! Yönlendiriliyorsunuz...';
                    successMsg.style.display = 'block';
                    setTimeout(() => window.location.href = '/admin', 2000);
                } else {
                    errorMsg.textContent = data.message || 'Geçersiz kod';
                    errorMsg.style.display = 'block';
                    inputs.forEach(i => i.value = '');
                    inputs[0].focus();
                }
            } catch (err) {
                errorMsg.textContent = 'Bağlantı hatası';
                errorMsg.style.display = 'block';
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = '2FA\\'yı Etkinleştir';
            }
        }
    </script>
</body>
</html>
"""


# ======================================================
# KULLANICI YÖNETİM SAYFASI
# ======================================================

USER_MANAGEMENT_PAGE_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kullanıcı Yönetimi - Kassandra Admin</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #e0e0e0;
        }
        
        .top-nav {
            background: rgba(0,0,0,0.4);
            padding: 12px 25px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .top-nav .page-title { font-size: 1.3rem; color: #fff; }
        .home-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white !important;
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            text-decoration: none;
            font-size: 14px;
        }
        
        .container { max-width: 1200px; margin: 0 auto; padding: 30px 20px; }
        
        .card {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 16px;
            padding: 25px;
            margin-bottom: 20px;
        }
        .card h2 { margin-bottom: 20px; color: #fff; }
        
        .user-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 15px;
        }
        .user-card {
            background: rgba(0,0,0,0.2);
            border-radius: 12px;
            padding: 20px;
            border-left: 4px solid #667eea;
        }
        .user-card.admin { border-left-color: #f59e0b; }
        .user-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        .user-name { font-size: 1.1rem; font-weight: 600; }
        .user-role {
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.75rem;
            background: rgba(102, 126, 234, 0.2);
            color: #667eea;
        }
        .user-card.admin .user-role {
            background: rgba(245, 158, 11, 0.2);
            color: #f59e0b;
        }
        .user-info { color: #888; font-size: 0.85rem; margin-bottom: 5px; }
        .user-2fa {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.75rem;
            margin-top: 10px;
        }
        .user-2fa.enabled { background: rgba(34, 197, 94, 0.2); color: #4ade80; }
        .user-2fa.disabled { background: rgba(239, 68, 68, 0.2); color: #f87171; }
        
        .user-actions {
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }
        .user-actions button {
            padding: 8px 15px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.8rem;
        }
        .btn-danger { background: #ef4444; color: white; }
        .btn-secondary { background: rgba(255,255,255,0.1); color: #fff; }
        
        /* Modal */
        .modal {
            display: none;
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: rgba(0,0,0,0.8);
            align-items: center;
            justify-content: center;
            z-index: 1000;
        }
        .modal.active { display: flex; }
        .modal-content {
            background: #1a1a2e;
            border-radius: 16px;
            padding: 30px;
            width: 100%;
            max-width: 450px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .modal-content h3 { margin-bottom: 20px; }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 8px; color: #aaa; }
        .form-group input, .form-group select {
            width: 100%;
            padding: 12px;
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 8px;
            background: rgba(0,0,0,0.2);
            color: #fff;
        }
        .modal-actions {
            display: flex;
            gap: 10px;
            margin-top: 20px;
        }
        .modal-actions button {
            flex: 1;
            padding: 12px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1rem;
        }
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .btn-cancel { background: rgba(255,255,255,0.1); color: #fff; }
        
        .add-user-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px 25px;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            font-size: 1rem;
            margin-bottom: 20px;
        }
        
        .alert {
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .alert-success { background: rgba(34, 197, 94, 0.2); border: 1px solid rgba(34, 197, 94, 0.3); color: #4ade80; }
        .alert-error { background: rgba(239, 68, 68, 0.2); border: 1px solid rgba(239, 68, 68, 0.3); color: #f87171; }
        
        .qr-modal-content {
            text-align: center;
        }
        .qr-modal-content img {
            background: white;
            padding: 15px;
            border-radius: 10px;
            margin: 20px 0;
        }
        .secret-display {
            background: rgba(0,0,0,0.3);
            padding: 15px;
            border-radius: 8px;
            font-family: monospace;
            color: #00d4ff;
            margin: 15px 0;
            word-break: break-all;
        }
    </style>
</head>
<body>
    <nav class="top-nav">
        <span class="page-title">👥 Kullanıcı Yönetimi</span>
        <a href="/admin" class="home-btn">🏠 Ana Sayfa</a>
    </nav>
    
    <div class="container">
        <div id="alertContainer"></div>
        
        <button class="add-user-btn" onclick="showAddUserModal()">+ Yeni Kullanıcı Ekle</button>
        
        <div class="card">
            <h2>📋 Kullanıcılar</h2>
            <div class="user-grid" id="userGrid">
                <p style="color:#888;">Yükleniyor...</p>
            </div>
        </div>
    </div>
    
    <!-- Yeni Kullanıcı Modal -->
    <div class="modal" id="addUserModal">
        <div class="modal-content">
            <h3>➕ Yeni Kullanıcı Ekle</h3>
            <form id="addUserForm" onsubmit="handleAddUser(event)">
                <div class="form-group">
                    <label>Kullanıcı Adı</label>
                    <input type="text" id="newUsername" required placeholder="Kullanıcı adı">
                </div>
                <div class="form-group">
                    <label>Şifre</label>
                    <input type="password" id="newPassword" required placeholder="En az 8 karakter" minlength="8">
                </div>
                <div class="form-group">
                    <label>Görünen Ad</label>
                    <input type="text" id="newDisplayName" placeholder="İsim Soyisim">
                </div>
                <div class="form-group">
                    <label>Rol</label>
                    <select id="newRole">
                        <option value="operator">Operatör</option>
                        <option value="admin">Admin</option>
                    </select>
                </div>
                <div class="modal-actions">
                    <button type="button" class="btn-cancel" onclick="closeModal('addUserModal')">İptal</button>
                    <button type="submit" class="btn-primary">Oluştur</button>
                </div>
            </form>
        </div>
    </div>
    
    <!-- 2FA QR Modal -->
    <div class="modal" id="qrModal">
        <div class="modal-content qr-modal-content">
            <h3>📱 2FA Kurulumu</h3>
            <p style="color:#888;">Kullanıcı bu QR kodu Google Authenticator ile taramalı:</p>
            <img id="qrImage" src="" alt="QR Kod">
            <div class="secret-display" id="secretDisplay"></div>
            <p style="color:#888; font-size:0.85rem;">Bu bilgileri kullanıcıyla paylaşın. Pencereyi kapattıktan sonra tekrar göremezsiniz!</p>
            <div class="modal-actions">
                <button type="button" class="btn-primary" onclick="closeModal('qrModal')" style="flex:1;">Tamam</button>
            </div>
        </div>
    </div>
    
    <script>
        async function loadUsers() {
            try {
                const res = await fetch('/auth/users');
                const data = await res.json();
                
                const grid = document.getElementById('userGrid');
                
                if (!data.users || data.users.length === 0) {
                    grid.innerHTML = '<p style="color:#888;">Kullanıcı bulunamadı</p>';
                    return;
                }
                
                grid.innerHTML = data.users.map(user => `
                    <div class="user-card ${user.role}">
                        <div class="user-header">
                            <span class="user-name">👤 ${user.display_name || user.username}</span>
                            <span class="user-role">${user.role === 'admin' ? 'Admin' : 'Operatör'}</span>
                        </div>
                        <div class="user-info">🔑 ${user.username}</div>
                        <div class="user-info">📅 Oluşturulma: ${new Date(user.created_at).toLocaleDateString('tr-TR')}</div>
                        ${user.last_login ? `<div class="user-info">🕐 Son giriş: ${new Date(user.last_login).toLocaleString('tr-TR')}</div>` : ''}
                        <span class="user-2fa ${user.totp_enabled ? 'enabled' : 'disabled'}">
                            ${user.totp_enabled ? '🔐 2FA Aktif' : '⚠️ 2FA Kapalı'}
                        </span>
                        <div class="user-actions">
                            <button class="btn-secondary" onclick="resetPassword('${user.username}')">🔑 Şifre Sıfırla</button>
                            ${user.role !== 'admin' ? `<button class="btn-danger" onclick="deleteUser('${user.username}')">🗑️ Sil</button>` : ''}
                        </div>
                    </div>
                `).join('');
            } catch (err) {
                console.error('Kullanıcılar yüklenemedi:', err);
            }
        }
        
        function showAddUserModal() {
            document.getElementById('addUserModal').classList.add('active');
        }
        
        function closeModal(id) {
            document.getElementById(id).classList.remove('active');
        }
        
        function showAlert(message, type) {
            const container = document.getElementById('alertContainer');
            container.innerHTML = `<div class="alert alert-${type}">${message}</div>`;
            setTimeout(() => container.innerHTML = '', 5000);
        }
        
        async function handleAddUser(e) {
            e.preventDefault();
            
            const username = document.getElementById('newUsername').value.trim();
            const password = document.getElementById('newPassword').value;
            const displayName = document.getElementById('newDisplayName').value.trim();
            const role = document.getElementById('newRole').value;
            
            try {
                const res = await fetch('/auth/users', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password, display_name: displayName, role })
                });
                
                const data = await res.json();
                
                if (data.success) {
                    closeModal('addUserModal');
                    document.getElementById('addUserForm').reset();
                    
                    // QR kodu göster
                    document.getElementById('qrImage').src = data.qr_url;
                    document.getElementById('secretDisplay').textContent = data.totp_secret;
                    document.getElementById('qrModal').classList.add('active');
                    
                    loadUsers();
                } else {
                    showAlert(data.message || 'Hata oluştu', 'error');
                }
            } catch (err) {
                showAlert('Bağlantı hatası', 'error');
            }
        }
        
        async function deleteUser(username) {
            if (!confirm(`"${username}" kullanıcısını silmek istediğinize emin misiniz?`)) return;
            
            try {
                const res = await fetch(`/auth/users/${username}`, { method: 'DELETE' });
                const data = await res.json();
                
                if (data.success) {
                    showAlert('Kullanıcı silindi', 'success');
                    loadUsers();
                } else {
                    showAlert(data.message || 'Silinemedi', 'error');
                }
            } catch (err) {
                showAlert('Bağlantı hatası', 'error');
            }
        }
        
        async function resetPassword(username) {
            const newPassword = prompt(`"${username}" için yeni şifre girin (en az 8 karakter):`);
            if (!newPassword || newPassword.length < 8) {
                alert('Şifre en az 8 karakter olmalı');
                return;
            }
            
            try {
                const res = await fetch(`/auth/users/${username}/password`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ password: newPassword })
                });
                
                const data = await res.json();
                
                if (data.success) {
                    showAlert('Şifre güncellendi', 'success');
                } else {
                    showAlert(data.message || 'Güncellenemedi', 'error');
                }
            } catch (err) {
                showAlert('Bağlantı hatası', 'error');
            }
        }
        
        // Sayfa yüklendiğinde
        loadUsers();
    </script>
</body>
</html>
"""
