# 🎯 Banko AI Assistant - Demo Guide

## 🚀 Quick Demo Setup

**Prerequisites**: Docker/Podman with docker-compose installed

### Automated Setup (Recommended)
```bash
# 1. Start everything (database + app)
./start-banko.sh

# 2. Access the demo
# 🏦 Banko AI: http://localhost:5000/banko
# 📈 Database UI: http://localhost:8080

# 3. Configure for demo
# - Click "DB Operations" button (show/hide database activity)
# - Click "Voice: ON" → "Voice: OFF" (optional, for quiet demos)
```

### Manual Setup (Alternative)
```bash
# 1. Start database only
./start-database.sh
python run-app.py --provider watsonx

# 2. Open browser: http://localhost:5000/banko
```

## 🎤 Voice Commands & Text Prompts

### 💰 **Balance & Overview Questions**
```
🗣️ Voice: "What's my current balance?"
💬 Text: "What's my current balance?"
📊 Shows: Total spending, transaction count, financial summary

🗣️ Voice: "Give me an overview of my spending"
💬 Text: "Show me my spending overview"
📊 Shows: Category breakdown, spending patterns, recommendations

🗣️ Voice: "How much have I spent this month?"
💬 Text: "What are my monthly expenses?"
📊 Shows: Total amounts, transaction analysis, budget tips
```

### 🏪 **Category-Based Queries**
```
🗣️ Voice: "How much did I spend on restaurants?"
💬 Text: "Show me my restaurant spending"
📊 Shows: Restaurant transactions, merchant analysis, dining recommendations

🗣️ Voice: "What about grocery shopping?"
💬 Text: "Analyze my grocery expenses"
📊 Shows: Grocery spending, merchant patterns, savings tips

🗣️ Voice: "How much on gas and transportation?"
💬 Text: "Transportation and fuel costs"
📊 Shows: Transportation breakdown, gas stations, travel patterns

🗣️ Voice: "Show me entertainment expenses"
💬 Text: "What did I spend on entertainment?"
📊 Shows: Entertainment analysis, subscription detection, recommendations
```

### 🛍️ **Merchant-Specific Queries**
```
🗣️ Voice: "How much at Starbucks?"
💬 Text: "Show Starbucks transactions"
📊 Shows: Starbucks spending, frequency analysis, alternatives

🗣️ Voice: "Walmart purchases this year"
💬 Text: "All Walmart transactions"
📊 Shows: Walmart spending, category breakdown, patterns

🗣️ Voice: "Amazon shopping analysis"
💬 Text: "How much on Amazon?"
📊 Shows: Amazon spending, purchase patterns, budget impact
```

### 💳 **Payment Method Analysis**
```
🗣️ Voice: "Credit card versus cash spending"
💬 Text: "Compare payment methods"
📊 Shows: Payment method breakdown, spending behavior analysis

🗣️ Voice: "How much on my debit card?"
💬 Text: "Debit card transactions"
📊 Shows: Debit card usage, transaction patterns, insights
```

### 📅 **Time-Based Queries**
```
🗣️ Voice: "Weekly spending patterns"
💬 Text: "Show me weekly expenses"
📊 Shows: Weekly analysis, spending trends, patterns

🗣️ Voice: "Weekend versus weekday spending"
💬 Text: "Compare weekend and weekday expenses"
📊 Shows: Day-of-week analysis, spending behavior insights
```

### 🚨 **Advanced Analysis Prompts**
```
🗣️ Voice: "Find unusual transactions"
💬 Text: "Show me spending anomalies"
📊 Shows: Anomaly detection, unusual transactions, alerts

🗣️ Voice: "Budget recommendations"
💬 Text: "Give me budget advice"
📊 Shows: Personalized recommendations, 50/30/20 rule, savings tips

🗣️ Voice: "Subscription analysis"
💬 Text: "What subscriptions do I have?"
📊 Shows: Recurring payments, subscription analysis, cancellation suggestions
```

## 🔍 Database Tracing - How to Follow the Data Flow

### 🎛️ **Enable Database Visibility**
1. **Click "DB Operations" button** (top-right corner)
2. **Submit any query** - watch the real-time operations
3. **Observe the flow**: Query → Embedding → Vector Search → Analysis → AI Response

### 📊 **Real-Time Operation Tracking**
When you submit a query, you'll see:

```
🕐 10:30:15 📤 Query: Processing: "How much did I spend on restaurants?"
🕐 10:30:16 🔍 Embedding: Generating query embedding using SentenceTransformer
🕐 10:30:17 🗄️ Vector Search: Searching CockroachDB with vector similarity
🕐 10:30:18 📊 Analysis: Analyzing spending patterns and categories
🕐 10:30:19 🤖 AI Processing: Generating personalized response with Watsonx/Bedrock
🕐 10:30:20 ✅ Complete: Response generated successfully
```

### 🗄️ **Database Operations Flow**

#### **Step 1: Query Processing**
```
User Input: "restaurant spending"
↓
SentenceTransformer Model: all-MiniLM-L6-v2
↓
384-dimensional embedding vector
```

#### **Step 2: Vector Search**
```sql
-- CockroachDB Vector Search Query
SELECT 
    description, merchant, shopping_type, expense_amount,
    embedding <=> :search_embedding as similarity_score
FROM expenses
ORDER BY embedding <=> :search_embedding
LIMIT 5
```

#### **Step 3: Transaction Categorization**
```python
# ML-based categorization analysis
- Merchant pattern matching (regex-based)
- Description keyword analysis
- Amount-based heuristics
- Confidence scoring (0.3 to 0.9)
- Anomaly detection
```

#### **Step 4: Financial Insights Generation**
```python
# Analytics computed from search results
- Total amount, transaction count
- Category breakdown (spending by type)
- Top merchants, payment methods
- Average transaction size
- Spending anomalies
```

#### **Step 5: AI Response Generation**
```python
# Enhanced prompt with:
- Original user query
- Search results with financial summary
- Category analysis and recommendations
- Personalized budget tips
- Markdown-formatted response
```

### 🔧 **Manual Database Verification**

#### **Check Database Connection**
```bash
# Verify database is running
./start-database.sh status

# Check API status
curl http://localhost:5000/ai-status
```

#### **Direct Database Query**
```bash
# Connect to CockroachDB
docker exec -it banko-cockroachdb ./cockroach sql --insecure

# Check data
SELECT COUNT(*) FROM expenses;
SELECT shopping_type, COUNT(*) FROM expenses GROUP BY shopping_type;
```

#### **Vector Search Testing**
```bash
# Test vector search directly
python scripts/demo_standalone_search.py

# Interactive mode:
# 1. Database connection testing
# 2. Interactive search mode  
# 3. Predefined demo queries
# 4. Performance metrics
```

### 📈 **Performance Monitoring**

#### **Response Time Breakdown**
- **Embedding Generation**: ~500ms
- **Vector Search**: ~500ms  
- **Transaction Analysis**: ~500ms
- **AI Processing**: ~1000ms
- **Total Response Time**: ~2.5 seconds

#### **Database Metrics**
```sql
-- Check table size
SELECT 
    table_name,
    row_count,
    approximate_disk_size
FROM crdb_internal.table_row_statistics 
WHERE table_name = 'expenses';

-- Vector index usage
EXPLAIN (ANALYZE) 
SELECT * FROM expenses 
ORDER BY embedding <=> '[0.1, 0.2, ...]' 
LIMIT 5;
```

## 🎭 **Demo Script for Presentations**

### **Opening (1 minute)**
1. **Show homepage**: "Welcome to Banko AI Assistant"
2. **Enable DB Operations**: "Let's see what happens behind the scenes"
3. **Optional**: Turn off voice for professional setting

### **Core Demo (3-4 minutes)**
1. **Basic Query**: "What's my spending overview?"
   - Watch database operations in real-time
   - Point out vector search and AI processing
   
2. **Category Analysis**: "How much on restaurants?"
   - Show transaction categorization in action
   - Highlight ML-based merchant recognition
   - Point out budget recommendations
   
3. **Advanced Insights**: "Find unusual transactions"
   - Demonstrate anomaly detection
   - Show personalized recommendations
   - Highlight spending patterns

### **Technical Deep-Dive (2-3 minutes)**
1. **Show Database Operations Panel**: Real-time tracking
2. **Explain Vector Search**: "384-dimensional embeddings"
3. **Highlight AI Features**: "Multi-language, voice, categorization"

### **Voice Demo (1 minute)** - If Enabled
1. **Enable voice**: Click "Voice: OFF" → "Voice: ON"
2. **Voice query**: "How much did I spend on coffee?"
3. **Voice response**: Click speaker button to hear response

## 🔬 **Transaction Categorizer Details**

### **Works with ALL Providers** ✅
- **✅ IBM Watsonx**: Full integration with ML categorization
- **✅ AWS Bedrock**: Full integration with ML categorization  
- **✅ Automatic**: Categorization works regardless of AI provider

### **Categories Detected**
- 🛒 **Grocery**: Walmart, Kroger, Safeway, Whole Foods, etc.
- 🍕 **Restaurants**: McDonald's, Starbucks, Pizza places, etc.
- ⛽ **Gas**: Shell, BP, Exxon, Chevron, etc.
- 🎬 **Entertainment**: Netflix, Spotify, Cinemas, etc.
- 🛍️ **Shopping**: Amazon, eBay, Retail stores, etc.
- 🏥 **Healthcare**: Pharmacies, Hospitals, Medical, etc.
- 💡 **Utilities**: Electric, Water, Internet, Phone, etc.
- 🚗 **Transportation**: Uber, Lyft, Metro, Parking, etc.

### **Smart Features**
- **High Confidence**: Merchant name matching (90% confidence)
- **Medium Confidence**: Description keyword matching (70% confidence)
- **Anomaly Detection**: Transactions 3x above category average
- **Budget Recommendations**: Based on spending patterns
- **Subscription Detection**: Recurring payment identification

**The transaction categorizer provides intelligent financial insights across all AI providers!** 🎯

## 📊 Behind-the-Scenes: Database Query Tracing

For technical demos, you can show the actual SQL queries happening in real-time:

### Query Monitoring Commands

```bash
# Method 1: Built-in startup script command
./start-banko.sh query-logs

# Method 2: Dedicated query watcher (recommended for demos)
./scripts/watch-queries.sh

# Method 3: Manual Docker logs
docker logs -f banko-cockroachdb | grep --color=always "QUERY\|SELECT\|INSERT"
```

### What You'll See During Demo

When users interact with the AI, you'll see:

1. **Vector Similarity Searches**:
   ```sql
   SELECT id, description, amount, merchant, category, embedding <-> $1 AS distance 
   FROM expenses ORDER BY distance LIMIT 10
   ```

2. **Expense Data Queries**:
   ```sql
   SELECT * FROM expenses WHERE category = 'food' AND amount > 50
   ```

3. **Embedding Operations**:
   ```sql
   INSERT INTO expenses (description, amount, merchant, category, embedding) 
   VALUES ($1, $2, $3, $4, $5)
   ```

### Demo Tips for Query Tracing

1. **Split Screen Setup**: Run query watcher in one terminal, demo in browser
2. **Explain Vector Search**: Show how natural language becomes SQL with embeddings
3. **Highlight Performance**: Point out sub-second response times
4. **Show Intelligence**: Demonstrate how AI finds relevant transactions semantically

### Key Query Patterns to Point Out

- **Semantic Search**: `embedding <-> $1` (vector distance calculation)
- **Fast Retrieval**: Index-optimized queries for real-time responses  
- **Complex Analysis**: Aggregations for financial insights
- **Smart Filtering**: Context-aware data retrieval

**Perfect for showing the technical foundation behind the AI magic!** 🔬✨
