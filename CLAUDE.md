# CLAUDE.md — banko-ai-assistant

This file orients any Claude Code session (or human contributor) picking up this repo cold.

## What this project is

Banko AI Assistant is a **production-ready agentic RAG demo** for a fictional bank. It demonstrates retrieval-augmented generation, multi-agent orchestration on LangGraph, durable workflow checkpointing on CockroachDB, multi-provider LLM support, and (in v1.1 of the Spending Coach work) streaming, observability, MCP exposure, and airgap deployment.

It is **not** "just a RAG demo." The repo was renamed from `banko-ai-assistant-rag-demo` in April 2026 because "RAG" undersells what it does — the agentic and multi-provider story is the headline.

**Primary audience for the demo**: AWS re:Invent, IBM TechXchange / Think, and enterprise customer POCs (regulated industries and airgap segments included).

## High-level architecture

```
Flask + SocketIO web app
  ├── Multi-agent layer (LangGraph 1.x, CockroachDBSaver checkpointing)
  │     ├── Receipt agent (OCR via tesseract + pdf2image)
  │     ├── Fraud agent
  │     ├── Budget agent
  │     ├── Coach agent (planned — see spec)
  │     └── Supervisor (planned — LLM-routed dispatch)
  ├── AI provider abstraction (banko_ai/ai_providers/)
  │     ├── watsonx.ai (DEFAULT, also default classifier model)
  │     ├── OpenAI
  │     ├── AWS Bedrock (internally identified as "aws", not "bedrock")
  │     ├── Google Gemini
  │     └── Ollama (planned — for airgap)
  ├── Vector RAG (langchain-cockroachdb 0.2.x, C-SPANN cosine indexes,
  │     384-dim all-MiniLM-L6-v2 embeddings — local, no API key)
  ├── Cache layer (3 tiers: query, embedding, vector_search, all in CRDB)
  ├── CDC config (banko_ai/pipeline/config.py — webhook + Kafka modes;
  │     consumers planned in Coach spec)
  └── CockroachDB (v25.4.0+, vector indexes are GA, row-level TTL for
        checkpoints and signal/nudge tables)
```

Full architecture diagram in `docs/superpowers/specs/2026-05-21-proactive-spending-coach-design.md` §3.1.

## Repo layout

| Path | Purpose |
|---|---|
| `banko_ai/agents/` | LangGraph specialist agents + workflows |
| `banko_ai/ai_providers/` | Provider abstraction; ALL LLM calls go through here, no direct SDK use anywhere else |
| `banko_ai/config/` | Env-driven settings (~15 knobs) |
| `banko_ai/vector_search/` | Semantic search, embedding enrichment, sample data generator |
| `banko_ai/utils/` | DatabaseManager, cache manager, migration runner, retry/pooling, chat history |
| `banko_ai/web/` | Flask app (~1800 LOC in `app.py`), agent dashboard, auth stub |
| `banko_ai/pipeline/` | CDC config (Kafka, webhook, COS) — consumer impls planned |
| `banko_ai/coach/` | **Planned** — Spending Coach (see spec) |
| `banko_ai/agents/supervisor.py` | **Planned** — LLM-routed multi-agent supervisor |
| `banko_ai/observability/` | **Planned** — OTel instrumentation |
| `tests/` | 16+ test suites; integration tests need a populated DB (skipped in CI when DB is absent) |
| `tests/eval/` | **Planned** — eval harness (LLM-as-judge on fixtures) |
| `scripts/` | Dev/ops helpers (build-docker, demo_standalone_search, watch-queries) |
| `scripts/coach/` | **Planned** — mock_signals.py + assert_nudges.py |
| `scripts/airgap/` | **Planned** — preload-models.sh |
| `docs/` | API.md, DOCKER.md, superpowers/specs/ |
| `PIPELINE_CONTRACT.md` | **Planned** (repo root) — contract for the sibling pipeline repo |

## Sibling repo (you will touch its outputs, not its code)

`~/idea_workspace/cockroachdb-watsonx-data-pipeline` (GitHub: `cockroachlabs-field/cockroachdb-watsonx-data-pipeline`) — the streaming/lakehouse side. It produces CDC events from CockroachDB into Apache Iceberg on IBM watsonx.data, with two paths: webhook (demo) and Debezium-Kafka (prod). It is developed in a **separate Claude Code session**. The contract between the two repos lives in `PIPELINE_CONTRACT.md` (planned) at this repo's root. The pipeline repo writes to a `spending_signals` table; this repo consumes it via webhook or Kafka.

Schema for `expenses` table is **shared** between both repos — keep them in sync if you ever change it here.

## Tech stack quick reference

- **Python**: 3.10+ (3.12 recommended)
- **CockroachDB**: 25.4.0+ (vector indexes are GA)
- **Embeddings**: `all-MiniLM-L6-v2` via sentence-transformers (384-dim, local)
- **Agent framework**: LangGraph 1.x
- **Vector store / chat history / checkpointer**: `langchain-cockroachdb` 0.2.x
- **Web**: Flask 3.1.3 + Flask-SocketIO + eventlet (prod) / threading (dev)
- **Dep manager**: `uv` (lockfile is `uv.lock`)
- **Testing**: pytest, ruff, mypy
- **Docker**: multi-arch (amd64/arm64), images on Docker Hub at `virag/banko-ai-assistant`

## Conventions and gotchas — do not relearn these the hard way

These come from prior development pain (mostly from droid sessions Feb-Apr 2026). Honoring them prevents reintroducing fixed bugs and avoids known footguns.

### LLM and AI

- **Default provider is watsonx**. Override via `AI_SERVICE=openai|aws|gemini|ollama` env var. The UI provider switcher must key on `AI_SERVICE`, not model name — there was a real bug where the watsonx logo kept showing even when OpenAI was active because display logic keyed on model.
- AWS Bedrock is identified internally as `"aws"`, NOT `"bedrock"` — docstring is inconsistent in places but the env value is `aws`.
- **All LLM calls go through `banko_ai/ai_providers/`** — never import `openai`, `anthropic`, `boto3.client('bedrock-runtime')`, etc. directly anywhere else. This is what makes airgap mode (Ollama) and provider switching work cleanly.
- Dynamic model discovery is the pattern for every provider — never hardcode model lists.
- LangGraph checkpoints auto-expire after 7 days via CRDB row-level TTL (`CHECKPOINT_TTL_DAYS`).

### CockroachDB and vector search

- Vector indexes are C-SPANN, cosine ops (`<=>` operator). **Do not use L2** — the codebase migrated away from it.
- No `CAST` in vector queries — the `<=>` operator on a `VECTOR(384)` column does the right thing directly.
- Pre-v25.4.0, the `feature.vector_index.enabled` cluster setting was required. GA now — no longer needed but harmless to set.
- User-specific vector index `idx_expenses_user_embedding` exists; all per-user vector queries should filter by `user_id` to use it.

### Receipt OCR

- Tesseract MUST be in PATH or receipt upload silently returns "Unknown" for all fields. This bit us — see `scripts/setup_system_deps.sh` for installer.

### Caching

- 3-layer cache: `query_cache` (semantic, 0.75 similarity threshold), `embedding_cache` (per-provider — provider is part of the unique key, this was a bug), `vector_search_cache`.
- Cache hits are reported via `/api/cache/stats`.
- TTL default 24h; configurable.

### Frontend

- Agent dashboard activity feed must reflect REAL agent activity. The user has been bitten by canned/hardcoded demo lights — never ship a dashboard with synthetic events.

### Documentation

- ONE end-to-end doc for any new feature, not a sprawl of `FEATURE_X.md` + `FEATURE_X_NOTES.md` + `FEATURE_X_FIXES.md`. The user has explicitly deleted droid-era doc piles. Keep `docs/` lean.
- README target: ~250 lines, with embedded architecture diagram. Currently 469 lines — slim in the Coach v1 (see spec §8.2).
- Demo marketing tone: Cisco / CockroachDB customer-story register. **Reject validation-speak** like "we prove it at scale with an industry-standard benchmark." The user has pushed back on that phrasing.

### Git workflow

- See `~/.claude/projects/.../memory/feedback_local_testing_before_push.md` — **NEVER commit or push until thoroughly tested locally against every relevant LLM provider.** This applies to bot PRs too (dependabot batches go through local rebase + smoke before push — see spec §8.1).
- **Do NOT add bot/agent co-author trailers** to commits or PR bodies (`Co-Authored-By: Claude ...`, "Generated with Claude Code", etc.). Commits should look like Virag wrote them. See `~/.claude/projects/.../memory/feedback_no_bot_commit_trailers.md`.
- Default branch is `main`. Branch sync confusion (`agentic_ai` vs `main`) has bitten before — confirm which branch you're on.

### Open bugs flagged but not yet fixed

- **Watsonx API surface drift**: `banko_ai/agents/llm_factory.py` uses `WatsonxLLM` (the deprecated `/ml/v1/text/generation` endpoint) with `decoding_method: "sample"` (also deprecated). Each request logs three `WatsonxAPIWarning`s. Migrate to `ChatWatsonx` and drop `decoding_method` before IBM removes the old endpoint.
- The watsonx model dropdown lists every chat-capable model IBM returns, including code-tuned ones (`ibm/granite-8b-code-instruct`) that echo prompt templates on JSON extraction tasks. The `ReceiptExtraction` Pydantic gate now catches the bad payloads (422 instead of 500), but the dropdown still presents the foot-gun. Consider annotating models with a "suitable for structured extraction" hint, or filtering code-tuned models out of the JSON-extraction code paths.
- `agent_memory.access_count` never incremented on read (defer to memory-system v2).
- `SentenceTransformer` re-instantiated per call in `base_agent.py` (perf bug; fixing risks regression — defer).
- `documents` table schema drift between `database.py` and `agent_schema.py` (both create it; reconcile when next touching either).
- `.gitignore:45` has unanchored `test_*.py` (intended for local utility scripts), which blocks new `tests/test_*.py` from being tracked — every new pytest module needs `git add -f`. Change to `/test_*.py` (root-anchored) or remove.
- `tests/test_env_config.py` is a print-script with module-level `sys.exit(0)`, not a pytest module — crashes collection. CI already ignores it. Rename to `scripts/check_env_config.py` or delete.

## Deployment modes (all three must keep working)

| Mode | LLM | Embeddings | DB | Use case |
|---|---|---|---|---|
| **Cloud** | watsonx / OpenAI / Bedrock / Gemini | local (sentence-transformers) | CRDB | SaaS, conferences |
| **Hybrid** | cloud LLM | local | on-prem CRDB + on-prem CDC pipeline | enterprise customers |
| **Airgap** | Ollama (granite3.3:8b default) | local | on-prem CRDB + on-prem CDC | gov, regulated industries; "disconnect wifi during the talk" demo |

See `memory/project_airgap_first_class.md` — airgap is not optional, it is a first-class deployment target. Any new code must work in all three modes.

## Running locally

```bash
docker compose up -d                            # CRDB + banko (cloud-ready)
# OR
docker compose -f docker-compose.airgap.yml up  # CRDB + banko + Ollama + Jaeger
```

Then visit http://localhost:5000. App generates 5000 sample expense records on first run.

## Testing locally (the required path before any push)

```bash
make test-local        # unit + integration + eval (mock judge) + lint + types
# Then:
docs/coach-smoke-checklist.md   # 14-item human-driven gate, ~5-10 min
# Then run smoke against EVERY provider (watsonx, OpenAI, AWS, Gemini, Ollama)
```

CI is **not enough**. CI gates on lint/types/unit/integration/eval (mock judge), but the multi-provider smoke is a human-driven, locally-run check.

## Active design docs

- `docs/superpowers/specs/2026-05-21-proactive-spending-coach-design.md` — current flagship enhancement (Coach + Supervisor + OTel + MCP + Eval + Ollama airgap + housekeeping). ~11 days of work. v1 in progress.

## Where the auto-memory lives

Per-project Claude memory is at `~/.claude/projects/-Users-viragtripathi-idea-workspace-banko-ai-assistant/memory/`. Read `MEMORY.md` there for the index of user preferences, project facts, and feedback rules. Update it as you learn new things.
