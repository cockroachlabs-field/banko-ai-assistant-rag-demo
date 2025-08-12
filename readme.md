# 🏦 Banko AI Assistant

> **Conversational Banking Assistant** with Retrieval Augmented Generation (RAG), Multi-AI Provider Support, and Real-time Vector Search

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![CockroachDB](https://img.shields.io/badge/database-CockroachDB-purple.svg)](https://www.cockroachlabs.com/)

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

- **🤖 Multi-AI Provider Support**: IBM Watsonx AI & AWS Bedrock with dynamic switching
- **🔍 Vector Search**: Semantic expense search using CockroachDB with pgvector
- **🎙️ Voice Assistant**: Speech-to-text input and text-to-speech output (toggleable)
- **💬 Interactive Chat**: Real-time conversation with markdown rendering
- **📊 Financial Insights**: Spending analysis, budget recommendations, transaction categorization
- **🌍 Multi-language Support**: Voice input/output in 10+ languages
- **⚡ Token Optimization**: Multi-layer caching system (50-80% token reduction)
- **♿ Accessibility**: Keyboard shortcuts, screen reader support, voice navigation
- **🔍 Query Tracing**: Real-time database operation visibility for demos
- **🔄 Dynamic Embeddings**: Real-world embedding generation on-the-fly

## 🚀 Quick Start

### Prerequisites
- **Docker/Podman** with docker-compose support
- **Git** for cloning the repository

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

# 3. Start everything
./start-banko.sh

# 🎉 Access at http://localhost:5000
```

### Manual Setup (Alternative)

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
```bash
# Watch live SQL queries during demos
./scripts/watch-queries.sh

# Or view raw logs
docker logs -f banko-cockroachdb | grep --color=always "SELECT|INSERT|UPDATE"
```

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

---

**🎉 Ready to revolutionize your financial conversations?**

Get started in under 5 minutes with our automated setup! 🚀

## �� What's New

- ✅ **Dynamic Embedding Generation**: Real-world approach with on-the-fly embedding creation
- ✅ **Consolidated Documentation**: Streamlined docs structure with focused guides
- ✅ **Token Optimization**: Multi-layer caching for 50-80% cost reduction
- ✅ **Enhanced Voice Interface**: Multi-language support with toggleable features
