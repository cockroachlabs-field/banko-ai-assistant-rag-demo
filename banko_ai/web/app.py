"""
Main Flask application for Banko AI Assistant.

This module creates and configures the Flask application with all routes and functionality.
"""

import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from sqlalchemy import create_engine, text

# Apply CockroachDB version parsing workaround before any database imports
from sqlalchemy.dialects.postgresql.base import PGDialect
original_get_server_version_info = PGDialect._get_server_version_info

def patched_get_server_version_info(self, connection):
    try:
        return original_get_server_version_info(self, connection)
    except Exception:
        return (25, 3, 0)

PGDialect._get_server_version_info = patched_get_server_version_info

from ..config.settings import get_config
from ..ai_providers.factory import AIProviderFactory
from ..vector_search.search import VectorSearchEngine
from ..vector_search.generator import EnhancedExpenseGenerator
from ..utils.cache_manager import BankoCacheManager
from .auth import UserManager


def get_provider_display_info(ai_service, ai_provider=None, current_model=None, connection_status=None):
    """Get display information for the current AI provider including proper icons."""
    service = ai_service.lower()
    
    # Provider-specific configurations
    provider_configs = {
        'watsonx': {
            'name': 'IBM Watsonx',
            'icon_file': 'watsonx-icon.svg',
            'icon_alt': 'IBM Watsonx'
        },
        'gemini': {
            'name': 'Google Gemini',
            'icon_file': 'google-gemini-icon.svg',
            'icon_alt': 'Google Gemini'
        },
        'aws': {
            'name': 'AWS Bedrock',
            'icon_file': 'aws-bedrock-icon.svg',
            'icon_alt': 'AWS Bedrock'
        },
        'openai': {
            'name': 'OpenAI',
            'icon_file': 'openai-icon.svg',  # Fallback to watsonx icon for now
            'icon_alt': 'OpenAI'
        }
    }
    
    # Get provider config or use default
    config = provider_configs.get(service, {
        'name': 'IBM Watsonx',
        'icon_file': 'watsonx-icon.svg',
        'icon_alt': 'AI Provider'
    })
    
    # Get current model if not provided
    if current_model is None and ai_provider:
        current_model = getattr(ai_provider, 'current_model', 'Unknown')
    
    # Get connection status if not provided
    if connection_status is None and ai_provider:
        # Check if we have API credentials without making a call
        has_credentials = bool(
            getattr(ai_provider, 'api_key', None) or 
            getattr(ai_provider, 'access_key_id', None) or
            getattr(ai_provider, 'project_id', None)
        )
        connection_status = 'connected' if has_credentials else 'demo'
    
    return {
        'name': config['name'],
        'current_service': ai_service.upper(),
        'current_model': current_model or 'Unknown',
        'status': connection_status or 'disconnected',
        'icon_file': config['icon_file'],
        'icon_alt': config['icon_alt'],
        'icon': '🧠'  # Keep emoji as fallback
    }


def check_database_connection(database_url: str):
    """
    Check if the database is accessible and has the required table.
    Matches the original app.py implementation.
    
    Returns:
        tuple: (success: bool, message: str, table_exists: bool, record_count: int)
    """
    try:
        engine = create_engine(database_url)
        
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


def auto_setup_data_if_needed(database_url: str):
    """
    Automatically set up data if the database is empty or has very few records.
    This integrates seamlessly into the app startup - matches original app.py.
    """
    try:
        db_connected, db_message, table_exists, record_count = check_database_connection(database_url)
        
        if not db_connected:
            print(f"❌ Database connection failed: {db_message}")
            return False
            
        # Create table if it doesn't exist
        if not table_exists:
            print("🔧 Creating expenses table...")
            try:
                # Use the unified DatabaseManager
                from ..utils.database import DatabaseManager
                db_manager = DatabaseManager(database_url)
                
                if db_manager.create_tables():
                    print("✅ Expenses table created successfully")
                    # Re-check the database status
                    db_connected, db_message, table_exists, record_count = check_database_connection(database_url)
                else:
                    print(f"❌ Failed to create table")
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
                from ..vector_search.generator import EnhancedExpenseGenerator
                
                generator = EnhancedExpenseGenerator(database_url)
                
                # Generate a reasonable amount for demos (5K records)
                generator.generate_and_save(5000, user_id=None, clear_existing=False)
                
                print("✅ Generated 5,000 realistic expense records")
                return True
                
            except Exception as e:
                print(f"⚠️  Data generation failed: {e}")
                return False
        
        return True
        
    except Exception as e:
        print(f"⚠️  Auto-setup error: {e}")
        return False


def create_app() -> Flask:
    """Create and configure the Flask application."""
    # Get the directory containing this file
    # Set up template and static directories
    # Use package-relative paths that work both in development and PyPI installation
    current_dir = os.path.dirname(os.path.abspath(__file__))
    package_dir = os.path.dirname(current_dir)  # Go up to banko_ai package root
    
    template_dir = os.path.join(package_dir, 'templates')
    static_dir = os.path.join(package_dir, 'static')
    
    # Ensure directories exist
    if not os.path.exists(template_dir):
        # Fallback for PyPI installation
        import banko_ai
        package_root = os.path.dirname(banko_ai.__file__)
        template_dir = os.path.join(package_root, 'templates')
        static_dir = os.path.join(package_root, 'static')
    
    app = Flask(__name__, 
                template_folder=template_dir,
                static_folder=static_dir)
    
    # Load configuration
    config = get_config()
    app.config['SECRET_KEY'] = config.secret_key
    app.config['DEBUG'] = config.debug
    
    # Initialize components
    user_manager = UserManager()
    cache_manager = BankoCacheManager()
    search_engine = VectorSearchEngine(config.database_url, cache_manager)
    expense_generator = EnhancedExpenseGenerator(config.database_url)
    
    # Initialize AI provider
    try:
        ai_config = config.get_ai_config()
        ai_provider = AIProviderFactory.create_provider(
            config.ai_service, 
            ai_config[config.ai_service],
            cache_manager
        )
    except Exception as e:
        print(f"Warning: Could not initialize AI provider: {e}")
        ai_provider = None
    
    # Auto-setup data if needed (matching original app.py)
    print("🔍 Checking database setup...")
    auto_setup_data_if_needed(config.database_url)
    
    @app.route('/')
    def index():
        """Main application page."""
        # Ensure user is logged in
        user_id = user_manager.get_current_user()['id'] if user_manager.get_current_user() else None
        current_user = user_manager.get_current_user()
        
        # Get AI provider info for display
        ai_provider_display = get_provider_display_info(config.ai_service, ai_provider)
        
        return render_template('index.html', 
                             user=current_user,
                             ai_provider=ai_provider_display)
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """User login page."""
        if request.method == 'POST':
            username = request.form.get('username')
            if username:
                user_id = user_manager.create_user(username)
                user_manager.login_user(user_id)
                return redirect(url_for('index'))
        
        return render_template('login.html')
    
    @app.route('/logout')
    def logout():
        """User logout."""
        user_manager.logout_user()
        return redirect(url_for('index'))
    
    @app.route('/api/search', methods=['POST'])
    def api_search():
        """API endpoint for expense search."""
        try:
            data = request.get_json()
            query = data.get('query', '')
            limit = data.get('limit', 10)
            threshold = data.get('threshold', 0.7)
            # Use original simple logic - no user filtering
            results = search_engine.search_expenses(
                query=query,
                user_id=None,  # No user filtering like original
                limit=limit,
                threshold=threshold
            )
            
            # Convert to serializable format
            search_results = []
            for result in results:
                search_results.append({
                    'expense_id': result.expense_id,
                    'user_id': result.user_id,
                    'description': result.description,
                    'merchant': result.merchant,
                    'amount': result.amount,
                    'date': result.date,
                    'similarity_score': result.similarity_score,
                    'metadata': result.metadata
                })
            
            return jsonify({
                'success': True,
                'results': search_results,
                'query': query,
                'user_id': None
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/rag', methods=['POST'])
    def api_rag():
        """API endpoint for RAG responses."""
        try:
            if not ai_provider:
                return jsonify({
                    'success': False,
                    'error': 'AI provider not available'
                }), 500
            
            data = request.get_json()
            query = data.get('query', '')
            language = data.get('language', 'en')
            # Use original simple logic - no user filtering
            search_results = search_engine.search_expenses(
                query=query,
                user_id=None,  # No user filtering like original
                limit=5,
                threshold=0.7
            )
            
            # Generate RAG response - use original simple logic
            rag_response = ai_provider.generate_rag_response(
                query=query,
                context=search_results,
                user_id=None,  # No user filtering like original
                language=language
            )
            
            return jsonify({
                'success': True,
                'response': rag_response.response,
                'sources': [
                    {
                        'expense_id': result.expense_id,
                        'description': result.description,
                        'merchant': result.merchant,
                        'amount': result.amount,
                        'similarity_score': result.similarity_score
                    }
                    for result in rag_response.sources
                ],
                'metadata': rag_response.metadata
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/generate-data', methods=['POST'])
    def api_generate_data():
        """API endpoint for generating sample data."""
        try:
            data = request.get_json()
            count = data.get('count', 1000)
            user_id = user_manager.get_current_user()['id'] if user_manager.is_logged_in() else None
            clear_existing = data.get('clear_existing', False)
            
            # Generate expenses
            generated_count = expense_generator.generate_and_save(
                count=count,
                user_id=user_id,
                clear_existing=clear_existing
            )
            
            return jsonify({
                'success': True,
                'generated_count': generated_count,
                'message': f'Generated {generated_count} expense records'
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/user-summary')
    def api_user_summary():
        """API endpoint for user spending summary."""
        try:
            if not user_manager.is_logged_in():
                return jsonify({
                    'success': False,
                    'error': 'User not logged in'
                }), 401
            
            user_id = user_manager.get_current_user()['id']
            summary = search_engine.get_user_spending_summary(user_id)
            
            return jsonify({
                'success': True,
                'summary': summary
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/ai-providers')
    def api_ai_providers():
        """API endpoint for available AI providers."""
        try:
            providers = AIProviderFactory.get_available_providers()
            current_provider = config.ai_service
            
            return jsonify({
                'success': True,
                'providers': providers,
                'current': current_provider
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/models')
    def api_models():
        """API endpoint for available models for current provider."""
        try:
            if not ai_provider:
                return jsonify({
                    'success': False,
                    'error': 'AI provider not available'
                }), 500
            
            available_models = ai_provider.get_available_models()
            current_model = ai_provider.get_current_model()
            
            return jsonify({
                'success': True,
                'models': available_models,
                'current': current_model,
                'provider': config.ai_service
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/models', methods=['POST'])
    def api_set_model():
        """API endpoint for switching models."""
        try:
            if not ai_provider:
                return jsonify({
                    'success': False,
                    'error': 'AI provider not available'
                }), 500
            
            data = request.get_json()
            model = data.get('model')
            
            if not model:
                return jsonify({
                    'success': False,
                    'error': 'Model name is required'
                }), 400
            
            success = ai_provider.set_model(model)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': f'Switched to {model}',
                    'current_model': ai_provider.get_current_model()
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'Model {model} is not available'
                }), 400
                
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/health')
    def api_health():
        """Health check endpoint."""
        try:
            # Check database connection
            engine = create_engine(config.database_url)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            # Check AI provider
            ai_status = "unknown"
            current_model = "unknown"
            ai_provider_available = False
            if ai_provider:
                ai_provider_available = True
                ai_status = "connected" if ai_provider.test_connection() else "disconnected"
                current_model = ai_provider.get_current_model()
            
            return jsonify({
                'success': True,
                'database': 'connected',
                'ai_provider': ai_status,
                'ai_service': config.ai_service,
                'current_model': current_model,
                'ai_provider_available': ai_provider_available
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/banko', methods=['GET', 'POST'])
    def chat():
        """Main chat interface - using original simple logic."""
        # Clear chat history on GET request (fresh start)
        if request.method == 'GET':
            session['chat'] = []
        elif 'chat' not in session:
            session['chat'] = []
        
        # Get AI provider info for display
        ai_provider_display = get_provider_display_info(config.ai_service, ai_provider)
        
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
                    # Use simple search that matches original implementation
                    if hasattr(ai_provider, 'search_expenses'):
                        # Use the simple search method that returns dictionaries like original
                        search_results = ai_provider.search_expenses(prompt, limit=10)
                    else:
                        # Fallback to search engine simple method
                        search_results = search_engine.simple_search_expenses(prompt, limit=10)
                    
                    print(f"Using watsonx for response generation in {target_language}")
                    
                    # Convert SearchResult objects to dictionaries if needed
                    if search_results and hasattr(search_results[0], 'description'):
                        # Convert SearchResult objects to dict format
                        search_results_dict = []
                        for result in search_results:
                            search_results_dict.append({
                                'description': result.description,
                                'merchant': result.merchant,
                                'shopping_type': result.metadata.get('shopping_type', 'Unknown'),
                                'expense_amount': result.amount,
                                'similarity_score': result.similarity_score
                            })
                        search_results = search_results_dict
                    
                    # Generate RAG response with language preference - use original simple approach
                    if target_language != 'English':
                        enhanced_prompt = f"{user_message}\n\nPlease respond in {target_language}."
                        if hasattr(ai_provider, 'simple_rag_response'):
                            rag_response_text = ai_provider.simple_rag_response(enhanced_prompt, search_results)
                        else:
                            rag_response = ai_provider.generate_rag_response(enhanced_prompt, search_results, None, response_language)
                            rag_response_text = rag_response.response if hasattr(rag_response, 'response') else str(rag_response)
                    else:
                        if hasattr(ai_provider, 'simple_rag_response'):
                            rag_response_text = ai_provider.simple_rag_response(user_message, search_results)
                        else:
                            rag_response = ai_provider.generate_rag_response(user_message, search_results, None, response_language)
                            rag_response_text = rag_response.response if hasattr(rag_response, 'response') else str(rag_response)
                    
                    print(f"Response from watsonx: {rag_response_text}")
                    
                    session['chat'].append({'text': rag_response_text, 'class': 'Assistant'})
                    
                except Exception as e:
                    error_message = f"Sorry, I'm experiencing technical difficulties. Error: {str(e)}"
                    print(f"Error with watsonx: {str(e)}")
                    session['chat'].append({'text': error_message, 'class': 'Assistant'})
                    
        return render_template('index.html', 
                             chat=session['chat'], 
                             ai_provider=ai_provider_display, 
                             current_page='banko')

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
        # Get AI provider info for display (without making LLM calls)
        if ai_provider:
            # Use cached provider info to avoid LLM calls
            provider_name = ai_provider.get_provider_name()
            current_model = getattr(ai_provider, 'current_model', 'Unknown')
            # Check if we have API credentials without making a call
            has_credentials = bool(
                getattr(ai_provider, 'api_key', None) or 
                getattr(ai_provider, 'access_key_id', None) or
                getattr(ai_provider, 'project_id', None)
            )
            connection_status = 'connected' if has_credentials else 'demo'
        else:
            provider_name = 'Unknown'
            current_model = 'Unknown'
            connection_status = 'disconnected'
        
        ai_provider_display = get_provider_display_info(config.ai_service, ai_provider, current_model, connection_status)
        return render_template('dashboard.html', 
                             current_page='settings',
                             ai_provider=ai_provider_display)

    @app.route('/ai-status')
    def ai_status():
        """Endpoint to check the status of AI services and database."""
        # Check database status
        db_connected, db_message, table_exists, record_count = check_database_connection(config.database_url)
        
        status = {
            'current_service': config.ai_service,
            'watsonx_available': config.ai_service.lower() == 'watsonx',
            'aws_bedrock_available': config.ai_service.lower() == 'aws',
            'database': {
                'connected': db_connected,
                'status': db_message,
                'expenses_table_exists': table_exists,
                'record_count': record_count,
                'connection_string': config.database_url.replace("@", "@***") if db_connected else "Not connected"
            }
        }
        
        # Check AI provider status (without making LLM calls)
        if ai_provider:
            # Check credentials without making API calls
            has_credentials = bool(
                getattr(ai_provider, 'api_key', None) or 
                getattr(ai_provider, 'access_key_id', None) or
                getattr(ai_provider, 'project_id', None)
            )
            provider_name = ai_provider.get_provider_name()
            current_model = getattr(ai_provider, 'current_model', 'Unknown')
            
            status['ai_status'] = {
                'connected': has_credentials,
                'message': 'API credentials configured' if has_credentials else 'Running in demo mode'
            }
            status['active_service_name'] = provider_name
            status['current_model'] = current_model
        else:
            status['ai_status'] = {
                'connected': False,
                'message': 'No AI provider configured'
            }
            status['active_service_name'] = 'Unknown'
            status['current_model'] = 'Unknown'
        
        return status

    @app.route('/test-ai-connection')
    def test_ai_connection():
        """Endpoint to actually test AI provider connection (makes LLM call)."""
        if not ai_provider:
            return {'error': 'No AI provider configured'}, 400
        
        try:
            # This will make an actual LLM call to test connection
            is_connected = ai_provider.test_connection()
            return {
                'connected': is_connected,
                'message': 'Connection test successful' if is_connected else 'Connection test failed',
                'provider': ai_provider.get_provider_name(),
                'model': getattr(ai_provider, 'current_model', 'Unknown')
            }
        except Exception as e:
            return {
                'connected': False,
                'message': f'Connection test failed: {str(e)}',
                'provider': ai_provider.get_provider_name(),
                'model': getattr(ai_provider, 'current_model', 'Unknown')
            }, 500

    @app.route('/cache-stats')
    def cache_stats():
        """Endpoint to view cache performance statistics"""
        if not cache_manager:
            return {'error': 'Cache manager not available'}, 503
        
        try:
            stats = cache_manager.get_cache_stats(hours=24)
            
            # Calculate overall hit rate
            total_requests = 0
            total_hits = 0
            
            for cache_type, cache_stats in stats.items():
                if cache_type != 'total_tokens_saved':
                    total_requests += cache_stats.get('hits', 0) + cache_stats.get('misses', 0)
                    total_hits += cache_stats.get('hits', 0)
            
            overall_hit_rate = (total_hits / total_requests) if total_requests > 0 else 0
            
            return {
                'success': True,
                'cache_enabled': True,
                'overall_hit_rate': overall_hit_rate,
                'total_requests': total_requests,
                'total_hits': total_hits,
                'total_tokens_saved': stats.get('total_tokens_saved', 0),
                'cache_details': stats
            }
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
            if config.ai_service.lower() == 'watsonx':
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
            results['suggestions'].extend([
                'Check network latency',
                'Try again later',
                'Switch to AWS Bedrock: export AI_SERVICE=aws'
            ])
        except Exception as e:
            results['config_test'] = {'status': 'error', 'message': f'Unexpected error: {str(e)}'}
            results['overall_status'] = 'unhealthy'
            results['suggestions'].append('Check application logs for more details')
        
        return results
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Not found'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': 'Internal server error'}), 500
    
    return app
