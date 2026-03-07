# Intent Regression Matrix

Bu tablo, degisiklik tipine gore minimum kontrol setini secmek icin kullanilir.

## 1) Degisiklik -> Kontrol Seti

- `intent_semantic_service.py` degisti:
  - `test_intent_router_service.py`
  - `test_chat_pipeline_routes.py -k "unknown_guard or price"`

- `intent_policy_service.py` degisti:
  - `test_intent_policy_service.py`
  - `test_chat_pipeline_routes.py -k "booking_flow_chain or price_flow_chain"`

- `intent_normalizer_service.py` degisti:
  - `test_chat_pipeline_routes.py -k "explicit_booking or payment_followup or cjk"`

- `chat_routes.py` intent/guard bolumu degisti:
  - `test_chat_pipeline_routes.py` (hedefli filtre yerine genis kosum onerilir)
  - Kritik: `price_intent_without_elektra_result`, `low_confidence_known_intent`

- `scenario_intent_examples.json` degisti:
  - `test_intent_router_service.py`
  - `test_intent_semantic_external_scenarios.py`

## 2) Risk Skorlama

- `low`:
  - Kapsam dar
  - Hedefli testler yesil
  - Davranis degisikligi yok

- `medium`:
  - Kapsam orta
  - Davranis degisikligi var ama beklenen
  - En az bir yeni regression testi eklendi

- `high`:
  - Core routing/guard degisti
  - Yanlis handoff veya yanlis flow riski var
  - Testler eksik veya kirmizi

## 3) Merge Karari

- `low` -> merge uygun
- `medium` -> merge + takip notu
- `high` -> merge blok, fix zorunlu

