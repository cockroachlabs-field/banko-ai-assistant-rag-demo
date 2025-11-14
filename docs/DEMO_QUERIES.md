# Re:Invent Demo - Database Queries

## Quick Demo Queries

### 1. Show Recent Agent Decisions (with agent types)
```sql
cockroach sql --insecure -e "
SELECT 
    a.agent_type,
    d.decision_type,
    SUBSTRING(d.reasoning, 1, 100) as reasoning_preview
FROM agent_decisions d
JOIN agent_state a ON d.agent_id = a.agent_id
ORDER BY d.created_at DESC
LIMIT 5;
"
```
**Shows**: What agents decided recently with preview of reasoning

---

### 2. Show Deployed Agents (Multi-Region)
```sql
cockroach sql --insecure -e "
SELECT 
    agent_type,
    region,
    status,
    last_heartbeat
FROM agent_state
ORDER BY agent_type, region;
"
```
**Shows**: Agents deployed across us-east-1, us-west-2, us-central-1

---

### 3. Show Recent Expenses from Receipts
```sql
cockroach sql --insecure -e "
SELECT 
    merchant,
    expense_amount,
    shopping_type,
    expense_date
FROM expenses
ORDER BY created_at DESC
LIMIT 5;
"
```
**Shows**: Expenses extracted from uploaded receipts

---

### 4. Show Fraud Analysis (Most Impressive!)
```sql
cockroach sql --insecure -e "
SELECT 
    reasoning
FROM agent_decisions d
JOIN agent_state a ON d.agent_id = a.agent_id
WHERE a.agent_type = 'fraud'
ORDER BY d.created_at DESC
LIMIT 1;
"
```
**Shows**: Full AI fraud analysis reasoning - this is the money shot!

---

### 5. Show Budget Analysis
```sql
cockroach sql --insecure -e "
SELECT 
    d.context->>'status' as budget_status,
    d.context->>'current_spend' as spent,
    d.context->>'budget' as budget,
    SUBSTRING(d.reasoning, 1, 200) as analysis
FROM agent_decisions d
JOIN agent_state a ON d.agent_id = a.agent_id
WHERE d.decision_type = 'budget_check'
ORDER BY d.created_at DESC
LIMIT 1;
"
```
**Shows**: Budget status with AI reasoning

---

### 6. Show Agent Memory Count
```sql
cockroach sql --insecure -e "
SELECT 
    a.agent_type,
    COUNT(m.memory_id) as memory_count
FROM agent_state a
LEFT JOIN agent_memory m ON a.agent_id = m.agent_id
GROUP BY a.agent_type;
"
```
**Shows**: How much each agent has learned (memory with vector embeddings)

---

### 7. Show Complete Agent Decision Trail
```sql
cockroach sql --insecure -e "
SELECT 
    a.agent_type,
    a.region,
    d.decision_type,
    d.confidence,
    d.created_at
FROM agent_decisions d
JOIN agent_state a ON d.agent_id = a.agent_id
ORDER BY d.created_at DESC
LIMIT 10;
"
```
**Shows**: Complete audit trail of agent decisions

---

## For Live Demo

### Pre-Demo Setup
```bash
# Populate with demo data
python3 demo_wow_factor.py

# Verify data
cockroach sql --insecure -e "SELECT COUNT(*) FROM agent_decisions;"
```

### During Demo (After Receipt Upload)
1. Show terminal output (real-time cascade)
2. Run query #4 (fraud reasoning) - most impressive!
3. Run query #3 (show extracted expense)
4. Run query #2 (show multi-region deployment)

### The "Wow" Moment
Show the fraud reasoning query - it displays the full AI analysis:
- Duplicate check results
- Statistical analysis
- Vector search for similar fraud
- Merchant verification
- Confidence score calculation

This proves the agent is "thinking" with AI!

---

## Alternative: Browser Console

If terminal/SQL is awkward during demo, show in browser console:

```javascript
// In browser console at http://localhost:5001/agents
fetch('/api/agents/activity')
  .then(r => r.json())
  .then(data => console.table(data.activities))
```

Shows agent activity in nice formatted table!
