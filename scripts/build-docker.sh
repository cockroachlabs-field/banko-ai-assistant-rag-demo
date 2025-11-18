#!/bin/bash
#
# Multi-architecture Docker Build Script for Banko AI Assistant
# Builds for both amd64 and arm64 platforms
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DOCKER_REPO="virag/banko-ai-assistant"
PLATFORMS="linux/amd64,linux/arm64"
TIMESTAMP=$(date +%Y.%m.%d-%H%M)

# Parse command line arguments
PUSH=false
TAG="latest"

while [[ $# -gt 0 ]]; do
    case $1 in
        --push)
            PUSH=true
            shift
            ;;
        --tag)
            TAG="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --push          Push the built images to Docker Hub"
            echo "  --tag TAG       Specify additional custom tag (latest and timestamp always included)"
            echo "  --help          Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                           # Build locally"
            echo "  $0 --push                    # Build and push: latest + timestamp"
            echo "  $0 --push --tag v1.0.33      # Build and push: latest + v1.0.33 + timestamp"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Banko AI Assistant - Multi-Arch Docker Build        ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Repository:${NC} ${DOCKER_REPO}"
echo -e "${GREEN}Platforms:${NC}  ${PLATFORMS}"
echo -e "${GREEN}Tag:${NC}        ${TAG}"
echo -e "${GREEN}Timestamp:${NC}  ${TIMESTAMP}"
echo -e "${GREEN}Push:${NC}       ${PUSH}"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    exit 1
fi

# Check if buildx is available
if ! docker buildx version &> /dev/null; then
    echo -e "${RED}Error: Docker buildx is not available${NC}"
    echo "Please install Docker Desktop or enable buildx"
    exit 1
fi

# Create or use existing buildx builder
echo -e "${YELLOW}→ Setting up buildx builder...${NC}"
if ! docker buildx inspect multiarch-builder &> /dev/null; then
    echo "Creating new builder 'multiarch-builder'..."
    docker buildx create --name multiarch-builder --use
else
    echo "Using existing builder 'multiarch-builder'..."
    docker buildx use multiarch-builder
fi

# Bootstrap the builder
docker buildx inspect --bootstrap

echo ""
echo -e "${YELLOW}→ Building Docker image for ${PLATFORMS}...${NC}"
echo ""

# Prepare build command
if [ "$PUSH" = true ]; then
    echo -e "${GREEN}Building multi-arch and pushing to Docker Hub...${NC}"
    BUILD_CMD="docker buildx build --platform ${PLATFORMS} --push"
    BUILD_CMD="${BUILD_CMD} -t ${DOCKER_REPO}:latest"
    BUILD_CMD="${BUILD_CMD} -t ${DOCKER_REPO}:${TIMESTAMP}"
    # If custom tag is provided and different from 'latest', add it
    if [ "$TAG" != "latest" ]; then
        BUILD_CMD="${BUILD_CMD} -t ${DOCKER_REPO}:${TAG}"
    fi
else
    echo -e "${GREEN}Building for local platform only (use --push for multi-arch)...${NC}"
    echo -e "${YELLOW}Note: Local builds are single-platform. Use --push for multi-arch builds.${NC}"
    BUILD_CMD="docker buildx build --load"
    BUILD_CMD="${BUILD_CMD} -t ${DOCKER_REPO}:${TAG}"
fi

BUILD_CMD="${BUILD_CMD} ."

echo -e "${BLUE}Command:${NC} ${BUILD_CMD}"
echo ""

# Execute build
if $BUILD_CMD; then
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║             Build completed successfully!             ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    if [ "$PUSH" = true ]; then
        echo -e "${GREEN}✓ Images pushed to Docker Hub:${NC}"
        echo -e "  • ${DOCKER_REPO}:latest"
        echo -e "  • ${DOCKER_REPO}:${TIMESTAMP}"
        if [ "$TAG" != "latest" ]; then
            echo -e "  • ${DOCKER_REPO}:${TAG}"
        fi
        echo ""
        echo -e "${BLUE}View on Docker Hub:${NC}"
        echo -e "  https://hub.docker.com/r/${DOCKER_REPO}/tags"
    else
        echo -e "${GREEN}✓ Image built locally:${NC}"
        echo -e "  • ${DOCKER_REPO}:${TAG}"
        echo ""
        echo -e "${YELLOW}Note: Image was built for ${PLATFORMS} but only loaded for current architecture${NC}"
        echo -e "${BLUE}To push to Docker Hub, run:${NC}"
        echo -e "  ./build-docker.sh --push"
    fi
    
    echo ""
    echo -e "${BLUE}To run the image:${NC}"
    echo -e "  docker run -p 5000:5000 -e DATABASE_URL=... -e AI_SERVICE=... ${DOCKER_REPO}:${TAG}"
    echo ""
    echo -e "${BLUE}To use with docker-compose:${NC}"
    echo -e "  docker-compose up -d"
    echo ""
else
    echo ""
    echo -e "${RED}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║                Build failed!                           ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════════════╝${NC}"
    exit 1
fi
