#!/usr/bin/env python3
"""
Quick Watsonx Connection Test

This script provides a simple way to test your Watsonx API connection.
Run this before using the full demo to ensure your credentials are working.

Usage:
    python test_connection.py
"""

import sys
import os

# Add parent directory to path so we can import config
sys.path.append('..')

def quick_test():
    """Perform a quick connection test."""
    print("🔧 Watsonx Connection Test")
    print("=" * 40)
    
    try:
        # Test import
        from watsonx import test_watsonx_connection
        print("✅ Watsonx module imported successfully")
        
        # Test connection
        print("⏳ Testing API connection...")
        success, message = test_watsonx_connection()
        
        if success:
            print("🎉 SUCCESS: Watsonx connection working!")
            print(f"   Test response: {message[:100]}...")
            print("\nYou're ready to use the Banko AI assistant with Watsonx!")
            print("Next: Run 'python demo_watsonx.py' for a full demo")
        else:
            print("❌ FAILED: Connection test failed")
            print(f"   Error: {message}")
            print("\nTroubleshooting:")
            print("1. Check your config.py file exists")
            print("2. Verify WATSONX_API_KEY is correct")
            print("3. Confirm WATSONX_PROJECT_ID is valid")
            print("4. Ensure you have internet connectivity")
            
    except ImportError as e:
        print("❌ FAILED: Could not import Watsonx module")
        print(f"   Error: {e}")
        print("\nMake sure you're running from the project root or watsonx directory")
    except Exception as e:
        print("❌ FAILED: Unexpected error")
        print(f"   Error: {e}")

if __name__ == "__main__":
    quick_test()
