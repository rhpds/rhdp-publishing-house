#!/bin/bash
# Build and push the Publishing House Maintenance RHDH dynamic plugin as an OCI image

set -euo pipefail

VERSION="${1:-1.0.0}"
NO_PUSH="${2:-}"
PLUGIN_DIR="$(cd "$(dirname "$0")" && pwd)"
IMAGE="quay.io/rhpds/backstage-plugin-ph-maintenance:${VERSION}"

echo "==> Building plugin version ${VERSION}"

cd "${PLUGIN_DIR}"

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

echo "==> Building OCI image: ${IMAGE}"
podman build --platform linux/amd64 --no-cache \
  --annotation "io.backstage.dynamic-packages=${ANNOTATION}" \
  -t "${IMAGE}" -f Containerfile .

echo "==> Image built: ${IMAGE}"

if [ "${NO_PUSH}" = "--no-push" ]; then
  echo "==> Skipping push (--no-push)"
else
  echo "==> Pushing to quay.io..."
  podman push "${IMAGE}"
  echo "==> Pushed: ${IMAGE}"
fi

echo ""
echo "==> Done."
