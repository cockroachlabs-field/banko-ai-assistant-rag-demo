"""
IBM Watsonx AI Integration Package for Banko Assistant

This package provides seamless integration with IBM Watsonx AI services,
enabling the Banko Assistant to leverage Watsonx's powerful language models
for financial data analysis and conversational assistance.

Modules:
    watsonx: Core integration module containing API functions and utilities

Key Features:
    - RAG (Retrieval Augmented Generation) responses
    - Expense search and analysis
    - Configurable API integration
    - Error handling and fallback mechanisms
    - Connection testing utilities

Usage:
    from watsonx.watsonx import search_expenses, RAG_response
    
    # Search expenses
    results = search_expenses("restaurant spending")
    
    # Generate AI response
    response = RAG_response("How much did I spend on food?", results)

Configuration:
    Set up your config.py file with:
    - WATSONX_API_KEY: Your IBM Watsonx API key
    - WATSONX_PROJECT_ID: Your Watsonx project ID
    - WATSONX_MODEL_ID: The model ID to use (optional)

Environment Variables (alternative to config.py):
    - WATSONX_API_KEY
    - WATSONX_PROJECT_ID  
    - WATSONX_MODEL_ID

Author: Banko AI Team
Version: 1.0.0
Date: 2024
"""

from .watsonx import (
    search_expenses,
    RAG_response,
    test_watsonx_connection,
    call_watsonx_api,
    get_watsonx_config
)

__version__ = "1.0.0"
__author__ = "Banko AI Team"

__all__ = [
    "search_expenses",
    "RAG_response", 
    "test_watsonx_connection",
    "call_watsonx_api",
    "get_watsonx_config"
]
