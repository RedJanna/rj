# RUNBOOK — Çalıştırma / Sorun Giderme

## 1) Günlük başlatma
- Backend
- n8n
- Cloudflare tunnel

> Not: Script'ler ayrı tutulmalı: start_backend.bat / start_n8n.bat / start_cloudflare.bat
> Not: Backend acilisinda `ELEKTRA_WALKIN_AGENCY_ID` bos ise varsayilan `247664` atanir.

## 2) Sağlık kontrol
- Backend: http://127.0.0.1:8000/health
- n8n editor: https://webhook.nexlumeai.com (varsa)
- Tunnel: cloudflared loglarında connected/registered

## 3) En sık sorunlar
### 3.1 fastapi yok / modül yok
- Çözüm: venv + pip install

### 3.2 requirements.txt encoding hatası
- Çözüm: UTF-8 requirements_pip.txt kullan

### 3.3 n8n kapanıyor
- Çözüm: n8n PATH / Node kurulum kontrolü (where n8n, where node)

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
