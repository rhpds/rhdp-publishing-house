#!/bin/bash
set -e

IMAGE_NAME=${1:-quay.io/treddy08/central-api}
TAG=${2:-latest}

echo "Building Central API image: ${IMAGE_NAME}:${TAG}"

# Build the image for linux/amd64 platform
podman build --platform linux/amd64 -t ${IMAGE_NAME}:${TAG} -f Dockerfile .

echo "Image built successfully: ${IMAGE_NAME}:${TAG}"
echo ""
echo "To push the image:"
echo "  podman push ${IMAGE_NAME}:${TAG}"
