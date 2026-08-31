# SonataFlow CR Update - infra02

**Date**: 2026-08-31  
**Cluster**: infra02 (wdc07)  
**Namespace**: publishing-house

---

## Changes Applied

### 1. Workflow Definition Update
**Added `notes: []` field in Setup state**

Previously missing in infra02, this field was added to match infra01's workflow definition.

**Location**: `spec.flow.states[1]` (Setup state)  
**Field**: `stateDataFilter.output`  
**Change**: Added `notes: [],` to the initialization object

This field is used to track workflow notes and comments throughout the lifecycle.

### 2. Container Image Update
**Updated to version 1.6**

```yaml
Before: quay.io/rhpds/publishing-house-workflow:1.5
After:  quay.io/rhpds/publishing-house-workflow:1.6
```

Version 1.6 contains the latest workflow logic from infra01 BuildConfig #2943.

---

## Verification

```bash
✅ Image verified:
   oc get sonataflow publishinghouseworkflow -n publishing-house \
     -o jsonpath='{.spec.podTemplate.container.image}'
   
   Result: quay.io/rhpds/publishing-house-workflow:1.6

✅ Notes field verified:
   oc get sonataflow publishinghouseworkflow -n publishing-house \
     -o yaml | grep -A 30 "name: Setup" | grep "notes:"
   
   Result: notes: [],

✅ Pod status:
   NAME                                       READY   STATUS    RESTARTS   AGE
   publishinghouseworkflow-66c569dbd7-vtpds   1/1     Running   0          3m
```

---

## GitOps Considerations

Since infra02 runs in GitOps mode, this manual update should be:

1. **Documented** in the source repository
2. **Synchronized** with the GitOps manifests
3. **Monitored** for drift detection

### Recommended Actions

Update the GitOps source manifest to include:
- The `notes: []` field in the Setup state
- Image reference: `quay.io/rhpds/publishing-house-workflow:1.6`

---

## What Changed in Workflow 1.6

From infra01 BuildConfig #2943:

- 4-stage lifecycle orchestration
- Jira epic/task sync improvements
- Drift detection with baseline SHA tracking
- Rejection workflow with fix-and-resubmit
- Zero-touch showroom support
- **Added notes field for lifecycle annotations**

---

## Files Generated

- `/tmp/sonataflow-infra02-update.yaml` - Applied CR manifest
- `/tmp/infra01-sonataflow.yaml` - Source CR from infra01  
- `/tmp/infra02-sonataflow.yaml` - Original CR from infra02

---

## Next Steps

- [ ] Update GitOps repository with these changes
- [ ] Monitor workflow pod logs for any errors
- [ ] Test workflow creation via RHDH template
- [ ] Verify notes field is populated in new workflow instances

---

**Status**: ✅ Successfully applied to infra02
**Pod Status**: Running
**Applied**: 2026-08-31 08:35 UTC
