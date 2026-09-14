# Optimization Baseline and Acceptance Gates

## Purpose

This document defines the measurement gate for incremental performance work. It preserves the
current FastAPI, PostgreSQL/pgvector, event/claim/inference, freshness, provenance, budget, and
single-process runtime boundaries. It does not authorize a platform replacement, Redis, Qdrant,
or a multi-worker deployment.

The baseline uses only sanitized fixtures and a disposable PostgreSQL database. It must not fetch
live sources, call a provider, read Gmail, or retain query/source bodies in metrics.

## Baseline scenarios

| Scenario | Dataset and operation | Required measurements |
| --- | --- | --- |
| RSS no-change run | Existing feed fixtures run twice | fetched, stale, duplicate, accepted, article fetches, provider calls, cache hits |
| Source failure | Existing timeout/429/5xx fixtures | cooldown decision, retry count, and safe error category |
| Knowledge search | Seeded public events with metadata, claims, and compatible vectors | SQL candidate count, search p50/p95, result IDs, Recall@5/10, and NDCG@10 |
| Event clustering | Same-event and similarly named-but-distinct fixture pairs | corroboration precision and false-merge count |
| LLM result reuse | Repeated validated structured request fixture | cache-hit ratio, provider-call count, tokens, and estimated cost |

Each timing measurement records only an operation name, duration, count, safe outcome category,
and cache flag. It never records a source URL query string, prompt, source body, email data, or
credential.

## Acceptance gates

An optimization is accepted only when all applicable gates pass against the same fixture corpus:

1. Correctness: no freshness, deduplication, provenance, fact-versus-inference, authorization, or
   budget regression; the full offline test suite remains green.
2. Retrieval: Recall@10 and NDCG@10 do not decrease. Result ordering changes require a reviewed
   golden-result update, not a tolerance-based silent change.
3. Performance: the measured p95 of the targeted operation improves by at least 15 percent, or
   the change removes a verified provider/network request. A change with no measurable benefit is
   removed.
4. Cost: provider calls and estimated cost do not increase for an equivalent fixture run unless a
   separate quality gain is documented and approved.
5. Operations: `EXPLAIN (ANALYZE, BUFFERS)` is captured on the disposable database before adding
   an index. An index is retained only when its plan is selected and it improves the target query.
6. Rollback: every migration/index/cache policy has a reversible path and does not delete raw
   provenance or compatible existing vectors.

Absolute millisecond limits are intentionally not set before the first local/VPS baselines; host
hardware, PostgreSQL version, and corpus size materially affect them. Comparisons use the same
host, database configuration, fixture corpus, and repeated-run count.

## First disposable-database observation

On 2026-09-12, a PostgreSQL 17/pgvector disposable database at migration `20260912_0022` ran the
current 180-day, newest-first event candidate query inside a rolled-back transaction containing
5,000 synthetic events. `EXPLAIN (ANALYZE, BUFFERS)` reported 1.845 ms execution time for the
100-row query. The planner selected a sequential scan because the time window covered most rows;
this is expected at that small corpus size. No HNSW, IVFFlat, partition, or new index is justified
by this observation. The synthetic rows were rolled back and no source, email, provider, or user
content was used.

The same database confirmed that `20260908_0014` already supplies
`ix_llm_calls_created_at`. A rolled-back 100,000-row synthetic ledger query used that index for
the daily-budget predicate and completed in 0.997 ms. No duplicate ledger index was added.

## Delivery sequence

1. Capture the baseline and commit the sanitized measurements/plan shape, never production data.
2. Add conditional RSS fetch state and bounded concurrent metadata collection only if it eliminates
   verified repeat work while preserving deterministic processing order.
3. Move hybrid retrieval candidate selection into PostgreSQL: structured filters first, then
   full-text and compatible-vector candidates, followed by the existing deterministic rerank.
4. Keep exact pgvector search while the corpus is small. Evaluate an HNSW index only after the
   baseline demonstrates a search bottleneck and verify filtered recall before enabling it.
5. Add cache retention and re-embedding maintenance only after their cardinality and operational
   cost are measured.

## Reporting format

Every optimization work log records: baseline and candidate revision, fixture corpus revision,
run count, p50/p95, candidate counts, Recall@K/NDCG, provider calls/cost, selected query plan,
and the rollback location. Report aggregates only.
