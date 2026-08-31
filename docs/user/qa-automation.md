# QA Automation

Every project scaffolds a `qa-automation/` directory with two stub playbooks: `e2e.yml` and `healthcheck.yml`. Both start as `TODO` placeholders — you replace them as part of building automation.

## healthcheck.yml

Checks that the services **your workshop/demo provisions** are up after provisioning finishes.

**In scope** — anything your automation deploys on top of the base infrastructure:

- Custom workloads deployed via Ansible roles/collections
- ArgoCD Applications (sync + health status)
- Services/processes started on a VM (systemd units, containers, listening ports)
- Any app endpoint your automation stands up

**Out of scope** — the base infrastructure itself. That's already verified by whoever provisions it (AgnosticD / demo team infra), before your automation ever runs:

- OpenShift cluster health (API server, console, node status)
- VM boot, OS, network reachability

| Your demo uses... | Health-check | Don't health-check |
|---|---|---|
| OCP cluster + custom workloads (Ansible/GitOps) | Workload pods Running, app endpoints respond, ArgoCD Application sync/health | Cluster API server, console, node health |
| A VM + services you start on it | Your services (systemd units, containers, app ports) | The VM itself (boot, OS, network) |

**Requirements:**

- Completes in under 60 seconds
- Exit `0` = healthy, non-zero = unhealthy
- Non-destructive and idempotent — safe to run against a live environment, safe to re-run

## e2e.yml

Walks through the learner's steps from the module content and confirms the workshop/demo can be completed start to finish, unattended. Script the learner's documented steps directly — CLI/API calls that mirror what they'd do manually.

**Requirements:**

- Fails on the first broken step, with a message identifying which module/step failed
- Runs unattended, start to finish, no manual intervention

## Running as OpenShift cluster admin

By default, `healthcheck.yml`/`e2e.yml` run with the Showroom pod's own in-cluster identity, which is `edit`-scoped to its own namespace. If your checks need to look outside that namespace — cluster-scoped resources, other namespaces, ArgoCD `Application` status in `openshift-gitops` — enable the runtime-automation cluster-admin identity instead.

See [rhpds/ph-openshift-monorepo-example](https://github.com/rhpds/ph-openshift-monorepo-example) for a full working example: [`qa-automation/healthcheck.yml`](https://github.com/rhpds/ph-openshift-monorepo-example/blob/main/qa-automation/healthcheck.yml) and [`qa-automation/e2e.yml`](https://github.com/rhpds/ph-openshift-monorepo-example/blob/main/qa-automation/e2e.yml) both use this identity to check ArgoCD Application sync/health and namespaces outside their own.

**Enable the QA automation endpoints** — devs must set this in the AgnosticV catalog item's `common.yml` for `/stream/qa/healthcheck` and `/stream/qa/e2e` to exist at all:

```yaml
ocp4_workload_showroom_runtime_automation_enable: true
```

**Enable cluster-admin permissions** — this authenticates both the `kubernetes.core.k8s*` Ansible modules and `oc` via shell inside the playbooks:

```yaml
ocp4_workload_showroom_runtime_automation_cluster_admin: true
ocp4_workload_showroom_openshift_api_url: "{{ openshift_api_url }}"
ocp4_workload_showroom_openshift_api_token: "{{ openshift_cluster_admin_token }}"
```

This populates a `runtime-automation-kubeconfig` Secret that the playbook reads into a `k8s_kubeconfig` variable. Wire it into `module_defaults` for `kubernetes.core.k8s*`/`helm` tasks, and into the `KUBECONFIG`/`K8S_AUTH_KUBECONFIG` environment variables for `oc` and any nested `ansible-playbook` calls — see the example playbooks above for the exact pattern.

## Running against a deployed Showroom

Once the environment is provisioned, copy the Showroom URL from the order. Hosts, GUIDs, and clusters vary — the paths do not. Example: `https://showroom-abc12.apps.ocpv00.rhdp.net`

The easiest way to run a playbook is to open it in a browser. Ansible output streams in the tab until the playbook finishes (`✓ Completed successfully!` or `✗ Failed (exit code N)`, then `__DONE__`).

- Health check: `https://showroom-abc12.apps.ocpv00.rhdp.net/stream/qa/healthcheck`
- E2E: `https://showroom-abc12.apps.ocpv00.rhdp.net/stream/qa/e2e`

A 404 means that playbook is not in the **deployed** content tree. Push `qa-automation/` and re-provision or re-sync before retrying.

The same endpoints work from curl if you prefer the command line (`-N` streams `TASK` lines live; `-k` covers cluster TLS):

```bash
SHOWROOM=https://showroom-abc12.apps.ocpv00.rhdp.net

# Fast readiness check (< 60s)
curl -sk -N "$SHOWROOM/stream/qa/healthcheck"

# Full unattended walkthrough
curl -sk -N "$SHOWROOM/stream/qa/e2e"
```

## Marking complete

`publishing-house/spec.yaml` tracks these independently: `development.e2e.status` and `development.healthCheck.status`. Set each to `complete` once implemented and tested — both must be `complete` to pass compliance checks.
