"""
Main Flask application for Banko AI Assistant.

This module creates and configures the Flask application with all routes and functionality.
"""

import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO
from sqlalchemy import text

from ..config.settings import get_config
from ..ai_providers.factory import AIProviderFactory
from ..vector_search.search import VectorSearchEngine
from ..vector_search.generator import EnhancedExpenseGenerator
from ..utils.cache_manager import BankoCacheManager
from ..utils.db_retry import create_resilient_engine
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
        # Use official sqlalchemy-cockroachdb dialect (no conversion needed!)
        engine = create_resilient_engine(database_url)
        
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
    print(f"🔧 Initializing AI Provider: {config.ai_service}")
    print(f"   Environment AI_SERVICE: {os.getenv('AI_SERVICE', 'NOT SET')}")
    try:
        ai_config = config.get_ai_config()
        ai_provider = AIProviderFactory.create_provider(
            config.ai_service, 
            ai_config[config.ai_service],
            cache_manager
        )
        print(f"✅ AI Provider initialized: {ai_provider.get_provider_name() if ai_provider else 'None'}")
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
    
    # OLD ROUTE REMOVED - replaced by /api/generate-data with SocketIO support below
    
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
            # Debug logging
            provider_name = ai_provider.get_provider_name() if ai_provider else 'None'
            print(f"🔍 /api/health called - config.ai_service: {config.ai_service}, provider: {provider_name}")
            
            # Check database connection with proper pooling
            # Use official sqlalchemy-cockroachdb dialect (no conversion needed!)
            engine = create_resilient_engine(config.database_url)
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

    @app.route('/api/upload-receipt', methods=['POST'])
    def upload_receipt():
        """Handle receipt upload and process with Agent system"""
        import uuid
        import tempfile
        from pathlib import Path
        
        try:
            # Check if file was uploaded
            if 'receipt' not in request.files:
                return jsonify({
                    'success': False,
                    'error': 'No receipt file provided'
                }), 400
            
            file = request.files['receipt']
            
            if file.filename == '':
                return jsonify({
                    'success': False,
                    'error': 'No file selected'
                }), 400
            
            # Save file temporarily
            file_ext = Path(file.filename).suffix
            temp_path = f"/tmp/receipt_{uuid.uuid4()}{file_ext}"
            file.save(temp_path)
            
            print(f"📄 Receipt uploaded: {file.filename} → {temp_path}")
            
            # Initialize Receipt Agent
            try:
                from banko_ai.agents.receipt_agent import ReceiptAgent
                from langchain_openai import ChatOpenAI
                from sentence_transformers import SentenceTransformer
                import os
                
                llm = ChatOpenAI(
                    model='gpt-4o-mini',
                    api_key=os.getenv('OPENAI_API_KEY'),
                    temperature=0.7
                )
                embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
                
                receipt_agent = ReceiptAgent(
                    region='us-east-1',
                    llm=llm,
                    database_url=config.database_url,
                    embedding_model=embedding_model
                )
                
                print(f"🤖 Receipt Agent created: {receipt_agent.agent_id[:8]}...")
                
                # Process document
                result = receipt_agent.process_document(
                    file_path=temp_path,
                    user_id=session.get('user_id', 'demo_user'),
                    document_type='receipt'
                )
                
                print(f"✅ Processing result: {result.get('success', False)}")
                
                # Check if processing actually succeeded
                if not result.get('success', False):
                    # Processing failed - return error with details
                    errors = result.get('errors', ['Unknown processing error'])
                    print(f"❌ Receipt processing failed: {errors}")
                    return jsonify({
                        'success': False,
                        'error': f"Receipt processing failed: {', '.join(errors)}",
                        'details': result
                    }), 500
                
                # Extract data for response (Receipt Agent returns 'extracted_fields')
                extracted = result.get('extracted_fields', {})
                
                print(f"📊 Extracted fields: {extracted}")
                
                # Emit real-time update: Receipt Agent completed
                try:
                    socketio.emit('agent_activity', {
                        'agent_type': 'receipt',
                        'region': 'us-east-1',
                        'status': 'processing',
                        'message': f"Processing receipt from {extracted.get('merchant', 'Unknown')}",
                        'timestamp': datetime.now().isoformat()
                    })
                except:
                    pass
                
                # Step 1: Add expense to expenses table
                expense_id = None
                try:
                    from datetime import datetime
                    from sqlalchemy import text
                    import uuid
                    
                    # Use official sqlalchemy-cockroachdb dialect (no conversion needed!)
                    engine = create_resilient_engine(config.database_url)
                    
                    expense_id = str(uuid.uuid4())
                    
                    # Get or create proper UUID for user
                    session_user_id = session.get('user_id', 'demo_user')
                    if isinstance(session_user_id, str) and not session_user_id.count('-') == 4:
                        # Not a UUID, create a deterministic one for demo_user
                        import hashlib
                        user_uuid = uuid.UUID(hashlib.md5(session_user_id.encode()).hexdigest())
                        user_id = str(user_uuid)
                    else:
                        user_id = session_user_id
                    
                    # Handle None values from extraction
                    amount = extracted.get('amount')
                    if amount is None or amount == 'None':
                        amount = 0.0
                    else:
                        amount = float(amount)
                    
                    # Handle missing date - use today as default
                    expense_date = extracted.get('date')
                    if expense_date is None or expense_date == 'None' or expense_date == '':
                        expense_date = datetime.now().strftime('%Y-%m-%d')
                    
                    # Handle missing merchant
                    merchant = extracted.get('merchant', 'Unknown')
                    if not merchant or merchant == 'None':
                        merchant = 'Unknown'
                    
                    # Generate embedding for expense using natural language
                    # This helps match conversational queries like "when did I go to X?"
                    merchant = extracted.get('merchant', 'Unknown')
                    category = extracted.get('category', 'general')
                    expense_text = f"Spent ${amount} at {merchant} for {category} on {expense_date.strftime('%Y-%m-%d') if hasattr(expense_date, 'strftime') else expense_date}"
                    
                    from sentence_transformers import SentenceTransformer
                    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
                    embedding = embedding_model.encode(expense_text).tolist()
                    
                    # Get category and items for tags and description
                    category = extracted.get('category', 'general')
                    items = extracted.get('items', [])
                    
                    # Generate tags from merchant and category
                    tags = []
                    if merchant and merchant != 'Unknown':
                        # Add first word of merchant name (lowercase)
                        tags.append(merchant.lower().split()[0])
                    if category and category != 'general':
                        tags.append(category.lower())
                    
                    # Format better description
                    if items and len(items) > 0:
                        item_list = ', '.join(items)
                        description = f"Spent ${amount:.2f} at {merchant} for {item_list}."
                    else:
                        description = f"Spent ${amount:.2f} on {category} at {merchant}."
                    
                    with engine.connect() as conn:
                        # Format embedding as array literal for CockroachDB
                        embedding_str = '[' + ','.join(str(x) for x in embedding) + ']'
                        
                        # Format tags array for CockroachDB
                        tags_str = '{' + ','.join(f'"{tag}"' for tag in tags) + '}' if tags else None
                        
                        conn.execute(text("""
                            INSERT INTO expenses (
                                expense_id, user_id, expense_amount, shopping_type,
                                merchant, expense_date, description, payment_method,
                                tags, embedding, created_at
                            ) VALUES (
                                :expense_id, :user_id, :amount, :category,
                                :merchant, :date, :description, :payment_method,
                                :tags, CAST(:embedding AS VECTOR(384)), NOW()
                            )
                        """), {
                            'expense_id': expense_id,
                            'user_id': user_id,
                            'amount': amount,
                            'category': category,
                            'merchant': merchant,
                            'date': expense_date,
                            'description': description,
                            'payment_method': extracted.get('payment_method', 'unknown') if extracted.get('payment_method') else 'unknown',
                            'tags': tags_str,
                            'embedding': embedding_str
                        })
                        conn.commit()
                    
                    print(f"💰 Expense added to expenses table: {expense_id}")
                    print(f"   📝 Description: {description}")
                    print(f"   🏷️  Tags: {tags}")
                    
                    # Emit update: Expense added
                    try:
                        socketio.emit('agent_activity', {
                            'agent_type': 'receipt',
                            'region': 'us-east-1',
                            'status': 'completed',
                            'message': f"Added expense: {extracted.get('merchant', 'Unknown')} - ${amount}",
                            'timestamp': datetime.now().isoformat()
                        })
                    except:
                        pass
                    
                except Exception as e:
                    print(f"⚠️  Failed to add expense to table: {e}")
                    import traceback
                    traceback.print_exc()
                
                # Step 2: Trigger Fraud Agent
                fraud_result = "✅ No issues detected"
                try:
                    from banko_ai.agents.fraud_agent import FraudAgent
                    from langchain_openai import ChatOpenAI
                    
                    fraud_llm = ChatOpenAI(
                        model='gpt-4o-mini',
                        api_key=os.getenv('OPENAI_API_KEY'),
                        temperature=0.7
                    )
                    
                    fraud_agent = FraudAgent(
                        region='us-west-2',
                        llm=fraud_llm,
                        database_url=config.database_url,
                        embedding_model=embedding_model,
                        fraud_threshold=0.7
                    )
                    
                    print(f"🕵️  Running fraud check...")
                    
                    # Emit update: Fraud Agent started
                    try:
                        socketio.emit('agent_activity', {
                            'agent_type': 'fraud',
                            'region': 'us-west-2',
                            'status': 'processing',
                            'message': 'Scanning for suspicious patterns...',
                            'timestamp': datetime.now().isoformat()
                        })
                    except:
                        pass
                    
                    fraud_check = fraud_agent.scan_recent_expenses(
                        hours=24,
                        limit=10
                    )
                    
                    if fraud_check.get('fraudulent_count', 0) > 0:
                        fraud_result = f"⚠️  {fraud_check['fraudulent_count']} suspicious transactions"
                    else:
                        fraud_result = "✅ No issues detected"
                    
                    print(f"   {fraud_result}")
                    
                    # Emit update: Fraud Agent completed
                    try:
                        socketio.emit('agent_activity', {
                            'agent_type': 'fraud',
                            'region': 'us-west-2',
                            'status': 'completed',
                            'message': fraud_result,
                            'timestamp': datetime.now().isoformat()
                        })
                    except:
                        pass
                    
                except Exception as e:
                    print(f"⚠️  Fraud check failed: {e}")
                    fraud_result = "⚠️  Check failed"
                
                # Step 3: Trigger Budget Agent
                budget_result = "Budget updated"
                try:
                    from banko_ai.agents.budget_agent import BudgetAgent
                    
                    budget_llm = ChatOpenAI(
                        model='gpt-4o-mini',
                        api_key=os.getenv('OPENAI_API_KEY'),
                        temperature=0.7
                    )
                    
                    budget_agent = BudgetAgent(
                        region='us-central-1',
                        llm=budget_llm,
                        database_url=config.database_url,
                        alert_threshold=0.8
                    )
                    
                    print(f"📊 Running budget check...")
                    
                    # Emit update: Budget Agent started
                    try:
                        socketio.emit('agent_activity', {
                            'agent_type': 'budget',
                            'region': 'us-central-1',
                            'status': 'processing',
                            'message': 'Analyzing budget impact...',
                            'timestamp': datetime.now().isoformat()
                        })
                    except:
                        pass
                    
                    # Get budget from config (can be set via MONTHLY_BUDGET_DEFAULT env var)
                    from ..config.settings import get_config
                    app_config = get_config()
                    
                    budget_check = budget_agent.check_budget_status(
                        user_id=user_id,
                        monthly_budget=app_config.monthly_budget_default
                    )
                    
                    status = budget_check.get('status', 'unknown')
                    if status == 'over_budget':
                        budget_result = "⚠️  Over budget!"
                    elif status == 'on_pace_to_exceed':
                        budget_result = "⚠️  On pace to exceed"
                    else:
                        budget_result = "✅ Within budget"
                    
                    print(f"   {budget_result}")
                    
                    # Emit update: Budget Agent completed
                    try:
                        socketio.emit('agent_activity', {
                            'agent_type': 'budget',
                            'region': 'us-central-1',
                            'status': 'completed',
                            'message': budget_result,
                            'timestamp': datetime.now().isoformat()
                        })
                    except:
                        pass
                    
                except Exception as e:
                    print(f"⚠️  Budget check failed: {e}")
                    budget_result = "⚠️  Check failed"
                
                return jsonify({
                    'success': True,
                    'merchant': extracted.get('merchant', 'Unknown'),
                    'amount': str(extracted.get('amount', '0.00')),
                    'category': extracted.get('category', 'Unknown'),
                    'date': extracted.get('date', 'Unknown'),
                    'items': extracted.get('items', []),
                    'expense_id': expense_id,
                    'fraud_status': fraud_result,
                    'budget_impact': budget_result,
                    'document_id': result.get('document_id'),
                    'message': 'Receipt processed by Receipt, Fraud, and Budget agents'
                })
                
            except Exception as agent_error:
                print(f"⚠️  Agent processing error: {agent_error}")
                import traceback
                traceback.print_exc()
                
                # Return error (not fake success)
                return jsonify({
                    'success': False,
                    'error': f'Agent processing failed: {str(agent_error)}',
                    'message': 'Receipt uploaded but processing failed. Check server logs.'
                }), 500
        
        except Exception as e:
            print(f"❌ Receipt upload error: {e}")
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
                    
                    print(f"Using {config.ai_service} for response generation in {target_language}")
                    
                    # Convert SearchResult objects to dictionaries if needed
                    if search_results and hasattr(search_results[0], 'description'):
                        # Convert SearchResult objects to dict format - MUST include ALL fields!
                        search_results_dict = []
                        for result in search_results:
                            search_results_dict.append({
                                'expense_id': result.expense_id,
                                'user_id': result.user_id,
                                'description': result.description,
                                'merchant': result.merchant,
                                'expense_amount': result.amount,
                                'expense_date': result.date,  # ← WAS MISSING!
                                'shopping_type': result.metadata.get('shopping_type', 'Unknown'),
                                'payment_method': result.metadata.get('payment_method', 'Unknown'),  # ← WAS MISSING!
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
                    
                    print(f"Response from {config.ai_service}: {rag_response_text}")
                    
                    session['chat'].append({'text': rag_response_text, 'class': 'Assistant'})
                    
                except Exception as e:
                    error_message = f"Sorry, I'm experiencing technical difficulties. Error: {str(e)}"
                    print(f"Error with {config.ai_service}: {str(e)}")
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
    
    # Initialize SocketIO for real-time updates (needed before data generator routes)
    # Use threading mode for Flask dev server, eventlet mode for Gunicorn production
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
    app.socketio = socketio
    
    # Data Generator Routes
    generation_state = {'running': False, 'should_stop': False}
    
    @app.route('/data-generator')
    def data_generator_page():
        """Render data generator page."""
        return render_template('data_generator.html')
    
    @app.route('/api/generate-data', methods=['POST'])
    def start_generation():
        """Start data generation with real-time updates."""
        if generation_state['running']:
            return jsonify({'error': 'Generation already running'}), 400
        
        data = request.json
        count = data.get('count', 1000)
        clear_existing = data.get('clear_existing', False)
        continuous = data.get('continuous', False)
        
        def generate_in_background():
            # CRITICAL: Need Flask app context for SocketIO in background thread
            # Use app.socketio to ensure we have the right instance
            with app.app_context():
                generation_state['running'] = True
                generation_state['should_stop'] = False
                generator = EnhancedExpenseGenerator(config.database_url)
                sock = app.socketio  # Get socketio instance from app
                
                try:
                    print("🚀 Starting generation...")
                    sock.emit('generation_progress', {
                        'current': 0, 
                        'total': count, 
                        'message': 'Starting generation...'
                    })
                    
                    if clear_existing:
                        print("🗑️  Clearing existing data...")
                        sock.emit('generation_progress', {
                            'current': 0, 
                            'total': count, 
                            'message': 'Clearing data...'
                        })
                        generator.clear_expenses()
                    
                    # Use same batch size as generator for consistency
                    batch_size = int(os.getenv('DATA_GEN_BATCH_SIZE', '50'))
                    import time
                    
                    # Main generation loop - supports continuous mode
                    while not generation_state['should_stop']:
                        total_generated = 0
                        start_time = time.time()
                        
                        # Generate one batch of records
                        while total_generated < count and not generation_state['should_stop']:
                            batch = min(batch_size, count - total_generated)
                            generated = generator.generate_and_save(count=batch, clear_existing=False)
                            total_generated += generated
                            
                            elapsed = time.time() - start_time
                            speed = total_generated / elapsed if elapsed > 0 else 0
                            
                            progress_data = {
                                'current': total_generated,
                                'total': count,
                                'speed': round(speed, 1),
                                'message': f'Generated {total_generated:,} / {count:,} ({speed:.0f} rec/sec)'
                            }
                            print(f"📊 Progress: {total_generated}/{count} ({speed:.0f} rec/sec)")
                            sock.emit('generation_progress', progress_data)
                        
                        print(f"✅ Generation complete: {total_generated} records")
                        sock.emit('generation_complete', {
                            'total_generated': total_generated,
                            'elapsed': round(time.time() - start_time, 1),
                            'continuous': continuous
                        })
                        
                        # If not continuous mode or stopped, exit
                        if not continuous or generation_state['should_stop']:
                            break
                        
                        # Brief pause before next cycle in continuous mode
                        time.sleep(1)
                        print("🔄 Continuous mode: Restarting generation...")
                        sock.emit('generation_progress', {
                            'current': 0,
                            'total': count,
                            'message': 'Continuous mode: Restarting...'
                        })
                except Exception as e:
                    print(f"❌ Error during generation: {e}")
                    import traceback
                    traceback.print_exc()
                    sock.emit('generation_error', {'message': str(e)})
                finally:
                    generation_state['running'] = False
        
        import threading
        thread = threading.Thread(target=generate_in_background)
        thread.daemon = True
        thread.start()
        
        return jsonify({'status': 'started'})
    
    @app.route('/api/stop-generation', methods=['POST'])
    def stop_generation():
        """Stop data generation."""
        generation_state['should_stop'] = True
        return jsonify({'status': 'stopping'})
    
    @app.route('/api/reset-generation', methods=['POST'])
    def reset_generation():
        """Reset generation state."""
        generation_state['running'] = False
        generation_state['should_stop'] = False
        return jsonify({'status': 'reset'})
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Not found'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': 'Internal server error'}), 500
    
    # Register agent dashboard blueprint
    from .agent_dashboard import agent_dashboard
    app.register_blueprint(agent_dashboard)
    
    return app
