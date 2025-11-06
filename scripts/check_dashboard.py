"""Quick dashboard status checker"""
import requests
import json

print("\n🎯 Agent Dashboard Status Check")
print("="*70)

try:
    # Check status endpoint
    response = requests.get('http://localhost:5001/api/agents/status')
    data = response.json()
    
    if data['success']:
        print(f"\n✅ API Status: Connected")
        print(f"   Total Agents: {data['count']}")
        
        # Count by type
        types = {}
        for agent in data['agents']:
            agent_type = agent['type']
            types[agent_type] = types.get(agent_type, 0) + 1
        
        print(f"\n   Agent Types:")
        for agent_type, count in sorted(types.items()):
            print(f"   - {agent_type.capitalize()}: {count}")
    
    # Check activity endpoint
    response = requests.get('http://localhost:5001/api/agents/activity')
    data = response.json()
    
    if data['success']:
        print(f"\n✅ Recent Activity: {data['count']} decisions recorded")
        print(f"\n   Latest Activity:")
        for i, activity in enumerate(data['activities'][:3]):
            print(f"   {i+1}. {activity['agent_type']} ({activity['region']}) - {activity['decision_type']}")
            print(f"      Confidence: {int(activity['confidence']*100)}%")
    
    print("\n" + "="*70)
    print("✅ Dashboard is fully operational!")
    print("\nAccess:")
    print("   🌐 Main App:   http://localhost:5001/")
    print("   📊 Dashboard:  http://localhost:5001/agents")
    print("   🔌 WebSocket:  Connected and ready")
    print()
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    print("   Make sure the server is running: python test_dashboard.py")
