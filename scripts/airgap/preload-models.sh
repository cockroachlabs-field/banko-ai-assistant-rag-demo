#!/usr/bin/env bash
# Pull the airgap model into the compose volume while still online.
# Run once with a network connection; after that the airgap stack starts
# without ever leaving the machine.
set -euo pipefail
cd "$(dirname "$0")/../.."

MODEL="${OLLAMA_MODEL:-granite3.3:8b}"

docker compose -f docker-compose.airgap.yml up -d ollama
echo "Pulling ${MODEL} into the ollama-models volume..."
docker compose -f docker-compose.airgap.yml exec ollama ollama pull "$MODEL"

echo "Warming the embedding model cache..."
docker compose -f docker-compose.airgap.yml run --rm \
    -e HF_HUB_OFFLINE=0 -e TRANSFORMERS_OFFLINE=0 banko-ai \
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

echo "Done. Models are cached in named volumes. You can go offline and run:"
echo "  docker compose -f docker-compose.airgap.yml up -d"
