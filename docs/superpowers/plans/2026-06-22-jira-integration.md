# Jira Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement one-directional Jira sync (PH → Jira) for onboarded projects in Publishing House Central, creating Epics and Tasks in RHDPCD that mirror manifest phase progress.

**Architecture:** A synchronous `JiraClient` HTTP service (follows `GitRepoReader` pattern) talks to Jira Cloud REST API v3 via Basic auth. `JiraSyncService` composes `JiraClient` + `PhaseEngine` to create/sync Jira issues. Sync is triggered by gate passes (primary) and periodic reconciliation (secondary). A `jira_task_mappings` DB table tracks which manifest paths map to which Jira issues.

**Tech Stack:** Python 3.11, httpx (sync), SQLAlchemy ORM, Alembic, FastMCP, Jira Cloud REST API v3, pytest

## Global Constraints

- Jira integration applies to `rhdp_published` (onboarded) projects ONLY. Self-published and express are excluded.
- One-directional sync: PH → Jira always. Jira → PH never.
- JiraSyncService is deterministic Python — no LLM in the loop.
- PH never overwrites story point values on existing Jira tasks.
- All Jira API calls go through `JiraClient` — no direct HTTP calls from other modules.
- `JiraClient` enforces `allowed_project_key` on all write operations — prevents accidental issue creation in unrelated Jira projects regardless of what the caller passes.
- Initiatives are created manually by managers in Jira. PH never creates them. During intake, the skill calls `get_open_initiatives()` to let the developer pick one. The selected Initiative key is stored in `manifest.integrations.jira.initiative_key` and read at Epic creation time. If no Initiative is selected, the Epic is created without a parent (unassigned — a manager can reparent it in Jira later).
- Follow existing Central patterns: sync httpx client, `SessionLocal()` in MCP tools, `JSONBType` for flexible columns.
- Codebase: `~/devel/publishing-house/rhdp-publishing-house-central/src/backend/`
- Tests: SQLite-backed, mocked httpx for Jira API calls.

## File Map

**New files:**
| File | Responsibility |
|------|---------------|
| `app/services/jira_client.py` | HTTP client for Jira REST API v3 (Basic auth, CRUD operations) |
| `app/services/jira_sync.py` | Business logic: create_project, sync_project, get_open_initiatives, _diff_state |
| `app/models/jira_task_mapping.py` | SQLAlchemy model for jira_task_mappings table |
| `alembic/versions/e5f6g7h8i9j0_add_jira_task_mappings.py` | Migration for jira_task_mappings table |
| `tests/test_jira_client.py` | JiraClient unit tests |
| `tests/test_jira_sync.py` | JiraSyncService unit tests |
| `tests/test_jira_integration.py` | Integration tests (gate hooks, ph_get_status) |

**Modified files:**
| File | Change |
|------|--------|
| `app/core/config.py` | Add `jira_url`, `jira_email`, `jira_api_token`, `jira_project_key` settings |
| `app/mcp/gate_tools.py` | Hook `JiraSyncService.sync_project()` after gate passes in `ph_request_gate`; add `jira` block to `ph_get_status` |
| `app/main.py` | Import `JiraTaskMapping` model; hook Jira reconciliation into `_scheduled_refresh` |
| `alembic/env.py` | Import `JiraTaskMapping` for autogenerate |
| `ansible/templates/manifests-infra.yaml.j2` | Add `ph-central-jira-credentials` Secret |
| `ansible/templates/manifests-app.yaml.j2` | Add `JIRA_*` env vars to backend container |

---

### Task 1: JiraClient — HTTP Client for Jira REST API

**Files:**
- Create: `app/services/jira_client.py`
- Modify: `app/core/config.py`
- Test: `tests/test_jira_client.py`

**Interfaces:**
- Consumes: `settings.jira_url`, `settings.jira_email`, `settings.jira_api_token`, `settings.jira_project_key`
- Produces:
  - `JiraClient(base_url, email, api_token, allowed_project_key)` — constructor; `allowed_project_key` is enforced on all write operations
  - `JiraClient.create_issue(fields: dict) -> dict` — returns `{"key": "RHDPCD-42", "id": "10001"}`; raises `JiraError` if `fields.project.key` doesn't match `allowed_project_key`
  - `JiraClient.transition_issue(issue_key: str, transition_id: str, fields: dict | None = None) -> None` — raises `JiraError` if issue_key prefix doesn't match `allowed_project_key`
  - `JiraClient.add_comment(issue_key: str, body: str) -> None` — raises `JiraError` if issue_key prefix doesn't match `allowed_project_key`
  - `JiraClient.search_jql(jql: str, fields: list[str] | None = None, max_results: int = 50) -> list[dict]`
  - `JiraClient.get_issue(issue_key: str, fields: list[str] | None = None) -> dict`
  - `JiraError(message: str, status_code: int | None = None)`

- [ ] **Step 1: Add Jira settings to config**

Add to `app/core/config.py`, inside the `Settings` class after the existing fields:

```python
    # Jira integration (onboarded projects only)
    jira_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""
    jira_project_key: str = "RHDPCD"
```

- [ ] **Step 2: Write failing tests for JiraClient**

Create `tests/test_jira_client.py`:

```python
import base64
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.services.jira_client import JiraClient, JiraError


@pytest.fixture
def jira():
    return JiraClient(
        base_url="https://test.atlassian.net",
        email="test@example.com",
        api_token="test-token",
        allowed_project_key="RHDPCD",
    )


def test_auth_header(jira):
    expected = base64.b64encode(b"test@example.com:test-token").decode()
    assert jira._headers["Authorization"] == f"Basic {expected}"


def test_create_issue_success(jira):
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"key": "RHDPCD-42", "id": "10001"}
    mock_response.raise_for_status = MagicMock()

    with patch.object(jira._client, "post", return_value=mock_response):
        result = jira.create_issue({"summary": "Test Epic", "issuetype": {"id": "10000"}})

    assert result["key"] == "RHDPCD-42"


def test_create_issue_failure(jira):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = '{"errors": {"summary": "required"}}'
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Bad Request", request=MagicMock(), response=mock_response
    )

    with patch.object(jira._client, "post", return_value=mock_response):
        with pytest.raises(JiraError, match="Jira API error"):
            jira.create_issue({})


def test_transition_issue(jira):
    mock_response = MagicMock()
    mock_response.status_code = 204
    mock_response.raise_for_status = MagicMock()

    with patch.object(jira._client, "post", return_value=mock_response):
        jira.transition_issue("RHDPCD-42", "31")


def test_transition_with_resolution(jira):
    mock_response = MagicMock()
    mock_response.status_code = 204
    mock_response.raise_for_status = MagicMock()

    with patch.object(jira._client, "post", return_value=mock_response) as mock_post:
        jira.transition_issue("RHDPCD-42", "41", fields={"resolution": {"name": "Done"}})

    call_json = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
    assert call_json["fields"]["resolution"]["name"] == "Done"


def test_add_comment(jira):
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.raise_for_status = MagicMock()

    with patch.object(jira._client, "post", return_value=mock_response) as mock_post:
        jira.add_comment("RHDPCD-42", "Gate passed: vetting approved")

    call_json = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
    assert "Gate passed" in call_json["body"]["content"][0]["content"][0]["text"]


def test_search_jql(jira):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "issues": [
            {"key": "RHDPCD-10", "fields": {"summary": "Summit 2027 Labs"}},
        ],
        "total": 1,
    }
    mock_response.raise_for_status = MagicMock()

    with patch.object(jira._client, "post", return_value=mock_response):
        results = jira.search_jql('project = RHDPCD AND issuetype = Initiative AND status != Closed')

    assert len(results) == 1
    assert results[0]["key"] == "RHDPCD-10"


def test_get_issue(jira):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "key": "RHDPCD-42",
        "fields": {"status": {"name": "In Progress", "id": "3"}},
    }
    mock_response.raise_for_status = MagicMock()

    with patch.object(jira._client, "get", return_value=mock_response):
        result = jira.get_issue("RHDPCD-42", fields=["status"])

    assert result["fields"]["status"]["name"] == "In Progress"


def test_jira_not_configured():
    client = JiraClient(base_url="", email="", api_token="", allowed_project_key="RHDPCD")
    assert not client.is_configured


def test_create_issue_rejects_wrong_project():
    jira = JiraClient(
        base_url="https://test.atlassian.net",
        email="test@example.com",
        api_token="test-token",
        allowed_project_key="RHDPCD",
    )
    with pytest.raises(JiraError, match="Project key mismatch"):
        jira.create_issue({"project": {"key": "GPTEINFRA"}, "summary": "Rogue issue"})


def test_transition_rejects_wrong_project_prefix():
    jira = JiraClient(
        base_url="https://test.atlassian.net",
        email="test@example.com",
        api_token="test-token",
        allowed_project_key="RHDPCD",
    )
    with pytest.raises(JiraError, match="Issue key .* not in allowed project"):
        jira.transition_issue("GPTEINFRA-999", "31")


def test_add_comment_rejects_wrong_project_prefix():
    jira = JiraClient(
        base_url="https://test.atlassian.net",
        email="test@example.com",
        api_token="test-token",
        allowed_project_key="RHDPCD",
    )
    with pytest.raises(JiraError, match="Issue key .* not in allowed project"):
        jira.add_comment("OTHER-1", "sneaky comment")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd ~/devel/publishing-house/rhdp-publishing-house-central/src/backend && python -m pytest tests/test_jira_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.jira_client'`

- [ ] **Step 4: Implement JiraClient**

Create `app/services/jira_client.py`:

```python
"""HTTP client for Jira Cloud REST API v3."""

import base64
import logging

import httpx

logger = logging.getLogger(__name__)


class JiraError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class JiraClient:
    """Synchronous Jira REST API v3 client with Basic auth.

    All write operations enforce allowed_project_key to prevent
    accidental issue creation in unrelated Jira projects.
    """

    API_PATH = "/rest/api/3"

    def __init__(self, base_url: str, email: str, api_token: str, allowed_project_key: str):
        self._base_url = base_url.rstrip("/")
        self._email = email
        self._api_token = api_token
        self._allowed_project_key = allowed_project_key
        credentials = base64.b64encode(f"{email}:{api_token}".encode()).decode()
        self._headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        self._client = httpx.Client(timeout=30.0)

    @property
    def is_configured(self) -> bool:
        return bool(self._base_url and self._email and self._api_token)

    def _url(self, path: str) -> str:
        return f"{self._base_url}{self.API_PATH}{path}"

    def _enforce_project_key(self, fields: dict) -> None:
        """Reject issue creation targeting any project other than the configured one."""
        project_key = fields.get("project", {}).get("key", "")
        if project_key != self._allowed_project_key:
            raise JiraError(
                f"Project key mismatch: got '{project_key}', "
                f"allowed '{self._allowed_project_key}'"
            )

    def _enforce_issue_prefix(self, issue_key: str) -> None:
        """Reject operations on issues that don't belong to the configured project."""
        prefix = issue_key.split("-")[0] if "-" in issue_key else ""
        if prefix != self._allowed_project_key:
            raise JiraError(
                f"Issue key '{issue_key}' not in allowed project "
                f"'{self._allowed_project_key}'"
            )

    def _handle_error(self, e: httpx.HTTPStatusError) -> None:
        status = e.response.status_code
        detail = e.response.text[:500]
        logger.error("Jira API error %d: %s", status, detail)
        raise JiraError(f"Jira API error {status}: {detail}", status_code=status)

    def create_issue(self, fields: dict) -> dict:
        self._enforce_project_key(fields)
        try:
            resp = self._client.post(
                self._url("/issue"),
                headers=self._headers,
                json={"fields": fields},
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            self._handle_error(e)

    def transition_issue(
        self, issue_key: str, transition_id: str, fields: dict | None = None
    ) -> None:
        self._enforce_issue_prefix(issue_key)
        payload: dict = {"transition": {"id": transition_id}}
        if fields:
            payload["fields"] = fields
        try:
            resp = self._client.post(
                self._url(f"/issue/{issue_key}/transitions"),
                headers=self._headers,
                json=payload,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            self._handle_error(e)

    def add_comment(self, issue_key: str, body: str) -> None:
        self._enforce_issue_prefix(issue_key)
        adf_body = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": body}],
                }
            ],
        }
        try:
            resp = self._client.post(
                self._url(f"/issue/{issue_key}/comment"),
                headers=self._headers,
                json={"body": adf_body},
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            self._handle_error(e)

    def search_jql(
        self, jql: str, fields: list[str] | None = None, max_results: int = 50
    ) -> list[dict]:
        payload: dict = {"jql": jql, "maxResults": max_results}
        if fields:
            payload["fields"] = fields
        try:
            resp = self._client.post(
                self._url("/search"),
                headers=self._headers,
                json=payload,
            )
            resp.raise_for_status()
            return resp.json().get("issues", [])
        except httpx.HTTPStatusError as e:
            self._handle_error(e)

    def get_issue(self, issue_key: str, fields: list[str] | None = None) -> dict:
        params = {}
        if fields:
            params["fields"] = ",".join(fields)
        try:
            resp = self._client.get(
                self._url(f"/issue/{issue_key}"),
                headers=self._headers,
                params=params,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            self._handle_error(e)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd ~/devel/publishing-house/rhdp-publishing-house-central/src/backend && python -m pytest tests/test_jira_client.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
cd ~/devel/publishing-house/rhdp-publishing-house-central
git add src/backend/app/services/jira_client.py src/backend/app/core/config.py src/backend/tests/test_jira_client.py
git commit -m "Add JiraClient HTTP service and config settings"
```

---

### Task 2: JiraTaskMapping Model + Alembic Migration

**Files:**
- Create: `app/models/jira_task_mapping.py`
- Create: `alembic/versions/e5f6g7h8i9j0_add_jira_task_mappings.py`
- Modify: `alembic/env.py`
- Test: `tests/test_jira_sync.py` (model portion)

**Interfaces:**
- Consumes: `Base` from `app.core.database`, `JSONBType` from `app.core.types`
- Produces:
  - `JiraTaskMapping` — SQLAlchemy model with columns: `id`, `project_id`, `jira_epic_key`, `deliverable_type`, `module_id`, `jira_issue_key`, `manifest_path`, `default_points`, `created_at`, `updated_at`
  - `DeliverableType` — string enum: `design_doc`, `module_outline`, `module_content`, `module_automation`, `module_verified`, `code_review`, `e2e_test`, `final_review`

- [ ] **Step 1: Write failing test for model**

Add to `tests/test_jira_sync.py` (create file):

```python
import uuid
from datetime import datetime, timezone

import pytest

from app.models.jira_task_mapping import JiraTaskMapping, DeliverableType


def test_deliverable_type_values():
    assert DeliverableType.DESIGN_DOC == "design_doc"
    assert DeliverableType.MODULE_CONTENT == "module_content"
    assert DeliverableType.MODULE_AUTOMATION == "module_automation"
    assert DeliverableType.MODULE_VERIFIED == "module_verified"
    assert DeliverableType.CODE_REVIEW == "code_review"
    assert DeliverableType.E2E_TEST == "e2e_test"
    assert DeliverableType.FINAL_REVIEW == "final_review"


def test_create_jira_task_mapping(db_session):
    project_id = uuid.uuid4()
    mapping = JiraTaskMapping(
        project_id=project_id,
        jira_epic_key="RHDPCD-42",
        deliverable_type=DeliverableType.MODULE_CONTENT,
        module_id="module-01",
        jira_issue_key="RHDPCD-87",
        manifest_path="lifecycle.phases.writing.modules[id=module-01].status",
        default_points=5,
    )
    db_session.add(mapping)
    db_session.commit()

    result = db_session.query(JiraTaskMapping).filter_by(jira_issue_key="RHDPCD-87").first()
    assert result is not None
    assert result.deliverable_type == DeliverableType.MODULE_CONTENT
    assert result.module_id == "module-01"
    assert result.default_points == 5


def test_project_level_mapping_has_null_module_id(db_session):
    mapping = JiraTaskMapping(
        project_id=uuid.uuid4(),
        jira_epic_key="RHDPCD-42",
        deliverable_type=DeliverableType.DESIGN_DOC,
        module_id=None,
        jira_issue_key="RHDPCD-43",
        manifest_path="lifecycle.phases.intake.status",
        default_points=3,
    )
    db_session.add(mapping)
    db_session.commit()

    result = db_session.query(JiraTaskMapping).filter_by(jira_issue_key="RHDPCD-43").first()
    assert result.module_id is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/devel/publishing-house/rhdp-publishing-house-central/src/backend && python -m pytest tests/test_jira_sync.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement JiraTaskMapping model**

Create `app/models/jira_task_mapping.py`:

```python
"""Jira task mapping — links manifest deliverables to Jira issues."""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class DeliverableType(str, enum.Enum):
    DESIGN_DOC = "design_doc"
    MODULE_OUTLINE = "module_outline"
    MODULE_CONTENT = "module_content"
    MODULE_AUTOMATION = "module_automation"
    MODULE_VERIFIED = "module_verified"
    CODE_REVIEW = "code_review"
    E2E_TEST = "e2e_test"
    FINAL_REVIEW = "final_review"


class JiraTaskMapping(Base):
    __tablename__ = "jira_task_mappings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), nullable=False)
    jira_epic_key = Column(String(50), nullable=False)
    deliverable_type = Column(String(30), nullable=False)
    module_id = Column(String(50), nullable=True)
    jira_issue_key = Column(String(50), nullable=False, unique=True)
    manifest_path = Column(String(500), nullable=False)
    default_points = Column(Integer, nullable=False)
    created_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_jira_task_mappings_project", "project_id"),
        Index("ix_jira_task_mappings_epic", "jira_epic_key"),
    )
```

- [ ] **Step 4: Add model import to alembic/env.py**

Add `JiraTaskMapping` to the import list in `alembic/env.py`:

```python
from app.models.jira_task_mapping import JiraTaskMapping
```

- [ ] **Step 5: Create Alembic migration**

Create `alembic/versions/e5f6g7h8i9j0_add_jira_task_mappings.py`:

```python
"""Add jira_task_mappings table.

Revision ID: e5f6g7h8i9j0
Revises: d3e4f5g6h7i8
Create Date: 2026-06-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e5f6g7h8i9j0"
down_revision = "d3e4f5g6h7i8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jira_task_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("jira_epic_key", sa.String(50), nullable=False),
        sa.Column("deliverable_type", sa.String(30), nullable=False),
        sa.Column("module_id", sa.String(50), nullable=True),
        sa.Column("jira_issue_key", sa.String(50), nullable=False, unique=True),
        sa.Column("manifest_path", sa.String(500), nullable=False),
        sa.Column("default_points", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_jira_task_mappings_project", "jira_task_mappings", ["project_id"])
    op.create_index("ix_jira_task_mappings_epic", "jira_task_mappings", ["jira_epic_key"])


def downgrade() -> None:
    op.drop_table("jira_task_mappings")
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd ~/devel/publishing-house/rhdp-publishing-house-central/src/backend && python -m pytest tests/test_jira_sync.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
cd ~/devel/publishing-house/rhdp-publishing-house-central
git add src/backend/app/models/jira_task_mapping.py src/backend/alembic/versions/e5f6g7h8i9j0_add_jira_task_mappings.py src/backend/alembic/env.py src/backend/tests/test_jira_sync.py
git commit -m "Add JiraTaskMapping model and migration"
```

---

### Task 3: JiraSyncService — Core Business Logic

**Files:**
- Create: `app/services/jira_sync.py`
- Test: `tests/test_jira_sync.py` (extend)

**Interfaces:**
- Consumes:
  - `JiraClient` from Task 1 — `create_issue()`, `transition_issue()`, `add_comment()`, `search_jql()`
  - `JiraTaskMapping`, `DeliverableType` from Task 2
  - `PhaseEngine.get_profile(deployment_mode)` from `app.services.phase_engine`
  - `settings.jira_project_key` from `app.core.config`
  - `SessionLocal` / SQLAlchemy session for DB operations
- Produces:
  - `JiraSyncService(jira_client: JiraClient, project_key: str)` — constructor
  - `JiraSyncService.create_project(db, project_id: UUID, manifest: dict, initiative_key: str | None) -> dict` — returns `{"epic_key": "...", "task_count": N}`
  - `JiraSyncService.sync_project(db, project_id: UUID, manifest: dict, gate_record: dict | None = None) -> dict` — returns `{"changes": [...], "synced": True}`
  - `JiraSyncService.get_open_initiatives(db) -> list[dict]` — returns `[{"key": "...", "summary": "..."}]`
  - `get_manifest_status(manifest: dict, deliverable_type: str, module_id: str | None) -> str` — module-level function
  - `build_deliverable_list(manifest: dict, deployment_mode: str) -> list[dict]` — module-level function
  - Jira constants: `ISSUE_TYPE_EPIC`, `ISSUE_TYPE_TASK`, `TRANSITION_*`, `FIELD_*`

- [ ] **Step 1: Write failing tests for manifest status extraction**

Add to `tests/test_jira_sync.py`:

```python
from app.services.jira_sync import get_manifest_status, build_deliverable_list


SAMPLE_MANIFEST = {
    "project": {
        "name": "OCP Getting Started",
        "deployment_mode": "rhdp_published",
    },
    "lifecycle": {
        "phases": {
            "intake": {"status": "completed"},
            "vetting": {"status": "completed"},
            "spec_refinement": {"status": "completed"},
            "writing": {
                "status": "in_progress",
                "modules": [
                    {"id": "module-01", "title": "First App", "status": "drafted", "verified": False},
                    {"id": "module-02", "title": "Scaling", "status": "pending", "verified": False},
                ],
            },
            "automation": {
                "status": "in_progress",
                "modules": [
                    {"id": "module-01", "status": "completed"},
                    {"id": "module-02", "status": "pending"},
                ],
            },
            "code_security_review": {"status": "pending"},
            "final_review": {"status": "pending"},
        },
    },
}


def test_design_doc_status_completed():
    status = get_manifest_status(SAMPLE_MANIFEST, "design_doc", None)
    assert status == "completed"


def test_design_doc_status_pending():
    manifest = {
        "lifecycle": {"phases": {"intake": {"status": "pending"}, "vetting": {"status": "pending"}}}
    }
    assert get_manifest_status(manifest, "design_doc", None) == "pending"


def test_module_content_status():
    status = get_manifest_status(SAMPLE_MANIFEST, "module_content", "module-01")
    assert status == "in_progress"  # "drafted" maps to in_progress


def test_module_content_pending():
    status = get_manifest_status(SAMPLE_MANIFEST, "module_content", "module-02")
    assert status == "pending"


def test_module_automation_status():
    status = get_manifest_status(SAMPLE_MANIFEST, "module_automation", "module-01")
    assert status == "completed"


def test_module_verified_false():
    status = get_manifest_status(SAMPLE_MANIFEST, "module_verified", "module-01")
    assert status == "pending"


def test_code_review_status():
    status = get_manifest_status(SAMPLE_MANIFEST, "code_review", None)
    assert status == "pending"


def test_missing_phase_treated_as_pending():
    manifest = {"lifecycle": {"phases": {}}}
    assert get_manifest_status(manifest, "e2e_test", None) == "pending"


def test_missing_modules_falls_back_to_phase():
    manifest = {
        "lifecycle": {"phases": {"writing": {"status": "in_progress"}}}
    }
    status = get_manifest_status(manifest, "module_content", "module-01")
    assert status == "in_progress"


def test_build_deliverable_list_3_modules():
    deliverables = build_deliverable_list(SAMPLE_MANIFEST, "rhdp_published")
    types = [d["deliverable_type"] for d in deliverables]

    assert types[0] == "design_doc"
    assert types.count("module_outline") == 2
    assert types.count("module_content") == 2
    assert types.count("module_automation") == 2
    assert types.count("module_verified") == 2
    assert "code_review" in types
    assert "e2e_test" in types
    assert "final_review" in types

    design = next(d for d in deliverables if d["deliverable_type"] == "design_doc")
    assert design["points"] == 3
    assert design["module_id"] is None

    mod1_content = next(
        d for d in deliverables
        if d["deliverable_type"] == "module_content" and d["module_id"] == "module-01"
    )
    assert mod1_content["points"] == 5
    assert mod1_content["summary"] == "Module 1: Content — First App"


def test_build_deliverable_list_excludes_non_onboarded():
    deliverables = build_deliverable_list(SAMPLE_MANIFEST, "self_published")
    assert deliverables == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/devel/publishing-house/rhdp-publishing-house-central/src/backend && python -m pytest tests/test_jira_sync.py::test_design_doc_status_completed -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement manifest status extraction and deliverable list**

Create `app/services/jira_sync.py` with the constants, `get_manifest_status`, and `build_deliverable_list`:

```python
"""Jira sync service — one-directional sync from PH manifest to Jira."""

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.jira_task_mapping import DeliverableType, JiraTaskMapping
from app.services.jira_client import JiraClient, JiraError

logger = logging.getLogger(__name__)

# Jira Cloud issue type IDs (OJA-ITS-003 on RHDPCD)
ISSUE_TYPE_EPIC = "10000"
ISSUE_TYPE_TASK = "10014"
ISSUE_TYPE_INITIATIVE = "10103"

# Jira transition IDs (OJA-ITS-003 four-state workflow)
TRANSITION_NEW = "51"
TRANSITION_IN_PROGRESS = "31"
TRANSITION_CLOSED = "41"

# Jira custom field IDs
FIELD_STORY_POINTS = "customfield_10028"
FIELD_EPIC_NAME = "customfield_10011"

# Manifest status → Jira transition mapping
STATUS_TO_TRANSITION = {
    "pending": TRANSITION_NEW,
    "in_progress": TRANSITION_IN_PROGRESS,
    "completed": TRANSITION_CLOSED,
}

# Jira status category → manifest status (for reverse lookup during diff)
JIRA_CATEGORY_TO_STATUS = {
    "To Do": "pending",
    "In Progress": "in_progress",
    "Done": "completed",
}

# Deliverable templates with default points
DELIVERABLE_DEFAULTS = {
    DeliverableType.DESIGN_DOC: {"summary": "Design Doc", "points": 3},
    DeliverableType.MODULE_OUTLINE: {"summary": "Module {n}: Outline — {title}", "points": 5},
    DeliverableType.MODULE_CONTENT: {"summary": "Module {n}: Content — {title}", "points": 5},
    DeliverableType.MODULE_AUTOMATION: {"summary": "Module {n}: Automation — {title}", "points": 8},
    DeliverableType.MODULE_VERIFIED: {"summary": "Module {n}: Verified — {title}", "points": 5},
    DeliverableType.CODE_REVIEW: {"summary": "Code & Security Review", "points": 3},
    DeliverableType.E2E_TEST: {"summary": "E2E Test", "points": 8},
    DeliverableType.FINAL_REVIEW: {"summary": "Final Review", "points": 1},
}

# Manifest path templates for each deliverable type
MANIFEST_PATHS = {
    DeliverableType.DESIGN_DOC: "lifecycle.phases.intake.status+lifecycle.phases.vetting.status",
    DeliverableType.MODULE_OUTLINE: "lifecycle.phases.spec_refinement.modules[id={module_id}].status",
    DeliverableType.MODULE_CONTENT: "lifecycle.phases.writing.modules[id={module_id}].status",
    DeliverableType.MODULE_AUTOMATION: "lifecycle.phases.automation.modules[id={module_id}].status",
    DeliverableType.MODULE_VERIFIED: "lifecycle.phases.writing.modules[id={module_id}].verified",
    DeliverableType.CODE_REVIEW: "lifecycle.phases.code_security_review.status",
    DeliverableType.E2E_TEST: "lifecycle.phases.e2e_test.status",
    DeliverableType.FINAL_REVIEW: "lifecycle.phases.final_review.status",
}

MODULE_DELIVERABLE_TYPES = {
    DeliverableType.MODULE_OUTLINE,
    DeliverableType.MODULE_CONTENT,
    DeliverableType.MODULE_AUTOMATION,
    DeliverableType.MODULE_VERIFIED,
}

# Writing module statuses that map to in_progress
WRITING_IN_PROGRESS_STATUSES = {"drafted", "in_progress", "in_review"}


def _get_phase(manifest: dict, phase_name: str) -> dict:
    return manifest.get("lifecycle", {}).get("phases", {}).get(phase_name, {})


def _find_module(modules: list[dict], module_id: str) -> dict | None:
    return next((m for m in modules if m.get("id") == module_id), None)


def get_manifest_status(manifest: dict, deliverable_type: str, module_id: str | None) -> str:
    """Extract the current PH status for a deliverable from the manifest."""

    if deliverable_type == DeliverableType.DESIGN_DOC:
        intake = _get_phase(manifest, "intake").get("status", "pending")
        vetting = _get_phase(manifest, "vetting").get("status", "pending")
        if intake == "completed" and vetting == "completed":
            return "completed"
        if intake in WRITING_IN_PROGRESS_STATUSES or vetting in WRITING_IN_PROGRESS_STATUSES:
            return "in_progress"
        return "pending"

    if deliverable_type == DeliverableType.MODULE_OUTLINE:
        phase = _get_phase(manifest, "spec_refinement")
        modules = phase.get("modules", [])
        if modules and module_id:
            mod = _find_module(modules, module_id)
            return mod.get("status", "pending") if mod else "pending"
        return phase.get("status", "pending")

    if deliverable_type == DeliverableType.MODULE_CONTENT:
        phase = _get_phase(manifest, "writing")
        modules = phase.get("modules", [])
        if modules and module_id:
            mod = _find_module(modules, module_id)
            if mod:
                s = mod.get("status", "pending")
                return "in_progress" if s in WRITING_IN_PROGRESS_STATUSES else s
            return "pending"
        s = phase.get("status", "pending")
        return "in_progress" if s in WRITING_IN_PROGRESS_STATUSES else s

    if deliverable_type == DeliverableType.MODULE_AUTOMATION:
        phase = _get_phase(manifest, "automation")
        modules = phase.get("modules", [])
        if modules and module_id:
            mod = _find_module(modules, module_id)
            return mod.get("status", "pending") if mod else "pending"
        return phase.get("status", "pending")

    if deliverable_type == DeliverableType.MODULE_VERIFIED:
        phase = _get_phase(manifest, "writing")
        modules = phase.get("modules", [])
        if modules and module_id:
            mod = _find_module(modules, module_id)
            if mod:
                return "completed" if mod.get("verified") else "pending"
            return "pending"
        return "pending"

    if deliverable_type == DeliverableType.CODE_REVIEW:
        return _get_phase(manifest, "code_security_review").get("status", "pending")

    if deliverable_type == DeliverableType.E2E_TEST:
        return _get_phase(manifest, "e2e_test").get("status", "pending")

    if deliverable_type == DeliverableType.FINAL_REVIEW:
        return _get_phase(manifest, "final_review").get("status", "pending")

    return "pending"


def build_deliverable_list(manifest: dict, deployment_mode: str) -> list[dict]:
    """Build the list of Jira deliverables for a project based on its manifest and mode."""
    if deployment_mode != "rhdp_published":
        return []

    modules = (
        manifest.get("lifecycle", {})
        .get("phases", {})
        .get("writing", {})
        .get("modules", [])
    )

    deliverables = []

    # Design Doc (project-level)
    d = DELIVERABLE_DEFAULTS[DeliverableType.DESIGN_DOC]
    deliverables.append({
        "deliverable_type": DeliverableType.DESIGN_DOC,
        "summary": d["summary"],
        "points": d["points"],
        "module_id": None,
        "manifest_path": MANIFEST_PATHS[DeliverableType.DESIGN_DOC],
    })

    # Per-module deliverables
    for i, mod in enumerate(modules, 1):
        mod_id = mod.get("id", f"module-{i:02d}")
        mod_title = mod.get("title", f"Module {i}")
        for dt in [
            DeliverableType.MODULE_OUTLINE,
            DeliverableType.MODULE_CONTENT,
            DeliverableType.MODULE_AUTOMATION,
            DeliverableType.MODULE_VERIFIED,
        ]:
            d = DELIVERABLE_DEFAULTS[dt]
            deliverables.append({
                "deliverable_type": dt,
                "summary": d["summary"].format(n=i, title=mod_title),
                "points": d["points"],
                "module_id": mod_id,
                "manifest_path": MANIFEST_PATHS[dt].format(module_id=mod_id),
            })

    # Project-level deliverables (after modules)
    for dt in [DeliverableType.CODE_REVIEW, DeliverableType.E2E_TEST, DeliverableType.FINAL_REVIEW]:
        d = DELIVERABLE_DEFAULTS[dt]
        deliverables.append({
            "deliverable_type": dt,
            "summary": d["summary"],
            "points": d["points"],
            "module_id": None,
            "manifest_path": MANIFEST_PATHS[dt],
        })

    return deliverables
```

- [ ] **Step 4: Run extraction tests to verify they pass**

Run: `cd ~/devel/publishing-house/rhdp-publishing-house-central/src/backend && python -m pytest tests/test_jira_sync.py -v`
Expected: All PASS

- [ ] **Step 5: Write failing tests for JiraSyncService**

Add to `tests/test_jira_sync.py`:

```python
from unittest.mock import MagicMock, patch, call
from app.services.jira_sync import JiraSyncService, TRANSITION_IN_PROGRESS, TRANSITION_CLOSED


@pytest.fixture
def mock_jira():
    client = MagicMock(spec=JiraClient)
    client.is_configured = True
    return client


@pytest.fixture
def sync_service(mock_jira):
    return JiraSyncService(jira_client=mock_jira, project_key="RHDPCD")


def test_create_project_creates_epic_and_tasks(sync_service, mock_jira, db_session):
    project_id = uuid.uuid4()
    mock_jira.create_issue.side_effect = [
        {"key": "RHDPCD-100", "id": "100"},   # Epic
        {"key": "RHDPCD-101", "id": "101"},   # Design Doc
        {"key": "RHDPCD-102", "id": "102"},   # Module 1: Outline
        {"key": "RHDPCD-103", "id": "103"},   # Module 1: Content
        {"key": "RHDPCD-104", "id": "104"},   # Module 1: Automation
        {"key": "RHDPCD-105", "id": "105"},   # Module 1: Verified
        {"key": "RHDPCD-106", "id": "106"},   # Code & Security Review
        {"key": "RHDPCD-107", "id": "107"},   # E2E Test
        {"key": "RHDPCD-108", "id": "108"},   # Final Review
    ]

    manifest = {
        "project": {"name": "Test Lab", "deployment_mode": "rhdp_published"},
        "lifecycle": {
            "phases": {
                "intake": {"status": "completed"},
                "vetting": {"status": "completed"},
                "writing": {
                    "modules": [
                        {"id": "module-01", "title": "First Module", "status": "pending"},
                    ],
                },
                "automation": {"status": "pending"},
            },
        },
    }

    result = sync_service.create_project(db_session, project_id, manifest, "RHDPCD-10")

    assert result["epic_key"] == "RHDPCD-100"
    assert result["task_count"] == 8
    assert mock_jira.create_issue.call_count == 9  # 1 epic + 8 tasks

    # Verify mappings stored
    mappings = db_session.query(JiraTaskMapping).filter_by(project_id=project_id).all()
    assert len(mappings) == 8


def test_create_project_skips_non_onboarded(sync_service, mock_jira, db_session):
    manifest = {
        "project": {"name": "Self Pub", "deployment_mode": "self_published"},
        "lifecycle": {"phases": {}},
    }
    result = sync_service.create_project(db_session, uuid.uuid4(), manifest, None)
    assert result["skipped"] is True
    mock_jira.create_issue.assert_not_called()


def test_sync_project_transitions_tasks(sync_service, mock_jira, db_session):
    project_id = uuid.uuid4()

    # Pre-populate mappings
    for key, dtype, path in [
        ("RHDPCD-101", "design_doc", "lifecycle.phases.intake.status+lifecycle.phases.vetting.status"),
        ("RHDPCD-102", "code_review", "lifecycle.phases.code_security_review.status"),
    ]:
        db_session.add(JiraTaskMapping(
            project_id=project_id,
            jira_epic_key="RHDPCD-100",
            deliverable_type=dtype,
            jira_issue_key=key,
            manifest_path=path,
            default_points=3,
        ))
    db_session.commit()

    # Mock Jira returns current status
    mock_jira.search_jql.return_value = [
        {"key": "RHDPCD-101", "fields": {"status": {"statusCategory": {"name": "To Do"}}}},
        {"key": "RHDPCD-102", "fields": {"status": {"statusCategory": {"name": "To Do"}}}},
    ]

    manifest = {
        "lifecycle": {
            "phases": {
                "intake": {"status": "completed"},
                "vetting": {"status": "completed"},
                "code_security_review": {"status": "pending"},
            },
        },
    }

    result = sync_service.sync_project(db_session, project_id, manifest)

    # Design doc should transition to Closed (completed)
    mock_jira.transition_issue.assert_called_once()
    call_args = mock_jira.transition_issue.call_args
    assert call_args[0][0] == "RHDPCD-101"
    assert call_args[0][1] == TRANSITION_CLOSED
    assert result["changes"]


def test_sync_project_idempotent(sync_service, mock_jira, db_session):
    project_id = uuid.uuid4()
    db_session.add(JiraTaskMapping(
        project_id=project_id,
        jira_epic_key="RHDPCD-100",
        deliverable_type="design_doc",
        jira_issue_key="RHDPCD-101",
        manifest_path="lifecycle.phases.intake.status+lifecycle.phases.vetting.status",
        default_points=3,
    ))
    db_session.commit()

    mock_jira.search_jql.return_value = [
        {"key": "RHDPCD-101", "fields": {"status": {"statusCategory": {"name": "Done"}}}},
    ]

    manifest = {
        "lifecycle": {
            "phases": {
                "intake": {"status": "completed"},
                "vetting": {"status": "completed"},
            },
        },
    }

    result = sync_service.sync_project(db_session, project_id, manifest)
    assert not result["changes"]
    mock_jira.transition_issue.assert_not_called()


def test_get_open_initiatives(sync_service, mock_jira, db_session):
    mock_jira.search_jql.return_value = [
        {"key": "RHDPCD-10", "fields": {"summary": "Summit 2027 Labs"}},
        {"key": "RHDPCD-20", "fields": {"summary": "BAU Content"}},
    ]

    results = sync_service.get_open_initiatives()
    assert len(results) == 2
    assert results[0]["key"] == "RHDPCD-10"
```

- [ ] **Step 6: Implement JiraSyncService class**

Add to `app/services/jira_sync.py` (after the existing functions):

```python
class JiraSyncService:
    """One-directional Jira sync: PH manifest → Jira issues."""

    def __init__(self, jira_client: JiraClient, project_key: str):
        self._jira = jira_client
        self._project_key = project_key

    def create_project(
        self,
        db: Session,
        project_id: UUID,
        manifest: dict,
        initiative_key: str | None,
    ) -> dict:
        deployment_mode = manifest.get("project", {}).get("deployment_mode", "")
        if deployment_mode != "rhdp_published":
            logger.info("Skipping Jira creation for non-onboarded project (mode=%s)", deployment_mode)
            return {"skipped": True, "reason": f"deployment_mode={deployment_mode}"}

        project_name = manifest.get("project", {}).get("name", "Untitled Project")
        deliverables = build_deliverable_list(manifest, deployment_mode)

        # Create Epic
        epic_fields = {
            "project": {"key": self._project_key},
            "issuetype": {"id": ISSUE_TYPE_EPIC},
            "summary": project_name,
            FIELD_EPIC_NAME: project_name,
        }
        if initiative_key:
            epic_fields["parent"] = {"key": initiative_key}

        epic = self._jira.create_issue(epic_fields)
        epic_key = epic["key"]
        logger.info("Created Jira Epic %s for project %s", epic_key, project_name)

        # Create Tasks
        mappings = []
        for d in deliverables:
            task_fields = {
                "project": {"key": self._project_key},
                "issuetype": {"id": ISSUE_TYPE_TASK},
                "summary": d["summary"],
                "parent": {"key": epic_key},
                FIELD_STORY_POINTS: float(d["points"]),
            }
            task = self._jira.create_issue(task_fields)
            logger.info("Created Jira Task %s: %s (%d pts)", task["key"], d["summary"], d["points"])

            mapping = JiraTaskMapping(
                project_id=project_id,
                jira_epic_key=epic_key,
                deliverable_type=d["deliverable_type"],
                module_id=d["module_id"],
                jira_issue_key=task["key"],
                manifest_path=d["manifest_path"],
                default_points=d["points"],
            )
            mappings.append(mapping)

        db.add_all(mappings)
        db.commit()

        return {"epic_key": epic_key, "task_count": len(mappings)}

    def sync_project(
        self,
        db: Session,
        project_id: UUID,
        manifest: dict,
        gate_record: dict | None = None,
    ) -> dict:
        mappings = (
            db.query(JiraTaskMapping)
            .filter(JiraTaskMapping.project_id == project_id)
            .all()
        )
        if not mappings:
            return {"changes": [], "synced": False, "reason": "no_mappings"}

        epic_key = mappings[0].jira_epic_key
        changes = self._diff_and_transition(db, manifest, mappings)

        if changes and gate_record:
            comment = self._format_gate_comment(gate_record, changes)
            try:
                self._jira.add_comment(epic_key, comment)
            except JiraError:
                logger.warning("Failed to add gate comment to %s", epic_key)

        return {"changes": changes, "synced": True}

    def get_open_initiatives(self) -> list[dict]:
        jql = (
            f"project = {self._project_key} "
            f"AND issuetype = Initiative "
            f"AND status != Closed"
        )
        issues = self._jira.search_jql(jql, fields=["summary", "duedate", "labels"])
        return [
            {
                "key": issue["key"],
                "summary": issue["fields"].get("summary", ""),
                "due_date": issue["fields"].get("duedate"),
                "labels": issue["fields"].get("labels", []),
            }
            for issue in issues
        ]

    def get_jira_summary(self, db: Session, project_id: UUID) -> dict | None:
        mappings = (
            db.query(JiraTaskMapping)
            .filter(JiraTaskMapping.project_id == project_id)
            .all()
        )
        if not mappings:
            return None

        epic_key = mappings[0].jira_epic_key
        total_points = sum(m.default_points for m in mappings)

        return {
            "epic_key": epic_key,
            "epic_url": f"https://redhat.atlassian.net/browse/{epic_key}",
            "task_count": len(mappings),
            "points_total": total_points,
        }

    def _diff_and_transition(
        self, db: Session, manifest: dict, mappings: list[JiraTaskMapping]
    ) -> list[dict]:
        epic_key = mappings[0].jira_epic_key
        issue_keys = [m.jira_issue_key for m in mappings]

        jql = f"parent = {epic_key}"
        jira_issues = self._jira.search_jql(jql, fields=["status"], max_results=100)
        jira_status_map = {}
        for issue in jira_issues:
            category = issue["fields"]["status"]["statusCategory"]["name"]
            jira_status_map[issue["key"]] = JIRA_CATEGORY_TO_STATUS.get(category, "pending")

        changes = []
        for mapping in mappings:
            manifest_status = get_manifest_status(
                manifest, mapping.deliverable_type, mapping.module_id
            )
            jira_status = jira_status_map.get(mapping.jira_issue_key, "pending")

            if manifest_status == jira_status:
                continue

            transition_id = STATUS_TO_TRANSITION.get(manifest_status)
            if not transition_id:
                continue

            fields = None
            if manifest_status == "completed":
                fields = {"resolution": {"name": "Done"}}

            try:
                self._jira.transition_issue(mapping.jira_issue_key, transition_id, fields=fields)
                changes.append({
                    "issue_key": mapping.jira_issue_key,
                    "deliverable": mapping.deliverable_type,
                    "module_id": mapping.module_id,
                    "from": jira_status,
                    "to": manifest_status,
                })
                logger.info(
                    "Transitioned %s: %s → %s",
                    mapping.jira_issue_key, jira_status, manifest_status,
                )
            except JiraError as e:
                logger.warning(
                    "Failed to transition %s: %s", mapping.jira_issue_key, e.message
                )

        return changes

    @staticmethod
    def _format_gate_comment(gate_record: dict, changes: list[dict]) -> str:
        phase = gate_record.get("phase", "unknown")
        result = gate_record.get("result", "unknown")
        requested_by = gate_record.get("requested_by", "unknown")
        approved_by = gate_record.get("approved_by", "")
        override = gate_record.get("override", False)

        lines = [f"PH Central gate: {phase} — {result}"]
        if requested_by:
            lines.append(f"Requested by: {requested_by}")
        if approved_by and approved_by != requested_by:
            lines.append(f"Approved by: {approved_by}")
        if override:
            lines.append("⚠ Override: proceeded despite negative validation")

        if changes:
            lines.append(f"\nTasks updated ({len(changes)}):")
            for c in changes[:10]:
                label = c.get("deliverable", "")
                if c.get("module_id"):
                    label += f" [{c['module_id']}]"
                lines.append(f"  • {c['issue_key']} ({label}): {c['from']} → {c['to']}")

        return "\n".join(lines)
```

- [ ] **Step 7: Run all sync tests to verify they pass**

Run: `cd ~/devel/publishing-house/rhdp-publishing-house-central/src/backend && python -m pytest tests/test_jira_sync.py -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
cd ~/devel/publishing-house/rhdp-publishing-house-central
git add src/backend/app/services/jira_sync.py src/backend/tests/test_jira_sync.py
git commit -m "Add JiraSyncService with create, sync, and initiative listing"
```

---

### Task 4: Central Integration — Gate Hooks, ph_get_status, Periodic Sync, Ansible

**Files:**
- Modify: `app/mcp/gate_tools.py` — hook Jira sync after gate passes; add `jira` block to `ph_get_status`
- Modify: `app/main.py` — import `JiraTaskMapping`; hook Jira reconciliation into `_scheduled_refresh`
- Modify: `ansible/templates/manifests-infra.yaml.j2` — add Jira credentials Secret
- Modify: `ansible/templates/manifests-app.yaml.j2` — add Jira env vars
- Test: `tests/test_jira_integration.py`

**Interfaces:**
- Consumes:
  - `JiraSyncService` from Task 3
  - `JiraClient` from Task 1
  - `settings` from `app.core.config`
  - Existing `ph_request_gate` and `ph_get_status` in `gate_tools.py`
  - Existing `_scheduled_refresh` in `main.py`
- Produces:
  - `_get_jira_sync_service() -> JiraSyncService | None` — factory, returns None if Jira not configured
  - `ph_get_status` response now includes `jira: {...} | null`
  - `ph_request_gate` now triggers Jira sync after successful gate
  - Periodic refresh now reconciles Jira state

- [ ] **Step 1: Write failing integration tests**

Create `tests/test_jira_integration.py`:

```python
import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.models.jira_task_mapping import JiraTaskMapping
from app.services.jira_client import JiraClient
from app.services.jira_sync import JiraSyncService


def test_get_status_includes_jira_block(db_session):
    """ph_get_status should include jira summary when mappings exist."""
    project_id = uuid.uuid4()
    db_session.add(JiraTaskMapping(
        project_id=project_id,
        jira_epic_key="RHDPCD-100",
        deliverable_type="design_doc",
        jira_issue_key="RHDPCD-101",
        manifest_path="lifecycle.phases.intake.status",
        default_points=3,
    ))
    db_session.add(JiraTaskMapping(
        project_id=project_id,
        jira_epic_key="RHDPCD-100",
        deliverable_type="final_review",
        jira_issue_key="RHDPCD-102",
        manifest_path="lifecycle.phases.final_review.status",
        default_points=1,
    ))
    db_session.commit()

    mock_jira = MagicMock(spec=JiraClient)
    mock_jira.is_configured = True
    svc = JiraSyncService(jira_client=mock_jira, project_key="RHDPCD")

    summary = svc.get_jira_summary(db_session, project_id)

    assert summary is not None
    assert summary["epic_key"] == "RHDPCD-100"
    assert summary["epic_url"] == "https://redhat.atlassian.net/browse/RHDPCD-100"
    assert summary["points_total"] == 4
    assert summary["task_count"] == 2


def test_get_status_returns_none_without_mappings(db_session):
    mock_jira = MagicMock(spec=JiraClient)
    svc = JiraSyncService(jira_client=mock_jira, project_key="RHDPCD")

    summary = svc.get_jira_summary(db_session, uuid.uuid4())
    assert summary is None


def test_jira_service_factory_returns_none_when_not_configured():
    from app.services.jira_sync import create_jira_sync_service

    with patch("app.services.jira_sync.settings") as mock_settings:
        mock_settings.jira_url = ""
        mock_settings.jira_email = ""
        mock_settings.jira_api_token = ""
        mock_settings.jira_project_key = "RHDPCD"
        result = create_jira_sync_service()
        assert result is None


def test_jira_service_factory_returns_service_when_configured():
    from app.services.jira_sync import create_jira_sync_service

    with patch("app.services.jira_sync.settings") as mock_settings:
        mock_settings.jira_url = "https://test.atlassian.net"
        mock_settings.jira_email = "test@example.com"
        mock_settings.jira_api_token = "token"
        mock_settings.jira_project_key = "RHDPCD"
        result = create_jira_sync_service()
        assert result is not None
        assert isinstance(result, JiraSyncService)
```

- [ ] **Step 2: Add factory function to jira_sync.py**

Add at the bottom of `app/services/jira_sync.py`:

```python
from app.core.config import settings


def create_jira_sync_service() -> JiraSyncService | None:
    if not (settings.jira_url and settings.jira_email and settings.jira_api_token):
        logger.info("Jira integration not configured — skipping")
        return None
    client = JiraClient(
        base_url=settings.jira_url,
        email=settings.jira_email,
        api_token=settings.jira_api_token,
        allowed_project_key=settings.jira_project_key,
    )
    return JiraSyncService(jira_client=client, project_key=settings.jira_project_key)
```

- [ ] **Step 3: Run integration tests**

Run: `cd ~/devel/publishing-house/rhdp-publishing-house-central/src/backend && python -m pytest tests/test_jira_integration.py -v`
Expected: All PASS

- [ ] **Step 4: Hook Jira sync into ph_request_gate**

Modify `app/mcp/gate_tools.py`. After the existing gate evaluation returns an approved result, add the Jira sync call. Find the `ph_request_gate` function and add after the gate result is computed:

```python
from app.services.jira_sync import create_jira_sync_service

# Add after gate evaluation succeeds (result["approved"] == True):
if result.get("approved"):
    jira_svc = create_jira_sync_service()
    if jira_svc:
        try:
            mappings = db.query(JiraTaskMapping).filter_by(project_id=project.id).first()
            if mappings:
                jira_svc.sync_project(db, project.id, manifest, gate_record=result)
            else:
                # First gate pass for an onboarded project — create Jira Epic+Tasks
                deployment_mode = manifest.get("project", {}).get("deployment_mode", "")
                if deployment_mode == "rhdp_published":
                    # Initiative key comes from manifest (set during intake)
                    initiative_key = (
                        manifest.get("integrations", {})
                        .get("jira", {})
                        .get("initiative_key")
                    )
                    jira_svc.create_project(db, project.id, manifest, initiative_key=initiative_key)
        except Exception:
            logger.warning("Jira sync failed for %s — non-blocking", project.id, exc_info=True)
```

Import `JiraTaskMapping` at the top of `gate_tools.py`:

```python
from app.models.jira_task_mapping import JiraTaskMapping
```

- [ ] **Step 5: Add jira block to ph_get_status response**

Modify `app/mcp/gate_tools.py`. In the `ph_get_status` function, after computing the status result, add the Jira summary. Find where the result dict is constructed and add:

```python
# After result dict is built:
jira_summary = None
jira_svc = create_jira_sync_service()
if jira_svc:
    jira_summary = jira_svc.get_jira_summary(db, project.id)
result["jira"] = jira_summary
```

- [ ] **Step 6: Hook Jira reconciliation into periodic refresh**

Modify `app/main.py`. In the `_scheduled_refresh` function, after `refresh_all_projects(db, ...)`, add Jira reconciliation:

```python
from app.services.jira_sync import create_jira_sync_service

def _scheduled_refresh():
    db = SessionLocal()
    try:
        refresh_all_projects(db, github_token=settings.github_token)
        _reconcile_jira(db)
    finally:
        db.close()


def _reconcile_jira(db):
    jira_svc = create_jira_sync_service()
    if not jira_svc:
        return

    from app.models.jira_task_mapping import JiraTaskMapping
    from app.models.project import Project

    project_ids_with_jira = (
        db.query(JiraTaskMapping.project_id)
        .distinct()
        .all()
    )

    for (project_id,) in project_ids_with_jira:
        project = db.query(Project).filter_by(id=project_id).first()
        if not project or not project.cached_manifest_data:
            continue
        try:
            jira_svc.sync_project(db, project_id, project.cached_manifest_data)
        except Exception:
            logger.warning("Jira reconciliation failed for %s", project_id, exc_info=True)
```

Add `JiraTaskMapping` to the model import in `main.py`:

```python
from app.models.jira_task_mapping import JiraTaskMapping  # noqa: F401 (Alembic)
```

- [ ] **Step 7: Add Ansible templates for Jira credentials**

Modify `ansible/templates/manifests-infra.yaml.j2`. Add the Jira credentials Secret after the existing github-token Secret:

```jinja2
{% if jira_email is defined and jira_api_token is defined %}
---
apiVersion: v1
kind: Secret
metadata:
  name: {{ app_name }}-jira-credentials
  namespace: {{ target_namespace }}
type: Opaque
stringData:
  email: "{{ jira_email }}"
  token: "{{ jira_api_token }}"
{% endif %}
```

Modify `ansible/templates/manifests-app.yaml.j2`. Add Jira env vars to the backend container's env section:

```jinja2
{% if jira_url is defined %}
            - name: JIRA_URL
              value: "{{ jira_url }}"
            - name: JIRA_PROJECT_KEY
              value: "{{ jira_project_key | default('RHDPCD') }}"
            - name: JIRA_EMAIL
              valueFrom:
                secretKeyRef:
                  name: {{ app_name }}-jira-credentials
                  key: email
            - name: JIRA_API_TOKEN
              valueFrom:
                secretKeyRef:
                  name: {{ app_name }}-jira-credentials
                  key: token
{% endif %}
```

- [ ] **Step 8: Run full test suite**

Run: `cd ~/devel/publishing-house/rhdp-publishing-house-central/src/backend && python -m pytest tests/ -v --timeout=30`
Expected: All PASS

- [ ] **Step 9: Commit**

```bash
cd ~/devel/publishing-house/rhdp-publishing-house-central
git add src/backend/app/mcp/gate_tools.py src/backend/app/main.py src/backend/tests/test_jira_integration.py ansible/templates/manifests-infra.yaml.j2 ansible/templates/manifests-app.yaml.j2
git commit -m "Integrate Jira sync into gate passes, status, periodic refresh, and Ansible"
```

---

## Verification

After all tasks complete:

1. **Unit tests pass**: `python -m pytest tests/ -v --timeout=30` — all green
2. **Config works**: Set `JIRA_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` env vars locally, verify `settings.jira_url` loads
3. **Jira client talks to real API**: Quick manual test creating a test issue in RHDPCD (then delete it)
4. **Gate-driven sync works end-to-end**: Register a test project, advance a gate, verify Jira Epic+Tasks appear
5. **ph_get_status includes jira block**: Call `ph_get_status` for a project with Jira mappings, verify `jira` field populated
6. **Periodic reconciliation runs**: Check APScheduler logs for Jira reconciliation messages
7. **Ansible deploy works**: `ansible-playbook ansible/deploy.yml -e env=central-dev --tags apply` — verify Secret created, env vars mounted
