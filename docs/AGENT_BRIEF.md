# Active agent brief — M22.2/M22.3 acceptance

Date: 2026-09-25. `PROGRESS.md` owns implementation status; replace this brief for the next request.

## Accepted locally

- Daily Telegram briefing: compact Turkish output, subject-based questions, preparation 15 minutes before the configured delivery time, hold-until-target or explicit late delivery, ordered safe warning, bounded error categories. Historical 2026-09-25 error subcategories remain unknown.
- Source management: long-URL layout, existing-row edit, deterministic topic suggestion, and one allow-listed Telegram operator question for an ambiguous source. Pending questions and bulk imports use the same bounded path; no model call.
- Full offline gate: 339 passed, 6 skipped PostgreSQL integration cases, Ruff/compileall/Alembic/diff checks passed. Independent reviewers accepted the final scoped fixes.

## Remaining acceptance

1. In a disposable migrated PostgreSQL database, verify category compare-and-set, stable source ID and pending-question receipt behavior. No production data.
2. Only in an authorized production change window, deploy and observe one controlled configured-time briefing, the safe error-category counts, and one ambiguous-source question/answer in the configured operator chat. Do not claim the historical four RSS/two YouTube error causes from aggregate counts.

Source layout was visually checked in headless Chrome at desktop and 500 CSS px. A separate non-source table still widens `/admin` by 85px at 500px; defer that unrelated layout issue unless requested.

All agents use the standing Luna xhigh pool. Keep secrets, message text, raw source/provider content and production data out of reports. Ask the user for approval before production deployment or any destructive operation.
