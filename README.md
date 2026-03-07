# KassandraOpenAI

KassandraOpenAI, otel iletisim ve rezervasyon sureclerini yoneten bir FastAPI tabanli WhatsApp chatbot projesidir.

Bu README, projedeki kurulum, calistirma, test ve operasyon notlarini tek dosyada toplar.
Daha detayli operasyon notlari icin yine de `docs/` altindaki dosyalar referans alinabilir.

## Icindekiler

1. Proje Ozeti
2. Temel Yetenekler
3. Teknoloji Yigini
4. Dizin Yapisi
5. On Kosullar
6. Ortam Degiskenleri
7. Kurulum
8. Uygulamayi Calistirma
9. Saglik Kontrolleri
10. Test Calistirma Rehberi
11. StateStore Override (Izole Test)
12. Otomatik Dokuman Guncelleme (Snapshot + Hook)
13. Sorun Giderme
14. Runtime Veri ve Git Politikasi
15. Faydali Belgeler

## 1) Proje Ozeti

Amaç:
- WhatsApp uzerinden gelen mesajlari otel operasyonuna uygun sekilde yorumlamak,
- Fiyat/uygunluk/rezervasyon akislarini yonetmek,
- Gerekli durumda insan destegine devir yapmak,
- Disa bagli servisler (OpenAI, Meta WhatsApp, Elektra) ile calismayi surdurmek.

Calisma sekli (yuksek seviye):
- Girdi: `/chat` endpoint'ine mesaj gelir.
- On isleme: guvenlik, rate limit, dil tespiti, aktif akis kontrolu.
- Yonlendirme: intent/slot/policy degerlendirmesi.
- Cevap: uygun handler veya OpenAI fallback.
- Cikti: kullaniciya yanit + log/metric + gerekirse handoff.

## 2) Temel Yetenekler

- Cok asamali sohbet akislari (price, booking, reservation vb.)
- Intent + policy guard tabanli yonlendirme
- OpenAI destekli fallback yanitlama
- Admin ve monitoring endpointleri
- Runtime durum dosyalari ile state yonetimi
- Test odakli gelistirme: unit, integration, golden, e2e
- Degraded startup modu (kritik env eksiginde process ayakta kalir)

## 3) Teknoloji Yigini

- Dil: Python 3.10+
- API: FastAPI
- Sunucu: Uvicorn
- AI: OpenAI API
- Scheduler: APScheduler
- Veri: SQLite + JSON state dosyalari
- Test: pytest (+ pytest-asyncio, pytest-cov, pytest-html, pytest-json-report)

## 4) Dizin Yapisi

Ana klasorler:
- `app/`: uygulama kaynak kodu
- `tests/`: testler
- `docs/`: operasyon ve teknik dokumanlar
- `tools/`: yardimci scriptler
- `data/`, `conversations/`, `logs/`, `reservation_pdfs/`: runtime ciktilari

Onemli giris dosyalari:
- `app/main.py`: app olusturma + startup fallback/degraded davranisi
- `kassandra_openai_bot.py`: runtime entrypoint
- `start_backend.bat`: Windows backend baslatma scripti
- `start_cloudflare.bat`: Cloudflare tunnel baslatma scripti

## 5) On Kosullar

- Windows 10/11 veya Linux
- Python 3.10+ (onerilen: proje venv)
- pip
- (Opsiyonel) cloudflared
- OpenAI API anahtari
- WhatsApp/Meta bilgileri (gercek gonderim icin)
- Elektra bilgileri (fiyat/rezervasyon senaryolari icin)

## 6) Ortam Degiskenleri

Ornek konfigurasyon `/.env.example` dosyasindadir.

Kritik env:
- `OPENAI_API_KEY`

Sik kullanilan env:
- `OPENAI_MODEL` (varsayilan: `gpt-4.1-mini`)
- `FLOW_ORCHESTRATOR_MODE` (`off` / `active` / ortama gore diger modlar)
- `KASSANDRA_ENV` (`production`, `test`, `dev`, ...)
- `WHATSAPP_PHONE_ID`
- `WHATSAPP_TOKEN`
- `ELEKTRA_API_BASE_URL`
- `Elektra_Booking`
- `ELEKTRA_HOTEL_ID`

StateStore override env (test izolasyonu icin):
- `KASSANDRA_CONVERSATIONS_DIR`
- `KASSANDRA_MESSAGE_ID_FILE`
- `KASSANDRA_ROUTING_STATE_FILE`
- `KASSANDRA_PRICE_FLOW_FILE`
- `KASSANDRA_BOOKING_FLOW_FILE`
- `KASSANDRA_RESERVATIONS_DB`
- `KASSANDRA_RESERVATION_FLOW_FILE`
- `KASSANDRA_HOTEL_BOOKINGS_DB`
- `KASSANDRA_FOLLOWUP_FILE`
- `KASSANDRA_REMINDERS_FILE`
- `KASSANDRA_REMINDER_LOG_FILE`
- `KASSANDRA_PDF_CONFIG_FILE`

## 7) Kurulum

### 7.1 Projeyi hazirla

Windows (PowerShell):

```powershell
cd C:\KassandraOpenAI
py -3.10 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Linux/macOS:

```bash
cd /mnt/c/KassandraOpenAI
python3 -m venv .venv-wsl
source .venv-wsl/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 7.2 Env dosyasi olustur

```bash
cp .env.example .env
```

Sonra `.env` icine gerekli degerleri girin.

## 8) Uygulamayi Calistirma

### 8.1 Windows (onerilen script)

```powershell
cd C:\KassandraOpenAI
.\start_backend.bat
```

Script ozeti:
- UTF-8 ve log ayarlari yapar
- Venv python yolunu kullanir
- Gerekirse preflight kontrolu calistirir
- Varsayilan olarak `uvicorn app.main:app` ile ayaga kaldirir
- Crash durumunda auto-restart davranisini yonetir

### 8.2 Cloudflare tunnel (Windows)

```powershell
cd C:\KassandraOpenAI
.\start_cloudflare.bat
```

### 8.3 Dogrudan uvicorn ile calistirma

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 9) Saglik Kontrolleri

- Uygulama health: `GET /health`
- Admin health: `GET /admin/health` (admin auth gerektirebilir)

Yerel kontrol:

```bash
curl -sS http://127.0.0.1:8000/health
```

### Degraded startup davranisi

Kritik bir env (ornegin `OPENAI_API_KEY`) eksikse process tamamen dusmez.
Uygulama degraded modda acilir ve `/health` icinde hata detayini doner.

Ornek:

```json
{
  "status": "degraded",
  "env": "production",
  "startup_error": "RuntimeError",
  "startup_error_message": "Kritik ortam degiskenleri eksik: OPENAI_API_KEY ..."
}
```

## 10) Test Calistirma Rehberi

### 10.1 Legacy kontrat testi (orchestrator kapali)

```powershell
cd C:\KassandraOpenAI
.\venv\Scripts\Activate.ps1
$env:FLOW_ORCHESTRATOR_MODE = "off"
pytest tests\golden\ -v -m golden --tb=short -ra
pytest tests\integration\test_api_routes.py -v --tb=short -ra
```

### 10.2 Gercekci kontrat testi (orchestrator aktif)

```powershell
cd C:\KassandraOpenAI
.\venv\Scripts\Activate.ps1
$env:FLOW_ORCHESTRATOR_MODE = "active"
pytest tests\golden\ -v -m golden --tb=short -ra
pytest tests\integration\test_api_routes.py -v --tb=short -ra
```

### 10.3 Hedefli test calistirma ornegi

```powershell
$env:FLOW_ORCHESTRATOR_MODE = "active"
pytest tests\integration\test_api_routes.py -k "router_v2_ambiguity_prompt or domain_lock_choice_applies" -v --tb=short -ra
```

### 10.4 Parallel test notu

```powershell
python -m pip install pytest-xdist
pytest -n 2
```

## 11) StateStore Override (Izole Test)

Kalici state dosyalarindan izole kosu icin (PowerShell):

```powershell
$env:KASSANDRA_ROUTING_STATE_FILE = "C:\KassandraOpenAI\data\routing_states.test.json"
$env:KASSANDRA_PRICE_FLOW_FILE = "C:\KassandraOpenAI\data\price_flows.test.json"
$env:KASSANDRA_FOLLOWUP_FILE = "C:\KassandraOpenAI\data\followups.test.json"
$env:KASSANDRA_REMINDERS_FILE = "C:\KassandraOpenAI\data\reminders.test.json"
$env:KASSANDRA_REMINDER_LOG_FILE = "C:\KassandraOpenAI\data\reminder_logs.test.json"
```

Not:
- Bu override'lar testler arasinda state sizintisini azaltir.
- Terminal kapandiginda PowerShell env degerleri sifirlanir.

## 12) Otomatik Dokuman Guncelleme (Snapshot + Hook)

Bu proje `tools/generate_project_snapshot.py` ile docs altinda otomatik ozet uretebilir.

### 12.1 Ilk calistirma (Windows)

```cmd
py -3.10 tools\generate_project_snapshot.py --root C:\KassandraOpenAI
```

### 12.2 Git post-commit hook

1. `hooks/post-commit` dosyasini su hedefe kopyalayin:
- `.git/hooks/post-commit`

2. Calistirilabilir yapin (Git Bash):

```bash
chmod +x .git/hooks/post-commit
```

Sonuc:
- Her commit sonrasinda `docs/AI_BRIEF.md` AUTOGEN bolumu ve `docs/_generated/*` ciktilari guncellenir.

## 13) Sorun Giderme

### 13.1 ModuleNotFoundError / fastapi yok

- Dogru venv aktif mi kontrol edin.
- `pip install -r requirements.txt` tekrar calistirin.

### 13.2 `cloudflared` bulunamiyor

- `start_cloudflare.bat` icindeki varsayilan path:
  - `%ProgramFiles(x86)%\cloudflared\cloudflared.exe`
- Ya buraya kurun ya da PATH'e ekleyin.

### 13.3 Uygulama aciliyor ama beklendigi gibi yanit vermiyor

- `/health` cikisini kontrol edin.
- Loglari kontrol edin (`logs/`, `backend_boot.log`).
- Env degerlerini tekrar gozden gecirin (`OPENAI_API_KEY`, WhatsApp, Elektra).

### 13.4 Testlerde beklenmeyen state etkisi

- Override env ile izole dosya kullanin (bkz. Bolum 11).
- Gerekirse ilgili runtime JSON/DB dosyalarini temizleyin.

## 14) Runtime Veri ve Git Politikasi

Temel prensip:
- Runtime uretimleri repoya dahil ETMEYIN.

Git'e girmemesi gereken tipik dosyalar:
- `data/`
- `conversations/`
- `logs/`
- `reservation_pdfs/`
- `*.db`
- Geçici test raporlari/artifact'lar

Yedekleme notu:
- `.bak` turevi dosyalar aktif kaynak agacinda tutulmamali,
- gerekiyorsa `archive/backups/` altina tasinmali.

## 15) Faydali Belgeler

- `docs/RUNBOOK.md`: operasyon ve sorun giderme
- `docs/ONCALL_INTENT_ELEKTRA_RUNBOOK.md`: intent + Elektra icin tek dosyalik nobet kilavuzu
- `docs/OPS_SKILL_INDEX.md`: operasyonel skill secim haritasi (belirti -> skill)
- `docs/SKILL_DEVELOPMENT_PLAYBOOK.md`: yeni skill gelistirme rehberi (yapi + template + checklist)
- `docs/INTEGRATIONS.md`: dis servis entegrasyon notlari
- `docs/AI_BRIEF.md`: AI sohbetleri icin tek sayfa teknik ozet
- `docs/CHANGELOG.md`: degisiklik kayitlari

---

## Hizli Baslangic (One-Minute)

Windows:

```powershell
cd C:\KassandraOpenAI
py -3.10 -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# .env dosyasinda OPENAI_API_KEY degerini girin
.\start_backend.bat
```

Sonra:

```powershell
curl http://127.0.0.1:8000/health
```

Beklenen: `status: ok` (veya eksik env varsa `status: degraded`).
