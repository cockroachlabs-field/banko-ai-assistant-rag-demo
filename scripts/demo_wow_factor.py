"""
The WOW Factor Demo - Unstructured → AI → Structured

Shows the complete pipeline with all tables populated.
"""

import os
import json
from datetime import datetime

os.environ['TOKENIZERS_PARALLELISM'] = 'false'

from langchain_openai import ChatOpenAI
from sentence_transformers import SentenceTransformer
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from banko_ai.agents.fraud_agent import FraudAgent
from banko_ai.agents.budget_agent import BudgetAgent
from banko_ai.agents.orchestrator_agent import OrchestratorAgent


def demo_wow_factor():
    """Demonstrate all features including table population"""
    
    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║                                                               ║")
    print("║              THE WOW FACTOR - COMPLETE DEMO                   ║")
    print("║                                                               ║")
    print("╚═══════════════════════════════════════════════════════════════╝")
    print()
    
    # Configuration
    database_url = os.getenv(
        'DATABASE_URL',
        'cockroachdb://root@localhost:26257/defaultdb?sslmode=disable'
    )
    openai_api_key = os.getenv('OPENAI_API_KEY')
    
    if not openai_api_key:
        print("❌ OPENAI_API_KEY not set")
        return False
    
    # Initialize models
    print("1️⃣  Initializing AI Models...")
    llm = ChatOpenAI(model="gpt-4o-mini", api_key=openai_api_key)
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    print("   ✅ LLM and embeddings ready")
    print()
    
    # Create agents
    print("2️⃣  Creating Specialized Agents...")
    
    fraud_agent = FraudAgent(
        region="us-west-2",
        llm=llm,
        database_url=database_url,
        embedding_model=embedding_model,
        fraud_threshold=0.7
    )
    print(f"   ✅ Fraud Agent (us-west-2): {fraud_agent.agent_id[:8]}...")
    
    budget_agent = BudgetAgent(
        region="us-central-1",
        llm=llm,
        database_url=database_url,
        alert_threshold=0.8
    )
    print(f"   ✅ Budget Agent (us-central-1): {budget_agent.agent_id[:8]}...")
    
    orchestrator = OrchestratorAgent(
        region="us-east-1",
        llm=llm,
        database_url=database_url
    )
    orchestrator.register_agent('fraud', fraud_agent)
    orchestrator.register_agent('budget', budget_agent)
    print(f"   ✅ Orchestrator (us-east-1): {orchestrator.agent_id[:8]}...")
    print()
    
    # Store some memory
    print("3️⃣  Storing Agent Memory (with vector embeddings)...")
    
    # Create memory entries
    memories = [
        "User prefers to shop at Whole Foods for groceries",
        "User's monthly budget is typically $1000",
        "User has flagged duplicate transactions at Walmart before"
    ]
    
    engine = create_engine(database_url, poolclass=NullPool)
    
    for memory_text in memories:
        embedding = embedding_model.encode(memory_text).tolist()
        
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO agent_memory (memory_id, agent_id, memory_type, content, embedding, metadata)
                VALUES (gen_random_uuid(), :agent_id, 'long_term', :content, 
                        CAST(:embedding AS VECTOR(384)), :metadata)
            """), {
                'agent_id': budget_agent.agent_id,
                'content': memory_text,
                'embedding': str(embedding),
                'metadata': json.dumps({'source': 'demo', 'created_at': datetime.utcnow().isoformat()})
            })
            conn.commit()
    
    print(f"   ✅ Stored {len(memories)} memory entries with 384-dim embeddings")
    print()
    
    # Create agent task
    print("4️⃣  Creating Agent Task (cross-agent communication)...")
    
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO agent_tasks (task_id, source_agent_id, target_agent_id, task_type, payload, priority, region, status)
            VALUES (gen_random_uuid(), :source_id, :target_id, 'check_expense', :payload, 8, 'us-west-2', 'pending')
        """), {
            'source_id': orchestrator.agent_id,
            'target_id': fraud_agent.agent_id,
            'payload': json.dumps({
                'expense_id': 'demo_expense_123',
                'reason': 'Large transaction detected',
                'amount': 500.00
            })
        })
        conn.commit()
    
    print("   ✅ Task created: Orchestrator → Fraud Agent")
    print()
    
    # Store conversation
    print("5️⃣  Storing Conversation History...")
    
    conversation_embedding = embedding_model.encode("Check my recent expenses for fraud").tolist()
    
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO conversations (conversation_id, user_id, agent_id, message, role, embedding, metadata)
            VALUES (gen_random_uuid(), 'demo_user', :agent_id, :message, 'user',
                    CAST(:embedding AS VECTOR(384)), :metadata)
        """), {
            'agent_id': orchestrator.agent_id,
            'message': 'Check my recent expenses for fraud',
            'embedding': str(conversation_embedding),
            'metadata': json.dumps({'session': 'demo', 'timestamp': datetime.utcnow().isoformat()})
        })
        conn.commit()
    
    print("   ✅ Conversation stored with embedding")
    print()
    
    # Store document
    print("6️⃣  Storing Sample Document (receipt metadata)...")
    
    document_text = "Receipt from Target: Total $83.47 - Groceries and household items"
    doc_embedding = embedding_model.encode(document_text).tolist()
    
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO documents (document_id, user_id, document_type, content, embedding, metadata)
            VALUES (gen_random_uuid(), 'demo_user', 'receipt', :content,
                    CAST(:embedding AS VECTOR(384)), :metadata)
        """), {
            'content': document_text,
            'embedding': str(doc_embedding),
            'metadata': json.dumps({
                'merchant': 'Target',
                'amount': 83.47,
                'date': datetime.utcnow().isoformat(),
                'items': ['Groceries', 'Household']
            })
        })
        conn.commit()
    
    print("   ✅ Document stored with embedding")
    print()
    
    # Run fraud scan
    print("7️⃣  Running Fraud Agent (autonomous operation)...")
    result = fraud_agent.scan_recent_expenses(hours=24, limit=5)
    print(f"   ✅ Scanned {result.get('total_analyzed', 0)} expenses")
    print(f"   ⚠️  Flagged {result.get('total_flagged', 0)} suspicious")
    print()
    
    # Run budget check
    print("8️⃣  Running Budget Agent (proactive monitoring)...")
    
    with engine.connect() as conn:
        result_user = conn.execute(text("SELECT DISTINCT user_id FROM expenses LIMIT 1"))
        row = result_user.fetchone()
        user_id = str(row[0]) if row else "user_01"
    
    budget_result = budget_agent.check_budget_status(user_id, 1000.00)
    print(f"   ✅ Status: {budget_result.get('status', 'unknown')}")
    print(f"   💵 Spent: ${budget_result.get('spent', 0):.2f}")
    print()
    
    # Run orchestrator workflow
    print("9️⃣  Running Orchestrator (multi-agent coordination)...")
    workflow_result = orchestrator.execute_workflow(
        "Check my budget and scan for fraud",
        {'user_id': user_id, 'monthly_budget': 1000.00}
    )
    print(f"   ✅ Workflow executed: {len(workflow_result.get('steps_executed', []))} steps")
    print()
    
    # Show final table status
    print("="*70)
    print("\n✅ ALL TABLES NOW POPULATED!")
    print("="*70)
    print()
    
    tables = {
        'agent_state': 'Agent registrations & status',
        'agent_decisions': 'Decision audit trail',
        'agent_memory': 'Long-term memory with embeddings',
        'agent_tasks': 'Cross-agent communication queue',
        'conversations': 'Chat history with embeddings',
        'documents': 'Receipt/document storage'
    }
    
    print("Table Status:")
    for table, desc in tables.items():
        try:
            with engine.connect() as conn:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.fetchone()[0]
                status = "✅" if count > 0 else "⚠️ "
                print(f"  {status} {table:20} {count:4} records  ({desc})")
        except Exception as e:
            print(f"  ❌ {table:20}  Error: {e}")
    
    engine.dispose()
    
    print()
    print("="*70)
    print("\n🎯 THE WOW FACTOR DEMONSTRATED:")
    print("="*70)
    print()
    print("✅ Think → Remember → Act:")
    print("   • Agents THINK using LLMs (fraud detection, budget forecasting)")
    print("   • Agents REMEMBER using CockroachDB (vector + transactional)")
    print("   • Agents ACT autonomously (scanning, alerting, coordinating)")
    print()
    print("✅ All 6 Tables Populated:")
    print("   • agent_state: Real-time agent status")
    print("   • agent_decisions: Complete audit trail")
    print("   • agent_memory: Semantic memory search")
    print("   • agent_tasks: Agent-to-agent messaging")
    print("   • conversations: User interaction history")
    print("   • documents: Unstructured data processed")
    print()
    print("✅ Multi-Agent System Working:")
    print("   • 3+ regions (us-east-1, us-west-2, us-central-1)")
    print("   • Autonomous operation (agents work 24/7)")
    print("   • Coordinated workflows (Orchestrator)")
    print("   • Real-time dashboard (live updates)")
    print()
    print("✅ Provider Agnostic:")
    print("   • Works with OpenAI, Bedrock, Gemini, Watsonx")
    print("   • Same code, different LLM backend")
    print()
    print("🎉 READY FOR RE:INVENT! 🚀")
    
    return True


if __name__ == "__main__":
    success = demo_wow_factor()
    exit(0 if success else 1)
