# Handoff Quality Matrix

## 1) Reason Code Bazli Kontrol

- `elektra_price_unavailable`
  - Beklenen: Elektra sonucu yokken handoff
  - Kalite notu: metin net olmalı, fiyat uydurmamali

- `novel_topic_out_of_scope`
  - Beklenen: alan disi soru veya guvensiz belirsizlik
  - Kalite notu: kullaniciya neden devredildigi sade anlatilmali

- `low_confidence_below_auto_threshold`
  - Beklenen: confidence cok dusuk ve bilinen otomatik intent degil
  - Kalite notu: gereksiz handoff oranı izlenmeli

## 2) Kalite Puanlama (0-2)

Her handoff kaydi icin:
- Dogruluk:
  - 0 = gereksiz
  - 1 = tartismali
  - 2 = dogru

- Mesaj Netligi:
  - 0 = anlasilmaz
  - 1 = idare eder
  - 2 = net

- Guvenlik:
  - 0 = riskli (uydurma/yanlis bilgi)
  - 1 = kismen guvenli
  - 2 = tam guvenli

Toplam kalite puani = 6 uzerinden.

## 3) Hedef KPI

- Ortalama kalite puani >= 5.0
- Gereksiz handoff orani <= %15
- `elektra_price_unavailable` metin uygunluk orani >= %95

## 4) Aksiyon Esikleri

- Ortalama kalite < 4.0:
  - Acil iyilestirme
  - Guard ve mesaj metni birlikte guncellenir

- Gereksiz handoff > %20:
  - Intent/policy triage tetiklenir
  - Hedefli regression test seti calistirilir

