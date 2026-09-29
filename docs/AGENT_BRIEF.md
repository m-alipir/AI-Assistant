# Active brief — /daily and Gmail live failure recovery

**Status:** REVIEWED PLAN APPROVED, LOCAL REPAIR ACTIVE (2026-09-29).
**Coordinator task:** 01a0d53c-870c-7303-b6f4-80a0c166a1ff.
**Old preparation/wait prompts are superseded. Execute the current assignment.**

## Outcome
- `/daily` returns a concise Turkish briefing or a truthful actionable result; the 2026-09-29 run acknowledged then immediately reported `Çalıştırma / beklenmeyen çalıştırma hatası`.
- `/gmail` returns Google sign-in when backend is genuinely ready, then a read-only mailbox sync. Current response is a missing-configuration gate.

## Reviewed repair order
1. Correlate one existing VDS `entry_point=telegram_daily` runtime record with the failed user run, using only status, terminal_error stage/reason, bounded category counts, editor status/input count and budget dimension. Confirm deployed revision. No rerun to collect evidence, no raw details/logs/mail/secret values. If no matching record, live cause remains unproven.
2. Locally fix the confirmed shared mapping defect: `run_rss_now` records validated diagnostics.terminal_error but `_daily_failure_details` can ignore it and show generic runtime_error. Map `sources` to a user-readable stage. Preserve failure provenance and budget dimension; no success fabrication. Focused synthetic tests for budget/runtime/category and Telegram catch paths.
3. Gmail: trace existing direct read-only OAuth readiness. Confirm safe presence booleans for enabled/client ID/client secret or file/stable encryption key or file/public origin/redirect; DB intent migration and allowlisted actor; bot and callback topology. Preserve one-use actor-bound intent and PKCE. Fix only demonstrated code defects. No new broker or paid dependency. Do not claim real sign-in without operator OAuth client/Google registration and a user test.
4. Acceptance: offline focused tests and relevant regression; safe VDS deployment after code ready. A bounded `/daily` and read-only Gmail test require explicit provider-call/time/USD cap approval. Use a listed personal Google test user and report only connection/sync counts. Stop on missing same-run evidence, readiness failure, callback mismatch, state loss or spend cap.

## Boundaries
- No other project work. No guessing root cause from screenshot alone. No raw production logs, env values, private email, access tokens, or full Admin details. External calls require separate scope and cost approval.
- Review found in-memory PKCE lasts 10 minutes; poller imports app.main:app; callback must reach same web worker/process and not restart between initiation/callback. Worker topology risk is conditional.
- `gmail.readonly` is restricted. Google Testing requires allowlisted user and refresh authorization expires after seven days; no zero-cost guarantee. Exact callback URI must match Google's registration. Backend OAuth app credential setup cannot be replaced by a Telegram button.
- Coordinator owns this brief/progress and production actions; fixer owns local app/test changes. Do not edit shared docs without assignment.

## Agent final
Four short headings: Result; Evidence / changes; Verification; Open items. Publish in worker task and one REPORT to coordinator; genuine blocker as one NEEDS_DECISION.