# Operations Guide

Day-to-day operations for the Publishing House Central backend. Covers common deployment tasks, skill development rules, and troubleshooting.

See [Deployment Guide](deployment.md) for first-time setup and Ansible configuration.

## Common Tasks

All commands run from the `rhdp-publishing-house-central` repo root. The `-e env=dev` flag selects the environment vars file (`ansible/vars/dev.yml`). Substitute `prod` for production.

### Deploying Changes

| Task | Command | When to Use |
|------|---------|-------------|
| Rebuild backend only | `ansible-playbook ansible/deploy.yml -e env=dev --tags build-backend` | Backend code changes (Python, FastAPI, MCP tools) |
| Rebuild frontend only | `ansible-playbook ansible/deploy.yml -e env=dev --tags build-frontend` | Frontend code changes (Next.js, PatternFly) |
| Rebuild both | `ansible-playbook ansible/deploy.yml -e env=dev --tags builds` | Code changes spanning backend and frontend |
| Full redeploy | `ansible-playbook ansible/deploy.yml -e env=dev --tags deploy` | First deploy, major changes (code + config + schema) |
| Config/secret changes | `ansible-playbook ansible/deploy.yml -e env=dev --tags apply` | API keys, env vars, route config, Secrets, ConfigMaps |
| Run migrations | `ansible-playbook ansible/deploy.yml -e env=dev --tags migrate` | Schema changes (Alembic) |

Only build the changed component. Never do a full deploy for backend-only or frontend-only changes.

### Build Triggers

Commits pushed to the Central repo trigger OpenShift builds via the BuildConfig's `git_ref`. Batch commits and push at meaningful milestones -- each push triggers a build cycle.

There is no webhook for automatic builds. Ansible tags (`--tags builds`, `--tags build-backend`, `--tags build-frontend`) trigger builds manually. The BuildConfig pulls from the branch specified in `git_ref` (typically `main`).

### Migration Ordering

Migrations execute on the running backend pod. The pod must have the new code before running migrations. When changes include schema modifications:

1. Build the backend first: `--tags build-backend`
2. Then run migrations: `--tags migrate`

Or use `--tags deploy` to handle everything in the correct order.

### Running Tests

```bash
cd rhdp-publishing-house-central/src/backend
python -m pytest tests/ -x -q --timeout=30    # quick run
python -m pytest tests/ -v --timeout=60        # full suite
```

## Skill Development Rules

Rules that apply to all Publishing House skills. Read these before building or modifying any skill.

### Source of Truth

**Manifest is source of truth.** All project state flows from `publishing-house/manifest.yaml`. Central and Jira are downstream consumers. Never modify manifest fields outside your agent's scope.

**Content on disk is authoritative.** If a human modified a file, the skill treats the on-disk version as ground truth, even if it diverges from the spec. Build on top of what exists rather than overwriting it. Ask before reverting human work, even in autonomous mode.

### Boundaries

**Skills don't own phase transitions.** The orchestrator calls Central's gate tools at phase boundaries. Skills read inputs from the manifest and update their own artifacts. Never modify `lifecycle.current_phase` or other phase statuses.

**No direct external calls.** Skills never call RCARS, Jira, or GitHub directly. Everything goes through Central MCP tools (`ph_register`, `ph_get_status`, `ph_request_gate`, etc.).

### Read-Before-Write

**Read before you act.** Skills must read the current file from disk before modifying it. Never assume a file is the same as when an agent last wrote it. Human modifications are expected between sessions, between invocations, or mid-phase.

- Orchestrator: Read `manifest.yaml` at session start and after every agent dispatch.
- Writer: Read the module outline from `spec/modules/` immediately before writing.
- Editor: Read both the outline and the generated content before reviewing.
- All agents: The files on disk at dispatch time are the contract.

### Autonomy Levels

The manifest's `project.autonomy` field controls agent behavior:

| Level | Behavior |
|-------|----------|
| `guided` (default) | Confirm everything before writing to disk or committing |
| `assisted` | Auto-fix low-risk items. Pause at phase gates and decision points |
| `autonomous` | Work through the entire phase. Present output at the phase gate for review |

### File Conventions

| Directory | Purpose |
|-----------|---------|
| `publishing-house/spec/` | Specs |
| `publishing-house/spec/modules/` | Module outlines |
| `publishing-house/reviews/` | Review artifacts |
| `publishing-house/decisions/` | Decision records |
| `content/` | Content output |
| `automation/` | Automation output |

### Adding a New Skill

1. Create directory under `skills-plugin/skills/<name>/`.
2. Add `SKILL.md` with frontmatter (`name`, `description`, `model`).
3. Skill reads from manifest, does its work, updates its artifacts.
4. Skill must NOT modify phase-level state.
5. Add routing entry to the orchestrator's `SKILL.md`.

## Troubleshooting

### Pod Won't Start

Check logs:

```bash
oc logs deploy/central-backend -n <central-namespace>
```

Common causes:

- **Missing env vars.** Verify all required variables are set in `ansible/vars/dev.yml`. Check the pod's environment with `oc set env deploy/central-backend --list`.
- **DB connection failure.** Confirm PostgreSQL is running: `oc get pods -l app=postgresql -n <central-namespace>`. Check the `DATABASE_URL` connection string.
- **Missing API key Secret.** The `ph-mcp-api-keys` Secret must exist. See [MCP Authentication](mcp-auth.md) for API key management.

### MCP Tools Not Responding

1. Verify the MCP route is reachable: `curl -s https://<mcp-route-host>/health`.
2. Check API key validity. See [MCP Authentication](mcp-auth.md) for key rotation and hash generation.
3. Confirm the backend pod is healthy: `oc get pods -l app=central-backend -n <central-namespace>`.
4. Check backend logs for request errors: `oc logs deploy/central-backend -n <central-namespace> --tail=50`.

### Jira Sync Failures

Jira sync is non-blocking. Failures do not prevent phase transitions or gate evaluations.

Check Central logs for Jira client errors:

```bash
oc logs deploy/central-backend -n <central-namespace> | grep -i jira
```

Common causes:

- **Expired API token.** Regenerate the Jira API token and update the Secret via Ansible (`--tags apply`).
- **Network issues.** Transient connectivity to `redhat.atlassian.net`. Jira sync retries on the next scheduled refresh.

### RCARS Unavailability

RCARS unavailability blocks hard vetting gates but not soft ones. Content creation and phase transitions unrelated to vetting continue normally.

- Check SA token validity. Tokens rotate after 1 hour on OCP 4.11+. The backend re-reads the token per request -- verify the token file is mounted.
- Verify cross-namespace DNS resolution: `rcars-api.<rcars-namespace>.svc.cluster.local`.
- Check the RCARS pod is running: `oc get pods -l app=rcars-api -n <rcars-namespace>`.
- See [RCARS Service Auth](mcp-auth.md) for SA token and allowlist configuration.

### Stale Dashboard Data

The GitHub manifest refresh runs every 30 minutes. For immediate updates:

- Trigger a refresh via MCP tools (`ph_register` or `ph_get_status` with force).
- Restart the backend pod to clear any caches: `oc rollout restart deploy/central-backend -n <central-namespace>`.