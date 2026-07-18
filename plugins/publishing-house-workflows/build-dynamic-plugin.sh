#!/bin/bash
# Build and push the Publishing House Workflows RHDH dynamic plugin as an OCI image
# Uses the Containerfile with the required io.backstage.dynamic-packages annotation
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

# Compute the OCI annotation from package.json
ANNOTATION=$(node -e "
  const pkg = require('./package.json');
  const meta = [{ [pkg.name]: {
    name: pkg.name + '-dynamic',
    version: pkg.version,
    backstage: pkg.backstage,
    license: pkg.license
  }}];
  process.stdout.write(Buffer.from(JSON.stringify(meta)).toString('base64'));
")

# Build the image with the annotation
echo "==> Building OCI image: ${IMAGE}"
podman build --platform linux/amd64 \
  --annotation "io.backstage.dynamic-packages=${ANNOTATION}" \
  -t "${IMAGE}" -f Containerfile .

echo "==> Image built: ${IMAGE}"

# Push to quay.io
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
echo "  oc get configmap ph-developer-hub-dynamic-plugins -n publishing-house -o yaml | \\"
echo "    sed 's|ph-workflows:[0-9.]*|ph-workflows:${VERSION}|' | oc apply -f -"
echo "  oc rollout restart deployment backstage-developer-hub -n publishing-house"
