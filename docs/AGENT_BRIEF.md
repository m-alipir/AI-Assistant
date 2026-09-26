# Active brief — compact Telegram summary repair

## Current assignment — delivery diagnosis and Telegram controls

- Production deployment complete for commit 912b563: new stash/pop verified, env unchanged, migration successful before app recreation, app/DB healthy and health HTTP 200. User can test `/daily` and `/gmail`; no live command/provider acceptance claimed. Deferred Google-login work awaits separate assignment.

- Acceptance complete: disposable PostgreSQL upgrade/backfill/history, concurrency/slot identity and Gmail interval constraints passed. Previous 92 focused tests passed. No remaining local blocker; code not committed/pushed/deployed. Next production action must migrate to 0029 before new app startup, preserving server overrides and .env. Do not start deferred Google-login task automatically.

- Implementation report received: 92 focused tests pass, additive migration 0029 added. Remaining acceptance: disposable local PostgreSQL migration/history/slot-idempotency verification by the same Fixer, no automatic reviewer. Production deployment remains pending; personal Google login still deferred.

- Sequencing correction: finish this assignment before assigning personal Google-login simplification. The latter is deferred; do not investigate or implement it during this task.

- User-approved scheduling decision: replace coarse once-per-local-day claim with idempotency per actual scheduled delivery instant. Different future time on the same day is eligible; same slot after restart/concurrent attempts remains single. Preserve existing records and automatic duplicate protection; any schema adjustment must be additive and reported for deployment. Manual `/daily` remains distinct and bounded.

- Diagnose absent 22:00 delivery at 22:07: configured effective schedule (DB override versus env), timezone, durable daily claim, preparation state and notification delivery. Do not assume source count is the cause. Production evidence only safe status/counters and approved configuration values; no mail bodies, tokens or raw logs.
- Add `/daily` to request a fresh daily briefing using existing shared orchestration, bounded budget, deduplication and busy/claim safeguards; distinguish it from reading the latest stored `/ozet`.
- Default Gmail read-only polling to hourly; `/gmail` shows/sets a validated polling interval using existing persisted preferences and scheduler facilities. Polling means detection at the next interval, not instant push.
- Do not display source links in the daily Telegram summary; retain internal provenance. User originally deferred this to the next fix, which this assignment now prepares.
- One reused Fixer owns these related scheduler/Telegram changes. Coordinator owns docs. Focused offline fakes only; production diagnosis does not authorize ingestion/provider spending, mailbox reads, schedule changes, commit/push or deployment. Return evidence, checks, decisions and exact safe diagnostics if further authorization is needed. No automatic reviewer pass.

Date: 2026-09-26. `PROGRESS.md` owns status. Fixer reported the narrow repair ready; independent
review is running in the existing Luna high reviewer task. No production acceptance is claimed.

## Reported behavior

- Daily output arrives as separate article cards, with long text, English and technical field labels,
  rather than one short Turkish daily summary.
- First-14-day Yes/No buttons return invalid-feedback messages. App and poller are separate services;
  process-local token storage is a hypothesis to check, not a proven cause.
- The reported run has many budget-exhausted outcomes; the delivery header reports one second late.
  Historical local tests and basic deployment health do not establish correct live interaction.

## Findings and remaining evidence

- Final tie-order review accepted; reviewer ran the actual RSS selection regression (one passed). No remaining local review blocker for this repair. Next: prepare protected server transfer; CI and live acceptance remain open.

- Tie-order repair reported complete: shared section/date/event-ID order and SQL tie-break, real RSS same-date regression, four focused checks passing. Reviewer assigned only this final delta; deployment gate remains pending its verdict.

- Deployment gate: reviewer reproduced different visible/editor ID sets for six equal-date items with reversed detail input. Fixer must add a shared deterministic event-ID tie-break and a regression through actual RSS ingestion; timestamp fallback itself is accepted. Deployment waits for this narrow review.

- Fixer reports the final date delta repaired: RSS and YouTube briefing timestamps now use the same freshness reference as persisted events. Actual RSS ingestion (six entries, missing publication date and an unsectioned candidate) and YouTube missing-date regressions pass; 32 scoped tests reported passing. Independent review of this delta is pending; no live or CI acceptance is implied.

Latest review closed atomic result application and budget/failure separation. Remaining P1:
freshly appended RSS BriefingItem lacks the date used for its persisted event; editor and detail
sorting can still choose different five items. Fixer assigned the same freshness_reference_at date
and a regression through the actual freshly processed RSS path, not pre-dated synthetic items.

Fixer now reports shared section/date selection and DAILY_BRIEFING_ITEM_LIMIT across editor,
detail query and Telegram. Exact unique IDs and complete mutation preparation prevent partial
editing; editor budget skips are counted. 78 focused tests passed; this delta is under independent
review. Callback acceptance remains; CI metadata permission and live Telegram acceptance are pending.

Reviewer accepted the callback 20-character URL-safe round-trip, including '-'/'_', and existing
identity/expiry/one-use controls. Remaining editor blockers: indexing a <=5-ID result for every
news item can raise KeyError after partial mutation; editor and renderer candidate order/cap can
select different sets, leaving visible English items unedited. Returned these scoped blockers to
Fixer with real integration-branch offline regression requirements. Live acceptance remains pending.

Callback issuer/parser length mismatch is now reported fixed: 16-character tokens versus a
20-character reader. Fixer reports 88 focused tests passed. Reviewer must check random-token
alphabet handling, exact length, identity binding, expiry and single-use regression. No live
Telegram acceptance is claimed; CI still awaits metadata permission.

Latest fixer report: compact rendering/editor translation, long-sentence bounds, budget skips and
delay rounding are ready for independent review; 87 focused tests, Ruff, diff check passed. No
acceptance claimed yet. Callback remains unresolved; coordinator requested clarification of the
claimed scope exclusion. Actions metadata permission is pending; no remote logs were inspected.

- Confirmed: Telegram sends separate article cards; its test expects that behavior. A final editor
  helper exists but has no runtime call. English fallback paths exist; the user's screenshot shows
  technical `TITLE/SNIPPET` labels, whose entry point still needs precise classification.
- Feedback tokens are DB-backed, actor/chat-bound, one-use, and expire after 24 hours. Process-local
  storage is not the cause shown by local code. Multiple actors sharing a chat is a conditional
  mismatch path; real first-click failure remains unproven.
- Local verification: 23 selected offline tests and Ruff passed. No DB/VDS/provider/log inspection.
- GitHub Actions failure remains unclassified. The operator's PowerShell metadata command was
  attempted in Bash; that shell error is not evidence of the CI failure. Await safe run/job/step data.
- Timing label rounds positive delay upward and is calculated before actual Telegram delivery.

## Authorized repair

Reviewer returned `changes required`: English stored prose still passes through both summary
branches, and the current fixture hides that case. Long single-sentence text can lose its useful
description. Fixer was assigned these blockers; review accepted message bounds, safe links, and
numbered feedback mapping. The summary-file review hold is released for repair.

The user additionally authorized fixing the remaining reported issues: invalid first-14-day
feedback, CI failures, budget-exhaustion accounting/user warnings, and misleading delay labels.
Use the same Luna high fixer. Establish missing local evidence before repairing; remote Actions
metadata/log output still requires the user's specific permission. No production/provider calls,
commit/push, deployment, secret/config inspection, or unrelated category-onboarding changes.
Complete locally verifiable fixes and focused regression checks; report exact evidence/permission
needed for any blocked remainder rather than guessing or declaring it solved.

Fixer changed `app/telegram/service.py` and `tests/test_telegram.py`; four focused tests, Ruff,
diff check, and Graphify update were reported successful. Reviewer checks only this diff, especially
English stored-description handling, character bounds, safe links and numbered feedback mapping.
Coordinator task: `01a0d53c-870c-7303-b6f4-80a0c166a1ff` (local). User authorized workers to send
one final REPORT or blocking NEEDS_DECISION to that task; no routine progress/acknowledgment loops.

- Role: `docs/agent_roles/FIXER.md`; task `AI Assistant — Fixer`, GPT-6 Luna high.
- Outcome: one short Turkish daily-summary message instead of a header plus separate article cards;
  meaningful developments, compact section headings, safe source links, no raw field labels.
- Boundaries: local application/tests only; preserve unrelated documentation edits. No `.env`,
  secrets, server, live provider, remote CI logs, commit/push, deployment, or additional agents.
- Read only the affected flow. Existing findings are the starting point, not a new repo-wide review.
  If using the existing editor is necessary, do so during generation with existing budget/cache
  boundaries; `/ozet` must render stored content without a new provider call. No model-ID changes.
- First-14-day questions remain separate. If per-item feedback is retained, map each row explicitly
  to its numbered digest item rather than creating separate article messages or ambiguous buttons.
- Acceptance: bounded readable Turkish output, <=5 developments, no English/raw extraction metadata;
  <=3500 Telegram characters including safe links, focused regression tests and relevant lint.
- Do not guess-fix invalid Yes/No callbacks or Actions; those await specific evidence. Report any
  indispensable wider contract change before implementing it.

## Completed research assignment

- Role: `docs/agent_roles/REVIEWER.md`; one existing Luna xhigh agent, no parallel split.
- Outcome: evidence-led causes or explicit hypotheses for rendering, feedback validity, budget
  accounting, the timing label, and GitHub Actions failures; propose repairs without implementing them.
- Area: local Telegram/scheduled briefing flow, editor output, budget handling, and related tests.
- Boundaries: read-only, no tracked-file edits, provider calls, VDS inspection, commit/push, or
  category-onboarding work. Sensitive terminal commands/output require the user's specific approval.
- Acceptance: the common four-section report, with safe file/line evidence, missing tests, and the
  precise safe operator evidence needed if local code cannot settle a hypothesis.
- GitHub Actions: inspect local workflow definitions; remote run/job metadata or logs require the
  user's specific approval before any potentially sensitive command/output is accessed. Do not rerun CI.

Any later repair requires an authorized fixer assignment followed by independent review. M22.4
category-first source onboarding remains planned in `PROGRESS.md`, outside this investigation.
