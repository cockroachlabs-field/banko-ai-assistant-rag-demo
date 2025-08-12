# IBM Watsonx Integration for Banko AI Assistant

This folder contains the IBM Watsonx AI integration for the Banko AI Assistant project. It provides seamless integration with IBM Watsonx's language models to power conversational financial assistance.

## Overview

The Watsonx integration enables the Banko Assistant to:
- Analyze financial data using IBM's advanced AI models
- Provide conversational responses about expenses and financial patterns
- Search and retrieve relevant expense information using semantic similarity
- Generate contextual, accurate responses through RAG (Retrieval Augmented Generation)

## Files

### `watsonx.py`
The main integration module containing:
- **`search_expenses(query, limit=5)`**: Search for expenses using semantic similarity
- **`RAG_response(prompt, search_results=None, use_watsonx=True)`**: Generate AI responses with context
- **`call_watsonx_api(messages, config=None)`**: Direct API communication with Watsonx
- **`test_watsonx_connection()`**: Test and verify API connectivity
- **`get_watsonx_config()`**: Retrieve configuration from environment or config file

### `__init__.py`
Package initialization file that exports the main functions for easy importing.

### `demo_watsonx.py`
Complete demonstration script that tests all aspects of the Watsonx integration and provides an interactive chat interface.

### `test_connection.py`
Quick connection test script to verify your Watsonx API credentials are working.

### `README.md`
This documentation file.

## Configuration

### Method 1: Using config.py (Recommended)
Add the following to your `config.py` file:

```python
# IBM Watsonx Configuration
WATSONX_API_KEY = "your_watsonx_api_key_here"
WATSONX_PROJECT_ID = "your_watsonx_project_id_here"
WATSONX_MODEL_ID = "openai/gpt-oss-120b"  # or your preferred model
```

### Method 2: Using Environment Variables
Set the following environment variables:

```bash
export WATSONX_API_KEY="your_watsonx_api_key_here"
export WATSONX_PROJECT_ID="your_watsonx_project_id_here"
export WATSONX_MODEL_ID="openai/gpt-oss-120b"
```

## Usage

### Basic Usage
```python
from watsonx.watsonx import search_expenses, RAG_response

# Search for relevant expenses
results = search_expenses("restaurant expenses")

# Generate AI response with context
response = RAG_response("How much did I spend on restaurants?", results)
print(response)
```

### Testing Connection
```python
from watsonx.watsonx import test_watsonx_connection

success, message = test_watsonx_connection()
if success:
    print("Watsonx connection successful!")
else:
    print(f"Connection failed: {message}")
```

### Integration with Flask App
The integration is automatically used when you set the `AI_SERVICE` environment variable:

```bash
export AI_SERVICE=watsonx
python app.py
```

## API Endpoints

When using the Watsonx integration, the following API endpoints are available:

- **`/banko`**: Main chat interface (automatically uses Watsonx when configured)
- **`/ai-status`**: Check the status of AI services including Watsonx connectivity

## Error Handling

The integration includes comprehensive error handling:
- Connection timeouts and network errors
- Invalid API responses
- Missing configuration
- Graceful fallback to AWS Bedrock if Watsonx fails

## Model Options

The integration supports various IBM Watsonx models:
- `openai/gpt-oss-120b` (default)
- `meta-llama/llama-2-70b-chat`
- `ibm/granite-13b-chat-v2`
- And other models available in your Watsonx project

## Debugging

Enable debug mode by setting the Flask app to debug mode. The integration includes:
- Detailed logging of API calls
- Search result debugging
- Connection status monitoring
- Response format validation

## Security Considerations

- API keys are never logged or exposed in responses
- All API communications use HTTPS
- Configuration supports both environment variables and config files
- Timeouts prevent hanging requests

## Dependencies

The Watsonx integration requires:
- `requests`: For HTTP API calls
- `numpy`: For vector operations
- `sentence-transformers`: For embedding generation
- `sqlalchemy`: For database operations

## Troubleshooting

### Common Issues

1. **"Watsonx integration not available"**
   - Check that your API key is properly configured
   - Verify that the `requests` library is installed
   - Ensure the config.py file exists and has the correct variables

2. **"API key not found"**
   - Verify your `config.py` file has `WATSONX_API_KEY` defined
   - Or ensure the `WATSONX_API_KEY` environment variable is set

3. **"Connection timeout"**
   - Check your internet connection
   - Verify the Watsonx service is accessible from your network
   - Consider increasing the timeout value in the code if needed

4. **"Invalid response format"**
   - Ensure you're using a compatible model ID
   - Check that your project ID is correct
   - Verify your API key has the necessary permissions

### Testing Your Setup

#### Quick Connection Test
For a simple connection test:

```bash
cd watsonx
python test_connection.py
```

#### Full Demo
For a complete demonstration with interactive chat:

```bash
cd watsonx
python demo_watsonx.py
```

#### Manual Test
You can also test directly:

```bash
cd /path/to/your/project
python -c "from watsonx.watsonx import test_watsonx_connection; print(test_watsonx_connection())"
```

## Support

For issues specific to the Watsonx integration:
1. Check the configuration setup
2. Verify API key permissions
3. Test the connection using the provided test function
4. Review the Flask app logs for detailed error messages

For IBM Watsonx-specific issues, consult the IBM Watsonx documentation or contact IBM support.
