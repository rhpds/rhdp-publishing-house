# Central Deployment

The Publishing House Central is deployed to OpenShift using Ansible with Jinja2-templated manifests, following the same pattern as RCARS.

## Architecture

```mermaid
graph LR
    U[User] -->|HTTPS| R[Route - TLS]
    R --> OA[OAuth Proxy]
    OA --> FE["Next.js Frontend<br/>(port 3000)"]
    FE -->|"API proxy<br/>(/api/v1/*)"| BE["FastAPI Backend<br/>(port 8080)"]
    BE --> PG["PostgreSQL<br/>(PVC)"]

    CC[Claude Code] -->|"HTTPS<br/>/mcp"| MR[MCP Route - TLS]
    MR --> BE
```

- **Frontend:** Next.js 16 + PatternFly 6. Exposed via OpenShift Route with OAuth proxy for SSO.
- **Backend:** FastAPI + SQLAlchemy. Internal only (ClusterIP, no external Route).
- **Database:** PostgreSQL 16 with persistent storage.
- **Auth:** OpenShift OAuth proxy on the frontend. Backend trusts internal traffic.

For full architecture details, see [Central Architecture](../architecture/central.md).

## Prerequisites

- Ansible with `kubernetes.core` collection
- `oc` CLI authenticated to the target cluster (for initial bootstrap)
- GitHub Fine-Grained PAT scoped to `rhpds` org with Contents read access

Install the Ansible collection:

```bash
ansible-galaxy collection install -r ansible/requirements.yml
```

## Configuration

```bash
cp ansible/vars/dev.yml.example ansible/vars/dev.yml
```

Fill in all `CHANGEME` values:

| Variable | Description |
|----------|-------------|
| `cluster_domain` | OpenShift apps domain (e.g., `apps.mycluster.example.com`) |
| `kubeconfig` | Path to the management SA kubeconfig (after bootstrap) |
| `git_ref` | Git branch to build from (e.g., `main`) |
| `pg_password` | PostgreSQL password — generate with `openssl rand -hex 16` |
| `oauth_client_secret` | OAuth client secret — generate with `openssl rand -hex 16` |
| `oauth_cookie_secret` | OAuth cookie secret — generate with `openssl rand -hex 16` |
| `github_repo` | Repo in `owner/name` format (e.g., `rhpds/rhdp-publishing-house-central`) |
| `github_token` | GitHub PAT for fetching manifests from private repos |
| `rcars_url` | RCARS external URL for frontend links (e.g., `https://rcars-dev.apps.<cluster-domain>/`) |
| `rcars_internal_url` | RCARS cluster-internal URL (e.g., `http://rcars-api.rcars-dev.svc.cluster.local:8080`) |
| `rcars_stages` | RCARS catalog stages to query. Default: `prod`. Set to `prod,zt` or `prod,event,zt` to include other stages. |
| `mcp_route_host` | Hostname for the MCP endpoint Route (e.g., `ph-mcp-dev.apps.<cluster-domain>`) |
| `mcp_api_keys` | Dict of `name: sha256-hash` pairs for MCP API key auth. See [MCP Auth Admin Guide](mcp-auth.md) |
| `jira_url` | Jira Cloud instance URL (e.g., `https://redhat.atlassian.net`) |
| `jira_email` | Jira service account email |
| `jira_api_token` | Jira API token |
| `jira_project_key` | Jira project key (default: `RHDPCD`) |
| `litemaas_url` | LiteMaaS endpoint URL (preferred LLM provider) |
| `litemaas_key` | LiteMaaS API key |
| `vertex_project_id` | Google Vertex AI project ID (fallback) |
| `anthropic_api_key` | Anthropic API key (fallback) |
| `spec_review_model` | Model for spec review at approval gate (default: `claude-haiku-4-5`) |

**NEVER commit `dev.yml` or `prod.yml`** — they are gitignored. Only `.example` files are tracked.

## First-Time Deployment

```bash
# 1. Bootstrap management ServiceAccount (one-time, with personal kubeconfig)
ansible-playbook ansible/deploy.yml -e env=dev -e kubeconfig=~/.kube/config --tags mgmt-rbac

# 2. Update dev.yml with the generated mgmt kubeconfig path

# 3. Full deploy (infra + app + builds + migrations)
ansible-playbook ansible/deploy.yml -e env=dev --tags deploy
```

The `deploy` tag runs infra manifests, app manifests, builds, and database migrations in one pass.

## Playbook Tags

| Tag | What It Does | When to Use |
|-----|-------------|-------------|
| `mgmt-rbac` | Bootstrap management SA, ClusterRole, generate kubeconfig | One-time setup |
| `deploy` | Full deploy: infra + app + builds + migrate | First deploy or major changes (code + config + schema) |
| `apply` | App manifests only (Secrets, ConfigMaps, Deployments, Services, Route) | Config/secret changes (API keys, env vars, route config) |
| `builds` | Trigger builds + wait for rollout | Code changes only (after `git push`) |
| `build-backend` | Build backend only + rollout | Backend code changes |
| `build-frontend` | Build frontend only + rollout | Frontend code changes |
| `migrate` | Run Alembic migrations in backend pod | Schema changes only |

## Subsequent Deploys

```bash
# Full redeploy
ansible-playbook ansible/deploy.yml -e env=dev --tags deploy

# Rebuild only (after code push)
ansible-playbook ansible/deploy.yml -e env=dev --tags builds

# App manifests only (no build)
ansible-playbook ansible/deploy.yml -e env=dev --tags apply

# Schema migration only
ansible-playbook ansible/deploy.yml -e env=dev --tags migrate
```

## Build Triggers

Builds are triggered manually via Ansible tags (`--tags builds`, `--tags build-backend`, `--tags build-frontend`). The BuildConfigs use the `git_ref` from vars (e.g., `main`) to determine which branch to build from.

## Container Images

Two Containerfiles at the repo root:

- **`Containerfile.backend`** — UBI9 Python 3.11 multi-stage. Installs requirements, copies app + Alembic. Runs uvicorn on port 8080.
- **`Containerfile.frontend`** — UBI9 Node.js 20 multi-stage. Builds Next.js standalone output. Runs `node server.js` on port 3000.

## Repos

- [rhdp-publishing-house-central](https://github.com/rhpds/rhdp-publishing-house-central) — Central app and deployment manifests
- [rhdp-publishing-house](https://github.com/rhpds/rhdp-publishing-house) — the CLI skills and plugin
