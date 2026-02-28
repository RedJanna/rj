# Release Notes

- Release date: 2026-02-28
- Commit: `c0a034c`
- Scope: WhatsApp hotel conversation stability, deterministic routing guards, and live regression tooling reliability.

## Highlights
- Cancellation handoff flow now preserves Turkish language lock when users send composite slot payloads (`Rez ID + Ad Soyad + 1/2`).
- Room suitability query (`2 adults + 1 child`) now asks for explicit dates instead of reusing stale history dates.
- Price comparison questions are no longer misclassified as reservation operation requiring `Rez ID`.
- Full regression script output is now UTF-8 safe on Windows terminals (fixes `cp1254` Unicode errors).

## Behavior Changes
- `X01` branch in mixed-language flow now correctly returns `Missing: date range`; follow-up date message continues flow (`X02`).
- Cancellation hard handoff remains deterministic after required slots are collected and reply language stays consistent.
- Off-topic questions during booking/pricing no longer break active flow.

## Files Changed
- `app/routes/chat_routes.py`
- `app/utils/message_utils.py`
- `app/handlers/elektra_price_entry_handler.py`
- `app/services/operational_rule_service.py`
- `tools/run_whatsapp_regression.py`
- `tests/unit/test_chat_language_policy.py`
- `tests/unit/test_message_utils.py`
- `tests/unit/test_elektra_price_entry_handler.py`
- `tests/unit/test_operational_rule_service.py`

## Validation
- Unit tests (targeted): `127 passed`
- Live regression (`--full-flow`): PASS
- Honeymoon scenario script: PASS
- Safety controls after tests:
  - `blacklist.json`: empty
  - `rate_limits.json.blocked`: empty
  - `paused_conversations.json.paused`: empty

## Risk / Compatibility
- No API contract changes.
- No migration required.
- Deterministic guards were tightened in routing/intent edges; expected impact is reduced false routing.
