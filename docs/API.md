# 🔗 Banko AI Assistant API Documentation

## Core Endpoints

### Chat Interface
- **POST `/banko`** - Main chat endpoint
  - Body: `user_input=<query>`
  - Returns: HTML response with AI answer

### Health & Status
- **GET `/ai-status`** - Check AI service connectivity
- **GET `/cache-stats`** - View cache performance metrics
- **POST `/cache-cleanup`** - Manually trigger cache cleanup

### Web Interface
- **GET `/`** - Main chat interface (redirects to `/banko`)
- **GET `/banko`** - Chat interface
- **GET `/home`** - Landing page

## Response Formats

### AI Status Response
```json
{
    "active_service_name": "IBM Watsonx",
    "current_service": "watsonx",
    "watsonx_available": true,
    "aws_bedrock_available": true,
    "caching_enabled": true,
    "database": {
        "connected": true,
        "status": "Connected to CCL",
        "record_count": 3000
    }
}
```

### Cache Stats Response
```json
{
    "cache_enabled": true,
    "time_period": "24 hours",
    "overall_metrics": {
        "total_requests": 45,
        "total_hits": 23,
        "overall_hit_rate": 51.11,
        "total_tokens_saved": 1250,
        "estimated_cost_savings_usd": 0.025
    },
    "cache_details": {
        "embedding": {"hits": 15, "misses": 8, "hit_rate": 65.22},
        "vector_search": {"hits": 12, "misses": 10, "hit_rate": 54.55},
        "response": {"hits": 8, "misses": 14, "hit_rate": 36.36}
    }
}
```

## Usage Examples

### cURL Examples
```bash
# Check system health
curl http://localhost:5000/ai-status

# Send a chat message
curl -X POST http://localhost:5000/banko \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "user_input=Show me my grocery spending"

# View cache performance
curl http://localhost:5000/cache-stats

# Clear cache
curl -X POST http://localhost:5000/cache-cleanup
```

### Python Examples
```python
import requests

# Check AI status
response = requests.get('http://localhost:5000/ai-status')
print(response.json())

# Send chat query
response = requests.post('http://localhost:5000/banko', 
                        data={'user_input': 'What are my top expenses?'})
print(response.text)

# Get cache stats
response = requests.get('http://localhost:5000/cache-stats')
print(response.json())
```

## Environment Variables

| Variable       | Description                                 | Default                                                        | Required |
|----------------|---------------------------------------------|----------------------------------------------------------------|----------|
| `AI_SERVICE`   | AI provider to use (`watsonx` or `bedrock`) | `watsonx`                                                      | No       |
| `DATABASE_URL` | CockroachDB connection string               | `cockroachdb://root@localhost:26257/defaultdb?sslmode=disable` | No       |
| `FLASK_ENV`    | Flask environment                           | `production`                                                   | No       |

## Error Responses

### Common Error Codes
- **503** - AI service unavailable
- **500** - Internal server error
- **400** - Bad request (missing user_input)

### Error Response Format
```json
{
    "error": "Error description",
    "details": "Additional error details"
}
```
