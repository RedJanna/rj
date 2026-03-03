# Kurulum / Kullanım (Kısa)

## Dosyaları repo'ya koy
- docs/AI_BRIEF.md
- docs/RUNBOOK.md
- docs/INTEGRATIONS.md
- docs/CHANGELOG.md
- tools/generate_project_snapshot.py

## İlk çalıştırma (Windows)
CMD:
  py -3.10 tools\generate_project_snapshot.py --root C:\KassandraOpenAI

## Otomatik güncelle (Git hook)
1) hooks/post-commit dosyasını şuraya kopyala:
   .git/hooks/post-commit
2) Çalıştırılabilir yap (Git Bash):
   chmod +x .git/hooks/post-commit

Artık her commit'te docs/AI_BRIEF.md içindeki AUTOGEN bölümü ve docs/_generated çıktıları güncellenir.

# auto-commit test

# auto-commit test

## Test Profilleri (PowerShell)

Legacy (orchestrator kapali):
```powershell
cd C:\KassandraOpenAI
.\venv\Scripts\Activate.ps1
$env:FLOW_ORCHESTRATOR_MODE = "off"
pytest tests\golden\ -v -m golden --tb=short -ra
pytest tests\integration\test_api_routes.py -v --tb=short -ra
```

Gercekci (orchestrator aktif):
```powershell
cd C:\KassandraOpenAI
.\venv\Scripts\Activate.ps1
$env:FLOW_ORCHESTRATOR_MODE = "active"
pytest tests\golden\ -v -m golden --tb=short -ra
pytest tests\integration\test_api_routes.py -v --tb=short -ra
```

## StateStore Dosya Override (PowerShell)

Testleri kalici state dosyalarindan izole calistirmak icin:

```powershell
$env:KASSANDRA_ROUTING_STATE_FILE = "C:\KassandraOpenAI\data\routing_states.test.json"
$env:KASSANDRA_PRICE_FLOW_FILE = "C:\KassandraOpenAI\data\price_flows.test.json"
$env:KASSANDRA_FOLLOWUP_FILE = "C:\KassandraOpenAI\data\followups.test.json"
$env:KASSANDRA_REMINDERS_FILE = "C:\KassandraOpenAI\data\reminders.test.json"
$env:KASSANDRA_REMINDER_LOG_FILE = "C:\KassandraOpenAI\data\reminder_logs.test.json"
```

Ornek:
```powershell
$env:FLOW_ORCHESTRATOR_MODE = "active"
pytest tests\integration\test_api_routes.py -k "router_v2_ambiguity_prompt or domain_lock_choice_applies" -v --tb=short -ra
```

Tum desteklenen state/env override degiskenleri:
- `KASSANDRA_CONVERSATIONS_DIR`
- `KASSANDRA_MESSAGE_ID_FILE`
- `KASSANDRA_ROUTING_STATE_FILE`
- `KASSANDRA_PRICE_FLOW_FILE`
- `KASSANDRA_BOOKING_FLOW_FILE`
- `KASSANDRA_RESERVATIONS_DB`
- `KASSANDRA_RESERVATION_FLOW_FILE`
- `KASSANDRA_HOTEL_BOOKINGS_DB`
- `KASSANDRA_FOLLOWUP_FILE`
- `KASSANDRA_REMINDERS_FILE`
- `KASSANDRA_REMINDER_LOG_FILE`
- `KASSANDRA_PDF_CONFIG_FILE`

## Parallel Test Notu

`pytest -n 2` kullanimi icin:
```powershell
python -m pip install pytest-xdist
```

## Startup Env Hata Davranisi

Kritik bir env eksikse (ornegin `OPENAI_API_KEY`), uygulama process'i dusmez; `degraded` modda acilir ve `/health` endpoint'i acik hata detayi verir.

Ornek `/health` yaniti:
```json
{
  "status": "degraded",
  "env": "production",
  "startup_error": "RuntimeError",
  "startup_error_message": "Kritik ortam degiskenleri eksik: OPENAI_API_KEY. Ornek: PowerShell'de `$env:OPENAI_API_KEY = \"...\"` veya `.env` dosyasinda `OPENAI_API_KEY=...`."
}
```
