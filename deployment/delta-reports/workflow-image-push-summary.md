# SonataFlow Workflow Image Push - Summary

**Date**: 2026-08-31  
**Source**: infra01 (OpenShift internal registry)  
**Destination**: Quay.io

---

## Image Details

### Source (infra01)
```
Registry: image-registry.openshift-image-registry.svc:5000
Repository: publishing-house/publishinghouseworkflow
Tag: latest
SHA: sha256:ce117d19221c82ffa92f27535c4b9f46bd48a66117778bac37c1c54eb44c6a1f
Build: #2943 (BuildConfig)
```

### Destination (Quay.io)
```
Repository: quay.io/rhpds/publishing-house-workflow
Tags: 1.6, latest
Manifest: sha256:ce4056157d228...
Architecture: linux/amd64
Size: 503 MB
Pushed: Aug 30, 2026 22:28 UTC
```

---

## Version History

| Version | Date | Size | Notes |
|---------|------|------|-------|
| **1.6** | Aug 30, 2026 | 503 MB | ✅ Latest (from infra01 build #2943) |
| 1.5 | Aug 14, 2026 | 501 MB | Previous version |
| 1.4 | Aug 13, 2026 | 505 MB | |
| 1.3 | Aug 12, 2026 | 505 MB | |

---

## Deployment Updates

### Update infra02 to 1.6

```bash
oc config use-context publishing-house/api-ocpv-infra02-wdc07-infra-demo-redhat-com:6443/treddy@redhat.com

# Update SonataFlow CR
oc patch sonataflow publishinghouseworkflow -n publishing-house \
  --type=merge \
  -p '{"spec":{"podTemplate":{"container":{"image":"quay.io/rhpds/publishing-house-workflow:1.6"}}}}'

# Verify rollout
oc rollout status deployment/publishinghouseworkflow -n publishing-house
```

### Update infra01 to use Quay.io (optional)

Currently infra01 builds from source. To align with infra02:

```bash
oc config use-context publishing-house/api-ocpv-infra01-dal12-infra-demo-redhat-com:6443/treddy@redhat.com

# Update SonataFlow CR to use external registry
oc patch sonataflow publishinghouseworkflow -n publishing-house \
  --type=merge \
  -p '{"spec":{"podTemplate":{"container":{"image":"quay.io/rhpds/publishing-house-workflow:1.6"}}}}'
```

---

## Verification

```bash
# Check Quay.io API
curl -s https://quay.io/api/v1/repository/rhpds/publishing-house-workflow/tag/1.6 | jq .

# Pull and inspect
podman pull quay.io/rhpds/publishing-house-workflow:1.6
podman inspect quay.io/rhpds/publishing-house-workflow:1.6 | jq '.[0] | {Architecture, Os, Size}'
```

---

## What Changed in 1.6

This version contains the latest workflow logic from infra01's preview-mode BuildConfig:
- 4-stage lifecycle: Intake → Content Review → Infra Review → Env Setup → Development → Testing → Published
- Jira integration with epic/task sync
- Drift detection and baseline SHA tracking
- Rejection workflow with fix-and-resubmit
- Zero-touch showroom support

Built from: `publishinghouseworkflow` BuildConfig build #2943

---

## Next Steps

1. ✅ Image pushed to Quay.io as 1.6 and latest
2. ⏭️ Update infra02 to use 1.6
3. ⏭️ Deploy dynamic-plugins ConfigMap to infra02
4. ⏭️ Update central-api to 1.21.18/1.21.19 in infra02
