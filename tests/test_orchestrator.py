"""
Test Orchestrator Agent with multi-agent workflows.

This demonstrates:
- Multi-agent coordination
- Complex workflow execution
- Result synthesis
"""

import os

# Disable tokenizers parallelism warning
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

from langchain_openai import ChatOpenAI
from sentence_transformers import SentenceTransformer

from banko_ai.agents.orchestrator_agent import OrchestratorAgent
from banko_ai.agents.fraud_agent import FraudAgent
from banko_ai.agents.budget_agent import BudgetAgent


def test_orchestrator():
    """Test Orchestrator Agent"""
    
    print("🧪 Testing Orchestrator Agent")
    print("="*70)
    
    # Configuration
    database_url = os.getenv(
        'DATABASE_URL',
        'cockroachdb://root@localhost:26257/defaultdb?sslmode=disable'
    )
    openai_api_key = os.getenv('OPENAI_API_KEY')
    
    if not openai_api_key:
        print("❌ OPENAI_API_KEY not set")
        return False
    
    print(f"✅ Database: {database_url.split('@')[1]}")
    print()
    
    # Initialize models
    print("1️⃣  Initializing shared resources...")
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        api_key=openai_api_key,
        temperature=0.7
    )
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    print("   ✅ LLM and embedding model ready")
    print()
    
    # Create specialized agents
    print("2️⃣  Creating specialized agents...")
    
    fraud_agent = FraudAgent(
        region="us-west-2",
        llm=llm,
        database_url=database_url,
        embedding_model=embedding_model,
        fraud_threshold=0.7
    )
    print(f"   ✅ Fraud Agent: {fraud_agent.agent_id[:8]}...")
    
    budget_agent = BudgetAgent(
        region="us-central-1",
        llm=llm,
        database_url=database_url,
        alert_threshold=0.8
    )
    print(f"   ✅ Budget Agent: {budget_agent.agent_id[:8]}...")
    print()
    
    # Create Orchestrator
    print("3️⃣  Creating Orchestrator Agent...")
    orchestrator = OrchestratorAgent(
        region="us-east-1",
        llm=llm,
        database_url=database_url
    )
    print(f"   ✅ Orchestrator: {orchestrator.agent_id[:8]}...")
    print()
    
    # Register agents with orchestrator
    print("4️⃣  Registering agents with orchestrator...")
    orchestrator.register_agent('fraud', fraud_agent)
    orchestrator.register_agent('budget', budget_agent)
    print()
    
    # Test 1: Check agent status
    print("5️⃣  Checking agent status...")
    statuses = orchestrator.get_agent_status()
    print(f"   Registered agents: {len([s for s in statuses.values() if isinstance(s, dict)])}")
    for agent_id, status in statuses.items():
        if isinstance(status, dict):
            print(f"   - {status['type']:12} ({status['region']:15}) Status: {status['status']}")
    print()
    
    # Test 2: Simple workflow - Budget check only
    print("6️⃣  Test Workflow 1: Simple budget check...")
    
    # Get a sample user
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import NullPool
    
    engine = create_engine(database_url, poolclass=NullPool)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT DISTINCT user_id FROM expenses LIMIT 1"))
        row = result.fetchone()
        user_id = str(row[0]) if row else "user_01"
    engine.dispose()
    
    result1 = orchestrator.execute_workflow(
        user_request="Am I over budget this month?",
        context={'user_id': user_id, 'monthly_budget': 1000.00}
    )
    
    print(f"\n   Workflow Result:")
    print(f"   - Success: {'✅' if result1['success'] else '❌'}")
    print(f"   - Steps executed: {len(result1['steps_executed'])}")
    
    if result1.get('plan'):
        print(f"   - Planned steps:")
        for step in result1['plan'].get('steps', []):
            print(f"     {step['step_number']}. {step['agent']}.{step['action']}")
    
    if result1.get('final_result'):
        synthesis = result1['final_result'].get('synthesis', '')
        if synthesis:
            print(f"\n   Final Response:")
            print(f"   {synthesis[:200]}..." if len(synthesis) > 200 else f"   {synthesis}")
    print()
    
    # Test 3: Complex workflow - Multiple agents
    print("7️⃣  Test Workflow 2: Complex expense audit...")
    
    result2 = orchestrator.execute_workflow(
        user_request="Audit my recent expenses and check my budget status",
        context={'user_id': user_id, 'monthly_budget': 1000.00}
    )
    
    print(f"\n   Workflow Result:")
    print(f"   - Success: {'✅' if result2['success'] else '❌'}")
    print(f"   - Steps executed: {len(result2['steps_executed'])}")
    
    if result2.get('plan'):
        print(f"   - Planned steps:")
        for step in result2['plan'].get('steps', []):
            print(f"     {step['step_number']}. {step['agent']}.{step['action']}")
    
    if result2.get('final_result'):
        synthesis = result2['final_result'].get('synthesis', '')
        if synthesis:
            print(f"\n   Final Response:")
            # Show first 300 chars
            lines = synthesis.split('\n')
            for line in lines[:5]:  # First 5 lines
                print(f"   {line}")
            if len(lines) > 5:
                print(f"   ... ({len(lines)-5} more lines)")
    print()
    
    # Summary
    print("="*70)
    print("🎉 Orchestrator test completed!")
    print()
    print("Summary:")
    print(f"  • Orchestrator created and working")
    print(f"  • {len(orchestrator.available_agents)} agents registered")
    print(f"  • Executed {len(result1['steps_executed']) + len(result2['steps_executed'])} total workflow steps")
    print(f"  • Multi-agent coordination successful: {'✅' if result2['success'] else '❌'}")
    print()
    print("Next steps:")
    print("  - Add more agents (Receipt, Analyst)")
    print("  - Build real-time agent dashboard")
    print("  - Create WebSocket for live updates")
    print("  - Integrate with chaos demo for multi-region testing")
    
    return result1['success'] and result2['success']


if __name__ == "__main__":
    success = test_orchestrator()
    exit(0 if success else 1)
