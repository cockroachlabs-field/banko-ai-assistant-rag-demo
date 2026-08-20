#!/usr/bin/env bash
# Pull the airgap models into the compose volumes while still online.
# Run once with a network connection; after that the airgap stack starts
# without ever leaving the machine.
#
# This script pulls models and nothing else: no database, no app, and it
# stops the ollama container it briefly needs before exiting. (Optional
# since the compose file grew an ollama-init service, but this remains
# the explicit night-before-a-talk path.)
set -euo pipefail
cd "$(dirname "$0")/../.."

MODEL="${OLLAMA_MODEL:-granite3.3:8b}"
COMPOSE="docker compose -f docker-compose.airgap.yml"

# The ollama daemon has to run to pull into the ollama-models volume;
# --no-deps keeps it to just that one container, and it is stopped below.
$COMPOSE up -d --no-deps ollama
echo "Pulling ${MODEL} into the ollama-models volume..."
$COMPOSE exec ollama ollama pull "$MODEL"
$COMPOSE stop ollama
echo "ollama stopped again; model is in the named volume."

echo "Warming the embedding model cache..."
# --no-deps so this does not drag up cockroachdb and the rest of the
# stack; the one-liner only touches the hf-cache volume.
$COMPOSE run --rm --no-deps \
    -e HF_HUB_OFFLINE=0 -e TRANSFORMERS_OFFLINE=0 banko-ai \
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

echo "Done. Models are cached in named volumes and nothing was left running."
echo "You can go offline and run:"
echo "  docker compose -f docker-compose.airgap.yml up -d"
