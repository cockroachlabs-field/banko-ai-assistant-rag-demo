[![PyPI version](https://img.shields.io/pypi/v/banko-ai-assistant)](https://pypi.org/project/banko-ai-assistant/)
[![Python versions](https://img.shields.io/pypi/pyversions/banko-ai-assistant)](https://pypi.org/project/banko-ai-assistant/)
[![License](https://img.shields.io/pypi/l/banko-ai-assistant)](https://pypi.org/project/banko-ai-assistant/)
[![Downloads](https://img.shields.io/pypi/dm/banko-ai-assistant)](https://pypi.org/project/banko-ai-assistant/)
[![Docker Pulls](https://img.shields.io/docker/pulls/virag/banko-ai-assistant)](https://hub.docker.com/r/virag/banko-ai-assistant)
[![Docker Image Size](https://img.shields.io/docker/image-size/virag/banko-ai-assistant/latest)](https://hub.docker.com/r/virag/banko-ai-assistant)

# Banko AI Assistant

Agentic banking AI on CockroachDB. A working demo of LangGraph multi-agent workflows, vector RAG, multi-provider LLM routing, and durable checkpointing — all backed by a single CockroachDB cluster.

![Banko AI Assistant](https://raw.githubusercontent.com/cockroachlabs-field/banko-ai-assistant/main/banko_ai/static/banko-ai-assistant-watsonx.gif)

## Architecture

![Banko AI Architecture](https://raw.githubusercontent.com/cockroachlabs-field/banko-ai-assistant/main/banko_ai/static/banko-ai-architecture.png)

Five layers, one database:

| Layer | What it does | Where |
|-------|--------------|-------|
| **Web** | Flask + SocketIO UI, REST API, real-time agent status | `banko_ai/web/` |
| **Agents** | LangGraph pipeline (`Receipt → Fraud → Budget`) checkpointed by `CockroachDBSaver` for crash recovery and replay | `banko_ai/agents/` |
| **AI providers** | One abstraction over watsonx, OpenAI, AWS Bedrock, Gemini — switchable at runtime, models discovered dynamically | `banko_ai/ai_providers/` |
| **Vector search** | `CockroachDBVectorStore` with C-SPANN cosine indexes, 384-dim `all-MiniLM-L6-v2` embeddings (local, no API key) | `banko_ai/vector_search/` |
| **Persistence** | CockroachDB stores SQL, vectors, and agent state in one cluster | `banko_ai/utils/` |

Core integrations via [`langchain-cockroachdb`](https://github.com/cockroachdb/langchain-cockroachdb):

| Component | Purpose | Table |
|-----------|---------|-------|
| `CockroachDBEngine` | Shared async connection pool (psycopg3) | — |
| `CockroachDBVectorStore` | Semantic search with C-SPANN cosine indexes | `expense_vectors` |
| `CockroachDBChatMessageHistory` | Persistent chat per session/thread | `chat_message_store` |
| `CockroachDBSaver` | LangGraph checkpointer for durable workflows | `checkpoint*` tables |

## Features

- **Multi-agent receipt pipeline** — Receipt OCR → fraud screen → budget impact, with durable checkpoints
- **Multi-provider LLM** — watsonx (default), OpenAI, AWS Bedrock, Google Gemini; swap from Settings or env without restart
- **Dynamic model discovery** — model lists come from the provider API, not a hardcoded enum
- **Vector RAG** — C-SPANN cosine indexes over expenses, embeddings generated locally
- **Persistent chat** — conversations survive restarts via `CockroachDBChatMessageHistory`
- **Three-layer cache** — query / embedding / vector-search caches with semantic similarity thresholds
- **Agent dashboard** — real-time view of agent status and activity (no canned demo data)
- **Packaged** — `pip install banko-ai-assistant` or `docker-compose up -d`

## Quick Start

### Prerequisites

- Python 3.10+ (3.12 recommended)
- CockroachDB v25.4.0+ (vector indexes are GA)
- At least one AI provider API key (watsonx, OpenAI, AWS, or Gemini)

### Install

```bash
# PyPI
pip install banko-ai-assistant

# Or with uv (faster)
uv pip install banko-ai-assistant

# Or Docker
docker-compose up -d

# Or develop locally
git clone https://github.com/cockroachlabs-field/banko-ai-assistant
cd banko-ai-assistant
uv pip install -e ".[dev]"
```

### Start CockroachDB

```bash
brew install cockroachdb/tap/cockroach   # macOS

cockroach start-single-node \
  --insecure \
  --store=./cockroach-data \
  --listen-addr=localhost:26257 \
  --http-addr=localhost:8080 \
  --background

cockroach sql --insecure --execute "SELECT version();"
```

### Run

```bash
export AI_SERVICE="watsonx"                    # or openai, aws, gemini
export WATSONX_API_KEY="..."
export WATSONX_PROJECT_ID="..."
export DATABASE_URL="cockroachdb://root@localhost:26257/defaultdb?sslmode=disable"

banko-ai run                          # default: port 5000, generates 5000 sample records
banko-ai run --port 5001              # custom port (macOS AirPlay grabs 5000)
banko-ai run --generate-data 10000    # more sample data
banko-ai run --no-data                # skip data generation
banko-ai run --debug                  # debug mode
```

Open http://localhost:5000.

On first start the app connects to CockroachDB, creates its schema (expense, agent, cache, and checkpoint tables), generates sample data with embeddings, initializes the selected AI provider, and starts the Flask server.

## Configuration

### Core

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | CockroachDB connection string | `cockroachdb://root@localhost:26257/defaultdb?sslmode=disable` |
| `AI_SERVICE` | AI provider (`watsonx`, `openai`, `aws`, `gemini`) | `watsonx` |
| `SECRET_KEY` | Flask session key (auto-generated if not set) | random |

`postgresql://` and `postgres://` URLs are auto-normalized to `cockroachdb://`.

### AI providers

```bash
# IBM watsonx
export WATSONX_API_KEY="..."
export WATSONX_PROJECT_ID="..."
export WATSONX_MODEL_ID="openai/gpt-oss-120b"          # default
# Optional: WATSONX_API_URL, WATSONX_TOKEN_URL, WATSONX_TIMEOUT

# OpenAI
export OPENAI_API_KEY="..."
export OPENAI_MODEL="gpt-4o-mini"                       # default

# AWS Bedrock (note: AI_SERVICE=aws, not bedrock)
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_REGION="us-east-1"
export AWS_MODEL_ID="us.anthropic.claude-3-5-haiku-20241022-v1:0"

# Google Gemini (Vertex AI)
export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account.json"
export GOOGLE_PROJECT_ID="..."
export GOOGLE_MODEL="gemini-2.0-flash-001"              # default
export GOOGLE_LOCATION="us-central1"
# Or the Generative AI API:
export GOOGLE_API_KEY="..."
```

Override model lists with `WATSONX_MODELS`, `OPENAI_MODELS`, `AWS_MODELS`, `GEMINI_MODELS` (comma-separated).

### Cache, fraud, and pool

```bash
# Semantic cache
export CACHE_SIMILARITY_THRESHOLD="0.75"   # 0.0-1.0
export CACHE_TTL_HOURS="24"
export CACHE_STRICT_MODE="true"            # require data match for hits

# Fraud detection
export FRAUD_DUPLICATE_WINDOW_DAYS="60"

# DB connection pool
export DB_POOL_SIZE="100"
export DB_MAX_OVERFLOW="100"
export DB_POOL_TIMEOUT="30"
export DB_POOL_RECYCLE="3600"
export DB_POOL_PRE_PING="true"
```

| Cache preset | Threshold | Strict | Typical hit rate |
|--------------|-----------|--------|------------------|
| Demo | 0.75 | false | 80-90% |
| Balanced (recommended) | 0.75 | true | 60-70% |
| Conservative | 0.85 | true | 50-60% |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web interface |
| `/api/health` | GET | Health check (DB + AI status) |
| `/api/ai-providers` | GET | Available AI providers |
| `/api/models` | GET/POST | List or switch models |
| `/api/search` | POST | Vector search expenses |
| `/api/vectorstore-search` | POST | Search via langchain-cockroachdb VectorStore |
| `/api/rag` | POST | RAG-based Q&A with AI insights |
| `/api/upload-receipt` | POST | Upload receipt image/PDF for agent processing |
| `/api/agents/status` | GET | Agent dashboard data |
| `/api/chat-history/<id>` | GET/DELETE | Persistent chat history per session |
| `/api/generate-data` | POST | Generate sample expense data |
| `/data-generator` | GET | Data generator UI |
| `/cache-stats` | GET | Cache performance statistics |
| `/diagnostics/watsonx` | GET | watsonx connection diagnostics |

```bash
# Health
curl http://localhost:5000/api/health

# Vector search
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "coffee shop expenses", "limit": 5}'

# RAG
curl -X POST http://localhost:5000/api/rag \
  -H "Content-Type: application/json" \
  -d '{"query": "What are my biggest expenses this month?"}'

# Receipt upload
curl -X POST http://localhost:5000/api/upload-receipt -F "receipt=@receipt.png"
```

## Database Schema

| Group | Tables |
|-------|--------|
| Core | `expenses` (with 384-dim embedding), `expense_vectors` (LangChain VectorStore), `chat_message_store`, `checkpoint*` (LangGraph state) |
| Agents | `agent_state`, `agent_memory`, `agent_tasks`, `agent_decisions`, `documents` |
| Cache | `query_cache`, `embedding_cache`, `vector_search_cache`, `cache_stats` |

Vector indexes use C-SPANN cosine ops:

```sql
CREATE INDEX idx_expenses_embedding ON expenses USING cspann (embedding vector_cosine_ops);
CREATE INDEX idx_cspann_expense_vectors_embedding ON expense_vectors USING cspann (embedding vector_cosine_ops);
```

## CLI

```bash
banko-ai run [OPTIONS]            # run the app
banko-ai generate-data --count N  # generate sample data
banko-ai clear-data               # clear all data
banko-ai status                   # check status
banko-ai search "query"           # vector search from the shell
banko-ai help
```

## Project Structure

```
banko_ai/
├── agents/          # LangGraph specialist agents + workflows (CockroachDBSaver)
├── ai_providers/    # Provider abstraction — all LLM calls go through here
├── config/          # Env-driven settings
├── pipeline/        # CDC config (webhook + Kafka modes)
├── utils/           # DB engine, cache, schema, retry/pooling, chat history
├── vector_search/   # Search engine, enrichment, data generator, VectorStore wrapper
├── web/             # Flask app, agent dashboard, auth
└── cli.py
```

## Testing

```bash
python -m pytest tests/ -v               # all tests
python tests/test_vector_index.py        # vector search verification
python tests/test_cache_after_cleanup.py # cache system
python tests/test_all_providers.py       # multi-provider
python tests/test_env_config.py          # env config
ruff check banko_ai/                     # lint
```

Integration tests need a populated CockroachDB; they're skipped automatically in CI when the DB isn't available.

## Deployment Modes

| Mode | LLM | Embeddings | Data plane |
|------|-----|------------|-----------|
| **Cloud** | watsonx / OpenAI / Bedrock / Gemini | local | CockroachDB |
| **Hybrid** | cloud LLM | local | on-prem CockroachDB + CDC pipeline |
| **Airgap** *(roadmap)* | Ollama | local | on-prem everything |

## Roadmap

Currently in design (`docs/superpowers/specs/`):

- **Proactive Spending Coach** — streaming CDC signals (budget thresholds, anomalies, recurring-charge drift) trigger an LLM-powered nudge through the agent pipeline, with optional conversational follow-up.
- **OpenTelemetry observability** — spans across web → agent → LLM → DB, viewable in Jaeger.
- **Multi-agent supervisor** — LLM-routed dispatch across Receipt / Fraud / Budget / Coach.
- **MCP server** — expose agent capabilities over the Model Context Protocol.
- **Ollama airgap mode** — full functionality with no outbound network calls (granite3.3 default).
- **Eval harness** — LLM-as-judge fixtures gated on pass-rate ≥ 0.85.

The companion streaming pipeline (Debezium → Kafka → Iceberg on watsonx.data) lives in [`cockroachlabs-field/cockroachdb-watsonx-data-pipeline`](https://github.com/cockroachlabs-field/cockroachdb-watsonx-data-pipeline).

## Troubleshooting

**CockroachDB version** — must be v25.4.0+ for vector indexes. Check with `cockroach version`.

**DB connection error** — verify the single-node command above is running, then `cockroach sql --insecure --execute "SHOW TABLES;"`.

**AI provider issues** — confirm keys are exported, then hit `/api/health`. For watsonx specifically, `/diagnostics/watsonx` has connection details.

**Port 5000 in use (macOS)** — AirPlay Receiver claims port 5000. Either disable it in System Settings → AirDrop & Handoff, or run `banko-ai run --port 5001`.

## License

MIT
