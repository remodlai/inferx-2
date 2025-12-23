#!/bin/bash
# Build Scheduler Docker image using buildx for multi-platform support

set -e

# Configuration
IMAGE_NAME="remodlai/inferx-scheduler"
TAG="${1:-latest}"

# Change to parent directory to include inferx-common in build context
cd "$(dirname "$0")/.."

echo "Building $IMAGE_NAME:$TAG for linux/amd64..."

# Build for linux/amd64 (for EKS/x86_64 nodes)
docker buildx build \
    --platform linux/amd64 \
    -t $IMAGE_NAME:$TAG \
    --load \
    -f scheduler/Dockerfile \
    .

echo "✅ Build complete: $IMAGE_NAME:$TAG"
echo ""
echo "To push to registry:"
echo "  docker push $IMAGE_NAME:$TAG"
echo ""
echo "To build and push in one step:"
echo "  docker buildx build --platform linux/amd64 -t $IMAGE_NAME:$TAG --push ."
