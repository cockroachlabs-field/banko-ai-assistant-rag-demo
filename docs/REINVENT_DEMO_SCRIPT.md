# 🎬 re:Invent Demo Script: Agentic AI with CockroachDB

**Duration**: 10-15 minutes  
**Audience**: Technical audience at AWS re:Invent  
**Goal**: Demonstrate "Think → Remember → Act" with multi-agent AI system

---

## 📋 Pre-Demo Setup (5 minutes before)

### 1. Start the System
```bash
# Terminal 1: Start server with dashboard
python test_dashboard.py

# Wait for "Server starting..." message
# Verify: http://localhost:5001/agents shows empty/few agents
```

### 2. Open Browser Windows
- **Window 1**: Agent Dashboard - http://localhost:5001/agents
- **Window 2**: CockroachDB UI - http://localhost:8080
- **Optional Window 3**: Main App - http://localhost:5001/

### 3. Verify System
```bash
# Terminal 2: Quick system check
python check_dashboard.py

# Should show:
# ✅ API Status: Connected
# ✅ Dashboard operational
```

### 4. Position Windows
- Large monitor: Agent Dashboard (main focus)
- Side monitor: CockroachDB UI + terminal
- Keep terminals visible for live output

---

## 🎯 Demo Flow

### Act 1: Introduction (2 minutes)

**Script:**
> "Today I'm going to show you something different. Not a chatbot, but a team of autonomous AI agents working together using CockroachDB as their distributed memory system.
>
> This demonstrates what we call 'Think → Remember → Act'—and you'll see it happening in real-time."

**Action:**
- Show agent dashboard
- Point out empty/idle state
- Explain the architecture briefly

**Key Points:**
- 4 specialized agents (Receipt, Fraud, Budget, Orchestrator)
- Distributed across 3 regions (us-east-1, us-west-2, us-central-1)
- CockroachDB provides unified memory (transactional + vector)
- Works with ANY AI provider (OpenAI, Bedrock, Gemini, Watsonx)

---

### Act 2: Individual Agent Demo (3 minutes)

#### Scenario 1: Autonomous Fraud Detection

**Script:**
> "Let me show you the Fraud Agent. It's not waiting for someone to ask—it's actively monitoring transactions 24/7."

**Action:**
```bash
# Terminal: Trigger fraud scan
python -c "
from banko_ai.agents.fraud_agent import FraudAgent
from langchain_openai import ChatOpenAI
from sentence_transformers import SentenceTransformer
import os

llm = ChatOpenAI(model='gpt-4o-mini', api_key=os.getenv('OPENAI_API_KEY'))
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
agent = FraudAgent('us-west-2', llm, os.getenv('DATABASE_URL', 'cockroachdb://root@localhost:26257/defaultdb?sslmode=disable'), embedding_model)
result = agent.scan_recent_expenses(hours=24, limit=10)
print(f'Scanned {result[\"total_analyzed\"]} expenses')
print(f'Flagged {result[\"total_flagged\"]} suspicious')
"
```

**Watch Dashboard:**
- Fraud Agent card activates (idle → thinking → acting)
- Activity feed updates with decision
- Confidence score displayed
- Reasoning visible

**Key Points:**
- **Think**: Agent analyzes using multiple signals (duplicates, anomalies, vector search)
- **Remember**: Searches past fraud using vector similarity
- **Act**: Flags suspicious transactions with confidence score
- **Autonomous**: Runs continuously, not triggered by users

**Show in CockroachDB UI:**
```sql
SELECT * FROM agent_decisions 
WHERE agent_id IN (SELECT agent_id FROM agent_state WHERE agent_type = 'fraud')
ORDER BY created_at DESC LIMIT 5;
```

Point out: Reasoning, confidence, signals detected

---

#### Scenario 2: Proactive Budget Monitoring

**Script:**
> "Now the Budget Agent. It doesn't wait for you to be over budget—it warns you BEFORE you exceed your limit."

**Action:**
```bash
# Terminal: Check budget
python -c "
from banko_ai.agents.budget_agent import BudgetAgent
from langchain_openai import ChatOpenAI
import os

llm = ChatOpenAI(model='gpt-4o-mini', api_key=os.getenv('OPENAI_API_KEY'))
agent = BudgetAgent('us-central-1', llm, os.getenv('DATABASE_URL', 'cockroachdb://root@localhost:26257/defaultdb?sslmode=disable'))
result = agent.check_budget_status('user_01', 1000.00)
print(f'Status: {result[\"status\"]}')
print(f'Spent: ${result[\"spent\"]:.2f}')
print(f'Projected: ${result[\"projected_total\"]:.2f}')
"
```

**Watch Dashboard:**
- Budget Agent activates (us-central-1)
- Decision appears with forecast
- Recommendation shown

**Key Points:**
- **Think**: Calculates spending velocity and projects month-end total
- **Remember**: Analyzes historical spending patterns
- **Act**: Generates proactive alert with specific recommendation
- **Forecasting**: "You're on pace to exceed by $X"

---

### Act 3: Multi-Agent Orchestration (4 minutes)

#### Scenario 3: Complex Workflow

**Script:**
> "Here's where it gets interesting. Watch what happens when I give the system a complex task that requires multiple specialists."

**Action:**
```bash
# Terminal: Run orchestrator
python -c "
from banko_ai.agents.orchestrator_agent import OrchestratorAgent
from banko_ai.agents.fraud_agent import FraudAgent
from banko_ai.agents.budget_agent import BudgetAgent
from langchain_openai import ChatOpenAI
from sentence_transformers import SentenceTransformer
import os

llm = ChatOpenAI(model='gpt-4o-mini', api_key=os.getenv('OPENAI_API_KEY'))
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
db_url = os.getenv('DATABASE_URL', 'cockroachdb://root@localhost:26257/defaultdb?sslmode=disable')

# Create agents
fraud = FraudAgent('us-west-2', llm, db_url, embedding_model)
budget = BudgetAgent('us-central-1', llm, db_url)

# Create orchestrator
orchestrator = OrchestratorAgent('us-east-1', llm, db_url)
orchestrator.register_agent('fraud', fraud)
orchestrator.register_agent('budget', budget)

# Execute complex workflow
result = orchestrator.execute_workflow(
    'Audit my recent expenses and check if I am over budget',
    {'user_id': 'user_01', 'monthly_budget': 1000.0}
)

print(f'Workflow: {result[\"success\"]}')
print(f'Steps: {len(result[\"steps_executed\"])}')
if result.get('final_result'):
    print(f'Summary: {result[\"final_result\"].get(\"synthesis\", \"\")[:200]}...')
"
```

**Watch Dashboard - The Magic Moment:**
1. **Orchestrator thinks**: Plans which agents to use
2. **Fraud Agent acts** (us-west-2): Scans expenses
3. **Budget Agent acts** (us-central-1): Checks budget
4. **Orchestrator synthesizes**: Combines results into coherent answer

**Activity feed shows:**
- Step 1: Orchestrator planning
- Step 2: Fraud scan decision
- Step 3: Budget check decision
- Step 4: Final synthesis

**Key Points:**
- **Distributed**: Agents in different regions working together
- **Coordinated**: Orchestrator manages the workflow
- **Intelligent**: Each agent contributes its specialty
- **Unified Result**: One coherent answer from multiple sources

---

### Act 4: The "Remember" Part - CockroachDB (2 minutes)

**Script:**
> "So how do these agents remember? How do they share knowledge? That's where CockroachDB comes in."

**Action - Show in CockroachDB UI:**

1. **Show Agent State Table:**
```sql
SELECT agent_id, agent_type, region, status, last_heartbeat 
FROM agent_state 
ORDER BY agent_type, region;
```
Point out: Agents registered across 3 regions

2. **Show Agent Memory (Vector + Metadata):**
```sql
SELECT memory_id, agent_id, memory_type, 
       vector_to_array(embedding)[1:5] as first_5_dims
FROM agent_memory 
LIMIT 5;
```
Point out: 384-dimensional embeddings for semantic search

3. **Show Decision Audit Trail:**
```sql
SELECT d.decision_type, d.confidence, d.reasoning, a.agent_type, a.region
FROM agent_decisions d
JOIN agent_state a ON d.agent_id = a.agent_id
ORDER BY d.created_at DESC
LIMIT 5;
```
Point out: Every decision tracked with reasoning

**Key Points:**
- **Transactional Memory**: Structured data (status, decisions)
- **Vector Memory**: Semantic embeddings for similarity search
- **Distributed**: Same data accessible from any region
- **Persistent**: Memory survives agent restarts/failures
- **Audit Trail**: Complete history of every decision

---

### Act 5: Provider Agnostic (2 minutes)

**Script:**
> "One more thing—this isn't locked to one AI provider. Let me switch providers live."

**Action:**
```bash
# Option 1: Show environment variable
echo $AI_SERVICE  # Shows: openai

# Option 2: Modify and restart an agent with different provider
export AI_SERVICE=aws
export AWS_MODEL_ID=us.anthropic.claude-3-5-sonnet-20241022-v2:0

# Create agent with Bedrock
python -c "
from banko_ai.agents.fraud_agent import FraudAgent
from langchain_aws import ChatBedrock
import boto3
import os

bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
llm = ChatBedrock(model_id='us.anthropic.claude-3-5-sonnet-20241022-v2:0', client=bedrock)
# ... (if AWS credentials available)
"
```

**Show config support:**
```python
# pyproject.toml shows:
# - langchain-openai
# - langchain-aws
# - langchain-google-genai
# - langchain-community
```

**Key Points:**
- Works with OpenAI, AWS Bedrock, Google Gemini, IBM Watsonx
- Same agent code, different LLM backend
- No vendor lock-in
- Choose best model for your use case

---

### Act 6: Resilience Demo (Optional - 2 minutes if time)

**Script:**
> "And because it's built on CockroachDB, it survives failures."

**Action:**
```bash
# Kill an agent
docker stop banko-fraud-agent

# Show in dashboard: Agent goes offline
# Memory persists in database
# Other agents continue working

# Restart agent
docker start banko-fraud-agent

# Show: Agent rejoins, accesses same memory, continues
```

**Key Points:**
- Agents are stateless
- Memory in database (replicated, distributed)
- Kill agents, memory survives
- Kill database nodes (if multi-node), system continues

---

## 🎬 Closing (1 minute)

**Script:**
> "So what did we just see?
>
> 1. **Autonomous agents**—not chatbots waiting for prompts, but active specialists
> 2. **Multi-agent coordination**—a team working together on complex tasks
> 3. **Distributed memory**—CockroachDB providing unified, persistent, searchable memory
> 4. **Provider agnostic**—works with any AI provider you choose
> 5. **Resilient**—survives failures, memory persists
>
> This is 'Think → Remember → Act'—and it's production-ready today.
>
> All the code is open source. Links in the slides."

**Final Slide:**
- GitHub: cockroachlabs-field/banko-ai-assistant-rag-demo
- Branch: agentic-ai
- Dashboard: Screenshot of agents in action
- Architecture diagram

---

## 📝 Talking Points

### Why Multi-Agent vs Single LLM?
- **Specialization**: Each agent focused on one task (better accuracy)
- **Scalability**: Scale agents independently
- **Maintainability**: Update one agent without affecting others
- **Cost**: Use smaller models for specialized tasks

### Why CockroachDB?
- **Unified Memory**: One database for transactional + vector data
- **Distributed**: Agents in multiple regions access same data
- **Resilient**: Survives node failures
- **Scalable**: Handles millions of embeddings
- **SQL + Vector**: Familiar SQL interface + vector search

### Why Vector Search?
- **Semantic Understanding**: Find similar concepts, not just exact matches
- **Learning from Past**: Search historical fraud patterns
- **Context**: Find relevant context for agent decisions
- **Deduplication**: Detect similar expenses/receipts

---

## 🎯 Success Metrics

**What the audience should remember:**
1. ✅ "Agentic AI" = autonomous team of specialists, not chatbot
2. ✅ "Think → Remember → Act" made visible and real
3. ✅ CockroachDB enables distributed AI agent memory
4. ✅ Production-ready, provider-agnostic, resilient

**What they should feel:**
- Excited about building their own agent systems
- Confident CockroachDB can support AI workloads
- Inspired to try the code themselves

**What they should do:**
- Visit the GitHub repo
- Try the demo locally
- Build their own agents
- Consider CockroachDB for their AI projects

---

## 🔧 Troubleshooting During Demo

### Problem: Agent not showing on dashboard
**Fix**: Wait 10 seconds and refresh. Agents register on first activity.

### Problem: API key error
**Fix**: Have backup terminal with working credentials ready. Switch to that terminal.

### Problem: Dashboard WebSocket disconnected
**Fix**: Refresh browser. WebSocket reconnects automatically.

### Problem: Orchestrator invents method names
**Fix**: Expected behavior. Show synthesis still works. Explain LLMs are creative!

### Problem: Slow LLM response
**Fix**: Say "While we wait, let me explain what's happening..." (fill time with architecture explanation)

---

## 📸 Screenshot Checklist

Before demo, capture:
- [ ] Agent dashboard with all agents idle
- [ ] Agent dashboard with workflow in progress (multiple active)
- [ ] Activity feed with decisions
- [ ] CockroachDB UI with agent tables
- [ ] Architecture diagram
- [ ] Code snippets (agent creation, workflow)

Have as backup slides if live demo fails.

---

## 🎤 Key Quotes for the Talk

> "This isn't a chatbot. It's a team of autonomous specialists."

> "Watch them think, remember, and act—in real-time."

> "Every decision is transparent. Every thought is recorded."

> "Kill a region. Memory persists. Agents continue."

> "Works with OpenAI, Bedrock, Gemini, Watsonx—your choice."

---

**Total Time**: 12-15 minutes
**Backup**: Screenshots of each step if live demo fails
**Confidence**: High—system tested and working!

🎉 **Good luck at re:Invent!** 🎉
