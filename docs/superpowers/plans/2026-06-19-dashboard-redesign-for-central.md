# Dashboard Redesign for PH Central — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the PH Central frontend and REST API to use Central's data model (cached phase statuses from PhaseEngine, gate history from GateService, manifests from GitRepoReader) instead of the old Manifest/Phase DB models.

**Architecture:** The backend services (PhaseEngine, GateService, GitRepoReader) already exist. This plan adds cached status fields to the Project model, rewrites the REST API to wrap those services, updates the periodic sync to populate the cache, then rewrites the frontend to consume the new API shape. The pipeline board uses a 6-column data-driven kanban config. The project detail page shows gate history inline per phase.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Alembic, PostgreSQL (JSONB). Next.js 15, React 19, PatternFly 6, TypeScript.

## Global Constraints

- Work on the `feature/ph-central-registration` branch in `~/devel/publishing-house/rhdp-publishing-house-central/`
- Backend: `src/backend/`, tests: `src/backend/tests/`
- Frontend: `src/frontend/src/`
- Tests use SQLite in-memory via the existing `conftest.py` fixture (`test_db`, `client`, `db_session`)
- Use `JSONBType` from `app.core.types` for all JSONB columns (works with both PostgreSQL and SQLite)
- Use `yaml.safe_load` always — never `yaml.load`
- PatternFly 6 components only (Red Hat standard) with LCARS dark theme CSS
- Name: "Publishing House Central" — no subtitle

---

### Task 1: Add cached status fields to Project model + Alembic migration

**Files:**
- Modify: `src/backend/app/models/project.py`
- Create: `src/backend/alembic/versions/d3e4f5g6h7i8_add_cached_status_fields.py`
- Test: `src/backend/tests/test_project_cached_fields.py`

**Interfaces:**
- Consumes: existing `Project` model, `JSONBType` from `app.core.types`
- Produces: `Project.cached_phase_statuses` (JSONB, nullable), `Project.cached_current_phase` (String(50), nullable), `Project.cached_next_action` (JSONB, nullable), `Project.cached_manifest_data` (JSONB, nullable), `Project.cached_at` (DateTime(timezone=True), nullable)

- [ ] **Step 1: Write the failing test**

Create `src/backend/tests/test_project_cached_fields.py`:

```python
"""Test that Project model has cached status fields."""
from datetime import datetime, timezone
from app.models.project import Project


def test_project_has_cached_fields(db_session):
    project = Project(
        name="Test",
        repo_url="git@github.com:rhpds/test.git",
        branch="main",
        cached_phase_statuses={"intake": "completed", "writing": "in_progress"},
        cached_current_phase="writing",
        cached_next_action={"next_phase": "writing", "action": "continue", "detail": "Continue working on writing"},
        cached_manifest_data={"project": {"name": "Test"}, "lifecycle": {"current_phase": "writing"}},
        cached_at=datetime.now(timezone.utc),
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    assert project.cached_phase_statuses == {"intake": "completed", "writing": "in_progress"}
    assert project.cached_current_phase == "writing"
    assert project.cached_next_action["action"] == "continue"
    assert project.cached_manifest_data["project"]["name"] == "Test"
    assert project.cached_at is not None


def test_project_cached_fields_nullable(db_session):
    project = Project(name="Bare", repo_url="git@github.com:rhpds/bare.git", branch="main")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    assert project.cached_phase_statuses is None
    assert project.cached_current_phase is None
    assert project.cached_next_action is None
    assert project.cached_manifest_data is None
    assert project.cached_at is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/backend && python -m pytest tests/test_project_cached_fields.py -v`
Expected: FAIL — `Project` has no `cached_phase_statuses` attribute

- [ ] **Step 3: Add cached fields to Project model**

Modify `src/backend/app/models/project.py` — add after the `owner_email` field:

```python
from app.core.types import JSONBType

# ... existing fields ...
    owner_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Cached status from periodic sync (populated by GitRepoReader + PhaseEngine)
    cached_phase_statuses: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)
    cached_current_phase: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    cached_next_action: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)
    cached_manifest_data: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)
    cached_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd src/backend && python -m pytest tests/test_project_cached_fields.py -v`
Expected: PASS

- [ ] **Step 5: Create Alembic migration**

Create `src/backend/alembic/versions/d3e4f5g6h7i8_add_cached_status_fields.py`:

```python
"""Add cached status fields to projects table.

Revision ID: d3e4f5g6h7i8
Revises: c2d3e4f5g6h7
Create Date: 2026-06-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d3e4f5g6h7i8"
down_revision = "c2d3e4f5g6h7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("cached_phase_statuses", postgresql.JSONB(), nullable=True))
    op.add_column("projects", sa.Column("cached_current_phase", sa.String(50), nullable=True))
    op.add_column("projects", sa.Column("cached_next_action", postgresql.JSONB(), nullable=True))
    op.add_column("projects", sa.Column("cached_manifest_data", postgresql.JSONB(), nullable=True))
    op.add_column("projects", sa.Column("cached_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "cached_at")
    op.drop_column("projects", "cached_manifest_data")
    op.drop_column("projects", "cached_next_action")
    op.drop_column("projects", "cached_current_phase")
    op.drop_column("projects", "cached_phase_statuses")
```

- [ ] **Step 6: Commit**

```bash
git add src/backend/app/models/project.py src/backend/alembic/versions/d3e4f5g6h7i8_add_cached_status_fields.py src/backend/tests/test_project_cached_fields.py
git commit -m "Add cached status fields to Project model for dashboard"
```

---

### Task 2: New Pydantic schemas for Central API responses

**Files:**
- Modify: `src/backend/app/schemas/project.py`
- Test: `src/backend/tests/test_schemas_central.py`

**Interfaces:**
- Consumes: `Project` model fields from Task 1
- Produces: `CentralProjectCreate(BaseModel)` with `repo_url: str` and `branch: str = "main"`, `CentralProjectResponse(BaseModel)` with all project fields + cached status fields, `GateRecordResponse(BaseModel)` matching GateRecord model, `ProjectStatusResponse(BaseModel)` for live status endpoint

- [ ] **Step 1: Write the failing test**

Create `src/backend/tests/test_schemas_central.py`:

```python
"""Test Central Pydantic schemas."""
from datetime import datetime, timezone
from app.schemas.project import CentralProjectCreate, CentralProjectResponse, GateRecordResponse, ProjectStatusResponse


def test_central_project_create_defaults():
    data = CentralProjectCreate(repo_url="git@github.com:rhpds/test.git")
    assert data.branch == "main"


def test_central_project_create_custom_branch():
    data = CentralProjectCreate(repo_url="git@github.com:rhpds/test.git", branch="feature/x")
    assert data.branch == "feature/x"


def test_central_project_response_from_dict():
    resp = CentralProjectResponse(
        id="550e8400-e29b-41d4-a716-446655440000",
        name="Test",
        repo_url="git@github.com:rhpds/test.git",
        branch="main",
        owner_github="stencell",
        owner_email=None,
        deployment_mode="rhdp_published",
        registered_at=datetime.now(timezone.utc),
        last_synced_at=None,
        cached_phase_statuses={"intake": "completed"},
        cached_current_phase="writing",
        cached_next_action={"next_phase": "writing", "action": "continue", "detail": "x"},
        cached_manifest_data=None,
        cached_at=None,
    )
    assert resp.name == "Test"
    assert resp.branch == "main"
    assert resp.cached_phase_statuses == {"intake": "completed"}


def test_gate_record_response():
    resp = GateRecordResponse(
        gate_id="550e8400-e29b-41d4-a716-446655440001",
        phase="vetting",
        result="approved",
        reason="All prerequisites satisfied",
        findings=None,
        requested_by="dev@redhat.com",
        approved_by=None,
        is_self_approval=False,
        override=False,
        spec_commit=None,
        created_at=datetime.now(timezone.utc),
    )
    assert resp.result == "approved"


def test_project_status_response():
    resp = ProjectStatusResponse(
        current_phase="writing",
        phase_statuses={"intake": "completed", "writing": "in_progress"},
        next_action={"next_phase": "writing", "action": "continue", "detail": "x"},
        deployment_mode="rhdp_published",
    )
    assert resp.current_phase == "writing"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/backend && python -m pytest tests/test_schemas_central.py -v`
Expected: FAIL — `CentralProjectCreate` not found

- [ ] **Step 3: Rewrite schemas**

Replace `src/backend/app/schemas/project.py` with:

```python
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class CentralProjectCreate(BaseModel):
    repo_url: str
    branch: str = "main"


class CentralProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    repo_url: str
    branch: str
    owner_github: Optional[str] = None
    owner_email: Optional[str] = None
    deployment_mode: Optional[str] = None
    registered_at: datetime
    last_synced_at: Optional[datetime] = None
    cached_phase_statuses: Optional[dict] = None
    cached_current_phase: Optional[str] = None
    cached_next_action: Optional[dict] = None
    cached_manifest_data: Optional[dict] = None
    cached_at: Optional[datetime] = None


class GateRecordResponse(BaseModel):
    gate_id: str
    phase: str
    result: str
    reason: str
    findings: Optional[dict] = None
    requested_by: Optional[str] = None
    approved_by: Optional[str] = None
    is_self_approval: bool = False
    override: bool = False
    spec_commit: Optional[str] = None
    created_at: datetime


class ProjectStatusResponse(BaseModel):
    current_phase: str
    phase_statuses: dict
    next_action: dict
    deployment_mode: str
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd src/backend && python -m pytest tests/test_schemas_central.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/backend/app/schemas/project.py src/backend/tests/test_schemas_central.py
git commit -m "Add Central Pydantic schemas for dashboard API"
```

---

### Task 3: Rewrite REST API endpoints

**Files:**
- Modify: `src/backend/app/api/projects.py`
- Test: `src/backend/tests/test_api_projects_central.py`

**Interfaces:**
- Consumes: `CentralProjectCreate`, `CentralProjectResponse`, `GateRecordResponse`, `ProjectStatusResponse` from Task 2. `Project` model from Task 1. `GitRepoReader.fetch_manifest(owner, repo, ref) -> dict` from `app.services.git_repo_reader`. `PhaseEngine.get_next_action(manifest) -> dict` from `app.services.phase_engine`. `GateService.get_history(db, project_id) -> list[dict]` from `app.services.gate_service`. `parse_repo_url(url) -> tuple[str, str]` from `app.services.git_repo_reader`.
- Produces: REST endpoints: `GET /projects` (list), `POST /projects` (register), `GET /projects/{id}` (detail), `GET /projects/{id}/status` (live), `GET /projects/{id}/gates` (history), `POST /projects/{id}/refresh`, `DELETE /projects/{id}`

- [ ] **Step 1: Write the failing test**

Create `src/backend/tests/test_api_projects_central.py`:

```python
"""Test rewritten Central REST API endpoints."""
import uuid
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from app.models.project import Project
from app.models.gate_record import GateRecord

SAMPLE_MANIFEST = {
    "project": {
        "name": "Test Workshop",
        "owner_github": "stencell",
        "owner_email": "nate@redhat.com",
        "deployment_mode": "rhdp_published",
    },
    "lifecycle": {
        "current_phase": "writing",
        "phases": {
            "intake": {"status": "completed"},
            "writing": {"status": "in_progress"},
        },
    },
}


def _seed_project(db_session, **overrides):
    defaults = dict(
        name="Test Workshop",
        repo_url="git@github.com:rhpds/test-workshop.git",
        branch="main",
        deployment_mode="rhdp_published",
        owner_github="stencell",
        cached_phase_statuses={"intake": "completed", "writing": "in_progress"},
        cached_current_phase="writing",
        cached_next_action={"next_phase": "writing", "action": "continue", "detail": "Continue"},
        cached_manifest_data=SAMPLE_MANIFEST,
        cached_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    project = Project(**defaults)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


def test_list_projects_returns_cached_status(client, db_session):
    _seed_project(db_session)
    resp = client.get("/api/v1/projects")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["branch"] == "main"
    assert data[0]["cached_current_phase"] == "writing"
    assert "phases" not in data[0]


def test_get_project_detail(client, db_session):
    project = _seed_project(db_session)
    resp = client.get(f"/api/v1/projects/{project.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cached_manifest_data"] is not None
    assert data["cached_phase_statuses"]["intake"] == "completed"


def test_get_project_not_found(client):
    resp = client.get(f"/api/v1/projects/{uuid.uuid4()}")
    assert resp.status_code == 404


@patch("app.api.projects.GitRepoReader")
def test_register_project(mock_reader_cls, client):
    reader_instance = MagicMock()
    reader_instance.fetch_manifest.return_value = SAMPLE_MANIFEST
    mock_reader_cls.return_value = reader_instance

    resp = client.post("/api/v1/projects", json={
        "repo_url": "git@github.com:rhpds/new-project.git",
        "branch": "main",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test Workshop"
    assert data["branch"] == "main"
    assert data["cached_current_phase"] == "writing"


@patch("app.api.projects.GitRepoReader")
def test_register_duplicate_rejected(mock_reader_cls, client, db_session):
    _seed_project(db_session)
    resp = client.post("/api/v1/projects", json={
        "repo_url": "git@github.com:rhpds/test-workshop.git",
        "branch": "main",
    })
    assert resp.status_code == 409


def test_delete_project(client, db_session):
    project = _seed_project(db_session)
    resp = client.delete(f"/api/v1/projects/{project.id}")
    assert resp.status_code == 204


def test_get_gates(client, db_session):
    project = _seed_project(db_session)
    record = GateRecord(
        project_id=project.id,
        phase="vetting",
        result="approved",
        reason="All prerequisites satisfied",
        requested_by="dev@redhat.com",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(record)
    db_session.commit()

    resp = client.get(f"/api/v1/projects/{project.id}/gates")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["phase"] == "vetting"
    assert data[0]["result"] == "approved"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/backend && python -m pytest tests/test_api_projects_central.py -v`
Expected: FAIL — old API returns `phases` array, new fields not present

- [ ] **Step 3: Rewrite the projects API**

Replace `src/backend/app/api/projects.py` with:

```python
"""Projects API endpoints — Central data model."""
import uuid
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.project import Project
from app.models.gate_record import GateRecord
from app.schemas.project import (
    CentralProjectCreate,
    CentralProjectResponse,
    GateRecordResponse,
    ProjectStatusResponse,
)
from app.services.git_repo_reader import GitRepoReader, GitRepoReaderError, parse_repo_url
from app.services.phase_engine import PhaseEngine
from app.services.gate_service import GateService

router = APIRouter(prefix="/projects", tags=["projects"])


def _get_reader() -> GitRepoReader:
    return GitRepoReader(token=settings.github_token)


def _cache_status(project: Project, manifest: dict) -> None:
    """Compute and cache phase status on a project from a parsed manifest."""
    lifecycle = manifest.get("lifecycle", {})
    phases = lifecycle.get("phases", {})
    project.cached_phase_statuses = {name: p.get("status", "pending") for name, p in phases.items()}
    project.cached_current_phase = lifecycle.get("current_phase", "intake")
    project.cached_next_action = PhaseEngine.get_next_action(manifest)
    project.cached_manifest_data = manifest
    project.cached_at = datetime.now(timezone.utc)
    project.last_synced_at = datetime.now(timezone.utc)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CentralProjectResponse)
def register_project(data: CentralProjectCreate, db: Session = Depends(get_db)):
    """Register a new project by fetching its manifest from git."""
    existing = db.query(Project).filter(
        Project.repo_url == data.repo_url,
        Project.branch == data.branch,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project already registered: {data.repo_url}@{data.branch}",
        )

    reader = _get_reader()
    try:
        owner, repo = parse_repo_url(data.repo_url)
        manifest = reader.fetch_manifest(owner, repo, data.branch)
    except (ValueError, GitRepoReaderError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    project_meta = manifest.get("project", {})
    project = Project(
        name=project_meta.get("name") or repo,
        repo_url=data.repo_url,
        branch=data.branch,
        owner_github=project_meta.get("owner_github") or project_meta.get("owner"),
        owner_email=project_meta.get("owner_email"),
        deployment_mode=project_meta.get("deployment_mode"),
    )
    _cache_status(project, manifest)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=List[CentralProjectResponse])
def list_projects(db: Session = Depends(get_db)):
    """List all registered projects with cached status."""
    return db.query(Project).order_by(Project.name).all()


@router.get("/{project_id}", response_model=CentralProjectResponse)
def get_project(project_id: uuid.UUID, db: Session = Depends(get_db)):
    """Get a single project with full cached data."""
    project = db.query(Project).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project {project_id} not found")
    return project


@router.get("/{project_id}/status", response_model=ProjectStatusResponse)
def get_project_status(project_id: uuid.UUID, db: Session = Depends(get_db)):
    """Get live phase status by fetching manifest from git."""
    project = db.query(Project).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project {project_id} not found")

    reader = _get_reader()
    try:
        owner, repo = parse_repo_url(project.repo_url)
        manifest = reader.fetch_manifest(owner, repo, project.branch)
    except (ValueError, GitRepoReaderError) as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Failed to fetch manifest: {e}")

    _cache_status(project, manifest)
    db.commit()

    lifecycle = manifest.get("lifecycle", {})
    phases = lifecycle.get("phases", {})
    return ProjectStatusResponse(
        current_phase=lifecycle.get("current_phase", "intake"),
        phase_statuses={name: p.get("status", "pending") for name, p in phases.items()},
        next_action=PhaseEngine.get_next_action(manifest),
        deployment_mode=manifest.get("project", {}).get("deployment_mode", "rhdp_published"),
    )


@router.get("/{project_id}/gates", response_model=List[GateRecordResponse])
def get_project_gates(project_id: uuid.UUID, db: Session = Depends(get_db)):
    """Get gate history (custody chain) for a project."""
    project = db.query(Project).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project {project_id} not found")

    history = GateService.get_history(db, project.id)
    return [GateRecordResponse(**r) for r in history]


@router.post("/{project_id}/refresh", response_model=CentralProjectResponse)
def refresh_project(project_id: uuid.UUID, db: Session = Depends(get_db)):
    """Refresh a project by re-fetching its manifest from git."""
    project = db.query(Project).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project {project_id} not found")

    reader = _get_reader()
    try:
        owner, repo = parse_repo_url(project.repo_url)
        manifest = reader.fetch_manifest(owner, repo, project.branch)
    except (ValueError, GitRepoReaderError) as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Failed to refresh: {e}")

    project_meta = manifest.get("project", {})
    project.name = project_meta.get("name") or project.name
    project.owner_github = project_meta.get("owner_github") or project_meta.get("owner") or project.owner_github
    project.owner_email = project_meta.get("owner_email") or project.owner_email
    project.deployment_mode = project_meta.get("deployment_mode") or project.deployment_mode
    _cache_status(project, manifest)
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: uuid.UUID, db: Session = Depends(get_db)):
    """Delete a project registration."""
    project = db.query(Project).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project {project_id} not found")
    db.delete(project)
    db.commit()


@router.get("/{project_id}/worklog")
def get_project_worklog(project_id: uuid.UUID, db: Session = Depends(get_db)):
    """Get worklog entries for a project."""
    from app.models.worklog import WorklogEntry
    project = db.query(Project).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project {project_id} not found")
    entries = db.query(WorklogEntry).filter_by(project_id=project_id).order_by(WorklogEntry.timestamp.desc()).all()
    return [{"id": str(e.id), "entry_id": e.entry_id, "timestamp": e.timestamp.isoformat() if e.timestamp else None,
             "author": e.author, "status": e.status, "type": e.type, "content": e.content,
             "resolved_at": e.resolved_at.isoformat() if e.resolved_at else None, "resolved_by": e.resolved_by} for e in entries]


@router.get("/{project_id}/launch")
def get_project_launch(project_id: uuid.UUID, db: Session = Depends(get_db)):
    """Get launch instructions derived from cached manifest data."""
    from app.services.launch_instructions import get_launch_instructions
    project = db.query(Project).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project {project_id} not found")
    if not project.cached_manifest_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No manifest data cached yet — try refreshing")
    return get_launch_instructions(project.cached_manifest_data)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd src/backend && python -m pytest tests/test_api_projects_central.py -v`
Expected: PASS

- [ ] **Step 5: Run full backend test suite**

Run: `cd src/backend && python -m pytest tests/ -v --timeout=30`
Expected: Some old tests in `test_api_projects.py` may fail because the API shape changed. That's expected — those tests test the old schema. Either update them to match the new schema or delete them if they're fully superseded by `test_api_projects_central.py`.

- [ ] **Step 6: Commit**

```bash
git add src/backend/app/api/projects.py src/backend/tests/test_api_projects_central.py
git commit -m "Rewrite projects REST API for Central data model"
```

---

### Task 4: Update periodic sync to cache phase statuses

**Files:**
- Modify: `src/backend/app/services/refresh.py`
- Test: `src/backend/tests/test_refresh_central.py`

**Interfaces:**
- Consumes: `GitRepoReader.fetch_manifest(owner, repo, ref) -> dict`, `PhaseEngine.get_next_action(manifest) -> dict`, `parse_repo_url(url) -> tuple[str, str]`, `Project` model with cached fields from Task 1
- Produces: `refresh_project(db, project, github_token, force) -> None` (updated to populate cached fields), `refresh_all_projects(db, github_token, force) -> None` (unchanged interface)

- [ ] **Step 1: Write the failing test**

Create `src/backend/tests/test_refresh_central.py`:

```python
"""Test that refresh populates cached status fields."""
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from app.models.project import Project
from app.services.refresh import refresh_project

SAMPLE_MANIFEST = {
    "project": {
        "name": "Refreshed Workshop",
        "owner_github": "stencell",
        "deployment_mode": "rhdp_published",
    },
    "lifecycle": {
        "current_phase": "writing",
        "phases": {
            "intake": {"status": "completed"},
            "vetting": {"status": "completed"},
            "writing": {"status": "in_progress"},
            "automation": {"status": "pending"},
        },
    },
}


@patch("app.services.refresh.GitRepoReader")
def test_refresh_populates_cached_fields(mock_reader_cls, db_session):
    reader_instance = MagicMock()
    reader_instance.fetch_manifest.return_value = SAMPLE_MANIFEST
    mock_reader_cls.return_value = reader_instance

    project = Project(
        name="Old Name",
        repo_url="git@github.com:rhpds/test.git",
        branch="main",
    )
    db_session.add(project)
    db_session.commit()

    refresh_project(db_session, project, github_token="fake-token", force=True)

    db_session.refresh(project)
    assert project.cached_current_phase == "writing"
    assert project.cached_phase_statuses["intake"] == "completed"
    assert project.cached_phase_statuses["writing"] == "in_progress"
    assert project.cached_next_action is not None
    assert project.cached_next_action["action"] == "continue"
    assert project.cached_manifest_data is not None
    assert project.cached_at is not None
    assert project.name == "Refreshed Workshop"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/backend && python -m pytest tests/test_refresh_central.py -v`
Expected: FAIL — current `refresh_project` doesn't populate cached fields

- [ ] **Step 3: Rewrite refresh service**

Replace `src/backend/app/services/refresh.py` with:

```python
"""Refresh service — fetches manifests from git and caches status."""
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Semaphore

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.project import Project
from app.services.git_repo_reader import GitRepoReader, GitRepoReaderError, parse_repo_url
from app.services.phase_engine import PhaseEngine

logger = logging.getLogger(__name__)

_refresh_semaphore = Semaphore(10)


def refresh_project(
    db: Session,
    project: Project,
    github_token: str,
    force: bool = False,
) -> None:
    """Refresh a project's cached status from git.

    Fetches the manifest via GitRepoReader, runs PhaseEngine, and
    stores computed status + full manifest on the project record.
    """
    try:
        owner, repo = parse_repo_url(project.repo_url)
        reader = GitRepoReader(token=github_token)
        manifest = reader.fetch_manifest(owner, repo, project.branch)

        lifecycle = manifest.get("lifecycle", {})
        phases = lifecycle.get("phases", {})

        project_meta = manifest.get("project", {})
        project.name = project_meta.get("name") or project.name
        project.owner_github = project_meta.get("owner_github") or project_meta.get("owner") or project.owner_github
        project.owner_email = project_meta.get("owner_email") or project.owner_email
        project.deployment_mode = project_meta.get("deployment_mode") or project.deployment_mode

        project.cached_phase_statuses = {name: p.get("status", "pending") for name, p in phases.items()}
        project.cached_current_phase = lifecycle.get("current_phase", "intake")
        project.cached_next_action = PhaseEngine.get_next_action(manifest)
        project.cached_manifest_data = manifest
        project.cached_at = datetime.now(timezone.utc)
        project.last_synced_at = datetime.now(timezone.utc)

        db.commit()

    except (ValueError, GitRepoReaderError) as e:
        logger.warning("Failed to refresh %s@%s: %s", project.repo_url, project.branch, e)
    except Exception:
        logger.exception("Unexpected error refreshing %s@%s", project.repo_url, project.branch)
        db.rollback()


def _refresh_single(project_id, github_token: str, force: bool = False) -> None:
    """Refresh a single project in its own DB session (thread-safe)."""
    with _refresh_semaphore:
        db = SessionLocal()
        try:
            project = db.query(Project).get(project_id)
            if project:
                refresh_project(db, project, github_token, force=force)
        finally:
            db.close()


def refresh_all_projects(
    db: Session,
    github_token: str,
    force: bool = False,
) -> None:
    """Refresh all registered projects in parallel."""
    projects = db.query(Project).all()
    project_ids = [p.id for p in projects]

    if not project_ids:
        return

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(_refresh_single, pid, github_token, force)
            for pid in project_ids
        ]
        for future in futures:
            future.result()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd src/backend && python -m pytest tests/test_refresh_central.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/backend/app/services/refresh.py src/backend/tests/test_refresh_central.py
git commit -m "Update refresh service to cache phase statuses via PhaseEngine"
```

---

### Task 5: Frontend types and API client

**Files:**
- Modify: `src/frontend/src/types/index.ts`
- Modify: `src/frontend/src/services/api.ts`

**Interfaces:**
- Consumes: REST endpoints from Task 3
- Produces: `CentralProject` type, `GateRecord` type, `ProjectStatus` type, `ProjectCreate` type, `PIPELINE_COLUMNS` config array, `api` object with methods: `listProjects() -> CentralProject[]`, `getProject(id) -> CentralProject`, `registerProject(data) -> CentralProject`, `refreshProject(id) -> CentralProject`, `deleteProject(id) -> void`, `getProjectStatus(id) -> ProjectStatus`, `getProjectGates(id) -> GateRecord[]`

- [ ] **Step 1: Rewrite types**

Replace `src/frontend/src/types/index.ts` with:

```typescript
export interface CentralProject {
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

export interface GateRecord {
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

export interface ProjectStatus {
  current_phase: string;
  phase_statuses: Record<string, string>;
  next_action: { next_phase: string | null; action: string; detail: string };
  deployment_mode: string;
}

export interface ProjectCreate {
  repo_url: string;
  branch?: string;
}

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

export interface LaunchInstructions {
  deployment_mode: string;
  description: string;
  steps: { step: number; action: string; url?: string; value?: string; detail?: string }[];
  showroom_repo?: string;
  automation_repo?: string;
}

export type ColumnStyle = "standard" | "iterative" | "parallel";

export interface PipelineColumnDef {
  id: string;
  label: string;
  phases: readonly string[];
  style: ColumnStyle;
  color: string;
}

export const PIPELINE_COLUMNS: readonly PipelineColumnDef[] = [
  { id: "intake", label: "Intake", phases: ["intake"], style: "standard", color: "#4dabf7" },
  { id: "vetting", label: "Vetting / Spec", phases: ["vetting", "spec_refinement"], style: "iterative", color: "#ffd43b" },
  { id: "approval", label: "Approval", phases: ["approval"], style: "standard", color: "#a9e34b" },
  { id: "development", label: "Writing + Automation", phases: ["writing", "automation"], style: "parallel", color: "#69db7c" },
  { id: "review", label: "Review", phases: ["editing", "code_security_review"], style: "standard", color: "#e599f7" },
  { id: "ready", label: "Ready", phases: ["final_review", "ready_for_publishing"], style: "standard", color: "#20c997" },
] as const;
```

- [ ] **Step 2: Rewrite API client**

Replace `src/frontend/src/services/api.ts` with:

```typescript
import type { CentralProject, ProjectCreate, GateRecord, ProjectStatus, WorklogEntry, LaunchInstructions } from "@/types";

const API_BASE = "/api/v1";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`API error ${response.status}: ${errorText}`);
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

export const api = {
  listProjects: () => request<CentralProject[]>("/projects"),
  getProject: (id: string) => request<CentralProject>(`/projects/${id}`),
  registerProject: (data: ProjectCreate) =>
    request<CentralProject>("/projects", { method: "POST", body: JSON.stringify(data) }),
  refreshProject: (id: string) =>
    request<CentralProject>(`/projects/${id}/refresh`, { method: "POST" }),
  deleteProject: (id: string) =>
    request<void>(`/projects/${id}`, { method: "DELETE" }),
  getProjectStatus: (id: string) =>
    request<ProjectStatus>(`/projects/${id}/status`),
  getProjectGates: (id: string) =>
    request<GateRecord[]>(`/projects/${id}/gates`),
  getWorklog: (projectId: string, status?: "open" | "resolved") =>
    request<WorklogEntry[]>(`/projects/${projectId}/worklog${status ? `?status=${status}` : ""}`),
  getLaunchInstructions: (projectId: string) =>
    request<LaunchInstructions>(`/projects/${projectId}/launch`),
};
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd src/frontend && npx tsc --noEmit 2>&1 | head -30`
Expected: Type errors in components that still reference old types (`Project`, `Phase`, `KANBAN_COLUMNS`). That's expected — Tasks 6-9 fix those.

- [ ] **Step 4: Commit**

```bash
git add src/frontend/src/types/index.ts src/frontend/src/services/api.ts
git commit -m "Rewrite frontend types and API client for Central data model"
```

---

### Task 6: Pipeline board (kanban) rewrite

**Files:**
- Modify: `src/frontend/src/app/pipeline/page.tsx`
- Modify: `src/frontend/src/components/KanbanColumn.tsx`
- Modify: `src/frontend/src/components/ProjectCard.tsx`

**Interfaces:**
- Consumes: `CentralProject`, `PIPELINE_COLUMNS`, `PipelineColumnDef` from Task 5. `api.listProjects()` from Task 5.
- Produces: `PipelinePage` component, `KanbanColumn` component (props: `column: PipelineColumnDef`, `projects: CentralProject[]`), `ProjectCard` component (props: `project: CentralProject`, `columnStyle: ColumnStyle`)

- [ ] **Step 1: Rewrite ProjectCard**

Replace `src/frontend/src/components/ProjectCard.tsx` with:

```tsx
"use client";
import Link from "next/link";
import { Label } from "@patternfly/react-core";
import type { CentralProject, ColumnStyle } from "@/types";

interface ProjectCardProps {
  project: CentralProject;
  columnStyle: ColumnStyle;
}

function formatPhaseStatus(status: string): string {
  return status.replace(/_/g, " ");
}

export default function ProjectCard({ project, columnStyle }: ProjectCardProps) {
  const statuses = project.cached_phase_statuses || {};

  return (
    <Link href={`/projects/${project.id}`} style={{ textDecoration: "none", color: "inherit" }}>
      <div style={{
        background: "rgba(255,255,255,0.06)",
        borderRadius: 6,
        padding: "0.5rem",
        fontSize: "0.8rem",
        marginBottom: "0.4rem",
        borderLeft: "3px solid rgba(255,255,255,0.15)",
        cursor: "pointer",
      }}>
        <div style={{ fontWeight: 600, marginBottom: "0.2rem" }}>{project.name}</div>
        <div style={{ color: "#888", fontSize: "0.7rem", marginBottom: "0.3rem" }}>
          {project.owner_github || "—"}
        </div>

        {project.deployment_mode && (
          <Label isCompact style={{ fontSize: "0.6rem", marginBottom: "0.3rem" }}>
            {project.deployment_mode}
          </Label>
        )}

        {columnStyle === "parallel" && (
          <div style={{ display: "flex", gap: "0.4rem", marginTop: "0.3rem", fontSize: "0.65rem" }}>
            <div style={{ flex: 1 }}>
              <div style={{ color: "#69db7c" }}>Writing</div>
              <div style={{ color: "#888" }}>{formatPhaseStatus(statuses["writing"] || "pending")}</div>
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ color: "#ff8787" }}>Automation</div>
              <div style={{ color: "#888" }}>{formatPhaseStatus(statuses["automation"] || "pending")}</div>
            </div>
          </div>
        )}

        {columnStyle === "iterative" && project.cached_next_action?.detail && (
          <div style={{ fontSize: "0.6rem", color: "#ffd43b", marginTop: "0.2rem" }}>
            {project.cached_next_action.detail.length > 60
              ? project.cached_next_action.detail.slice(0, 60) + "…"
              : project.cached_next_action.detail}
          </div>
        )}
      </div>
    </Link>
  );
}
```

- [ ] **Step 2: Rewrite KanbanColumn**

Replace `src/frontend/src/components/KanbanColumn.tsx` with:

```tsx
"use client";
import type { CentralProject, PipelineColumnDef } from "@/types";
import ProjectCard from "@/components/ProjectCard";

interface KanbanColumnProps {
  column: PipelineColumnDef;
  projects: CentralProject[];
}

const STYLE_BADGES: Record<string, { label: string; bg: string }> = {
  iterative: { label: "ITERATIVE", bg: "rgba(255,212,59,0.3)" },
  parallel: { label: "PARALLEL", bg: "rgba(105,219,124,0.3)" },
};

export default function KanbanColumn({ column, projects }: KanbanColumnProps) {
  const badge = STYLE_BADGES[column.style];

  return (
    <div style={{
      flex: column.style === "standard" ? 1 : 1.4,
      minWidth: column.style === "standard" ? 110 : 160,
      background: `${column.color}15`,
      borderRadius: 8,
      padding: "0.5rem",
    }}>
      <div style={{
        fontSize: "0.7rem",
        fontWeight: 700,
        color: column.color,
        textTransform: "uppercase",
        marginBottom: "0.5rem",
        display: "flex",
        alignItems: "center",
        gap: "0.3rem",
      }}>
        {column.label}
        {badge && (
          <span style={{
            fontSize: "0.55rem",
            background: badge.bg,
            padding: "1px 5px",
            borderRadius: 3,
          }}>
            {badge.label}
          </span>
        )}
        {projects.length > 0 && (
          <span style={{ fontSize: "0.6rem", color: "#888", marginLeft: "auto" }}>
            {projects.length}
          </span>
        )}
      </div>
      {projects.map((p) => (
        <ProjectCard key={p.id} project={p} columnStyle={column.style} />
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Rewrite pipeline page**

Replace `src/frontend/src/app/pipeline/page.tsx` with:

```tsx
"use client";
import { useEffect, useState } from "react";
import { PageSection, Content, Spinner, EmptyState, EmptyStateBody, Button } from "@patternfly/react-core";
import Link from "next/link";
import { api } from "@/services/api";
import type { CentralProject } from "@/types";
import { PIPELINE_COLUMNS } from "@/types";
import KanbanColumn from "@/components/KanbanColumn";

function getColumnId(project: CentralProject): string {
  const statuses = project.cached_phase_statuses || {};

  for (let i = PIPELINE_COLUMNS.length - 1; i >= 0; i--) {
    const col = PIPELINE_COLUMNS[i];
    const hasActive = col.phases.some((p) => statuses[p] === "in_progress");
    if (hasActive) return col.id;
  }

  for (let i = PIPELINE_COLUMNS.length - 1; i >= 0; i--) {
    const col = PIPELINE_COLUMNS[i];
    const hasCompleted = col.phases.some((p) => statuses[p] === "completed");
    if (hasCompleted) return col.id;
  }

  return "intake";
}

export default function PipelinePage() {
  const [projects, setProjects] = useState<CentralProject[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.listProjects().then(setProjects).catch(console.error).finally(() => setLoading(false));
  }, []);

  if (loading) return <PageSection><Spinner /></PageSection>;

  if (projects.length === 0) {
    return (
      <PageSection>
        <EmptyState>
          <Content><Content component="h1">No projects in the pipeline</Content></Content>
          <EmptyStateBody>Register a project to see it on the board.</EmptyStateBody>
          <Link href="/register"><Button variant="primary">Register Project</Button></Link>
        </EmptyState>
      </PageSection>
    );
  }

  const columnProjects: Record<string, CentralProject[]> = {};
  for (const col of PIPELINE_COLUMNS) columnProjects[col.id] = [];
  for (const project of projects) {
    const colId = getColumnId(project);
    columnProjects[colId]?.push(project);
  }

  return (
    <>
      <PageSection><Content><Content component="h1">Pipeline</Content></Content></PageSection>
      <PageSection>
        <div style={{ display: "flex", gap: "0.75rem", minHeight: 400, overflowX: "auto" }}>
          {PIPELINE_COLUMNS.map((col) => (
            <KanbanColumn key={col.id} column={col} projects={columnProjects[col.id]} />
          ))}
        </div>
      </PageSection>
    </>
  );
}
```

- [ ] **Step 4: Verify TypeScript compiles for these files**

Run: `cd src/frontend && npx tsc --noEmit 2>&1 | grep -E "(pipeline|KanbanColumn|ProjectCard)" | head -10`
Expected: No errors from these three files. Other files may still have errors (fixed in later tasks).

- [ ] **Step 5: Commit**

```bash
git add src/frontend/src/app/pipeline/page.tsx src/frontend/src/components/KanbanColumn.tsx src/frontend/src/components/ProjectCard.tsx
git commit -m "Rewrite pipeline board with 6-column data-driven kanban"
```

---

### Task 7: Project detail page rewrite

**Files:**
- Modify: `src/frontend/src/app/projects/[id]/page.tsx`
- Modify: `src/frontend/src/components/PhaseProgressBar.tsx`
- Modify: `src/frontend/src/components/PhaseAccordion.tsx`
- Modify: `src/frontend/src/components/ArtifactsList.tsx`

**Interfaces:**
- Consumes: `CentralProject`, `GateRecord`, `PIPELINE_COLUMNS` from Task 5. `api.getProject(id)`, `api.refreshProject(id)`, `api.deleteProject(id)`, `api.getProjectGates(id)` from Task 5.
- Produces: `ProjectDetailPage` component, `PhaseProgressBar` (props: `phaseStatuses: Record<string, string>`, `currentPhase: string | null`), `PhaseAccordion` (props: `phaseName: string`, `status: string`, `gates: GateRecord[]`, `artifacts: ArtifactItem[]`, `repoUrl: string`, `branch: string`), `ArtifactsList` (props: `project: CentralProject`)

- [ ] **Step 1: Rewrite PhaseProgressBar**

Replace `src/frontend/src/components/PhaseProgressBar.tsx` with:

```tsx
"use client";

interface PhaseProgressBarProps {
  phaseStatuses: Record<string, string>;
  currentPhase: string | null;
  onPhaseClick?: (phase: string) => void;
}

const STATUS_COLORS: Record<string, string> = {
  completed: "#20c997",
  in_progress: "#ffd43b",
  pending: "#333",
  skipped: "#555",
};

export default function PhaseProgressBar({ phaseStatuses, currentPhase, onPhaseClick }: PhaseProgressBarProps) {
  const phases = Object.entries(phaseStatuses);
  if (phases.length === 0) return null;

  return (
    <div style={{ display: "flex", gap: "0.25rem", alignItems: "center" }}>
      {phases.map(([name, status]) => {
        const isCurrent = name === currentPhase;
        const color = STATUS_COLORS[status] || STATUS_COLORS.pending;

        return (
          <div
            key={name}
            onClick={() => onPhaseClick?.(name)}
            style={{
              flex: 1,
              height: isCurrent ? 10 : 6,
              background: color,
              borderRadius: 3,
              cursor: onPhaseClick ? "pointer" : "default",
              opacity: status === "pending" ? 0.4 : 1,
              transition: "height 0.2s ease",
            }}
            title={`${name.replace(/_/g, " ")}: ${status}`}
          />
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Rewrite PhaseAccordion**

Replace `src/frontend/src/components/PhaseAccordion.tsx` with:

```tsx
"use client";
import { useState } from "react";
import { Label } from "@patternfly/react-core";
import type { GateRecord } from "@/types";

interface ArtifactItem {
  path: string;
  label?: string;
}

interface PhaseAccordionProps {
  phaseName: string;
  status: string;
  gates: GateRecord[];
  artifacts: ArtifactItem[];
  repoUrl: string;
  branch: string;
}

function toHttpsUrl(repoUrl: string): string {
  return repoUrl.replace(/^git@github\.com:/, "https://github.com/").replace(/\.git$/, "");
}

function githubFileUrl(repoUrl: string, branch: string, path: string): string {
  return `${toHttpsUrl(repoUrl)}/blob/${branch}/${path}`;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

const STATUS_COLORS: Record<string, string> = {
  completed: "#20c997",
  in_progress: "#ffd43b",
  pending: "#666",
  skipped: "#888",
};

const GATE_RESULT_COLORS: Record<string, string> = {
  approved: "#20c997",
  rejected: "#ff6b6b",
  overridden: "#ffd43b",
};

export default function PhaseAccordion({ phaseName, status, gates, artifacts, repoUrl, branch }: PhaseAccordionProps) {
  const [expanded, setExpanded] = useState(false);
  const latestGate = gates.length > 0 ? gates[gates.length - 1] : null;
  const statusColor = STATUS_COLORS[status] || "#666";

  return (
    <div style={{
      background: "rgba(255,255,255,0.03)",
      borderRadius: 6,
      borderLeft: `3px solid ${statusColor}`,
      marginBottom: "0.5rem",
    }}>
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          padding: "0.6rem 0.8rem",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <span style={{ fontSize: "0.85rem", fontWeight: 500 }}>
            {phaseName.replace(/_/g, " ")}
          </span>
          <Label isCompact color={status === "completed" ? "green" : status === "in_progress" ? "gold" : "grey"}>
            {status.replace(/_/g, " ")}
          </Label>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          {latestGate && (
            <span style={{ fontSize: "0.65rem", color: GATE_RESULT_COLORS[latestGate.result] || "#888" }}>
              gate: {latestGate.result}
            </span>
          )}
          <span style={{ color: "#555", fontSize: "0.75rem" }}>{expanded ? "▾" : "▸"}</span>
        </div>
      </div>

      {expanded && (
        <div style={{ padding: "0 0.8rem 0.6rem", fontSize: "0.8rem" }}>
          {/* Gate history */}
          {gates.length > 0 && (
            <div style={{ marginBottom: "0.5rem" }}>
              <div style={{ fontSize: "0.65rem", color: "#888", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.3rem" }}>
                Gate History
              </div>
              {gates.map((g) => (
                <div key={g.gate_id} style={{
                  padding: "0.3rem 0.5rem",
                  background: "rgba(255,255,255,0.03)",
                  borderRadius: 4,
                  marginBottom: "0.25rem",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}>
                  <div>
                    <span style={{ color: GATE_RESULT_COLORS[g.result] || "#888", fontWeight: 600, fontSize: "0.75rem" }}>
                      {g.result.toUpperCase()}
                    </span>
                    {g.override && <Label isCompact color="gold" style={{ marginLeft: "0.3rem", fontSize: "0.55rem" }}>OVERRIDE</Label>}
                    <span style={{ color: "#888", marginLeft: "0.5rem", fontSize: "0.7rem" }}>
                      {g.reason.length > 80 ? g.reason.slice(0, 80) + "…" : g.reason}
                    </span>
                  </div>
                  <div style={{ fontSize: "0.65rem", color: "#666", whiteSpace: "nowrap" }}>
                    {g.requested_by && <span>{g.requested_by} · </span>}
                    {formatDate(g.created_at)}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Artifacts */}
          {artifacts.length > 0 && (
            <div>
              <div style={{ fontSize: "0.65rem", color: "#888", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.3rem" }}>
                Artifacts
              </div>
              {artifacts.map((a, i) => (
                <div key={`${a.path}-${i}`} style={{ marginBottom: "0.15rem" }}>
                  <a
                    href={a.path.startsWith("http") ? a.path : githubFileUrl(repoUrl, branch, a.path)}
                    target="_blank"
                    rel="noopener"
                    style={{ color: "var(--accent-blue, #73bcf7)", fontSize: "0.75rem" }}
                  >
                    {a.label || a.path}
                  </a>
                </div>
              ))}
            </div>
          )}

          {gates.length === 0 && artifacts.length === 0 && (
            <div style={{ color: "#555", fontSize: "0.75rem" }}>No gate records or artifacts for this phase.</div>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Update ArtifactsList for new data source**

Replace `src/frontend/src/components/ArtifactsList.tsx` with:

```tsx
"use client";
import type { CentralProject } from "@/types";

interface ArtifactsListProps {
  project: CentralProject;
}

interface ArtifactItem {
  path: string;
  label?: string;
  type: "document" | "automation" | "review" | "content" | "other";
  phaseName: string;
}

function toHttpsUrl(repoUrl: string): string {
  return repoUrl.replace(/^git@github\.com:/, "https://github.com/").replace(/\.git$/, "");
}

function githubFileUrl(repoUrl: string, branch: string, path: string): string {
  return `${toHttpsUrl(repoUrl)}/blob/${branch}/${path}`;
}

function classifyArtifact(path: string, phaseName: string): ArtifactItem["type"] {
  const lower = path.toLowerCase();
  if (lower.includes("review") || lower.includes("feedback")) return "review";
  if (lower.includes("automation") || lower.includes("ansible") || lower.includes("playbook")) return "automation";
  if (lower.endsWith(".adoc") || lower.endsWith(".md") || lower.includes("content/")) return "content";
  if (phaseName === "automation") return "automation";
  if (phaseName === "writing") return "content";
  if (["editing", "code_security_review", "final_review"].includes(phaseName)) return "review";
  return "document";
}

const TYPE_LABELS: Record<string, string> = {
  document: "Documents", automation: "Automation", review: "Reviews", content: "Content", other: "Other",
};

const TYPE_COLORS: Record<string, string> = {
  document: "var(--lcars-amber, #FF9900)", automation: "var(--lcars-red, #ff8787)",
  review: "var(--lcars-purple, #9966CC)", content: "var(--lcars-green, #69db7c)", other: "var(--text-muted, #888)",
};

function extractArtifacts(project: CentralProject): ArtifactItem[] {
  const manifest = project.cached_manifest_data;
  if (!manifest) return [];

  const lifecycle = manifest.lifecycle as Record<string, unknown> | undefined;
  if (!lifecycle) return [];

  const phases = lifecycle.phases as Record<string, Record<string, unknown>> | undefined;
  if (!phases) return [];

  const items: ArtifactItem[] = [];
  for (const [phaseName, phaseData] of Object.entries(phases)) {
    const artifacts = (phaseData.artifacts as string[] | undefined) || [];
    for (const path of artifacts) {
      items.push({ path, phaseName, type: classifyArtifact(path, phaseName) });
    }

    const modules = phaseData.modules as Array<Record<string, string>> | undefined;
    if (modules) {
      for (const mod of modules) {
        if (mod.content_path) {
          items.push({ path: mod.content_path, label: `${mod.title} (content)`, phaseName, type: "content" });
        }
      }
    }
  }
  return items;
}

export default function ArtifactsList({ project }: ArtifactsListProps) {
  const allItems = extractArtifacts(project);

  if (allItems.length === 0) {
    return (
      <div style={{ padding: "2rem", textAlign: "center", color: "var(--text-muted, #888)" }}>
        No artifacts found across project phases.
      </div>
    );
  }

  const byPhase: Record<string, ArtifactItem[]> = {};
  const byType: Record<string, number> = {};
  for (const item of allItems) {
    (byPhase[item.phaseName] ||= []).push(item);
    byType[item.type] = (byType[item.type] || 0) + 1;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
        {Object.entries(byType).map(([type, count]) => (
          <span key={type} style={{
            fontSize: "0.75rem", fontWeight: 600, color: TYPE_COLORS[type] || "#888",
            background: "rgba(255,255,255,0.04)", padding: "0.2rem 0.6rem", borderRadius: "4px",
            borderLeft: `2px solid ${TYPE_COLORS[type] || "#888"}`,
          }}>
            {count} {TYPE_LABELS[type] || type}
          </span>
        ))}
      </div>

      {Object.entries(byPhase).map(([phaseName, items]) => (
        <div key={phaseName} style={{
          background: "rgba(255,255,255,0.03)", borderRadius: 6,
          borderLeft: "3px solid rgba(255,255,255,0.1)", padding: "0.7rem 0.85rem",
        }}>
          <div style={{ fontSize: "0.72rem", color: "#666", textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: "0.4rem" }}>
            {phaseName.replace(/_/g, " ")}
          </div>
          {items.map((item, i) => (
            <div key={`${item.path}-${i}`} style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem", marginBottom: "0.2rem" }}>
              <a
                href={item.path.startsWith("http") ? item.path : githubFileUrl(project.repo_url, project.branch, item.path)}
                target="_blank" rel="noopener" style={{ color: "var(--accent-blue, #73bcf7)" }}
              >
                {item.label || item.path}
              </a>
              <span style={{ fontSize: "0.65rem", color: TYPE_COLORS[item.type], textTransform: "uppercase" }}>
                {item.type}
              </span>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Rewrite project detail page**

Replace `src/frontend/src/app/projects/[id]/page.tsx` with:

```tsx
"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  PageSection, Content, Spinner, Label, Card, CardBody, Split, SplitItem,
  Tabs, Tab, TabTitleText, Badge,
  Dropdown, DropdownList, DropdownItem, MenuToggle, Divider,
  Modal, ModalBody, ModalHeader, ModalFooter, Button,
} from "@patternfly/react-core";
import { EllipsisVIcon } from "@patternfly/react-icons";
import { api } from "@/services/api";
import type { CentralProject, GateRecord } from "@/types";
import PhaseProgressBar from "@/components/PhaseProgressBar";
import PhaseAccordion from "@/components/PhaseAccordion";
import WorklogTimeline, { useOpenWorklogCount } from "@/components/WorklogTimeline";
import ArtifactsList from "@/components/ArtifactsList";
import LaunchInstructions from "@/components/LaunchInstructions";

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

function toHttpsUrl(repoUrl: string): string {
  return repoUrl.replace(/^git@github\.com:/, "https://github.com/").replace(/\.git$/, "");
}

function extractPhaseArtifacts(manifest: Record<string, unknown> | null, phaseName: string): Array<{ path: string; label?: string }> {
  if (!manifest) return [];
  const lifecycle = manifest.lifecycle as Record<string, unknown> | undefined;
  if (!lifecycle) return [];
  const phases = lifecycle.phases as Record<string, Record<string, unknown>> | undefined;
  if (!phases || !phases[phaseName]) return [];
  const phaseData = phases[phaseName];
  const artifacts: Array<{ path: string; label?: string }> = [];
  for (const path of (phaseData.artifacts as string[] | undefined) || []) {
    artifacts.push({ path });
  }
  return artifacts;
}

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;
  const [project, setProject] = useState<CentralProject | null>(null);
  const [gates, setGates] = useState<GateRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<string>("overview");
  const [kebabOpen, setKebabOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [expandedPhase, setExpandedPhase] = useState<string | null>(null);
  const [visitedTabs, setVisitedTabs] = useState<Set<string>>(new Set(["overview"]));

  const openCount = useOpenWorklogCount(projectId);

  useEffect(() => {
    Promise.all([
      api.getProject(projectId),
      api.getProjectGates(projectId),
    ]).then(([proj, g]) => {
      setProject(proj);
      setGates(g);
    }).catch(console.error).finally(() => setLoading(false));
  }, [projectId]);

  const handleRefresh = async () => {
    setKebabOpen(false);
    setRefreshing(true);
    try {
      const refreshed = await api.refreshProject(projectId);
      setProject(refreshed);
      setGates(await api.getProjectGates(projectId));
    } catch (err) { console.error("Refresh failed:", err); }
    finally { setRefreshing(false); }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try { await api.deleteProject(projectId); router.push("/projects"); }
    catch (err) { console.error("Delete failed:", err); }
    finally { setDeleting(false); setShowDeleteModal(false); }
  };

  const handleTabSelect = (_event: React.MouseEvent<HTMLElement, MouseEvent>, tabKey: string | number) => {
    const key = tabKey as string;
    setActiveTab(key);
    setVisitedTabs((prev) => new Set(prev).add(key));
  };

  if (loading) return <PageSection><Spinner /></PageSection>;
  if (!project) return <PageSection><Content><Content component="h1">Project not found</Content></Content></PageSection>;

  const phaseStatuses = project.cached_phase_statuses || {};
  const phaseNames = Object.keys(phaseStatuses);
  const integrations = (project.cached_manifest_data?.integrations || {}) as Record<string, string | null>;

  return (
    <>
      <PageSection>
        <Split hasGutter>
          <SplitItem isFilled>
            <Content><Content component="h1" style={{ marginBottom: "0.25rem" }}>{project.name}</Content></Content>
            <div style={{ display: "flex", gap: "0.75rem", fontSize: "0.85rem", color: "#888", alignItems: "center" }}>
              {project.deployment_mode && <Label isCompact>{project.deployment_mode}</Label>}
              <span>Owner: {project.owner_github || "—"}</span>
              <span>Branch: {project.branch}</span>
            </div>
          </SplitItem>
          <SplitItem>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span style={{ fontSize: "0.75rem", color: "#666" }}>
                {refreshing ? "Refreshing…" : `Last synced: ${formatDate(project.last_synced_at)}`}
              </span>
              <Dropdown isOpen={kebabOpen} onSelect={() => setKebabOpen(false)} onOpenChange={setKebabOpen}
                toggle={(toggleRef) => (
                  <MenuToggle ref={toggleRef} variant="plain" onClick={() => setKebabOpen(!kebabOpen)} isExpanded={kebabOpen} aria-label="Project actions">
                    <EllipsisVIcon />
                  </MenuToggle>
                )} popperProps={{ position: "end" }}>
                <DropdownList>
                  <DropdownItem key="refresh" onClick={handleRefresh} isDisabled={refreshing}>Refresh from GitHub</DropdownItem>
                  <Divider />
                  <DropdownItem key="delete" onClick={() => { setKebabOpen(false); setShowDeleteModal(true); }}
                    style={{ color: "var(--lcars-red, #ff8787)" }}>Delete project</DropdownItem>
                </DropdownList>
              </Dropdown>
            </div>
          </SplitItem>
        </Split>
      </PageSection>

      <PageSection style={{ paddingTop: 0 }}>
        <Tabs activeKey={activeTab} onSelect={handleTabSelect} style={{ marginBottom: "1rem" }}>
          <Tab eventKey="overview" title={<TabTitleText>Overview</TabTitleText>}>
            <div style={{ marginTop: "1rem" }}>
              <div style={{ marginBottom: "1.5rem" }}>
                <PhaseProgressBar
                  phaseStatuses={phaseStatuses}
                  currentPhase={project.cached_current_phase}
                  onPhaseClick={(phase) => setExpandedPhase(expandedPhase === phase ? null : phase)}
                />
              </div>
              <Split hasGutter>
                <SplitItem isFilled style={{ flex: 3 }}>
                  {phaseNames.map((name) => (
                    <PhaseAccordion
                      key={name}
                      phaseName={name}
                      status={phaseStatuses[name]}
                      gates={gates.filter((g) => g.phase === name)}
                      artifacts={extractPhaseArtifacts(project.cached_manifest_data, name)}
                      repoUrl={project.repo_url}
                      branch={project.branch}
                    />
                  ))}
                </SplitItem>
                <SplitItem style={{ flex: 2, minWidth: 250 }}>
                  <Card style={{ marginBottom: "0.75rem" }}>
                    <CardBody>
                      <div style={{ fontSize: "0.75rem", color: "#888", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.5rem" }}>Project Info</div>
                      <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem", fontSize: "0.85rem" }}>
                        {[
                          ["owner", project.owner_github || "—"],
                          ["mode", project.deployment_mode || "—"],
                          ["branch", project.branch],
                          ["registered", formatDate(project.registered_at)],
                        ].map(([key, val]) => (
                          <div key={key} style={{ display: "flex", justifyContent: "space-between" }}>
                            <span style={{ color: "#888" }}>{key}</span><span>{val}</span>
                          </div>
                        ))}
                      </div>
                    </CardBody>
                  </Card>
                  <Card style={{ marginBottom: "0.75rem" }}>
                    <CardBody>
                      <div style={{ fontSize: "0.75rem", color: "#888", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.5rem" }}>Links</div>
                      <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem", fontSize: "0.85rem" }}>
                        <a href={toHttpsUrl(project.repo_url)} target="_blank" rel="noopener">GitHub Repo</a>
                        {integrations.showroom_repo
                          ? <a href={integrations.showroom_repo} target="_blank" rel="noopener">Showroom</a>
                          : <span style={{ color: "#555" }}>Showroom — not set</span>}
                        {integrations.automation_repo
                          ? <a href={integrations.automation_repo} target="_blank" rel="noopener">Automation</a>
                          : <span style={{ color: "#555" }}>Automation — not set</span>}
                      </div>
                    </CardBody>
                  </Card>
                  {project.cached_next_action && (
                    <Card>
                      <CardBody>
                        <div style={{ fontSize: "0.75rem", color: "#888", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.5rem" }}>Next Action</div>
                        <div style={{ fontSize: "0.85rem" }}>
                          <Label isCompact color={project.cached_next_action.action === "blocked" ? "red" : "blue"}>
                            {project.cached_next_action.action}
                          </Label>
                          <div style={{ marginTop: "0.3rem", color: "#aaa" }}>{project.cached_next_action.detail}</div>
                        </div>
                      </CardBody>
                    </Card>
                  )}
                </SplitItem>
              </Split>
            </div>
          </Tab>

          <Tab eventKey="worklog" title={
            <TabTitleText>Worklog{" "}
              {openCount !== null && openCount > 0 && (
                <Badge style={{ backgroundColor: "var(--lcars-amber, #FF9900)", color: "var(--bg-primary, #0f1117)", marginLeft: "0.4rem", fontSize: "0.7rem", fontWeight: 700 }}>
                  {openCount}
                </Badge>
              )}
            </TabTitleText>
          }>
            <div style={{ marginTop: "1rem" }}>{visitedTabs.has("worklog") && <WorklogTimeline projectId={projectId} />}</div>
          </Tab>

          <Tab eventKey="artifacts" title={<TabTitleText>Artifacts</TabTitleText>}>
            <div style={{ marginTop: "1rem" }}>{visitedTabs.has("artifacts") && <ArtifactsList project={project} />}</div>
          </Tab>

          <Tab eventKey="launch" title={<TabTitleText>Launch</TabTitleText>}>
            <div style={{ marginTop: "1rem" }}>{visitedTabs.has("launch") && <LaunchInstructions projectId={projectId} />}</div>
          </Tab>
        </Tabs>
      </PageSection>

      {showDeleteModal && (
        <Modal isOpen onClose={() => setShowDeleteModal(false)} aria-label="Delete project" variant="small">
          <ModalHeader title="Delete Project" />
          <ModalBody>Are you sure you want to remove <strong>{project.name}</strong> from Central? This only removes the registration — it does not affect the repository.</ModalBody>
          <ModalFooter>
            <Button variant="danger" onClick={handleDelete} isLoading={deleting}>Delete</Button>
            <Button variant="link" onClick={() => setShowDeleteModal(false)}>Cancel</Button>
          </ModalFooter>
        </Modal>
      )}
    </>
  );
}
```

- [ ] **Step 5: Verify TypeScript compiles for modified files**

Run: `cd src/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: Errors only from files not yet updated (projects/page.tsx, register/page.tsx, layout.tsx). The files modified in this task should compile clean.

- [ ] **Step 6: Commit**

```bash
git add src/frontend/src/app/projects/\[id\]/page.tsx src/frontend/src/components/PhaseProgressBar.tsx src/frontend/src/components/PhaseAccordion.tsx src/frontend/src/components/ArtifactsList.tsx
git commit -m "Rewrite project detail page with gate drill-down and Central data"
```

---

### Task 8: Projects list page, register page, and naming updates

**Files:**
- Modify: `src/frontend/src/app/projects/page.tsx`
- Modify: `src/frontend/src/app/register/page.tsx`
- Modify: `src/frontend/src/app/layout.tsx`
- Delete or clear: `src/frontend/src/components/RefreshButton.tsx` (inlined into projects page)

**Interfaces:**
- Consumes: `CentralProject`, `ProjectCreate` from Task 5. `api.listProjects()`, `api.registerProject(data)`, `api.deleteProject(id)`, `api.refreshProject(id)` from Task 5.
- Produces: `ProjectsPage` component, `RegisterPage` component (with branch field), updated `RootLayout` with "Publishing House Central" title

- [ ] **Step 1: Rewrite projects list page**

Replace `src/frontend/src/app/projects/page.tsx` with:

```tsx
"use client";
import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  PageSection, Content, Toolbar, ToolbarContent, ToolbarItem,
  SearchInput, Label, Spinner, EmptyState, EmptyStateBody, Button,
  Modal, ModalBody, ModalHeader, ModalFooter,
} from "@patternfly/react-core";
import {
  Table, Thead, Tbody, Tr, Th, Td,
  OuterScrollContainer, InnerScrollContainer,
} from "@patternfly/react-table";
import SyncAltIcon from "@patternfly/react-icons/dist/esm/icons/sync-alt-icon";
import TrashIcon from "@patternfly/react-icons/dist/esm/icons/trash-icon";
import { api } from "@/services/api";
import type { CentralProject } from "@/types";
import PhaseProgressBar from "@/components/PhaseProgressBar";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<CentralProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [deleteProject, setDeleteProject] = useState<CentralProject | null>(null);
  const [deleting, setDeleting] = useState(false);

  const loadProjects = useCallback(async () => {
    try { setProjects(await api.listProjects()); }
    catch (error) { console.error("Failed to load projects:", error); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadProjects(); }, [loadProjects]);

  const handleRefresh = async (project: CentralProject) => {
    try { await api.refreshProject(project.id); loadProjects(); }
    catch (err) { console.error("Refresh failed:", err); }
  };

  const handleDelete = async () => {
    if (!deleteProject) return;
    setDeleting(true);
    try { await api.deleteProject(deleteProject.id); setDeleteProject(null); loadProjects(); }
    catch (err) { console.error("Delete failed:", err); }
    finally { setDeleting(false); }
  };

  const filtered = projects.filter((p) => p.name.toLowerCase().includes(search.toLowerCase()));

  if (loading) return <PageSection><Spinner /></PageSection>;

  if (projects.length === 0) {
    return (
      <PageSection>
        <EmptyState>
          <Content><Content component="h1">No projects registered</Content></Content>
          <EmptyStateBody>Register a project to start tracking its lifecycle.</EmptyStateBody>
          <Link href="/register"><Button variant="primary">Register Project</Button></Link>
        </EmptyState>
      </PageSection>
    );
  }

  return (
    <>
      <PageSection><Content><Content component="h1">Projects</Content></Content></PageSection>
      <PageSection>
        <Toolbar>
          <ToolbarContent>
            <ToolbarItem>
              <SearchInput placeholder="Search projects..." value={search} onChange={(_e, val) => setSearch(val)} onClear={() => setSearch("")} />
            </ToolbarItem>
            <ToolbarItem align={{ default: "alignEnd" }}><Label>{filtered.length} projects</Label></ToolbarItem>
          </ToolbarContent>
        </Toolbar>
        <OuterScrollContainer style={{ maxHeight: "calc(100vh - 280px)" }}>
          <InnerScrollContainer>
            <Table variant="compact" isStriped>
              <Thead>
                <Tr>
                  <Th width={25}>Project</Th>
                  <Th width={10}>Branch</Th>
                  <Th width={10}>Mode</Th>
                  <Th width={10}>Phase</Th>
                  <Th width={30} style={{ textAlign: "center" }}>Progress</Th>
                  <Th width={15} style={{ textAlign: "center" }}>Actions</Th>
                </Tr>
              </Thead>
              <Tbody>
                {filtered.map((project) => (
                  <Tr key={project.id}>
                    <Td><Link href={`/projects/${project.id}`} style={{ fontWeight: 500 }}>{project.name}</Link></Td>
                    <Td style={{ fontSize: "0.8rem", color: "#888" }}>{project.branch}</Td>
                    <Td>{project.deployment_mode ? <Label isCompact>{project.deployment_mode}</Label> : "—"}</Td>
                    <Td style={{ fontSize: "0.8rem" }}>{project.cached_current_phase?.replace(/_/g, " ") || "—"}</Td>
                    <Td style={{ textAlign: "center" }}>
                      {project.cached_phase_statuses
                        ? <PhaseProgressBar phaseStatuses={project.cached_phase_statuses} currentPhase={project.cached_current_phase} />
                        : <span style={{ color: "#555", fontSize: "0.8rem" }}>Not synced</span>}
                    </Td>
                    <Td style={{ textAlign: "center" }}>
                      <div style={{ display: "flex", gap: "0.25rem", justifyContent: "center" }}>
                        <Button variant="plain" aria-label="Refresh" onClick={() => handleRefresh(project)}><SyncAltIcon /></Button>
                        <Button variant="plain" aria-label="Delete" onClick={() => setDeleteProject(project)}
                          style={{ color: "var(--pf-t--global--color--nonstatus--red--default, #c9190b)" }}><TrashIcon /></Button>
                      </div>
                    </Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          </InnerScrollContainer>
        </OuterScrollContainer>
      </PageSection>

      {deleteProject && (
        <Modal isOpen onClose={() => setDeleteProject(null)} aria-label="Delete project" variant="small">
          <ModalHeader title="Delete Project" />
          <ModalBody>Are you sure you want to remove <strong>{deleteProject.name}</strong>?</ModalBody>
          <ModalFooter>
            <Button variant="danger" onClick={handleDelete} isLoading={deleting}>Delete</Button>
            <Button variant="link" onClick={() => setDeleteProject(null)}>Cancel</Button>
          </ModalFooter>
        </Modal>
      )}
    </>
  );
}
```

- [ ] **Step 2: Add branch field to register page**

Replace `src/frontend/src/app/register/page.tsx` with:

```tsx
"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  PageSection, Content, Form, FormGroup, FormHelperText, HelperText, HelperTextItem,
  TextInput, Button, Alert, Card, CardBody,
} from "@patternfly/react-core";
import { api } from "@/services/api";

export default function RegisterPage() {
  const router = useRouter();
  const [repoUrl, setRepoUrl] = useState("");
  const [branch, setBranch] = useState("main");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successName, setSuccessName] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessName(null);
    setLoading(true);
    try {
      const project = await api.registerProject({ repo_url: repoUrl, branch: branch || "main" });
      setSuccessName(project.name);
      setTimeout(() => router.push(`/projects/${project.id}`), 2000);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Registration failed";
      if (message.includes("400")) setError("This repo doesn't have a Publishing House manifest");
      else if (message.includes("409")) setError("This repository and branch are already registered");
      else setError(message);
    } finally { setLoading(false); }
  };

  return (
    <>
      <PageSection>
        <Content>
          <Content component="h1">Register Project</Content>
          <Content component="p">Register a project by providing its GitHub repository URL. Central will fetch the manifest and track lifecycle progress.</Content>
        </Content>
      </PageSection>
      <PageSection>
        <Card style={{ maxWidth: 600 }}>
          <CardBody>
            {error && <Alert variant="danger" title="Registration failed" isInline style={{ marginBottom: "1rem" }}>{error}</Alert>}
            {successName && <Alert variant="success" title="Project registered" isInline style={{ marginBottom: "1rem" }}>{`"${successName}" registered successfully. Redirecting...`}</Alert>}
            <Form onSubmit={handleSubmit}>
              <FormGroup label="GitHub Repository URL" isRequired fieldId="repo-url">
                <TextInput id="repo-url" value={repoUrl} onChange={(_e, val) => setRepoUrl(val)} placeholder="e.g., git@github.com:rhpds/my-workshop.git" isRequired />
                <FormHelperText><HelperText><HelperTextItem>SSH or HTTPS URL. Must contain publishing-house/manifest.yaml.</HelperTextItem></HelperText></FormHelperText>
              </FormGroup>
              <FormGroup label="Branch" fieldId="branch">
                <TextInput id="branch" value={branch} onChange={(_e, val) => setBranch(val)} placeholder="main" />
                <FormHelperText><HelperText><HelperTextItem>Defaults to main. Use a different branch for feature work.</HelperTextItem></HelperText></FormHelperText>
              </FormGroup>
              <Button type="submit" isDisabled={!repoUrl.trim() || !!successName} isLoading={loading}>Register</Button>
            </Form>
          </CardBody>
        </Card>
      </PageSection>
    </>
  );
}
```

- [ ] **Step 3: Update layout with new naming**

In `src/frontend/src/app/layout.tsx`, make these changes:

1. Replace `<Content component="h3" style={{ color: "white", margin: 0 }}>RHDP Publishing House</Content>` with `<Content component="h3" style={{ color: "white", margin: 0 }}>Publishing House Central</Content>`
2. Remove the subtitle line: delete the `<MastheadContent>` block containing "Content Lifecycle Portal"

The result for the masthead section should be:

```tsx
  const masthead = (
    <Masthead>
      <MastheadMain>
        <MastheadBrand>
          <Link href="/pipeline" style={{ display: "flex", alignItems: "center", gap: "0.75rem", textDecoration: "none" }}>
            <img src="/logo-full.svg" alt="Publishing House Central" style={{ height: 48 }} />
            <Content component="h3" style={{ color: "white", margin: 0 }}>Publishing House Central</Content>
          </Link>
        </MastheadBrand>
      </MastheadMain>
    </Masthead>
  );
```

Remove the `MastheadContent` import from the PatternFly import line if it's no longer used.

- [ ] **Step 4: Delete RefreshButton component (no longer needed)**

The RefreshButton was a standalone component for the old projects table. The new projects page inlines the refresh action. Delete `src/frontend/src/components/RefreshButton.tsx`.

- [ ] **Step 5: Verify full TypeScript compilation**

Run: `cd src/frontend && npx tsc --noEmit`
Expected: PASS — all files should compile cleanly. If there are errors from `Breadcrumbs.tsx` or `WorklogTimeline.tsx` referencing old types, fix the imports (they should only use `WorklogEntry` which is preserved in the new types).

- [ ] **Step 6: Commit**

```bash
git add src/frontend/src/app/projects/page.tsx src/frontend/src/app/register/page.tsx src/frontend/src/app/layout.tsx
git rm src/frontend/src/components/RefreshButton.tsx
git commit -m "Update projects list, register page, and naming to Publishing House Central"
```

---

### Task 9: Clean up old backend code and run full test suite

**Files:**
- Delete: `src/backend/tests/test_api_projects.py` (superseded by `test_api_projects_central.py`)
- Modify: `src/backend/app/main.py` (update title)

**Interfaces:**
- Consumes: all prior tasks
- Produces: clean test suite, updated app title

- [ ] **Step 1: Update app title in main.py**

In `src/backend/app/main.py`, change both `title=` strings from `"Publishing House Portal API"` to `"Publishing House Central API"`. Also update the `description` to `"API for Publishing House Central content lifecycle management"`.

- [ ] **Step 2: Remove old projects API test**

Delete `src/backend/tests/test_api_projects.py` — it tests the old `ProjectWithPhases` schema which no longer exists.

- [ ] **Step 3: Run full backend test suite**

Run: `cd src/backend && python -m pytest tests/ -v --timeout=30`
Expected: All tests pass. If any tests in other files (e.g., `test_api_validations.py`, `test_refresh.py`) fail because they depend on old schemas or the old `refresh_project` signature, fix them:
- Tests that import `ProjectWithPhases` → update to use `CentralProjectResponse`
- Tests that call the old `refresh_project` with the old `github_client.fetch_manifest` → update to mock `GitRepoReader` instead

- [ ] **Step 4: Run frontend build**

Run: `cd src/frontend && npm run build`
Expected: Build succeeds. This verifies that all TypeScript compiles and the Next.js build produces valid output.

- [ ] **Step 5: Commit**

```bash
git rm src/backend/tests/test_api_projects.py
git add src/backend/app/main.py
git commit -m "Clean up old tests and update app title to Publishing House Central"
```
