---
name: intent-ops-triage
description: Intent routing sapmalarini operasyonel olarak triage eder; yanlis intent secimi, gereksiz handoff, yanlis clarify dongusu ve PRICE vs BOOKING cakismalarinda kullan.
---

# Intent Ops Triage

## Overview

Bu skill, chat pipeline icindeki intent kararinin neden beklenenden farkli oldugunu sistematik olarak tespit etmek icin kullanilir. Amaç hizli degil, dogru teshis koymaktir: olay yeniden uretilir, kok neden siniflandirilir, duzeltme kapsamli testle dogrulanir.

## Ne Zaman Kullanilir

- Kullaniciya yanlis akisa giren cevap veriliyorsa (or. price yerine booking).
- `handoff` veya `clarify_required` beklenmedik bicimde tetikleniyorsa.
- `OUT_OF_SCOPE_OTHER` fazla artiyor veya bilinen intentler dusuk confidence ile dagiliyorsa.
- Yeni intent ornekleri eklendikten sonra regressions goruluyorsa.
- `chat_routes` uzerindeki guard/override sirasi degistiginde davranis kaydiysa.

## Kapsam ve Sinirlar

- Kapsam: intent tanilama, intent zorlamalari, slot-clarify etkisi, unknown-guard etkisi.
- Kapsam disi: Elektra endpoint arizasi kozu, network/WAF sorunu, WhatsApp delivery sorunu.
- Not: Local FAQ sadece PRICE/BOOKING yonlendirmesini etkiledigi kadar ele alin.

## Girdi Sozlesmesi

- Problemli mesaj ornegi (ham metin).
- Beklenen intent ve gercek intent/status/reason_code.
- Mumkunse 3-5 turn conversation history.
- Hangi ortamda goruldugu (local/test/live), tarih-saat ve correlation id.

## Operasyonel Workflow

1. Olayi sabitle
- Mesaj, expected intent, actual intent/status ve reason_code kaydini netlestir.
- Ilk mesaj mi devam mesaji mi oldugunu belirle (ilk mesaj welcome guard sonucu etkiler).

2. Reproduction kur
- Once hedef unit testleri calistir:
```bash
pytest -q tests/unit/test_intent_router_service.py tests/unit/test_intent_policy_service.py tests/unit/test_chat_pipeline_routes.py
```
- Gerekirse tek testi izole kos:
```bash
pytest -q tests/unit/test_chat_pipeline_routes.py -k "unknown_guard or price_intent_without_elektra_result"
```

3. Karar zincirini asama asama izle
- Semantic layer: `app/services/intent_semantic_service.py`
- Policy layer: `app/services/intent_policy_service.py`
- Normalizer/force layer: `app/services/intent_normalizer_service.py`
- Router orchestration: `app/routes/chat_routes.py`
- Slot contract: `app/content/intent_slot_contract.py`
- Taxonomy/threshold: `app/content/intent_taxonomy.py`

4. Koku nedeni siniflandir
- `semantic_coverage_gap`: ornekler yetersiz, yeni varyantlari yakalayamiyor.
- `policy_mapping_gap`: intent dogru ama tool/required_slot policy yanlis.
- `override_collision`: explicit booking/price zorlugu current intent ile cakisiyor.
- `slot_merge_or_clarify_issue`: history merge veya missing slot karari hatali.
- `unknown_guard_false_positive`: bilinen intent dusuk confidence ile gereksiz handoff.

5. Duzeltmeyi minimal tut
- Once en dar alanda degisiklik yap (or. bir helper veya bir threshold).
- Guard sirasini degistiriyorsan mutlaka ilgili regression test ekle.
- PRICE niyeti varsa LLM fallback ile fiyat uretimine izin verme.

6. Dogrulama
- Degistirdigin bolgeye gore test paketini tekrar calistir.
- En az bir negatif test ekle: "bu degisiklik su akisi bozmamali".

## Cikti Formati (Ops Raporu)

Rapor su alanlari zorunlu icermeli:
- Incident: tek cumle ozet.
- Expected vs Actual: intent/status/reason_code farki.
- Root Cause Class: yukaridaki siniflardan biri.
- Evidence: ilgili dosya ve test adlari.
- Fix Plan: degisecek dosyalar ve risk.
- Validation: calisan test komutlari ve sonuc.
- Residual Risk: bilinen kalan riskler.

## Dosya Haritasi

- `app/routes/chat_routes.py`
- `app/services/intent_router_service.py`
- `app/services/intent_policy_service.py`
- `app/services/intent_normalizer_service.py`
- `app/services/intent_semantic_service.py`
- `app/content/intent_slot_contract.py`
- `app/content/intent_taxonomy.py`
- `app/content/scenario_intent_examples.json`
- `tests/unit/test_chat_pipeline_routes.py`
- `tests/unit/test_intent_router_service.py`
- `tests/unit/test_intent_policy_service.py`

## Guvenlik ve Kalite Kurallari

- Sadece bu incident ile ilgili dosyalari degistir; unrelated refactor yapma.
- Low-confidence guard gevsetmesi yapiliyorsa, `KNOWN_AUTO_INTENTS` ve regression test birlikte guncellenmeli.
- "Fix" adina handoff guard'larini tamamen devre disi birakma.
