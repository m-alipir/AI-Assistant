# Model Routing and Cost Policy

## Principle
Use role-based model configuration. Business logic requests a role, never a hardcoded model slug.

Roles:
- `gatekeeper`
- `extractor`
- `reasoner`
- `editor`
- `embedding`

## Tier 0 — no LLM
Use deterministic code for:
- fetching
- time/freshness checks
- exact/canonical dedup
- known sender rules
- URL normalization
- content hashing
- database filtering
- alias lookup
- scheduling/retention

## Gatekeeper
Input: title + description/snippet + metadata + small content sample only if needed.
Output via strict JSON Schema:
- relevant
- global_importance
- personal_relevance estimate
- candidate category path(s)
- candidate entities/topics
- importance
- needs_full_extraction

Requirements:
- cheap
- low latency
- structured outputs

## Extractor
Input: relevant content or chunks.
Output via strict schema:
- compact summary
- what changed
- claims/facts with source locators
- numbers/dates
- entities/topics/categories
- uncertainty/rumor markers

Prefer cheap/medium model. Long transcripts use map/merge extraction.

## Reasoner
Only for selective correlation/contradiction/implication tasks.
Receives compact new event + top historical memories, never the whole database.
Use stronger reasoning model.

## Editor
Usually one strong call per daily briefing. Input is already distilled structured data.
The editor may prioritize and phrase; it must not invent unsupported facts.

## Embedding
Use a dedicated embedding model via OpenRouter or another configured provider. Store the model ID and dimensionality with embedding metadata. Model changes requiring dimension changes need a migration/re-embedding plan. Leave existing vectors readable but exclude incompatible rows from semantic comparison, generate replacement vectors through the configured `embedding` role, verify coverage, then retire old vectors in a separately approved operation.

## OpenRouter integration requirements
- Use OpenRouter model API/catalog to inspect current capabilities/pricing when requested.
- Do not auto-change production models based only on catalog price.
- Model role mappings live in config.
- Each role can define ordered fallbacks.
- Machine-consumed responses use `response_format.type=json_schema`, strict schema where supported.
- Prefer providers/models that honor required parameters; configure provider routing appropriately.
- Record token usage and estimated cost per call.
- Use prompt/provider caching only where it materially reduces repeated large stable prefixes.

## Application-level result cache
Key at minimum:
`content_hash + task_type + prompt_version + model_id + schema_version`

If key matches and prior validated result exists, skip the API call.

Prompt versions must change when a prompt's structure or deterministic truncation policy changes.
Each role also has a configuration-driven maximum input-character ceiling. Gatekeeper metadata,
extractor source text, Search/Ask candidates, and editor context are clipped before the provider
boundary; no retained inbox/body or full historical memory is used as a fallback.

## Budget policy
Configurable daily soft/hard budgets by role and total.
- soft limit: log/warn and reduce optional correlation work
- hard limit: skip optional LLM work, never silently exceed; still run deterministic ingestion and surface degraded-state health
- email `Action Required` classification may have a small reserved budget so a busy news day cannot consume all capacity
- `daily_max_provider_calls` is a second durable daily circuit breaker. It protects deployments
  whose provider or configured price is unavailable; unknown cost is not treated as evidence of
  zero cost.
- Within the documented single-process runtime, a shared non-queuing provider-work slot prevents
  an uncached manual, scheduler, retry, or Ask request from overlapping into duplicate paid work.
  A busy request returns a safe retryable status rather than waiting in a hidden queue.

## Model catalog helper
Provide a CLI/admin action that can query the OpenRouter model catalog and show candidates per role filtered by capabilities (e.g. structured outputs) and price. It is advisory only; changing active models is explicit configuration.
