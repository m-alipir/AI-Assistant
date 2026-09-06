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
- `llm_calls` (role, model, prompt version, token usage, estimated cost, cache hit, status)
- `briefings`
- `briefing_items`
- `processing_errors`

## Retention defaults
Configurable defaults:
- public raw article/transcript: 30 days
- distilled events/claims/inferences: persistent
- email raw body: 7 days or less; compact classification/action summary retained as needed
- LLM raw prompts/responses: do not retain sensitive full payloads by default; store metadata + validated structured result where useful
