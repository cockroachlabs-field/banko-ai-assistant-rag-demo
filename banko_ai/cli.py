"""
Command-line interface for Banko AI Assistant.

This module provides CLI commands for running the application and managing data.
"""

import click
import os
from .config.settings import get_config
from .vector_search.generator import EnhancedExpenseGenerator
from .web.app import create_app


@click.group()
def cli():
    """Banko AI Assistant - AI-powered expense analysis and RAG system."""
    pass


@cli.command()
@click.option('--host', default='0.0.0.0', help='Host to bind to')
@click.option('--port', default=5000, help='Port to bind to')
@click.option('--debug', is_flag=True, help='Enable debug mode')
@click.option('--generate-data', type=int, default=5000, help='Generate sample data before starting (default: 5000 records)')
@click.option('--no-data', is_flag=True, help='Skip data generation and start with empty database')
@click.option('--clear-data', is_flag=True, help='Clear existing data before generating new data')
@click.option('--background', is_flag=True, help='Run in background mode (suppress Flask output)')
def run(host, port, debug, generate_data, no_data, clear_data, background):
    """Run the Banko AI Assistant web application."""
    # Show beautiful startup banner
    click.echo("🏦 === Banko AI Assistant Starting === 🏦")
    
    # Load configuration and show AI service info
    config = get_config()
    ai_service = config.ai_service.upper()
    click.echo(f"🤖 AI Service: {config.ai_service}")
    
    # Check AI provider availability
    try:
        from .ai_providers.factory import AIProviderFactory
        ai_config = config.get_ai_config()
        ai_provider = AIProviderFactory.create_provider(
            config.ai_service, 
            ai_config[config.ai_service]
        )
        
        # Test connection and show status
        if ai_provider.test_connection():
            click.echo(f"🔧 {ai_service} Available: True")
            click.echo(f"✅ Active AI Service: {ai_service}")
        else:
            click.echo(f"🔧 {ai_service} Available: False")
            click.echo(f"⚠️  {ai_service} running in demo mode")
    except Exception as e:
        click.echo(f"🔧 {ai_service} Available: False")
        click.echo(f"⚠️  {ai_service} running in demo mode")
    
    click.echo("=" * 44)
    
    # Generate data if not explicitly disabled
    if not no_data:
        click.echo("🔍 Checking database setup...")
        click.echo(f"Using database: {config.database_url}")
        click.echo(f"Generating {generate_data} sample expense records...")
        generator = EnhancedExpenseGenerator(config.database_url)
        
        # Check if data already exists
        try:
            existing_count = generator.get_expense_count()
            if existing_count > 0 and not clear_data:
                click.echo(f"✅ Database already contains {existing_count} expense records")
            else:
                if clear_data:
                    click.echo("Clearing existing data...")
                    generator.clear_expenses()
                
                actual_count = generator.generate_and_save(generate_data)
                click.echo(f"✅ Successfully generated {actual_count} expense records")
        except Exception as e:
            click.echo(f"❌ Error generating data: {e}")
            return
    else:
        click.echo("Skipping data generation (--no-data flag used)")
    
    # Show startup completion message
    click.echo(f"🚀 Starting server on http://localhost:{port}")
    click.echo("🎉 Banko AI is ready to help with your finances!")
    click.echo("=" * 44)
    
    # Create and run the app
    app = create_app()
    
    if background:
        # Background mode - suppress Flask output
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        
        # Show final message for background mode
        click.echo(f"🚀 Banko AI running in background on http://localhost:{port}")
        click.echo("💡 Use 'banko-ai status' to check if it's running")
        click.echo("🛑 Use 'pkill -f banko-ai' to stop the background process")
    
    app.run(host=host, port=port, debug=debug)


@cli.command()
@click.option('--count', default=1000, help='Number of records to generate')
@click.option('--user-id', help='User ID for generated records')
@click.option('--clear', is_flag=True, help='Clear existing data before generating')
def generate_data(count, user_id, clear):
    """Generate sample expense data."""
    config = get_config()
    generator = EnhancedExpenseGenerator(config.database_url)
    
    click.echo(f"Generating {count} expense records...")
    
    generated_count = generator.generate_and_save(
        count=count,
        user_id=user_id,
        clear_existing=clear
    )
    
    click.echo(f"Successfully generated {generated_count} expense records")


@cli.command()
def clear_data():
    """Clear all expense data."""
    config = get_config()
    generator = EnhancedExpenseGenerator(config.database_url)
    
    if generator.clear_expenses():
        click.echo("Successfully cleared all expense data")
    else:
        click.echo("Failed to clear expense data")


@cli.command()
def status():
    """Show application status."""
    config = get_config()
    generator = EnhancedExpenseGenerator(config.database_url)
    
    # Show current configuration
    click.echo("🔧 Current Configuration:")
    click.echo(f"   AI Service: {config.ai_service}")
    click.echo(f"   Database: {config.database_url}")
    
    if config.ai_service == 'gemini':
        click.echo(f"   Google Project: {config.google_project_id}")
        click.echo(f"   Google Model: {config.google_model}")
        click.echo(f"   Google Location: {config.google_location}")
        creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        api_key = os.getenv("GOOGLE_API_KEY")
        click.echo(f"   Service Account: {'✅' if creds_path else '❌'} {creds_path or 'Not set'}")
        click.echo(f"   API Key Fallback: {'✅' if api_key else '❌'} {'Set' if api_key else 'Not set'}")
    
    click.echo()
    
    # Check database connection
    try:
        count = generator.get_expense_count()
        click.echo(f"✅ Database connected - {count} expense records")
    except Exception as e:
        click.echo(f"❌ Database error: {e}")
        return
    
    # Check AI provider
    try:
        from .ai_providers.factory import AIProviderFactory
        ai_config = config.get_ai_config()
        ai_provider = AIProviderFactory.create_provider(
            config.ai_service, 
            ai_config[config.ai_service]
        )
        
        if ai_provider.test_connection():
            click.echo(f"✅ AI provider ({config.ai_service}) connected")
            if hasattr(ai_provider, 'use_vertex_ai'):
                api_type = "Vertex AI" if ai_provider.use_vertex_ai else "Generative AI API"
                click.echo(f"   Using: {api_type}")
        else:
            click.echo(f"❌ AI provider ({config.ai_service}) disconnected")
    except Exception as e:
        click.echo(f"❌ AI provider error: {e}")


@cli.command()
@click.option('--host', default='0.0.0.0', help='Host to bind to')
@click.option('--port', default=5000, help='Port to bind to')
@click.option('--generate-data', type=int, default=5000, help='Generate sample data before starting (default: 5000 records)')
@click.option('--no-data', is_flag=True, help='Skip data generation and start with empty database')
@click.option('--clear-data', is_flag=True, help='Clear existing data before generating new data')
def start(host, port, generate_data, no_data, clear_data):
    """Start Banko AI in background mode (equivalent to 'run --background')."""
    # Show beautiful startup banner
    click.echo("🏦 === Banko AI Assistant Starting === 🏦")
    
    # Load configuration and show AI service info
    config = get_config()
    ai_service = config.ai_service.upper()
    click.echo(f"🤖 AI Service: {config.ai_service}")
    
    # Check AI provider availability
    try:
        from .ai_providers.factory import AIProviderFactory
        ai_config = config.get_ai_config()
        ai_provider = AIProviderFactory.create_provider(
            config.ai_service, 
            ai_config[config.ai_service]
        )
        
        # Test connection and show status
        if ai_provider.test_connection():
            click.echo(f"🔧 {ai_service} Available: True")
            click.echo(f"✅ Active AI Service: {ai_service}")
        else:
            click.echo(f"🔧 {ai_service} Available: False")
            click.echo(f"⚠️  {ai_service} running in demo mode")
    except Exception as e:
        click.echo(f"🔧 {ai_service} Available: False")
        click.echo(f"⚠️  {ai_service} running in demo mode")
    
    click.echo("=" * 44)
    
    # Generate data if not explicitly disabled
    if not no_data:
        click.echo("🔍 Checking database setup...")
        click.echo(f"Using database: {config.database_url}")
        click.echo(f"Generating {generate_data} sample expense records...")
        generator = EnhancedExpenseGenerator(config.database_url)
        
        # Check if data already exists
        try:
            existing_count = generator.get_expense_count()
            if existing_count > 0 and not clear_data:
                click.echo(f"✅ Database already contains {existing_count} expense records")
            else:
                if clear_data:
                    click.echo("Clearing existing data...")
                    generator.clear_expenses()
                
                actual_count = generator.generate_and_save(generate_data)
                click.echo(f"✅ Successfully generated {actual_count} expense records")
        except Exception as e:
            click.echo(f"❌ Error generating data: {e}")
            return
    else:
        click.echo("Skipping data generation (--no-data flag used)")
    
    # Show startup completion message
    click.echo(f"🚀 Starting server on http://localhost:{port}")
    click.echo("🎉 Banko AI is ready to help with your finances!")
    click.echo("=" * 44)
    
    # Create and run the app in background mode
    app = create_app()
    
    # Background mode - suppress Flask output
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    # Show final message for background mode
    click.echo(f"🚀 Banko AI running in background on http://localhost:{port}")
    click.echo("💡 Use 'banko-ai status' to check if it's running")
    click.echo("🛑 Use 'pkill -f banko-ai' to stop the background process")
    
    app.run(host=host, port=port, debug=False)


@cli.command()
def help():
    """Show detailed help and setup instructions."""
    click.echo("""
🤖 Banko AI Assistant - Setup Guide
====================================

This is a modern AI-powered expense analysis application with RAG capabilities.

PREREQUISITES:
--------------
- CockroachDB v25.2.4+ (recommended: v25.3.3)
- Vector index feature enabled: SET CLUSTER SETTING feature.vector_index.enabled = true;
- Start single node: cockroach start-single-node --insecure --store=./cockroach-data --listen-addr=localhost:26257 --http-addr=localhost:8080 --background

QUICK START:
-----------
1. Set up your environment variables:
   export AI_SERVICE="watsonx"  # or "openai", "aws", "gemini"
   export DATABASE_URL="cockroachdb://root@localhost:26257/defaultdb?sslmode=disable"

2. Configure your AI provider:

   For Watsonx (IBM):
   export WATSONX_API_KEY="your_api_key_here"
   export WATSONX_PROJECT_ID="your_project_id_here"
   export WATSONX_MODEL="meta-llama/llama-2-70b-chat"

   For OpenAI:
   export OPENAI_API_KEY="your_api_key_here"
   export OPENAI_MODEL="gpt-3.5-turbo"

   For AWS Bedrock:
   export AWS_ACCESS_KEY_ID="your_access_key"
   export AWS_SECRET_ACCESS_KEY="your_secret_key"
   export AWS_REGION="us-east-1"
   export AWS_MODEL="anthropic.claude-3-sonnet-20240229-v1:0"

   For Google Gemini (Two Options):
   
   Option 1 - Vertex AI (Recommended):
   export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account.json"
   export GOOGLE_PROJECT_ID="your-google-cloud-project-id"
   export GOOGLE_MODEL="gemini-1.5-pro"
   export GOOGLE_LOCATION="us-central1"  # optional, defaults to us-central1
   Note: Requires Vertex AI API enabled in Google Cloud Console
   
   Option 2 - Generative AI API (Fallback):
   export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account.json"
   export GOOGLE_PROJECT_ID="your-google-cloud-project-id"
   export GOOGLE_MODEL="gemini-1.5-pro"
   export GOOGLE_API_KEY="your-gemini-api-key"  # Get from https://makersuite.google.com/app/apikey
   Note: Will automatically fallback to this if Vertex AI is unavailable

3. Start the application:
   banko-ai run                    # Normal mode with full output
   banko-ai start                  # Background mode (quiet) - same as run --background
   banko-ai run --background       # Background mode (quiet)
   banko-ai run --no-data          # Skip data generation
   banko-ai run --debug            # Enable debug mode

COMMANDS:
---------
  run              Run the web application (normal mode)
  start            Start the web application (background mode)
  generate-data    Generate sample expense data
  clear-data       Clear all expense data
  status           Show application status
  search           Search expenses using vector similarity
  help             Show this help message

FEATURES:
---------
✅ Multi-AI Provider Support (OpenAI, AWS Bedrock, IBM Watsonx, Google Gemini)
✅ Dynamic Model Switching (switch models without restart)
✅ User Authentication & User-Specific Vector Indexing
✅ Enhanced Vector Search with Data Enrichment
✅ Modern PyPI-Ready Package Structure
✅ Real-time Chat Interface
✅ Expense Analysis & Categorization
✅ Multi-language Support

ENDPOINTS:
----------
Web Interface: http://localhost:5000
API Health: http://localhost:5000/api/health
AI Providers: http://localhost:5000/api/ai-providers
Models: http://localhost:5000/api/models
Search: POST http://localhost:5000/api/search (JSON: {"query": "your search", "limit": 10})
RAG: POST http://localhost:5000/api/rag (JSON: {"query": "your question", "limit": 5})

TROUBLESHOOTING:
---------------
- Database connection issues: Check DATABASE_URL
- AI provider errors: Verify API keys and configuration
- Model switching: Use the Settings tab in the web interface
- Vector search: Ensure database has expense data

Gemini-Specific Issues:
- "404 Publisher Model not found": Enable Vertex AI API in Google Cloud Console
- "Permission denied to enable service": Use your main Google account, not service account
- Vertex AI unavailable: Provider will auto-fallback to Generative AI API if GOOGLE_API_KEY is set
- Service account issues: Ensure the JSON file path is correct and accessible

For more information, visit: https://github.com/cockroachlabs-field/banko-ai-assistant-rag-demo
""")


@cli.command()
@click.argument('query')
@click.option('--user-id', help='User ID to filter results')
@click.option('--limit', default=10, help='Maximum number of results')
def search(query, user_id, limit):
    """Search expenses using vector similarity."""
    config = get_config()
    from .vector_search.search import VectorSearchEngine
    
    search_engine = VectorSearchEngine(config.database_url)
    results = search_engine.search_expenses(
        query=query,
        user_id=user_id,
        limit=limit
    )
    
    if not results:
        click.echo("No results found")
        return
    
    click.echo(f"Found {len(results)} results for '{query}':")
    click.echo()
    
    for i, result in enumerate(results, 1):
        click.echo(f"{i}. {result.description}")
        click.echo(f"   Merchant: {result.merchant}")
        click.echo(f"   Amount: ${result.amount:.2f}")
        click.echo(f"   Date: {result.date}")
        click.echo(f"   Similarity: {result.similarity_score:.3f}")
        click.echo()


def main():
    """Main CLI entry point."""
    cli()


if __name__ == '__main__':
    main()
