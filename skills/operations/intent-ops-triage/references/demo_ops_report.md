# Intent Ops Triage - Demo Ops Reports

## Demo 1 - PRICE yerine BOOKING gitmesi gerekirken yanlis yonlendirme

- Incident:
  - Tarih: 2026-03-04 13:05 +03:00
  - Mesaj: "14-18 Agustos icin deluxe oda rezervasyonunu baslatalim"
  - Sikayet: Kullanici booking baslatmak istiyor ama sistem price/clarify dongusune giriyor.

- Expected vs Actual:
  - Expected intent: `HOTEL_BOOKING_CREATE`
  - Actual intent: `PRICE_QUERY`
  - Actual status: `clarify_required`
  - Actual reason_code: `missing_required_slots`

- Root Cause Class:
  - `override_collision`

- Evidence:
  - `app/services/intent_normalizer_service.py`
    - `force_primary_intent_from_explicit_message(...)` icinde price marker booking markerin onune geciyor.
  - `app/routes/chat_routes.py`
    - `_force_primary_intent_from_explicit_message(...)` cagrisi sonrasi booking override tekrar kontrol edilse de mesajda fiyat markerlari oldugu icin PRICE tarafina geri cekiliyor.
  - Regression test boslugu:
    - Booking + date + room tipinin birlikte geldigi explicit create senaryosu yok.

- Fix Plan:
  - `force_primary_intent_from_explicit_message(...)` icinde su kurali ekle:
    - Explicit booking create sinyali varsa ve "baslatalim/create/start" niyeti acik ise PRICE marker varligina ragmen `HOTEL_BOOKING_CREATE` oncelikli olsun.
  - Yeni test ekle:
    - `tests/unit/test_chat_pipeline_routes.py`
    - "explicit booking create with room/date" senaryosunda booking chain calismali.

- Validation:
  - Komut:
    - `pytest -q tests/unit/test_intent_router_service.py tests/unit/test_intent_policy_service.py tests/unit/test_chat_pipeline_routes.py -k "booking or explicit or force_primary_intent"`
  - Beklenen:
    - Yeni test PASS
    - Fiyat akisini dogrudan tetikleyen mevcut testler PASS

- Residual Risk:
  - "rezervasyon + fiyat karsilastirma" gibi hibrit mesajlarda false booking riski olabilir.
  - Bu risk icin negatif test eklenmeli: sadece fiyat karsilastirma yapan cumle PRICE kalmali.


## Demo 2 - Bilinen intent low confidence nedeniyle gereksiz unknown handoff suphe

- Incident:
  - Tarih: 2026-03-04 13:22 +03:00
  - Mesaj: "14-18 agustos 2 kisi fiyat"
  - Sikayet: Bazi ortamlarda low confidence gorunuyor, ekip unknown handoff olacagini saniyor.

- Expected vs Actual:
  - Expected intent: `PRICE_QUERY`
  - Actual intent: `PRICE_QUERY` (semantic confidence dusuk)
  - Actual status: `handoff`
  - Actual reason_code: `elektra_price_unavailable`

- Root Cause Class:
  - `semantic_coverage_gap` degil, `unknown_guard_false_positive` degil.
  - Gercek neden: Elektra sonucunun donmemesi.

- Evidence:
  - `tests/unit/test_chat_pipeline_routes.py::test_chat_low_confidence_known_intent_does_not_force_unknown_guard_handoff`
  - Bilinen intentlerde unknown guard yerine Elektra handoff guvencesi calisiyor.

- Fix Plan:
  - Intent degil, Elektra operasyonu incelenmeli.
  - Bu incident `elektra-endpoint-ops` skilline devredilir.

- Validation:
  - Komut:
    - `pytest -q tests/unit/test_chat_pipeline_routes.py -k "low_confidence_known_intent"`
  - Beklenen:
    - `reason_code == elektra_price_unavailable`

- Residual Risk:
  - Ekip tarafinda yanlis triage (intent sanip Elektra kok nedenini kacirma) devam edebilir.
  - Runbook'ta "intent vs dependency" ayrim maddesi zorunlu tutulmali.
