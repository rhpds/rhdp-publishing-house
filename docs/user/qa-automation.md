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

Walks through the learner's steps from the module content and confirms the workshop/demo can be completed start to finish, unattended.

**Guided patterns** (AgD v2 Guided, ZT Guided) — reuse what already exists instead of re-implementing it. Each module already has standalone `runtime-automation/<module>/{setup,solve,validate}.yml` playbooks that take the same extravars Nookbag passes when a learner clicks Solve/Validate (`k8s_kubeconfig`, `student_ns`, `bastion_host`, etc.). Loop through modules in `ui-config.yml` order and run `setup.yml` (if present) → `solve.yml` → `validate.yml` for each, stopping on the first failure. (The template repo's `.scaffolds/zt-guided-migration/qa-automation/` shows this same loop-and-fail-fast shape adapted for older shell-script-based modules — same idea, different execution mechanism.)

**Open/classic pattern** (AgD v2 Open) — there are no solve/validate playbooks to call into, since classic Showroom has no solve/validate buttons. Script the learner's documented steps directly (CLI/API calls that mirror what they'd do manually).

**Requirements:**

- Fails on the first broken step, with a message identifying which module/step failed
- Runs unattended, start to finish, no manual intervention

## Marking complete

`publishing-house/spec.yaml` tracks these independently: `development.e2e.status` and `development.healthCheck.status`. Set each to `complete` once implemented and tested — both must be `complete` to pass compliance checks.
