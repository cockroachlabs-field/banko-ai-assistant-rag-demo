# 🚀 Quick Demo Start Guide

**Use this for a quick demo** (5-10 minutes) without the full re:Invent setup.

---

## 🎯 Quick Start (3 steps)

### Step 1: Start Everything (1 minute)

```bash
# Open Terminal 1
cd /path/to/banko-ai-assistant-rag-demo

# Make sure CockroachDB is running
# If using Docker:
docker-compose up -d cockroachdb

# If using local install:
cockroach start-single-node --insecure --listen-addr=localhost:26257 --http-addr=localhost:8080 &

# Set API key
export OPENAI_API_KEY="sk-..."

# Start dashboard
python test_dashboard.py
```

Wait for:
```
✅ Server starting...
   Main App: http://localhost:5001/
   Dashboard: http://localhost:5001/agents
```

### Step 2: Open Browser (30 seconds)

Open these URLs:

1. **Main App** (new tab): http://localhost:5001/
2. **Agent Dashboard** (new tab): http://localhost:5001/agents  
3. **CockroachDB UI** (optional): http://localhost:8080

Position windows side-by-side to see both.

### Step 3: Run Demo Workflow (1 minute)

Open **Terminal 2**:

```bash
# Quick multi-agent demo
python test_orchestrator.py
```

**Watch the magic happen on the dashboard!** 🎉

---

## 🎬 5-Minute Demo Script

### Intro (30 seconds)

> "Let me show you our agentic AI system. This isn't a chatbot—it's a team of autonomous agents working together."

**Show:**
- Dashboard with agent cards
- Point out different regions (us-east-1, us-west-2, us-central-1)

### Demo 1: Individual Agent (1 minute)

> "First, let's see the Fraud Agent working autonomously."

**Terminal 2:**
```bash
python -c "
import os
os.environ['TOKENIZERS_PARALLELISM'] = 'false'
from langchain_openai import ChatOpenAI
from sentence_transformers import SentenceTransformer
from banko_ai.agents.fraud_agent import FraudAgent

llm = ChatOpenAI(model='gpt-4o-mini', api_key=os.getenv('OPENAI_API_KEY'))
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
agent = FraudAgent('us-west-2', llm, os.getenv('DATABASE_URL', 'cockroachdb://root@localhost:26257/defaultdb?sslmode=disable'), embedding_model)

print('🔍 Fraud Agent scanning recent expenses...')
result = agent.scan_recent_expenses(hours=24, limit=10)
print(f'Analyzed: {result[\"total_analyzed\"]} | Flagged: {result[\"total_flagged\"]}')
"
```

**Point out on dashboard:**
- Agent card activates (idle → thinking → acting → idle)
- Activity feed updates
- Confidence score shows
- Reasoning visible

> "Notice how it's not just flagging transactions—it's explaining WHY with confidence scores."

### Demo 2: Multi-Agent Coordination (2 minutes)

> "Now watch what happens with a complex request requiring multiple agents."

**Terminal 2:**
```bash
python test_orchestrator.py
```

**Point out:**
1. **Orchestrator thinks**: Plans which agents to use
2. **Fraud Agent acts**: Scans expenses (us-west-2)
3. **Budget Agent acts**: Checks budget (us-central-1)
4. **Orchestrator synthesizes**: Combines results

> "See how they work together? Each agent specializes, but the orchestrator coordinates them into one coherent answer."

### Demo 3: The Memory (1 minute)

> "Their memory? CockroachDB. Let me show you."

**Open CockroachDB UI** (http://localhost:8080):

Navigate to: **Databases → defaultdb → Tables**

Show:
- `agent_state` - Agent status across regions
- `agent_decisions` - Complete audit trail
- `agent_memory` - Vector embeddings for semantic search

**Run SQL:**
```sql
SELECT agent_type, region, status, last_heartbeat 
FROM agent_state 
ORDER BY last_heartbeat DESC 
LIMIT 5;
```

> "Every decision, every thought, every memory—stored here. Distributed, replicated, searchable. And it survives failures."

### Demo 4: Navigation Integration (30 seconds)

**Go back to main app** (http://localhost:5001/)

> "And it's all integrated. Watch this."

- Click "Agent Dashboard" in sidebar
- Opens in new tab
- Click "Back to Banko"
- Returns to main app

> "Users can monitor agents while using the banking app. Seamless."

### Closing (30 seconds)

> "So what did we just see?
> 
> 1. **Autonomous agents**—not chatbots, but specialists doing real work
> 2. **Multi-agent coordination**—working together on complex tasks
> 3. **CockroachDB as distributed memory**—persistent, searchable, resilient
> 4. **Provider agnostic**—works with OpenAI, Bedrock, Gemini, Watsonx
> 
> And it's open source. GitHub link in the slides."

---

## 🎯 Even Quicker Demo (2 minutes)

If you only have 2 minutes:

### 1. Show Dashboard (30 seconds)
```bash
# Start server
python test_dashboard.py
```

Open: http://localhost:5001/agents

> "This is our agent dashboard. Each card is an autonomous AI agent."

### 2. Run One Test (1 minute)
```bash
python test_orchestrator.py
```

> "Watch them work together—orchestrator coordinates fraud and budget agents, synthesizes the result. Think → Remember → Act, visible in real-time."

### 3. Show Database (30 seconds)

Open: http://localhost:8080

> "Their memory: CockroachDB. Distributed, persistent, with vector search. Every decision tracked, every memory searchable."

**Done!** 🎉

---

## 🛠️ Troubleshooting During Demo

### If something breaks:

**1. Server died:**
```bash
python test_dashboard.py
```

**2. Agents not showing:**
```bash
python test_all_agents.py  # Registers some agents
```
Then refresh dashboard.

**3. API key error:**
```bash
export OPENAI_API_KEY="sk-..."
```
Restart server.

**4. Database error:**
```bash
docker-compose restart cockroachdb
```
Wait 10 seconds, restart server.

**5. Total failure:**
> "While that restarts, let me show you the architecture..."

Pull up screenshots or architecture diagram while fixing.

---

## 📸 Have Backup Screenshots

In case live demo fails, have these ready:

1. Dashboard with multiple active agents
2. Activity feed with decisions
3. CockroachDB tables (agent_state, agent_decisions)
4. Orchestrator workflow output
5. Architecture diagram

Save in: `/screenshots/` folder

---

## 🎤 Key Talking Points

### "Think → Remember → Act"
- **Think**: LLMs reason about problems (visible in activity feed)
- **Remember**: CockroachDB stores memory (show tables)
- **Act**: Agents execute real operations (see status changes)

### "Why Multi-Agent?"
- **Specialization**: Each agent focuses on one task (better accuracy)
- **Scalability**: Scale agents independently
- **Maintainability**: Update one agent without breaking others

### "Why CockroachDB?"
- **Unified Memory**: Transactional + Vector in one database
- **Distributed**: Agents in multiple regions, same data
- **Resilient**: Survives node failures (memory persists)
- **Scalable**: Handles millions of embeddings

### "Provider Agnostic"
- Works with OpenAI, AWS Bedrock, Google Gemini, IBM Watsonx
- Same agent code, different LLM backend
- No vendor lock-in

---

## ⚡ Speed Run Commands

Copy-paste for fastest demo setup:

```bash
# Terminal 1: Start everything
cd ~/banko-ai-assistant-rag-demo
export OPENAI_API_KEY="sk-..."
docker-compose up -d cockroachdb && sleep 5
python test_dashboard.py

# Terminal 2: Run demo (wait 10 sec after Terminal 1)
cd ~/banko-ai-assistant-rag-demo
export OPENAI_API_KEY="sk-..."
python test_orchestrator.py

# Browser: Open these
open http://localhost:5001/agents
open http://localhost:8080
```

**Demo time:** 5-10 minutes  
**Prep time:** 2 minutes  
**Wow factor:** 🚀🚀🚀

---

## 📊 Success Metrics

Your demo is successful if audience:

1. ✅ Sees agents working autonomously
2. ✅ Understands multi-agent coordination
3. ✅ Recognizes CockroachDB's role
4. ✅ Appreciates "Think → Remember → Act"
5. ✅ Wants to try it themselves

**Call to Action:**
> "All code is on GitHub. Try it yourself, build your own agents. Let's make AI systems that think, remember, and act."

🎉 **You're ready to demo!**
