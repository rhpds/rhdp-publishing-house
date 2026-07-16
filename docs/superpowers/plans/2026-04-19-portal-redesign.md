# Portal Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve the PH dashboard into a portal with sidebar nav, tabbed project detail (worklog, artifacts, launch), validation result storage via MCP, and 100+ project scale support.

**Architecture:** FastAPI backend with new tables (worklog_entries, validation_runs), worklog.yaml parsing in refresh engine, MCP server as streamable HTTP on `/mcp`, Next.js frontend with PatternFly sidebar nav and LCARS-inspired theme. Git remains source of truth for project state; DB is a cache plus operational data (validation results).

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, PostgreSQL, Next.js 15, PatternFly 6, FastMCP, Pydantic v2

**Spec:** `docs/superpowers/specs/2026-04-19-portal-redesign.md`

---

## Phase 1: Backend Foundation

### Task 1: Database Schema — Worklog and Validation Tables

**Files:**
- Create: `src/backend/alembic/versions/<auto>_add_worklog_and_validation_tables.py`
- Modify: `src/backend/app/models/__init__.py`
- Create: `src/backend/app/models/worklog.py`
- Create: `src/backend/app/models/validation.py`
- Modify: `src/backend/app/models/project.py` (add deployment_mode, owner_github columns)

- [ ] **Step 1: Create WorklogEntry ORM model**

Create `src/backend/app/models/worklog.py`:

```python
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class WorklogEntry(Base):
    __tablename__ = "worklog_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    entry_id = Column(String(100), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    author = Column(String(100))
    status = Column(String(20), nullable=False)  # open, resolved
    type = Column(String(20))  # note, decision, handoff, action, summary
    content = Column(Text, nullable=False)
    resolved_at = Column(DateTime(timezone=True))
    resolved_by = Column(String(100))

    __table_args__ = (
        {"schema": None},
    )
```

- [ ] **Step 2: Create ValidationRun ORM model**

Create `src/backend/app/models/validation.py`:

```python
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.core.database import Base


class ValidationRun(Base):
    __tablename__ = "validation_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    phase = Column(String(50), nullable=False)
    validator = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False)  # pass, fail, warning
    run_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    run_by = Column(String(100))
    summary = Column(Text)
    findings = Column(JSONB)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
```

- [ ] **Step 3: Add deployment_mode and owner_github to Project model**

Modify `src/backend/app/models/project.py` — add two columns:

```python
deployment_mode = Column(String(20))  # onboarded, self_service
owner_github = Column(String(100))
```

- [ ] **Step 4: Update models __init__.py to import new models**

Add imports for `WorklogEntry` and `ValidationRun` in `src/backend/app/models/__init__.py`.

- [ ] **Step 5: Generate and review Alembic migration**

Run: `cd src/backend && alembic revision --autogenerate -m "add worklog and validation tables"`

Review the generated migration. Ensure it includes:
- `worklog_entries` table with unique constraint on `(project_id, entry_id)`
- `validation_runs` table
- Index `idx_worklog_project_status` on `(project_id, status)`
- Index `idx_validation_project_phase` on `(project_id, phase)`
- Index `idx_validation_run_at` on `(run_at DESC)`
- New columns on `projects`: `deployment_mode`, `owner_github`

- [ ] **Step 6: Run migration**

Run: `cd src/backend && alembic upgrade head`

- [ ] **Step 7: Commit**

```bash
git add src/backend/app/models/ src/backend/alembic/
git commit -m "Add worklog_entries and validation_runs tables, extend projects"
```

---

### Task 2: Pydantic Schemas for Worklog and Validation

**Files:**
- Create: `src/backend/app/schemas/worklog.py`
- Create: `src/backend/app/schemas/validation.py`
- Modify: `src/backend/app/schemas/project.py` (add deployment_mode, owner_github, remove name from create)

- [ ] **Step 1: Create worklog schemas**

Create `src/backend/app/schemas/worklog.py`:

```python
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class WorklogEntryResponse(BaseModel):
    id: UUID
    entry_id: str
    timestamp: datetime
    author: str | None
    status: str
    type: str | None
    content: str
    resolved_at: datetime | None
    resolved_by: str | None

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Create validation schemas**

Create `src/backend/app/schemas/validation.py`:

```python
from datetime import datetime
from uuid import UUID
from typing import Any
from pydantic import BaseModel


class ValidationFinding(BaseModel):
    severity: str  # error, warning, info
    message: str
    file: str | None = None
    line: int | None = None


class ValidationRunCreate(BaseModel):
    phase: str
    validator: str
    status: str  # pass, fail, warning
    run_by: str | None = None
    summary: str | None = None
    findings: list[ValidationFinding] | None = None


class ValidationRunResponse(BaseModel):
    id: UUID
    project_id: UUID
    phase: str
    validator: str
    status: str
    run_at: datetime
    run_by: str | None
    summary: str | None
    findings: list[dict[str, Any]] | None

    model_config = {"from_attributes": True}
```

- [ ] **Step 3: Update project schemas**

Modify `src/backend/app/schemas/project.py`:
- `ProjectCreate`: remove `name` field, keep only `repo_url`
- `ProjectResponse`: add `deployment_mode: str | None` and `owner_github: str | None`

- [ ] **Step 4: Commit**

```bash
git add src/backend/app/schemas/
git commit -m "Add worklog and validation Pydantic schemas, simplify ProjectCreate"
```

---

### Task 3: Worklog Parsing in Refresh Engine

**Files:**
- Create: `src/backend/app/services/worklog_parser.py`
- Modify: `src/backend/app/services/refresh.py`
- Modify: `src/backend/app/services/github_client.py`
- Create: `src/backend/tests/test_worklog_parser.py`

- [ ] **Step 1: Write worklog parser tests**

Create `src/backend/tests/test_worklog_parser.py` with tests for:
- Parse valid worklog YAML with open and resolved entries
- Parse worklog with summary (squashed) entries
- Handle missing/empty worklog gracefully (return empty list)
- Handle malformed YAML (return empty list, don't crash)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src/backend && pytest tests/test_worklog_parser.py -v`

- [ ] **Step 3: Implement worklog parser**

Create `src/backend/app/services/worklog_parser.py`:

```python
import yaml
from datetime import datetime


def parse_worklog(raw_yaml: str) -> list[dict]:
    """Parse worklog.yaml content into a list of entry dicts."""
    try:
        data = yaml.safe_load(raw_yaml)
    except yaml.YAMLError:
        return []

    if not data or not isinstance(data, dict):
        return []

    entries = data.get("entries", [])
    if not isinstance(entries, list):
        return []

    parsed = []
    for entry in entries:
        if not isinstance(entry, dict) or "id" not in entry or "content" not in entry:
            continue
        parsed.append({
            "entry_id": str(entry["id"]),
            "timestamp": entry.get("timestamp"),
            "author": entry.get("author"),
            "status": entry.get("status", "open"),
            "type": entry.get("type"),
            "content": entry["content"],
            "resolved_at": entry.get("resolved_at"),
            "resolved_by": entry.get("resolved_by"),
        })

    return parsed
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src/backend && pytest tests/test_worklog_parser.py -v`

- [ ] **Step 5: Add worklog.yaml fetching to GitHub client**

Modify `src/backend/app/services/github_client.py` — add a `fetch_worklog()` function that tries `publishing-house/worklog.yaml`. Returns `None` if not found (404 is expected for projects without a worklog yet).

- [ ] **Step 6: Integrate worklog into refresh service**

Modify `src/backend/app/services/refresh.py`:
- After fetching and parsing the manifest, also fetch `worklog.yaml`
- Parse worklog entries with `parse_worklog()`
- Delete existing worklog entries for the project
- Insert new worklog entries from parsed data
- Extract `deployment_mode` and `owner_github` from parsed manifest, update project record

- [ ] **Step 7: Run full test suite**

Run: `cd src/backend && pytest -v`

- [ ] **Step 8: Commit**

```bash
git add src/backend/app/services/ src/backend/tests/
git commit -m "Add worklog parsing to refresh engine"
```

---

### Task 4: Validation API Endpoints

**Files:**
- Create: `src/backend/app/api/validations.py`
- Modify: `src/backend/app/main.py` (register new router)
- Create: `src/backend/tests/test_api_validations.py`

- [ ] **Step 1: Write validation endpoint tests**

Create `src/backend/tests/test_api_validations.py` with tests for:
- POST validation results (201 created, returns run with ID)
- GET validation runs for a project (list, ordered by run_at desc)
- GET specific validation run by ID (includes findings)
- POST to nonexistent project returns 404
- GET empty list for project with no validations

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src/backend && pytest tests/test_api_validations.py -v`

- [ ] **Step 3: Implement validation endpoints**

Create `src/backend/app/api/validations.py`:

```python
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.project import Project
from app.models.validation import ValidationRun
from app.schemas.validation import ValidationRunCreate, ValidationRunResponse

router = APIRouter(prefix="/api/v1/projects/{project_id}/validations", tags=["validations"])


@router.post("", response_model=ValidationRunResponse, status_code=201)
def create_validation_run(project_id: UUID, body: ValidationRunCreate, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    run = ValidationRun(
        project_id=project_id,
        phase=body.phase,
        validator=body.validator,
        status=body.status,
        run_by=body.run_by,
        summary=body.summary,
        findings=[f.model_dump() for f in body.findings] if body.findings else None,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


@router.get("", response_model=list[ValidationRunResponse])
def list_validation_runs(project_id: UUID, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return (
        db.query(ValidationRun)
        .filter(ValidationRun.project_id == project_id)
        .order_by(ValidationRun.run_at.desc())
        .all()
    )


@router.get("/{run_id}", response_model=ValidationRunResponse)
def get_validation_run(project_id: UUID, run_id: UUID, db: Session = Depends(get_db)):
    run = (
        db.query(ValidationRun)
        .filter(ValidationRun.project_id == project_id, ValidationRun.id == run_id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="Validation run not found")
    return run
```

- [ ] **Step 4: Register router in main.py**

Modify `src/backend/app/main.py` — import and include the validations router.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd src/backend && pytest tests/test_api_validations.py -v`

- [ ] **Step 6: Commit**

```bash
git add src/backend/app/api/validations.py src/backend/app/main.py src/backend/tests/test_api_validations.py
git commit -m "Add validation results API endpoints"
```

---

### Task 5: Worklog and Launch API Endpoints

**Files:**
- Modify: `src/backend/app/api/projects.py` (add worklog and launch endpoints, simplify registration)
- Create: `src/backend/app/services/launch_instructions.py`
- Create: `src/backend/tests/test_launch_instructions.py`

- [ ] **Step 1: Write launch instructions service tests**

Create `src/backend/tests/test_launch_instructions.py` with tests for:
- Onboarded project returns CI link from manifest integrations
- Self-service project returns generic CI link + repo URL + revision + path parameters
- Project with missing integrations returns helpful message

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src/backend && pytest tests/test_launch_instructions.py -v`

- [ ] **Step 3: Implement launch instructions service**

Create `src/backend/app/services/launch_instructions.py`:

```python
def get_launch_instructions(manifest_data: dict) -> dict:
    """Generate ordering instructions based on deployment_mode and integrations."""
    project = manifest_data.get("project", {})
    integrations = manifest_data.get("integrations", {})
    mode = project.get("deployment_mode", "")

    if mode == "onboarded":
        return {
            "deployment_mode": "onboarded",
            "description": "This project has its own catalog item in RHDP.",
            "steps": [
                {"step": 1, "action": "Go to the RHDP catalog", "url": "https://catalog.demo.redhat.com"},
                {"step": 2, "action": f"Search for the catalog item", "detail": integrations.get("catalog_item_name") or "Check the manifest for the catalog item name"},
                {"step": 3, "action": "Order with default parameters"},
            ],
        }
    elif mode == "self_service":
        return {
            "deployment_mode": "self_service",
            "description": "This project uses the generic Field Source CI. You provide the GitOps repo when ordering.",
            "steps": [
                {"step": 1, "action": "Go to the RHDP catalog", "url": "https://catalog.demo.redhat.com"},
                {"step": 2, "action": "Order 'Field Sourced Content - OpenShift Base (CNV)'"},
                {"step": 3, "action": "Enable 'Existing Gitops Repo' checkbox"},
                {"step": 4, "action": "Set GitOps Repo URL", "value": integrations.get("automation_repo", "")},
                {"step": 5, "action": "Set GitOps Revision", "value": "main"},
                {"step": 6, "action": "Set GitOps Path", "value": integrations.get("automation_path", "")},
            ],
            "showroom_repo": integrations.get("showroom_repo"),
            "automation_repo": integrations.get("automation_repo"),
        }
    else:
        return {
            "deployment_mode": mode or "unknown",
            "description": "Deployment mode not set. Update the manifest with deployment_mode: onboarded or self_service.",
            "steps": [],
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src/backend && pytest tests/test_launch_instructions.py -v`

- [ ] **Step 5: Add worklog and launch endpoints to projects API**

Modify `src/backend/app/api/projects.py`:
- Add `GET /api/v1/projects/{id}/worklog` — returns worklog entries from DB, filtered by status if query param provided
- Add `GET /api/v1/projects/{id}/launch` — returns launch instructions from parsed manifest data
- Simplify `POST /api/v1/projects` — accept only `repo_url`, derive name/owner/mode from manifest

- [ ] **Step 6: Update existing project tests for simplified registration**

Modify `src/backend/tests/test_api_projects.py` — registration tests should send only `repo_url`, not `name`.

- [ ] **Step 7: Run full test suite**

Run: `cd src/backend && pytest -v`

- [ ] **Step 8: Commit**

```bash
git add src/backend/app/api/ src/backend/app/services/ src/backend/tests/
git commit -m "Add worklog, launch endpoints; simplify registration to repo URL only"
```

---

### Task 6: Refresh Engine — Scale and Frequency

**Files:**
- Modify: `src/backend/app/services/refresh.py`
- Modify: `src/backend/app/services/github_client.py`
- Modify: `src/backend/app/main.py` (change schedule to 30 min)
- Modify: `src/backend/app/core/config.py` (add refresh interval setting)

- [ ] **Step 1: Add incremental refresh check to GitHub client**

Modify `src/backend/app/services/github_client.py` — add `get_repo_last_push(owner, repo)` that calls GitHub API for repo metadata and returns `pushed_at` timestamp. This is a lightweight check to avoid fetching manifests for repos that haven't changed.

- [ ] **Step 2: Update refresh service with incremental logic**

Modify `src/backend/app/services/refresh.py`:
- Before fetching manifest, check `pushed_at` vs `last_refreshed_at`
- Skip fetch if repo hasn't changed since last refresh
- Add `force` parameter to bypass the incremental check
- Use `asyncio.gather` with `asyncio.Semaphore(10)` for parallel refresh of multiple projects

- [ ] **Step 3: Update refresh schedule to 30 minutes**

Modify `src/backend/app/core/config.py` — add `REFRESH_INTERVAL_MINUTES: int = 30`.
Modify `src/backend/app/main.py` — use the config value for the APScheduler interval.

- [ ] **Step 4: Run full test suite**

Run: `cd src/backend && pytest -v`

- [ ] **Step 5: Commit**

```bash
git add src/backend/app/
git commit -m "Add incremental refresh, parallel execution, 30-min schedule"
```

---

### Task 7: Swagger UI and Schema Cleanup

**Files:**
- Modify: `src/backend/app/main.py` (ensure docs are enabled and titled)
- Review all endpoints for typed responses

- [ ] **Step 1: Verify Swagger UI is accessible**

FastAPI enables `/docs` and `/redoc` by default. Verify this is not disabled anywhere. Add a descriptive title:

```python
app = FastAPI(
    title="Publishing House Portal API",
    description="API for the RHDP Publishing House content lifecycle portal",
    version="0.2.0",
)
```

- [ ] **Step 2: Audit all endpoints for typed response models**

Review every endpoint in `projects.py`, `validations.py`, `health.py`. Every endpoint must have a `response_model` parameter. No raw dict returns.

- [ ] **Step 3: Run full test suite**

Run: `cd src/backend && pytest -v`

- [ ] **Step 4: Commit**

```bash
git add src/backend/app/
git commit -m "Configure Swagger UI, audit response schemas"
```

---

## Phase 2: Frontend Redesign

### Task 8: Sidebar Navigation Layout

**Files:**
- Modify: `src/frontend/src/app/layout.tsx` (replace top nav with sidebar)
- Create: `src/frontend/src/components/Sidebar.tsx`
- Create: `src/frontend/src/components/Breadcrumbs.tsx`

- [ ] **Step 1: Create Sidebar component**

Create `src/frontend/src/components/Sidebar.tsx` — PatternFly `Nav` component with vertical layout:
- Pipeline link
- Projects link
- Tools section with RCARS Advisor external link
- Active state highlighting based on current path
- LCARS-inspired styling: angular panels, color bands, dark background (#1a1a2e)

- [ ] **Step 2: Create Breadcrumbs component**

Create `src/frontend/src/components/Breadcrumbs.tsx` — PatternFly `Breadcrumb` component. Reads current path and renders breadcrumb trail. Project detail pages show: Projects / {project name} / {active tab}.

- [ ] **Step 3: Update layout.tsx**

Modify `src/frontend/src/app/layout.tsx`:
- Replace the existing Masthead/top-nav layout with a sidebar + main content layout
- Sidebar on the left (fixed width, collapsible)
- Breadcrumbs at the top of the main content area
- Main content fills remaining space

- [ ] **Step 4: Test in browser**

Run: `cd src/frontend && npm run dev`
Verify: sidebar visible, links navigate correctly, breadcrumbs update, responsive on smaller screens.

- [ ] **Step 5: Commit**

```bash
git add src/frontend/src/
git commit -m "Replace top nav with PatternFly sidebar and breadcrumbs"
```

---

### Task 9: LCARS Theme Styling

**Files:**
- Create: `src/frontend/src/styles/lcars-theme.css`
- Modify: `src/frontend/src/app/layout.tsx` (import theme)

- [ ] **Step 1: Create LCARS theme CSS**

Create `src/frontend/src/styles/lcars-theme.css` with:
- LCARS color palette variables (amber #e8a838, blue #73bcf7, red #ff8787, green #69db7c, dark backgrounds)
- Angular panel borders and color band accents
- Typography overrides (clean, modern but Trek-inspired)
- PatternFly component overrides for dark mode consistency
- Match the RCARS app's visual style from `~/devel/working/rcars-advisory/src/rcars/web/static/`

Reference the RCARS CSS at `~/devel/working/rcars-advisory/src/rcars/web/static/css/` for the exact color values and patterns.

- [ ] **Step 2: Import theme in layout**

Add import in `layout.tsx`.

- [ ] **Step 3: Test in browser**

Verify visual consistency. Compare side-by-side with RCARS if possible.

- [ ] **Step 4: Commit**

```bash
git add src/frontend/src/styles/ src/frontend/src/app/layout.tsx
git commit -m "Add LCARS-inspired theme consistent with RCARS"
```

---

### Task 10: Tabbed Project Detail Page

**Files:**
- Modify: `src/frontend/src/app/projects/[id]/page.tsx` (add tabs)
- Create: `src/frontend/src/components/WorklogTimeline.tsx`
- Create: `src/frontend/src/components/ArtifactsList.tsx`
- Create: `src/frontend/src/components/LaunchInstructions.tsx`
- Modify: `src/frontend/src/types/index.ts` (add worklog, validation types)
- Modify: `src/frontend/src/services/api.ts` (add worklog, launch, validation API calls)

- [ ] **Step 1: Add TypeScript types**

Modify `src/frontend/src/types/index.ts` — add:

```typescript
export interface WorklogEntry {
  id: string;
  entry_id: string;
  timestamp: string;
  author: string | null;
  status: "open" | "resolved";
  type: "note" | "decision" | "handoff" | "action" | "summary" | null;
  content: string;
  resolved_at: string | null;
  resolved_by: string | null;
}

export interface ValidationRun {
  id: string;
  project_id: string;
  phase: string;
  validator: string;
  status: "pass" | "fail" | "warning";
  run_at: string;
  run_by: string | null;
  summary: string | null;
  findings: ValidationFinding[] | null;
}

export interface ValidationFinding {
  severity: "error" | "warning" | "info";
  message: string;
  file: string | null;
  line: number | null;
}

export interface LaunchInstructions {
  deployment_mode: string;
  description: string;
  steps: { step: number; action: string; url?: string; value?: string; detail?: string }[];
  showroom_repo?: string;
  automation_repo?: string;
}
```

- [ ] **Step 2: Add API client functions**

Modify `src/frontend/src/services/api.ts` — add:
- `getWorklog(projectId: string): Promise<WorklogEntry[]>`
- `getLaunchInstructions(projectId: string): Promise<LaunchInstructions>`
- `getValidationRuns(projectId: string): Promise<ValidationRun[]>`

- [ ] **Step 3: Create WorklogTimeline component**

Create `src/frontend/src/components/WorklogTimeline.tsx`:
- Renders worklog entries as a timeline
- Open items highlighted (amber border, "action needed" or "decision" badges)
- Resolved items muted with strikethrough and green "resolved" badge
- Summary entries styled distinctly (condensed, system-authored)
- Sorted by timestamp descending

- [ ] **Step 4: Create ArtifactsList component**

Create `src/frontend/src/components/ArtifactsList.tsx`:
- Aggregates artifacts from all phases in the manifest
- Groups by phase or by type (design docs, modules, automation, reviews)
- Each artifact links to GitHub (using the repo URL from project)
- Also includes content_path links from writing modules

- [ ] **Step 5: Create LaunchInstructions component**

Create `src/frontend/src/components/LaunchInstructions.tsx`:
- Fetches launch instructions from API
- Renders numbered steps
- Steps with URLs render as clickable links
- Steps with values render the value in a copyable code block
- Shows deployment mode prominently at the top

- [ ] **Step 6: Update project detail page with tabs**

Modify `src/frontend/src/app/projects/[id]/page.tsx`:
- Add PatternFly `Tabs` component with four tabs: Overview, Worklog, Artifacts, Launch
- Overview tab: existing phase accordion (PhaseAccordion) + progress bar + project header
- Worklog tab: WorklogTimeline component + badge showing open entry count
- Artifacts tab: ArtifactsList component
- Launch tab: LaunchInstructions component
- Validation results shown inline in Overview under relevant phases (small badge)

- [ ] **Step 7: Test in browser**

Run dev server, navigate to a project detail page. Verify:
- Tabs switch correctly
- Worklog displays entries (may be empty for projects without worklog.yaml)
- Artifacts aggregates from phase metadata
- Launch shows instructions based on deployment_mode
- Phase accordion still works as before in Overview tab

- [ ] **Step 8: Commit**

```bash
git add src/frontend/src/
git commit -m "Add tabbed project detail: worklog, artifacts, launch tabs"
```

---

### Task 11: Simplified Registration Page

**Files:**
- Modify: `src/frontend/src/app/register/page.tsx`

- [ ] **Step 1: Simplify registration form**

Modify `src/frontend/src/app/register/page.tsx`:
- Remove the `name` field
- Keep only the `repo_url` field
- Update the submit handler to send only `{ repo_url }`
- After successful registration, show the project name (from manifest) in a success message
- Add error handling: "This repo doesn't have a Publishing House manifest" for 400 responses

- [ ] **Step 2: Test in browser**

Register a project with only a repo URL. Verify the project appears with the correct name from the manifest.

- [ ] **Step 3: Commit**

```bash
git add src/frontend/src/app/register/
git commit -m "Simplify registration to repo URL only"
```

---

## Phase 3: MCP Server

### Task 12: MCP Server Setup

**Files:**
- Create: `src/backend/app/mcp/__init__.py`
- Create: `src/backend/app/mcp/server.py`
- Create: `src/backend/app/mcp/tools.py`
- Modify: `src/backend/app/main.py` (mount MCP)
- Modify: `src/backend/requirements.txt` (add fastmcp)

- [ ] **Step 1: Add fastmcp dependency**

Add `fastmcp` to `src/backend/requirements.txt`.

Run: `cd src/backend && pip install -r requirements.txt`

- [ ] **Step 2: Create MCP server module**

Create `src/backend/app/mcp/server.py`:

```python
from fastmcp import FastMCP

mcp = FastMCP(
    name="publishing-house",
    instructions="Publishing House portal MCP server. Provides cross-project visibility, launch instructions, and validation result storage for RHDP content lifecycle projects.",
)
```

- [ ] **Step 3: Create MCP tools**

Create `src/backend/app/mcp/tools.py` with four tools:

```python
from app.mcp.server import mcp
from app.core.database import get_db
from app.models.project import Project
from app.models.validation import ValidationRun
from app.services.launch_instructions import get_launch_instructions


@mcp.tool()
def ph_list_projects() -> list[dict]:
    """List all Publishing House projects with their current phase and status."""
    # Query all projects, join phases, return summary
    ...


@mcp.tool()
def ph_get_launch_instructions(project_id: str) -> dict:
    """Get step-by-step ordering instructions for deploying a project."""
    # Look up project, get parsed manifest, return launch instructions
    ...


@mcp.tool()
def ph_store_validation_results(
    project_id: str,
    phase: str,
    validator: str,
    status: str,
    summary: str | None = None,
    findings: list[dict] | None = None,
    run_by: str | None = None,
) -> dict:
    """Store validation results from agnosticv:validator or showroom:verify-content."""
    # Create ValidationRun record, return confirmation
    ...


@mcp.tool()
def ph_get_validation_results(project_id: str, phase: str | None = None) -> list[dict]:
    """Get validation results for a project, optionally filtered by phase."""
    # Query validation_runs, return results
    ...
```

Implement each tool using the same DB session pattern as the REST endpoints. The tools call the same service functions.

- [ ] **Step 4: Mount MCP on FastAPI app**

Modify `src/backend/app/main.py`:

```python
from app.mcp.tools import mcp  # importing tools registers them on the mcp instance

# Mount MCP as streamable HTTP
app.mount("/mcp", mcp.streamable_http_app())
```

- [ ] **Step 5: Test MCP endpoint**

Run the backend server. Verify `/mcp` responds to MCP protocol requests.

Test with curl or the MCP inspector tool if available:
```bash
curl -X POST http://localhost:8081/mcp -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
```

Expected: JSON response listing the four tools.

- [ ] **Step 6: Commit**

```bash
git add src/backend/app/mcp/ src/backend/app/main.py src/backend/requirements.txt
git commit -m "Add MCP server with list, launch, validation tools"
```

---

### Task 13: MCP Auth (Investigation + Implementation)

**Files:**
- Create: `src/backend/app/mcp/auth.py`
- Modify: `src/backend/app/mcp/server.py` (conditionally enable auth)
- Modify: `src/backend/app/core/config.py` (add MCP auth settings)

> **Note:** This task requires investigation first. Read the reporting-mcp auth implementation at `~/devel/working/rcars-advisory/` or via GitHub at `rhpds/demo-reporting/reporting-mcp/src/core/auth.py`. Understand which Keycloak realm is used and how Claude Code obtains a token. If the Keycloak infrastructure is not accessible, defer this task and keep `MCP_AUTH_ENABLED=false`.

- [ ] **Step 1: Investigate Keycloak setup**

Check with the reporting-mcp team (or the repo's README/env.example) for:
- Which Keycloak realm URL to use
- How Claude Code clients obtain JWT tokens
- Whether the same realm works for PH

If blocked, skip to Step 5 (ship without auth, flag for follow-up).

- [ ] **Step 2: Add auth config settings**

Modify `src/backend/app/core/config.py`:

```python
MCP_AUTH_ENABLED: bool = False
KEYCLOAK_REALM_URL: str | None = None
```

- [ ] **Step 3: Implement KeycloakTokenVerifier**

Create `src/backend/app/mcp/auth.py` — follow the `rhpds/demo-reporting` pattern:
- `KeycloakTokenVerifier` class implementing `verify_token(token: str) -> AccessToken | None`
- JWKS client with key caching
- RS256 signature validation
- Issuer validation against `KEYCLOAK_REALM_URL`
- Audience validation disabled (dynamic OAuth clients)

- [ ] **Step 4: Wire auth into MCP server**

Modify `src/backend/app/mcp/server.py` — conditionally pass `token_verifier` to FastMCP based on `MCP_AUTH_ENABLED` config.

- [ ] **Step 5: Commit**

```bash
git add src/backend/app/mcp/ src/backend/app/core/config.py
git commit -m "Add MCP auth (Keycloak JWT, toggleable)"
```

---

## Phase 4: Integration and Polish

### Task 14: End-to-End Verification

**Files:** No new files. Testing and verification only.

- [ ] **Step 1: Run full backend test suite**

Run: `cd src/backend && pytest -v`
All tests must pass.

- [ ] **Step 2: Run frontend build**

Run: `cd src/frontend && npm run build`
Must build without errors.

- [ ] **Step 3: Start full stack locally**

Run: `./dev-services.sh start`
Verify all services start (postgres, backend, frontend).

- [ ] **Step 4: Test registration flow**

1. Go to `/register`
2. Enter a project repo URL (use one of the example projects)
3. Verify project appears with name from manifest
4. Verify phases are populated
5. Verify worklog tab shows entries (if worklog.yaml exists)
6. Verify launch tab shows instructions

- [ ] **Step 5: Test pipeline view**

Navigate to `/pipeline`. Verify projects appear in correct kanban columns.

- [ ] **Step 6: Test MCP endpoint**

```bash
curl -X POST http://localhost:8081/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"ph_list_projects","arguments":{}},"id":1}'
```

Verify response includes registered projects.

- [ ] **Step 7: Test validation storage via MCP**

```bash
curl -X POST http://localhost:8081/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"ph_store_validation_results","arguments":{"project_id":"<uuid>","phase":"automation","validator":"agnosticv:validator","status":"pass","summary":"All checks passed"}},"id":2}'
```

Verify result stored. Check portal UI shows validation badge on the project.

- [ ] **Step 8: Verify Swagger UI**

Navigate to `http://localhost:8081/docs`. Verify all endpoints are documented with schemas.

- [ ] **Step 9: Commit any fixes**

```bash
git add -A
git commit -m "Fix integration issues from end-to-end testing"
```

---

### Task 15: Deploy to OpenShift Dev

**Files:**
- Modify: `ansible/templates/manifests-app.yaml.j2` (if MCP port or env vars needed)
- Modify: `ansible/vars/common.yml` (if new env vars)

- [ ] **Step 1: Review deployment manifests for new requirements**

Check if the MCP endpoint needs any additional configuration:
- The MCP runs on the same port as the FastAPI app (8081), so no new service/route needed
- New env vars: `MCP_AUTH_ENABLED`, `KEYCLOAK_REALM_URL` (if auth is enabled)
- New pip dependency: `fastmcp` (handled by Containerfile pip install)

- [ ] **Step 2: Deploy to dev**

```bash
cd ansible
ansible-playbook deploy.yml -e env=dev --tags update
```

- [ ] **Step 3: Run database migration on dev**

The migration runs automatically on startup if configured, or manually:
```bash
oc exec -n publishing-house-dev deployment/ph-portal-backend -- alembic upgrade head
```

- [ ] **Step 4: Verify deployment**

- Check portal UI is accessible via the OpenShift route
- Test registration, project detail tabs, pipeline view
- Test MCP endpoint via curl against the deployed URL

- [ ] **Step 5: Commit any deployment fixes**

```bash
git add ansible/
git commit -m "Update deployment for portal redesign"
```
