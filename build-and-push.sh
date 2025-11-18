#!/bin/bash
# Build and push multi-architecture Docker image
set -e

IMAGE_NAME="${1:-virag/banko-ai-assistant}"
TAG="${2:-latest}"

echo "🐳 Building Multi-Architecture Docker Image"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Image: $IMAGE_NAME:$TAG"
echo "Platforms: linux/amd64, linux/arm64"
echo ""

# Check if buildx is available
if ! docker buildx version > /dev/null 2>&1; then
    echo "❌ docker buildx not found. Please install Docker with buildx support."
    exit 1
fi

# Create or use existing builder
if ! docker buildx inspect multiarch > /dev/null 2>&1; then
    echo "📦 Creating multiarch builder..."
    docker buildx create --name multiarch --use
    docker buildx inspect --bootstrap
else
    echo "✅ Using existing multiarch builder"
    docker buildx use multiarch
fi

# Build and push
echo ""
echo "🔨 Building and pushing image..."
echo ""

docker buildx build \
    --platform linux/amd64,linux/arm64 \
    -t "$IMAGE_NAME:$TAG" \
    --push \
    .

echo ""
echo "✅ Successfully built and pushed: $IMAGE_NAME:$TAG"
echo ""
echo "Verify on Docker Hub:"
echo "  https://hub.docker.com/r/${IMAGE_NAME#*/}/tags"
echo ""
echo "Pull and test:"
echo "  docker pull $IMAGE_NAME:$TAG"
echo "  docker run -p 5000:5000 -e AI_SERVICE=openai -e OPENAI_API_KEY=your_key $IMAGE_NAME:$TAG"
