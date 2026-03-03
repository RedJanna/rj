# INTEGRATIONS — Dış Sistemler ve Kontratlar

## 1) WhatsApp (Meta Cloud API)
- Token: SET/NOT SET
- Phone ID: SET/NOT SET
- Webhook: n8n üzerinden

## 2) Elektraweb BookingAPI
- Base URL: https://bookingapi.elektraweb.com (varsayılan)
- Auth:
  - POST /login + Authorization: Bearer <API_KEY> → jwt
  - Sonraki çağrılar: Authorization: Bearer <JWT>
- Rezervasyon/price endpointleri:
  - Fiyat sorgu: `GET /hotel/{hotel-id}/price/`
  - Rezervasyon olusturma (aktif): `POST /hotel/{hotel-id}/createReservation`
  - Rezervasyon islem endpointleri (fallback/aday):
    - create: `/hotel/{hotel-id}/createReservation`, `/hotel/{hotel-id}/reservation/create`, `/hotel/{hotel-id}/reservations/create`
    - get: `/hotel/{hotel-id}/reservation`, `/hotel/{hotel-id}/getReservation`, `/hotel/{hotel-id}/reservation/detail`
    - list: `/hotel/{hotel-id}/reservationList`, `/hotel/{hotel-id}/reservations`, `/hotel/{hotel-id}/reservation/list`
    - update: `/hotel/{hotel-id}/updateReservation`, `/hotel/{hotel-id}/reservation/update`
    - cancel: `/hotel/{hotel-id}/cancelReservation`, `/hotel/{hotel-id}/reservation/cancel`
- Gerekli env:
  - `Elektra_Booking` (zorunlu)
  - `ELEKTRA_HOTEL_ID` (onerilen; varsayilan `21966`)
  - `ELEKTRA_WALKIN_AGENCY_ID` (opsiyonel ama onerilir; sayisal olmalidir)
- Opsiyonel endpoint override env (comma-separated):
  - `ELEKTRA_CREATE_RESERVATION_PATHS`
  - `ELEKTRA_GET_RESERVATION_PATHS`
  - `ELEKTRA_LIST_RESERVATIONS_PATHS`
  - `ELEKTRA_UPDATE_RESERVATION_PATHS`
  - `ELEKTRA_CANCEL_RESERVATION_PATHS`
- Odeme update profil env:
  - `PAYMENT_SUPPLIER_MODE` (`bookingapi` onerilen)
  - `PAYMENT_SUPPLIER_FALLBACK_HOTELADVISOR` (`false` onerilen; sadece acil fallback)
  - `PAYMENT_UPDATE_PROFILE` (`auto`, `tenant_21966`, `default`)
- Odeme update metrik eventleri (SQLite metrics):
  - `payment_update_ok`
  - `payment_pax_remap_ok`
  - `payment_quote_remap_ok`
- Not:
  - `ELEKTRA_WALKIN_AGENCY_ID` yoksa sistem, fiyat teklifinden gelen `price-agency-id` ile devam etmeyi dener.
  - Proje kokundeki `.env` dosyasi otomatik yuklenir.
  - Fallback mekanizmasi 404/405 durumunda bir sonraki endpoint adayini dener.
  - Canli endpoint doğrulama için:
    - `python tools/elektra_endpoint_probe.py --hotel-id 21966`
    - Mutating endpoint adaylari dahil: `python tools/elektra_endpoint_probe.py --hotel-id 21966 --include-mutating`

## 3) Cloudflare Tunnel
- Tunnel adı: nexlume-api
- Ingress/service: [HTTP mi HTTPS mi? — burada dokümante et]
