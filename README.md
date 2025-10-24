[![PyPI version](https://img.shields.io/pypi/v/banko-ai-assistant)](https://pypi.org/project/banko-ai-assistant/)
[![Python versions](https://img.shields.io/pypi/pyversions/banko-ai-assistant)](https://pypi.org/project/banko-ai-assistant/)
[![License](https://img.shields.io/pypi/l/banko-ai-assistant)](https://pypi.org/project/banko-ai-assistant/)
[![Downloads](https://img.shields.io/pypi/dm/banko-ai-assistant)](https://pypi.org/project/banko-ai-assistant/)

# 🤖 Banko AI Assistant - RAG Demo

A modern AI-powered expense analysis application with Retrieval-Augmented Generation (RAG) capabilities, built with CockroachDB vector search and multiple AI provider support.

![Banko AI Assistant](https://raw.githubusercontent.com/cockroachlabs-field/banko-ai-assistant-rag-demo/main/banko_ai/static/banko-ai-assistant-watsonx.gif)

## ✨ Features

- **🔍 Advanced Vector Search**: Enhanced expense search using CockroachDB vector indexes
- **🤖 Multi-AI Provider Support**: OpenAI, AWS Bedrock, IBM Watsonx, Google Gemini
- **🔄 Dynamic Model Switching**: Switch between models without restarting the app
- **👤 User-Specific Indexing**: User-based vector indexes with regional partitioning
- **📊 Data Enrichment**: Contextual expense descriptions for better search accuracy
- **💾 Intelligent Caching**: Multi-layer caching system for optimal performance
- **🌐 Modern Web Interface**: Clean, responsive UI with real-time chat
- **📈 Analytics Dashboard**: Comprehensive expense analysis and insights
- **📦 PyPI Package**: Easy installation with `pip install banko-ai-assistant`
- **🎯 Enhanced Context**: Merchant and amount information included in search context
- **⚡ Performance Optimized**: User-specific vector indexes for faster queries

## 🚀 Quick Start

### Prerequisites

- **Python 3.8+**
- **CockroachDB v25.2.4+** (recommended: [v25.3.3](https://www.cockroachlabs.com/docs/releases/v25.3#v25-3-3))
- **Vector Index Feature Enabled** (required for vector search)
- **AI Provider API Key** (OpenAI, AWS, IBM Watsonx, or Google Gemini)

#### CockroachDB Setup

1. **Download and Install CockroachDB**:
   ```bash
   # Download CockroachDB v25.3.3 (recommended)
   # Visit: https://www.cockroachlabs.com/docs/releases/v25.3#v25-3-3
   
   # Or install via package manager
   brew install cockroachdb/tap/cockroach  # macOS
   ```

2. **Start CockroachDB Single Node**:
   ```bash
   # Start a single-node cluster (for development)
   cockroach start-single-node \
     --insecure \
     --store=./cockroach-data \
     --listen-addr=localhost:26257 \
     --http-addr=localhost:8080 \
     --background
   ```

3. **Enable Vector Index Feature**:
   ```sql
   -- Connect to the database
   cockroach sql --url="cockroachdb://root@localhost:26257/defaultdb?sslmode=disable"
   
   -- Enable vector index feature (required for vector search)
   SET CLUSTER SETTING feature.vector_index.enabled = true;
   ```

4. **Verify Setup**:
   ```sql
   -- Check if vector index is enabled
   SHOW CLUSTER SETTING feature.vector_index.enabled;
   -- Should return: true
   ```

### Installation

#### Option 1: PyPI Installation (Recommended)
```bash
# Install from PyPI
pip install banko-ai-assistant

# Set up environment variables (example with OpenAI)
export AI_SERVICE="openai"
export OPENAI_API_KEY="your_openai_api_key_here"
export OPENAI_MODEL="gpt-4o-mini"
export DATABASE_URL="cockroachdb://root@localhost:26257/defaultdb?sslmode=disable"

# Run the application
banko-ai run
```

#### Option 2: Development Installation
```bash
# Clone the repository
git clone https://github.com/cockroachlabs-field/banko-ai-assistant-rag-demo
cd banko-ai-assistant-rag-demo

# Install the package in development mode
pip install -e .

# Run the application
banko-ai run
```

#### Option 3: Direct Dependencies
```bash
# Install dependencies from pyproject.toml
pip install -e .

# Run the application
banko-ai run
```

### Configuration

Set up your environment variables:

```bash
# Required: Database connection
export DATABASE_URL="cockroachdb://root@localhost:26257/defaultdb?sslmode=disable"

# Required: AI Service (choose one)
export AI_SERVICE="watsonx"  # or "openai", "aws", "gemini"

# AI Provider Configuration (choose based on AI_SERVICE)
# For IBM Watsonx:
export WATSONX_API_KEY="your_api_key_here"
export WATSONX_PROJECT_ID="your_project_id_here"
export WATSONX_MODEL="meta-llama/llama-2-70b-chat"

# For OpenAI:
export OPENAI_API_KEY="your_api_key_here"
export OPENAI_MODEL="gpt-4o-mini"  # Options: gpt-4o-mini (default), gpt-4o, gpt-4-turbo, gpt-3.5-turbo

# For AWS Bedrock:
export AWS_ACCESS_KEY_ID="your_access_key"
export AWS_SECRET_ACCESS_KEY="your_secret_key"
export AWS_REGION="us-east-1"
export AWS_MODEL="us.anthropic.claude-3-5-sonnet-20241022-v2:0"  # Claude 3.5 Sonnet (default)

# For Google Gemini:
export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account.json"
export GOOGLE_MODEL="gemini-1.5-pro"
```

### Running the Application

The application automatically creates database tables and loads sample data (5000 records by default):

```bash
# Start with default settings (5000 sample records)
banko-ai run

# Start with custom data amount
banko-ai run --generate-data 10000

# Start without generating data
banko-ai run --no-data

# Start with debug mode
banko-ai run --debug
```

![Database Operations](https://raw.githubusercontent.com/cockroachlabs-field/banko-ai-assistant-rag-demo/main/banko_ai/static/banko-db-ops.png)

## 🎯 What Happens on Startup

1. **Database Connection**: Connects to CockroachDB and creates necessary tables
2. **Table Creation**: Creates `expenses` table with vector indexes and cache tables
3. **Data Generation**: Automatically generates 5000 sample expense records with enriched descriptions
4. **AI Provider Setup**: Initializes the selected AI provider and loads available models
5. **Web Server**: Starts the Flask application on http://localhost:5000

## 📊 Sample Data Features

The generated sample data includes:

- **Rich Descriptions**: "Bought food delivery at McDonald's for $56.68 fast significant purchase restaurant and service paid with debit card this month"
- **Merchant Information**: Realistic merchant names and categories
- **Amount Context**: Expense amounts with contextual descriptions
- **Temporal Context**: Recent, this week, this month, etc.
- **Payment Methods**: Bank Transfer, Debit Card, Credit Card, Cash, Check
- **User-Specific Data**: Multiple user IDs for testing user-specific search

![Analytics Dashboard](https://raw.githubusercontent.com/cockroachlabs-field/banko-ai-assistant-rag-demo/main/banko_ai/static/Anallytics.png)

## 🌐 Web Interface

Access the application at http://localhost:5000

### Main Features

- **🏠 Home**: Overview dashboard with expense statistics
- **💬 Chat**: AI-powered expense analysis and Q&A
- **🔍 Search**: Vector-based expense search
- **⚙️ Settings**: AI provider and model configuration
- **📊 Analytics**: Detailed expense analysis and insights

![Banko Response](https://raw.githubusercontent.com/cockroachlabs-field/banko-ai-assistant-rag-demo/main/banko_ai/static/banko-response.png)

## 🔧 CLI Commands

```bash
# Run the application
banko-ai run [OPTIONS]

# Generate sample data
banko-ai generate-data --count 2000

# Clear all data
banko-ai clear-data

# Check application status
banko-ai status

# Search expenses
banko-ai search "food delivery" --limit 10

# Show help
banko-ai help
```

## 🔌 API Endpoints

| Endpoint            | Method | Description                           |
|---------------------|--------|---------------------------------------|
| `/`                 | GET    | Web interface                         |
| `/api/health`       | GET    | System health check                   |
| `/api/ai-providers` | GET    | Available AI providers                |
| `/api/models`       | GET    | Available models for current provider |
| `/api/search`       | POST   | Vector search expenses                |
| `/api/rag`          | POST   | RAG-based Q&A                         |

### API Examples

```bash
# Health check
curl http://localhost:5000/api/health

# Search expenses
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "food delivery", "limit": 5}'

# RAG query
curl -X POST http://localhost:5000/api/rag \
  -H "Content-Type: application/json" \
  -d '{"query": "What are my biggest expenses this month?", "limit": 5}'
```

## 🏗️ Architecture

### Database Schema

- **expenses**: Main expense table with vector embeddings
- **query_cache**: Cached search results
- **embedding_cache**: Cached embeddings
- **insights_cache**: Cached AI insights
- **vector_search_cache**: Cached vector search results
- **cache_stats**: Cache performance statistics

### Vector Indexes

```sql
-- User-specific vector index for personalized search
CREATE INDEX idx_expenses_user_embedding ON expenses 
USING cspann (user_id, embedding vector_l2_ops);

-- General vector index for global search
CREATE INDEX idx_expenses_embedding ON expenses 
USING cspann (embedding vector_l2_ops);

-- Note: Regional partitioning syntax may vary by CockroachDB version
-- CREATE INDEX idx_expenses_regional ON expenses 
-- USING cspann (user_id, embedding vector_l2_ops) 
-- LOCALITY REGIONAL BY ROW AS region;
```

**Benefits:**
- **User-specific queries**: Faster search within user's data
- **Contextual results**: Enhanced merchant and amount information
- **Scalable performance**: Optimized for large datasets
- **Multi-tenant support**: Isolated user data with shared infrastructure

![Cache Statistics](https://raw.githubusercontent.com/cockroachlabs-field/banko-ai-assistant-rag-demo/main/banko_ai/static/cache-stats.png)

## 🔄 AI Provider Switching

Switch between AI providers and models dynamically:

1. Go to **Settings** in the web interface
2. Select your preferred AI provider
3. Choose from available models
4. Changes take effect immediately

### Supported Providers

- **OpenAI**: GPT-4o-mini (default), GPT-4o, GPT-4 Turbo, GPT-4, GPT-3.5 Turbo
- **AWS Bedrock**: Claude 3.5 Sonnet (default), Claude 3.5 Haiku, Claude 3 Opus, Claude 3 Sonnet
- **IBM Watsonx**: GPT-OSS-120B (default), Llama 2 (70B, 13B, 7B), Granite models
- **Google Gemini**: Gemini 1.5 Pro (default), Gemini 1.5 Flash, Gemini 1.0 Pro

![AI Status](https://raw.githubusercontent.com/cockroachlabs-field/banko-ai-assistant-rag-demo/main/banko_ai/static/ai-status.png)

## 📈 Performance Features

### Caching System

- **Query Caching**: Caches search results for faster responses
- **Embedding Caching**: Caches vector embeddings to avoid recomputation
- **Insights Caching**: Caches AI-generated insights
- **Multi-layer Optimization**: Intelligent cache invalidation and refresh

### Vector Search Optimization

- **User-Specific Indexes**: Faster search for individual users
- **Regional Partitioning**: Optimized for multi-region deployments
- **Data Enrichment**: Enhanced descriptions improve search accuracy
- **Batch Processing**: Efficient data loading and processing

![Query Watcher](https://raw.githubusercontent.com/cockroachlabs-field/banko-ai-assistant-rag-demo/main/banko_ai/static/query_watcher.png)

## 🛠️ Development

### Project Structure

```
banko_ai/
├── ai_providers/          # AI provider implementations
├── config/               # Configuration management
├── static/               # Web assets and images
├── templates/            # HTML templates
├── utils/                # Database and cache utilities
├── vector_search/        # Vector search and data generation
└── web/                  # Flask web application
```

### Adding New AI Providers

1. Create a new provider class in `ai_providers/`
2. Extend the `BaseAIProvider` class
3. Implement required methods
4. Add to the factory in `ai_providers/factory.py`

## 🐛 Troubleshooting

### Common Issues

**CockroachDB Version Issues**
```bash
# Check CockroachDB version (must be v25.2.4+)
cockroach version

# If version is too old, download v25.3.3:
# https://www.cockroachlabs.com/docs/releases/v25.3#v25-3-3
```

**Vector Index Feature Not Enabled**
```bash
# Connect to database and enable vector index feature
cockroach sql --url="cockroachdb://root@localhost:26257/defaultdb?sslmode=disable"

# Enable vector index feature
SET CLUSTER SETTING feature.vector_index.enabled = true;

# Verify it's enabled
SHOW CLUSTER SETTING feature.vector_index.enabled;
```

**Database Connection Error**
```bash
# Start CockroachDB single node
cockroach start-single-node \
  --insecure \
  --store=./cockroach-data \
  --listen-addr=localhost:26257 \
  --http-addr=localhost:8080 \
  --background

# Verify database exists
cockroach sql --url="cockroachdb://root@localhost:26257/defaultdb?sslmode=disable" --execute "SHOW TABLES;"
```

**AI Provider Disconnected**
- Verify API keys are set correctly
- Check network connectivity
- Ensure the selected model is available

**No Search Results**
- Ensure sample data is loaded: `banko-ai generate-data --count 1000`
- Check vector indexes are created
- Verify search query format

### Debug Mode

```bash
# Run with debug logging
banko-ai run --debug

# Check application status
banko-ai status
```

---

**Built with ❤️ using CockroachDB, Flask, and modern AI technologies such as watsonx.ai**