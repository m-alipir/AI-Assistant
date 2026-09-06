# Architecture

## 1. High-level flow

```text
RSS / YouTube / Gmail
        |
        v
Collectors -> Normalizer -> Freshness Gate -> Deterministic Dedup/Rules
                                                  |
                                                  v
                                           Cheap Gatekeeper LLM
                                                  |
                                      irrelevant -+-> discard/minimal seen record
                                                  |
                                                  v
                                           Content Extraction
                                                  |
                                                  v
                                        Structured Fact Extractor
                                                  |
                                                  v
                           Postgres/Supabase Knowledge + pgvector
                                      |           |
                                      +-----+-----+
                                            v
                                     Candidate Retrieval
                             SQL/entity/time -> lexical/vector rerank
                                            |
                                  correlation warranted?
                                     no          yes
                                      |            v
                                      |       Strong Reasoner
                                      +------------+
                                            |
                                            v
                                       Event Memory
                                            |
                                            v
                                      Daily Editor LLM
                                            |
                                            v
                                  Briefing + Delivery/UI
```

## 2. Runtime model
Codex is the builder, not the runtime. The finished application runs independently in Docker on a local PC or VPS.

Recommended components:
- Python 3.12+
- FastAPI for admin/API/health/manual triggers
- PostgreSQL (Supabase production target)
- pgvector extension for embeddings
- SQLAlchemy + Alembic
- httpx for external HTTP
- feedparser (or equivalent mature parser) for RSS/Atom
- yt-dlp wrapper for public YouTube metadata/subtitles/auto-subtitles
- Gmail API client + OAuth
- OpenRouter direct API client
- scheduler abstraction (current stable APScheduler or equivalent small library)
- pytest

Avoid orchestration frameworks unless evidence shows the simple service architecture is insufficient.

## 3. Service modules
Suggested layout (Codex may adjust naming without changing responsibilities):

```text
app/
  api/
  config/
  collectors/
    rss.py
    youtube.py
    gmail.py
  normalize/
  freshness/
  dedup/
  llm/
    client.py
    router.py
    schemas.py
    cache.py
  knowledge/
    taxonomy.py
    entities.py
    events.py
    retrieval.py
    correlation.py
  interests/
  briefing/
  delivery/
  db/
  jobs/
  observability/
tests/
migrations/
```

## 4. Deployment
### Local development
Docker Compose with application + PostgreSQL/pgvector is preferred so tests/development do not depend on a production Supabase instance.

### Production
- Application container on low-cost VPS.
- Supabase/Postgres may be remote, or a local Postgres/pgvector can be used if chosen later.
- No local frontier model inference required; LLM/embeddings are API calls.
- Container restart policy and healthcheck required.

## 5. Idempotency
Every source item should have a stable identity strategy:
- source-native GUID/video ID/message ID where available;
- canonical URL;
- normalized content hash as fallback.

Scheduled runs must be safe to execute repeatedly.

## 6. Retrieval strategy
Do not query the whole vector store first.
1. Narrow using structured filters: entity/category/topic/time/status.
2. Use Postgres full-text/lexical matching where useful.
3. Use pgvector similarity on the narrowed candidate set or indexed corpus.
4. Rerank using freshness, entity overlap, source/evidence quality, and semantic score.
5. Send only top candidates to a reasoner.

This hybrid retrieval pattern reduces irrelevant context and LLM tokens.

## 7. Event-centric storage
Multiple documents can report the same real-world event. Keep source documents separate but cluster them into an `event` so the briefing does not repeat the same story three times.

A single event may contain:
- primary source(s)
- secondary coverage
- video coverage
- extracted claims/facts
- inferred implications
- related historical events
