# Pipelines

## A. RSS/news pipeline
1. Fetch feed.
2. Normalize URL/GUID/title/timestamps.
3. Apply freshness gate before article fetch/LLM.
4. Exact/native-ID/canonical-URL/content-fingerprint dedup.
5. Apply deterministic source/topic rules.
6. Cheap gatekeeper classification using only compact metadata/snippet.
7. If relevant or globally important, fetch/extract article body when needed.
8. Structured fact/event extraction with cheap/medium model.
9. Normalize categories/entities/topics; known aliases first, LLM only for ambiguity/new candidates.
10. Event clustering/dedup with existing recent events.
11. Embed compact event/claim representation.
12. Retrieve historical candidates.
13. Escalate to strong correlation reasoner only when policy threshold is met.

### Freshness gate defaults
- `news.max_age_hours = 48`
- `world.max_age_hours = 36-48`
- per-source override allowed
- future tolerance default `6h`

Out-of-window items should not consume LLM tokens in normal daily mode.

## B. YouTube pipeline
1. Discover recent channel videos cheaply (RSS/channel metadata strategy).
2. Freshness gate (`youtube.max_age_hours`, default 72h).
3. Dedup by video ID.
4. Use yt-dlp wrapper to inspect metadata/subtitle tracks.
5. When a source configures `language: tr` or `language: en`, request only that language family
   (including common regional variants), then prefer human subtitles over automatic subtitles.
   If no matching subtitle exists, record `skipped_no_preferred_language_caption` and do not call
   an LLM. Sources without a language selection retain the legacy manual-then-automatic behavior.
6. Do not download video/audio when subtitles are available.
7. Optional later fallback: download audio + STT only if configured and item importance justifies cost.
8. Preserve timestamped segments where possible.
9. For long transcripts, segment by timestamps/chapters and run cheap structured extraction per chunk, then merge. Do not repeatedly send the full transcript to strong models.
10. Store raw transcript per retention policy; store compact persistent event/claims.

If extraction validation or event persistence fails after an LLM attempt, retain only the video
content hash and safe failure category. This blocks automatic/manual repeat processing until the
operational failure is reviewed, avoiding another LLM charge; no transcript, caption text, or
provider response is stored.

An operator may explicitly claim one blocked YouTube item from Admin. The database claim changes
only that item to `retrying`; concurrent clicks cannot run another attempt. Success creates the
event and Worth Watching briefing then clears the block. Any retry failure returns it to `blocked`
with a safe category, while normal/scheduled ingestion continues to skip it.

## C. Gmail pipeline
V1 prefers incremental polling rather than Pub/Sub to minimize infrastructure.

1. OAuth read-only per account.
2. Initial sync: bounded lookback only (default 48h).
3. Save Gmail `historyId` checkpoint.
4. Scheduled sync uses `history.list` from last checkpoint when possible.
5. Fetch only new/changed INBOX messages required for classification.
6. Deterministic rules first:
   - known recommendation/newsletter senders
   - automated notification patterns
   - known high-priority senders/patterns
7. Cheap LLM only for unknown/ambiguous messages.
8. Extract action item/deadline/application status only for relevant mail.
9. Email content does not enter general long-term knowledge memory by default.
10. Persist new history checkpoint only after successful processing.

If history synchronization becomes invalid/expired, perform a bounded recovery sync rather than scanning the entire mailbox.

## D. Event dedup / clustering
Escalation order:
1. same source external ID
2. canonical URL
3. content hash/fingerprint
4. normalized-title similarity
5. entity + time + key-fact overlap
6. embedding similarity
7. cheap LLM adjudication only if still ambiguous and merging matters

Never discard separate source provenance when clustering.

## E. Correlation pipeline
Trigger only when at least one is true:
- event importance >= configured threshold;
- global importance high;
- tracked entity/topic involved;
- retrieval finds high-scoring historical candidates;
- contradiction/update candidate detected.

Retrieval:
1. filter by entity/category/topic + sensible time window;
2. lexical/full-text candidates;
3. vector similarity;
4. combined rerank;
5. top 5–10 compact memories only to reasoner.

Reasoner output must be structured:
- relation type
- linked event IDs
- explanation
- evidence IDs
- whether it is fact-supported or inference
- confidence

## F. Daily briefing pipeline
1. Gather current-day processed events and relevant emails.
2. Score into separate queues:
   - Action Required
   - For You
   - Tech & Industry
   - World in Brief (interest-independent)
   - Worth Watching
3. Collapse duplicates/events.
4. Include only high-value correlations.
5. Send compact structured briefing context—not raw articles/transcripts—to final editor.
6. Atomically stage each safe candidate in a durable briefing outbox as its event/action metadata
   is persisted; this is not a second LLM/editor call.
7. Validate final structure and atomically drain a bounded outbox batch into one briefing and its
   item mapping. On render/persistence failure, leave the outbox untouched for the next run.
8. Deliver via configured adapters.

## G. Failure behavior
- One bad feed must not abort the entire daily run.
- One failed LLM provider/model should use configured fallback, within budget.
- Invalid structured output: retry bounded times, optionally use OpenRouter response-healing if configured; otherwise mark item failed for later retry.
- All retries must be bounded and observable.
- A post-extraction or event-persistence failure is a hash-only automatic block. It cannot trigger
  another ordinary manual/scheduled provider call. An operator may atomically claim one explicit
  retry; provider-busy and budget-exhausted skips remain retryable and are never converted into a
  permanent post-LLM block.
