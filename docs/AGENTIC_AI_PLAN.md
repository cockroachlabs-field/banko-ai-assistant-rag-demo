# 🤖 Agentic AI Multi-Region Demo - Implementation Plan

## Branch: `agentic-ai`

## Vision: The Ultimate re:Invent Demo

A **multi-agent system** deployed across **3 AWS regions** with **CockroachDB as unified memory**, demonstrating:
- 🧠 **THINK**: Multi-agent orchestration with visible reasoning
- 💾 **REMEMBER**: Distributed memory that survives region failures
- ⚡ **ACT**: Autonomous agents taking real-time actions

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR AGENT (US-EAST-1)               │
│  Coordinates agent team, plans workflows, delegates tasks       │
└────────────────────┬────────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┬────────────────────┐
        │                         │                     │
┌───────▼──────────┐   ┌─────────▼──────────┐   ┌─────▼────────────┐
│ US-EAST-1        │   │ US-WEST-2          │   │ US-CENTRAL-1     │
│ - Receipt Agent  │   │ - Fraud Agent      │   │ - Budget Agent   │
│ - Analyst Agent  │   │ - Learning Agent   │   │ - Report Agent   │
└───────┬──────────┘   └─────────┬──────────┘   └─────┬────────────┘
        │                         │                     │
        └─────────────┬───────────┴─────────────────────┘
                      │
┌─────────────────────▼─────────────────────────────────────────────┐
│              CockroachDB Multi-Region (5 nodes)                   │
│  - Agent coordination state                                       │
│  - Distributed agent memory (vector + transactional)              │
│  - Task queues                                                    │
│  - Cross-agent communication                                      │
│  - Session history                                                │
└───────────────────────────────────────────────────────────────────┘
```

## Integration with cockroach-chaos-demo

Your existing chaos demo provides:
- ✅ **5-node CockroachDB cluster** (3 regions)
- ✅ **HAProxy load balancer** (port 26257)
- ✅ **Toxiproxy** for network chaos
- ✅ **Docker orchestration**
- ✅ **Chaos control panel** (localhost:8088)
- ✅ **Vector index enabled**

We'll add:
- 🆕 **3 Agent worker containers** (one per region)
- 🆕 **Agent dashboard** (real-time agent activity)
- 🆕 **WebSocket server** (agent communication)
- 🆕 **S3/MinIO** for document uploads
- 🆕 **Background task scheduler**

## Component Breakdown

### 1. Agent Framework (Core)

**File Structure:**
```
banko_ai/
├── agents/
│   ├── __init__.py
│   ├── base_agent.py              # Base agent class
│   ├── orchestrator.py            # Orchestrator agent
│   ├── receipt_agent.py           # Document processing
│   ├── fraud_agent.py             # Fraud detection (autonomous)
│   ├── budget_agent.py            # Budget monitoring (proactive)
│   ├── analyst_agent.py           # Data analysis
│   ├── learning_agent.py          # System improvement
│   ├── report_agent.py            # Report generation
│   └── tools/
│       ├── __init__.py
│       ├── search_tools.py        # Vector & SQL search
│       ├── analysis_tools.py      # Statistics & patterns
│       ├── notification_tools.py  # Alerts & escalation
│       └── document_tools.py      # OCR & extraction
├── memory/
│   ├── __init__.py
│   ├── agent_memory.py            # Agent memory manager
│   ├── conversation_store.py     # Cross-session memory
│   └── coordination.py            # Agent coordination
└── workers/
    ├── __init__.py
    ├── autonomous_worker.py       # Background agent worker
    └── task_queue.py              # Distributed task queue
```

**Tech Stack:**
- **LangGraph**: Agent orchestration & workflows
- **LangChain**: Multi-provider LLM abstraction
- **Sentence Transformers**: Vector embeddings
- **Celery** (optional): Background task queue
- **WebSocket**: Real-time agent communication

### 2. Database Schema Extensions

```sql
-- Agent coordination and state
CREATE TABLE agent_state (
    agent_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_type STRING NOT NULL,        -- 'receipt', 'fraud', 'budget', etc.
    region STRING NOT NULL,            -- 'us-east-1', 'us-west-2', etc.
    status STRING NOT NULL,            -- 'idle', 'thinking', 'acting', 'blocked'
    current_task JSONB,
    last_heartbeat TIMESTAMP DEFAULT now(),
    metadata JSONB,
    INDEX (region, status)
);

-- Agent memory (vector + metadata)
CREATE TABLE agent_memory (
    memory_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID REFERENCES agent_state(agent_id),
    user_id STRING,
    memory_type STRING NOT NULL,       -- 'conversation', 'decision', 'pattern', 'preference'
    content TEXT NOT NULL,
    embedding VECTOR(384),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT now(),
    accessed_at TIMESTAMP DEFAULT now(),
    access_count INT DEFAULT 0
);

CREATE INDEX ON agent_memory USING cspann (user_id, embedding vector_l2_ops);
CREATE INDEX ON agent_memory (agent_id, memory_type, created_at DESC);

-- Cross-agent communication & task queue
CREATE TABLE agent_tasks (
    task_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_agent_id UUID,
    target_agent_id UUID,
    task_type STRING NOT NULL,         -- 'analyze', 'process', 'report', 'escalate'
    priority INT DEFAULT 5,
    payload JSONB,
    status STRING DEFAULT 'pending',   -- 'pending', 'processing', 'completed', 'failed'
    region STRING,                     -- Target region for locality
    created_at TIMESTAMP DEFAULT now(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    result JSONB,
    INDEX (status, priority DESC, created_at),
    INDEX (target_agent_id, status)
);

-- Agent decisions & audit log (for learning)
CREATE TABLE agent_decisions (
    decision_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID REFERENCES agent_state(agent_id),
    decision_type STRING NOT NULL,     -- 'fraud_flag', 'budget_alert', 'escalation'
    context JSONB NOT NULL,            -- Input data
    reasoning TEXT,                    -- Agent's thinking process
    action JSONB,                      -- What action was taken
    confidence FLOAT,                  -- 0.0 to 1.0
    user_feedback STRING,              -- 'correct', 'incorrect', null
    created_at TIMESTAMP DEFAULT now(),
    INDEX (agent_id, decision_type, created_at DESC),
    INDEX (user_feedback, created_at DESC)
);

-- Conversation history (cross-session)
CREATE TABLE conversations (
    conversation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id STRING NOT NULL,
    session_id STRING,
    message_role STRING NOT NULL,      -- 'user', 'assistant', 'system'
    message_content TEXT NOT NULL,
    message_embedding VECTOR(384),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT now(),
    INDEX (user_id, created_at DESC)
);

CREATE INDEX ON conversations USING cspann (user_id, message_embedding vector_l2_ops);

-- Documents & receipts
CREATE TABLE documents (
    document_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id STRING NOT NULL,
    document_type STRING NOT NULL,     -- 'receipt', 'invoice', 'report'
    s3_key STRING NOT NULL,
    original_filename STRING,
    extracted_text TEXT,
    extracted_data JSONB,              -- Structured fields
    embedding VECTOR(384),
    processing_status STRING DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    processed_by_agent_id UUID,
    created_at TIMESTAMP DEFAULT now(),
    processed_at TIMESTAMP,
    INDEX (user_id, document_type, created_at DESC)
);
```

### 3. Agent Types & Responsibilities

#### **Orchestrator Agent** (Region: US-EAST-1)
- **Role**: Team coordinator, workflow planner
- **Tools**: 
  - `delegate_task(agent, task)` - Assign work
  - `check_agent_status(agent_id)` - Monitor team
  - `synthesize_results(results)` - Combine outputs
- **Example**: User asks "Audit my expenses" → Plans multi-step workflow → Delegates to specialists

#### **Receipt Agent** (Region: US-EAST-1)
- **Role**: Document processing specialist
- **Tools**:
  - `extract_text(image)` - OCR with Tesseract
  - `parse_receipt(text)` - Extract fields with LLM
  - `store_document(data)` - Save to CockroachDB
  - `match_existing_expense(data)` - Dedupe check
- **Autonomous**: Monitors S3 bucket, processes new uploads
- **Demo**: Upload receipt → See agent extract data → Store in DB

#### **Fraud Agent** (Region: US-WEST-2)
- **Role**: 24/7 fraud detection
- **Tools**:
  - `search_similar_expenses(expense)` - Vector search
  - `calculate_fraud_score(expense)` - ML analysis
  - `check_blacklist(merchant)` - Transactional lookup
  - `escalate_to_human(decision)` - Alert system
- **Autonomous**: Runs every 30s, scans new expenses
- **Demo**: Insert duplicate expense → Agent auto-flags → Explains reasoning

#### **Budget Agent** (Region: US-CENTRAL-1)
- **Role**: Proactive budget monitoring
- **Tools**:
  - `forecast_spending(user_id)` - Trend analysis
  - `check_budget_limits(user_id)` - Compare vs limits
  - `generate_recommendations(data)` - Suggestions
  - `send_alert(user, message)` - Notifications
- **Autonomous**: Monitors spending patterns
- **Demo**: Approach budget limit → Agent sends proactive alert

#### **Analyst Agent** (Region: US-EAST-1)
- **Role**: Data analysis & insights
- **Tools**:
  - `calculate_statistics(query)` - SQL aggregations
  - `find_patterns(expenses)` - Vector clustering
  - `compare_periods(dates)` - Time-series analysis
  - `generate_insights(data)` - Narrative summaries
- **Demo**: "What are my spending trends?" → Agent analyzes → Reports findings

#### **Learning Agent** (Region: US-WEST-2)
- **Role**: System improvement from feedback
- **Tools**:
  - `record_feedback(decision, feedback)` - Store corrections
  - `update_patterns(pattern_id, data)` - Refine models
  - `share_learning(agents)` - Broadcast improvements
- **Demo**: Correct fraud flag → Agent learns → All agents updated

#### **Report Agent** (Region: US-CENTRAL-1)
- **Role**: Generate formatted reports
- **Tools**:
  - `fetch_data(query)` - Gather information
  - `format_report(data, template)` - PDF/HTML generation
  - `store_report(report)` - Save for later
- **Demo**: "Generate expense report" → Agent creates PDF

### 4. Docker Deployment Integration

**Update chaos demo docker-compose.yml:**

```yaml
services:
  # ... existing CockroachDB, HAProxy, Toxiproxy services ...

  # MinIO (S3-compatible storage) for documents
  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    ports:
      - "9000:9000"  # API
      - "9001:9001"  # Console
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - minio-data:/data
    networks:
      - crdb-net

  # Agent Worker - US-EAST-1
  agent-worker-east:
    build:
      context: ../banko-ai-assistant-rag-demo
      dockerfile: Dockerfile.agent
    container_name: agent-worker-east
    environment:
      - DATABASE_URL=postgresql://root@haproxy:26257/defaultdb?sslmode=disable
      - AGENT_REGION=us-east-1
      - AGENT_TYPES=orchestrator,receipt,analyst
      - AI_SERVICE=${AI_SERVICE:-openai}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - MINIO_ENDPOINT=minio:9000
    depends_on:
      - haproxy
      - minio
    networks:
      - crdb-net
    restart: unless-stopped

  # Agent Worker - US-WEST-2
  agent-worker-west:
    build:
      context: ../banko-ai-assistant-rag-demo
      dockerfile: Dockerfile.agent
    container_name: agent-worker-west
    environment:
      - DATABASE_URL=postgresql://root@haproxy:26257/defaultdb?sslmode=disable
      - AGENT_REGION=us-west-2
      - AGENT_TYPES=fraud,learning
      - AI_SERVICE=${AI_SERVICE:-openai}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      - haproxy
    networks:
      - crdb-net
    restart: unless-stopped

  # Agent Worker - US-CENTRAL-1
  agent-worker-central:
    build:
      context: ../banko-ai-assistant-rag-demo
      dockerfile: Dockerfile.agent
    container_name: agent-worker-central
    environment:
      - DATABASE_URL=postgresql://root@haproxy:26257/defaultdb?sslmode=disable
      - AGENT_REGION=us-central-1
      - AGENT_TYPES=budget,report
      - AI_SERVICE=${AI_SERVICE:-openai}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      - haproxy
    networks:
      - crdb-net
    restart: unless-stopped

  # Banko AI Web App (with agent dashboard)
  banko-ai:
    build:
      context: ../banko-ai-assistant-rag-demo
      dockerfile: Dockerfile
    container_name: banko-ai-web
    ports:
      - "5000:5000"
    environment:
      - DATABASE_URL=postgresql://root@haproxy:26257/defaultdb?sslmode=disable
      - AI_SERVICE=${AI_SERVICE:-openai}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - MINIO_ENDPOINT=minio:9000
      - ENABLE_AGENTS=true
    depends_on:
      - haproxy
      - minio
      - agent-worker-east
      - agent-worker-west
      - agent-worker-central
    networks:
      - crdb-net
    restart: unless-stopped

volumes:
  minio-data:

networks:
  crdb-net:
    external: true
```

### 5. UI Components

#### **Agent Dashboard** (New Tab)
```
┌─────────────────────────────────────────────────────┐
│  Agents | Chat | Analytics | Settings               │
├─────────────────────────────────────────────────────┤
│                                                     │
│  🌍 AGENT ACTIVITY MAP                              │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐      │
│  │ US-EAST-1 │  │ US-WEST-2 │  │US-CENTRAL │      │
│  │ 🟢 Active │  │ 🟢 Active │  │ 🟢 Active │      │
│  │           │  │           │  │           │      │
│  │Receipt🤖  │  │Fraud 🤖   │  │Budget🤖   │      │
│  │ THINKING  │  │  ACTING   │  │  IDLE     │      │
│  │           │  │           │  │           │      │
│  │Analyst🤖  │  │Learning🤖 │  │Report🤖   │      │
│  │  IDLE     │  │  IDLE     │  │  IDLE     │      │
│  └───────────┘  └───────────┘  └───────────┘      │
│                                                     │
│  📊 LIVE AGENT ACTIVITY                             │
│  ┌─────────────────────────────────────────────┐   │
│  │ 🤖 Fraud Agent (us-west-2)                  │   │
│  │ ├─ 🧠 THINKING: Analyzing expense pattern   │   │
│  │ ├─ 🔍 TOOL: search_similar_expenses()       │   │
│  │ ├─ 💾 MEMORY: Retrieved 3 past fraud cases  │   │
│  │ └─ ⚡ DECISION: Fraud score 87% - Escalating│   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  🎯 RECENT DECISIONS                                │
│  - Fraud Agent flagged duplicate $250 charge       │
│  - Budget Agent sent overspend alert to User #42   │
│  - Learning Agent updated fraud patterns from      │
│    user feedback                                    │
│                                                     │
│  📈 SYSTEM STATS                                    │
│  - Agents active: 6/6                              │
│  - Tasks completed today: 1,247                    │
│  - Average response time: 1.2s                     │
│  - Memory size: 45,892 entries                     │
└─────────────────────────────────────────────────────┘
```

#### **Enhanced Chat Interface**
```
User: "Audit my last quarter's expenses"

┌─────────────────────────────────────────────────────┐
│ 🤖 Orchestrator Agent                              │
│ I'll coordinate the team to handle this request.   │
│                                                     │
│ 📋 PLAN:                                            │
│ 1. Retrieve Q4 expenses (Analyst Agent)            │
│ 2. Check for fraud patterns (Fraud Agent)          │
│ 3. Analyze spending trends (Analyst Agent)         │
│ 4. Generate audit report (Report Agent)            │
│                                                     │
│ [▶️ Executing workflow...]                          │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ 📊 Analyst Agent (us-east-1)                       │
│ Retrieved 247 expenses totaling $8,450             │
│ [✓ Task completed in 0.8s]                         │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ 🚨 Fraud Agent (us-west-2)                         │
│ Found 2 suspicious patterns:                       │
│ - Duplicate charge: $250 on 11/15                  │
│ - Unusual merchant: High-risk category             │
│ [⚠️ Confidence: 87% - Needs review]                │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ 📝 Report Agent (us-central-1)                     │
│ Generated comprehensive audit report               │
│ [📄 Download Report] [📧 Email Report]             │
└─────────────────────────────────────────────────────┘
```

### 6. Demo Scenarios

#### **Scenario 1: Document Upload & Processing** (2 min)
```
1. Upload receipt image to web interface
2. Show Receipt Agent (us-east-1) immediately starts processing
3. Agent dashboard shows: "THINKING → ACTING"
4. OCR extraction → Field parsing → Store in DB
5. Agent matches with existing expense (deduplication)
6. Show final result in expenses table
```

#### **Scenario 2: Autonomous Fraud Detection** (2 min)
```
1. Insert duplicate expense via SQL (simulate user entry)
2. Fraud Agent (us-west-2) auto-detects within 30 seconds
3. Dashboard shows: Agent reasoning process
4. Agent searches similar cases (vector search)
5. Escalates to user with confidence score
6. User provides feedback → Learning Agent updates patterns
```

#### **Scenario 3: Multi-Agent Collaboration** (3 min)
```
1. User: "Audit my expenses and check my budget"
2. Orchestrator plans workflow
3. Dashboard shows agents coordinating:
   - Analyst retrieves data
   - Fraud checks for issues
   - Budget checks limits
   - Report generates summary
4. All agents work in parallel across regions
5. Results synthesized and presented
```

#### **Scenario 4: Region Failure & Recovery** (3 min) ⭐
```
1. Show all agents working (green status)
2. Kill US-WEST-2 region (Fraud + Learning agents)
3. Dashboard shows: "🔴 UNREACHABLE"
4. User makes query → Orchestrator adapts
5. Remaining agents continue working
6. Memory/data still accessible (CockroachDB replicas)
7. Recover region → Agents rejoin seamlessly
8. Show memory intact, no data loss
```

### 7. Dependencies to Add

```toml
# Add to pyproject.toml
dependencies = [
    # ... existing dependencies ...
    
    # Agent Framework
    "langgraph>=0.0.20",
    "langchain>=0.1.0",
    "langchain-openai>=0.0.5",
    "langchain-aws>=0.0.5",
    "langchain-google-genai>=0.0.5",
    
    # Document Processing
    "pytesseract>=0.3.10",
    "pdf2image>=1.16.3",
    "Pillow>=10.0.0",
    "PyPDF2>=3.0.0",
    
    # Background Tasks
    "celery>=5.3.0",
    "redis>=5.0.0",
    
    # WebSocket for real-time updates
    "python-socketio>=5.10.0",
    "flask-socketio>=5.3.5",
    
    # S3/MinIO
    "minio>=7.2.0",
    
    # Async support
    "asyncio>=3.4.3",
    "aiohttp>=3.9.0",
]
```

### 8. Implementation Phases

#### **Phase 1: Core Agent Framework** (Days 1-3)
- [ ] Base agent classes
- [ ] LangChain integration with existing providers
- [ ] Database schema updates
- [ ] Agent memory system
- [ ] Tool registry

#### **Phase 2: Specialized Agents** (Days 4-6)
- [ ] Receipt Agent + OCR
- [ ] Fraud Agent (autonomous)
- [ ] Budget Agent (proactive)
- [ ] Orchestrator Agent

#### **Phase 3: UI & Dashboard** (Days 7-8)
- [ ] Agent activity dashboard
- [ ] Real-time WebSocket updates
- [ ] Enhanced chat interface
- [ ] Document upload UI

#### **Phase 4: Multi-Region Deployment** (Days 9-10)
- [ ] Docker agent workers
- [ ] Integration with chaos demo
- [ ] Agent coordination across regions
- [ ] Failover testing

#### **Phase 5: Demo Scenarios & Polish** (Days 11-12)
- [ ] Pre-configured demo workflows
- [ ] Sample data generation
- [ ] Performance optimization
- [ ] Documentation & demo script

### 9. Key Differentiators for re:Invent

✅ **Multi-agent orchestration** - Not just one agent, a TEAM
✅ **Distributed across regions** - Showcases CockroachDB's scale
✅ **Autonomous operation** - Agents work 24/7, not just chat
✅ **Transparent reasoning** - See agents think in real-time
✅ **Provider agnostic** - Works with ANY AI provider
✅ **Survives failures** - Keep working during region outages
✅ **Learning system** - Gets smarter from user feedback
✅ **Unified memory** - Vector + transactional in one DB

## Next Steps

1. ✅ **Created branch**: `agentic-ai`
2. **Start with Phase 1** - Build core agent framework
3. **Integrate with chaos demo** - Modify docker-compose
4. **Build incrementally** - Test each agent independently
5. **Demo scenarios** - Create reproducible workflows

Ready to start building? Let me know which component you want to tackle first!
