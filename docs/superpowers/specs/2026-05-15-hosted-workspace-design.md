# Hosted Workspace Design (Dev Spaces Integration)

**Date:** 2026-05-15
**Status:** Brainstorm complete, pending team review
**Phase:** Milestone 2, Phase 4

## Problem

Users without local Claude Code or Anthropic model access cannot use PH skills. The portal provides project visibility but not execution capability. PH needs a hosted execution path that gives these users full skill parity — intake, writing, editing, automation, orchestration — without requiring local tooling setup.

## Solution

Integrate OpenShift Dev Spaces into the portal as an opt-in hosted workspace. Portal provisions a Dev Spaces workspace per project per user, pre-configured with Claude Code, PH skills, and all required tooling. Users click "Open in Dev Spaces" on a project detail page and land in a fully functional VS Code environment in their browser.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    OpenShift Cluster (ocpv-infra01)             │
│                                                                 │
│  ┌──────────────────────┐     ┌──────────────────────────────┐ │
│  │  PH Portal            │     │  Dev Spaces Operator         │ │
│  │  ns: publishing-house │     │  (CheCluster CRD)            │ │
│  │                       │     │                              │ │
│  │  ┌─────────────────┐ │     │  ┌────────────────────────┐  │ │
│  │  │ FastAPI Backend  │ │     │  │ Workspace Pod          │  │ │
│  │  │  - REST API      │◄──MCP──│  │  ┌──────────────────┐ │  │ │
│  │  │  - MCP Server    │ │     │  │  │ VS Code Server    │ │  │ │
│  │  │  - Workspace API │─┼─DS──►  │  │  + CC Extension   │ │  │ │
│  │  │    (CRUD)        │ │ API │  │  │  + PH Skills      │ │  │ │
│  │  └────────┬─────────┘ │     │  │  └──────────────────┘ │  │ │
│  │           │           │     │  │  ┌──────────────────┐ │  │ │
│  │  ┌────────▼─────────┐ │     │  │  │ CC CLI            │ │  │ │
│  │  │ Next.js Frontend │ │     │  │  │  + oc, ansible    │ │  │ │
│  │  │  - Project views │ │     │  │  │  + git, python    │ │  │ │
│  │  │  - "Open in DS"  │ │     │  │  └──────────────────┘ │  │ │
│  │  │    button        │ │     │  │                        │  │ │
│  │  └──────────────────┘ │     │  │  ENV: MAAS_API_KEY     │  │ │
│  │                       │     │  │  ENV: MCP_ENDPOINT     │  │ │
│  │  ┌──────────────────┐ │     │  └────────────────────────┘  │ │
│  │  │ PostgreSQL 16    │ │     │                              │ │
│  │  │  + workspace tbl │ │     └──────────────────────────────┘ │
│  │  └──────────────────┘ │                                      │
│  └──────────────────────┘     ┌──────────────────────────────┐ │
│                                │  LiteLLM (MaaS)              │ │
│                                │  POST /key/generate           │ │
│                                │  POST /key/delete             │ │
│                                └──────────────────────────────┘ │
│                                                                 │
│  ┌──────────────────────┐                                      │
│  │  RCARS (existing)     │                                      │
│  │  ns: rcars-dev        │                                      │
│  └──────────────────────┘                                      │
└─────────────────────────────────────────────────────────────────┘
```

### Key Principles

1. **One-way integration:** Workspace calls portal MCP tools. Portal never pushes to workspace.
2. **Opt-in:** Workspace is optional. Portal works identically without it. No changes to the experience for users who don't want a workspace.
3. **Git is the sync mechanism:** No custom sync infrastructure. `git pull --rebase --autostash` on resume, `git push` on commit. Same as local CC.
4. **Portal provisions, Dev Spaces manages:** Portal creates and links workspaces. Dev Spaces handles lifecycle (idle timeout, persistence, resource quotas).
5. **Short-lived keys:** MaaS key provisioned at workspace creation, validated on resume, revoked on deletion. User never sees or manages keys.
6. **CC updated at session start:** Base image has CC pre-installed as fallback. Startup script updates to latest.

### Why Dev Spaces (Not Lighter Alternatives)

Three approaches were evaluated:

| Approach | Verdict | Reasoning |
|----------|---------|-----------|
| **Dev Spaces + Full IDE** | **Chosen** | Full CC parity, Red Hat product dog-fooding story, workspace persistence and lifecycle management for free, opt-in and non-intrusive |
| Containerized CC + Web Terminal | Rejected | Lighter resources but no file editor, no dog-fooding story, custom lifecycle management required, terminal-only UX limits audience |
| Chat UI with CC Backend | Rejected | Most engineering for least capability. CC-to-chat translation is extremely complex and lossy. Can't achieve full skill parity. |

Dev Spaces was chosen partly for the dog-fooding value — "we run PH on Dev Spaces" is a compelling demo. The infrastructure overhead is acceptable given the cluster is already available and the Dev Spaces operator install is trivial.

The portal↔workspace interface is designed as an abstraction (WorkspaceManager service) so a lighter execution backend could replace Dev Spaces later without portal changes. This is explicitly a backlog item for express mode, where Dev Spaces may be heavier than needed.

## Target Audience

**Phase 1:** Content developers comfortable with an IDE and terminal. They know git, can navigate VS Code, and understand the PH workflow. They just don't have CC or model access locally.

**Phase 2 (backlog):** Broader audience — solution architects, field engineers, PMMs. May need guided onboarding, simplified views, or a conversational layer on top of the workspace. Not in scope for this spec.

## User Flow

### First Time: Creating a Workspace

```
User visits project detail page in portal
  │
  ▼
Sees "Open in Dev Spaces" button (subtle, non-intrusive)
  │
  ▼
Clicks button
  │
  ▼
Portal backend:
  1. Calls LiteLLM API: POST /key/generate
     - alias: "ph-{user_id}-{project_id}"
     - duration: configurable (env var, default TBD: 7d or 30d)
     - models: [configured model list]
     - metadata: { owner: user_email, project_id, created_by: "publishing-house" }
  2. Calls Dev Spaces API: create workspace
     - devfile: PH custom devfile
     - repo: project's git repo URL
     - env vars: MAAS_API_KEY, MCP_ENDPOINT, PROJECT_ID
  3. Stores workspace record in DB
  │
  ▼
Redirects user to workspace URL → VS Code opens in browser
```

### Returning: Workspace Running

```
User visits project detail page → button shows "Open Workspace"
  │
  ▼
Clicks button → redirects to stored workspace URL
```

### Returning: Workspace Stopped

```
User visits project detail page → button shows "Resume Workspace"
  │
  ▼
Clicks button
  │
  ▼
Portal backend:
  1. Calls LiteLLM: GET /key/info → check if key is still valid
  2. If expired: provisions new key (POST /key/generate), updates workspace env
  3. Calls Dev Spaces API: start workspace
  │
  ▼
Redirects user to workspace URL
```

### Workspace Startup Sequence

Every time a workspace starts or resumes, the post-start lifecycle hook runs:

```
1. Update CC CLI    (npm update -g @anthropic-ai/claude-code)
2. Update CC VS Code extension
3. git pull --rebase --autostash   (sync latest from remote)
4. Validate MaaS key               (quick health check against LiteLLM)
5. Configure CC env vars            (ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL)
```

### Workspace Teardown

```
User or admin deletes workspace (via Dev Spaces dashboard or portal)
  │
  ▼
Portal backend:
  1. Calls Dev Spaces API: delete workspace
  2. Calls LiteLLM: POST /key/delete → revoke key
  3. Removes workspace record from DB
```

## Portal UI Changes

Minimal. One button on the project detail page. No new pages.

| Workspace State | Button Label | Button Action |
|----------------|-------------|---------------|
| None exists | "Open in Dev Spaces" | Create workspace + redirect |
| Running | "Open Workspace" | Redirect to workspace URL |
| Stopped | "Resume Workspace" | Validate key, start workspace, redirect |

No workspace list page. No workspace management UI in the portal. Dev Spaces has its own dashboard for that. Portal links to workspaces, doesn't manage them.

## MaaS Key Lifecycle

Keys are provisioned via the LiteLLM REST API (`POST /key/generate`). The portal owns the full key lifecycle — users never see, copy, or manage keys.

```
Workspace created → Key provisioned (duration: configurable TTL)
  │
  ├── Workspace active → Key valid, CC works
  │
  ├── Workspace idled by Dev Spaces → Key still valid (TTL-based)
  │
  ├── Workspace resumed → Portal validates key
  │     ├── Valid → continue
  │     └── Expired → portal provisions new key, updates workspace env
  │
  └── Workspace deleted → Portal revokes key (POST /key/delete)
```

**Key duration** is a configurable environment variable (`LITELLM_KEY_DURATION`). Default TBD (7d or 30d). If a key expires while a workspace is stopped, the user must restart the workspace from the portal — the resume flow auto-provisions a new key. No mid-session key rotation.

**Key-to-user mapping:** Key alias `ph-{user_id}-{project_id}` plus LiteLLM metadata `{ owner: user_email }` provides traceability in both directions. Portal DB `workspaces` table stores `maas_key_alias` and `maas_key_id`.

### LiteLLM Integration

Portal backend calls the LiteLLM REST API directly — no Ansible role needed for runtime operations. Reference implementation: `rhpds/rhpds.litellm_virtual_keys` (Ansible role used for RHDP lab provisioning, demonstrates the full API surface).

| Operation | LiteLLM Endpoint | When |
|-----------|------------------|------|
| Provision key | `POST /key/generate` | Workspace creation |
| Validate key | `GET /key/info?key={token}` | Workspace resume |
| Revoke key | `POST /key/delete` | Workspace deletion |
| Extend key | `POST /key/update` | Future (if needed) |

Auth: Bearer token with LiteLLM master key. Master key stored as OpenShift Secret, mounted into portal pod.

## Portal Backend Changes

### New Services

**`app/services/workspace_manager.py`** — Orchestrates workspace lifecycle. Calls LiteLLMClient and DevSpacesClient. Manages DB records.

| Method | Purpose |
|--------|---------|
| `create_workspace(project_id, user_id)` | Provision key → create workspace → store record → return URL |
| `get_workspace(project_id, user_id)` | Return workspace record (URL, status, key info) |
| `resume_workspace(project_id, user_id)` | Validate key → reprovision if expired → start workspace → return URL |
| `delete_workspace(project_id, user_id)` | Delete workspace → revoke key → remove record |
| `get_workspace_status(project_id, user_id)` | Query Dev Spaces API → return status enum |

**`app/services/litellm_client.py`** — Async HTTP client for LiteLLM API. Same patterns as `rcars_client.py` (retry logic, structured errors, async).

| Method | LiteLLM Endpoint |
|--------|------------------|
| `provision_key(alias, user_id, duration, models, metadata)` | `POST /key/generate` |
| `validate_key(token)` | `GET /key/info?key={token}` |
| `revoke_key(token_hash)` | `POST /key/delete` |
| `extend_key(key_id, duration)` | `POST /key/update` |

Config env vars: `LITELLM_URL`, `LITELLM_MASTER_KEY`, `LITELLM_KEY_DURATION`, `LITELLM_MODELS`

**`app/services/devspaces_client.py`** — Client for Dev Spaces API. Manages workspace CRUD.

| Method | Purpose |
|--------|---------|
| `create_workspace(devfile_url, repo_url, env_vars)` | Create workspace → return workspace_id + URL |
| `start_workspace(workspace_id)` | Start stopped workspace |
| `stop_workspace(workspace_id)` | Stop running workspace |
| `delete_workspace(workspace_id)` | Delete workspace + PVC |
| `get_status(workspace_id)` | Return status: running, stopped, starting, not_found |

Config env vars: `DEVSPACES_API_URL`, `DEVSPACES_TOKEN`

### New Database Model

```
workspaces
  ├── id              (UUID, PK)
  ├── project_id      (FK → projects.id)
  ├── user_id         (string, from OAuth proxy headers)
  ├── workspace_id    (string, Dev Spaces workspace ID)
  ├── workspace_url   (string, browser URL for redirect)
  ├── maas_key_alias  (string, "ph-{user_id}-{project_id}")
  ├── maas_key_id     (string, LiteLLM key ID for updates/revocation)
  ├── created_at      (timestamp)
  └── updated_at      (timestamp)

Constraint: unique(project_id, user_id)
```

One workspace per project per user. Alembic migration required.

### New API Routes

```
POST   /api/v1/projects/{id}/workspace        Create workspace
GET    /api/v1/projects/{id}/workspace        Get workspace info + status
POST   /api/v1/projects/{id}/workspace/start  Resume stopped workspace
DELETE /api/v1/projects/{id}/workspace        Delete workspace + revoke key
```

All routes require authenticated user (via OAuth proxy headers). User can only manage their own workspaces.

## Custom UDI Image

Base image: `registry.redhat.io/devspaces/udi-rhel9`
Published to: `quay.io/rhpds/ph-udi:latest`

### Image Contents

**Already in base UDI:**
- oc CLI
- git
- Python 3.11+
- Node.js
- VS Code Server

**Added layers:**
- Claude Code CLI (`npm install -g @anthropic-ai/claude-code`)
- CC VS Code extension (pre-installed into extensions directory)
- PH skills plugin (cloned and configured, MCP endpoint pre-set)
- Ansible + required collections (`pip install ansible-core` + `ansible-galaxy install`)
- Workspace startup script (`/opt/ph/scripts/workspace-startup.sh`)

### Image Update Strategy

- **CC CLI:** Pre-installed in image as fallback (works if npm is unreachable). Updated to latest at every workspace start via startup script. No image rebuild needed for CC updates.
- **Base image:** Rebuild periodically (monthly or on major tooling changes) for Ansible collections, Python packages, security patches.
- **PH skills plugin:** Pre-configured in image. Optionally git-pull latest at startup.

### Startup Script

```bash
#!/bin/bash
# /opt/ph/scripts/workspace-startup.sh
# Runs as Dev Spaces postStart lifecycle command

# 1. Update CC to latest
npm update -g @anthropic-ai/claude-code 2>/dev/null || true

# 2. Update VS Code extension (mechanism TBD — marketplace or vsix)

# 3. Sync project repo
cd /projects/${PROJECT_REPO_NAME}
git pull --rebase --autostash

# 4. Validate MaaS key
curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer ${MAAS_API_KEY}" \
  ${LITELLM_URL}/key/info \
  | grep -q "200" || echo "WARNING: MaaS key may be invalid. Restart workspace from PH portal."

# 5. Configure CC environment
export ANTHROPIC_API_KEY=${MAAS_API_KEY}
export ANTHROPIC_BASE_URL=${LITELLM_URL}/v1
```

## Devfile

```yaml
schemaVersion: 2.2.0
metadata:
  name: publishing-house-workspace

components:
  - name: dev
    container:
      image: quay.io/rhpds/ph-udi:latest
      memoryLimit: 4Gi
      cpuLimit: "2"
      mountSources: true
      env:
        - name: MAAS_API_KEY
          value: ""  # injected at workspace creation
        - name: MCP_ENDPOINT
          value: https://publishing-house.apps.example.com/mcp
        - name: LITELLM_URL
          value: https://litellm.example.com
        - name: PROJECT_ID
          value: ""  # injected at workspace creation

commands:
  - id: post-start
    exec:
      component: dev
      commandLine: /opt/ph/scripts/workspace-startup.sh
      workingDir: /projects

events:
  postStart:
    - post-start
```

Devfile stored in portal repo or served dynamically by the portal backend. Env vars injected at workspace creation time via Dev Spaces API.

## Prerequisites

- [ ] Dev Spaces operator installed on ocpv-infra01 cluster
- [ ] LiteLLM endpoint accessible from portal namespace (network policy or route)
- [ ] Custom UDI image built and pushed to quay.io/rhpds/ph-udi
- [ ] Dev Spaces API auth configured (service account or OAuth token for portal backend)
- [ ] PH skills plugin repo accessible from workspace pods (GitHub SSH or HTTPS)

## Backlog (Out of Scope)

Items parked during brainstorming. Tracked in BACKLOG.md.

| Item | Why Deferred |
|------|-------------|
| **Lightweight express mode execution** | Dev Spaces is heavy for one-off demos. Evaluate code-server or headless CC later. Portal↔workspace interface designed to allow backend swap. |
| **MCP auth rationalization** | MCP auth is currently manual API keys. Needs proper design — possibly tied to workspace identity. Separate effort. |
| **Broader audience UX** | Phase 1 targets content developers. SAs, field engineers, PMMs need guided onboarding and simplified views. Phase 2. |
| **MaaS key TTL tuning** | Start with configurable default, tune based on usage data. |
| **Mid-session key rotation** | If key expires during active work, user restarts workspace from portal. Acceptable for Phase 1. Automated rotation is future work if usage patterns demand it. |

## Architectural Guardrails

These constraints preserve future flexibility:

1. **WorkspaceManager is an abstraction.** It hides whether the backend is Dev Spaces, custom pods, or something else. Frontend and API routes don't know or care. A lighter backend can replace Dev Spaces without touching anything above the service layer.

2. **One-way integration only.** Portal does not push to workspaces. If bidirectional communication is ever needed, it must be a conscious architectural decision with its own spec, not scope creep.

3. **Keys are portal-managed.** Users never see, copy, or manage keys. This contract holds regardless of execution backend or key provider.

4. **Workspace is opt-in.** No manifest field, no required configuration. Portal tracks workspace state in its own DB. Skills and CC work identically whether running locally or in Dev Spaces.
