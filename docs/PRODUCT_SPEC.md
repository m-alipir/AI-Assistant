# Product Specification

## 1. Product goal
A self-hosted personal intelligence service that converts noisy daily inputs into a compact, sourced, connected briefing.

The product is not merely an RSS summarizer. It maintains a structured memory of meaningful events/facts and can connect a new development to prior relevant developments (for example: a semiconductor capacity change and its plausible implications for AMD/NVIDIA), while clearly separating source-backed claims from model inference.

## 2. Primary input streams
### Technology / industry
- Configurable RSS/Atom feeds from reputable technology publications.
- Official/company feeds or announcement pages when practical.
- Configurable YouTube channels/videos.

### World/general
- A separate set of broad reputable news sources.
- These items are not suppressed by the personalized-interest score.
- A small set of globally important events appears under `Dünyada Neler Oldu? / World in Brief`.

### Gmail
- Multiple accounts (initial target: 2+).
- Read-only OAuth.
- Surface action-required mail, job application updates, recruiter messages, security alerts, important personal/transactional items.
- De-emphasize known recommendations/newsletters/automated noise with deterministic rules before LLM classification.

## 3. Briefing output
Default order:
1. **Action Required** — important email/action items.
2. **Senin İçin / For You** — high-relevance items based on stable + adaptive interests.
3. **Tech & Industry** — important technology events that may not be explicitly personalized.
4. **Connections / Why It Matters** — only meaningful historical correlations with evidence.
5. **Dünyada Neler Oldu? / World in Brief** — 3–7 globally important items independent of interest profile.
6. **Worth Watching** — selected YouTube/video items where watching the original adds value.

Each important item should include:
- headline/title;
- compact summary;
- what changed/new information;
- why it matters (when justified);
- confidence/evidence quality signal;
- source links and publication time;
- optional historical connection(s), clearly marked as inference when applicable.

## 4. Freshness requirements
Freshness must be checked before expensive extraction/LLM work.

Store at least:
- `source_published_at`
- `source_updated_at` when available
- `discovered_at`
- `fetched_at`
- `freshness_status`

Rules:
- Normalize all source timestamps to UTC.
- Default news lookback: 48 hours (configurable globally/per source).
- Default YouTube lookback: 72 hours (configurable).
- First run must obey the same lookback; never process the entire historical RSS/channel backlog by accident.
- Stale items may be recorded as lightweight seen/fingerprint records but must not incur normal LLM processing unless explicit backfill is requested.
- If published time is missing, use `discovered_at` only as a fallback and mark timestamp confidence accordingly.
- Items implausibly future-dated (default >6h beyond fetch time) are quarantined/flagged, not briefed.
- An old article with a fresh `updated_at` is not automatically a new event. Reprocess only if content changed materially and the update itself is relevant.

## 5. Interest behavior
Interest affects ranking and placement, not existence of the global-news stream.

There are three layers:
- **Base interests**: manually configured, stable.
- **Explicit preferences**: user says more/less of a topic/entity; immediate effect.
- **Adaptive interests**: inferred from repeated interaction over roughly 1–2 weeks; slow, capped, and reversible.

A single click/question must never radically rewrite the profile.

## 6. Knowledge organization
The user must be able to browse/query hierarchical categories such as:
`Technology > Semiconductors > Manufacturing`

Entities are normalized separately, for example:
`AMD`, `TSMC`, `NVIDIA`, `Ryzen`, `RDNA`.

An AMD item can therefore be found by:
- category path;
- entity membership;
- topic/tag;
- date range;
- text/full-text query;
- semantic similarity.

Do not model the database as a single folder tree where each item can have only one location.

## 7. Non-goals for V1
- Autonomous email sending/replies.
- Autonomous job applications.
- Full web-browser agent crawling arbitrary sites.
- Running large local LLM inference on a low-cost CPU VPS.
- Qdrant unless pgvector becomes measurably inadequate.
- Full mobile app.
- Complex multi-agent orchestration framework.
