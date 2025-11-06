#!/bin/bash
#
# Banko AI - Demo Mode Startup Script
# Configures cache for aggressive caching (more cache hits for demos)
#

echo "🚀 Starting Banko AI in DEMO MODE"
echo "================================="
echo ""
echo "Cache Configuration:"
echo "  - Similarity Threshold: 0.75 (balanced)"
echo "  - Strict Mode: FALSE (lenient - cache on similarity alone)"
echo "  - TTL: 24 hours"
echo ""
echo "This configuration provides:"
echo "  ✅ High cache hit rate (~80-90%)"
echo "  ✅ Fast responses"
echo "  ⚠️  May return cached response with slightly different data"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""
echo "================================="

# Set cache configuration for demo mode
export CACHE_SIMILARITY_THRESHOLD="0.75"
export CACHE_STRICT_MODE="false"
export CACHE_TTL_HOURS="24"

# Keep your existing AI and database config
# These should already be set in your environment or you can add them here:
# export AI_SERVICE="watsonx"
# export DATABASE_URL="cockroachdb://root@localhost:26257/defaultdb?sslmode=disable"

# Start the app
banko-ai run
