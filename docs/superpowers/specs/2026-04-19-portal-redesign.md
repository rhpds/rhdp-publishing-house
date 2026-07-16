# Publishing House Portal Redesign

**Date:** 2026-04-19
**Status:** Draft
**Author:** Nate Stephany + Claude

## Summary

Evolve the Publishing House dashboard into a portal that serves three audiences: managers tracking multiple projects, developers checking status and artifacts, and end users who need launch/ordering instructions. Add an MCP server as a gateway to external systems and validation result storage. Enhance skills to read project state locally instead of via MCP, keeping token usage focused on creative and coding work rather than status queries.

## Goals

1. **Reduce token waste** — Status checks, worklog reads, and manifest parsing happen locally via skill or via cheap MCP lookups, not by loading heavy orchestrator prompts.
2. **Stakeholder visibility** — Managers see all projects in a pipeline kanban, drill into phase detail, view worklogs and artifacts.
3. **Developer quick access** — Developers check status and find spec files in the portal without Claude Code. Git links to all artifacts.
4. **End user launch path** — Completed or in-progress projects show ordering instructions ("how do I run this?").
5. **External system gateway** — MCP server bridges Claude Code to RCARS, Babylon, validation storage, and cross-project queries without each user's session calling those systems directly.
6. **API-first** — Backend API documented via Swagger UI (FastAPI auto-generated OpenAPI), exposable externally later.
7. **Scale** — Architecture must handle 100+ registered projects (event scale: 50+ active projects plus BAU work).

## Non-Goals (This Iteration)

- RCARS integration beyond a nav link and shared visual theme
- RCARS vetting API endpoint (designed for in architecture, not built)
- Direct CI ordering from the portal (Babylon integration)
- Auto-registration of projects from Claude Code
- Recommendation engine changes
- Self-service deployment skill workflow (intake question for onboarded vs self_service, catalog_item substep skip logic, GitOps repo generation targeting the generic CI — handled separately in skill design)

## Architecture

### System Overview

```
Developer (Claude Code)          Manager (Browser)         End User (Browser)
       │                              │                          │
       │ skill reads local files      │ portal UI                │ portal UI
       │ (manifest, worklog, specs)   │                          │
       │                              ▼                          ▼
       │                     ┌─────────────────┐
       │ MCP                 │  Portal Backend  │
       ├────────────────────►│  (FastAPI)       │
       │ cross-project,      │                  │
       │ launch instructions,│  - REST API      │
       │ validation storage, │  - MCP endpoint  │
       │ future: vetting     │  - Refresh engine │
       │                     │  - Swagger UI     │
       │                     └────────┬─────────┘
       │                              │
       │                     ┌────────▼─────────┐
       │                     │   PostgreSQL      │
       │                     │   (cache of git   │
       │                     │    + validation   │
       │                     │      results)     │
       │                     └────────┬─────────┘
       │                              │
       │                     ┌────────▼─────────┐
       │                     │  GitHub API       │
       │                     │  (source of truth)│
       │                     └──────────────────┘
```

### Key Principle

**Git is the source of truth for project state.** The portal DB is a cache of git data (manifest, worklog) plus operational data that doesn't belong in git (validation results). If the portal goes down, developers read files from their local clone and everything still works — they just lose cross-project views, validation history, and launch instructions until it comes back.

### Components

#### 1. Portal UI (Next.js + PatternFly 6)

**Layout:** Sidebar navigation (PatternFly vertical nav) with breadcrumb trail at the top of the content area.

**Visual theme:** Star Trek LCARS-inspired dark theme, consistent with RCARS. PatternFly 6 components styled with LCARS color palette (angular panels, color bands, distinctive typography). Both apps should feel like they belong to the same platform.

**Sidebar nav items:**
- Pipeline (kanban view)
- Projects (table/list view)
- Tools section: RCARS Advisor (external link, same visual theme)

**Pages:**

| Page | Path | Purpose |
|------|------|---------|
| Pipeline | `/pipeline` | Kanban board — projects grouped by active phase |
| Projects | `/projects` | Searchable project table with progress bars |
| Project Detail | `/projects/[id]` | Tabbed view (see below) |
| Register | `/register` | Single field: GitHub repo URL |

**Project Detail Tabs:**

| Tab | Content |
|-----|---------|
| Overview | Phase accordion (expandable, shows assignees, dates, artifacts per phase). Active phase auto-expanded. Progress bar at top. Validation results shown inline per phase when available. |
| Worklog | Timeline of worklog entries from `worklog.yaml`. Shows open/resolved status, author, timestamp. Not a task tracker — captures human context, decisions, handoffs. |
| Artifacts | Aggregated list of all artifacts across all phases — design docs, module outlines, automation manifests, lab guides, review docs. Links to GitHub. Duplicates phase-level artifact links for convenience. |
| Launch | Ordering instructions based on `deployment_mode`. For `onboarded`: link to the project's catalog item in RHDP. For `self_service`: link to generic CI + parameters (automation repo URL, Showroom repo URL, Helm values, revision, path). |

**Registration flow:**
1. User provides GitHub repo URL (single field)
2. Backend fetches `publishing-house/manifest.yaml` from the repo
3. Project name, owner, type, deployment mode — all pulled from manifest
4. Project created in DB with parsed manifest + phases + worklog

#### 2. Portal Backend (FastAPI)

**REST API** consumed by the frontend and available as MCP. All endpoints documented via Swagger UI at `/docs`.

**Project endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/projects` | Register project (repo URL only, manifest is source of truth) |
| GET | `/api/v1/projects` | List all projects with summary status |
| GET | `/api/v1/projects/{id}` | Full project detail (manifest + phases + worklog) |
| POST | `/api/v1/projects/{id}/refresh` | Trigger immediate refresh from GitHub |
| DELETE | `/api/v1/projects/{id}` | Remove project from portal |
| GET | `/api/v1/projects/{id}/launch` | Launch/ordering instructions |

**Validation endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/projects/{id}/validations` | Store validation run results (from skill via MCP) |
| GET | `/api/v1/projects/{id}/validations` | List validation runs for a project |
| GET | `/api/v1/projects/{id}/validations/{run_id}` | Detailed results for a specific run |

**Cross-project endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/pipeline` | All projects grouped by kanban column |
| GET | `/api/v1/projects?status={phase_status}` | Filter projects by phase status |

**Health/docs:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health` | Health check |
| GET | `/docs` | Swagger UI (auto-generated) |
| GET | `/redoc` | ReDoc (auto-generated) |

**Pydantic schemas:** Strictly typed request/response models. OpenAPI spec is auto-generated and accurate. No untyped dict returns.

#### 3. MCP Server

**Focused on cross-project access, external system gateway, and storing operational data that doesn't belong in git.** Not for single-project developer workflows — developers read local files via skills.

**Initial MCP tools:**

| Tool | Description |
|------|-------------|
| `ph_list_projects` | Cross-project status summary (for managers using Claude Code) |
| `ph_get_launch_instructions` | Step-by-step ordering instructions for a project |
| `ph_store_validation_results` | Store AgnosticV validator or Showroom verify-content results |
| `ph_get_validation_results` | Retrieve latest validation results for a project/phase |

**Designed for (future):**

| Tool | Description |
|------|-------------|
| `ph_request_vetting` | Call RCARS API, return duplicate/overlap analysis |
| `ph_order_ci` | Trigger Babylon CI order |
| `ph_cross_project_query` | "Which projects are stuck in automation?" type queries |

**Auth:** Keycloak JWT validation following the `rhpds/demo-reporting` reporting-mcp pattern. `MCP_AUTH_ENABLED=false` for local dev, JWT validation in production. User identity from token claims.

**Transport:** Streamable HTTP (`/mcp` endpoint on the same FastAPI app). Can also run as stdio for local dev.

#### 4. Refresh Engine

Reads `manifest.yaml` and `worklog.yaml` from each registered project's GitHub repo, parses, and caches in PostgreSQL.

**Schedule:** Every 30 minutes by default. On-demand via portal UI button and via MCP trigger.

**Scale considerations (100+ projects):**
- Parallel GitHub API calls (async, bounded concurrency to respect rate limits)
- Incremental refresh: check repo last-push timestamp via GitHub API before fetching full manifest. Skip repos with no changes since last refresh.
- Stagger refreshes to avoid GitHub API rate limit spikes
- Individual project refresh on-demand (don't refresh all 100+ when one project is updated)
- DB indexes on common query paths (project status, phase status, deployment mode)

**Refresh flow:**
1. Check repo last-push timestamp (GitHub API, lightweight)
2. If unchanged since last refresh → skip
3. Fetch `publishing-house/manifest.yaml` from GitHub API
4. Fetch `publishing-house/worklog.yaml` from GitHub API (if exists)
5. Parse manifest → extract phases, substeps, metadata, artifacts
6. Parse worklog → extract entries with status, author, timestamp
7. Upsert into DB (replace manifest/phases/worklog, preserve project record)
8. Record refresh timestamp and status

#### 5. Worklog

**Location:** `publishing-house/worklog.yaml` in the project repo (git).

**Format:**

```yaml
# Publishing House Worklog
# Human context, decisions, and notes that bridge sessions and people.
# Not a task tracker — the manifest tracks structured progress.

entries:
  - id: "2026-04-15-001"
    timestamp: "2026-04-15T14:30:00Z"
    author: "sborenst"
    status: open          # open | resolved
    type: decision        # note | decision | handoff | action
    content: "Need to decide on DataSphere vs Parksmap for module 2 demo app. DataSphere is newer but Parksmap has more community examples."

  - id: "2026-04-14-001"
    timestamp: "2026-04-14T10:00:00Z"
    author: "sborenst"
    status: resolved
    type: action
    content: "Check with Prakhar on CNV pool sizing for multi-user deployments."
    resolved_at: "2026-04-15T09:00:00Z"
    resolved_by: "sborenst"

  # Squashed summary (old entries compressed by skill)
  - id: "summary-2026-04-10"
    timestamp: "2026-04-10T00:00:00Z"
    author: "system"
    status: resolved
    type: summary
    content: "April 10: Project created. Intake completed — 5-module workshop design approved. Spec refinement normalized design doc from Parksmap v1 to DataSphere. Automation catalog and requirements completed."
```

**Skill responsibilities:**
- Read `worklog.yaml` at session start to understand human context
- Write new entries (LLM-assisted: expand terse notes into readable entries)
- Summarize session work as a worklog entry at session end
- Periodically squash old resolved entries into summary entries to keep file size bounded
- Commit and push worklog changes to git

**Portal responsibilities:**
- Read worklog from DB cache (populated by refresh engine)
- Display timeline on Worklog tab (open items highlighted, resolved items available)
- Show badge count of open items on the tab

**Post-implementation review flag:** Revisit worklog UX and storage model after initial user feedback. The "structured YAML in git, DB caches, skill handles intelligence" model may need adjustment based on how people actually use it.

#### 6. Validation Results

**Problem:** Skills like `agnosticv:validator` and `showroom:verify-content` produce structured output (pass/fail, findings, recommendations). This data is operational — timestamped snapshots of validation runs — not project source-of-truth state. Storing it in git creates noise; it belongs in the DB.

**Flow:**
1. Developer runs validation skill locally (e.g., `agnosticv:validator` or `showroom:verify-content`)
2. Skill produces structured results (pass/fail, findings list, severity, recommendations)
3. Skill calls MCP tool `ph_store_validation_results` to post results to the portal DB
4. Portal displays results on the Overview tab, inline under the relevant phase
5. Portal could also run validations itself (future — portal-triggered validation)

**Data model:**

```sql
CREATE TABLE validation_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    phase VARCHAR(50) NOT NULL,          -- which phase this validates
    validator VARCHAR(100) NOT NULL,     -- 'agnosticv:validator', 'showroom:verify-content'
    status VARCHAR(20) NOT NULL,         -- pass, fail, warning
    run_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    run_by VARCHAR(100),                 -- who triggered it
    summary TEXT,                        -- one-line result summary
    findings JSONB,                      -- structured findings array
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_validation_project_phase ON validation_runs(project_id, phase);
CREATE INDEX idx_validation_run_at ON validation_runs(run_at DESC);
```

**Findings JSONB structure:**

```json
[
  {
    "severity": "error",
    "message": "common.yaml missing asset_uuid",
    "file": "agd_v2/my-lab/common.yaml",
    "line": null
  },
  {
    "severity": "warning",
    "message": "No description.adoc found",
    "file": null,
    "line": null
  }
]
```

**Portal display:** On the Overview tab, under each phase, show the latest validation result if one exists — a small badge (pass/fail/warning) with a link to expand full findings. Validation history available on click.

**Note:** This is one of the stronger justifications for the MCP server. Validation results don't belong in git, but they need to be accessible to both the portal UI and future Claude Code sessions. The MCP bridges that gap.

## Database Schema Changes

Current schema: `projects`, `manifests`, `phases`.

**Add:**

```sql
-- Worklog entries (cached from git)
CREATE TABLE worklog_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    entry_id VARCHAR(100) NOT NULL,     -- from worklog.yaml
    timestamp TIMESTAMPTZ NOT NULL,
    author VARCHAR(100),
    status VARCHAR(20) NOT NULL,        -- open, resolved
    type VARCHAR(20),                   -- note, decision, handoff, action, summary
    content TEXT NOT NULL,
    resolved_at TIMESTAMPTZ,
    resolved_by VARCHAR(100),
    UNIQUE (project_id, entry_id)
);

CREATE INDEX idx_worklog_project_status ON worklog_entries(project_id, status);

-- Validation results (operational data, not cached from git)
CREATE TABLE validation_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    phase VARCHAR(50) NOT NULL,
    validator VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,
    run_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    run_by VARCHAR(100),
    summary TEXT,
    findings JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_validation_project_phase ON validation_runs(project_id, phase);
CREATE INDEX idx_validation_run_at ON validation_runs(run_at DESC);
```

**Modify `projects` table:**
- Remove `name` from registration input (read from manifest)
- Add `deployment_mode` (cached from manifest for filtering)
- Add `owner_github` (cached from manifest for display)

## Registration Flow Changes

**Current:** User provides name + repo URL.
**New:** User provides repo URL only.

1. Validate URL format (GitHub SSH or HTTPS)
2. Fetch `publishing-house/manifest.yaml` from GitHub API
3. Parse manifest — extract `project.name`, `project.owner_github`, `project.type`, `project.deployment_mode`
4. If manifest is missing or unparseable → error: "This repo doesn't have a Publishing House manifest."
5. Check for duplicate `repo_url` → 409 Conflict
6. Create project in DB with manifest-derived fields
7. Fetch and parse `worklog.yaml` if it exists
8. Return created project

## Auth

### Portal UI
OpenShift OAuth proxy sidecar (already implemented). No changes needed.

### MCP Server
Keycloak JWT validation following the `rhpds/demo-reporting` reporting-mcp pattern:
- `KeycloakTokenVerifier` validates JWT signature + issuer via JWKS endpoint
- Keys cached locally, no per-request roundtrip
- `MCP_AUTH_ENABLED=false` for local development
- User identity extracted from JWT claims for attribution
- Uses the MCP SDK's built-in `TokenVerifier` protocol

### Auth investigation needed
The Keycloak/SSO infrastructure details need to be understood before implementation. Specifically: which Keycloak realm, how Claude Code obtains a token, and whether the reporting-mcp's Keycloak instance is the same one we'd use. This is a prerequisite for MCP auth but not a blocker for the portal UI work.

## RCARS Relationship

**This iteration:** RCARS is a separate application with a nav link from the PH portal sidebar. Both use the LCARS-inspired dark theme for visual consistency — same color palette, angular panel styling, typography.

**Future iterations:**
- MCP tool `ph_request_vetting` calls RCARS API to check for content duplicates/overlaps
- Portal could embed RCARS advisor results in the vetting phase detail
- RCARS could link back to PH portal for items it knows are PH-managed
- Shared catalog data (RCARS already knows about all CIs; PH portal knows about PH-managed projects)

**Architecture consideration:** RCARS and the PH portal share the same deployment cluster (ocpv-infra01). Internal service-to-service calls are feasible when the vetting API is built.

## Token Efficiency Strategy

The primary token savings come from **skill design**, not MCP calls.

| Operation | Current (token-heavy) | New (token-efficient) |
|-----------|----------------------|----------------------|
| "What's my status?" | Load orchestrator skill (~400 lines) + read manifest | Skill reads `manifest.yaml` directly, parses YAML, formats response |
| "What's outstanding?" | Load orchestrator + read manifest + reason about phases | Skill reads `worklog.yaml`, filters open entries, presents list |
| "What should I work on?" | Load orchestrator + full phase analysis | Skill reads manifest, checks phase statuses, returns next pending |
| "How do I order this?" | N/A (not supported) | MCP call to `ph_get_launch_instructions` or skill reads manifest `integrations` |
| "Which projects are stuck?" | Not possible from single repo | MCP call to `ph_list_projects` with status filter |
| "Did validation pass?" | Re-run validation or check logs | MCP call to `ph_get_validation_results` |

**Skill changes needed:**
- Orchestrator skill becomes lighter — for status/worklog queries, it reads local files directly without loading reference docs
- Worklog management (read, write, squash) is a skill concern, not MCP
- Validation skills post results to portal via MCP after running locally
- Heavy skill loading reserved for creative work (writing, automation, editing)

## Migration from Current Dashboard

The current dashboard has: project registration, kanban pipeline, project table, project detail with phase accordion.

**What stays:** Phase accordion component, kanban view logic, manifest parser, GitHub client, refresh engine core.

**What changes:**
- Registration: remove name field, pull everything from manifest
- Layout: add sidebar nav, breadcrumbs, tabbed project detail
- New tabs: Worklog, Artifacts, Launch
- Refresh engine: add `worklog.yaml` parsing, increase frequency to 30 min, add incremental refresh
- API: add Swagger UI, type all responses with Pydantic schemas
- Backend: add MCP endpoint (initial tools: list projects, launch instructions, validation storage)
- Theme: LCARS-inspired dark palette, consistent with RCARS

**What's new:**
- Worklog table in DB + display
- Validation runs table in DB + display
- Artifacts aggregation tab
- Launch instructions tab and endpoint
- MCP server (streamable HTTP on `/mcp`)
- Keycloak auth for MCP (investigation needed first)
- Incremental refresh for 100+ project scale
