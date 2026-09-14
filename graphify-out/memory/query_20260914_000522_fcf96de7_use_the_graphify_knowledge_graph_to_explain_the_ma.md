---
type: "query"
date: "2026-09-14T00:05:22.555130+00:00"
question: "Use the Graphify knowledge graph to explain the main architecture of this project. Do not inspect the whole codebase manually unless the graph is insufficient."
contributor: "graphify"
outcome: "useful"
source_nodes: ["create_app()", "DeterministicIngestionPipeline", "KnowledgeSearchService", "OpenRouterClient", "DailyScheduler", "TelegramWebhookHandler"]
---

# Q: Use the Graphify knowledge graph to explain the main architecture of this project. Do not inspect the whole codebase manually unless the graph is insufficient.

## Answer

Expanded from graph vocab: [api, ingestion, rss, gmail, briefing, knowledge, llm, database, postgres, telegram, worker, scheduler]. The graph shows FastAPI composition in app/main.py; RSS, YouTube, and Gmail runtime jobs feed deterministic ingestion and freshness/deduplication, then persistence/correlation/embedding-backed knowledge search. A shared OpenRouter LLM layer provides routing, extraction, embeddings, budgets, caching, and provider coordination. Briefing assembly renders persisted items; Telegram and API routes expose delivery and interaction, with a daily scheduler coordinating runs.

## Outcome

- Signal: useful

## Source Nodes

- create_app()
- DeterministicIngestionPipeline
- KnowledgeSearchService
- OpenRouterClient
- DailyScheduler
- TelegramWebhookHandler