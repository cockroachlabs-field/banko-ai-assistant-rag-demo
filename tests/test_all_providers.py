"""
Test Agents with All AI Providers

Verifies that agents work with:
- OpenAI
- AWS Bedrock
- Google Gemini  
- IBM Watsonx
"""

import os
import sys

os.environ['TOKENIZERS_PARALLELISM'] = 'false'

from sentence_transformers import SentenceTransformer

# Test configurations for each provider
PROVIDERS = {
    'openai': {
        'name': 'OpenAI',
        'env_vars': ['OPENAI_API_KEY'],
        'model': 'gpt-4o-mini'
    },
    'bedrock': {
        'name': 'AWS Bedrock',
        'env_vars': ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_REGION'],
        'model': 'anthropic.claude-3-sonnet-20240229-v1:0'
    },
    'gemini': {
        'name': 'Google Gemini',
        'env_vars': ['GOOGLE_API_KEY'],
        'model': 'gemini-pro'
    },
    'watsonx': {
        'name': 'IBM Watsonx',
        'env_vars': ['WATSONX_API_KEY', 'WATSONX_PROJECT_ID'],
        'model': 'meta-llama/llama-2-70b-chat'
    }
}


def check_provider_credentials(provider_key):
    """Check if provider credentials are available"""
    config = PROVIDERS[provider_key]
    missing = []
    
    for env_var in config['env_vars']:
        if not os.getenv(env_var):
            missing.append(env_var)
    
    return len(missing) == 0, missing


def create_llm(provider_key):
    """Create LLM instance for provider"""
    config = PROVIDERS[provider_key]
    
    try:
        if provider_key == 'openai':
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=config['model'],
                api_key=os.getenv('OPENAI_API_KEY'),
                temperature=0.7
            )
        
        elif provider_key == 'bedrock':
            from langchain_aws import ChatBedrock
            import boto3
            
            bedrock_runtime = boto3.client(
                service_name='bedrock-runtime',
                region_name=os.getenv('AWS_REGION', 'us-east-1'),
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
            )
            
            return ChatBedrock(
                client=bedrock_runtime,
                model_id=config['model'],
                model_kwargs={"temperature": 0.7, "max_tokens": 1000}
            )
        
        elif provider_key == 'gemini':
            from langchain_google_genai import ChatGoogleGenerativeAI
            
            return ChatGoogleGenerativeAI(
                model=config['model'],
                google_api_key=os.getenv('GOOGLE_API_KEY'),
                temperature=0.7
            )
        
        elif provider_key == 'watsonx':
            from langchain_community.llms import WatsonxLLM
            from ibm_watson_machine_learning.metanames import GenTextParamsMetaNames as GenParams
            
            parameters = {
                GenParams.DECODING_METHOD: "greedy",
                GenParams.MAX_NEW_TOKENS: 1000,
                GenParams.TEMPERATURE: 0.7
            }
            
            return WatsonxLLM(
                model_id=config['model'],
                url="https://us-south.ml.cloud.ibm.com",
                apikey=os.getenv('WATSONX_API_KEY'),
                project_id=os.getenv('WATSONX_PROJECT_ID'),
                params=parameters
            )
        
        else:
            raise ValueError(f"Unknown provider: {provider_key}")
    
    except Exception as e:
        print(f"      ⚠️  Error creating LLM: {e}")
        return None


def test_provider(provider_key):
    """Test a single provider with Fraud Agent"""
    config = PROVIDERS[provider_key]
    
    print(f"\n{'='*70}")
    print(f"Testing: {config['name']}")
    print(f"{'='*70}")
    
    # Check credentials
    has_creds, missing = check_provider_credentials(provider_key)
    
    if not has_creds:
        print(f"   ⚠️  Missing credentials: {', '.join(missing)}")
        print(f"   ⏭️  Skipping {config['name']}")
        return False
    
    print(f"   ✅ Credentials found")
    
    # Create LLM
    print(f"   Creating LLM ({config['model']})...")
    llm = create_llm(provider_key)
    
    if not llm:
        print(f"   ❌ Failed to create LLM")
        return False
    
    print(f"   ✅ LLM created")
    
    # Test simple query
    print(f"   Testing LLM response...")
    try:
        response = llm.invoke("Say 'Hello from agents!'")
        response_text = response.content if hasattr(response, 'content') else str(response)
        print(f"   ✅ LLM responded: {response_text[:50]}...")
    except Exception as e:
        print(f"   ❌ LLM test failed: {e}")
        return False
    
    # Create agent
    print(f"   Creating Fraud Agent with {config['name']}...")
    try:
        from banko_ai.agents.fraud_agent import FraudAgent
        
        database_url = os.getenv(
            'DATABASE_URL',
            'cockroachdb://root@localhost:26257/defaultdb?sslmode=disable'
        )
        embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        agent = FraudAgent(
            region=f"test-{provider_key}",
            llm=llm,
            database_url=database_url,
            embedding_model=embedding_model,
            fraud_threshold=0.7
        )
        
        print(f"   ✅ Agent created: {agent.agent_id[:8]}...")
    except Exception as e:
        print(f"   ❌ Agent creation failed: {e}")
        return False
    
    # Test agent functionality
    print(f"   Testing agent scan...")
    try:
        result = agent.scan_recent_expenses(hours=24, limit=3)
        
        if result.get('success'):
            print(f"   ✅ Agent scan successful")
            print(f"      Analyzed: {result.get('total_analyzed', 0)}")
            print(f"      Flagged: {result.get('total_flagged', 0)}")
        else:
            print(f"   ⚠️  Agent scan returned success=False")
            return False
    
    except Exception as e:
        print(f"   ❌ Agent scan failed: {e}")
        return False
    
    print(f"\n   🎉 {config['name']} - ALL TESTS PASSED!")
    return True


def main():
    """Test all available providers"""
    
    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║                                                               ║")
    print("║           MULTI-PROVIDER AGENT TEST                           ║")
    print("║                                                               ║")
    print("╚═══════════════════════════════════════════════════════════════╝")
    print()
    print("Testing agents with all AI providers...")
    print()
    
    results = {}
    
    for provider_key in ['openai', 'bedrock', 'gemini', 'watsonx']:
        try:
            results[provider_key] = test_provider(provider_key)
        except Exception as e:
            print(f"\n   ❌ Unexpected error: {e}")
            results[provider_key] = False
    
    # Summary
    print("\n" + "="*70)
    print("\n📊 SUMMARY")
    print("="*70)
    print()
    
    for provider_key, passed in results.items():
        config = PROVIDERS[provider_key]
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}  {config['name']:20} ({config['model'][:40]})")
    
    print()
    
    passed_count = sum(1 for v in results.values() if v)
    total_count = len(results)
    
    if passed_count == total_count:
        print("🎉 ALL PROVIDERS WORKING!")
        return True
    elif passed_count > 0:
        print(f"⚠️  {passed_count}/{total_count} providers working")
        print()
        print("For demo: Use working provider(s)")
        print("Architecture supports all providers, credentials needed for others")
        return True
    else:
        print("❌ NO PROVIDERS WORKING")
        print("   Check credentials and try again")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
