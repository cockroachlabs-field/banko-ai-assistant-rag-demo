#!/bin/bash
set -e

echo "🏦 Banko AI Assistant - Starting..."
echo "========================================="
echo ""

# Docker Compose already handles:
# - Waiting for CockroachDB to be healthy
# - Running cockroach-init to enable vector index feature
# So we just start the application directly

echo "🚀 Starting Banko AI Assistant..."
echo ""

# Execute the main command (passed as arguments to this script)
exec "$@"
