# Publishing House Dashboard — Design Spec

**Date:** 2026-04-12
**Status:** Draft
**Scope:** Standalone POC — cross-project visibility dashboard for Publishing House content lifecycle

## Problem

Publishing House works well for individual or paired content creation via CLI skills, but managers and PMs have no way to see status across multiple projects. Each project's state lives in its own `manifest.yaml` inside its own repo. There is no central view.

## Solution

A standalone web dashboard that provides cross-project visibility into the Publishing House content lifecycle. Projects register once via the UI, and the dashboard pulls manifest state from GitHub on a scheduled and on-demand basis.

## Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Hosting | Standalone POC | Move fast, prove the concept, integrate later (RCARS or Labagator) |
| Stack | FastAPI + Next.js + PatternFly 6 | Matches Labagator stack; PatternFly is Red Hat standard; keeps integration path open |
| Database | PostgreSQL | Consistent with RCARS and Labagator; production-ready from the start |
| Registration | Manual via UI | Simpler than API key management; SSO handles auth; low-frequency operation. API registration may be added later. |
| Manifest access | GitHub API | Lightweight, no cloning. Cached locally with nightly refresh + manual per-project refresh. |
| Auth (production) | OpenShift OAuth proxy / SSO | Same pattern as Labagator and other RHDP tools |
| Auth (local dev) | Bypass or simple mock | Local-first development workflow before OpenShift deployment |

## Architecture

```
┌─────────────────────┐       ┌──────────────────────┐
│  Next.js Frontend   │──────▶│   FastAPI Backend     │
│  (PatternFly 6)     │  API  │                       │
│                     │       │  - Project CRUD       │
│  - Pipeline (kanban)│       │  - Manifest caching   │
│  - Projects (table) │       │  - Refresh scheduler  │
│  - Project detail   │       │  - GitHub API client   │
│  - Register form    │       │                       │
└─────────────────────┘       └──────────┬────────────┘
                                         │
                              ┌──────────▼────────────┐
                              │     PostgreSQL         │
                              │  - projects            │
                              │  - manifests           │
                              │  - phases              │
                              └────────────────────────┘
                                         ▲
                                    Nightly job +
                                    on-demand refresh
                                         │
                              ┌──────────┴────────────┐
                              │   GitHub Repos         │
                              │  publishing-house/     │
                              │    manifest.yaml       │
                              └────────────────────────┘
```

### Data Flow

1. User logs into dashboard, navigates to Register page, enters repo URL and project name.
2. Backend validates the repo URL, fetches `publishing-house/manifest.yaml` via GitHub API, parses it, and stores structured data in PostgreSQL.
3. Nightly scheduled job refreshes all registered projects by re-fetching their manifests.
4. Users can trigger a per-project "Refresh Now" from the table or detail view.
5. Frontend reads from PostgreSQL cache — never hits GitHub directly.

## Data Model

### `projects` table

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `name` | VARCHAR | Display name (provided at registration) |
| `repo_url` | VARCHAR | GitHub repo URL (unique) |
| `registered_at` | TIMESTAMP | When the project was registered |
| `last_refreshed_at` | TIMESTAMP | When manifest was last fetched |
| `refresh_status` | VARCHAR | `success` / `error` / `pending` |
| `refresh_error` | TEXT | Error message if last refresh failed (nullable) |

### `manifests` table

Stores the latest manifest snapshot per project. Overwritten on each refresh (no history for the POC).

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `project_id` | UUID | FK → projects (unique — one row per project) |
| `raw_yaml` | TEXT | Raw manifest content (for display/debugging) |
| `parsed_data` | JSONB | Parsed manifest as structured JSON |
| `fetched_at` | TIMESTAMP | When this snapshot was fetched |

### `phases` table

Denormalized from manifest for fast dashboard queries. Rebuilt on each refresh.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `project_id` | UUID | FK → projects |
| `phase_name` | VARCHAR | Phase identifier (see Phase Definitions below) |
| `status` | VARCHAR | Phase-level status (see Status Definitions below) |
| `assignees` | JSONB | List of people assigned to this phase |
| `metadata` | JSONB | Phase-specific data (modules list, substeps, approval info, etc.) |

## Status Definitions

Statuses must be clearly defined so the dashboard, the manifest, and the skills all agree on what each means.

### Phase-Level Statuses

These apply to each lifecycle phase (intake, approval, content, automation, etc.):

| Status | Meaning |
|--------|---------|
| `pending` | Phase has not started. Prerequisites may or may not be met. |
| `in_progress` | Phase is actively being worked on. |
| `completed` | Phase is done. All deliverables for this phase are finished. |
| `skipped` | Phase was intentionally skipped (e.g., automation not needed). |

### Module-Level Statuses (Content Phase)

These apply to individual modules within the writing/editing workflow:

| Status | Meaning |
|--------|---------|
| `pending` | Module has not been started. |
| `in_progress` | Module is actively being written or edited. |
| `drafted` | Initial draft is complete. Content exists but has not been through editing. |
| `approved` | Module has passed editing review and is considered final. |

### Automation Substep Statuses

These apply to the five substeps within the automation phase:

| Status | Meaning |
|--------|---------|
| `pending` | Substep has not started. |
| `in_progress` | Substep is actively being worked on. |
| `completed` | Substep is done. |
| `deferred` | Substep is planned but deferred to a later date (e.g., e2e_checks). |

## Lifecycle Phases

### Dashboard Columns (Kanban)

The kanban board groups manifest phases into 7 columns:

| Kanban Column | Manifest Phases Rolled Up | Color |
|---------------|---------------------------|-------|
| **Intake** | `intake`, `vetting`, `spec_refinement` | Blue |
| **Approval** | `approval` | Yellow |
| **Content** | `writing`, `editing` | Green |
| **Automation** | `automation` (5 substeps) | Red |
| **Code & Security Review** | `code_security_review` (rename from `security_review`) | Purple |
| **Final Review** | `final_review` | Violet |
| **Ready** | `ready_for_publishing` | Teal |

Cards in grouped columns show a sub-phase label (e.g., `↳ vetting` within Intake) so the specific position is visible.

### Phase Dependencies

```
Intake → Approval → [Content + Automation] → Code & Security Review → Final Review → Ready
                     (can be concurrent)      (both must complete)
```

- **Content** cannot start until **Approval** is completed.
- **Content** and **Automation** can be active concurrently. This is the only concurrent pair.
- Small fixes to content during automation do not reopen the Content phase.
- **Code & Security Review** cannot start until both **Content** and **Automation** are completed. This phase covers code review (primarily for automation) and security review (for both content and automation).
- **Final Review** cannot start until **Code & Security Review** is completed.
- **Ready for Publishing** is set when **Final Review** is completed.

### Concurrent Content + Automation

In practice, content creation and automation iterate together. A module may be written, then automation attempted, revealing that instructions need adjustment. The dashboard handles this by:

- Allowing both Content and Automation phases to have `status: in_progress` simultaneously.
- On the kanban, showing the card in the further-along phase (Automation) with a visual indicator that Content is also active.
- On the table, showing both phase segments glowing in the progress bar.
- On the detail view, expanding both phase accordions.

The manifest supports this because each phase has an independent `status` field. The dashboard derives kanban position from the set of active phases rather than a single `current_phase` field.

**Manifest evolution note:** The existing `lifecycle.current_phase` field should be deprecated in favor of reading individual phase statuses. The dashboard ignores `current_phase` and derives state from the phase-level `status` fields.

## Frontend Views

### 1. Pipeline View (Kanban)

- 7 columns, one per kanban phase group.
- Project cards show: name (clickable → detail), module count, assignee(s), sub-phase label, status flag (when noteworthy).
- Column headers show phase name and project count.
- Phase colors are consistent across all views.

### 2. Projects View (Table)

- Sortable, filterable table of all registered projects.
- Columns: Project name (clickable → detail), Type, Modules, Assignees, Phase Progress (7-segment bar), Refresh button.
- Phase progress bar: filled + colored = completed, glowing outline = active, dark = not started.
- Concurrent phases both glow (e.g., Content and Automation active simultaneously).
- Filters: Phase dropdown, Type dropdown (workshop/demo), text search.
- Per-row refresh button (⟳) triggers on-demand manifest fetch.

### 3. Project Detail View

- Breadcrumb navigation back to Projects.
- Header: project name, type badge, module count, owner, refresh button + last refresh time.
- Labeled progress bar across the top (same 7 phases, larger with text labels).
- Accordion sections per phase:
  - Completed phases: collapsed, show checkmark and summary.
  - Active phases: expanded, show sub-details (module list with individual statuses, automation substeps, etc.).
  - Future phases: greyed out, show dependency prerequisites.
- Sidebar (responsive, roughly 40% width on wide screens):
  - Project info: type, owner, autonomy level, created date, registered date.
  - Links: GitHub repo, raw manifest, Showroom repo (if set), automation repo (if set).
  - Assignees: listed with their phase assignment.
- Layout is responsive — both panes flex with browser width, roughly equal weight. Not lopsided.

### 4. Register View

- Simple form: repo URL, project name.
- Backend validates the repo URL is accessible and contains `publishing-house/manifest.yaml`.
- On success, immediately fetches and caches the manifest, redirects to the project detail view.

### Navigation

Top-level tabs: **Pipeline** | **Projects** | **Register**

Global elements:
- Last refresh timestamp.
- Future: global "Refresh All" button.

## Refresh Strategy

- **Nightly batch:** Scheduled job iterates all registered projects and re-fetches manifests via GitHub API.
- **On-demand per-project:** "Refresh Now" button on table rows and detail view header. Triggers an immediate GitHub API fetch for that project.
- **Cache-first reads:** Frontend always reads from PostgreSQL. No direct GitHub calls from the frontend.

## Security

- **Production:** OpenShift OAuth proxy / SSO, same as Labagator and other RHDP tools. All routes protected.
- **Local development:** Auth bypass or simple mock user for testing.
- **GitHub API access:** Backend uses a GitHub token (stored as an environment variable, never committed) to read manifest files from private repos.
- **Future consideration:** If API-based registration is added later, it will require token-based auth (API keys managed through the UI).

## Local Development

The POC must run locally for testing and validation before any OpenShift deployment:

- FastAPI backend with uvicorn.
- Next.js dev server.
- PostgreSQL via Podman (using the `agnosticd` podman machine).
- No OpenShift or SSO dependencies for local dev.

## Out of Scope (POC)

- Date/milestone tracking — no due dates, no timeline views.
- Automated project registration via API (future consideration).
- Drag-and-drop on the kanban (read-only visualization).
- Editing project state from the dashboard (manifest is source of truth).
- Notifications or alerts.
- OpenShift deployment manifests (Helm chart is a follow-on task).
- Integration with RCARS or Labagator (evaluate after POC).
