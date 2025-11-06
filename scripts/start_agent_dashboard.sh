#!/bin/bash
# Start Banko AI with Agent Dashboard and WebSocket support

# Set up environment
export FLASK_APP=banko_ai.web.app:create_app
export FLASK_ENV=development

# Disable tokenizers parallelism warning
export TOKENIZERS_PARALLELISM=false

# Get port from environment or use default
PORT=${PORT:-5001}

echo "🚀 Starting Banko AI with Agent Dashboard..."
echo "   Dashboard URL: http://localhost:$PORT/agents"
echo "   Main App URL: http://localhost:$PORT/"
echo ""

# Run with eventlet for WebSocket support
python3 -c "
from banko_ai.web.app import create_app
import eventlet

app = create_app()
socketio = app.socketio

print('✅ Agent Dashboard ready at /agents')
print('✅ WebSocket server initialized')
print('')

# Run with SocketIO
socketio.run(app, host='0.0.0.0', port=$PORT, debug=True)
"
