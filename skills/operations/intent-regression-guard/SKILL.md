---
name: intent-regression-guard
description: Intent/router/policy degisikliklerinden sonra kritik sohbet davranislarinda regresyon riski olup olmadigini hizli ve odakli sekilde kontrol eder. Intent, slot-clarify, unknown-guard ve price-vs-booking gecislerinde kullan.
---

# Intent Regression Guard

## Overview

Bu skill, intent tarafinda yapilan kod veya veri degisikliklerinin "yanlis akisa gitme" riskini release oncesi yakalamak icin kullanilir. Amaç tum testleri kosmak degil, en kritik akislari hizli tarayip risk raporu cikarmaktir.

## Ne Zaman Kullanilir

- `app/services/intent_*` dosyalarinda degisiklik yapildiysa.
- `app/routes/chat_routes.py` icindeki guard/override sirasi degistiyse.
- `app/content/scenario_intent_examples.json` guncellendiyse.
- Yeni bir intent eklendiyse veya threshold degerleri oynandiysa.

## Kapsam ve Sinirlar

- Kapsam: intent secimi, slot-clarify karari, unknown/handoff guard, booking-price gate.
- Kapsam disi: Elektra endpoint/network/auth arizasi.
- Kapsam disi: WhatsApp delivery/webhook altyapi sorunu.

## Girdi Sozlesmesi

- Degisen dosya listesi.
- Etkilenen intent(ler).
- En az 3 temsilci mesaj (happy-path, edge-case, negative).
- Beklenen davranis tanimi (intent/status/reason_code).

## Operasyonel Workflow

1. Degisiklik etki haritasi cikar
- Degisen dosyalari su listede esle:
- `intent_semantic_service.py`
- `intent_policy_service.py`
- `intent_normalizer_service.py`
- `chat_routes.py`
- `intent_slot_contract.py`

2. Kritik regresyon setini sec
- Price query yanitliyor mu?
- Explicit booking create yanlislikla price'a kayiyor mu?
- Low confidence bilinen intent gereksiz unknown handoff oluyor mu?
- Local/faq mesajlari booking/price zincirini bosuna tetikliyor mu?

3. Hedefli dogrulama komutlarini hazirla
```bash
PYTHONPATH=. pytest -q tests/unit/test_intent_router_service.py tests/unit/test_intent_policy_service.py
PYTHONPATH=. pytest -q tests/unit/test_chat_pipeline_routes.py -k "price or booking or unknown_guard"
```

4. Sonucu risk seviyesine cevir
- `low`: davranis degisikligi yok, kritik set yesil.
- `medium`: davranis degisimi var ama kontrollu.
- `high`: yanlis intent/handoff ile musteri etkisi var.

5. Aksiyon belirle
- `low`: merge uygun.
- `medium`: ek regression testiyle merge.
- `high`: merge blok, fix + yeniden dogrulama.

## Cikti Formati

- Change Scope:
- Impacted Intents:
- Regression Checks:
- Risk Level (`low|medium|high`):
- Blockers:
- Recommended Action:

## Dosya Haritasi

- `app/services/intent_router_service.py`
- `app/services/intent_policy_service.py`
- `app/services/intent_semantic_service.py`
- `app/services/intent_normalizer_service.py`
- `app/routes/chat_routes.py`
- `app/content/intent_slot_contract.py`
- `app/content/scenario_intent_examples.json`
- `tests/unit/test_intent_router_service.py`
- `tests/unit/test_intent_policy_service.py`
- `tests/unit/test_chat_pipeline_routes.py`

## References

- `references/regression_matrix.md`: Hangi degisiklikte hangi kontrol seti kosulur.

## Guvenlik Kurallari

- Secret/token degerlerini rapora yazma.
- Yalnizca ilgili intent dosyalarini degistir; ilgisiz refactor yapma.
- Musteri etkisi olan `high` riskte "test etmeden merge" yapma.
