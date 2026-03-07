---
name: live-handoff-quality-check
description: Canliya dusen handoff mesajlarinin dogruluk, gereklilik ve musteri deneyimi kalitesini denetler. Gereksiz handoff artisinda veya handoff metin kalitesi dustugunde kullanilir.
---

# Live Handoff Quality Check

## Overview

Bu skill, "canli destek devri dogru yerde mi oluyor, metin guvenli ve anlasilir mi?" sorusuna cevap verir. Hedef, gereksiz handoff'lari azaltmak ve gerekli handoff'lari net/guvenli metinle sunmaktir.

## Ne Zaman Kullanilir

- Handoff oraninda ani artis varsa.
- Kullanici "neden canli destege atti?" sikayeti geliyorsa.
- `reason_code` dagilimi anormal degisiyorsa.
- Yeni guard degisikligi sonrasi kalite kontrol gerekiyorsa.

## Kapsam ve Sinirlar

- Kapsam: handoff tetikleme dogrulugu, reason_code tutarliligi, musteriye giden mesaj kalitesi.
- Kapsam disi: Elektra endpoint cerrahisi (bu `elektra-endpoint-ops`).
- Kapsam disi: intent model tuning (bu `intent-ops-triage`).

## Girdi Sozlesmesi

- Son 24 saatten temsilci handoff ornekleri (mesaj + status + reason_code).
- Beklenen davranis politikasi (hangi durumda handoff olmali/olmamalı).
- Kullanici sikayet ornekleri (varsa).

## Operasyonel Workflow

1. Handoff envanterini cikar
- Hangi `reason_code` ne kadar goruluyor?
- En cok tekrar eden 3 neden hangisi?

2. Ornekleri kalite sinifina ayir
- `dogru_handoff`: sistemde net belirsizlik/eksik bagimlilik var.
- `gereksiz_handoff`: aslinda cevaplanabilecek konuda handoff olmus.
- `zayif_mesaj`: handoff dogru ama metin anlasilmaz/eksik.

3. Metin kalite kontrolu
- Mesaj kisa ve net mi?
- Teknik detay/icerik kirilmasi var mi?
- Kullaniciya sonraki adim acik mi?

4. Kok neden bagla
- `unknown_guard` artisina bagli mi?
- `elektra_price_unavailable` artisina bagli mi?
- `policy_guard` yan etkisi var mi?

5. Iyilestirme plani cikar
- Kisa vadede: metin duzeltmesi / threshold ince ayar / guard istisnasi.
- Orta vadede: test ekleme ve dashboard alarm esigi.

## Cikti Formati (Kalite Raporu)

- Time Window:
- Top Reason Codes:
- Correct vs Unnecessary Handoff:
- Message Quality Issues:
- Root Cause Hypothesis:
- Immediate Actions:
- Follow-up Actions:

## Dosya Haritasi

- `app/routes/chat_routes.py`
- `app/handlers/chat_precheck_handler.py`
- `app/handlers/handoff_handler.py`
- `app/services/intent_policy_service.py`
- `tests/unit/test_chat_pipeline_routes.py`
- `tests/unit/test_chat_precheck_handler.py`
- `tests/integration/test_api_routes.py`

## References

- `references/handoff_quality_matrix.md`

## Guvenlik Kurallari

- Telefon/PII degerlerini maskele.
- Handoff metinlerini raporlarken sadece gerekli kisimlari tut.
- Musteri guveni icin "emin degilse canli destek" ilkesini bozmadan iyilestirme yap.
