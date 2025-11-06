#!/bin/bash
# Quick Demo Startup Script

echo "🚀 Starting Banko AI Demo with Agents"
echo "======================================================================"
echo ""

# Kill any existing server on port 5001
echo "1️⃣  Stopping old server (if running)..."
lsof -ti:5001 2>/dev/null | xargs kill -9 2>/dev/null
sleep 2
echo "   ✅ Port 5001 cleared"
echo ""

# Set environment variables
echo "2️⃣  Setting environment variables..."
export AI_SERVICE=openai
export TOKENIZERS_PARALLELISM=false
export DATABASE_URL="cockroachdb://root@localhost:26257/defaultdb?sslmode=disable"

echo "   DEBUG: AI_SERVICE=${AI_SERVICE}"
echo "   DEBUG: OPENAI_API_KEY is ${OPENAI_API_KEY:+SET}"

# Check for OpenAI key
if [ -z "$OPENAI_API_KEY" ]; then
    echo "   ⚠️  OPENAI_API_KEY not set!"
    echo "   Run: export OPENAI_API_KEY='sk-...'"
    exit 1
fi
echo "   ✅ OPENAI_API_KEY: ${OPENAI_API_KEY:0:10}..."
echo "   ✅ AI_SERVICE: $AI_SERVICE"
echo ""

# Check database
echo "3️⃣  Checking CockroachDB..."
if curl -s http://localhost:26257/health?ready=1 | grep -q "ok"; then
    echo "   ✅ CockroachDB running"
else
    echo "   ⚠️  CockroachDB not responding"
    echo "   Start it with: cockroach start-single-node --insecure &"
    exit 1
fi
echo ""

# Start server
echo "4️⃣  Starting server..."
echo "   📊 Main App: http://localhost:5001/"
echo "   📊 Dashboard: http://localhost:5001/agents"
echo ""
echo "   Features:"
echo "   • 📄 Receipt upload button (in chat)"
echo "   • 🤖 Agent Dashboard link (in sidebar)"
echo "   • 🔍 Real-time agent visualization"
echo ""
echo "   Press Ctrl+C to stop"
echo ""

# Run server
python3 test_dashboard.py
