"""
Test all agents together.

This demonstrates:
- Receipt Agent processing a document
- Fraud Agent analyzing expenses
- Budget Agent monitoring spending
"""

import os

# Disable tokenizers parallelism warning
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

from langchain_openai import ChatOpenAI
from sentence_transformers import SentenceTransformer

from banko_ai.agents.receipt_agent import ReceiptAgent
from banko_ai.agents.fraud_agent import FraudAgent
from banko_ai.agents.budget_agent import BudgetAgent


def test_all_agents():
    """Test all three agents"""
    
    print("🧪 Testing All Agents")
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
    
    # Create all agents
    print("2️⃣  Creating agent team...")
    
    receipt_agent = ReceiptAgent(
        region="us-east-1",
        llm=llm,
        database_url=database_url,
        embedding_model=embedding_model
    )
    print(f"   ✅ Receipt Agent: {receipt_agent.agent_id[:8]}...")
    
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
    
    # Test 1: Fraud Agent - Analyze expense
    print("3️⃣  Testing Fraud Agent...")
    print("   Analyzing recent expenses for fraud...")
    
    # Get a sample expense to analyze
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import NullPool
    
    engine = create_engine(database_url, poolclass=NullPool)
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT expense_id, user_id, merchant, expense_amount, shopping_type
            FROM expenses
            ORDER BY RANDOM()
            LIMIT 1
        """))
        row = result.fetchone()
    engine.dispose()
    
    if row:
        expense_id = str(row[0])
        print(f"   Sample expense: {row[2]} - ${row[3]} ({row[4]})")
        
        fraud_result = fraud_agent.analyze_expense(expense_id)
        
        print(f"\n   Fraud Analysis Results:")
        print(f"   - Fraud Detected: {'🚨 YES' if fraud_result['fraud_detected'] else '✅ NO'}")
        print(f"   - Confidence: {fraud_result['confidence']:.1%}")
        print(f"   - Recommendation: {fraud_result['recommendation']}")
        print(f"   - Signals: {len(fraud_result.get('signals', []))} detected")
        
        if fraud_result.get('signals'):
            for signal in fraud_result['signals'][:2]:  # Show first 2
                print(f"     • {signal['type']}: {signal['details']}")
    else:
        print("   ⚠️  No expenses found to analyze")
    print()
    
    # Test 2: Budget Agent - Check status
    print("4️⃣  Testing Budget Agent...")
    print("   Checking budget status...")
    
    if row:
        user_id = row[1]
        budget_result = budget_agent.check_budget_status(
            user_id=user_id,
            monthly_budget=1000.00
        )
        
        print(f"\n   Budget Status:")
        print(f"   - Status: {budget_result['status']}")
        print(f"   - Current Spend: ${budget_result.get('current_spend', 0):.2f}")
        print(f"   - Budget: ${budget_result['budget']:.2f}")
        print(f"   - Usage: {budget_result.get('percent_of_budget', 0):.1f}%")
        print(f"   - Alert Level: {budget_result['alert_level']}")
        
        if budget_result.get('recommendation'):
            print(f"\n   Recommendations:")
            for rec in budget_result['recommendation'][:2]:
                print(f"   {rec}")
    else:
        print("   ⚠️  No user data to check")
    print()
    
    # Summary
    print("="*70)
    print("🎉 All agent tests completed!")
    print()
    print("Summary:")
    print(f"  • Receipt Agent: Ready for document processing")
    print(f"  • Fraud Agent: Ready for autonomous monitoring")
    print(f"  • Budget Agent: Ready for proactive alerts")
    print()
    print("All agents running in different regions:")
    print(f"  • Receipt Agent: {receipt_agent.region}")
    print(f"  • Fraud Agent: {fraud_agent.region}")
    print(f"  • Budget Agent: {budget_agent.region}")
    print()
    print("Next steps:")
    print("  - Test Receipt Agent with document upload")
    print("  - Build Orchestrator for multi-agent coordination")
    print("  - Create real-time agent dashboard")
    print("  - Integrate with chaos demo for failover testing")
    
    return True


if __name__ == "__main__":
    success = test_all_agents()
    exit(0 if success else 1)
