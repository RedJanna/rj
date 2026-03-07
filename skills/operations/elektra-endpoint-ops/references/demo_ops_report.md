# Elektra Endpoint Ops - Demo Ops Reports

## Demo 1 - Price intent var ama Elektra endpoint 404/405 nedeniyle handoff

- Incident:
  - Tarih: 2026-03-04 13:18 +03:00
  - Mesaj: "14-18 Agustos 2 yetiskin toplam fiyat nedir?"
  - Sonuc: `status=handoff`, `reason_code=elektra_price_unavailable`

- Classification:
  - `path_mismatch`

- Evidence:
  - Elektra cagrilarinda tekrarli `HTTP 404` / `HTTP 405`.
  - `app/services/elektraweb_booking_service.py` icinde operation endpoint adaylari denense de dogru path bulunamiyor.
  - Ornek kontrol:
    - `_resolve_endpoint_candidates("get_reservation", hotel_id)`
    - `_resolve_endpoint_candidates("list_reservations", hotel_id)`

- Action Plan:
  - `ELEKTRA_GET_RESERVATION_PATHS` ve `ELEKTRA_LIST_RESERVATIONS_PATHS` env override degerlerini guncelle.
  - Canli probe ile aday endpointleri siniflandir:
    - `python3 tools/elektra_endpoint_probe.py --hotel-id 21966`
  - 404/405 disi (`400/422` validation) veren endpointleri "possible_match" olarak aday tut.

- Validation:
  - `pytest -q tests/unit/test_elektra_endpoint_candidates.py`
  - `pytest -q tests/unit/test_elektra_price_entry_handler.py`
  - `pytest -q tests/unit/test_chat_pipeline_routes.py -k "price_intent_without_elektra_result"`
  - Beklenen:
    - Endpoint candidate testleri PASS
    - Price-entry guard testleri PASS
    - Hata varken bile guvenli handoff davranisi korunur.

- Safety:
  - Elektra sonucu yokken fiyat uretimi yok.
  - Secret degerler loglanmaz.

- Residual Risk:
  - Vendor tarafli path degisimi tekrar olursa ayni ariza doner.
  - Periyodik endpoint probe (read-only) operasyon takvimine alinmali.


## Demo 2 - Auth/captcha kaynakli erisim hatasi

- Incident:
  - Tarih: 2026-03-04 13:41 +03:00
  - Semptom: `ElektrawebAuthError`, status 401/403 dalgalanmasi
  - Etki: price ve reservation actionlarinda degrade

- Classification:
  - `auth_error`

- Evidence:
  - Login/JWT adimindan sonra API cagrilarinda 401/403.
  - `Elektra_Booking` set ama token formati/expire supheli.
  - Opsiyonel `ELEKTRA_X_CAPTCHA` eksik veya gecersiz.

- Action Plan:
  - `Elektra_Booking` anahtarini rotate et.
  - WAF/captcha gerekiyorsa `ELEKTRA_X_CAPTCHA` degerini guncelle.
  - Sadece SET/NOT_SET kontrolu raporla; tokeni terminale yazma.
  - Sonrasinda read-only endpoint probe tekrar calistir.

- Validation:
  - `python3 tools/elektra_endpoint_probe.py --hotel-id 21966`
  - Beklenen:
    - 401/403 yerine en az bir endpointte `validation_error_possible_match` veya 200.
  - Uygulama guvencesi:
    - `status=handoff` ve `reason_code=elektra_price_unavailable` fallback davranisi korunur.

- Safety:
  - Mutating probe (`--include-mutating`) varsayilan disinda.
  - Canli rezervasyon olusturan test islenmez.

- Residual Risk:
  - Kisa sureli vendor auth dalgalanmasi tekrar edebilir.
  - Retry/backoff ve incident alarm esiklerinin izlenmesi gerekir.
