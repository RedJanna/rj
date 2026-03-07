# Operations Skill Index

Bu dosya, operasyonel skill'lerin "hangi belirtiye hangi skill" mantigiyla hizli secilmesi icin hazirlandi.

## 1) Hızlı Karar Tablosu

| Belirti / Durum | Kullanılacak Skill | Neden |
|---|---|---|
| Sistem ayakta mi emin degilim, health/env kontrolu lazim | `chat-platform-ops-guard` | Once platform hazirligini dogrular |
| Fiyat/musaitlik cevaplari handoff'a dusuyor, Elektra supheli | `elektra-endpoint-ops` | Endpoint/auth/path/runtime arizayi teshis eder |
| Deploy oncesi Elektra hazirlik raporu istiyorum | `elektra-config-readiness` | Go/No-Go readiness karari verir |
| Kullaniciya yanlis intent/akis seciliyorsa | `intent-ops-triage` | Intent/router/guard kok nedenini bulur |
| Intent kodu degisti, regressions var mi bakmak istiyorum | `intent-regression-guard` | Hedefli regresyon risk taramasi yapar |
| Canli handoff kalitesi dustu / gereksiz handoff artisi var | `live-handoff-quality-check` | Handoff dogruluk + mesaj kalitesi denetler |

## 2) Skill Kartları

### `chat-platform-ops-guard`
- Konum: `skills/operations/chat-platform-ops-guard`
- Odak: health, env readiness, temel smoke
- Cikti: platform risk ozeti + escalation yolu

### `elektra-endpoint-ops`
- Konum: `skills/operations/elektra-endpoint-ops`
- Odak: Elektra endpoint hatalari (401/403/404/405/timeout/success:false)
- Cikti: incident sinifi + guvenli aksiyon plani

### `elektra-config-readiness`
- Konum: `skills/operations/elektra-config-readiness`
- Odak: deploy oncesi Elektra hazirlik seviyesi
- Cikti: `ready | risky | not_ready` karari

### `intent-ops-triage`
- Konum: `skills/operations/intent-ops-triage`
- Odak: yanlis intent, gereksiz handoff, clarify dongusu
- Cikti: root cause + fix kapsamı + validation planı

### `intent-regression-guard`
- Konum: `skills/operations/intent-regression-guard`
- Odak: intent degisikliklerinden sonra regresyon riski
- Cikti: risk seviyesi (`low|medium|high`) + merge onerisi

### `live-handoff-quality-check`
- Konum: `skills/operations/live-handoff-quality-check`
- Odak: handoff dogruluk ve mesaj kalitesi
- Cikti: kalite raporu + KPI/aksiyon

## 3) Birlikte Kullanım (Önerilen Sıra)

1. `chat-platform-ops-guard`
2. Sorun Elektra ise:
- `elektra-config-readiness` (hazirlik) -> `elektra-endpoint-ops` (ariza)
3. Sorun intent/handoff ise:
- `intent-ops-triage` -> `intent-regression-guard` -> `live-handoff-quality-check`

## 4) Tek Cümlelik Seçim Kuralı

- "Sistem ayakta mi?" -> platform skill
- "Fiyat motoru niye cevap vermiyor?" -> Elektra skill
- "Sistem niye yanlis anladi?" -> intent skill
- "Canli devir kalitesi niye dustu?" -> handoff quality skill

## 5) Vaka Bazli Mini Senaryolar

### Vaka 1: Fiyat sorusu ama cevapta handoff geliyor
- Ornek mesaj: "14-18 Agustos 2 yetiskin fiyat nedir?"
- Ilk skill: `elektra-config-readiness`
- Sonraki skill: `elektra-endpoint-ops`
- Beklenen cikti:
  - Ready degilse go/no-go raporu
  - Ariza varsa config/auth/path/runtime sinifi + aksiyon

### Vaka 2: "Rezervasyon baslatalim" diyor ama fiyat akisi aciliyor
- Ornek mesaj: "14-18 Agustos deluxe oda rezervasyonunu baslatalim"
- Ilk skill: `intent-ops-triage`
- Sonraki skill: `intent-regression-guard`
- Beklenen cikti:
  - Yanlis yonlendirme kok nedeni
  - Regresyon risk seviyesi ve merge karari

### Vaka 3: Handoff sayisi birden patladi
- Belirti: son saatlerde handoff oraninda ani artis
- Ilk skill: `live-handoff-quality-check`
- Sonraki skill: `intent-ops-triage` (gereksiz handoff suphesi varsa)
- Beklenen cikti:
  - Dogru/gereksiz handoff ayrimi
  - Mesaj kalite puani + acil iyilestirme listesi

### Vaka 4: Deploy sonrasi sistem tutarsiz davraniyor
- Belirti: bazen cevap veriyor, bazen vermiyor
- Ilk skill: `chat-platform-ops-guard`
- Sonraki skill: belirtiye gore `elektra-*` veya `intent-*`
- Beklenen cikti:
  - Platform risk ozeti
  - Dogru skill'e net escalation yolu

### Vaka 5: Intent kodunda degisiklik var, release oncesi kontrol lazim
- Belirti: `intent_*` veya `chat_routes` degisimi
- Ilk skill: `intent-regression-guard`
- Beklenen cikti:
  - Hedefli kontrol seti
  - Risk seviyesi (`low|medium|high`)
  - Release tavsiyesi (go/no-go)

## 6) Tek Satirlik Komut Seti (Vaka Baslangici)

Not:
- Bu komutlar "ilk kontrol" icindir.
- Detay analiz secilen skill dokumaninda devam eder.

### Vaka 1 (Fiyat sorusu handoff)
```bash
PYTHONPATH=. pytest -q tests/unit/test_chat_pipeline_routes.py -k "price_intent_without_elektra_result or low_confidence_known_intent"
```

### Vaka 2 (Rezervasyon yerine fiyat akisi)
```bash
PYTHONPATH=. pytest -q tests/unit/test_chat_pipeline_routes.py -k "explicit_booking or booking_flow_chain or price_flow_chain"
```

### Vaka 3 (Handoff patlamasi)
```bash
PYTHONPATH=. pytest -q tests/unit/test_chat_pipeline_routes.py tests/unit/test_chat_precheck_handler.py -k "handoff or unknown_guard or policy_guard"
```

### Vaka 4 (Deploy sonrasi tutarsizlik)
```bash
curl -sS http://127.0.0.1:8000/health && curl -sS http://127.0.0.1:8000/api/v1/health
```

### Vaka 5 (Release oncesi intent degisikligi)
```bash
PYTHONPATH=. pytest -q tests/unit/test_intent_router_service.py tests/unit/test_intent_policy_service.py tests/unit/test_chat_pipeline_routes.py -k "price or booking or unknown_guard"
```
