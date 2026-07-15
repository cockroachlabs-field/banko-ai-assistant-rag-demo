# Proactive Spending Coach — Design Spec

| | |
|---|---|
| **Status** | Draft (awaiting user review) |
| **Date** | 2026-05-21 |
| **Author** | Virag Tripathi (with Claude Code) |
| **Replaces** | n/a — net-new flagship feature |
| **Related** | `PIPELINE_CONTRACT.md` (repo root, to be written), `cockroachdb-watsonx-data-pipeline` (sibling repo, producer-side work) |

## 1. Summary

Banko AI Assistant grows a new **event-driven specialist agent** ("Coach") that reacts to streaming spending signals produced by the sibling `cockroachdb-watsonx-data-pipeline`. The Coach delivers proactive, contextual nudges to users ("you're at 82% of dining budget with 9 days left") and supports conversational follow-up using a planner-executor pattern. Five additional capabilities ride along to make v1 a coherent "best-in-class" deliverable: a multi-agent LangGraph **Supervisor** that routes between Coach and the existing specialists; an **MCP server** exposing Coach tools to any MCP-compatible client; an **OpenTelemetry** instrumentation layer with a local Jaeger trace UI; a lightweight **eval harness** for nudge quality (LLM-as-judge, ≥0.85 pass-rate gate); and full **airgap support** via Ollama (Granite default) for offline / regulated deployments.

The feature also drives a one-time **pre-flight cleanup**: drain 12 open dependabot PRs (closing 16 security alerts including 4 highs), slim the 469-line README to ~250 lines with embedded architecture, and produce a canonical pipeline-side contract document.

## 2. Goals & non-goals

### Goals (v1)

- Real-time, event-driven AI nudges driven by a streaming source of truth (not polling, not canned data).
- One coherent demo story spanning **streaming + agentic + MCP + observability + airgap** — five current AI-buzz themes in service of one user story.
- Clean separation between the *producer* (pipeline repo) and *consumer* (this repo) via a written contract, so both repos can ship in parallel via independent Claude Code sessions.
- Every code path works in all three deployment modes: cloud, hybrid, airgap.
- The Coach's brain is a true product surface — same backend serves the Flask UI, an MCP client (Claude Desktop, Cursor), and the eval harness.
- Eval coverage closes the largest current credibility gap: zero agent-quality measurement today.

### Non-goals (explicit deferrals to v2 or later)

- Voice (realtime API) — own flagship, own spec.
- Tiered episodic/semantic/procedural memory — own spec.
- Runtime hallucination guardrails (LLM-judge gating at request time) — eval catches these offline; runtime gating is a separate latency/cost design.
- True multi-tenancy via vector namespace isolation — was always optional in the original langchain-cockroachdb spec; stays optional.
- Mobile / Slack / Teams frontends — MCP enables these; building them in v1 dilutes focus.
- External retry-worker process for failed signals — in-process queue suffices for the demo; flagged in pipeline contract as a known prod gap.
- Additional signal types beyond the three chosen (velocity, goal proximity) — easy to add later as fixture + pipeline-side compute.
- HTTP/SSE MCP transports — stdio only in v1.
- A bundled-in-image Ollama model — image stays slim, model pulled on first run by a preload script.

## 3. Architecture

### 3.1 End-to-end view

```
┌────────────────────── PIPELINE REPO (other Claude session) ─────────────────────┐
│                                                                                  │
│   CRDB transactions ─► streaming aggregator ─► spending_signals table (CRDB)     │
│                                                       │                          │
│   ┌───────────────────────────────┬───────────────────┴──────────────────────┐  │
│   │ DEMO path                     │ PROD path                                │  │
│   │ CRDB CHANGEFEED               │ CRDB ─► Debezium ─► Kafka topic          │  │
│   │   format=json                 │   debezium-connector-cockroachdb 3.5.0   │  │
│   │   webhook sink                │   topic: banko.spending_signals          │  │
│   └────────────┬──────────────────┴────────────────────────┬─────────────────┘  │
└────────────────┼──────────────────────────────────────────┬┴────────────────────┘
                 │ HTTP POST                                ▼ consume
┌────────────────┼────────────────────────────────────────────────────────────────┐
│    BANKO REPO  ▼                                                                │
│   /api/cdc/signals webhook receiver         SignalsKafkaConsumer (optional)     │
│              │                                            │                     │
│              └──────────────┬─────────────────────────────┘                     │
│                             ▼                                                   │
│                  SignalHandler (transport-agnostic)                             │
│                             │                                                   │
│                             ▼                                                   │
│              ┌─────────────────────────────────────────┐                        │
│              │ Supervisor (LangGraph, LLM-routed)      │                        │
│              │  Receipt | Fraud | Budget | Coach (new) │                        │
│              └────────────────────┬────────────────────┘                        │
│                                   ▼                                             │
│                     CoachAgent (planner-executor)                               │
│                  ┌────────────────┴────────────────┐                            │
│              tools:                            memory:                          │
│              get_user_budget                   agent_memory                     │
│              get_recent_signals                coach_nudges (new table)         │
│              get_recent_txns                   CockroachDBSaver                 │
│              set_budget, explain_nudge                                          │
│                                   │                                             │
│             ┌─────────────────────┼─────────────────────┐                       │
│             ▼                     ▼                     ▼                       │
│       MCP server (stdio)   Flask UI (Live Coach)   Eval harness                 │
│                                                    pytest + LLM judge           │
│                                                                                 │
│   All spans → OTel SDK → OTel Collector → Jaeger (Grafana UI optional)          │
│                                                                                 │
│   LLM provider (one of):                                                        │
│     watsonx.ai | OpenAI | AWS Bedrock | Gemini | Ollama (airgap)                │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Key design principles

1. **Transport-agnostic SignalHandler.** Webhook adapter and Kafka consumer normalize incoming events into the same `Signal` dataclass; the Coach can't tell them apart. Switching modes is `CDC_MODE=webhook|kafka`, no code change.
2. **Supervisor is additive, not a rewrite.** Existing single-agent flows (receipt upload, fraud-on-transaction) keep their direct entry points. The Supervisor is the entry only for the *conversational* surface and for net-new flows. Zero blast radius on existing tests.
3. **Provider abstraction is the only point of LLM variation.** No direct OpenAI/Anthropic/watsonx client calls anywhere outside `banko_ai/ai_providers/`. This is what makes airgap mode a one-implementation drop-in.
4. **MCP wraps the same tools the agent uses internally.** Behavior cannot drift between channels because there is exactly one tools module.
5. **Correlation ID (`signal_id` or `thread_id`) flows through every component** — logs, DB rows, spans, external calls. One ID reconstructs the entire causal chain.
6. **Eval is part of the loop, not an afterthought.** PRs that regress nudge quality fail CI.

### 3.3 Contract boundary

Everything *upstream* of the `spending_signals` table is the pipeline repo's responsibility. Everything *downstream* (webhook receiver, Kafka consumer, Coach, Supervisor, MCP, UI, eval, OTel) is this repo's. The two sides connect via:
- The `spending_signals` table DDL (defined here; pipeline writes to it)
- The webhook payload format (CRDB changefeed envelope)
- The Kafka topic schema (`banko.spending_signals`)

All three connection points are defined in `PIPELINE_CONTRACT.md` at the repo root.

## 4. Components

| # | Component | Path (new unless noted) | Est LOC |
|---|---|---|---|
| 1 | `Signal` dataclass + types | `banko_ai/coach/signals.py` | ~80 |
| 2 | `SignalHandler` (transport-agnostic) | `banko_ai/coach/handler.py` | ~120 |
| 3 | Webhook receiver endpoint | `banko_ai/web/app.py` (+30 LOC) | ~50 |
| 4 | Kafka consumer (flag-gated) | `banko_ai/coach/kafka_consumer.py` | ~150 |
| 5 | `CoachAgent` (planner-executor) | `banko_ai/coach/agent.py` | ~250 |
| 6 | Coach tools | `banko_ai/coach/tools.py` | ~200 |
| 7 | MCP server | `banko_ai/coach/mcp_server.py` | ~150 |
| 8 | UI: Live Coach tab | `banko_ai/web/templates/coach.html` + routes + SocketIO | ~250 |
| 9 | Eval harness | `tests/eval/` | ~300 |
| 10 | Mock signal generator | `scripts/coach/mock_signals.py` | ~100 |
| 11 | DB migrations | `banko_ai/utils/migration.py` (+) | ~80 |
| 12 | `PIPELINE_CONTRACT.md` | repo root | (doc) |
| 13 | **Agent Supervisor** | `banko_ai/agents/supervisor.py` | ~300 |
| 14 | **OTel instrumentation** | `banko_ai/observability/tracing.py` + compose services | ~150 |
| 15 | **OllamaProvider** | `banko_ai/ai_providers/ollama_provider.py` | ~150 |
| 16 | Ollama service in compose | `docker-compose.yml`, `docker-compose.airgap.yml` | (config) |
| 17 | Model preload script | `scripts/airgap/preload-models.sh` | ~40 |

**Total**: ~17 components, ~2300 LOC of code + ~400 LOC docs + DB migrations. **Estimated effort: ~11 days** (see §10 for the breakdown).

### 4.1 Notes on the nuanced components

**CoachAgent (#5) — planner-executor.** Two modes share one LangGraph:
- *Reactive*: entry node receives a `Signal`; planner produces a 1-3 step plan ("gather context for this signal, draft nudge, persist"); executor runs steps (parallel where possible); final node persists to `coach_nudges` and emits a SocketIO event. Usually one LLM call, occasionally two.
- *Conversational*: entry receives a user message + thread history (via existing `CockroachDBChatMessageHistory`); planner decomposes into tool calls; executor iterates (hard cap: 5 steps); reply is streamed back via SSE. Reuses `CockroachDBSaver` checkpointer so a long conversation survives a restart.

**Supervisor (#13) — LLM-routed dispatcher with backwards-compatible bypass.**
- LangGraph `StateGraph` with a Supervisor node + edges to Receipt, Fraud, Budget, Coach.
- Classifier LLM (uses cheapest available model — Haiku 4.5 on Bedrock, `granite-3-2b-instruct` on watsonx, Gemini Flash, or `granite3.3:2b` on Ollama) maps incoming work to one of `{receipt, fraud_check, budget_query, coach_conversation, multi}`. `multi` dispatches to ≥2 specialists in parallel and merges results.
- **Bypass paths**: existing endpoints (`/api/receipt/upload`, fraud-on-insert hooks) keep their direct call into the relevant specialist. The Supervisor entry is only used by `/api/chat`, `/api/coach/chat`, the conversational MCP tool, and any new multi-specialist flows.
- Fallback: if classifier LLM fails, drop to a static keyword router covering the top ~80% of intents. Surface the degradation in `/health/coach`.

**MCP server (#7)** — stdio transport for v1 (Claude Desktop / Cursor compatible). Exposes 6 tools: `get_user_budget`, `get_recent_signals`, `get_recent_transactions`, `set_budget`, `explain_nudge`, `simulate_signal`. Thin wrapper around the same `tools.py` module the agent uses internally; the MCP layer is responsible for converting Python dataclass / dict returns into MCP-compliant JSON-serializable responses. The acceptance gate (§9 item 4) checks that the JSON returned to an MCP client deserializes to a structure equal to what the agent receives internally.

**Eval harness (#9)** — `tests/eval/cases.yaml` holds ~25 fixtures: `{signal, user_context, expected_traits: [mentions_budget_remaining, no_hallucinated_merchant, tone:supportive, length<200chars, ...]}`. pytest loads each, runs the CoachAgent with mocked DB calls (Coach still issues real LLM calls for planner + synthesizer), sends the output to a judge LLM (cloud: Claude Sonnet 4.6 or Granite via watsonx; airgap: `granite3.3:2b` via Ollama) with a structured rubric. CI gate: pass-rate ≥ 0.85. Cost cap: ≤ $2/run on cloud (Coach LLM + judge × 25 cases with small models), $0 on airgap.

**OTel instrumentation (#14)** — adds `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-instrumentation-flask`, `opentelemetry-instrumentation-sqlalchemy`, `opentelemetry-exporter-otlp` deps; an `otel-collector` + `jaeger` (single container, ports 16686 UI / 4317 OTLP) in compose; one env var (`OTEL_ENABLED=true`) gates the whole thing. Instruments: Flask routes (auto), DB sessions (auto), Supervisor classify, Specialist dispatch, Planner, Executor steps (one span per tool call), Synthesizer, Webhook receive, Kafka consume, MCP tool invoke. Jaeger over Tempo for v1: single container, no Grafana datasource setup, identical demo value.

**OllamaProvider (#15)** — implements existing `AIProvider` base class; dynamic model discovery via Ollama's `/api/tags` endpoint matching the pattern already used for the other 4 providers; default model `granite3.3:8b` for Coach LLM, `granite3.3:2b` for Supervisor classifier and eval judge. Provider selection stays env-driven (`AI_SERVICE=ollama`, `OLLAMA_BASE_URL=http://ollama:11434`).

### 4.2 Database additions

```sql
CREATE TABLE spending_signals (
  signal_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        UUID NOT NULL,
  signal_type    STRING NOT NULL,   -- 'budget_threshold' | 'anomaly' | 'recurring_drift'
  severity       STRING NOT NULL,   -- 'info' | 'warn' | 'critical'
  payload        JSONB NOT NULL,    -- signal-type-specific fields
  produced_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  consumed_at    TIMESTAMPTZ,
  idempotency_key STRING NOT NULL UNIQUE,
  INDEX (user_id, produced_at DESC)
) WITH (ttl_expire_after = '30 days');

CREATE TABLE coach_nudges (
  nudge_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  signal_id      UUID REFERENCES spending_signals(signal_id),
  user_id        UUID NOT NULL,
  message        STRING NOT NULL,
  tool_trace     JSONB,             -- which tools were called, in order
  provider_used  STRING,
  trace_id       STRING,            -- OTel trace ID for cross-reference
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  INDEX (user_id, created_at DESC)
) WITH (ttl_expire_after = '90 days');
```

`spending_signals` is written by the pipeline (and by `mock_signals.py` in dev). `coach_nudges` is written by the CoachAgent. Both use CockroachDB row-level TTL, matching the pattern already in use for LangGraph checkpoints.

## 5. Data flow

### 5.1 Reactive nudge (budget threshold)

```
1. Pipeline computes user "dining" budget at 82% utilization →
   INSERT INTO spending_signals (...)

2. CRDB CHANGEFEED on spending_signals fires on insert →
   POST https://banko/api/cdc/signals
     X-Banko-Signature: hmac(secret, body)
     X-Idempotency-Key: <signal_id>

3. Webhook receiver verifies HMAC + idempotency, normalizes to Signal(...),
   hands to SignalHandler.

4. SignalHandler:
   - Look up user prefs (DND hours, opted-out signal types)
   - If suppressed: mark consumed_at, log, exit
   - Else: invoke Supervisor.dispatch(signal) → Supervisor classifies as
     'coach_conversation' (signal-type → Coach route) → CoachAgent.react(signal)

5. CoachAgent (reactive mode):
   - Planner LLM call: produce 1-3 step plan
   - Executor runs tools in parallel where possible
   - Synthesizer LLM call: produce nudge text
   - Persist to coach_nudges with tool_trace + trace_id
   - Emit SocketIO event 'coach.nudge' to user's room

6. Browser (Live Coach tab) receives event, animates a new card.
   Card shows: nudge text, signal-type badge, "show evidence" (expands
   tool_trace), reply box.

7. UPDATE spending_signals SET consumed_at = now() WHERE signal_id = ?
```

**Latency budget**: signal-to-card ~2-4s under normal load on cloud LLM, ~5-15s on Ollama CPU. Webhook ack returns in <100ms (handler is async).

### 5.2 Conversational follow-up

```
1. User types "show me where I'd usually overshoot" in the reply box.

2. Browser POSTs /api/coach/chat {nudge_id, message, thread_id}.

3. Route fetches history via CockroachDBChatMessageHistory, hands to
   Supervisor.dispatch(message, history, context={nudge_id})
   → Supervisor classifies as 'coach_conversation'
   → CoachAgent.converse(message, history, context)

4. CoachAgent (conversational mode):
   - Planner LLM call: decompose into tool calls
   - Executor iterates (max 5 steps, hard cap)
   - Checkpoint saved at every node via CockroachDBSaver
   - Persist reply to chat_message_store

5. Stream reply back to browser via SSE.
```

### 5.3 Multi-intent (Supervisor routes to 2+ specialists)

User asks "am I over my dining budget AND was that Uber charge weird?"

```
1. Supervisor classifier returns 'multi' → [budget_query, fraud_check]
2. Supervisor dispatches to Budget and Fraud agents in parallel
3. Supervisor merge node combines responses, resolves contradictions
4. Single coherent reply streamed back to user
```

### 5.4 Prod-mode flow (Kafka/Debezium variant)

Steps 1-3 differ; step 4 onward is identical:

```
1. Pipeline INSERTs into spending_signals (same).
2. Debezium-CockroachDB connector captures the row, publishes to
   Kafka topic banko.spending_signals (key=user_id, value=JSON).
3. banko's SignalsKafkaConsumer polls, normalizes, calls SignalHandler.
```

### 5.5 MCP-driven flow (third channel)

User opens Claude Desktop → adds banko MCP server → asks "what's my dining budget?":

```
1. Claude Desktop sends tool call get_user_budget(user_id=u123,
   category=dining) over stdio.
2. MCP server invokes the same Tools.get_user_budget the agent uses.
3. Claude Desktop synthesizes the user-facing reply itself.
```

Same data layer, zero duplication.

## 6. Error handling & resilience

Every transport boundary has idempotency; every failure has a defined disposition; nothing fails silently. Correlation ID flows end-to-end.

### 6.1 Per-component error matrix

| Component | Failure | Disposition |
|---|---|---|
| Webhook receiver | HMAC mismatch | 401, log signature/source IP |
| | Duplicate idempotency key | 200 OK + `replayed: true` |
| | Malformed payload | 400 with structured error |
| | Handler raises | 202 Accepted to CRDB, enqueue retry, surface in /health |
| | Backpressure | 503 + Retry-After |
| Kafka consumer | Broker disconnect | Exp backoff (1s → 30s), surface to /health |
| | Poison message | After 3 fails: publish to `banko.spending_signals.dlq` + commit |
| | Slow handler | Manual offset commit only after handler success |
| | Lag growing | Metric, alert at 1000 unprocessed |
| CoachAgent (LLM) | Provider timeout | Retry once; if fails, emit fallback template, tag `provider_status: fallback` |
| | Tool failure | Retry once; planner re-plans with available data; abort if no minimum context |
| | Rate limit | Circuit breaker (5 consecutive 429s → 60s pause); failover to secondary provider if configured |
| | Token budget exceeded | Truncate history at message boundary; log truncation |
| | Agent loop > 5 steps | Hard abort, persist partial trace |
| Supervisor | Classifier LLM fails | Drop to static keyword router; surface degradation in /health |
| | Specialist fails | Return partial answer + trace ID |
| MCP server | Tool exception | MCP error response with retryable flag |
| | Stdio disconnect | Clean exit |
| Database | CRDB unavailable | Existing pool retry from `utils/database.py` |
| | Migration partial | CRDB DDL is transactional; atomic rollback. Add startup schema_version check. |
| Frontend | SocketIO disconnect | Auto-reconnect; on reconnect, `GET /api/coach/nudges?since=<last_id>` |
| | Race: nudge before tab open | Latest 20 loaded on tab open; SocketIO carries deltas only |

### 6.2 Cross-cutting

- **Correlation ID** = `signal_id` (reactive) or `thread_id` (conversational). Stamped on every log line, DB row, span attribute, external call.
- **Structured JSON logging** with `signal_id`, `user_id`, `component`, `latency_ms`, `outcome`.
- **Trace context propagation**: `signal_id` is a span attribute, not just a log field. One Jaeger query reconstructs the causal chain.
- **Privacy redactor**: `tool_trace` shown in UI is filtered (no account numbers, no raw PII); full trace remains in `coach_nudges.tool_trace` for ops.
- **Per-user rate limit on conversational mode**: token-bucket, default 30 messages / 5 min, configurable via env.
- **Health endpoint** (`/health/coach`) reports: webhook lag, Kafka lag (if mode=kafka), agent in-flight count, LLM circuit breaker state, last successful nudge timestamp, classifier degradation state.

## 7. Testing strategy

The bar: **`make test-local` runs all gates one command, exit-zero, in under 5 minutes (cloud) or 10 minutes (airgap CPU). Plus a 14-item manual smoke checklist before any push.**

### 7.1 Test pyramid

| Layer | Where | What it covers | Speed | CI? |
|---|---|---|---|---|
| Unit | `tests/coach/test_*.py` | Pure logic: signal normalization, planner parsing, redactor, HMAC, idempotency, rate-limit, supervisor routing | <1s each, ~50 tests | every PR |
| Integration | `tests/coach/integration/` | Real local CRDB (testcontainer or compose), Coach end-to-end with stubbed LLM, webhook receiver | ~30s | every PR |
| E2E | `tests/coach/e2e/` | Real CRDB, real Flask, real LLM (smoke), `mock_signals.py` fires 3 signal types, SocketIO assertion | ~2min | nightly + on-demand |
| Eval | `tests/eval/test_nudges.py` | LLM-as-judge on 25 fixtures; pass-rate ≥ 0.85 gate | ~3min, ≤$1 | every PR |
| Trace assertion | `tests/observability/test_tracing.py` | Asserts expected span tree for E2E flow | ~30s | every PR |
| Manual smoke | `docs/coach-smoke-checklist.md` | 14-item human-driven gate | ~5-10min | enforced by discipline |

### 7.2 LLM mocking

The Coach is half deterministic plumbing, half LLM call. `banko_ai/coach/agent.py` accepts an injected `llm_invoker` callable. Default = real provider. Tests inject a `StubInvoker` that returns canned planner responses keyed on signal type, and template synthesizer responses with real interpolated values. Real LLM exercised only in: E2E, eval, manual smoke — all opt-in via env flags so accidental runs don't cost money.

### 7.3 Manual smoke checklist (`docs/coach-smoke-checklist.md`)

Run by the human contributor on a local laptop before any `git push`. Not automated, not delegated to CI — the point is a person sees the feature working end-to-end with their own eyes against real provider responses.

1. `docker compose up -d` brings stack up clean; `/health/coach` green
2. Open Live Coach tab — empty state renders, no console errors
3. `mock_signals.py --type=budget_threshold` — card animates in, correct category + remaining $
4. Click "show evidence" — tool trace expands, shows actual SQL
5. Reply "show me last week's dining" — agent responds with real numbers
6. Switch provider mid-session (e.g., watsonx → OpenAI) — next nudge uses new provider (verify `provider_used`)
7. `mock_signals.py --type=anomaly` and `--type=recurring_drift` — each produces distinct, sensible nudge
8. Kill the LLM provider (block egress / bad key) — fallback template nudge fires, tagged `provider_status: fallback`
9. Stop CRDB mid-conversation — UI shows degraded state, no crash; restart CRDB, conversation resumes from checkpoint
10. Open MCP server, connect from Claude Desktop, ask "what's my dining budget?" — gets real answer
11. **Open Jaeger UI (http://localhost:16686)** — find trace for most recent nudge, verify ≥ 8 spans (supervisor → coach → tools → synthesizer)
12. **Multi-intent question** ("am I over budget AND was that uber charge weird?") — Supervisor dispatches to Budget+Fraud in parallel, response merges both
13. **Switch to Ollama** (`AI_SERVICE=ollama`), fire each signal type — nudges produced (latency ≤ 15s on CPU, ≤ 3s on GPU)
14. **Disconnect network entirely** (`docker network disconnect bridge`), repeat items 3-7 — all must still work

### 7.4 Multi-provider matrix

Smoke checklist items 3-7 must pass against **every provider the running deployment has credentials for**. Ship-readiness minimum: **all five** — watsonx, OpenAI, AWS Bedrock, Gemini, Ollama. Provider-specific bugs (token limits, tool-calling format differences, streaming behavior) only surface when each is exercised. One green provider is not enough. The smoke checklist's repeat pass per provider is what enforces this; CI does not (cost-prohibitive).

### 7.5 Prod-mode (Kafka) testing

`testcontainers-python` runs `redpanda` (Kafka-compatible, lighter than full Kafka) in `tests/coach/integration/test_kafka_consumer.py`. Exercises: poison-message DLQ, manual commit, lag metric. Mock generator gains `--transport=kafka` flag.

### 7.6 Coverage targets

- **80% line** on `banko_ai/coach/`, `banko_ai/agents/supervisor.py`, `banko_ai/observability/`, `banko_ai/ai_providers/ollama_provider.py` (enforced via `pytest --cov-fail-under=80`).
- **100% on contract paths**: HMAC verification, idempotency dedup, signal normalization, eval rubric scoring, Supervisor classification routing.
- No coverage gate on stub adapters / glue.

## 8. Pre-flight housekeeping

### 8.1 Dependency / vulnerability cleanup

12 open PRs / 16 alerts (4 high, 11 medium, 1 low). Batch by risk:

| Batch | PRs | Strategy |
|---|---|---|
| Safe bumps | #50 idna, #47 urllib3, #46 gunicorn range, #42 pypdf, #38 softprops/action | Single sweep PR, lockfile-only, closes ~7 alerts |
| LangChain family (lockstep) | #45 langchain-core, #48 langchain-classic, #43 langchain-openai, #44 langchain-text-splitters, #49 langsmith | Coordinated PR; fix API drift in one go; closes ~6 alerts including 3 highs |
| sentence-transformers | #39, #36 backline | Separate; needs embedding sanity check (regenerate a fixture vector, compare cosine distance) |
| transformers | manual bump | One-line in pyproject + lockfile regen; closes alert #94 |

Process per batch:

1. Fetch the dependabot branches locally (`gh pr checkout`) and rebase them into a single combined local branch per batch (e.g., `chore/dep-batch-safe-bumps`).
2. Regenerate the uv lockfile and resolve conflicts locally.
3. Run `make test-local` plus the full manual smoke checklist (§7.3) against each provider.
4. Only after all gates pass: push the combined branch, close the superseded individual dependabot PRs with a comment pointing at the combined PR, and merge the combined PR.

This sequence keeps "no commit/push until thoroughly tested" intact even though we're shipping bot-authored changes — we re-validate the combined result before either step.

### 8.2 README slim & restructure

Current state: 469 lines, 12 real sections, with broken markdown (code-block comments parsed as headings — fix throughout). Target structure (~250 lines):

```
# Banko AI Assistant
  [badges, one-paragraph what-and-why, architecture diagram]
## Quick start                (consolidates Quick Start + Configuration + Running)
## Features                   (slim list; link to docs/ for depth)
## The Spending Coach         (NEW — the flagship)
## Streaming integration      (NEW — webhook + Kafka, links to PIPELINE_CONTRACT.md)
## Deployment modes           (NEW — cloud / hybrid / airgap)
## Configuration reference    (env var table, no prose)
## API & MCP reference        (HTTP endpoints + MCP tools, table form)
## Observability              (NEW — Jaeger trace view)
## Development                (testing, lint, CI, eval)
## Troubleshooting            (pruned)
## License
```

Move depth into `docs/`: `architecture.md`, `providers.md`, `agents.md`, `coach.md`, `airgap.md`.

### 8.3 Opportunistic bug fixes (only where adjacent to Coach work)

| Bug | Fix? | Reason |
|---|---|---|
| 4 SQL-injection f-strings in `banko_ai/utils/agent_schema.py` | Yes | We're adding `spending_signals` + `coach_nudges` via same migration layer; ~30 min to parameterize |
| Hardcoded Flask secret | Yes | We're touching `web/app.py` for the webhook route; ~10 lines |
| `agent_memory.access_count` never incremented on read | No | Coach uses fresh memory pattern; leave for memory-system v2 |
| `SentenceTransformer` re-instantiated per call in `base_agent.py` | No | Existing perf bug unrelated to Coach; risk to existing agents |
| `documents` table schema drift | No | Unrelated to Coach |

## 9. Definition of done for v1

The Spending Coach is "done" when **all** of the following hold:

1. `docker compose up -d` brings the stack up clean on a laptop; `/health/coach` returns green
2. `scripts/coach/mock_signals.py --type={budget_threshold,anomaly,recurring_drift}` each produces a nudge in `coach_nudges` and an event on the Live Coach tab within 5s (cloud) / 15s (Ollama CPU)
3. Replying to a nudge yields a multi-tool response with real DB values (verified by tool_trace)
4. The MCP server connects to Claude Desktop and `get_user_budget` returns the same JSON the agent gets internally
5. All 14 items in the manual smoke checklist pass against **every configured provider** (watsonx, OpenAI, Bedrock, Gemini, Ollama)
6. Eval suite pass-rate ≥ 0.85 on 25 fixtures; judge model run ≤ $1 (cloud) / $0 (airgap)
7. `make test-local` is green
8. README is ≤ 250 lines, has the architecture diagram, has a "Spending Coach" section, no broken markdown headings
9. All 16 open dependabot alerts closed (PRs merged in grouped batches per §8.1, smoke re-run after each batch is integrated locally and before any push)
10. `PIPELINE_CONTRACT.md` exists at the repo root and has been handed to the pipeline-repo Claude session
11. **Jaeger shows a complete trace for a signal-to-nudge flow, ≥ 8 spans, including LLM call duration breakdown**
12. **Multi-intent question routes through Supervisor → 2 specialists → coherent merged response (no contradiction between specialists)**
13. **Supervisor classification accuracy ≥ 90% on a 10-sample intent fixture set**
14. **`docker compose -f docker-compose.airgap.yml up` produces a working stack with no external network calls** (verified by `docker network inspect` / network policy)

## 10. Effort estimate

| Block | Days |
|---|---|
| Coach core (signals, agent, tools, webhook, mock generator, DB migrations) | 2.0 |
| Kafka consumer + tests | 0.5 |
| MCP server + Claude Desktop verification | 0.5 |
| Flask Live Coach tab (UI + SocketIO) | 1.0 |
| Eval harness (fixtures, judge, CI gate) | 1.0 |
| Multi-agent Supervisor | 2.5 |
| OTel + Jaeger + instrumentation | 1.0 |
| Ollama provider + airgap compose + preload | 0.8 |
| Dep cleanup + README rewrite + PIPELINE_CONTRACT.md | 1.0 |
| Manual smoke (×5 providers, ×3 deployment modes) + buffer | 1.0 |
| **Total** | **~11.3 days** |

Realistically 2-3 calendar weeks at part-time pace, allowing for the test-locally-thoroughly-before-push discipline.

## 11. Pipeline-side contract (`PIPELINE_CONTRACT.md` outline)

The full document lives at the repo root and is the artifact handed to the pipeline-repo Claude session. Skeleton:

1. **`spending_signals` table DDL** — canonical schema (this repo creates the migration; pipeline writes to it)
2. **Per signal type**: trigger condition, required fields, example row
   - `budget_threshold`: fires at 50%/80%/100% per user × category
   - `anomaly`: deviates from user's pattern (amount-for-merchant, off-hours, new geo)
   - `recurring_drift`: subscription amount change
3. **Webhook contract**: URL `POST /api/cdc/signals`, headers (`X-Banko-Signature`, `X-Idempotency-Key`), payload format (CRDB changefeed JSON envelope), idempotency semantics
4. **Kafka contract**: topic `banko.spending_signals`, key `user_id`, value JSON schema, partitioning notes, ordering guarantees per partition
5. **Mock signal generator** — `scripts/coach/mock_signals.py` in this repo; pipeline side can use it as a reference implementation
6. **Integration smoke test** — `scripts/coach/assert_nudges.py` in this repo; pipeline side runs it to prove end-to-end delivery
7. **Operational notes**: idempotency, retries, ordering, backpressure, schema evolution policy, known prod gaps (external retry worker)

## 12. Open questions

None blocking. Items deferred to implementation-time decisions:

- Specific Jaeger vs Tempo+Grafana choice (currently Jaeger for simplicity; revisit if user wants Grafana panels alongside trace view)
- Eval fixture authoring: handcrafted vs LLM-generated then human-curated (likely the latter, but defer until we have the harness running)
- Whether to ship `granite3.3:8b` or a smaller default for CPU-only airgap deployments (test-and-decide)
