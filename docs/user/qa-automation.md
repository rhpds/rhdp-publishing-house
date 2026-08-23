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
