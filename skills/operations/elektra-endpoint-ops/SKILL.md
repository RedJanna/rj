---
name: elektra-endpoint-ops
description: Elektra fiyat/rezervasyon endpoint arizalarini operasyonel olarak teshis eder; config, auth, path, timeout ve fallback/handoff davranislarini guvenli sekilde yonetmek icin kullanilir.
---

# Elektra Endpoint Ops

## Overview

Bu skill Elektra entegrasyonundaki canli hata sinyallerini (401/403/404/405/timeout/success:false) kok nedene indirger ve dogru aksiyon plani uretir. Odak: dogru fiyat cevabi veya guvenli handoff; asla uydurma fiyat uretimi yok.

## Ne Zaman Kullanilir

- `elektra_price_unavailable` reason_code artisinda.
- `ElektrawebConfigError` veya `ElektrawebAuthError` loglandiginda.
- Fiyat sorulari fallback/handoff'a dusup cevap kalitesi bozuldugunda.
- Admin tarafinda reservation create/get/update/cancel endpointleri kirildiginda.

## Kapsam ve Sinirlar

- Kapsam: Elektra env, endpoint path adaylari, auth/login, response siniflandirma, fiyat-entry guard davranisi.
- Kapsam disi: intent semantik tuning (bu, `intent-ops-triage` skill alanidir).
- Kapsam disi: WhatsApp teslimat arizasi (bu, platform skill alanidir).

## Girdi Sozlesmesi

- Hata zamani, operation (`price`, `create_reservation`, `get_reservation`, vb.).
- HTTP status/body snippet veya app log ozeti.
- Ilgili mesaj ornegi ve status/reason_code.
- Mevcut env durumu (SET/NOT_SET, secret degeri degil).

## Operasyonel Workflow

1. Readiness kontrolu (secret degerini aciklama)
- Asagidaki degiskenlerin durumunu dogrula: `Elektra_Booking`, `ELEKTRA_API_BASE_URL`, `ELEKTRA_HOTEL_ID`, path override env'leri.
- Sadece SET/NOT_SET raporla; token veya sifreyi loglama.

2. Hata turunu siniflandir
- `config_error`: eksik env, bos endpoint listesi, yanlis path formati.
- `auth_error`: 401/403, captcha/WAF, token gecersizligi.
- `path_mismatch`: 404/405, endpoint adaylari uyumsuz.
- `runtime_error`: timeout/transport hatasi.
- `business_error`: `success:false`, quote mismatch, validation red.

3. Endpoint adaylarini dogrula
- Kod referansi: `app/services/elektraweb_booking_service.py` icindeki `_resolve_endpoint_candidates`.
- Hedef test:
```bash
pytest -q tests/unit/test_elektra_endpoint_candidates.py
```
- Canli probe gerekiyorsa (network ve izin ile):
```bash
python3 tools/elektra_endpoint_probe.py --hotel-id 21966
```

4. Price entry guard davranisini teyit et
- Kod referansi: `app/handlers/elektra_price_entry_handler.py`.
- Kritik noktalar:
- Transfer konusmasinda price tetiklenmemeli.
- Politika/bilgi sorulari Elektra'ya gitmemeli.
- Tarih yoksa history date re-use karari dikkatli olmali.
- Dil lock varken detector sonucu override edilmemeli.
- Hedef test:
```bash
pytest -q tests/unit/test_elektra_price_entry_handler.py
```

5. Chat fallback guvencesini dogrula
- Kod referansi: `app/routes/chat_routes.py`.
- Price niyeti olup Elektra sonucu yoksa `handoff` + `elektra_price_unavailable` beklenir.
- Hedef test:
```bash
pytest -q tests/unit/test_chat_pipeline_routes.py -k "price_intent_without_elektra_result or low_confidence_known_intent"
```

6. Aksiyon plana cevir
- Config/path problemi: env ve endpoint path duzelt, test + smoke tekrar.
- Auth problemi: key/captcha rotasyonu ve login dogrulama.
- Runtime problemi: timeout/transport gozden gecir, gecici handoff guvencesi koru.
- Business problemi: payload/quote tutarliligini kontrol et, gerekiyorsa booking fiyatini yeniden cek.

## Hata -> Aksiyon Matrisi

- 401/403:
- `Elektra_Booking` token formati, `ELEKTRA_X_CAPTCHA`, WAF politikasi kontrol edilir.
- 404/405:
- `ELEKTRA_*_PATHS` override degerleri ve default candidate listeleri guncellenir.
- `success:false` + quote mismatch:
- response body'den gerekli quote cikarimi ve booking payload tutarliligi incelenir.
- timeout/transport:
- gecici handoff korunur, retry/backoff ayari degerlendirilir.

## Cikti Formati (Ops Raporu)

- Incident: hangi operasyon kirildi.
- Classification: config/auth/path/runtime/business.
- Evidence: ilgili log satiri, endpoint adayi, status code.
- Action: uygulanan degisiklikler.
- Validation: calisan test komutlari ve sonuclar.
- Safety: fiyat uydurulmadi, handoff guard korundu.

## Dosya Haritasi

- `app/services/elektraweb_booking_service.py`
- `app/handlers/elektra_price_entry_handler.py`
- `app/routes/chat_routes.py`
- `tools/elektra_endpoint_probe.py`
- `tests/unit/test_elektra_endpoint_candidates.py`
- `tests/unit/test_elektra_price_entry_handler.py`
- `tests/unit/test_chat_pipeline_routes.py`
- `start_backend.bat`

## Guvenlik ve Operasyon Kurallari

- Secret degerler raporda maskelenir.
- Mutating endpoint probe (`--include-mutating`) varsayilan degildir; sadece acik ihtiyacta.
- Fiyat/musaitlik sorusunda Elektra sonucu yokken LLM serbest fiyat cevabi uretilmez.
