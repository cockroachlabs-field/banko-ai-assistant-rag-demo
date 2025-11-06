#!/bin/bash
# Restart the dashboard server to pick up template changes

echo "🔄 Restarting Agent Dashboard Server..."

# Find and kill existing test_dashboard process
PID=$(ps aux | grep -E "[t]est_dashboard" | awk '{print $2}' | head -1)
if [ ! -z "$PID" ]; then
    echo "   Stopping old server (PID: $PID)..."
    kill $PID 2>/dev/null
    sleep 2
fi

# Start new server
echo "   Starting new server..."
python test_dashboard.py &
NEW_PID=$!

echo ""
echo "✅ Server restarted!"
echo "   New PID: $NEW_PID"
echo "   Dashboard: http://localhost:5001/agents"
echo ""
echo "   Wait 5 seconds for initialization, then test:"
echo "   python test_navigation.py"
