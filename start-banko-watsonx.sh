#!/bin/bash

# Banko AI Assistant Startup Script with Watsonx
# This script sets the correct environment variables and starts the app

echo "🚀 Starting Banko AI Assistant with Watsonx..."
echo "Setting up environment variables..."

export DATABASE_URL="cockroachdb://root@localhost:26257/defaultdb?sslmode=disable"
export AI_SERVICE="watsonx"

echo "✅ Environment configured:"
echo "   - AI Service: $AI_SERVICE"
echo "   - Database: CockroachDB (localhost:26257)"
echo ""

echo "Starting Flask application..."
python app.py
