#!/usr/bin/env python3
"""
Demo script for testing IBM Watsonx integration with Banko AI Assistant

This script demonstrates:
1. Watsonx connection testing
2. Basic RAG response generation  
3. Financial assistant conversation simulation

Run this script to verify that your Watsonx integration is working correctly.
"""

import os
import sys

# Add parent directory to path so we can import config and app
sys.path.append('..')

def test_watsonx_integration():
    """Test the complete Watsonx integration."""
    print("=== Banko AI Assistant - Watsonx Integration Demo ===")
    print()
    
    # Test 1: Connection Test
    print("1. Testing Watsonx Connection...")
    try:
        from watsonx import test_watsonx_connection
        success, message = test_watsonx_connection()
        if success:
            print("✅ Connection successful!")
            print(f"   Response preview: {message[:100]}...")
        else:
            print("❌ Connection failed!")
            print(f"   Error: {message}")
            return False
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False
    
    print()
    
    # Test 2: RAG Response Test
    print("2. Testing RAG Response Generation...")
    try:
        from watsonx import RAG_response
        
        # Simulate a financial question
        test_prompt = "Hello! I'm testing the Banko AI assistant. Can you help me with my finances?"
        response = RAG_response(test_prompt, search_results=None)
        
        print("✅ RAG response generated successfully!")
        print(f"   User Query: {test_prompt}")
        print(f"   AI Response: {response[:200]}...")
        
    except Exception as e:
        print(f"❌ RAG response test failed: {e}")
        return False
    
    print()
    
    # Test 3: App Integration Test  
    print("3. Testing App Integration...")
    try:
        # Set environment to use Watsonx
        os.environ['AI_SERVICE'] = 'watsonx'
        
        # Import app functions
        from app import get_ai_service_functions
        
        search_func, rag_func, service_name = get_ai_service_functions()
        print(f"✅ App configured to use: {service_name}")
        
        # Test a sample financial question
        financial_question = "How can I track my spending better?"
        ai_response = rag_func(financial_question, [])  # Empty search results for demo
        
        print(f"   Sample Query: {financial_question}")
        print(f"   AI Response: {ai_response[:200]}...")
        
    except Exception as e:
        print(f"❌ App integration test failed: {e}")
        return False
    
    print()
    print("🎉 All tests passed! Watsonx integration is working correctly.")
    print()
    print("Next steps:")
    print("1. Set up your expense database with sample data")
    print("2. Create config.py with your Watsonx credentials (copy from config.example.py)")
    print("3. Run the Flask app with: export AI_SERVICE=watsonx && python app.py")
    print("4. Visit http://localhost:5000/banko to chat with your AI assistant")
    print("5. Check service status at: http://localhost:5000/ai-status")
    
    return True

def interactive_demo():
    """Run an interactive demo conversation."""
    print("\n=== Interactive Demo ===")
    print("Type financial questions to test the assistant (type 'quit' to exit):")
    print()
    
    from watsonx import RAG_response
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'bye']:
                print("Goodbye! 👋")
                break
                
            if not user_input:
                continue
                
            # Generate response using Watsonx
            response = RAG_response(user_input, search_results=None)
            print(f"Banko Assistant: {response}")
            print()
            
        except KeyboardInterrupt:
            print("\nGoodbye! 👋")
            break
        except Exception as e:
            print(f"Error: {e}")
            print("Please try again or type 'quit' to exit.")

if __name__ == "__main__":
    print("Starting Watsonx Integration Demo...")
    print()
    
    # Run the integration tests
    if test_watsonx_integration():
        # Ask if user wants to try interactive demo
        try:
            choice = input("\nWould you like to try the interactive demo? (y/n): ").lower().strip()
            if choice in ['y', 'yes']:
                interactive_demo()
        except KeyboardInterrupt:
            print("\nDemo completed. Thank you!")
    else:
        print("❌ Integration tests failed. Please check your configuration.")
        print("\nTroubleshooting:")
        print("1. Verify your Watsonx API key in config.py")
        print("2. Check your project ID is correct")
        print("3. Ensure you have internet connectivity")
        print("4. Review the error messages above for specific issues")
