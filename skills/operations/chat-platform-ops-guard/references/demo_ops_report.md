# Chat Platform Ops Guard - Demo Ops Report

## Demo - Deploy sonrasi readiness ve risk ozeti

- Run Timestamp:
  - 2026-03-04 13:52 +03:00

- Platform Status:
  - `amber`

- Health:
  - `GET /health`: 200
  - `GET /api/v1/health`: 200
  - Not: Uygulama ayakta, route cevap veriyor.

- Env Readiness (SET/NOT_SET):
  - `OPENAI_API_KEY`: SET
  - `WHATSAPP_TOKEN`: SET
  - `WHATSAPP_PHONE_ID`: SET
  - `Elektra_Booking`: NOT_SET
  - `ADMIN_TOKEN`: SET
  - Etki:
    - Chat cevabi calisir.
    - Fiyat/rezervasyon Elektra bagimli senaryolar degrade olur.

- Smoke Result:
  - Basit chat smoke: PASS
  - Ilk mesaj welcome davranisi: PASS
  - Price flow smoke (Elektra bagimli): FAIL -> beklenen guvenli handoff
  - Handoff fallback guvencesi: PASS (`reason_code=elektra_price_unavailable`)

- Escalation:
  - Birincil: `elektra-endpoint-ops`
  - Ikincil: `intent-ops-triage` (sadece Elektra duzeldikten sonra hala routing anomalisi varsa)

- Next Action:
  - 1. `Elektra_Booking` ortam degiskenini secret manager/OS env uzerinden set et.
  - 2. Endpoint probe ile path/auth dogrula.
  - 3. Price regression smoke tekrar calistir.
  - 4. Sonucu runbook'a incident kapama notu olarak isle.

- Residual Risk:
  - Elektra bagimli tum user sorulari canli ekibe dusecegi icin operasyonel yuk artar.
  - Bu durum uzun surerse SLA etkilenir.
