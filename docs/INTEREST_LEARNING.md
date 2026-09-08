# Interest Learning

## Goal
Personalization should improve over weeks without creating a twitchy filter bubble.

Interest weighting influences ranking and briefing section placement. It must never suppress the independent `World in Brief` stream.

## Three-layer profile
### 1. Base
Manually seeded stable interests. Examples can include AI, GPU, CPU, game development, graphics programming, software/automation.

### 2. Explicit
Direct user instructions:
- “Give me more NVIDIA news.”
- “Less crypto.”
- “Never show celebrity news unless globally important.”

These are high-confidence and take effect immediately. Store the explicit preference as a durable event so it can be reversed later.

### 3. Adaptive
Learned from repeated behavior. Candidate signals:
- asked a follow-up about an event/entity
- used “more like this”
- opened/expanded/saved repeatedly
- manually promoted an item
- repeated topic questions inside this product
- “less like this” / dismissed repeatedly

Do not treat mere non-click/ignore as a strong negative signal.

## Stability algorithm (initial policy)
- Record every signal as a `feedback_event`.
- Recompute candidate adaptive scores nightly over a rolling 14-day window.
- Use time decay (target half-life ~7 days).
- A topic/entity should not materially affect adaptive ranking until there are repeated signals, e.g. >=4 positive weighted signals across >=3 distinct days, unless an explicit preference exists.
- Apply adaptive changes gradually, no more than a configurable delta per 7-day period (suggested initial cap: +/-0.25).
- If no reinforcing signals occur for ~21 days, adaptive deltas drift back toward neutral.
- Explicit preferences are separate from adaptive decay.
- Keep a history of profile changes for explainability and rollback.

Exact coefficients are config, not magic constants scattered through code.

## Free-form feedback
If the user gives natural-language preference feedback, use a cheap structured classifier only to map the statement to normalized entities/topics/categories and intent (`more`, `less`, `mute`, `reset`). The preference math/update itself is deterministic.

## Effective ranking
Conceptually:
`effective_interest = clamp(base + explicit_delta + adaptive_delta)`

Final item rank should also consider:
- event importance
- global importance
- freshness
- source/evidence quality
- novelty
- redundancy penalty

Personal interest must not be the sole ranking variable.

## Transparency
Admin UI/API should expose:
- current base/explicit/adaptive/effective weights
- why an adaptive weight changed (aggregated signal counts)
- last update date
- reset/override controls
