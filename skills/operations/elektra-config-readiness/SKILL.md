---
name: elektra-config-readiness
description: Elektra fiyat/rezervasyon akisi icin ortam degiskeni, endpoint adaylari ve temel baglanti hazirligini kontrol eder; deploy oncesi go/no-go karari vermek icin kullanilir.
---

# Elektra Config Readiness

## Overview

Bu skill Elektra entegrasyonunun calismasi icin gerekli minimum hazirlik seviyesini olcer. Cikti olarak "hazir / riskli / hazir degil" siniflamasi ve net aksiyon listesi verir.

## Ne Zaman Kullanilir

- Yeni ortama cikis (staging/prod) oncesi.
- Fiyat sorulari handoff'a dusmeye basladiysa.
- `Elektra_Booking` degisimi (rotate) sonrasi.
- Endpoint override env'leri guncellendiyse.

## Kapsam ve Sinirlar

- Kapsam: env hazirligi, endpoint candidate mantigi, read-only probe, basic chat price smoke.
- Kapsam disi: intent semantik tuning.
- Kapsam disi: mutating reservation operasyonlari (create/update/cancel testleri).

## Girdi Sozlesmesi

- Ortam adi (`dev|staging|prod`)
- SET/NOT_SET envanteri
- Son hata sinyali (varsa HTTP status/reason_code)
- Hotel id bilgisi

## Operasyonel Workflow

1. Zorunlu degisken kontrolu (sadece SET/NOT_SET)
- `Elektra_Booking`
- `ELEKTRA_API_BASE_URL`
- `ELEKTRA_HOTEL_ID`

2. Onerilen degiskenler
- `ELEKTRA_GET_RESERVATION_PATHS`
- `ELEKTRA_UPDATE_RESERVATION_PATHS`
- `ELEKTRA_X_CAPTCHA` (ortama bagli)

3. Endpoint adaylari mantik kontrolu
- Kod referansi: `app/services/elektraweb_booking_service.py`
- `tests/unit/test_elektra_endpoint_candidates.py` icindeki senaryolarla uyumlu mu bak.

4. Read-only probe (gerekiyorsa)
```bash
python3 tools/elektra_endpoint_probe.py --hotel-id 21966
```
- 404/405 agirlikliysa path mismatch riski.
- 401/403 agirlikliysa auth/captcha riski.

5. Uygulama davranis guvencesi
- Fiyat akisi yoksa sistem `elektra_price_unavailable` ile guvenli handoff'a dusmeli.
- Kod referansi: `app/routes/chat_routes.py`

6. Karar ver
- `ready`: deploy uygun
- `risky`: deploy kosullu (aksiyonla)
- `not_ready`: deploy blok

## Cikti Formati (Go/No-Go)

- Environment:
- Mandatory Env Check:
- Optional Env Check:
- Endpoint Probe Summary:
- App Safety Check:
- Final Decision (`ready|risky|not_ready`):
- Required Actions:

## Dosya Haritasi

- `app/services/elektraweb_booking_service.py`
- `app/handlers/elektra_price_entry_handler.py`
- `app/routes/chat_routes.py`
- `tools/elektra_endpoint_probe.py`
- `tests/unit/test_elektra_endpoint_candidates.py`
- `tests/unit/test_elektra_price_entry_handler.py`
- `tests/unit/test_chat_pipeline_routes.py`

## References

- `references/readiness_matrix.md`

## Guvenlik Kurallari

- Token/secret degerlerini rapora yazma.
- Mutating endpoint testlerini varsayilan akisa koyma.
- "Ready" demeden once en az bir safety kontrolu yazili olarak raporla.
