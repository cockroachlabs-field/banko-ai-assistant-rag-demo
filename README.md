# 🏦 Banko AI Assistant

> **Conversational Banking Assistant** with Retrieval Augmented Generation (RAG), Multi-AI Provider Support, and Real-time Vector Search

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![CockroachDB](https://img.shields.io/badge/database-CockroachDB-purple.svg)](https://www.cockroachlabs.com/)

## 🎬 Live Demo

![Banko AI Assistant Demo](static/banko-ai-assistant-watsonx.gif)
*Experience intelligent banking conversations with voice input, real-time AI responses, and seamless navigation*

> **See Banko AI Assistant in Action** - Key Features & Capabilities

### �� AI Status & Integration
![AI Status Dashboard](static/ai-status.png)
*Real-time AI service status, provider switching, and health monitoring*

### 📊 Cache Performance & Statistics  
![Cache Statistics](static/cache-stats.png)
*Multi-layer caching system with 50-80% token reduction and performance metrics*

### 💬 Intelligent Banking Conversations
![Banko AI Response](static/banko-response.png)
*Natural language processing for expense queries, spending analysis, and financial insights*

### 🔍 Real-time Database Operations
![Database Operations](static/banko-db-ops.png)
*Live query tracing, vector search operations, and database performance monitoring*

### 👀 Query Watcher & Live Monitoring
![Query Watcher](static/query_watcher.png)
*Real-time SQL query visibility, performance tracking, and demo-friendly operation logs*

---
## ✨ Features

### 🚀 **Core AI & Intelligence**
- **🤖 Multi-AI Provider Support**: IBM Watsonx AI & AWS Bedrock with dynamic switching
- **🔍 Vector Search**: Semantic expense search using CockroachDB with pgvector
- **📊 Financial Insights**: Spending analysis, budget recommendations, transaction categorization
- **⚡ Token Optimization**: Multi-layer caching system (50-80% token reduction)

### 🎙️ **Voice & Language**
- **🎤 Voice Assistant**: Speech-to-text input and text-to-speech output with visual toggle
- **🌍 Multi-language Support**: Voice input/output + AI responses in 10+ languages (Hindi, Spanish, French, German, Italian, Portuguese, Japanese, Korean, Chinese)
- **🔴 Smart Voice Toggle**: Red indicator when OFF, green when ON with keyboard shortcut (Ctrl+M)
- **💾 Language Persistence**: Your language selection is remembered across sessions

### 💬 **User Experience**
- **🎯 Interactive Chat**: Real-time conversation with markdown rendering and loading animations
- **⌨️ Keyboard Optimized**: Enter key and Send button both show amazing loading animation
- **♿ Accessibility**: Keyboard shortcuts, screen reader support, voice navigation
- **🏆 Partnership Branding**: Professional header showcasing IBM Watsonx × CockroachDB partnership

### 🔧 **Development & Operations**
- **🛠️ Zero-Config Setup**: Automatic table creation and data generation on startup
- **🎯 Unified Data Generation**: Single, simple expense data generator with dynamic embeddings  
- **🔍 Query Tracing**: Real-time database operation visibility for demos
- **📱 Production Ready**: CockroachDB favicon, responsive design, smooth animations

## 🚀 Quick Start

### Prerequisites
- **Docker/Podman** with docker-compose support
- **Git** for cloning the repository

**For Local Deployment (Optional):**
- **Python 3.11+** with pip
- **CockroachDB** binary installed
- **AI Service API Keys** (Watsonx, AWS Bedrock)
- **Connection String Format**: Use `cockroachdb://` prefix (not `postgresql://`) for CockroachDB connections

```bash
# Install Docker/Podman (choose one)
# Docker:
curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh

# Podman + podman-compose:
brew install podman podman-compose  # macOS
# Then create docker aliases:
sudo ln -sf $(which podman) /usr/local/bin/docker
sudo ln -sf $(which podman-compose) /usr/local/bin/docker-compose
```

### Automated Setup (Recommended)

```bash
# 1. Clone and enter directory
git clone https://github.com/cockroachlabs-field/banko-ai-assistant-rag-demo.git
cd banko-ai-assistant-rag-demo

# 2. Configure API keys
cp config.example.py config.py
# Edit config.py with your API keys

# 3. Start everything (includes automatic data generation)
./start-banko.sh

# 🎉 Access at http://localhost:5000
```

### 🌍 Multi-Language Usage

1. **Change Voice Language**: Click the language dropdown (🇺🇸 EN) in the voice controls
2. **AI Response Language**: AI will automatically respond in your selected language
3. **Supported Languages**: English, Spanish, French, German, Italian, Portuguese, Japanese, Korean, Chinese, Hindi
4. **Persistence**: Your language choice is saved and restored on next visit

**Example:**
- Switch to Hindi (🇮🇳 HI) 
- Type: "hello" 
- Get response: "नमस्ते! मैं बैंको हूँ..."

### Manual Data Generation (Optional)
```bash
# Generate custom amount of data
cd vector_search
python dynamic_expenses.py --records 5000 --clear

# Run interactive demo
python dynamic_expenses.py --demo
```

### Manual Setup (Alternative)

### 🚀 Multi-Deployment Options

#### 🐳 **Option 1: Docker/Podman (Recommended)**
```bash
# Start everything with Docker/Podman
./start-banko.sh

# Check status
./start-banko.sh status

# View logs
./start-banko.sh logs

# Stop services
./start-banko.sh stop
```

#### 💻 **Option 2: Local CockroachDB**
```bash
# Install CockroachDB locally first
# https://www.cockroachlabs.com/docs/stable/install-cockroachdb.html

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# Start local CockroachDB
cockroach start-single-node --insecure --store=./cockroach-data --listen-addr=localhost:26257 --http-addr=localhost:8080 --background

# Enable vector features
cockroach sql --insecure --host=localhost:26257 --execute="SET CLUSTER SETTING feature.vector_index.enabled = true;"

# Setup database and start app
export DATABASE_URL="cockroachdb://root@localhost:26257/defaultdb?sslmode=disable"
# Enable vector indexes in Cockroach Cloud (run this once):
# cockroach sql --url="cockroachdb://user:pass@host:port/db?sslmode=require" --execute="SET CLUSTER SETTING feature.vector_index.enabled = true;"
# Note: Use cockroachdb:// prefix for CockroachDB connections (not postgresql://)
# Cockroach Cloud provides postgresql:// URLs - replace with cockroachdb://
export AI_SERVICE="watsonx"  # or "aws_bedrock"
cd vector_search
python create_table.py
python insert_data.py
cd ..
python app.py
```

#### ☁️ **Option 3: Cockroach Cloud**

**Note:** The scripts now include automatic fallback to handle CockroachDB version compatibility issues with SQLAlchemy. If you encounter connection errors, the scripts will automatically try alternative connection methods.
```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# Setup database and start app
export DATABASE_URL="cockroachdb://user:pass@host:port/db?sslmode=require"  # Replace postgresql:// with cockroachdb:// from Cockroach Cloud
# Enable vector indexes in Cockroach Cloud (run this once):
# cockroach sql --url="cockroachdb://user:pass@host:port/db?sslmode=require" --execute="SET CLUSTER SETTING feature.vector_index.enabled = true;"
# Note: Use cockroachdb:// prefix for CockroachDB connections (not postgresql://)
# Cockroach Cloud provides postgresql:// URLs - replace with cockroachdb://
export AI_SERVICE="watsonx"  # or "aws_bedrock"
cd vector_search
python create_table.py
python insert_data.py
cd ..
python app.py
```

```bash
# Start database only
./start-database.sh

# Run app locally
python3 run-app.py --ai-service watsonx  # or bedrock
```

## ⚙️ Configuration

Create `config.py` from the example:

```python
# IBM Watsonx Configuration
WATSONX_API_KEY = "your_watsonx_api_key_here"
WATSONX_PROJECT_ID = "your_project_id_here"

# AWS Bedrock Configuration (optional)
AWS_ACCESS_KEY = "your_aws_access_key"
AWS_SECRET_KEY = "your_aws_secret_key"
AWS_REGION = "us-east-1"

# AI Service Selection
AI_SERVICE = "watsonx"  # or "bedrock"
```

## 🗄️ Database Setup

CockroachDB starts automatically with Docker. For manual setup:

```bash
# Create tables and load sample data
docker exec banko-app python vector_search/create_table.py
docker exec banko-app python vector_search/insert_data.py
```

## ⚡ Token Optimization & Caching

Intelligent **multi-layer caching** reduces AI token usage by 50-80%:

### Cache Monitoring
```bash
# View cache performance
curl http://localhost:5000/cache-stats

# Check AI service status
curl http://localhost:5000/ai-status

# Manual cache cleanup
curl -X POST http://localhost:5000/cache-cleanup
```

### Cache Architecture
- **Response Cache**: Semantic similarity matching for similar queries
- **Embedding Cache**: Reuses SentenceTransformer embeddings
- **Vector Search Cache**: Caches database query results  
- **Optimized Prompts**: 75% reduction in prompt tokens

## 🔄 Dynamic Embedding Generation

Experience **real-world embedding generation**:

```bash
# Simulate dynamic expense addition with on-the-fly embeddings
docker exec banko-app python vector_search/dynamic_expenses.py

# This demonstrates:
# ✅ Real-time expense addition (like a mobile app)
# ✅ Dynamic search with query-time embedding generation  
# ✅ No pre-computed embeddings required
```

## 🎯 Demo & Usage

### Quick Demo Commands
```bash
# Demo token optimization
python3 demo_token_optimization.py

# Voice commands (when enabled)
"Show me my grocery spending"
"What's my biggest expense category?"
"Help me create a budget"
```

### Voice Features
- **Toggle**: Click the 🎤 button to enable/disable voice features
- **Languages**: English, Spanish, French, German, Italian, Portuguese, Japanese, Korean, Chinese, Hindi
- **Shortcuts**: `Ctrl+Shift+V` (voice input), `Ctrl+Shift+S` (speech output), `Ctrl+Enter` (send)

### Database Query Tracing

The query watcher now supports multiple deployment types with automatic detection:

```bash
# Auto-detect deployment and start monitoring
./scripts/watch-queries.sh

# Force specific deployment type
./scripts/watch-queries.sh --type container    # Docker/Podman
./scripts/watch-queries.sh --type local       # Local CockroachDB binary
./scripts/watch-queries.sh --type cloud       # CockroachDB Cloud

# Advanced options
./scripts/watch-queries.sh --help              # Show all options
./scripts/watch-queries.sh --debug             # Show raw SQL queries
./scripts/watch-queries.sh --sql-only          # Force SQL monitoring
./scripts/watch-queries.sh --type local --logs /path/to/logs  # Try log files
./scripts/watch-queries.sh --type cloud --url "postgresql://user:pass@host:26257/db"

# Legacy method (container logs)
docker logs -f banko-cockroachdb | grep --color=always "SELECT|INSERT|UPDATE"
```

**Deployment Support:**
- **🐳 Container**: Monitors Docker/Podman container logs (real-time)
- **💻 Local Binary**: Uses SQL-based monitoring (recommended) or log files
- **☁️ Cloud**: Uses SQL-based monitoring for CockroachDB Cloud (managed service)

**💡 Note**: For local deployments, SQL-based monitoring is now the default as it's more reliable than log file monitoring, which requires specific CockroachDB logging configuration.

## 🔧 Advanced Usage

### Switch AI Providers
```bash
# Change AI service
export AI_SERVICE=bedrock  # or watsonx
./start-banko.sh restart
```

### Add Custom Expenses Dynamically
```bash
# Use the dynamic expense generator
docker exec -it banko-app python3 -c "
from vector_search.dynamic_expenses import DynamicExpenseGenerator
gen = DynamicExpenseGenerator()
gen.simulate_real_time_expenses(count=5)
"
```

### Development
```bash
# Run without containers
python3 run-app.py --debug --ai-service watsonx

# Database shell
docker exec -it banko-cockroachdb ./cockroach sql --insecure
```

## 🛠️ Troubleshooting

### Common Issues
```bash
# Container conflicts
./start-banko.sh  # Automatically handles cleanup

# Port already in use
./start-banko.sh stop && ./start-banko.sh

# Podman permission issues
sudo chmod +x /usr/local/bin/docker
sudo chmod +x /usr/local/bin/docker-compose
```

### Debug Commands
```bash
# Check service status
./start-banko.sh status

# View logs
docker-compose logs -f banko-app

# Test AI connection
curl http://localhost:5000/ai-status
```

## 📊 Monitoring

### Health Checks
- **App**: http://localhost:5000/ai-status
- **Database**: http://localhost:8080 (CockroachDB Admin UI)
- **Cache Performance**: http://localhost:5000/cache-stats

### Performance Metrics
- Token usage reduction: 50-80%
- Response time: <2s for cached queries
- Vector search: ~100ms for 3000+ records
- Dynamic embeddings: Generated in real-time

## 🏗️ Architecture Highlights

### Real-World Patterns
- **Dynamic Embeddings**: No pre-computed embeddings, generated on-demand
- **Multi-AI Support**: Seamless switching between Watsonx and Bedrock
- **Intelligent Caching**: Multi-layer optimization for production efficiency
- **Vector Search**: CockroachDB with pgvector for semantic similarity
- **Containerized Deployment**: Docker/Podman with automated setup

## 📄 License

This project is licensed under the [MIT License](LICENSE).

## 🔗 Documentation

- **[Demo Guide](docs/DEMO_GUIDE.md)**: Comprehensive demonstration instructions
- **[Token Optimization Report](docs/TOKEN_OPTIMIZATION_REPORT.md)**: Detailed caching implementation
- **[Vector Search Guide](docs/VECTOR_SEARCH_DEMO.md)**: CockroachDB vector operations
- **[API Documentation](docs/API.md)**: REST endpoints and usage
