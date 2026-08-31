# Central API Alignment - Complete

**Date**: 2026-08-31  
**Completed**: Both clusters aligned

---

## Changes Applied

### 1. ✅ infra02: Updated central-api image

```bash
Before: quay.io/rhpds/central-api:1.21.17
After:  quay.io/rhpds/central-api:1.21.18
```

**Status**: Deployment rolled out successfully  
**Pod**: central-api-7d9b86ff5b-hwq4h (Running)

---

### 2. ✅ infra01: Updated ph-validation-policy ConfigMap

Synced from infra02 (which had newer content).

**Added to infra01**:
- `valid_cloud_providers`: Added `gcp`, `google`
- `products`: Added:
  - Red Hat Advanced Cluster Management (RHACM, ACM)
  - Red Hat Hardened Images (RHHI)
  - Red Hat OpenShift Lightspeed

**Verification**:
```
infra01 hash: 7af2a4a087103ae0...
infra02 hash: 7af2a4a087103ae0...
Status: ✅ IDENTICAL
```

---

## Verification Results

### Central API Images
```
infra01: quay.io/rhpds/central-api:1.21.18 ✅
infra02: quay.io/rhpds/central-api:1.21.18 ✅
```

### Validation Policy ConfigMap
```
infra01: 7af2a4a087103ae0... ✅
infra02: 7af2a4a087103ae0... ✅
Status: IDENTICAL
```

---

## What Was NOT Changed

✅ **central-api-config** - Cluster-specific URLs (correct as-is)  
✅ **central-api-spec** - Already identical  
✅ **central-api-data PVC** - Already exists in both  

---

## Current State

Both clusters now have:
- ✅ Same central-api image version (1.21.18)
- ✅ Same validation policy (including GCP, RHACM, RHHI, OLS support)
- ✅ Cluster-specific configs (CORS, OIDC URLs) appropriate for each cluster

---

## Files Generated

```
/tmp/ph-validation-policy-clean.yaml - Synced policy from infra02
```

---

**Status**: ✅ Complete - Central API fully aligned across both clusters
