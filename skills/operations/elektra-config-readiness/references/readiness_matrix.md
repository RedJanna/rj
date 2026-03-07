# Elektra Readiness Matrix

## 1) Zorunlu Degiskenler

- `Elektra_Booking`
- `ELEKTRA_API_BASE_URL`
- `ELEKTRA_HOTEL_ID`

Kurallar:
- Herhangi biri `NOT_SET` ise sonuc en fazla `not_ready`.
- Secret degerleri asla raporlanmaz.

## 2) Probe Sonucu Siniflama

- Cogu endpoint `404/405`:
  - Sinif: `path_risk`
  - Aksiyon: path override/env adaylarini guncelle

- Cogu endpoint `401/403`:
  - Sinif: `auth_risk`
  - Aksiyon: key/captcha kontrolu, rotate

- En az bir endpoint `200` veya `400/422` (validation):
  - Sinif: `reachable`
  - Aksiyon: app-level smoke'e gec

## 3) Uygulama Guvenlik Davranisi

- Price sonucu yoksa:
  - `status=handoff`
  - `reason_code=elektra_price_unavailable`
- Bu davranis bozuksa:
  - Risk seviyesi otomatik `high`

## 4) Final Karar

- `ready`:
  - Mandatory env tam
  - Probe `reachable`
  - App safety guard calisiyor

- `risky`:
  - Mandatory env tam
  - Probe kismi sorunlu
  - Safety guard calisiyor

- `not_ready`:
  - Mandatory env eksik
  - veya safety guard calismiyor

