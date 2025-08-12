#!/usr/bin/env python3
"""
Banko AI Assistant - Application Runner

This script provides an easy way to run the Banko AI Assistant with 
different AI providers (Watsonx, AWS Bedrock, etc.)

Usage:
    python run-app.py [--provider watsonx|aws] [--port 5000]
"""

import os
import sys
import argparse
from app import app, check_database_connection

def print_banner():
    """Print a nice banner."""
    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║                    🏦 BANKO AI ASSISTANT 🤖                   ║")
    print("║               Conversational Banking Assistant                ║")
    print("╚═══════════════════════════════════════════════════════════════╝")
    print()

def check_prerequisites():
    """Check that all prerequisites are met."""
    print("🔍 Checking prerequisites...")
    
    # Check database connection
    db_connected, db_message, table_exists, record_count = check_database_connection()
    
    if not db_connected:
        print(f"❌ Database not available: {db_message}")
        print("💡 Start the database first:")
        print("   ./start-database.sh")
        return False
    
    print(f"✅ Database: {db_message}")
    
    if not table_exists:
        print("❌ Expenses table not found")
        print("💡 Initialize the database:")
        print("   cd vector_search && python create_table.py && python insert_data.py")
        return False
    
    print(f"✅ Expenses table: {record_count:,} records")
    
    # Check config file
    if not os.path.exists('config.py'):
        print("❌ config.py not found")
        print("💡 Create config.py from template:")
        print("   cp config.example.py config.py")
        print("   # Then edit config.py with your API keys")
        return False
    
    print("✅ Configuration file exists")
    return True

def show_ai_provider_info(provider):
    """Show information about the selected AI provider."""
    print(f"\n🤖 AI Provider: {provider.upper()}")
    
    if provider == 'watsonx':
        print("   Using IBM Watsonx AI")
        print("   Models: openai/gpt-oss-120b, meta-llama/llama-2-70b-chat, etc.")
    elif provider == 'aws':
        print("   Using AWS Bedrock")
        print("   Models: Claude 3.5 Sonnet, etc.")
    else:
        print("   Custom provider configuration")
    
    print()

def main():
    """Main application entry point."""
    parser = argparse.ArgumentParser(description='Banko AI Assistant')
    parser.add_argument('--provider', '-p', 
                       choices=['watsonx', 'aws'], 
                       default='watsonx',
                       help='AI provider to use (default: watsonx)')
    parser.add_argument('--port', '-P', 
                       type=int, 
                       default=5000,
                       help='Port to run the application on (default: 5000)')
    parser.add_argument('--debug', '-d', 
                       action='store_true',
                       help='Run in debug mode')
    parser.add_argument('--check-only', '-c', 
                       action='store_true',
                       help='Only check prerequisites, don\'t start the app')
    
    args = parser.parse_args()
    
    print_banner()
    
    # Set the AI service environment variable
    os.environ['AI_SERVICE'] = args.provider
    
    # Check prerequisites
    if not check_prerequisites():
        print("\n❌ Prerequisites not met. Please fix the issues above.")
        sys.exit(1)
    
    if args.check_only:
        print("\n✅ All prerequisites met!")
        return
    
    show_ai_provider_info(args.provider)
    
    # Import after setting environment variable
    from app import get_ai_service_functions
    
    try:
        search_func, rag_func, service_name = get_ai_service_functions()
        print(f"✅ Active AI Service: {service_name}")
    except Exception as e:
        print(f"⚠️  AI Service Warning: {e}")
        print("   The app will still run, but AI features may not work")
    
    print(f"\n🚀 Starting Banko AI Assistant on port {args.port}...")
    print(f"📍 Access at: http://localhost:{args.port}")
    print(f"📊 AI Status: http://localhost:{args.port}/ai-status")
    print(f"🏠 Dashboard: http://localhost:{args.port}/home")
    print("\n💡 Press Ctrl+C to stop the server")
    print("=" * 60)
    
    try:
        # Run the Flask app
        app.run(
            host='0.0.0.0',
            port=args.port,
            debug=args.debug
        )
    except KeyboardInterrupt:
        print("\n\n👋 Banko AI Assistant stopped. Goodbye!")
    except Exception as e:
        print(f"\n❌ Error starting application: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
