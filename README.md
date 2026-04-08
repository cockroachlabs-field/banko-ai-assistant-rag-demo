[![PyPI version](https://img.shields.io/pypi/v/banko-ai-assistant)](https://pypi.org/project/banko-ai-assistant/)
[![Python versions](https://img.shields.io/pypi/pyversions/banko-ai-assistant)](https://pypi.org/project/banko-ai-assistant/)
[![License](https://img.shields.io/pypi/l/banko-ai-assistant)](https://pypi.org/project/banko-ai-assistant/)
[![Downloads](https://img.shields.io/pypi/dm/banko-ai-assistant)](https://pypi.org/project/banko-ai-assistant/)
[![Docker Pulls](https://img.shields.io/docker/pulls/virag/banko-ai-assistant)](https://hub.docker.com/r/virag/banko-ai-assistant)
[![Docker Image Size](https://img.shields.io/docker/image-size/virag/banko-ai-assistant/latest)](https://hub.docker.com/r/virag/banko-ai-assistant)

# Banko AI Assistant - RAG and Agentic-AI Demo

An AI-powered expense analysis application demonstrating Retrieval-Augmented Generation (RAG) and agentic-AI workflows with CockroachDB vector search and multiple AI provider support.

![Banko AI Assistant](https://raw.githubusercontent.com/cockroachlabs-field/banko-ai-assistant/main/banko_ai/static/banko-ai-assistant-watsonx.gif)

## Architecture

![Banko AI Architecture](https://raw.githubusercontent.com/cockroachlabs-field/banko-ai-assistant/main/banko_ai/static/banko-ai-architecture.png)

The application uses a five-layer architecture:

### 1. Presentation Layer

- **Flask Routes**: API endpoints for search, RAG, receipt upload, data generation, and agent status
- **Templates**: Responsive web UI with real-time chat
- **WebSocket Events**: Real-time agent activity updates via Flask-SocketIO

**Location**: `banko_ai/web/app.py`

### 2. Agent Orchestration

Multi-agent system with specialized agents:

- **Receipt Agent**: OCR and data extraction from uploaded receipts (images and PDFs)
- **Fraud Agent**: Duplicate detection, statistical anomaly analysis, and suspicious pattern recognition
- **Budget Agent**: Spending categorization and budget impact analysis
- **Orchestrator Agent**: Coordinates multi-agent workflows

Receipt uploads trigger a LangGraph pipeline: `Receipt -> Fraud -> Budget -> Done`, checkpointed by `CockroachDBSaver` for crash recovery and replay.

**Location**: `banko_ai/agents/`

### 3. AI Provider Layer

Abstraction layer with a standardized interface to multiple LLMs:

- **IBM Watsonx** (GPT-OSS-120B, Llama 3/4, Granite, Mistral)
- **OpenAI** (GPT-4o-mini, GPT-4o, GPT-4.1, GPT-5)
- **AWS Bedrock** (Claude Sonnet 4, Claude 3.5 Haiku, Claude Opus 4 via inference profiles)
- **Google Gemini** (Gemini 2.0 Flash, Gemini 1.5 Pro, Gemini 1.5 Flash)

Models are **dynamically discovered** from each provider's API. Switch providers and models from the Settings page or via environment variables -- no restart required. Override with `WATSONX_MODELS`, `OPENAI_MODELS`, `AWS_MODELS`, or `GEMINI_MODELS` (comma-separated).

**Location**: `banko_ai/ai_providers/`

### 4. Vector Search Engine

Semantic search using CockroachDB vector indexes:

- **Embeddings**: `all-MiniLM-L6-v2` (384 dimensions) via sentence-transformers -- runs locally, no API key needed
- **Cosine Similarity**: Industry-standard `<=>` operator with C-SPANN indexes
- **[langchain-cockroachdb](https://github.com/cockroachdb/langchain-cockroachdb)**: `CockroachDBVectorStore` with automatic C-SPANN indexing
- **Multi-Layer Caching**: Query cache, embedding cache, and vector search cache with configurable similarity thresholds

**Location**: `banko_ai/vector_search/`

### 5. Data Persistence

CockroachDB as a unified store for three data types:

- **SQL Data**: Structured financial data (expenses, accounts)
- **Vector Data**: 384-dimensional embeddings for semantic search
- **Agent State**: Memory, decisions, tasks, and workflow checkpoints

**Key integrations via [langchain-cockroachdb](https://github.com/cockroachdb/langchain-cockroachdb)**:

| Component | Purpose | Table |
|-----------|---------|-------|
| `CockroachDBEngine` | Shared async connection pool (psycopg3) | -- |
| `CockroachDBVectorStore` | Semantic search with C-SPANN cosine indexes | `expense_vectors` |
| `CockroachDBChatMessageHistory` | Persistent chat per session/thread | `chat_message_store` |
| `CockroachDBSaver` | LangGraph checkpointer for durable workflows | `checkpoint*` tables |

**Location**: `banko_ai/utils/`

## Features

- **RAG**: Retrieval-Augmented Generation with AI-powered financial insights
- **Vector Search**: Semantic expense search using CockroachDB C-SPANN vector indexes
- **Multi-Agent System**: Receipt processing, fraud detection, and budget analysis agents
- **LangGraph Workflows**: Multi-agent receipt pipeline with crash-resistant checkpointing
- **Duplicate Detection**: Fraud agent flags duplicate receipts (same merchant + amount)
- **Persistent Chat History**: Conversations stored in CockroachDB, survive restarts
- **Multi-AI Provider**: OpenAI, AWS Bedrock, IBM Watsonx, Google Gemini -- switch without restart
- **Dynamic Model Switching**: Change models from the Settings page
- **Data Generator**: Built-in UI to generate and seed sample expense data with embeddings
- **Multi-Layer Caching**: Query, embedding, and result caching with configurable thresholds
- **Agent Dashboard**: Real-time view of agent status, regions, and activity
- **Security**: Auto-generated Flask secret keys, no hardcoded credentials
- **PyPI Package**: `pip install banko-ai-assistant`
- **Docker**: `docker-compose up -d`

## Quick Start

### Prerequisites

- **Python 3.10+**
- **CockroachDB v25.4.0+** (with vector index support)
- **AI Provider API Key** (at least one: OpenAI, AWS, IBM Watsonx, or Google Gemini)

### Installation

**PyPI**
```bash
pip install banko-ai-assistant
```

**Docker**
```bash
docker-compose up -d
```

**Development**
```bash
git clone https://github.com/cockroachlabs-field/banko-ai-assistant
cd banko-ai-assistant
pip install -e ".[dev]"
```

**With uv (faster)**
```bash
uv pip install banko-ai-assistant
# Or for development:
uv pip install -e ".[dev]"
```

### CockroachDB Setup

```bash
# Install
brew install cockroachdb/tap/cockroach  # macOS

# Start single node
cockroach start-single-node \
  --insecure \
  --store=./cockroach-data \
  --listen-addr=localhost:26257 \
  --http-addr=localhost:8080 \
  --background

# Verify
cockroach sql --insecure --execute "SELECT version();"
```

### Run

```bash
# Set provider credentials (example: Watsonx)
export AI_SERVICE="watsonx"
export WATSONX_API_KEY="your_api_key"
export WATSONX_PROJECT_ID="your_project_id"
export DATABASE_URL="cockroachdb://root@localhost:26257/defaultdb?sslmode=disable"

# Start (generates 5000 sample records on first run)
banko-ai run
```

Open http://localhost:5000

## Configuration

### Core Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | CockroachDB connection string | `cockroachdb://root@localhost:26257/defaultdb?sslmode=disable` |
| `AI_SERVICE` | AI provider | `watsonx` |
| `SECRET_KEY` | Flask session key (auto-generated if not set) | Random |

**Note**: `postgresql://` and `postgres://` URLs are automatically normalized to `cockroachdb://` for proper dialect handling.

### AI Provider Configuration

#### IBM Watsonx
```bash
export WATSONX_API_KEY="your_api_key"
export WATSONX_PROJECT_ID="your_project_id"
export WATSONX_MODEL_ID="openai/gpt-oss-120b"  # Default
```

| Variable | Description | Default |
|----------|-------------|---------|
| `WATSONX_API_URL` | API endpoint URL | US South region |
| `WATSONX_TOKEN_URL` | IAM endpoint | IBM Cloud IAM |
| `WATSONX_TIMEOUT` | Timeout (sec) | `30` |

#### OpenAI
```bash
export OPENAI_API_KEY="your_key"
export OPENAI_MODEL="gpt-4o-mini"  # Default
```

#### AWS Bedrock
```bash
export AWS_ACCESS_KEY_ID="your_access_key"
export AWS_SECRET_ACCESS_KEY="your_secret_key"
export AWS_REGION="us-east-1"
export AWS_MODEL_ID="us.anthropic.claude-3-5-haiku-20241022-v1:0"
```

#### Google Gemini
```bash
export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account.json"
export GOOGLE_PROJECT_ID="your-project-id"
export GOOGLE_MODEL="gemini-2.0-flash-001"  # Default
export GOOGLE_LOCATION="us-central1"
```

Or use the Generative AI API:
```bash
export GOOGLE_API_KEY="your-gemini-api-key"
```

### Response Caching

```bash
export CACHE_SIMILARITY_THRESHOLD="0.75"  # Default (0.0-1.0)
export CACHE_TTL_HOURS="24"               # Default
export CACHE_STRICT_MODE="true"           # Default (requires data match)
```

| Preset | Threshold | Strict Mode | Hit Rate |
|--------|-----------|-------------|----------|
| Demo | 0.75 | false | 80-90% |
| Balanced (recommended) | 0.75 | true | 60-70% |
| Conservative | 0.85 | true | 50-60% |

### Fraud Detection

```bash
export FRAUD_DUPLICATE_WINDOW_DAYS="60"   # Days to look back for duplicates (default: 60)
```

### Database Connection Pool

```bash
export DB_POOL_SIZE="100"          # Base pool size (default)
export DB_MAX_OVERFLOW="100"       # Max overflow connections
export DB_POOL_TIMEOUT="30"        # Connection timeout (sec)
export DB_POOL_RECYCLE="3600"      # Recycle after (sec)
export DB_POOL_PRE_PING="true"     # Test before use
```

### Regional Configuration

```bash
# Watsonx EU
export WATSONX_API_URL="https://eu-de.ml.cloud.ibm.com/ml/v1/text/chat?version=2023-05-29"

# AWS Europe
export AWS_REGION="eu-west-1"

# Google Europe
export GOOGLE_LOCATION="europe-west1"
```

## Running the Application

```bash
# Start with default settings (5000 sample records)
banko-ai run

# Custom port
banko-ai run --port 5001

# Custom data amount
banko-ai run --generate-data 10000

# Without generating data
banko-ai run --no-data

# Debug mode
banko-ai run --debug
```

### What Happens on Startup

1. Connects to CockroachDB and creates tables (expenses, agent tables, cache tables)
2. Generates sample expense records with embeddings (if needed)
3. Initializes selected AI provider
4. Starts Flask web server

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
| `/diagnostics/watsonx` | GET | Watsonx connection diagnostics |

### Examples

```bash
# Health check
curl http://localhost:5000/api/health

# Vector search
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "coffee shop expenses", "limit": 5}'

# RAG query
curl -X POST http://localhost:5000/api/rag \
  -H "Content-Type: application/json" \
  -d '{"query": "What are my biggest expenses this month?"}'

# Upload receipt
curl -X POST http://localhost:5000/api/upload-receipt \
  -F "receipt=@receipt.png"

# Agent status
curl http://localhost:5000/api/agents/status
```

## Database Schema

### Core Tables

| Table | Purpose |
|-------|---------|
| `expenses` | Expense records with 384-dim vector embeddings |
| `expense_vectors` | LangChain VectorStore (C-SPANN cosine index) |
| `chat_message_store` | Persistent chat history per session |
| `checkpoint*` | LangGraph workflow state (CockroachDBSaver) |

### Agent Tables

| Table | Purpose |
|-------|---------|
| `agent_state` | Agent registration and heartbeats |
| `agent_memory` | Agent memory with vector embeddings |
| `agent_tasks` | Inter-agent task queue |
| `agent_decisions` | Fraud/budget decisions with feedback loop |
| `documents` | Uploaded receipt/document metadata |

### Cache Tables

| Table | Purpose |
|-------|---------|
| `query_cache` | Cached RAG responses with semantic similarity |
| `embedding_cache` | Cached vector embeddings |
| `vector_search_cache` | Cached search results |
| `cache_stats` | Cache hit/miss statistics |

### Vector Indexes

```sql
-- C-SPANN cosine indexes for semantic search
CREATE INDEX idx_expenses_embedding ON expenses USING cspann (embedding vector_cosine_ops);
CREATE INDEX idx_cspann_expense_vectors_embedding ON expense_vectors USING cspann (embedding vector_cosine_ops);
```

## CLI Commands

```bash
banko-ai run [OPTIONS]           # Run application
banko-ai generate-data --count N # Generate sample data
banko-ai clear-data              # Clear all data
banko-ai status                  # Check status
banko-ai search "query"          # Search expenses
banko-ai help                    # Help
```

## Project Structure

```
banko_ai/
├── agents/
│   ├── base_agent.py            # Base agent with memory, tasks, decisions
│   ├── receipt_agent.py         # OCR and data extraction
│   ├── fraud_agent.py           # Duplicate and anomaly detection
│   ├── budget_agent.py          # Budget impact analysis
│   ├── orchestrator_agent.py    # Multi-agent coordination
│   ├── receipt_workflow.py      # LangGraph pipeline + CockroachDBSaver
│   ├── llm_factory.py           # Provider-agnostic LLM creation
│   └── tools/                   # LangChain tools (search, analysis, document)
├── ai_providers/
│   ├── base.py                  # Provider interface
│   ├── factory.py               # Provider factory
│   ├── openai_provider.py
│   ├── aws_provider.py
│   ├── gemini_provider.py
│   └── watsonx_provider.py
├── config/
│   └── settings.py              # Centralized env-based configuration
├── utils/
│   ├── db_retry.py              # DB retry logic, URL normalization, connection pooling
│   ├── cache_manager.py         # Multi-layer semantic caching
│   ├── database.py              # Schema creation
│   ├── agent_schema.py          # Agent table schema
│   ├── crdb_engine.py           # Singleton CockroachDBEngine
│   └── crdb_chat_history.py     # CockroachDBChatMessageHistory wrapper
├── vector_search/
│   ├── search.py                # Vector search engine
│   ├── enrichment.py            # Data enrichment for embeddings
│   ├── generator.py             # Sample data generator with batch embeddings
│   └── crdb_vectorstore.py      # CockroachDBVectorStore wrapper
├── web/
│   ├── app.py                   # Flask app with all routes
│   ├── agent_dashboard.py       # Agent status API
│   └── auth.py                  # Authentication
├── cli.py                       # CLI entry point
└── __main__.py                  # Module entry point
```

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Individual test suites
python tests/test_vector_index.py        # Vector search verification
python tests/test_cache_after_cleanup.py # Cache system tests
python tests/test_all_providers.py       # Multi-provider tests
python tests/test_env_config.py          # Environment config tests

# Lint
ruff check banko_ai/
```

## Troubleshooting

### CockroachDB Version
Must be v25.4.0+ for vector index support:
```bash
cockroach version
```

### Database Connection Error
```bash
cockroach start-single-node --insecure --store=./cockroach-data \
  --listen-addr=localhost:26257 --http-addr=localhost:8080 --background
cockroach sql --insecure --execute "SHOW TABLES;"
```

### AI Provider Issues
- Verify API keys are correct and exported
- Check `/api/health` for connection status
- Use `/diagnostics/watsonx` for Watsonx-specific debugging

### Port 5000 in Use (macOS)
macOS AirPlay Receiver uses port 5000. Either disable it in System Settings > AirDrop & Handoff, or use a different port:
```bash
banko-ai run --port 5001
```

## License

MIT License
