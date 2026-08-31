# Central API Deployment - infra01 to infra02 Alignment

**Analysis Date**: 2026-08-31

---

## Summary

For central-api deployment, **only 2 resources need updating**:

1. ✅ **Image version**: `1.21.17` → `1.21.19`
2. ⚠️  **ph-validation-policy ConfigMap**: infra02 is MORE up-to-date than infra01

---

## Resource Comparison

### 1. Deployment Image

| Cluster | Current Version | Target |
|---------|----------------|--------|
| **infra01** | `quay.io/rhpds/central-api:1.21.18` | Reference |
| **infra02** | `quay.io/rhpds/central-api:1.21.17` | → 1.21.19 (latest) |

**Latest in Quay.io**: `1.21.19`

**Action**: Update infra02 to 1.21.19 ✅

---

### 2. ConfigMap: central-api-config

| Key | infra01 Value | infra02 Value | Match |
|-----|---------------|---------------|-------|
| All 15 keys | ✅ Present | ✅ Present | Structure ✅ |
| **CORS_ORIGINS** | `apps.ocpv-infra01.dal12` | `apps.ocpv-infra02.wdc07` | Expected ✓ |
| **OIDC_ISSUER_URL** | `infra01.dal12` | `infra02.wdc07` | Expected ✓ |
| Other 13 keys | Identical | Identical | ✅ |

**Status**: ✅ **No action needed** - Cluster-specific URLs are correct

---

### 3. ConfigMap: ph-validation-policy

**⚠️  IMPORTANT**: infra02 has NEWER content than infra01!

#### What infra02 HAS that infra01 LACKS:

**In `valid_cloud_providers`:**
```yaml
- gcp
- google
```

**In `products`:**
```yaml
- name: Red Hat Advanced Cluster Management
  aliases:
    - RHACM
    - ACM

- name: Red Hat Hardened Images
  aliases:
    - RHHI

- name: Red Hat OpenShift Lightspeed
  aliases:
    - OpenShift Lightspeed
```

**Decision Required**:
- **Option A**: Keep infra02 as-is (more complete) ← Recommended
- **Option B**: Replace with infra01 version (lose GCP, RHACM, RHHI, OLS)

---

### 4. PVC: central-api-data

| Cluster | Status | Size |
|---------|--------|------|
| **infra01** | ✅ Bound | 1Gi |
| **infra02** | ✅ Bound | 1Gi |

**Status**: ✅ **No action needed**

---

## Deployment Plan

### Recommended Actions:

```bash
# 1. Update central-api image only
oc config use-context publishing-house/api-ocpv-infra02-wdc07-infra-demo-redhat-com:6443/treddy@redhat.com

oc set image deployment/central-api \
  central-api=quay.io/rhpds/central-api:1.21.19 \
  -n publishing-house

# 2. Wait for rollout
oc rollout status deployment/central-api -n publishing-house --timeout=5m

# 3. Verify
oc get deployment central-api -n publishing-house \
  -o jsonpath='{.spec.template.spec.containers[0].image}'
```

**DO NOT** update ph-validation-policy (infra02 is already ahead).

---

## What's Already Aligned

✅ **central-api-config** - All keys present, cluster-specific URLs correct  
✅ **central-api-spec** - Exists in both  
✅ **central-api-data PVC** - Exists in both  
✅ **Deployment configuration** - Same envFrom, volumes, etc.  

---

## Summary Table

| Resource | infra01 | infra02 | Action |
|----------|---------|---------|--------|
| **Image** | 1.21.18 | 1.21.17 | → Update to 1.21.19 |
| **central-api-config** | ✅ Exists | ✅ Exists | No change (cluster-specific) |
| **ph-validation-policy** | Older | Newer | No change (keep infra02) |
| **central-api-spec** | ✅ Exists | ✅ Exists | Verify identical |
| **central-api-data PVC** | ✅ Bound | ✅ Bound | No change |

---

## Verification Commands

```bash
# Check image version
oc get deployment central-api -n publishing-house \
  -o jsonpath='{.spec.template.spec.containers[0].image}'

# Check ConfigMaps exist
oc get configmap central-api-config ph-validation-policy -n publishing-house

# Check PVC
oc get pvc central-api-data -n publishing-house

# Test API health
ROUTE=$(oc get route central-api -n publishing-house -o jsonpath='{.spec.host}')
curl https://$ROUTE/api/v1/health

# Check logs
oc logs deployment/central-api -n publishing-house --tail=50
```

---

## Conclusion

**For central-api alignment: Only update the image version.**

ConfigMaps already exist and are appropriate for each cluster. infra02's validation policy is actually more complete than infra01's.
