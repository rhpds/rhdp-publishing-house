# GitOps Automation

Publishing House provides a `gitops-helper` skill that generates Helm charts and ArgoCD manifests for your lab environment.

!!! info "This helper is optional"
    You can build GitOps automation manually or with any tool you prefer. If you do use the helper,
    its output is a starting point — read through everything it produces and verify it yourself
    before marking a workstream complete.

See [Development](development.md) for how GitOps Automation fits into the overall development workflow.

---

## Overview

GitOps automation in RHDP uses a **Helm + ArgoCD** model. An external deployer creates ArgoCD `Application` resources that point to Helm charts in your repo. The charts contain all the Kubernetes manifests needed to provision your lab environment.

Every lab has at least one chart, optionally two:

| Chart | Purpose | When to use |
|---|---|---|
| `bootstrap-infra` | Cluster-scoped shared resources — operators, shared services, shared namespaces | Always |
| `bootstrap-tenant` | Per-user tenant environment — user namespaces, user apps, RBAC, seed data | Multi-user labs only |

Tenant always comes with infra — never standalone.

---

## Directory structure

The automation scaffolding (created by the development skill's config-helper) produces this layout:

```
automation/gitops/
├── bootstrap-infra/
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
│       └── ...
└── bootstrap-tenant/        # optional, multi-user only
    ├── Chart.yaml
    ├── values.yaml
    └── templates/
        └── ...
```

The `gitops-helper` skill populates the `templates/` directories. It does not create the chart scaffold — that's handled by the development skill when you select GitOps Automation from the dashboard.

---

## Using the GitOps helper skill

### From the development dashboard

Select **GitOps Automation** from the development dashboard, then choose **Use GitOps helper**. Claude dispatches to the `gitops-helper` skill, which:

1. **Clones the reference repo** — pulls `rhdp-gitops-patterns` for example templates
2. **Asks about additional references** — you can provide extra Git repos with examples to draw from
3. **Gathers inputs** — reads your `spec.yaml`, design doc, and module outlines to understand what needs provisioning, then asks clarifying questions for anything unclear (namespaces, operators, services, VMs)
4. **Classifies resources** — decides what goes in infra vs tenant
5. **Generates templates** — creates Helm templates from reference patterns, applying sync-wave annotations and ArgoCD conventions
6. **Presents for review** — shows a summary of generated files, infra vs tenant breakdown, and any assumptions made
7. **Prints AgnosticV config** — generates a suggested `common.yml` snippet for wiring the chart into the RHDP deployer

### Standalone mode

The skill also works outside of Publishing House projects. Run it directly:

```
/rhdp-publishing-house:gitops-helper
```

In standalone mode, the pre-flight and workflow checks are skipped — the skill goes straight to verifying the automation directories and generating templates.

---

## Infra vs tenant

Deciding where a resource belongs:

| Infra (cluster-scoped, deployed once) | Tenant (per-user, deployed N times) |
|---|---|
| Operator Subscriptions and OperatorGroups | User namespaces |
| Shared services (GitLab, Gitea, DevHub) | User RBAC (RoleBindings) |
| Shared namespaces | User applications and deployments |
| Cluster RBAC (ClusterRoleBindings) | KubeVirt VMs |
| CatalogSources | Seed data (ConfigMaps, Secrets) |

If a resource looks tenant-scoped but no tenant chart exists, the skill asks whether to create one or place it in infra.

---

## Sync-wave ordering

ArgoCD sync-wave annotations control deployment order:

| Wave | Resources |
|------|-----------|
| -2 | Namespaces, OperatorGroups, Subscriptions |
| -1 | RBAC (RoleBindings, ClusterRoleBindings), ServiceAccounts |
| 0 | ConfigMaps, Secrets, Deployments, Services, standard workloads |
| 1+ | CRs that depend on operator-installed CRDs, Routes |

In the tenant chart, namespace creation (wave -2) must precede everything else.

---

## Tenant namespace isolation

Everything in `bootstrap-tenant` must target one of the tenant's own namespaces. Never deploy tenant resources into a shared or common namespace — if you do, each tenant deployment overwrites the previous one.

Tenant namespaces are derived from a list in `values.yaml`:

```yaml
username: user1
namespaces:
  - app
  - db
```

This produces `user1-app` and `user1-db`. All tenant resources must target one of these.

Every tenant namespace automatically gets an `edit` RoleBinding for the tenant user.

---

## Operator CRDs

Custom Resources that depend on CRDs installed by an operator Subscription need this annotation:

```yaml
argocd.argoproj.io/sync-options: SkipDryRunOnMissingResource=true
```

This prevents ArgoCD from failing the dry-run when the CRD doesn't exist yet (the operator hasn't installed it).

---

## Key conventions

- **No hardcoded domains** — construct URLs from `deployer.domain` (auto-injected by the deployer along with `deployer.apiUrl` and `deployer.guid`)
- **No ArgoCD Applications pointing back to subdirectories** — expand all manifests directly into the chart templates
- **No ApplicationSet in bootstrap-infra** — the ApplicationSet is for manual use only; do not enable it or add a `tenant:` key to infra's `values.yaml`
- **PVCs at the same sync-wave as their workload** — not with namespaces at wave -2 (WaitForFirstConsumer StorageClasses won't bind until a pod claims them)
- **Check reference patterns before generating from scratch** — the skill searches `rhdp-gitops-patterns/examples/` first

---

## Manual setup

If you prefer to build GitOps automation without the skill:

1. Select **GitOps Automation** from the development dashboard, choose **Do it myself**
2. Work in `automation/gitops/bootstrap-infra/templates/` (and `bootstrap-tenant/templates/` if applicable)
3. Follow the sync-wave ordering and namespace isolation conventions above
4. Use the [rhdp-gitops-patterns](https://github.com/rhpds/rhdp-gitops-patterns) repo as a reference for examples
5. Come back to the dashboard and mark GitOps automation complete when done

---

## Tips

- **Start with infra, then add tenant.** Get operators and shared services deploying first, then layer on per-user resources.
- **Use `helm template` to validate locally.** The gitops-helper runs this automatically, but you can do it manually: `helm template test automation/gitops/bootstrap-infra/`
- **Reference the patterns repo.** The `rhdp-gitops-patterns/examples/` directory has working examples for common components (GitLab, Gitea, DevHub, KubeVirt VMs, per-user ArgoCD, Istio Gateway).
- **Watch for operator quirks.** Some operators (e.g., Gitea) aren't in standard OLM catalogs and require a custom CatalogSource. The patterns repo documents these.

---

## AgnosticV integration

To deploy your GitOps automation, include the `ocp4_workload_gitops_bootstrap` workload in your AgnosticV catalog item's `common.yml` and configure it to point at your chart:

```yaml
workloads:
  - agnosticd.core_workloads.ocp4_workload_openshift_gitops
  - agnosticd.core_workloads.ocp4_workload_gitops_bootstrap

ocp4_workload_gitops_bootstrap_repo_url: https://github.com/rhpds/<your-repo>
ocp4_workload_gitops_bootstrap_repo_revision: "{{ gitops_repo_revision }}"
ocp4_workload_gitops_bootstrap_repo_path: automation/gitops/bootstrap-infra
ocp4_workload_gitops_bootstrap_application_name: bootstrap-infra
ocp4_workload_gitops_bootstrap_helm_values:
  # Only include values prone to external changes.
  # deployer.domain, deployer.apiUrl, and deployer.guid are auto-injected.
```

The `ocp4_workload_openshift_gitops` workload installs the OpenShift GitOps operator (ArgoCD). The `ocp4_workload_gitops_bootstrap` workload creates an ArgoCD `Application` that points to your Helm chart and syncs it.

Only include values that should be deployer-managed (operator channels, git revisions, image tags, secrets, user count). Leave everything else to the chart's `values.yaml` defaults.
