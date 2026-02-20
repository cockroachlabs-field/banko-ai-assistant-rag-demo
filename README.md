[![PyPI version](https://img.shields.io/pypi/v/banko-ai-assistant)](https://pypi.org/project/banko-ai-assistant/)
[![Python versions](https://img.shields.io/pypi/pyversions/banko-ai-assistant)](https://pypi.org/project/banko-ai-assistant/)
[![License](https://img.shields.io/pypi/l/banko-ai-assistant)](https://pypi.org/project/banko-ai-assistant/)
[![Downloads](https://img.shields.io/pypi/dm/banko-ai-assistant)](https://pypi.org/project/banko-ai-assistant/)
[![Docker Pulls](https://img.shields.io/docker/pulls/virag/banko-ai-assistant)](https://hub.docker.com/r/virag/banko-ai-assistant)
[![Docker Image Size](https://img.shields.io/docker/image-size/virag/banko-ai-assistant/latest)](https://hub.docker.com/r/virag/banko-ai-assistant)

# 🤖 Banko AI Assistant - RAG and Agentic-AI Demo

An AI-powered expense analysis application demonstrating Retrieval-Augmented Generation (RAG) and agentic-AI workflows with CockroachDB vector search and multiple AI provider support.

![Banko AI Assistant](https://raw.githubusercontent.com/cockroachlabs-field/banko-ai-assistant-rag-demo/main/banko_ai/static/banko-ai-assistant-watsonx.gif)

## Architecture

![Banko AI Architecture](https://raw.githubusercontent.com/cockroachlabs-field/banko-ai-assistant-rag-demo/main/banko_ai/static/banko-ai-architecture.png)

The application uses a five-layer architecture designed for scalability, flexibility, and intelligent data processing:

### 1. Presentation Layer (The Front Door)

**Role**: Handles all interactions with the outside world (users or other systems).

**Components**:
- **Flask Routes**: API endpoints that the application responds to
- **Templates**: HTML files for the user interface
- **WebSocket Events**: Real-time, two-way communication for live chat and status updates

**Location**: `banko_ai/web/app.py` and `templates/*.html`

### 2. Agent Orchestration (The Brain)

**Role**: Core logic tier that decides what needs to be done with a user's request.

**Components**:
- **Multi-Agent System**: Specialized agents designed for specific tasks instead of one monolithic AI
  - **Receipt Agent**: OCR and data extraction from uploaded receipts
  - **Fraud Agent**: Transaction analysis for suspicious patterns
  - **Budget Agent**: Categorization and spending analysis

**Function**: Receives input from the presentation layer and routes it to the correct specialized agent.

**Location**: `banko_ai/agents/*.py`

### 3. AI Provider Layer (The Translator)

**Role**: Abstraction layer providing a standardized interface to external Large Language Models (LLMs).

**Components**:
- **LangChain**: Framework for managing LLM interactions, chaining commands, and handling context
- **Provider Adapters**: Support for multiple backend providers (OpenAI, AWS Bedrock, Google Gemini, IBM Watsonx)

**Function**: Ensures agent orchestration code doesn't change when switching AI model providers.

**Location**: `banko_ai/ai_providers/*.py`

### 4. Vector Search Engine (The Semantic Memory)

**Role**: Enables semantic search based on meaning rather than keyword matching, critical for RAG.

**Components**:
- **Embeddings**: Converts text data into numerical vectors representing semantic meaning
- **Semantic Search**: Finds relevant information by comparing vector similarity
- **[langchain-cockroachdb](https://github.com/cockroachdb/langchain-cockroachdb) VectorStore**: LangChain-native `CockroachDBVectorStore` with C-SPANN indexes and cosine similarity
- **Cache**: Stores frequent search results for faster responses

**Location**: `banko_ai/vector_search/*.py`

### 5. Data Persistence (The Foundation)

**Role**: Ultimate storage location for all application data.

**Components**:
- **CockroachDB**: Distributed SQL database used as a hybrid database storing three distinct data types:
  - **SQL Data**: Structured financial data (expenses table)
  - **Vector Data**: Embeddings for semantic search directly in the database
  - **Agent State**: Short-term memory of AI agents (agent_state, agent_memory, agent_tasks), allowing ongoing conversations and multi-step tasks to persist across restarts
- **[langchain-cockroachdb](https://github.com/cockroachdb/langchain-cockroachdb)**: Official LangChain integration providing:
  - **CockroachDBEngine**: Shared async connection pool (psycopg3)
  - **CockroachDBVectorStore**: LangChain VectorStore backed by C-SPANN cosine indexes
  - **CockroachDBChatMessageHistory**: Persistent chat history per session/thread
  - **CockroachDBSaver**: LangGraph checkpointer for durable agent workflows

**Location**: `banko_ai/utils/database.py`, `banko_ai/utils/agent_schema.py`, `banko_ai/utils/crdb_engine.py`, `banko_ai/utils/crdb_chat_history.py`

This architecture enables:
- **Semantic expense matching** using CockroachDB vector search with cosine similarity
- **Context-aware responses** through retrieval-augmented generation
- **Flexible AI provider switching** without code changes
- **Persistent agent memory** for multi-turn conversations
- **Specialized task handling** through domain-specific agents

## Features

- **Vector Search**: Semantic expense search using CockroachDB C-SPANN vector indexes via [langchain-cockroachdb](https://github.com/cockroachdb/langchain-cockroachdb)
- **Persistent Chat History**: Conversations stored in CockroachDB via `CockroachDBChatMessageHistory`, survive restarts
- **LangGraph Workflows**: Multi-agent receipt pipeline (Receipt → Fraud → Budget) with `CockroachDBSaver` checkpointer
- **Multi-AI Provider**: OpenAI, AWS Bedrock, IBM Watsonx, Google Gemini
- **Dynamic Model Switching**: Change models without restarting
- **User-Specific Indexing**: Optimized vector indexes per user
- **Data Enrichment**: Contextual expense descriptions for better accuracy
- **Multi-Layer Caching**: Query, embedding, and result caching
- **Modern Web Interface**: Responsive UI with real-time chat
- **Analytics Dashboard**: Comprehensive expense analysis
- **PyPI Package**: `pip install banko-ai-assistant`
- **Agentic AI**: Budget planning, fraud detection, receipt processing

## Quick Start

### Installation Options

**Docker** (No Python required)
```bash
docker-compose up -d
```

**PyPI**
```bash
pip install banko-ai-assistant
banko-ai run
```

### Prerequisites

- **Python 3.10+** (if not using Docker)
- **CockroachDB v25.4.0+** (with vector index support)
- **AI Provider API Key** (OpenAI, AWS, IBM Watsonx, or Google Gemini)

### CockroachDB Setup

1. **Download and Install**:
   ```bash
   # Download CockroachDB v25.4.0 or later
   # Visit: https://www.cockroachlabs.com/docs/releases/
   
   # Or via package manager
   brew install cockroachdb/tap/cockroach  # macOS
   ```

2. **Start Single Node**:
   ```bash
   cockroach start-single-node \
     --insecure \
     --store=./cockroach-data \
     --listen-addr=localhost:26257 \
     --http-addr=localhost:8080 \
     --background
   ```

3. **Verify Setup**:
   ```bash
   cockroach sql --insecure --execute "SELECT version();"
   ```

### Installation

#### Docker
```bash
# Pull from Docker Hub
docker pull virag/banko-ai-assistant:latest

# Or use docker-compose
docker-compose up -d
```

#### PyPI
```bash
pip install banko-ai-assistant

# Set up environment variables
export AI_SERVICE="openai"
export OPENAI_API_KEY="your_key_here"
export OPENAI_MODEL="gpt-4o-mini"
export DATABASE_URL="cockroachdb://root@localhost:26257/defaultdb?sslmode=disable"

# Run
banko-ai run
```

#### Development
```bash
git clone https://github.com/cockroachlabs-field/banko-ai-assistant-rag-demo
cd banko-ai-assistant-rag-demo
pip install -e .
banko-ai run
```

## Configuration

### Core Settings (Required)

| Variable       | Description                   | Example                                       |
|----------------|-------------------------------|-----------------------------------------------|
| `DATABASE_URL` | CockroachDB connection string | `cockroachdb://root@localhost:26257/banko_ai` |
| `AI_SERVICE`   | AI provider                   | `watsonx`, `openai`, `aws`, `gemini`          |

### AI Provider Configuration

#### IBM Watsonx
```bash
export WATSONX_API_KEY="your_api_key"
export WATSONX_PROJECT_ID="your_project_id"
export WATSONX_MODEL_ID="meta-llama/llama-2-70b-chat"  # Default: openai/gpt-oss-120b
```

Optional:
| Variable             | Description      | Default           |
|----------------------|------------------|-------------------|
| `WATSONX_API_URL`    | API endpoint URL | US South region   |
| `WATSONX_TOKEN_URL`  | IAM endpoint     | IBM Cloud IAM     |
| `WATSONX_TIMEOUT`    | Timeout (sec)    | `30`              |

#### OpenAI
```bash
export OPENAI_API_KEY="your_key"
export OPENAI_MODEL="gpt-4o-mini"  # Default
```

Options: `gpt-4o-mini`, `gpt-4o`, `gpt-4-turbo`, `gpt-4`, `gpt-3.5-turbo`

#### AWS Bedrock
```bash
export AWS_ACCESS_KEY_ID="your_access_key"
export AWS_SECRET_ACCESS_KEY="your_secret_key"
export AWS_REGION="us-east-1"  # Default
export AWS_MODEL_ID="us.anthropic.claude-3-5-sonnet-20241022-v2:0"  # Default
```

Options: `claude-3-5-sonnet`, `claude-3-5-haiku`, `claude-3-opus`, `claude-3-sonnet`

#### Google Gemini
```bash
export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account.json"
export GOOGLE_PROJECT_ID="your-project-id"
export GOOGLE_MODEL="gemini-1.5-pro"  # Default: gemini-2.0-flash-001
export GOOGLE_LOCATION="us-central1"  # Default
```

Options: `gemini-1.5-pro`, `gemini-1.5-flash`, `gemini-1.0-pro`, `gemini-2.0-flash-001`

Alternative (Generative AI API):
```bash
export GOOGLE_API_KEY="your-gemini-api-key"
```

### Response Caching

Configure caching to balance performance and accuracy:

```bash
export CACHE_SIMILARITY_THRESHOLD="0.75"  # Default (0.0-1.0)
export CACHE_TTL_HOURS="24"               # Default
export CACHE_STRICT_MODE="true"           # Default
```

**Presets:**
- **Demo**: `THRESHOLD=0.75 STRICT_MODE=false` (80-90% hit rate)
- **Balanced**: `THRESHOLD=0.75 STRICT_MODE=true` (60-70% hit rate) ← Recommended
- **Conservative**: `THRESHOLD=0.85 STRICT_MODE=true` (50-60% hit rate)

**Caching Strategy:**
- **High confidence (≥0.90)**: Exact semantic match - use cache
- **Medium confidence (0.70-0.89)**: Similar match - use cache if data matches (strict mode)
- **Low confidence (<0.70)**: Different query - generate fresh response

**Example:**
| Threshold | Query 1           | Query 2              | Similarity | Cache Hit?  |
|-----------|-------------------|----------------------|------------|-------------|
| 0.75      | "coffee"          | "coffee spending"    | 0.69       | ❌ No        |
| 0.75      | "coffee expenses" | "my coffee spending" | 0.88       | ✅ Yes       |
| 0.85      | "coffee expenses" | "my coffee spending" | 0.88       | ✅ Yes       |
| 0.90      | "coffee expenses" | "my coffee spending" | 0.88       | ❌ No        |

### Database Connection Pool

```bash
export DB_POOL_SIZE="100"          # Base pool size
export DB_MAX_OVERFLOW="100"       # Max overflow connections
export DB_POOL_TIMEOUT="30"        # Connection timeout (sec)
export DB_POOL_RECYCLE="3600"      # Recycle after (sec)
export DB_POOL_PRE_PING="true"     # Test before use
export DB_CONNECT_TIMEOUT="10"     # DB connection timeout (sec)
```

**Recommendations:**
- **Low traffic** (<10 QPS): 10-50 connections
- **Medium traffic** (10-100 QPS): 100-500 connections
- **High traffic** (100+ QPS): 500-1000+ connections

### Additional Settings

```bash
export EMBEDDING_MODEL="all-MiniLM-L6-v2"  # Default
export FLASK_ENV="development"             # Options: development, production
export SECRET_KEY="random-secret-key"      # Generate with: python -c "import secrets; print(secrets.token_hex(32))"
```

### Regional Configuration

**Watsonx - EU:**
```bash
export WATSONX_API_URL="https://eu-de.ml.cloud.ibm.com/ml/v1/text/chat?version=2023-05-29"
```

**Watsonx - Tokyo:**
```bash
export WATSONX_API_URL="https://jp-tok.ml.cloud.ibm.com/ml/v1/text/chat?version=2023-05-29"
```

**AWS - Europe:**
```bash
export AWS_REGION="eu-west-1"
```

**Google - Europe:**
```bash
export GOOGLE_LOCATION="europe-west1"
```

### Multi-Region Database

For multi-region deployments, use a load balancer (HAProxy, AWS NLB) in front of CockroachDB:

```bash
# Development (local)
export DATABASE_URL="cockroachdb://root@localhost:26257/banko_ai?sslmode=disable"

# With load balancer
export DATABASE_URL="cockroachdb://root@haproxy-lb:26257/banko_ai?sslmode=verify-full"
```

**Failover Handling:**
1. Application connects to load balancer
2. Load balancer routes to healthy nodes
3. On failure, load balancer detects via health checks
4. Routes to healthy regions automatically
5. Application retry logic handles `StatementCompletionUnknown`
6. Retry succeeds via healthy region

## Running the Application

```bash
# Start with default settings (5000 sample records)
banko-ai run

# Custom data amount
banko-ai run --generate-data 10000

# Without generating data
banko-ai run --no-data

# Debug mode
banko-ai run --debug
```

![Database Operations](https://raw.githubusercontent.com/cockroachlabs-field/banko-ai-assistant-rag-demo/main/banko_ai/static/banko-db-ops.png)

## What Happens on Startup

1. **Database Connection**: Connects to CockroachDB and creates tables
2. **Table Creation**: Creates `expenses` table with vector indexes and cache tables
3. **Data Generation**: Generates 5000 sample expense records with enriched descriptions
4. **AI Provider Setup**: Initializes selected provider and loads available models
5. **Web Server**: Starts Flask application on http://localhost:5000

## Sample Data

Generated data includes:

- **Rich Descriptions**: "Bought food delivery at McDonald's for $56.68 fast significant purchase restaurant and service paid with debit card this month"
- **Merchant Information**: Realistic merchant names and categories
- **Amount Context**: Expense amounts with contextual descriptions
- **Temporal Context**: Recent, this week, this month
- **Payment Methods**: Bank Transfer, Debit Card, Credit Card, Cash, Check
- **Multi-User**: Multiple user IDs for testing user-specific search

![Analytics Dashboard](https://raw.githubusercontent.com/cockroachlabs-field/banko-ai-assistant-rag-demo/main/banko_ai/static/Anallytics.png)

## Web Interface

Access at http://localhost:5000

- **Home**: Overview dashboard with expense statistics
- **Chat**: AI-powered expense analysis and Q&A
- **Search**: Vector-based expense search
- **Settings**: AI provider and model configuration
- **Analytics**: Detailed expense analysis and insights

![Banko Response](https://raw.githubusercontent.com/cockroachlabs-field/banko-ai-assistant-rag-demo/main/banko_ai/static/banko-response.png)

## CLI Commands

```bash
# Run application
banko-ai run [OPTIONS]

# Generate sample data
banko-ai generate-data --count 20000

# Clear all data
banko-ai clear-data

# Check status
banko-ai status

# Search expenses
banko-ai search "food delivery" --limit 10

# Help
banko-ai help
```

## API Endpoints

| Endpoint                          | Method | Description                                         |
|-----------------------------------|--------|-----------------------------------------------------|
| `/`                               | GET    | Web interface                                       |
| `/api/health`                     | GET    | Health check                                        |
| `/api/ai-providers`               | GET    | Available AI providers                              |
| `/api/models`                     | GET    | Available models for current provider               |
| `/api/search`                     | POST   | Vector search expenses (original SQL-based)         |
| `/api/vectorstore-search`         | POST   | Vector search via langchain-cockroachdb VectorStore |
| `/api/rag`                        | POST   | RAG-based Q&A                                       |
| `/api/chat-history/<session_id>`  | GET    | Retrieve persistent chat history for a session      |
| `/api/chat-history/<session_id>`  | DELETE | Clear chat history for a session                    |

### Examples

```bash
# Health check
curl http://localhost:5000/api/health

# Search expenses (original)
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "food delivery", "limit": 5}'

# Search expenses (langchain-cockroachdb vectorstore)
curl -X POST http://localhost:5000/api/vectorstore-search \
  -H "Content-Type: application/json" \
  -d '{"query": "food delivery", "limit": 5}'

# RAG query
curl -X POST http://localhost:5000/api/rag \
  -H "Content-Type: application/json" \
  -d '{"query": "What are my biggest expenses this month?", "limit": 5}'

# Get chat history
curl http://localhost:5000/api/chat-history/my-session-id

# Clear chat history
curl -X DELETE http://localhost:5000/api/chat-history/my-session-id
```

## Database Schema

### Tables

- **expenses**: Expense records with vector embeddings (original SQL-based search)
- **expense_vectors**: LangChain VectorStore table (384-dim vectors, C-SPANN cosine index) via `langchain-cockroachdb`
- **chat_message_store**: Persistent chat history per session via `CockroachDBChatMessageHistory`
- **checkpoint**, **checkpoint_blobs**, **checkpoint_writes**: LangGraph workflow state via `CockroachDBSaver`
- **query_cache**: Cached search results
- **embedding_cache**: Cached embeddings
- **vector_search_cache**: Cached vector search results
- **cache_stats**: Cache performance statistics
- **agent_state**: Agent state management
- **agent_memory**: Agent memory and context
- **agent_tasks**: Agent task queue
- **documents**: Receipt and document storage

### Vector Indexes

The application uses **cosine similarity** (`<=>`) with CockroachDB **C-SPANN** indexes (not IVFFlat):

```sql
-- expense_vectors table (created automatically by langchain-cockroachdb)
CREATE INDEX IF NOT EXISTS idx_cspann_expense_vectors_embedding
ON expense_vectors
USING cspann (embedding vector_cosine_ops);

-- expenses table
CREATE INDEX idx_expenses_embedding
ON expenses
USING cspann (embedding vector_cosine_ops);

-- Agent memory index (multi-tenant prefix)
CREATE INDEX idx_agent_memory_embedding
ON agent_memory
USING cspann (user_id, embedding vector_cosine_ops);

-- Document index
CREATE INDEX idx_documents_embedding
ON documents
USING cspann (user_id, embedding vector_cosine_ops);
```

**Benefits:**
- C-SPANN indexes provide 10-100x faster vector search than full table scans
- Cosine similarity is the industry-standard metric for text embeddings
- Multi-tenant prefix columns enable per-user index scoping
- `langchain-cockroachdb` creates and manages indexes automatically

![Cache Statistics](https://raw.githubusercontent.com/cockroachlabs-field/banko-ai-assistant-rag-demo/main/banko_ai/static/cache-stats.png)

## AI Provider Switching

Switch providers and models dynamically:

1. Go to **Settings** in web interface
2. Select preferred AI provider
3. Choose from available models
4. Changes take effect immediately

### Supported Providers

- **OpenAI**: GPT-4o-mini, GPT-4o, GPT-4 Turbo, GPT-4, GPT-3.5 Turbo
- **AWS Bedrock**: Claude 3.5 Sonnet, Claude 3.5 Haiku, Claude 3 Opus, Claude 3 Sonnet
- **IBM Watsonx**: GPT-OSS-120B, Llama 2 (70B, 13B, 7B), Granite models
- **Google Gemini**: Gemini 1.5 Pro, Gemini 1.5 Flash, Gemini 1.0 Pro, Gemini 2.0 Flash

![AI Status](https://raw.githubusercontent.com/cockroachlabs-field/banko-ai-assistant-rag-demo/main/banko_ai/static/ai-status.png)

## Performance Features

### Caching System

- **Query Caching**: Search results for faster responses
- **Embedding Caching**: Vector embeddings to avoid recomputation
- **Insights Caching**: AI-generated insights
- **Multi-layer Optimization**: Intelligent cache invalidation

### Vector Search Optimization

- **User-Specific Indexes**: Faster search per user
- **Cosine Similarity**: Industry-standard distance metric for text embeddings
- **Data Enrichment**: Enhanced descriptions improve accuracy
- **Batch Processing**: Efficient data loading

## Troubleshooting

### CockroachDB Version
```bash
# Check version (must be v25.4.0+)
cockroach version

# Download latest:
# https://www.cockroachlabs.com/docs/releases/
```

### Database Connection Error
```bash
# Start CockroachDB
cockroach start-single-node \
  --insecure \
  --store=./cockroach-data \
  --listen-addr=localhost:26257 \
  --http-addr=localhost:8080 \
  --background

# Verify
cockroach sql --insecure --execute "SHOW TABLES;"
```

### AI Provider Issues
- Verify API keys are correct
- Check network connectivity
- Ensure selected model is available

### No Search Results
- Load sample data: `banko-ai generate-data --count 1000`
- Verify vector indexes created

### Cache Issues
```bash
# Clear all caches
banko-ai clear-cache

# Check cache statistics
curl http://localhost:5000/api/cache/stats
```

## langchain-cockroachdb Integration

This application uses the official [langchain-cockroachdb](https://github.com/cockroachdb/langchain-cockroachdb) library (v0.2.0+) for deep CockroachDB integration with the LangChain/LangGraph ecosystem.

### Components Used

| Component | Purpose | Table |
|-----------|---------|-------|
| `CockroachDBEngine` | Shared async connection pool (psycopg3) | — |
| `CockroachDBVectorStore` | Semantic search with C-SPANN cosine indexes | `expense_vectors` |
| `CockroachDBChatMessageHistory` | Persistent chat per session/thread | `chat_message_store` |
| `CockroachDBSaver` | LangGraph checkpointer for durable workflows | `checkpoint*` tables |

### Receipt Processing Workflow (LangGraph)

The receipt upload triggers a multi-agent LangGraph workflow persisted by `CockroachDBSaver`:

```
receipt_node → fraud_node → budget_node → END
```

- **receipt_node**: OCR + data extraction via Receipt Agent
- **fraud_node**: Duplicate/suspicious transaction analysis via Fraud Agent
- **budget_node**: Spending impact check via Budget Agent

State is checkpointed after every node, so the workflow survives crashes and can be inspected or replayed.

### Dual Vector Storage

Expenses are indexed into **two** stores for maximum flexibility:

1. **`expenses` table** (original): Raw SQL with hand-crafted queries, used by the existing search engine
2. **`expense_vectors` table** (new): LangChain `CockroachDBVectorStore` with automatic C-SPANN indexing, metadata filtering, and LangChain retriever compatibility

### File Layout

```
banko_ai/
├── utils/
│   ├── crdb_engine.py          # Singleton CockroachDBEngine + URL normalization
│   └── crdb_chat_history.py    # CockroachDBChatMessageHistory wrapper
├── vector_search/
│   └── crdb_vectorstore.py     # CockroachDBVectorStore wrapper + helpers
└── agents/
    └── receipt_workflow.py      # LangGraph StateGraph + CockroachDBSaver
```

## Testing Vector Search

Run the comprehensive test suite to verify vector search is working:

```bash
# Run all tests
python tests/test_vector_index.py

# With pytest
python -m pytest tests/test_vector_index.py -v
```

The test proves:
- Vector indexes are created and used
- Cosine similarity operator works correctly
- Query execution plan shows index usage
- No CAST required (v25.4.0+ compatible)

## License

Apache License 2.0

## Contributing

Contributions welcome! Please open an issue or submit a pull request.

## Support

- **Issues**: https://github.com/cockroachlabs-field/banko-ai-assistant-rag-demo/issues
- **PyPI**: https://pypi.org/project/banko-ai-assistant/
