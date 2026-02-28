## Summary
This PR stabilizes WhatsApp hotel conversation handling across pricing, cancellation, and mixed-language edge cases.

## What Changed
1. Language lock hardening for cancellation slot payloads.
2. Price-intent detection improvement for room suitability queries (adult+child) without explicit dates.
3. Operational RezID guard refinement to avoid false positives on price comparison questions.
4. Elektra entry guard to prevent stale date reuse in suitability messages.
5. Regression tool fix for Windows console encoding (`UTF-8` output safety).

## Why
- Prevent language drift in critical handoff messages.
- Keep booking flow robust when users ask context-switch/off-topic questions.
- Ensure deterministic prompts for missing dates in child-policy-like availability queries.
- Make regression runs reliable in Windows terminals.

## Testing
- `pytest -q tests/unit/test_elektra_price_entry_handler.py tests/unit/test_operational_rule_service.py tests/unit/test_message_utils.py tests/unit/test_chat_language_policy.py`
- `python tools/run_whatsapp_regression.py --base-url http://127.0.0.1:8000 --phone 905399988887 --full-flow`
- `powershell -File tools/tmp_honeymoon_live_test.ps1`

## Result
- Targeted unit suite: `127 passed`
- Full live flow regression: PASS
- Honeymoon scenario flow: PASS

## Notes
- No schema or endpoint changes.
- No data migration required.
