#!/bin/bash
set -e

IMAGE_NAME=${1:-quay.io/rhpds/central-api}
TAG=${2:-latest}

CONTAINER_CMD="${CONTAINER_CMD:-podman}"
if ! command -v "$CONTAINER_CMD" &>/dev/null; then
  CONTAINER_CMD="docker"
fi

echo "Building Central API image: ${IMAGE_NAME}:${TAG} using ${CONTAINER_CMD}"

# Build the image for linux/amd64 platform
"${CONTAINER_CMD}" build --platform linux/amd64 -t ${IMAGE_NAME}:${TAG} -f Containerfile .

echo "Image built successfully: ${IMAGE_NAME}:${TAG}"
echo ""
echo "To push the image:"
echo "  ${CONTAINER_CMD} push ${IMAGE_NAME}:${TAG}"
