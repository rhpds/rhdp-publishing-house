# Dashboard Redesign for Publishing House Central

**Date:** 2026-06-19
**Status:** Design approved
**Depends on:** PH Central backend (deployed on `feature/ph-central-registration` branch)

## Problem

The dashboard was built for the portal model — it reads from the `Manifest` model populated by `ph_sync_manifest` MCP pushes from the client. With PH Central, manifests are read from git by the backend, not pushed via MCP. The dashboard shows empty project cards because nothing populates the old model.

The frontend needs to be rewritten to use Central's data model: `Project`, `GateRecord`, `SubmittedResult`, and `PhaseEngine`. The backend services are already built — they just need REST endpoints to expose them to the frontend.

## Scope

- Rewrite REST endpoints in place (no backward compatibility — no other consumers exist)
- New TypeScript types matching Central's data model
- Pipeline board redesign with merged kanban columns
- Project detail page with gate history inline
- Register page with branch field
- Naming update to "Publishing House Central"

## Stack

- **Frontend:** Next.js 15 + PatternFly 6 (unchanged)
- **Styling:** PatternFly dark theme with LCARS color palette (`--bg-primary: #0f1117`, `--lcars-amber: #FF9900`, `--accent-blue: #73bcf7`) for visual alignment with RCARS. PatternFly stays as the component library (Red Hat standard), LCARS theming applied via CSS variables (existing `lcars-theme.css`).
- **Backend:** FastAPI REST endpoints wrapping existing Central services

---

## Data Architecture

### REST Endpoints (Rewrite in Place)

The old `/api/v1/projects` endpoints are rewritten to use Central services. No new path prefix — the old code is replaced.

| Endpoint | Wraps | Returns |
|---|---|---|
| `GET /api/v1/projects` | `Project` DB query | List of projects with cached phase status |
| `POST /api/v1/projects` | `GitRepoReader` + `_register_project()` | Newly registered project |
| `GET /api/v1/projects/{id}` | `Project` + cached status | Single project with full metadata |
| `GET /api/v1/projects/{id}/status` | `GitRepoReader` + `PhaseEngine` (live) | Live phase_statuses, current_phase, next_action |
| `GET /api/v1/projects/{id}/gates` | `GateService.get_history()` | GateRecord list |
| `POST /api/v1/projects/{id}/refresh` | `GitRepoReader` + cache update | Refreshed project with updated status |
| `DELETE /api/v1/projects/{id}` | DB delete | 204 |

Retained endpoints (updated for new data model):
- `GET /api/v1/projects/{id}/worklog` — worklog entries from git
- `GET /api/v1/projects/{id}/launch` — launch/ordering instructions from manifest

### Registration Flow

`POST /api/v1/projects` accepts `{ repo_url, branch }` where branch defaults to `"main"`. The endpoint:

1. Calls `GitRepoReader.fetch_manifest(owner, repo, branch)` to validate the repo has a PH manifest
2. Calls the same `_register_project()` logic used by the `ph_register` MCP tool
3. Runs an initial status computation and caches it
4. Returns the project record

This ensures the REST registration and MCP registration use identical logic.

### Phase Status Caching

The periodic sync job (APScheduler, already exists) fetches manifests from git for all registered projects and stores computed phase statuses in the `Project` record. Fields added to the project model:

- `cached_phase_statuses` (JSONB) — dict of phase name → status string
- `cached_current_phase` (String) — current phase name
- `cached_next_action` (JSONB) — PhaseEngine next action result
- `cached_at` (DateTime) — when the cache was last updated

The pipeline board reads from cache (single DB query, renders instantly). The project detail page shows cached data by default with a "Refresh" button that calls `GET /api/v1/projects/{id}/status` for a live fetch from git, which also updates the cache.

### Manifest Data Caching

The Artifacts tab and Launch tab depend on manifest content (phase metadata with artifact paths, deployment mode, integration repos). The periodic sync caches the full parsed manifest as a JSONB field on the project record:

- `cached_manifest_data` (JSONB) — full parsed manifest dict from git

This replaces the old `Manifest` model. The `Manifest` and `Phase` DB models are no longer needed — the project record holds everything. Artifacts are extracted from `cached_manifest_data.lifecycle.phases[*].metadata.artifacts`. Launch instructions are derived from `cached_manifest_data.project` and `cached_manifest_data.integrations`.

### TypeScript Types

```typescript
interface CentralProject {
  id: string;
  name: string;
  repo_url: string;
  branch: string;
  owner_github: string | null;
  owner_email: string | null;
  deployment_mode: string | null;
  registered_at: string;
  last_synced_at: string | null;
  cached_phase_statuses: Record<string, string> | null;
  cached_current_phase: string | null;
  cached_next_action: { next_phase: string | null; action: string; detail: string } | null;
  cached_manifest_data: Record<string, unknown> | null;
  cached_at: string | null;
}

interface GateRecord {
  gate_id: string;
  phase: string;
  result: "approved" | "rejected" | "overridden";
  reason: string;
  findings: Record<string, unknown> | null;
  requested_by: string | null;
  approved_by: string | null;
  is_self_approval: boolean;
  override: boolean;
  spec_commit: string | null;
  created_at: string;
}

interface ProjectStatus {
  current_phase: string;
  phase_statuses: Record<string, string>;
  next_action: { next_phase: string | null; action: string; detail: string };
  deployment_mode: string;
}

interface ProjectCreate {
  repo_url: string;
  branch?: string;  // defaults to "main"
}
```

---

## Pipeline Board

### Column Structure

Six columns, defined as a data-driven config array. Adding a phase or column means adding an entry to the config — no component changes.

```typescript
const PIPELINE_COLUMNS = [
  { id: "intake", label: "Intake", phases: ["intake"], style: "standard" },
  { id: "vetting", label: "Vetting / Spec", phases: ["vetting", "spec_refinement"], style: "iterative" },
  { id: "approval", label: "Approval", phases: ["approval"], style: "standard" },
  { id: "development", label: "Writing + Automation", phases: ["writing", "automation"], style: "parallel" },
  { id: "review", label: "Review", phases: ["editing", "code_security_review"], style: "standard" },
  { id: "ready", label: "Ready", phases: ["final_review", "ready_for_publishing"], style: "standard" },
] as const;
```

### Column Styles

The column renderer picks visual treatment from the `style` field:

- **`standard`** — plain column, cards show name + owner + deployment mode badge
- **`iterative`** — column header shows "ITERATIVE" badge. Cards show iteration count (number of gate records for the vetting phase). If the latest vetting gate was rejected, the card shows the rejection reason snippet (e.g., "high overlap with X").
- **`parallel`** — column header shows "PARALLEL" badge. Cards show dual progress indicators for writing and automation phases (e.g., "Writing: in_progress / Automation: pending").

### Column Placement Logic

For each project, read `cached_phase_statuses`. Find the rightmost column that has any phase with status `in_progress`. If none are in progress, find the rightmost column with a `completed` phase. Default to "intake" if all phases are pending.

### Empty State

When no projects exist, show an empty state with a "Register Project" button linking to `/register`.

---

## Project Detail Page

### Header

Project name as the page title. Below: deployment mode badge, owner, branch (shown because branch is part of project identity). Kebab menu with "Refresh from GitHub" and "Delete project" actions. "Last synced: [timestamp]" shown next to the kebab.

### Tabs

Four tabs:

#### Overview

- **Phase progress bar** — horizontal bar showing all phases for this project's deployment mode profile. Each phase shows its status (pending/in_progress/completed). The current phase is highlighted.
- **Phase drill-down** — clicking a phase in the progress bar expands an accordion showing:
  - Phase status and gate type (hard/soft)
  - Latest gate record for this phase (result, reason, who requested, timestamp)
  - Artifacts associated with this phase (links to GitHub)
  - If the gate was rejected: rejection reason and findings summary
  - If the gate was overridden: override flag visible
- **Sidebar cards:**
  - Project Info: name, owner, deployment mode, branch, registered date
  - Links: GitHub repo, Showroom repo (if set), Automation repo (if set)

#### Worklog

Session handoff timeline. Same as current implementation — worklog entries parsed from the git repo's worklog file, displayed in reverse chronological order.

#### Artifacts

All artifacts grouped by phase with GitHub links. Existing `ArtifactsList` component pattern preserved — artifacts extracted from manifest phase metadata, classified by type (document, content, automation, review), rendered as clickable links to the file in the GitHub repo. Summary badges at the top show counts by type.

Data source changes: artifacts are read from the cached manifest data (populated during sync) rather than from the old `Phase.metadata_` model. The extraction logic (classify by path, build GitHub URLs) stays the same.

#### Launch

Ordering/deployment instructions derived from the manifest. Step-by-step guide with copyable values. Shows deployment mode, repo links, and numbered action steps. Existing `LaunchInstructions` component preserved. Future: will evolve toward click-to-order when Babylon ordering automation is available.

---

## Register Page

Single-purpose registration form:

- **Repository URL** field (required) — SSH or HTTPS format
- **Branch** field (optional, defaults to `main`) — visible text input, not hidden behind "Advanced"
- **Submit** button — calls `POST /api/v1/projects` with `{ repo_url, branch }`
- Success: show confirmation, redirect to project detail page after 2 seconds
- Error handling: 400 (no manifest), 409 (already registered), generic errors

No project list on this page. The `/projects` page serves that purpose.

---

## Navigation and Naming

### Masthead

- Title: "Publishing House Central"
- No subtitle
- Logo: existing `logo-full.svg`

### Sidebar Nav

```
Pipeline        → /pipeline
Projects        → /projects
Register        → /register

Tools
  RCARS Advisor → external link (existing)
```

Same structure as current. Only the masthead text changes.

---

## What Gets Dropped

| Item | Reason |
|---|---|
| `Manifest` model as data source | Replaced by `GitRepoReader` + cached status on `Project` |
| `Phase` DB model for kanban placement | Replaced by `cached_phase_statuses` on project record |
| Old `refresh_project_service` flow | Replaced by periodic sync + `GitRepoReader` |
| `manifest_raw` and `project_data` on project response | Replaced by cached phase status fields |
| Old `KANBAN_COLUMNS` with 8 columns | Replaced by 6-column `PIPELINE_COLUMNS` config |

## What Stays

| Item | Notes |
|---|---|
| PatternFly 6 components | Red Hat standard, future integration friendly |
| LCARS dark theme CSS | Visual alignment with RCARS |
| Next.js 15 | No reason to switch frameworks |
| `ArtifactsList` component pattern | Updated to read from new data source |
| `LaunchInstructions` component | Kept for future ordering automation |
| `WorklogTimeline` component | Updated to read from new data source |
| Worklog and Launch REST endpoints | Updated for new data model |
| APScheduler periodic sync | Extended to cache phase statuses |

---

## Backend Changes Required

### New Fields on `Project` Model

Add to existing `Project` model (via Alembic migration):

- `cached_phase_statuses` — JSONB, nullable
- `cached_current_phase` — String(50), nullable
- `cached_next_action` — JSONB, nullable
- `cached_manifest_data` — JSONB, nullable (full parsed manifest for artifacts/launch)
- `cached_at` — DateTime(timezone=True), nullable

The `Manifest` and `Phase` models are no longer used by the frontend. They can be dropped or left in place — the frontend reads exclusively from the cached fields on `Project`.

### Rewritten `app/api/projects.py`

The projects router is rewritten to:
- List/get projects from `Project` with cached status
- Register via `GitRepoReader` + `_register_project()` (same logic as MCP `ph_register`)
- Add `/status` endpoint for live fetch
- Add `/gates` endpoint wrapping `GateService.get_history()`
- Keep worklog and launch endpoints, updated for new data model

### Updated Periodic Sync (`app/services/refresh.py`)

Extended to:
1. Fetch manifest from git via `GitRepoReader` for each registered project
2. Run `PhaseEngine.get_next_action()` on the manifest
3. Store computed `cached_phase_statuses`, `cached_current_phase`, `cached_next_action`, `cached_at` on the project record

### Pydantic Schemas

New response schemas matching the TypeScript types above. Replace old `ProjectWithPhases` schema with `CentralProjectResponse` that includes cached status fields instead of a phases array.

---

## Implementation Sequence

1. **Backend: DB migration + model update** — add cached status fields to Project
2. **Backend: Rewrite projects API** — new endpoints using Central services
3. **Backend: Update periodic sync** — cache phase statuses during sync
4. **Frontend: Types + API client** — new TypeScript types and API service functions
5. **Frontend: Pipeline board** — 6-column kanban with data-driven config
6. **Frontend: Project detail** — phase progress bar, gate drill-down, updated artifacts/worklog/launch
7. **Frontend: Register page** — add branch field
8. **Frontend: Naming** — masthead and any remaining references
