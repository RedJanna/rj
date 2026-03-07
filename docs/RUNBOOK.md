# RUNBOOK — Çalıştırma / Sorun Giderme

## 1) Günlük başlatma
- Backend
- Cloudflare tunnel

> Not: Script'ler ayrı tutulmalı: start_backend.bat / start_cloudflare.bat
> Not: Backend acilisinda `ELEKTRA_WALKIN_AGENCY_ID` bos ise varsayilan `247664` atanir.

## 2) Sağlık kontrol
- Backend: http://127.0.0.1:8000/health
- Tunnel: cloudflared loglarında connected/registered

## 3) En sık sorunlar
### 3.1 fastapi yok / modül yok
- Çözüm: venv + pip install

### 3.2 requirements.txt encoding hatası
- Çözüm: UTF-8 requirements_pip.txt kullan


### 3.4 cloudflared bulunamadı
- Çözüm: cloudflared.exe PATH veya tam yol

## 4) Log toplama (AI’ye verirken)
- Token/telefon maskeli
- Hata: stacktrace + hangi komutta oldu

## 5) Git baseline + calisma prensibi

Amac: Calisan kodu dondurmak, runtime veriyi repo disina almak.

### 5.1 Baseline alma
- `.gitignore` runtime ve artifact dosyalarini dislayacak sekilde tutulur.
- Runtime klasorleri icin sadece bos klasor iskeleti repoda kalir:
  - `data/.gitkeep`
  - `conversations/.gitkeep`
  - `logs/.gitkeep`
  - `reservation_pdfs/.gitkeep`
- Baseline commit sadece kod + dokuman + fixture icerir (runtime state icermez).
- Stabil surumde etiket onerisi:
  - `git tag -a baseline-YYYYMMDD -m "stable baseline"`

### 5.2 Runtime veri kurali
- `data/`, `conversations/`, `logs/`, `reservation_pdfs/`, `*.db` ve test raporlari repoya girmez.
- Lokal calismada uretilen state/log dosyalari ignore edilir.
- Paylasilacak ornek veri gerekiyorsa `data/fixtures/` altinda anonimlestirilmis olarak tutulur.

### 5.3 Calisma akisi
- Kod degisikligi -> test -> commit.
- Runtime dosya degisiklikleri commit kapsaminda olmamali.
- Uretimden alinan veri dogrudan repoya yazilmaz; gerekirse anonim fixture uretilir.

## 6) Test profilleri (PowerShell)

### 6.1 Legacy kontrat testi (orchestrator kapali)
```powershell
cd C:\KassandraOpenAI
.\venv\Scripts\Activate.ps1
$env:FLOW_ORCHESTRATOR_MODE = "off"

pytest tests\golden\ -v -m golden --tb=short -ra
pytest tests\integration\test_api_routes.py -v --tb=short -ra
```

### 6.2 Gercekci kontrat testi (orchestrator aktif)
```powershell
cd C:\KassandraOpenAI
.\venv\Scripts\Activate.ps1
$env:FLOW_ORCHESTRATOR_MODE = "active"

pytest tests\golden\ -v -m golden --tb=short -ra
pytest tests\integration\test_api_routes.py -v --tb=short -ra
```

Not:
- `FLOW_ORCHESTRATOR_MODE` PowerShell oturumu kapaninca sifirlanir.
- Ayni terminalde degeri kontrol etmek icin: `echo $env:FLOW_ORCHESTRATOR_MODE`

## 7) Yedekleme politikasi (.bak temizligi)

Amac: `.bak` dosyalarinin "guncel kaynak dosya" sanilmasini engellemek.

### 7.1 Tehlikeli .bak sinifi
- Entrypoint veya aktif kaynakla ayni isim kokune sahip olanlar:
  - Ornek: `app/web/admin_pages.py.bak_...` (aktif `admin_pages.py` ile karisabilir)
- `app/`, `routes/`, `core/`, `services/` altindaki tum `*.bak*` dosyalari.

### 7.2 Onerilen strateji
1. Calisan kaynak agacindan tasima:
   - `.bak` dosyalari `archive/backups/` altina tasinir.
2. Git ignore:
   - `archive/backups/**` ignore edilir (repo sismez).
3. Uzun sureli saklama:
   - Gerekirse harici zip/artifact deposuna alin.

### 7.3 Operasyon proseduru (PowerShell)
Repo icindeki `.bak` dosyalarini bul:
```powershell
Get-ChildItem -Recurse -File | Where-Object { $_.Name -match '\.bak(_|\.|$)' } | Select-Object FullName
```

`archive/backups/` altina tasi:
```powershell
$target = "C:\KassandraOpenAI\archive\backups"
New-Item -ItemType Directory -Force -Path $target | Out-Null
Get-ChildItem -Recurse -File | Where-Object { $_.Name -match '\.bak(_|\.|$)' } | ForEach-Object {
  Move-Item $_.FullName -Destination (Join-Path $target $_.Name) -Force
}
```

Son kontrol:
```powershell
Get-ChildItem app,routes,core,services -Recurse -File | Where-Object { $_.Name -match '\.bak(_|\.|$)' }
```
