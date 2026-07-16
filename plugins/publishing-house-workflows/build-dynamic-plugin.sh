#!/bin/bash
# Build and push the Publishing House Workflows RHDH dynamic plugin as an OCI image
# Prerequisites: node 18+, npx, podman, quay.io login
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

echo "==> Building plugin version ${VERSION}"

cd "${PLUGIN_DIR}"

# Clean previous build artifacts
rm -rf dist-dynamic dist node_modules yarn.lock

# Step 1: Install dependencies
echo "==> Installing dependencies..."
npm install --legacy-peer-deps 2>&1 | tail -3

# Step 2: Export dynamic plugin
echo "==> Exporting dynamic plugin..."
npx --yes @red-hat-developer-hub/cli@1.8.0 plugin export 2>&1

if [ ! -d "${PLUGIN_DIR}/dist-dynamic/dist-scalprum" ]; then
  echo "ERROR: Export failed - dist-dynamic/dist-scalprum not found"
  exit 1
fi

echo "==> Export successful"

# Step 3: Package as OCI image (amd64 for cluster deployment)
echo "==> Packaging as OCI image: ${IMAGE}"
npx --yes @red-hat-developer-hub/cli@1.8.0 plugin package --tag "${IMAGE}"

echo "==> Image built: ${IMAGE}"

# Step 4: Push to quay.io
if [ "${NO_PUSH}" = "--no-push" ]; then
  echo "==> Skipping push (--no-push)"
else
  echo "==> Pushing to quay.io..."
  podman push "${IMAGE}"
  echo "==> Pushed: ${IMAGE}"
fi

echo ""
echo "==> Done. Update backstage-dynamic-plugins ConfigMap:"
echo ""
echo "  oc get configmap backstage-dynamic-plugins -n backstage -o yaml | \\"
echo "    sed 's|ph-workflows:[0-9.]*|ph-workflows:${VERSION}|' | oc apply -f -"
echo "  oc rollout restart deployment backstage-developer-hub -n backstage"
