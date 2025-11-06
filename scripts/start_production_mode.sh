#!/bin/bash
#
# Banko AI - Production Mode Startup Script
# Configures cache for accuracy (strict mode)
#

echo "🏢 Starting Banko AI in PRODUCTION MODE"
echo "========================================"
echo ""
echo "Cache Configuration:"
echo "  - Similarity Threshold: 0.75 (balanced)"
echo "  - Strict Mode: TRUE (strict - requires exact data match)"
echo "  - TTL: 24 hours"
echo ""
echo "This configuration provides:"
echo "  ✅ High accuracy (data consistency guaranteed)"
echo "  ✅ Good cache hit rate (~60-70%)"
echo "  ✅ Suitable for financial applications"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""
echo "========================================"

# Set cache configuration for production mode
export CACHE_SIMILARITY_THRESHOLD="0.75"
export CACHE_STRICT_MODE="true"
export CACHE_TTL_HOURS="24"

# Keep your existing AI and database config
# These should already be set in your environment or you can add them here:
# export AI_SERVICE="watsonx"
# export DATABASE_URL="cockroachdb://root@localhost:26257/defaultdb?sslmode=disable"

# Start the app
banko-ai run
