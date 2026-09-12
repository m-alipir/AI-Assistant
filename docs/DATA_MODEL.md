# Data Model

This is the logical model. Exact SQL types/indexes may evolve through migrations.

## Core ingestion
### `sources`
- id
- name
- kind: rss | youtube | gmail | web
- stream: personalized | tech | world | email
- source_tier / trust metadata
- enabled
- config JSON (non-secret only)
- default_freshness_hours

### `source_items`
- id
- source_id
- external_id / guid
- canonical_url
- title
- author/channel/sender
- source_published_at
- source_updated_at
- discovered_at
- fetched_at
- timestamp_confidence
- freshness_status
- raw_content_ref or raw_text (subject to retention policy)
- content_hash
- processing_status
- language

Unique/idempotency constraints should use source ID + external ID where possible and canonical URL/hash fallback.

## Taxonomy
### `categories`
- id
- slug
- name
- parent_id
- materialized_path (e.g. `technology.semiconductors.manufacturing`)

### `entities`
- id
- canonical_name
- entity_type: company | product | person | technology | organization | project | other
- description
- status

### `entity_aliases`
- entity_id
- alias
- normalized_alias

### `entity_categories`
Maps entities into one or more categories so a UI can expose paths like Technology -> Semiconductors -> AMD without forcing the item itself into a single folder.

### `topics`
Free-but-normalized topic tags (e.g. `advanced-packaging`, `rdna`, `vulkan`).

### Link tables
- `item_categories`
- `item_entities`
- `item_topics`
- `event_categories`
- `event_entities`
- `event_topics`

## Knowledge / evidence
### `events`
- id
- canonical_title
- compact_summary
- first_seen_at
- last_updated_at
- importance
- global_importance
- status: active | superseded | corrected | archived
- embedding

### `event_sources`
- event_id
- source_item_id
- relation: primary | corroborating | commentary | video_coverage

### `claims`
Source-backed extracted statements.
- id
- event_id/source_item_id
- statement
- claim_type: reported_fact | announcement | estimate | rumor | quote | measurement
- occurred_at / valid_from / valid_until
- confidence/evidence score
- source_span/timestamp locator where available
- embedding optional

### `inferences`
Model-generated interpretation, never mixed with claims.
- id
- event_id
- inference_text
- inference_type: implication | connection | contradiction | forecast
- supporting_event_ids / claim_ids
- model_role/model_id/prompt_version
- confidence
- created_at

### `event_relations`
- source_event_id
- target_event_id
- relation_type
- score
- explanation/inference_id

## Embeddings
Store embeddings on compact memory/event/claim text, not blindly on giant raw transcripts.
Embedding dimension must be migration/config compatible with the configured embedding model.

## Interest learning
### `interest_profile`
- subject_type: category | entity | topic
- subject_id/key
- base_weight
- explicit_delta
- adaptive_delta
- effective_weight
- updated_at

### `feedback_events`
- timestamp
- action: explicit_more | explicit_less | opened | expanded | asked_followup | saved | dismissed | more_like_this | less_like_this
- subject references
- weight
- source context

### `interest_candidates`
Nightly/periodic computed candidate adjustments before they are allowed to affect the stable adaptive profile.

## Email state
### `gmail_accounts`
- id
- account_label (no secrets)
- last_history_id
- last_sync_at
- enabled
- token_scheme (`fernet-v1` for current authenticated ciphertext; `legacy_xor` values require
  reauthorization and are never decrypted)

OAuth secrets/tokens must not be plaintext columns here.

### `email_classifications`
- source_item_id
- class: action_required | application_update | recruiter | security | transactional | recommendation | newsletter | personal | other
- urgency
- action_summary
- linked_application/entity if applicable

### `applications` (optional but included in V1 if email classification supports it cleanly)
- company_entity_id
- role
- applied_at
- status
- last_update_at
- source_item_ids

## Operational
- `job_runs`
- `llm_calls` (role, model, token usage, provider/estimated/unavailable cost status, cache hit,
  logical provider-attempt status)
- `briefings`
- `briefing_items`
- `processing_errors`
- `briefing_outbox`: compact, non-sensitive briefing candidates staged atomically with an event or
  actionable email classification. Rows are deleted only in the same transaction that persists a
  rendered briefing, so a restart or briefing-write error does not re-run LLM extraction or lose
  the item.
- `post_llm_failures`: content hash, source kind, safe category, and retry state only. Normal runs
  skip a blocked item; one atomically claimed, explicit retry may process it.
- `agent_api_audit_log`: time, endpoint category, outcome, and response byte count for the separate
  read-only Agent API only. It never stores agent identity/IP, token, question/filter, source text,
  response payload, provider metadata, or Gmail identity/body data.
- `telegram_updates`: Telegram `update_id`, hashes of the authorized actor/chat, update kind, safe
  outcome category, and timestamps only. No command, callback, reply, provider result, or raw
  Telegram payload is retained. The update ID is the durable replay barrier before a model call or
  feedback mutation.
- `telegram_feedback_tokens`: short-lived random actor-bound tokens that map one rendered briefing
  item to an allowed feedback action. Tokens expire after 24h and are deleted on use.
- `notification_deliveries`: delivery idempotency is scoped by `channel` plus logical key, so a
  Telegram destination and ntfy do not suppress each other.

## Retention defaults
Configurable defaults:
- public raw article/transcript: 30 days
- distilled events/claims/inferences: persistent
- email raw body: 7 days or less; compact classification/action summary retained as needed
- LLM raw prompts/responses: do not retain sensitive full payloads by default; store metadata + validated structured result where useful
