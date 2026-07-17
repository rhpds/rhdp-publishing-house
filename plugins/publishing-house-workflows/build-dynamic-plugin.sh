#!/bin/bash
# Build and push the Publishing House Workflows RHDH dynamic plugin as an OCI image
# Uses a multi-stage Containerfile — no local node/npm required, only podman or docker
#
# Usage:
#   ./build-dynamic-plugin.sh                    # build and push 0.1.0
#   ./build-dynamic-plugin.sh 0.2.0              # build and push custom version
#   ./build-dynamic-plugin.sh 0.2.0 --no-push    # build only, skip push

set -euo pipefail

VERSION="${1:-0.1.0}"
NO_PUSH="${2:-}"
PLUGIN_DIR="$(cd "$(dirname "$0")" && pwd)"
IMAGE="quay.io/rhpds/backstage-plugin-ph-workflows:${VERSION}"

CONTAINER_CMD="${CONTAINER_CMD:-podman}"
if ! command -v "$CONTAINER_CMD" &>/dev/null; then
  CONTAINER_CMD="docker"
fi

echo "==> Building plugin version ${VERSION} using ${CONTAINER_CMD}"

cd "${PLUGIN_DIR}"

# Build OCI image via multi-stage Containerfile
"${CONTAINER_CMD}" build \
  --platform linux/amd64 \
  -t "${IMAGE}" \
  -f Containerfile .

echo "==> Image built: ${IMAGE}"

# Push to quay.io
if [ "${NO_PUSH}" = "--no-push" ]; then
  echo "==> Skipping push (--no-push)"
else
  echo "==> Pushing to quay.io..."
  "${CONTAINER_CMD}" push "${IMAGE}"
  echo "==> Pushed: ${IMAGE}"
fi

echo ""
echo "==> Done. Update backstage-dynamic-plugins ConfigMap:"
echo ""
echo "  oc get configmap ph-developer-hub-dynamic-plugins -n publishing-house -o yaml | \\"
echo "    sed 's|ph-workflows:[0-9.]*|ph-workflows:${VERSION}|' | oc apply -f -"
echo "  oc rollout restart deployment backstage-developer-hub -n publishing-house"
