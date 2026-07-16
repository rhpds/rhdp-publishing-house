---
title: System Design
description: Publishing House system overview, skills layer, Central backend, data flow, manifest model, auth, and deployment
---

# System Design

## System Overview

Publishing House is a three-part system -- a Claude Code skills plugin running locally on a developer's machine, a Central backend deployed on OpenShift, and integrations with RCARS and Jira -- that manages the full content development lifecycle for Red Hat Demo Platform labs, workshops, and demos.

### Components

| Component | Purpose |
|---|---|
| Skills Plugin | Local AI agents: intake, writing, editing, automation, worklog, orchestration |
| Central Backend | Gate authority, Jira sync engine, RCARS gateway, project dashboard API |
| Dashboard | Pipeline board, project detail views, gate decisions, validation results |
| RCARS | Content advisory -- semantic catalog search, overlap detection, recommendations |

The skills plugin is the primary interface -- content developers interact with Publishing House by running `/rhdp-publishing-house` in Claude Code. The orchestrator skill discovers the project, reads the manifest, and dispatches specialized skills. Skills talk to Central through MCP tools for gate decisions, Jira sync, RCARS queries, and state persistence. Central talks to external services on behalf of skills -- skills never call RCARS, Jira, or GitHub APIs directly.

```mermaid
graph TD
    Dev["Content Developer"] -->|"/rhdp-publishing-house"| CC["Claude Code"]

    subgraph "Skills Plugin (local)"
        CC --> Orch["Orchestrator"]
        Orch -->|"dispatch"| Intake["Intake"]
        Orch -->|"dispatch"| Writer["Writer"]
        Orch -->|"dispatch"| Editor["Editor"]
        Orch -->|"dispatch"| Auto["Automation"]
        Orch -->|"dispatch"| WL["Worklog"]
    end

    Writer -->|"wraps"| SLab["showroom:create-lab"]
    Editor -->|"wraps"| SVerify["showroom:verify-content"]
    Auto -->|"wraps"| ACat["agnosticv:catalog-builder"]

    Orch -->|"MCP tools<br/>(HTTPS, Bearer API key)"| MCP

    subgraph "Central Backend (OpenShift)"
        MCP["FastMCP Server<br/>/mcp endpoint"]
        MCP --> Gate["Gate Service<br/>+ PhaseEngine"]
        MCP --> Jira["Jira Sync Service"]
        MCP --> RC["RCARS Client"]
        Gate --> PG[(PostgreSQL)]
        Jira --> PG
        RC --> PG
    end

    subgraph "Dashboard"
        PG --> API["REST API"]
        OA["OAuth Proxy"] --> FE["Web Frontend"]
        API --> FE
    end

    RC -->|"cross-namespace"| RCARS["RCARS API"]
    Jira -->|"HTTPS"| JC["Jira Cloud"]

    style Orch fill:#1a73e8,color:#fff
    style MCP fill:#1a73e8,color:#fff
```

---

## Skills Layer

The skills plugin is a Claude Code plugin containing skills that run locally in the developer's session. Skills are AI agents -- each has a `SKILL.md` file that defines its identity, capabilities, and dispatch rules. They execute on the developer's machine with full access to the local filesystem and git repository.

### Skills

| Skill | Role | Wraps |
|---|---|---|
| **Orchestrator** | Hub. Discovers project, reads manifest, determines current phase, dispatches to the right skill. Calls Central for registration, status, and gate requests. | -- |
| **Intake** | Conversational project onboarding. Three entry paths: "I have a spec," "I have an idea," or "I have a Jira issue with requirements." Deployment mode selection. RCARS vetting via MCP. | -- |
| **Writer** | Content generation. Produces AsciiDoc modules for Showroom labs and demos from spec outlines. | `showroom:create-lab`, `showroom:create-demo` |
| **Automation** | Environment and deployment configuration. Four sub-phases: requirements analysis, catalog item creation, automation code scaffolding, testing. | `agnosticv:catalog-builder` |
| **Editor** | Content review. Runs quality checks against Red Hat content standards, generates review reports with dimension scores and findings. | `showroom:verify-content` |
| **Worklog** | Session bridging. Records what was accomplished, decisions made, and what should happen next. Enables multi-session continuity across days or weeks. | -- |

### Orchestrator as Hub

The orchestrator is the only skill a developer invokes directly. When `/rhdp-publishing-house` runs, the orchestrator:

1. **Discovers the project** -- checks for `publishing-house/manifest.yaml` in the current repo, or queries Central for registered projects by the current user.
2. **Reads the manifest** -- parses project metadata, current phase, and phase statuses.
3. **Calls Central** -- registers the project if new (`ph_register`), gets current status (`ph_get_status`), retrieves any pending gate decisions.
4. **Dispatches the appropriate skill** -- based on which lifecycle phase is active. If writing is in progress, the writer is dispatched. If intake hasn't completed, intake runs.

The orchestrator manages [phase transitions](lifecycle-phases.md) by calling Central's gate tools (`ph_request_gate`) at phase boundaries. Individual skills must not modify phase-level state -- they read their inputs from the manifest, produce their outputs (AsciiDoc modules, review reports, catalog configs), and hand control back to the orchestrator.

### Skills Wrap Platform Tools

Writer, editor, and automation skills wrap existing platform skills rather than implementing content generation or validation from scratch. Publishing House creates structured specs and manifests that describe what needs to be built, then hands them off to domain-specific skills that know how to build it. For example, the writer generates a structured payload from the project spec and passes it to `showroom:create-lab`, which handles AsciiDoc generation, scaffold setup, and Showroom conventions. This means PH skills benefit from improvements to the underlying tools without code changes -- and the platform tools can be used independently outside of Publishing House.

### MCP as the Only External Channel

Skills communicate with Central exclusively through MCP tools. A skill that needs RCARS content vetting calls `ph_rcars_query`. A skill that needs to record a gate decision calls `ph_request_gate`. Skills never make raw HTTP calls to external services. This constraint means Central controls all external access -- if an API changes or auth rotates, only Central's client code changes. Skills remain untouched.

### Autonomy Levels

Each project declares an autonomy level in its manifest, controlling how much confirmation the orchestrator requires from the developer:

- **Guided** -- confirm everything. The orchestrator presents each action and waits for approval before proceeding. Default for new projects.
- **Assisted** -- auto-fix low-risk issues. Routine corrections (formatting, minor AsciiDoc fixes) happen automatically. Structural changes still require confirmation.
- **Autonomous** -- auto-fix all clear findings. The orchestrator proceeds through phases with minimal interruption, only stopping for ambiguous decisions or gate failures.

The autonomy level affects orchestrator behavior, not skill behavior. Skills always produce the same output regardless of autonomy -- the orchestrator decides whether to apply that output automatically or present it for review.

---

## Central Backend

The Central backend is a FastAPI application deployed on OpenShift with a FastMCP server mounted at `/mcp`. It is the single gateway between skills and all external services. One codebase, one deployment, one database.

### Four Roles

**Gate authority.** When a project requests advancement to the next lifecycle phase, the gate service validates prerequisites using the PhaseEngine (a pure-logic module with no I/O dependencies) and records the decision in PostgreSQL. For example, the writing phase cannot start until the approval gate passes -- Central checks that spec refinement is complete and the spec meets structural and quality requirements before allowing advancement. Every gate decision -- approved or rejected, with rationale -- is recorded permanently. Records are appended, never modified, forming a complete audit trail of how a project moved through its lifecycle.

**Jira sync engine.** For onboarded projects (deployment mode `rhdp_published`), Central creates and updates Jira tickets automatically as work progresses. When a gate passes, corresponding Jira tasks transition. When a module completes writing, its task moves to Done. Sync is one-directional: PH pushes to Jira, Jira never drives PH state. This is a deliberate design choice -- the manifest in git is the source of truth, and Jira is a downstream reporting view. Jira sync is also non-blocking: if the Jira API returns an error or times out, the failure is logged but the gate decision still succeeds. Jira unavailability must never block content development.

**RCARS gateway.** Central proxies content advisory requests to RCARS. Three MCP tools (`ph_rcars_query`, `ph_rcars_catalog_search`, `ph_rcars_catalog_item`) expose RCARS capabilities to skills. See [RCARS Integration](rcars-integration.md) for the auth model and network topology.

**Project dashboard.** A web frontend gives visibility into all active projects. The dashboard sits behind an OpenShift OAuth proxy for SSO authentication. Key views: pipeline board (kanban by lifecycle phase), project detail (phase accordions, worklog timeline, artifacts), and gate decision history. The frontend consumes a REST API served by the same FastAPI process -- the MCP endpoint and REST API coexist in a single deployment.

### Gate Service and PhaseEngine

The gate service is the enforcement layer for lifecycle transitions. When the orchestrator calls `ph_request_gate(target_phase="writing")`, Central:

1. Fetches the project's manifest from GitHub to ensure it has the latest version.
2. Passes the manifest to the PhaseEngine, which checks whether all prerequisite phases for the target are completed.
3. If prerequisites are met, records a gate decision (project ID, target phase, decision, rationale, timestamp, requested_by) and returns approval.
4. If prerequisites are not met, returns rejection with a list of what's missing.

The PhaseEngine is a pure-logic module -- it takes a manifest dict and a target phase, applies the phase dependency graph, and returns a decision. No database calls, no HTTP calls. This makes it trivially testable and ensures gate logic is deterministic.

For the vetting phase specifically, the gate service also runs an RCARS query to check for content overlap before approving advancement. This is the only gate that involves an external service call.

### Background Manifest Sync

Central maintains a cached copy of each registered project's manifest in PostgreSQL. This cache is refreshed from GitHub on a schedule (default every 30 minutes). The sync process:

1. Iterates over all registered projects.
2. Checks each project's GitHub repo for the manifest file via the GitHub API.
3. If the manifest has changed (compared by content hash), parses it and updates the database.
4. Recomputes phase status using the PhaseEngine.

This catches changes that bypass the MCP path -- manual manifest edits, CI pipeline updates, changes made by developers who don't use PH skills. Manual refresh is also available through the dashboard UI and the `ph_register` MCP tool (which performs an immediate refresh).

---

## Data Flow

Two data paths feed the Central database, each serving a different purpose.

### Path 1: Skill to MCP to Central (Real-Time Writes)

This is the primary path during active development. When a developer works in Claude Code, the orchestrator calls MCP tools that write directly to Central:

- `ph_register` -- registers a new project, fetches its manifest from GitHub, creates the database record.
- `ph_get_status` -- reads the project's current phase status, computes the next recommended action.
- `ph_request_gate` -- requests phase advancement, triggers the PhaseEngine, records the gate decision, syncs to Jira.
- `ph_submit_results` -- stores structured results from local skill runs (content verification scores, automation validation).
- `ph_store_intake_results` -- persists intake session data across Claude Code restarts.

These writes flow through the FastMCP server, pass API key authentication, and update PostgreSQL immediately. Jira sync triggers as a side effect of gate transitions -- the Jira sync service is called after the gate record is committed, not before.

### Path 2: Background Sync (Scheduled Pull)

The background sync pulls manifests from GitHub on a schedule, recomputes phase status, and updates the cached state in PostgreSQL. This path catches changes that bypass the MCP path -- manual manifest edits, CI pipeline updates, changes made by developers who don't use PH skills.

The two paths converge in PostgreSQL. The dashboard reads from the database regardless of which path wrote the data.

---

## Manifest as Source of Truth

All project state flows from a single YAML file: `publishing-house/manifest.yaml` in the project's git repository. The manifest records project metadata, current lifecycle phases, phase completion statuses, module lists, automation configuration, and integration keys.

```yaml
project:
  name: "OCP Getting Started Workshop"
  owner_github: "jsmith"
  owner_email: "jsmith@redhat.com"
  type: "workshop"
  deployment_mode: "rhdp_published"
  autonomy: "guided"

lifecycle:
  phases:
    intake:
      status: "completed"
      completed_at: "2026-04-15 14:30"
      assignees: ["jsmith"]
    writing:
      status: "in_progress"
      assignees: ["jsmith", "mlee"]
      artifacts: ["content/modules/01-cluster-basics/pages/index.adoc"]
    automation:
      status: "pending"
```

Phase statuses follow a simple state machine: `pending` to `in_progress` to `completed` (or `skipped` for optional phases). Transitions are validated by the PhaseEngine and recorded as gate decisions. There is no backward transition -- a completed phase stays completed.

Central and Jira are downstream consumers. They read from the manifest (via GitHub sync or MCP calls) and never write back. If Central's database is wiped, re-registering the project from its repo URL reconstructs the full state. If Jira tickets are deleted, re-syncing recreates them. The manifest is the recovery point.

Express mode projects have no git repository -- they are transient, one-off demo environments where state lives in the Central database only. See [Deployment Modes](../user/deployment-modes.md) for details on how express mode differs.

---

## Auth Model

Two authentication boundaries protect the system, each using a different mechanism appropriate to its trust domain.

### Boundary 1: External -- Claude Code to Central

Claude Code users authenticate to the PH MCP endpoint using API keys sent as `Authorization: Bearer <raw-key>` headers over HTTPS.

- **Key storage:** API keys are stored securely in a Kubernetes Secret, volume-mounted into the backend pod.
- **Validation:** The MCP auth middleware validates the key on every tool call before dispatching.
- **Scope:** Authentication is all-or-nothing -- a valid key grants access to all MCP tools. There is no per-project or per-user scoping at the auth layer; any authenticated user can interact with any project. Fine-grained access control is a future consideration.
- **Key lifecycle:** Keys are currently provisioned and revoked through the Ansible deployer. The backend reads the key file at startup; adding or revoking a key requires a redeployment. A more robust key management system is planned. See [MCP Auth Admin Guide](../admin/mcp-auth.md).

### Boundary 2: Internal -- Central to RCARS

The Central backend authenticates to RCARS using its Kubernetes ServiceAccount token for cross-namespace calls within the OpenShift cluster.

- **Token source:** Auto-mounted by Kubernetes. The RCARS client re-reads this token from the filesystem on every request -- it is never cached in memory, because bound service account tokens rotate automatically.
- **Validation:** RCARS validates the token and checks the authenticated identity against an allowlist.
- **No secrets to manage:** Kubernetes handles the entire token lifecycle -- creation, rotation, and revocation are automatic.

The dashboard uses a third auth mechanism (OpenShift OAuth proxy for SSO), but this sits outside the PH system boundary -- it is standard OpenShift infrastructure.

---

## Deployment

Publishing House Central runs on OpenShift, managed entirely by Ansible. No manual `oc edit`, no ad-hoc kubectl -- all infrastructure state flows through the playbook.

### Topology

Central and RCARS run in separate namespaces on the same OpenShift cluster. RCARS is accessed via Kubernetes service DNS for cross-namespace communication.

### Ansible Deployer

All deployments use `ansible-playbook ansible/deploy.yml -e env=dev --tags <tag>` from the `rhdp-publishing-house-central` repo.

| Tag | What It Does |
|---|---|
| `deploy` | Full deploy: namespace, infra + app manifests, builds, migrations, rollout wait |
| `build-backend` | Build backend image, wait for build + rollout |
| `build-frontend` | Build frontend image, wait for build |
| `builds` | Build both backend and frontend |
| `apply` | Apply Kubernetes manifests only (config changes, secrets, env vars -- no builds) |
| `migrate` | Run Alembic migrations on the current pod |

**Migration ordering:** Migrations execute on the running backend pod, so the pod must have the new code before migrations run. When deploying changes that include schema modifications, run `--tags build-backend` before `--tags migrate`, or use `--tags deploy` which handles the ordering automatically.
