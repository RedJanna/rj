---
name: chat-platform-ops-guard
description: Chat platformunun operasyonel hazirlik ve guvenlik kontrollerini yapar; env/readiness, health endpointleri, temel smoke ve fallback/handoff guvencelerini dogrulamak icin kullanilir.
---

# Chat Platform Ops Guard

## Overview

Bu skill platform seviyesinde "servis ayakta mi ve guvenli mi" sorusunu cevaplar. Derin intent tuning veya Elektra endpoint cerrahisi yapmaz; onlarin bozuldugu noktayi tespit edip ilgili skill'e devreder.

## Ne Zaman Kullanilir

- Yeni deploy sonrasi operasyonel readiness kontrolu.
- "chat calisiyor ama davranis tutarsiz" sikayeti.
- Health endpoint, env, preflight veya webhook hatasi supheleri.
- Incident sonrasi hizli durum tespiti ve risk raporu ihtiyaci.

## Kapsam ve Sinirlar

- Kapsam: health check, startup env readiness, kritik flag kontrolu, temel chat smoke, handoff/fallback guvenceleri.
- Kapsam disi: intent siniflandirma kok neden analizi (`intent-ops-triage`).
- Kapsam disi: Elektra endpoint path/auth tuning (`elektra-endpoint-ops`).

## Operasyonel Workflow

1. Servis saglik kontrolu
```bash
curl -sS http://127.0.0.1:8000/health
curl -sS http://127.0.0.1:8000/api/v1/health
```
- 200 disinda sonuc varsa once platform problemi olarak ele al.

2. Env readiness kontrolu (deger degil, durum)
- Referans dosya: `sensitive_environment_variables.txt`.
- Kritik degiskenler: `OPENAI_API_KEY`, `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID`, `Elektra_Booking`, `ADMIN_TOKEN`.
- Gerekiyorsa settings semasini cek: `app/core/settings_service.py` icindeki `ENV_SETTINGS`.

3. Startup ve preflight baglamini kontrol et
- Referans: `start_backend.bat`, `tools/preflight_check.py`.
- `BACKEND_PREFLIGHT`, `ELEKTRA_*`, `BACKEND_RUNNER`, `BACKEND_PORT` gibi degerlerin beklenen oldugunu teyit et.

4. Temel chat smoke
- Hedef: chat route cevap veriyor mu, ilk mesaj welcome calisiyor mu, kritik handoff kurali devrede mi.
- Kullanilabilecek araclar:
```bash
python3 tools/smoke_chat.py
python3 tools/run_whatsapp_regression.py --language-smoke
```

5. Sorun siniflandir ve devret
- Intent kaynakliysa: `intent-ops-triage`.
- Elektra kaynakliysa: `elektra-endpoint-ops`.
- Platform kaynakliysa: env/startup/health aksiyonu ile devam et.

## Hizli Risk Matrisi

- `health_down`: servis ayakta degil, tum akislari etkiler.
- `critical_env_missing`: startup veya runtime davranislari guvensiz.
- `smoke_failed`: route yanitliyor ama guard/fallback bozuk.
- `external_dependency_risk`: Elektra/WhatsApp bagimliligi kismi degrade.

## Cikti Formati (Ops Durum Ozeti)

- Platform Status: green/amber/red.
- Health: endpoint sonuc ozeti.
- Env Readiness: sadece SET/NOT_SET farklari.
- Smoke Result: gecen/kalan temel kontroller.
- Escalation: intent mi Elektra mi platform mu.
- Next Action: tek sayfalik uygulanabilir adim listesi.

## Dosya Haritasi

- `app/routes/chat_routes.py`
- `app/core/settings_service.py`
- `start_backend.bat`
- `sensitive_environment_variables.txt`
- `tools/smoke_chat.py`
- `tools/run_whatsapp_regression.py`
- `tests/unit/test_chat_pipeline_routes.py`

## Guvenlik Kurallari

- Secret degerleri asla rapora yazma.
- SET/NOT_SET envanteri ile calis; token/sifreyi terminalde echo etme.
- Operasyonel kontrol adimlari, canli trafikte mutating islem tetiklememeli.
