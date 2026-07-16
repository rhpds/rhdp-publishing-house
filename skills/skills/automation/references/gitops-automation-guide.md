# GitOps Automation Guide

How to create GitOps automation for RHDP lab/demo environments using Helm + ArgoCD.
Follows the patterns in `https://github.com/rhpds/ci-template-gitops`.

## When to Use GitOps vs Ansible

| Use GitOps When | Use Ansible When |
|----------------|------------------|
| Environment is fully declarative (K8s manifests) | Tasks require imperative logic |
| Lab teaches GitOps concepts (ArgoCD is the point) | Lab doesn't involve GitOps |
| `self_published` deployment mode | `rhdp_published` with complex ordering needs |

## Architecture: Two Main Layers

```
cluster/infra/   → Operators and cluster infrastructure (deployed once per cluster)
tenant/          → Per-user lab workloads (deployed per user)
```

## Repo Structure

```
automation/
├── cluster/
│   └── infra/
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
│           └── application-<operator>.yaml
├── tenant/
│   ├── bootstrap/
│   │   ├── Chart.yaml
│   │   ├── values.yaml
│   │   └── templates/
│   │       └── application-<lab>.yaml
│   └── labs/
│       └── <project-id>/
│           ├── Chart.yaml
│           ├── values.yaml
│           └── templates/
│               ├── namespace.yaml
│               ├── rbac.yaml
│               ├── deployment.yaml
│               └── configmap-provisiondata.yaml
```

## Provision Data

Surface per-user connection info via labeled ConfigMaps:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: provisiondata-{{ .Values.deployer.guid }}
  namespace: {{ .Values.namespace }}
  labels:
    demo.redhat.com/tenant-{{ .Values.deployer.guid }}: "true"
data:
  showroom_url: "https://showroom-{{ .Values.namespace }}.{{ .Values.deployer.domain }}"
  app_url: "https://my-app-{{ .Values.namespace }}.{{ .Values.deployer.domain }}"
```

Always include `showroom_url` — it's the default delivery vehicle for lab guides.

## Field Source CI Integration (`self_published`)

```yaml
# common.yaml
workloads:
  - agnosticd.core_workloads.ocp4_workload_field_content_cluster
  - agnosticd.core_workloads.ocp4_workload_field_content_tenant

ocp4_workload_field_content_cluster_repo_url: https://github.com/<org>/<repo>.git
ocp4_workload_field_content_cluster_repo_path: cluster/infra

ocp4_workload_field_content_tenant_repo_url: https://github.com/<org>/<repo>.git
ocp4_workload_field_content_tenant_repo_path: tenant/bootstrap
```

## What to Automate vs What the Learner Does

If the lab says "open the application at..." → pre-deploy it.
If the lab says "run oc apply -f..." → the learner does it.
