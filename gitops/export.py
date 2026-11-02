#!/usr/bin/env python3
"""Export live cluster resources into clean GitOps manifests.

Faithfully captures the running state (no config changes), strips runtime-only
fields, adds an ArgoCD sync-wave annotation, and redacts Secret data values.
"""
import json
import os
import subprocess
import sys

BASE = os.path.join(os.path.dirname(__file__), "base")

# Annotations that are runtime/operator noise and should be dropped.
DROP_ANNOS = {
    "kubectl.kubernetes.io/last-applied-configuration",
    "kapp.k14s.io/original",
    "deployment.kubernetes.io/revision",
    "pv.kubernetes.io/bind-completed",
    "pv.kubernetes.io/bound-by-controller",
    "volume.beta.kubernetes.io/storage-provisioner",
    "volume.kubernetes.io/storage-provisioner",
    "volume.kubernetes.io/selected-node",
    "kubernetes.io/service-account.uid",
}
DROP_LABELS = {
    "kubectl.kubernetes.io/last-applied-configuration",
}


def oc_get(kind, name, namespace=None):
    cmd = ["oc", "get", kind, name, "-o", "json"]
    if namespace:
        cmd += ["-n", namespace]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        sys.stderr.write(f"SKIP {kind}/{name} ({namespace}): {out.stderr.strip()}\n")
        return None
    return json.loads(out.stdout)


def clean(obj, redact_secret=False):
    obj.pop("status", None)
    md = obj.get("metadata", {})
    for k in ("resourceVersion", "uid", "generation", "creationTimestamp",
              "selfLink", "managedFields", "ownerReferences"):
        md.pop(k, None)
    annos = md.get("annotations", {})
    for a in list(annos):
        if a in DROP_ANNOS or a.startswith("kapp."):
            annos.pop(a)
    if not annos:
        md.pop("annotations", None)
    labels = md.get("labels", {})
    for l in list(labels):
        if l in DROP_LABELS:
            labels.pop(l)

    kind = obj.get("kind")
    spec = obj.get("spec", {})
    if kind == "Service":
        for f in ("clusterIP", "clusterIPs", "ipFamilies", "ipFamilyPolicy",
                  "internalTrafficPolicy", "sessionAffinity"):
            spec.pop(f, None)
    if kind == "PersistentVolumeClaim":
        for f in ("volumeName", "volumeMode", "storageClassName"):
            spec.pop(f, None)
        obj["metadata"].get("annotations", {})  # already cleaned
    if kind == "Secret" and redact_secret:
        if "data" in obj:
            obj["data"] = {k: "" for k in obj["data"]}
        obj.setdefault("metadata", {}).setdefault("annotations", {})[
            "gitops.rhdp/REDACTED"] = "populate real values (or move to ExternalSecret)"
    # Service-account-token secrets: let k8s repopulate
    if kind == "Secret" and obj.get("type") == "kubernetes.io/service-account-token":
        obj.pop("data", None)
    return obj


def write(obj, wave, subdir, fname):
    import yaml
    md = obj.setdefault("metadata", {})
    annos = md.setdefault("annotations", {})
    annos["argocd.argoproj.io/sync-wave"] = str(wave)
    d = os.path.join(BASE, subdir)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, fname)
    with open(path, "w") as f:
        yaml.safe_dump(obj, f, default_flow_style=False, sort_keys=False)
    print(f"  wrote {subdir}/{fname} (wave {wave})")


# (kind, name, namespace, wave, subdir, filename, redact_secret)
RESOURCES = [
    # ---- wave 0: operators ----
    ("subscriptions.operators.coreos.com", "rhbk-operator", "keycloak", 0, "00-operators", "sub-rhbk.yaml", False),
    ("operatorgroup", "keycloak-operators", "keycloak", 0, "00-operators", "og-keycloak.yaml", False),
    ("subscriptions.operators.coreos.com", "rhdh-operator", "openshift-operators", 0, "00-operators", "sub-rhdh.yaml", False),
    ("subscriptions.operators.coreos.com", "devspaces", "openshift-operators", 0, "00-operators", "sub-devspaces.yaml", False),

    # ---- wave 1: secret sync + static secrets ----
    ("clustersecretstore", "vault-secret-store", None, 1, "10-secrets", "clustersecretstore.yaml", False),
    ("externalsecret", "publishing-house-credentials", "publishing-house", 1, "10-secrets", "es-publishing-house-credentials.yaml", False),
    ("externalsecret", "github-oauth-config", "openshift-devspaces", 1, "10-secrets", "es-github-oauth.yaml", False),
    ("secret", "keycloak-db-secret", "keycloak", 1, "10-secrets", "secret-keycloak-db.yaml", True),
    ("secret", "sonataflow-postgresql-svcbind", "publishing-house", 1, "10-secrets", "secret-sonataflow-svcbind.yaml", True),
    ("secret", "ph-developer-hub-env", "publishing-house", 1, "10-secrets", "secret-ph-developer-hub-env.yaml", True),
    ("secret", "sonataflow-console-oauth-proxy", "publishing-house", 1, "10-secrets", "secret-console-oauth.yaml", True),

    # ---- wave 2: data stores ----
    ("statefulset", "keycloak-db", "keycloak", 2, "20-data", "sts-keycloak-db.yaml", False),
    ("service", "keycloak-db", "keycloak", 2, "20-data", "svc-keycloak-db.yaml", False),
    ("statefulset", "sonataflow-postgresql", "publishing-house", 2, "20-data", "sts-sonataflow-postgresql.yaml", False),
    ("service", "sonataflow-postgresql", "publishing-house", 2, "20-data", "svc-sonataflow-postgresql.yaml", False),

    # ---- wave 3: keycloak identity ----
    ("keycloaks.k8s.keycloak.org", "keycloak", "keycloak", 3, "30-keycloak", "keycloak.yaml", False),
    ("keycloakrealmimport", "publishing-house", "keycloak", 3, "30-keycloak", "realmimport.yaml", False),

    # ---- wave 4: sonataflow platform ----
    ("sonataflowplatform", "sonataflow-platform", "publishing-house", 4, "40-sonataflow-platform", "sonataflowplatform.yaml", False),

    # ---- wave 5: central-api ----
    ("serviceaccount", "central-api", "publishing-house", 5, "50-central-api", "sa.yaml", False),
    ("clusterrolebinding", "central-api-tokenreview", None, 5, "50-central-api", "crb-tokenreview.yaml", False),
    ("configmap", "central-api-config", "publishing-house", 5, "50-central-api", "cm-config.yaml", False),
    ("configmap", "ph-validation-policy", "publishing-house", 5, "50-central-api", "cm-validation-policy.yaml", False),
    ("configmap", "central-api-spec", "publishing-house", 5, "50-central-api", "cm-central-api-spec.yaml", False),
    ("persistentvolumeclaim", "central-api-data", "publishing-house", 5, "50-central-api", "pvc-data.yaml", False),
    ("deployment", "central-api", "publishing-house", 5, "50-central-api", "deployment.yaml", False),
    ("service", "central-api", "publishing-house", 5, "50-central-api", "svc.yaml", False),
    ("route", "central-api", "publishing-house", 5, "50-central-api", "route.yaml", False),

    # ---- wave 5: sonataflow workflow (CR + inputs + preview workaround deploy/svc) ----
    ("configmap", "workflow-input-schema", "publishing-house", 5, "55-sonataflow-workflow", "cm-workflow-input-schema.yaml", False),
    ("configmap", "rhdp-published-input-schema", "publishing-house", 5, "55-sonataflow-workflow", "cm-rhdp-published-input-schema.yaml", False),
    ("sonataflow", "rhdp-published", "publishing-house", 5, "55-sonataflow-workflow", "sonataflow.yaml", False),
    ("deployment", "rhdp-published", "publishing-house", 6, "55-sonataflow-workflow", "deployment.yaml", False),
    ("service", "rhdp-published", "publishing-house", 6, "55-sonataflow-workflow", "svc.yaml", False),

    # ---- wave 6: RHDH inputs + CR ----
    ("serviceaccount", "rhdh-kubernetes-plugin", "publishing-house", 6, "60-rhdh", "sa-k8s-plugin.yaml", False),
    ("clusterrolebinding", "rhdh-kubernetes-plugin", None, 6, "60-rhdh", "crb-k8s-plugin.yaml", False),
    ("secret", "rhdh-k8s-integration", "publishing-house", 6, "60-rhdh", "secret-k8s-integration.yaml", False),
    ("configmap", "ph-developer-hub-app-config", "publishing-house", 6, "60-rhdh", "cm-app-config.yaml", False),
    ("configmap", "ph-developer-hub-dynamic-plugins", "publishing-house", 6, "60-rhdh", "cm-dynamic-plugins.yaml", False),
    ("configmap", "ph-rbac-policy", "publishing-house", 6, "60-rhdh", "cm-rbac-policy.yaml", False),
    ("configmap", "dynamic-plugins", "publishing-house", 6, "60-rhdh", "cm-dynamic-plugins-extra.yaml", False),
    ("persistentvolumeclaim", "developer-hub-dynamic-plugins-root", "publishing-house", 6, "60-rhdh", "pvc-dynamic-plugins.yaml", False),
    ("backstage", "developer-hub", "publishing-house", 6, "60-rhdh", "backstage.yaml", False),
    ("route", "central-publishing-house", "publishing-house", 6, "60-rhdh", "route.yaml", False),

    # ---- wave 6: devspaces ----
    ("checluster", "devspaces", "openshift-devspaces", 6, "60-devspaces", "checluster.yaml", False),

    # ---- wave 6: sonataflow management console ----
    ("deployment", "sonataflow-management-console", "publishing-house", 6, "65-mgmt-console", "deployment.yaml", False),
    ("service", "sonataflow-management-console", "publishing-house", 6, "65-mgmt-console", "svc.yaml", False),
    ("route", "sonataflow-management-console", "publishing-house", 6, "65-mgmt-console", "route.yaml", False),

    # ---- wave 7: jobs ----
    ("configmap", "drift-checker-script", "publishing-house", 7, "70-jobs", "cm-drift-checker.yaml", False),
    ("configmap", "inactivity-checker-script", "publishing-house", 7, "70-jobs", "cm-inactivity-checker.yaml", False),
    ("configmap", "workflow-cleanup-script", "publishing-house", 7, "70-jobs", "cm-workflow-cleanup.yaml", False),
    ("cronjob", "drift-checker", "publishing-house", 7, "70-jobs", "cronjob-drift-checker.yaml", False),
    ("cronjob", "inactivity-checker", "publishing-house", 7, "70-jobs", "cronjob-inactivity-checker.yaml", False),
    ("cronjob", "workflow-cleanup", "publishing-house", 7, "70-jobs", "cronjob-workflow-cleanup.yaml", False),
]


def main():
    for kind, name, ns, wave, subdir, fname, redact in RESOURCES:
        obj = oc_get(kind, name, ns)
        if obj is None:
            continue
        obj = clean(obj, redact_secret=redact)
        write(obj, wave, subdir, fname)


if __name__ == "__main__":
    main()
