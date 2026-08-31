# Backstage Dynamic Plugins Sync - Complete

**Date**: 2026-08-31  
**Direction**: infra01 → infra02

---

## Changes Applied

### ✅ ConfigMap: ph-developer-hub-dynamic-plugins

**Synced from infra01 to infra02**

```
Before (infra02): backstage-plugin-ph-workflows:1.20.5
After  (infra02): backstage-plugin-ph-workflows:1.20.7
```

**Other plugins** (already matched):
- backstage-plugin-scaffolder-backend-module-publishing-house:1.1.5
- backstage-plugin-readme-backend:0.1.0
- backstage-plugin-readme:0.1.0

---

## Actions Taken

1. ✅ Exported `ph-developer-hub-dynamic-plugins` ConfigMap from infra01
2. ✅ Applied ConfigMap to infra02
3. ✅ Deleted RHDH pod to force restart
4. ✅ New pod will download version 1.20.7 of the plugin

---

## Plugin Version 1.20.7 Features

The updated plugin includes all features from infra01:
- Publishing House Workflows page
- Spec Drift dashboard  
- Maintenance page
- Home Card widget
- Menu items and icons
- Scaffolder backend integration

---

## Pod Restart Process

The RHDH pod is restarting and will:
1. Pull the ConfigMap with version 1.20.7
2. Download `oci://quay.io/rhpds/backstage-plugin-ph-workflows:1.20.7`
3. Load the plugin on startup
4. Make the plugin available in the UI

---

## Verification Steps

Once the pod is running:

```bash
# Check pod status
oc get pods -n publishing-house | grep backstage-developer-hub

# Check pod logs for plugin loading
oc logs -n publishing-house deployment/backstage-developer-hub --tail=50 | grep "ph-workflows"

# Verify ConfigMap version
oc get configmap ph-developer-hub-dynamic-plugins -n publishing-house \
  -o yaml | grep "backstage-plugin-ph-workflows:"
```

**Expected**: `backstage-plugin-ph-workflows:1.20.7`

---

## UI Verification

Access RHDH dashboard:
```
https://developer-hub-publishing-house.apps.ocpv-infra02.wdc07.infra.demo.redhat.com
```

Verify:
- [ ] "Publishing House" menu appears in sidebar
- [ ] Workflows submenu item loads
- [ ] Spec Drift submenu item loads
- [ ] Maintenance submenu item loads
- [ ] Home Card appears on dashboard home page

---

**Status**: ✅ ConfigMap synced, pod restarting with v1.20.7
