#!/bin/bash
#
# Deploy Publishing House Delta from infra01 to infra02
# Generated: 2026-08-31
# Updated: Includes workflow image 1.6 update
#

set -e

INFRA02_CONTEXT="publishing-house/api-ocpv-infra02-wdc07-infra-demo-redhat-com:6443/treddy@redhat.com"
NAMESPACE="publishing-house"

echo "================================================================"
echo "Publishing House - Deploy Delta to infra02"
echo "================================================================"
echo

# Switch to infra02
echo "→ Switching to infra02 context..."
oc config use-context "$INFRA02_CONTEXT"
echo

# 1. Deploy dynamic-plugins ConfigMap
echo "→ Step 1: Deploying dynamic-plugins ConfigMap..."
if oc get configmap dynamic-plugins -n $NAMESPACE &>/dev/null; then
    echo "  ⚠️  ConfigMap 'dynamic-plugins' already exists. Updating..."
    oc apply -f /tmp/dynamic-plugins-deployable.yaml -n $NAMESPACE
else
    echo "  ✅ Creating new ConfigMap..."
    oc apply -f /tmp/dynamic-plugins-deployable.yaml -n $NAMESPACE
fi
echo

# 2. Update publishinghouseworkflow to version 1.6
echo "→ Step 2: Updating SonataFlow workflow to version 1.6..."
CURRENT_IMAGE=$(oc get sonataflow publishinghouseworkflow -n $NAMESPACE -o jsonpath='{.spec.podTemplate.container.image}')
echo "  Current: $CURRENT_IMAGE"
echo "  Target:  quay.io/rhpds/publishing-house-workflow:1.6"

if [[ "$CURRENT_IMAGE" == "quay.io/rhpds/publishing-house-workflow:1.6" ]]; then
    echo "  ✅ Already at target version"
else
    oc patch sonataflow publishinghouseworkflow -n $NAMESPACE \
      --type=merge \
      -p '{"spec":{"podTemplate":{"container":{"image":"quay.io/rhpds/publishing-house-workflow:1.6"}}}}'
    echo "  ✅ SonataFlow CR updated, rollout will begin"
fi
echo

# 3. Update central-api to 1.21.19 (latest)
echo "→ Step 3: Updating central-api to version 1.21.19..."
CURRENT_IMAGE=$(oc get deployment central-api -n $NAMESPACE -o jsonpath='{.spec.template.spec.containers[0].image}')
echo "  Current: $CURRENT_IMAGE"
echo "  Target:  quay.io/rhpds/central-api:1.21.19"

if [[ "$CURRENT_IMAGE" == "quay.io/rhpds/central-api:1.21.19" ]]; then
    echo "  ✅ Already at target version"
else
    oc set image deployment/central-api \
      central-api=quay.io/rhpds/central-api:1.21.19 \
      -n $NAMESPACE
    echo "  ✅ Image updated, rollout started"
fi
echo

# 4. Restart RHDH to pick up dynamic-plugins ConfigMap
echo "→ Step 4: Restarting RHDH to load dynamic-plugins..."
oc rollout restart deployment/backstage-developer-hub -n $NAMESPACE
echo "  ✅ Rollout restart initiated"
echo

# 5. Wait for rollouts
echo "→ Step 5: Waiting for rollouts to complete..."
echo "  Waiting for publishinghouseworkflow..."
oc rollout status deployment/publishinghouseworkflow -n $NAMESPACE --timeout=5m

echo "  Waiting for central-api..."
oc rollout status deployment/central-api -n $NAMESPACE --timeout=5m

echo "  Waiting for backstage-developer-hub..."
oc rollout status deployment/backstage-developer-hub -n $NAMESPACE --timeout=5m
echo

# 6. Verification
echo "================================================================"
echo "Deployment Complete - Verification"
echo "================================================================"
echo

echo "✅ SonataFlow Workflow version:"
oc get sonataflow publishinghouseworkflow -n $NAMESPACE -o jsonpath='{.spec.podTemplate.container.image}'
echo
echo

echo "✅ Central API version:"
oc get deployment central-api -n $NAMESPACE -o jsonpath='{.spec.template.spec.containers[0].image}'
echo
echo

echo "✅ RHDH pods:"
oc get pods -n $NAMESPACE -l app.kubernetes.io/name=backstage
echo

echo "✅ Workflow pods:"
oc get pods -n $NAMESPACE -l app=publishinghouseworkflow
echo

echo "✅ ConfigMap deployed:"
oc get configmap dynamic-plugins -n $NAMESPACE -o jsonpath='{.metadata.name}'
echo
echo

echo "================================================================"
echo "Next Steps"
echo "================================================================"
echo
echo "1. Verify RHDH dashboard:"
echo "   https://developer-hub-publishing-house.apps.ocpv-infra02.wdc07.infra.demo.redhat.com"
echo
echo "2. Check Publishing House plugin loaded:"
echo "   Navigate to: /publishing-house-workflows"
echo
echo "3. Verify Home Card appears on dashboard home"
echo
echo "4. Test workflow creation via template"
echo
echo "5. Check logs for errors:"
echo "   oc logs deployment/backstage-developer-hub -n $NAMESPACE --tail=100"
echo "   oc logs deployment/publishinghouseworkflow -n $NAMESPACE --tail=100"
echo "   oc logs deployment/central-api -n $NAMESPACE --tail=100"
echo
echo "================================================================"
echo "Deployment script completed successfully!"
echo "================================================================"
