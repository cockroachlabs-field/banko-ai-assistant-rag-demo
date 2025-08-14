from flask import Flask, request, render_template, redirect, url_for, session
from openai import OpenAI
from config import API_KEY
from sqlalchemy import create_engine, text
from sentence_transformers import SentenceTransformer
import numpy as np
import json
import os

# Import AI service modules
import sys
sys.path.append('AWS Bedrock')
from aws_bedrock import search_expenses as aws_search_expenses, RAG_response as aws_rag_response

# Import cache manager for monitoring
try:
    from cache_manager import cache_manager
except ImportError:
    print("⚠️ Cache manager not available")
    cache_manager = None

# Import Watsonx integration (with fallback if not configured)
try:
    from watsonx.watsonx import search_expenses as watsonx_search_expenses, RAG_response as watsonx_rag_response
    WATSONX_AVAILABLE = True
except ImportError as e:
    print(f"Watsonx integration not available: {e}")
    WATSONX_AVAILABLE = False

app = Flask(__name__)
client = OpenAI(api_key=API_KEY)
app.secret_key = 'your_secret_key'

# Configuration for AI service selection
# Can be set via environment variable or defaults to 'aws'
AI_SERVICE = os.getenv('AI_SERVICE', 'aws').lower()

# Database Configuration
DB_URI = os.getenv('DATABASE_URL', "cockroachdb://root@localhost:26257/defaultdb?sslmode=disable")

def check_database_connection():
    """
    Check if the database is accessible and has the required table.
    
    Returns:
        tuple: (success: bool, message: str, table_exists: bool, record_count: int)
    """
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(DB_URI)
        
        with engine.connect() as conn:
            # Test basic connection
            result = conn.execute(text('SELECT version()'))
            version = result.fetchone()[0]
            
            # Check if expenses table exists
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = 'expenses'
            """))
            table_exists = result.fetchone() is not None
            
            record_count = 0
            if table_exists:
                result = conn.execute(text('SELECT COUNT(*) FROM expenses'))
                record_count = result.fetchone()[0]
            
            return True, f"Connected to {version.split()[1]}", table_exists, record_count
            
    except Exception as e:
        return False, f"Database connection failed: {str(e)}", False, 0

def auto_setup_data_if_needed():
    """
    Automatically set up data if the database is empty or has very few records.
    This integrates seamlessly into the app startup.
    """
    try:
        db_connected, db_message, table_exists, record_count = check_database_connection()
        
        if not db_connected:
            print(f"❌ Database connection failed: {db_message}")
            return False
            
        # Create table if it doesn't exist
        if not table_exists:
            print("🔧 Creating expenses table...")
            try:
                import subprocess
                result = subprocess.run([sys.executable, 'vector_search/create_table.py'], 
                                      capture_output=True, text=True, cwd='.')
                if result.returncode == 0:
                    print("✅ Expenses table created successfully")
                    # Re-check the database status
                    db_connected, db_message, table_exists, record_count = check_database_connection()
                else:
                    print(f"❌ Failed to create table: {result.stderr}")
                    return False
            except Exception as e:
                print(f"❌ Table creation error: {e}")
                return False
            
        # If we have very few records, offer to generate more
        if record_count < 100:
            print(f"🔍 Found {record_count} expense records")
            print("🎯 Generating sample data for better demo experience...")
            
            try:
                # Use the unified data generator
                sys.path.append('vector_search')
                from dynamic_expenses import DynamicExpenseGenerator
                
                generator = DynamicExpenseGenerator()
                
                # Generate a reasonable amount for demos (5K records)
                generator.generate_expenses(5000)
                
                print("✅ Generated 5,000 realistic expense records")
                return True
                
            except ImportError:
                # Fallback to legacy CSV method
                print("📁 Using legacy data loading...")
                try:
                    from vector_search.insert_data import read_csv_data, insert_content
                    if os.path.exists('vector_search/expense_data.csv'):
                        data = read_csv_data('vector_search/expense_data.csv')
                        insert_content(data)
                        print("✅ Loaded legacy sample data")
                        return True
                except Exception as e:
                    print(f"⚠️  Could not load sample data: {e}")
                    return False
            except Exception as e:
                print(f"⚠️  Data generation failed: {e}")
                return False
        
        return True
        
    except Exception as e:
        print(f"⚠️  Auto-setup error: {e}")
        return False

def get_ai_service_functions():
    """
    Get the appropriate search and RAG functions based on the configured AI service.
    
    Returns:
        tuple: (search_function, rag_function, service_name)
    """
    if AI_SERVICE == 'watsonx' and WATSONX_AVAILABLE:
        return watsonx_search_expenses, watsonx_rag_response, 'IBM Watsonx'
    else:
        # Default to AWS Bedrock
        return aws_search_expenses, aws_rag_response, 'AWS Bedrock'

@app.route('/')
def root():
    return redirect(url_for('chat'))

@app.route('/banko', methods=['GET', 'POST'])
def chat():
    session['chat'] = []
    if 'chat' not in session:
        session['chat'] = []  # Initialize chat history if it doesn't exist
    
    # Get the configured AI service functions
    search_function, rag_function, service_name = get_ai_service_functions()
    
    # Get AI provider info for display
    ai_provider = {
        'name': service_name,
        'current_service': AI_SERVICE.upper(),
        'icon': '🧠' if AI_SERVICE.lower() == 'watsonx' else '☁️'
    }
    
    if request.method == 'POST':
        # Handle both 'message' and 'user_input' field names for compatibility
        user_message = request.form.get('user_input') or request.form.get('message')
        response_language = request.form.get('response_language', 'en-US')
        
        if user_message:
            session['chat'].append({'text': user_message, 'class': 'User'})
            prompt = user_message
            
            # Map language codes to language names for AI prompt
            language_map = {
                'en-US': 'English',
                'es-ES': 'Spanish', 
                'fr-FR': 'French',
                'de-DE': 'German',
                'it-IT': 'Italian',
                'pt-PT': 'Portuguese',
                'ja-JP': 'Japanese',
                'ko-KR': 'Korean',
                'zh-CN': 'Chinese',
                'hi-IN': 'Hindi'
            }
            
            target_language = language_map.get(response_language, 'English')
            
            try:
                # Search for relevant expenses using the configured AI service
                result = search_function(prompt)
                print(f"Using {service_name} for response generation in {target_language}")
                
                # Generate RAG response with language preference
                if target_language != 'English':
                    enhanced_prompt = f"{user_message}\n\nPlease respond in {target_language}."
                    rag_response = rag_function(enhanced_prompt, result)
                else:
                    rag_response = rag_function(user_message, result)
                    
                print(f"Response from {service_name}: {rag_response}")
                
                session['chat'].append({'text': rag_response, 'class': 'Assistant'})
                
            except Exception as e:
                error_message = f"Sorry, I'm experiencing technical difficulties with {service_name}. Please try again later."
                print(f"Error with {service_name}: {str(e)}")
                session['chat'].append({'text': error_message, 'class': 'Assistant'})
                
    return render_template('index.html', chat=session['chat'], ai_provider=ai_provider, current_page='banko')

@app.route('/home')
def dashboard():
    return render_template('dashboard.html', current_page='home')

@app.route('/savings')
def savings():
    return render_template('dashboard.html', current_page='savings')

@app.route('/wallet')
def wallet():
    return render_template('dashboard.html', current_page='wallet')

@app.route('/credit-card')
def credit_card():
    return render_template('dashboard.html', current_page='credit-card')

@app.route('/statements')
def statements():
    return render_template('dashboard.html', current_page='statements')

@app.route('/benefits')
def benefits():
    return render_template('dashboard.html', current_page='benefits')

@app.route('/settings')
def settings():
    return render_template('dashboard.html', current_page='settings')

@app.route('/ai-status')
def ai_status():
    """
    Endpoint to check the status of AI services and database.
    Useful for debugging and service monitoring.
    """
    # Check database status
    db_connected, db_message, table_exists, record_count = check_database_connection()
    
    status = {
        'current_service': AI_SERVICE,
        'watsonx_available': WATSONX_AVAILABLE,
        'aws_bedrock_available': True,  # Always available as it's the default
        'database': {
            'connected': db_connected,
            'status': db_message,
            'expenses_table_exists': table_exists,
            'record_count': record_count,
            'connection_string': DB_URI.replace("@", "@***") if db_connected else "Not connected"
        }
    }
    
    # Test Watsonx connection if available
    if WATSONX_AVAILABLE:
        try:
            from watsonx.watsonx import test_watsonx_connection
            watsonx_success, watsonx_message = test_watsonx_connection()
            status['watsonx_status'] = {
                'connected': watsonx_success,
                'message': watsonx_message
            }
        except Exception as e:
            status['watsonx_status'] = {
                'connected': False,
                'message': f"Connection test failed: {str(e)}"
            }
    
    # Get active service info
    _, _, service_name = get_ai_service_functions()
    status['active_service_name'] = service_name
    status['caching_enabled'] = cache_manager is not None
    
    return status

@app.route('/cache-stats')
def cache_stats():
    """Endpoint to view cache performance statistics"""
    if not cache_manager:
        return {'error': 'Cache manager not available'}, 503
    
    try:
        stats = cache_manager.get_cache_stats(hours=24)
        
        # Calculate overall metrics
        total_requests = 0
        total_hits = 0
        total_tokens_saved = stats.get('total_tokens_saved', 0)
        
        for cache_type, cache_stats in stats.items():
            if cache_type != 'total_tokens_saved':
                total_requests += cache_stats.get('hits', 0) + cache_stats.get('misses', 0)
                total_hits += cache_stats.get('hits', 0)
        
        overall_hit_rate = total_hits / total_requests if total_requests > 0 else 0
        
        response = {
            'cache_enabled': True,
            'time_period': '24 hours',
            'overall_metrics': {
                'total_requests': total_requests,
                'total_hits': total_hits,
                'overall_hit_rate': round(overall_hit_rate * 100, 2),
                'total_tokens_saved': total_tokens_saved,
                                            'estimated_cost_savings_usd': round(total_tokens_saved * 0.00002, 4)  # Rough estimate
            },
            'cache_details': stats
        }
        
        return response
        
    except Exception as e:
        return {'error': f'Failed to get cache stats: {str(e)}'}, 500

@app.route('/cache-cleanup', methods=['POST'])
def cache_cleanup():
    """Endpoint to manually trigger cache cleanup"""
    if not cache_manager:
        return {'error': 'Cache manager not available'}, 503
    
    try:
        cache_manager.cleanup_expired_cache()
        return {'message': 'Cache cleanup completed successfully'}
    except Exception as e:
        return {'error': f'Cache cleanup failed: {str(e)}'}, 500

@app.route('/diagnostics/watsonx')
def watsonx_diagnostics():
    """Watsonx connection diagnostics endpoint"""
    import socket
    import requests
    
    results = {
        'dns_test': {'status': 'unknown', 'message': ''},
        'http_test': {'status': 'unknown', 'message': ''},
        'config_test': {'status': 'unknown', 'message': ''},
        'overall_status': 'unknown',
        'suggestions': []
    }
    
    try:
        # Test DNS resolution
        socket.gethostbyname("iam.cloud.ibm.com")
        results['dns_test'] = {'status': 'success', 'message': 'DNS resolution successful'}
        
        # Test HTTP connectivity
        response = requests.get("https://iam.cloud.ibm.com", timeout=10)
        results['http_test'] = {'status': 'success', 'message': f'HTTP connectivity successful (status: {response.status_code})'}
        
        # Test configuration
        if WATSONX_AVAILABLE:
            results['config_test'] = {'status': 'success', 'message': 'Watsonx configuration available'}
            results['overall_status'] = 'healthy'
        else:
            results['config_test'] = {'status': 'warning', 'message': 'Watsonx not configured or unavailable'}
            results['overall_status'] = 'degraded'
            results['suggestions'].append('Configure WATSONX_API_KEY environment variable')
            
    except socket.gaierror as e:
        results['dns_test'] = {'status': 'error', 'message': f'DNS resolution failed: {str(e)}'}
        results['overall_status'] = 'unhealthy'
        results['suggestions'].extend([
            'Check your internet connection',
            'Verify DNS settings',
            'Try: nslookup iam.cloud.ibm.com'
        ])
    except requests.exceptions.ConnectionError as e:
        results['http_test'] = {'status': 'error', 'message': f'Connection failed: {str(e)}'}
        results['overall_status'] = 'unhealthy'
        results['suggestions'].extend([
            'Check firewall settings',
            'Verify network connectivity',
            'Switch to AWS Bedrock: export AI_SERVICE=aws'
        ])
    except requests.exceptions.Timeout as e:
        results['http_test'] = {'status': 'error', 'message': f'Connection timeout: {str(e)}'}
        results['overall_status'] = 'unhealthy'
        results['suggestions'].append('Network is slow or IBM Cloud services are experiencing issues')
    except Exception as e:
        results['overall_status'] = 'error'
        results['error'] = str(e)
    
    return results

if __name__ == '__main__':
    print("🏦 === Banko AI Assistant Starting === 🏦")
    print(f"🤖 AI Service: {AI_SERVICE}")
    print(f"🔧 Watsonx Available: {WATSONX_AVAILABLE}")
    
    # Get service info for startup
    _, _, service_name = get_ai_service_functions()
    print(f"✅ Active AI Service: {service_name}")
    print("=" * 45)
    
    # Auto-setup data if needed (seamless integration)
    print("🔍 Checking database setup...")
    auto_setup_data_if_needed()
    
    # Get port from environment variable or default to 5000
    port = int(os.environ.get("PORT", 5000))
    
    print(f"🚀 Starting server on http://localhost:{port}")
    print("🎉 Banko AI is ready to help with your finances!")
    print("=" * 45)

    # Run the app on all interfaces, using the configured port
    app.run(host='0.0.0.0', port=port, debug=True)
