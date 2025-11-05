#!/bin/bash
set -e

echo "🏦 Banko AI Assistant - Docker Entrypoint"
echo "========================================="

# Extract database host from DATABASE_URL
DB_HOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:]*\):.*/\1/p')
DB_PORT=$(echo $DATABASE_URL | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')

echo "📡 Waiting for CockroachDB at ${DB_HOST}:${DB_PORT}..."

# Wait for CockroachDB to be ready
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s -f "http://${DB_HOST}:8080/health?ready=1" > /dev/null 2>&1; then
        echo "✅ CockroachDB is ready!"
        break
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "⏳ Waiting for CockroachDB... (attempt $RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "❌ Failed to connect to CockroachDB after $MAX_RETRIES attempts"
    exit 1
fi

# Enable vector index feature (idempotent - safe to run multiple times)
echo "🔧 Enabling vector index feature..."

# Build cockroach sql command based on DATABASE_URL
COCKROACH_CMD="cockroach sql --url=\"${DATABASE_URL}\""

# Try to enable vector index feature
# If it fails, it might already be enabled or we don't have permissions (that's okay for production)
if command -v cockroach &> /dev/null; then
    # If cockroach CLI is available in the container
    cockroach sql --url="${DATABASE_URL}" --execute="SET CLUSTER SETTING feature.vector_index.enabled = true;" 2>/dev/null || \
        echo "⚠️  Could not enable vector index feature (may already be enabled or CLI not available)"
else
    echo "ℹ️  CockroachDB CLI not available in container - vector index feature should be enabled manually or via init container"
fi

echo "🚀 Starting Banko AI Assistant..."
echo ""

# Execute the main command (passed as arguments to this script)
exec "$@"
