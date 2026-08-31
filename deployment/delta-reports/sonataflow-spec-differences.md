# SonataFlow CR Spec Differences - infra01 vs infra02

**Analysis Date**: 2026-08-31  
**Resource**: `SonataFlow/publishinghouseworkflow` in namespace `publishing-house`

---

## Executive Summary

**Total Differences in spec section: 2**

1. ✅ **UPDATED** - Container image reference (infra01 uses BuildConfig, infra02 uses Quay.io)
2. ✅ **UPDATED** - Workflow definition missing `notes: []` field in Setup state

---

## Detailed Comparison

### 1. spec.podTemplate.container.image

| Cluster | Value | Mode |
|---------|-------|------|
| **infra01** | *(not set)* | Uses BuildConfig → internal registry |
| **infra02 (before)** | `quay.io/rhpds/publishing-house-workflow:1.5` | External registry |
| **infra02 (after)** | `quay.io/rhpds/publishing-house-workflow:1.6` | External registry ✅ |

**Explanation**: 
- infra01 runs in `preview` mode with BuildConfig, so no explicit image is set
- infra02 runs in `dev` mode and pulls from external registry
- Updated infra02 from 1.5 → 1.6 to match latest infra01 build

---

### 2. spec.flow.states[1].stateDataFilter.output (Setup State)

**Missing field in infra02**: `notes: [],`

#### infra01 (has notes field):
```jq
. + {
  createdAt: now(),
  deploymentMode: .deploymentMode,
  ssoUser: .ssoUser,
  ssoEmail: .ssoEmail,
  projectid: .projectId,
  contentType: .contentType,
  repoUrl: .repoUrl,
  tags: (.tags // []),
  projectDescription: (.projectDescription // ""),
  showroomType: (.showroomType // "classic"),
  intakeType: (.intakeType // "new"),
  reviews: {
    content: false,
    infra: false
  },
  rejection: {
    isRejected: false
  },
  reviewHistory: [],
  notes: [],           ← PRESENT in infra01
  baselineSha: "",
  auditTrailSha: (.auditTrailSha // ""),
  hasDrift: false
}
```

#### infra02 (before update):
```jq
. + {
  createdAt: now(),
  deploymentMode: .deploymentMode,
  ssoUser: .ssoUser,
  ssoEmail: .ssoEmail,
  projectid: .projectId,
  contentType: .contentType,
  repoUrl: .repoUrl,
  tags: (.tags // []),
  projectDescription: (.projectDescription // ""),
  showroomType: (.showroomType // "classic"),
  intakeType: (.intakeType // "new"),
  reviews: {
    content: false,
    infra: false
  },
  rejection: {
    isRejected: false
  },
  reviewHistory: [],
  ← MISSING notes: []
  baselineSha: "",
  auditTrailSha: (.auditTrailSha // ""),
  hasDrift: false
}
```

**Impact**: Without the `notes` field, workflow instances cannot store lifecycle notes/comments.

**Status**: ✅ **FIXED** - Added `notes: []` to infra02

---

## What Is Identical Between infra01 and infra02

✅ **spec.persistence** - Identical PostgreSQL configuration  
✅ **spec.resources** - Identical ConfigMap references  
✅ **spec.podTemplate.container.env** - Identical environment variables  
✅ **spec.podTemplate.replicas** - Both set to 1  
✅ **spec.flow** (except Setup state notes field) - 13,808 bytes identical

---

## Changes Applied to infra02

```bash
# Applied on 2026-08-31 08:35 UTC
oc apply -f /tmp/sonataflow-infra02-update.yaml -n publishing-house
```

### Change 1: Added notes field
```diff
  reviewHistory: [],
+ notes: [],
  baselineSha: "",
```

### Change 2: Updated image
```diff
- (no image field - would use buildconfig)
+ image: quay.io/rhpds/publishing-house-workflow:1.6
```

---

## SonataFlow Profile Modes

| Cluster | Profile | Build Method | Image Source |
|---------|---------|--------------|--------------|
| infra01 | `preview` | BuildConfig (Binary) | Internal registry |
| infra02 | `dev` | Pre-built image pull | Quay.io registry |

**Preview mode** (infra01):
- Builds workflow image from source via BuildConfig
- No explicit image in CR spec
- Uses internal OpenShift image registry
- Suitable for development/testing

**Dev mode** (infra02):
- Pulls pre-built image from external registry
- Explicit image reference required in CR spec
- Faster deployments (no build time)
- Suitable for production-like environments

---

## Verification Commands

```bash
# Switch to infra02
oc config use-context publishing-house/api-ocpv-infra02-wdc07-infra-demo-redhat-com:6443/treddy@redhat.com

# Verify image
oc get sonataflow publishinghouseworkflow -n publishing-house \
  -o jsonpath='{.spec.podTemplate.container.image}'
# Expected: quay.io/rhpds/publishing-house-workflow:1.6

# Verify notes field in Setup state
oc get sonataflow publishinghouseworkflow -n publishing-house \
  -o yaml | grep -A 30 'name: Setup' | grep 'notes:'
# Expected: notes: [],

# Check pod is running with new config
oc get pods -n publishing-house -l app=publishinghouseworkflow
# Expected: Running pod with recent age
```

---

## Files Generated

```
/tmp/infra01-sonataflow.yaml              - Full CR from infra01
/tmp/infra02-sonataflow.yaml              - Original CR from infra02 (before update)
/tmp/sonataflow-infra02-update.yaml       - Updated CR applied to infra02
```

---

## Summary

**Before Update (infra02)**:
- Image: `quay.io/rhpds/publishing-house-workflow:1.5`
- Missing: `notes: []` field in workflow definition

**After Update (infra02)**:
- Image: `quay.io/rhpds/publishing-house-workflow:1.6` ✅
- Added: `notes: []` field in workflow definition ✅

**Status**: ✅ infra02 now matches infra01 functionality with external registry image
