#!/bin/bash
set -e

echo "🏦 Banko AI Assistant - Starting..."
echo "========================================="
echo ""

# Docker Compose already handles:
# - Waiting for CockroachDB to be healthy
# - Running cockroach-init to enable vector index feature
# So we just start the application directly

# Gunicorn's multi-worker mode requires a stable SECRET_KEY, and the app
# refuses to invent one per worker (sessions would break across workers).
# Generating it here satisfies that: one key, all workers, this container
# run. A bare docker run works; sessions still reset when the container
# restarts, so set SECRET_KEY explicitly for stable demo sessions.
if [ -z "${SECRET_KEY:-}" ]; then
    export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
    echo "ℹ️  SECRET_KEY not provided; generated one for this container run."
    echo "   Sessions reset on container restart. Set -e SECRET_KEY=... to keep them."
    echo ""
fi

echo "🚀 Starting Banko AI Assistant..."
echo ""

# Execute the main command (passed as arguments to this script)
exec "$@"
