#!/bin/bash
# Build and push the scaffolder-backend-module-publishing-house RHDH dynamic plugin as an OCI image
#
# Usage:
#   ./build-dynamic-plugin.sh                    # build and push 1.0.0
#   ./build-dynamic-plugin.sh 1.0.1              # build and push custom version
#   ./build-dynamic-plugin.sh 1.0.0 --no-push    # build only, skip push

set -euo pipefail

VERSION="${1:-1.0.0}"
NO_PUSH="${2:-}"
PLUGIN_DIR="$(cd "$(dirname "$0")" && pwd)"
IMAGE="quay.io/rhpds/backstage-plugin-scaffolder-backend-module-publishing-house:${VERSION}"

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
podman build --platform linux/amd64 --no-cache \
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
echo "==> Done. Update backstage-dynamic-plugins ConfigMap and restart RHDH."
