# PH Central Plan 1: GitRepoReader + Registration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Central can read project repos via GitHub API and register projects automatically with branch-level identity.

**Architecture:** Extend the existing `github_client.py` into a `GitRepoReader` class that fetches any file by path and ref. Add `branch` to the `Project` model so (repo_url, branch) is the identity key. Create `gate_tools.py` with `ph_register` and an updated `ph_list_projects`. Wire into `main.py`.

**Tech Stack:** FastAPI, SQLAlchemy, httpx, FastMCP 3.2+, Alembic, pytest

## Global Constraints

- Python 3.11+, all code under `src/backend/app/`
- MCP tools create their own `SessionLocal()` — no FastAPI dependency injection in tool functions
- Tests use SQLite in-memory (see `tests/conftest.py`)
- All models use UUID primary keys and timezone-aware datetimes
- `yaml.safe_load` always — never `yaml.load`
- GitHub API token from `settings.github_token`

---

### Task 1: Add `branch` to Project Model + Migration

**Files:**
- Modify: `src/backend/app/models/project.py`
- Create: `src/backend/alembic/versions/b1c2d3e4f5g6_add_branch_to_projects.py`
- Modify: `tests/conftest.py` — update SAMPLE_MANIFEST_YAML if needed

**Interfaces:**
- Produces: `Project.branch` column (String(255), default "main"), unique constraint on (repo_url, branch)

- [ ] **Step 1: Write the migration**

```python
# alembic/versions/b1c2d3e4f5g6_add_branch_to_projects.py
"""Add branch column to projects table.

Revision ID: b1c2d3e4f5g6
Revises: a1b2c3d4e5f6
Create Date: 2026-06-19
"""
from alembic import op
import sqlalchemy as sa

revision = "b1c2d3e4f5g6"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("branch", sa.String(255), nullable=False, server_default="main"))
    op.drop_constraint("projects_repo_url_key", "projects", type_="unique")
    op.create_unique_constraint("uq_projects_repo_branch", "projects", ["repo_url", "branch"])


def downgrade() -> None:
    op.drop_constraint("uq_projects_repo_branch", "projects", type_="unique")
    op.create_unique_constraint("projects_repo_url_key", "projects", ["repo_url"])
    op.drop_column("projects", "branch")
```

- [ ] **Step 2: Update the Project model**

In `src/backend/app/models/project.py`, add the `branch` column and update the unique constraint:

```python
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, DateTime, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("repo_url", "branch", name="uq_projects_repo_branch"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    repo_url: Mapped[str] = mapped_column(String(500), nullable=False)
    branch: Mapped[str] = mapped_column(String(255), nullable=False, default="main")
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_refreshed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    refresh_status: Mapped[str] = mapped_column(String(20), default="pending")
    refresh_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    deployment_mode: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    owner_github: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    owner_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    manifest = relationship("Manifest", back_populates="project", uselist=False, cascade="all, delete-orphan")
    phases = relationship("Phase", back_populates="project", cascade="all, delete-orphan")
    worklog_entries = relationship("WorklogEntry", back_populates="project", cascade="all, delete-orphan")
    validation_runs = relationship("ValidationRun", back_populates="project", cascade="all, delete-orphan")
```

- [ ] **Step 3: Verify migration applies locally**

Run: `cd src/backend && alembic upgrade head`
Expected: Migration applies cleanly, `branch` column added.

- [ ] **Step 4: Commit**

```bash
git add app/models/project.py alembic/versions/b1c2d3e4f5g6_add_branch_to_projects.py
git commit -m "model: Add branch to Project for branch-level identity"
```

---

### Task 2: GitRepoReader Service

**Files:**
- Create: `src/backend/app/services/git_repo_reader.py`
- Create: `src/backend/tests/test_git_repo_reader.py`

**Interfaces:**
- Consumes: `settings.github_token` from `app.core.config`
- Produces:
  - `GitRepoReader(token: str)` constructor
  - `GitRepoReader.fetch_file(owner: str, repo: str, path: str, ref: str) -> str | None`
  - `GitRepoReader.fetch_manifest(owner: str, repo: str, ref: str) -> dict`
  - `GitRepoReader.file_exists(owner: str, repo: str, path: str, ref: str) -> bool`
  - `parse_repo_url(repo_url: str) -> tuple[str, str]` — re-exported from github_client

- [ ] **Step 1: Write failing tests**

```python
# tests/test_git_repo_reader.py
"""Tests for GitRepoReader service.

Uses httpx mock transport to avoid real GitHub API calls.
"""
import httpx
import base64
import pytest
import yaml

from app.services.git_repo_reader import GitRepoReader, GitRepoReaderError


def _mock_github_response(content: str, status_code: int = 200):
    """Create a mock GitHub API contents response."""
    encoded = base64.b64encode(content.encode()).decode()
    return httpx.Response(
        status_code=status_code,
        json={"content": encoded, "encoding": "base64"} if status_code == 200 else {"message": "Not Found"},
    )


SAMPLE_MANIFEST = """\
project:
  name: Test Lab
  id: test-lab
  owner_github: testuser
  owner_name: Test User
  type: workshop
  showroom_type: classic
  deployment_mode: rhdp_published
  autonomy: supervised
lifecycle:
  current_phase: intake
  phases:
    intake:
      status: pending
"""


class TestFetchFile:
    def test_returns_content_on_success(self):
        transport = httpx.MockTransport(
            lambda req: _mock_github_response("hello world")
        )
        reader = GitRepoReader(token="test-token", transport=transport)
        result = reader.fetch_file("rhpds", "my-lab", "README.md", "main")
        assert result == "hello world"

    def test_returns_none_on_404(self):
        transport = httpx.MockTransport(
            lambda req: _mock_github_response("", status_code=404)
        )
        reader = GitRepoReader(token="test-token", transport=transport)
        result = reader.fetch_file("rhpds", "my-lab", "missing.md", "main")
        assert result is None

    def test_raises_on_server_error(self):
        transport = httpx.MockTransport(
            lambda req: _mock_github_response("", status_code=500)
        )
        reader = GitRepoReader(token="test-token", transport=transport)
        with pytest.raises(GitRepoReaderError, match="HTTP 500"):
            reader.fetch_file("rhpds", "my-lab", "README.md", "main")

    def test_sends_auth_header(self):
        def check_auth(request):
            assert request.headers["Authorization"] == "Bearer my-token"
            return _mock_github_response("ok")

        transport = httpx.MockTransport(check_auth)
        reader = GitRepoReader(token="my-token", transport=transport)
        reader.fetch_file("rhpds", "my-lab", "README.md", "main")

    def test_sends_ref_param(self):
        def check_ref(request):
            assert request.url.params["ref"] == "feature-branch"
            return _mock_github_response("ok")

        transport = httpx.MockTransport(check_ref)
        reader = GitRepoReader(token="test", transport=transport)
        reader.fetch_file("rhpds", "my-lab", "README.md", "feature-branch")


class TestFetchManifest:
    def test_returns_parsed_dict(self):
        transport = httpx.MockTransport(
            lambda req: _mock_github_response(SAMPLE_MANIFEST)
        )
        reader = GitRepoReader(token="test", transport=transport)
        result = reader.fetch_manifest("rhpds", "my-lab", "main")
        assert result["project"]["name"] == "Test Lab"
        assert result["project"]["owner_github"] == "testuser"
        assert result["lifecycle"]["current_phase"] == "intake"

    def test_raises_when_manifest_not_found(self):
        transport = httpx.MockTransport(
            lambda req: _mock_github_response("", status_code=404)
        )
        reader = GitRepoReader(token="test", transport=transport)
        with pytest.raises(GitRepoReaderError, match="manifest"):
            reader.fetch_manifest("rhpds", "my-lab", "main")


class TestFileExists:
    def test_returns_true_when_exists(self):
        transport = httpx.MockTransport(
            lambda req: _mock_github_response("content")
        )
        reader = GitRepoReader(token="test", transport=transport)
        assert reader.file_exists("rhpds", "my-lab", "README.md", "main") is True

    def test_returns_false_when_missing(self):
        transport = httpx.MockTransport(
            lambda req: _mock_github_response("", status_code=404)
        )
        reader = GitRepoReader(token="test", transport=transport)
        assert reader.file_exists("rhpds", "my-lab", "missing.md", "main") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src/backend && python -m pytest tests/test_git_repo_reader.py -v`
Expected: ImportError — `git_repo_reader` module doesn't exist yet.

- [ ] **Step 3: Implement GitRepoReader**

```python
# app/services/git_repo_reader.py
"""Read files from GitHub repositories via the GitHub API.

Fetches specific files by path and ref without cloning.
Used by Central to read manifests, specs, and review outputs.
"""
from __future__ import annotations

import base64
import logging

import httpx
import yaml

from app.services.github_client import parse_repo_url  # noqa: F401 — re-export

logger = logging.getLogger(__name__)

MANIFEST_PATHS = [
    "publishing-house/manifest.yaml",
    "manifest.yaml",
]


class GitRepoReaderError(Exception):
    """Raised when a GitHub API read fails."""
    pass


class GitRepoReader:
    """Reads files from GitHub repos via the Contents API."""

    def __init__(self, token: str, transport: httpx.BaseTransport | None = None):
        self._token = token
        self._client = httpx.Client(
            base_url="https://api.github.com",
            headers={
                "Accept": "application/vnd.github.v3+json",
                **({"Authorization": f"Bearer {token}"} if token else {}),
            },
            timeout=30.0,
            transport=transport,
        )

    def fetch_file(self, owner: str, repo: str, path: str, ref: str) -> str | None:
        """Fetch a single file's content from a repo.

        Returns None if the file doesn't exist (404).
        Raises GitRepoReaderError on server errors.
        """
        response = self._client.get(
            f"/repos/{owner}/{repo}/contents/{path}",
            params={"ref": ref},
        )

        if response.status_code == 404:
            return None

        if response.status_code != 200:
            raise GitRepoReaderError(
                f"HTTP {response.status_code} fetching {owner}/{repo}/{path}@{ref}"
            )

        data = response.json()
        encoded = data.get("content", "")
        return base64.b64decode(encoded).decode("utf-8")

    def fetch_manifest(self, owner: str, repo: str, ref: str) -> dict:
        """Fetch and parse the project manifest.

        Tries standard manifest locations. Returns parsed YAML as dict.
        Raises GitRepoReaderError if no manifest is found.
        """
        for path in MANIFEST_PATHS:
            content = self.fetch_file(owner, repo, path, ref)
            if content is not None:
                return yaml.safe_load(content)

        raise GitRepoReaderError(
            f"No manifest found in {owner}/{repo}@{ref}. "
            f"Tried: {', '.join(MANIFEST_PATHS)}"
        )

    def file_exists(self, owner: str, repo: str, path: str, ref: str) -> bool:
        """Check if a file exists in the repo at the given ref."""
        return self.fetch_file(owner, repo, path, ref) is not None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src/backend && python -m pytest tests/test_git_repo_reader.py -v`
Expected: All 9 tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/services/git_repo_reader.py tests/test_git_repo_reader.py
git commit -m "feat: Add GitRepoReader service for GitHub file access"
```

---

### Task 3: ph_register and ph_list_projects MCP Tools

**Files:**
- Create: `src/backend/app/mcp/gate_tools.py`
- Modify: `src/backend/app/main.py` — import gate_tools
- Create: `src/backend/tests/test_gate_tools_register.py`

**Interfaces:**
- Consumes: `GitRepoReader.fetch_manifest()`, `parse_repo_url()`, `Project` model, `SessionLocal`
- Produces:
  - `ph_register(repo_url: str, branch: str = "main") -> dict` — MCP tool
  - `ph_list_projects(owner_email: str) -> list[dict]` — MCP tool

- [ ] **Step 1: Write failing tests**

```python
# tests/test_gate_tools_register.py
"""Tests for ph_register and ph_list_projects MCP tools."""
import base64
import uuid

import httpx
import pytest
import yaml

from app.core.database import SessionLocal
from app.models.project import Project
from app.mcp.gate_tools import _register_project, _list_projects_by_owner


SAMPLE_MANIFEST = {
    "project": {
        "name": "Test Workshop",
        "id": "test-workshop",
        "owner_github": "testuser",
        "owner_name": "Test User",
        "type": "workshop",
        "showroom_type": "classic",
        "deployment_mode": "rhdp_published",
        "autonomy": "supervised",
    },
    "lifecycle": {
        "current_phase": "intake",
        "phases": {
            "intake": {"status": "completed", "completed_at": "2026-06-19"},
            "vetting": {"status": "pending"},
        },
    },
}


class TestRegisterProject:
    def test_creates_new_project(self, db_session):
        result = _register_project(
            db=db_session,
            manifest=SAMPLE_MANIFEST,
            repo_url="git@github.com:rhpds/test-workshop.git",
            branch="main",
        )
        assert result["name"] == "Test Workshop"
        assert result["owner_github"] == "testuser"
        assert result["deployment_mode"] == "rhdp_published"
        assert result["current_phase"] == "intake"
        assert "project_id" in result

    def test_returns_existing_project_on_duplicate(self, db_session):
        result1 = _register_project(
            db=db_session,
            manifest=SAMPLE_MANIFEST,
            repo_url="git@github.com:rhpds/test-workshop.git",
            branch="main",
        )
        result2 = _register_project(
            db=db_session,
            manifest=SAMPLE_MANIFEST,
            repo_url="git@github.com:rhpds/test-workshop.git",
            branch="main",
        )
        assert result1["project_id"] == result2["project_id"]

    def test_different_branches_are_different_projects(self, db_session):
        result1 = _register_project(
            db=db_session,
            manifest=SAMPLE_MANIFEST,
            repo_url="git@github.com:rhpds/test-workshop.git",
            branch="main",
        )
        result2 = _register_project(
            db=db_session,
            manifest=SAMPLE_MANIFEST,
            repo_url="git@github.com:rhpds/test-workshop.git",
            branch="feature-v2",
        )
        assert result1["project_id"] != result2["project_id"]

    def test_updates_owner_from_manifest(self, db_session):
        _register_project(
            db=db_session,
            manifest=SAMPLE_MANIFEST,
            repo_url="git@github.com:rhpds/test-workshop.git",
            branch="main",
        )
        updated_manifest = {**SAMPLE_MANIFEST, "project": {**SAMPLE_MANIFEST["project"], "owner_github": "newowner"}}
        result = _register_project(
            db=db_session,
            manifest=updated_manifest,
            repo_url="git@github.com:rhpds/test-workshop.git",
            branch="main",
        )
        assert result["owner_github"] == "newowner"


class TestListProjectsByOwner:
    def test_returns_projects_for_owner(self, db_session):
        _register_project(
            db=db_session,
            manifest=SAMPLE_MANIFEST,
            repo_url="git@github.com:rhpds/lab-one.git",
            branch="main",
        )
        _register_project(
            db=db_session,
            manifest=SAMPLE_MANIFEST,
            repo_url="git@github.com:rhpds/lab-two.git",
            branch="main",
        )
        results = _list_projects_by_owner(db=db_session, owner_identifier="testuser")
        assert len(results) == 2

    def test_filters_by_owner_github(self, db_session):
        _register_project(
            db=db_session,
            manifest=SAMPLE_MANIFEST,
            repo_url="git@github.com:rhpds/lab-one.git",
            branch="main",
        )
        other_manifest = {**SAMPLE_MANIFEST, "project": {**SAMPLE_MANIFEST["project"], "owner_github": "other"}}
        _register_project(
            db=db_session,
            manifest=other_manifest,
            repo_url="git@github.com:rhpds/lab-two.git",
            branch="main",
        )
        results = _list_projects_by_owner(db=db_session, owner_identifier="testuser")
        assert len(results) == 1
        assert results[0]["name"] == "Test Workshop"

    def test_returns_empty_list_for_unknown_owner(self, db_session):
        results = _list_projects_by_owner(db=db_session, owner_identifier="nobody")
        assert results == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src/backend && python -m pytest tests/test_gate_tools_register.py -v`
Expected: ImportError — `gate_tools` module doesn't exist yet.

- [ ] **Step 3: Implement gate_tools.py**

```python
# app/mcp/gate_tools.py
"""High-level MCP tools for Publishing House Central.

These are the primary tools exposed to client skills.
Low-level tools (rcars_tools, session_tools) become internal.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.mcp.server import mcp
from app.models.project import Project
from app.services.git_repo_reader import GitRepoReader, GitRepoReaderError, parse_repo_url

logger = logging.getLogger(__name__)


def _get_reader() -> GitRepoReader:
    return GitRepoReader(token=settings.github_token)


def _register_project(
    db: Session,
    manifest: dict,
    repo_url: str,
    branch: str,
) -> dict:
    """Register or update a project from its manifest. Pure DB logic, no GitHub calls."""
    project_data = manifest.get("project", {})
    lifecycle = manifest.get("lifecycle", {})

    existing = db.query(Project).filter(
        Project.repo_url == repo_url,
        Project.branch == branch,
    ).first()

    if existing:
        existing.name = project_data.get("name", existing.name)
        existing.owner_github = project_data.get("owner_github", existing.owner_github)
        existing.owner_email = project_data.get("owner_email", existing.owner_email)
        existing.deployment_mode = project_data.get("deployment_mode", existing.deployment_mode)
        existing.last_refreshed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        project = existing
    else:
        project = Project(
            name=project_data.get("name", "Untitled"),
            repo_url=repo_url,
            branch=branch,
            owner_github=project_data.get("owner_github"),
            owner_email=project_data.get("owner_email"),
            deployment_mode=project_data.get("deployment_mode"),
            last_refreshed_at=datetime.now(timezone.utc),
        )
        db.add(project)
        db.commit()
        db.refresh(project)

    phases = lifecycle.get("phases", {})
    phase_statuses = {name: phase.get("status", "pending") for name, phase in phases.items()}

    return {
        "project_id": str(project.id),
        "name": project.name,
        "repo_url": project.repo_url,
        "branch": project.branch,
        "owner_github": project.owner_github,
        "deployment_mode": project.deployment_mode,
        "current_phase": lifecycle.get("current_phase", "intake"),
        "phase_statuses": phase_statuses,
    }


def _list_projects_by_owner(db: Session, owner_identifier: str) -> list[dict]:
    """List projects by owner (github username or email)."""
    projects = db.query(Project).filter(
        (Project.owner_github == owner_identifier) |
        (Project.owner_email == owner_identifier)
    ).order_by(Project.registered_at.desc()).all()

    results = []
    for p in projects:
        manifest_data = {}
        if p.manifest and p.manifest.parsed_data:
            manifest_data = p.manifest.parsed_data
        lifecycle = manifest_data.get("lifecycle", {})

        results.append({
            "project_id": str(p.id),
            "name": p.name,
            "repo_url": p.repo_url,
            "branch": p.branch,
            "owner_github": p.owner_github,
            "deployment_mode": p.deployment_mode,
            "current_phase": lifecycle.get("current_phase", "unknown"),
            "registered_at": p.registered_at.isoformat() if p.registered_at else None,
        })
    return results


@mcp.tool()
def ph_register(repo_url: str, branch: str = "main") -> dict:
    """Register a project with Publishing House Central.

    Reads the manifest from the git repo, creates or updates the project
    record, and returns the project status. Called automatically by skills
    on first contact with Central.

    Args:
        repo_url: Git repository URL (SSH or HTTPS format)
        branch: Git branch name (default: main)

    Returns:
        Project registration details including ID, phase status, and owner.
    """
    reader = _get_reader()
    try:
        owner, repo = parse_repo_url(repo_url)
        manifest = reader.fetch_manifest(owner, repo, branch)
    except (ValueError, GitRepoReaderError) as e:
        return {"error": str(e), "registered": False}

    db = SessionLocal()
    try:
        result = _register_project(db, manifest, repo_url, branch)
        result["registered"] = True
        return result
    finally:
        db.close()


@mcp.tool()
def ph_list_projects(owner_email: str) -> list[dict]:
    """List all projects registered in Central for a given owner.

    Searches by both GitHub username and email address.

    Args:
        owner_email: Owner's email or GitHub username

    Returns:
        List of registered projects with current phase and status.
    """
    db = SessionLocal()
    try:
        return _list_projects_by_owner(db, owner_email)
    finally:
        db.close()
```

- [ ] **Step 4: Register gate_tools in main.py**

Add the import to `app/main.py` after the existing MCP tool imports:

```python
    import app.mcp.rcars_tools  # noqa: F401 — registers RCARS MCP tools
    import app.mcp.session_tools  # noqa: F401 — registers session continuity MCP tools
    import app.mcp.gate_tools  # noqa: F401 — registers Central gate MCP tools
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd src/backend && python -m pytest tests/test_gate_tools_register.py -v`
Expected: All 7 tests pass.

- [ ] **Step 6: Run full test suite to check for regressions**

Run: `cd src/backend && python -m pytest tests/ -v --timeout=30`
Expected: All existing tests pass alongside the new ones.

- [ ] **Step 7: Commit**

```bash
git add app/mcp/gate_tools.py app/main.py tests/test_gate_tools_register.py
git commit -m "feat: Add ph_register and ph_list_projects MCP tools"
```

---

### Task 4: Integration Test — End-to-End Registration

**Files:**
- Create: `src/backend/tests/test_registration_e2e.py`

**Interfaces:**
- Consumes: `ph_register` tool function, `GitRepoReader` with mock transport, `Project` model

This test verifies the full flow: MCP tool call → GitHub API (mocked) → DB write → response.

- [ ] **Step 1: Write the integration test**

```python
# tests/test_registration_e2e.py
"""End-to-end test for project registration flow."""
import base64
from unittest.mock import patch

import httpx
import pytest
import yaml

from app.mcp.gate_tools import ph_register, ph_list_projects
from app.core.database import SessionLocal
from app.models.project import Project


SAMPLE_MANIFEST = {
    "project": {
        "name": "AI Workshop",
        "id": "ai-workshop",
        "owner_github": "stencell",
        "owner_name": "Nate Stephany",
        "type": "workshop",
        "showroom_type": "classic",
        "deployment_mode": "rhdp_published",
        "autonomy": "supervised",
    },
    "lifecycle": {
        "current_phase": "vetting",
        "phases": {
            "intake": {"status": "completed", "completed_at": "2026-06-19"},
            "vetting": {"status": "pending"},
            "spec_refinement": {"status": "pending"},
            "approval": {"status": "pending"},
            "writing": {"status": "pending"},
        },
    },
}


def _mock_transport(manifest_dict):
    """Create a mock transport that returns the given manifest."""
    manifest_yaml = yaml.dump(manifest_dict)
    encoded = base64.b64encode(manifest_yaml.encode()).decode()

    def handler(request):
        return httpx.Response(200, json={"content": encoded, "encoding": "base64"})

    return httpx.MockTransport(handler)


class TestRegistrationE2E:
    def test_register_creates_project_and_returns_status(self, test_db):
        transport = _mock_transport(SAMPLE_MANIFEST)
        with patch("app.mcp.gate_tools._get_reader") as mock_reader:
            from app.services.git_repo_reader import GitRepoReader
            mock_reader.return_value = GitRepoReader(token="test", transport=transport)

            result = ph_register(
                repo_url="git@github.com:rhpds/ai-workshop.git",
                branch="main",
            )

        assert result["registered"] is True
        assert result["name"] == "AI Workshop"
        assert result["owner_github"] == "stencell"
        assert result["current_phase"] == "vetting"
        assert result["deployment_mode"] == "rhdp_published"
        assert "project_id" in result

    def test_register_then_list_by_owner(self, test_db):
        transport = _mock_transport(SAMPLE_MANIFEST)
        with patch("app.mcp.gate_tools._get_reader") as mock_reader:
            from app.services.git_repo_reader import GitRepoReader
            mock_reader.return_value = GitRepoReader(token="test", transport=transport)

            ph_register(
                repo_url="git@github.com:rhpds/ai-workshop.git",
                branch="main",
            )

        projects = ph_list_projects(owner_email="stencell")
        assert len(projects) == 1
        assert projects[0]["name"] == "AI Workshop"
        assert projects[0]["branch"] == "main"

    def test_register_returns_error_for_invalid_url(self, test_db):
        result = ph_register(repo_url="not-a-url", branch="main")
        assert result["registered"] is False
        assert "error" in result

    def test_register_returns_error_when_repo_not_found(self, test_db):
        transport = httpx.MockTransport(
            lambda req: httpx.Response(404, json={"message": "Not Found"})
        )
        with patch("app.mcp.gate_tools._get_reader") as mock_reader:
            from app.services.git_repo_reader import GitRepoReader
            mock_reader.return_value = GitRepoReader(token="test", transport=transport)

            result = ph_register(
                repo_url="git@github.com:rhpds/nonexistent.git",
                branch="main",
            )

        assert result["registered"] is False
        assert "manifest" in result["error"].lower()
```

- [ ] **Step 2: Run the integration test**

Run: `cd src/backend && python -m pytest tests/test_registration_e2e.py -v`
Expected: All 4 tests pass.

- [ ] **Step 3: Run the full test suite**

Run: `cd src/backend && python -m pytest tests/ -v --timeout=30`
Expected: All tests pass — no regressions.

- [ ] **Step 4: Commit**

```bash
git add tests/test_registration_e2e.py
git commit -m "test: Add end-to-end registration integration tests"
```
