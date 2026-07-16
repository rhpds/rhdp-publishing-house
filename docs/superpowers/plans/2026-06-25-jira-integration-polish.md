# Jira Integration Polish — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the three remaining Jira integration items from RHDPCD-77: assignee from owner_email, dashboard sync button, and error edge case handling.

**Design spec:** `docs/superpowers/specs/2026-05-05-jira-integration-design.md` — see sections "Assignee from owner_email", "Dashboard Sync Button", and "Error Edge Cases — Manifest as Truth" for detailed design.

**Codebase:** `~/devel/publishing-house/rhdp-publishing-house-central/src/backend/`

**Tech Stack:** Python 3.11, httpx (sync), SQLAlchemy ORM, FastAPI, Next.js + PatternFly 6, pytest

## Global Constraints

- All Jira API calls go through `JiraClient` — no direct HTTP calls elsewhere.
- Jira sync is non-blocking — log errors, never fail gate passes or API calls.
- PH never overwrites Assignee or story points on existing Jira issues.
- Tests: SQLite-backed, mocked httpx for Jira API calls. `db_session` fixture from `conftest.py`.
- Follow existing patterns in `jira_client.py`, `jira_sync.py`, `gate_tools.py`.

---

### Task 1: JiraClient — Add `search_users` and `update_issue` Methods

**Files:**
- Modify: `app/services/jira_client.py`
- Modify: `tests/test_jira_client.py`

**Interfaces:**
- `JiraClient.search_users(query: str, max_results: int = 10) -> list[dict]` — Jira user search API
- `JiraClient.update_issue(issue_key: str, fields: dict) -> None` — PUT fields on existing issue

- [ ] **Step 1: Write failing tests**

Add to `tests/test_jira_client.py`:

```python
def test_search_users(jira):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"accountId": "70121:abc123", "displayName": "Tyrell Dev", "emailAddress": "tyrell@redhat.com"},
    ]
    mock_response.raise_for_status = MagicMock()

    with patch.object(jira._client, "get", return_value=mock_response) as mock_get:
        results = jira.search_users("tyrell@redhat.com")

    assert len(results) == 1
    assert results[0]["accountId"] == "70121:abc123"
    mock_get.assert_called_once()


def test_search_users_empty(jira):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = []
    mock_response.raise_for_status = MagicMock()

    with patch.object(jira._client, "get", return_value=mock_response):
        results = jira.search_users("nobody@example.com")

    assert results == []


def test_update_issue(jira):
    mock_response = MagicMock()
    mock_response.status_code = 204
    mock_response.raise_for_status = MagicMock()

    with patch.object(jira._client, "put", return_value=mock_response) as mock_put:
        jira.update_issue("RHDPCD-42", {"customfield_10028": 0.0})

    mock_put.assert_called_once()


def test_update_issue_rejects_wrong_project():
    jira = JiraClient(
        base_url="https://test.atlassian.net",
        email="test@example.com",
        api_token="test-token",
        allowed_project_key="RHDPCD",
    )
    with pytest.raises(JiraError, match="Issue key .* not in allowed project"):
        jira.update_issue("OTHER-1", {"summary": "sneaky"})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/devel/publishing-house/rhdp-publishing-house-central/src/backend && python -m pytest tests/test_jira_client.py -v -k "search_users or update_issue"
```

- [ ] **Step 3: Implement `search_users` and `update_issue`**

Add to `app/services/jira_client.py`, after the `get_issue` method:

```python
def search_users(self, query: str, max_results: int = 10) -> list[dict]:
    """Search for Jira users by email or display name."""
    params = {"query": query, "maxResults": max_results}
    try:
        resp = self._client.get(
            self._url("/user/search"),
            headers=self._headers,
            params=params,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        self._handle_error(e)

def update_issue(self, issue_key: str, fields: dict) -> None:
    """Update fields on an existing Jira issue."""
    self._enforce_issue_prefix(issue_key)
    try:
        resp = self._client.put(
            self._url(f"/issue/{issue_key}"),
            headers=self._headers,
            json={"fields": fields},
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        self._handle_error(e)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/devel/publishing-house/rhdp-publishing-house-central/src/backend && python -m pytest tests/test_jira_client.py -v
```

- [ ] **Step 5: Commit**

---

### Task 2: Assignee from owner_email

**Files:**
- Modify: `app/services/jira_sync.py` — `create_project` method
- Modify: `tests/test_jira_sync.py`

**Dependencies:** Task 1 (`search_users` method)

- [ ] **Step 1: Write failing tests**

Add to `tests/test_jira_sync.py`:

```python
def test_create_project_sets_assignee(sync_service, mock_jira, db_session):
    project_id = uuid.uuid4()
    mock_jira.search_users.return_value = [
        {"accountId": "70121:abc123", "displayName": "Tyrell Dev"},
    ]
    mock_jira.create_issue.side_effect = [
        {"key": "RHDPCD-200", "id": "200"},  # Epic
        {"key": "RHDPCD-201", "id": "201"},  # Design Doc
        {"key": "RHDPCD-202", "id": "202"},  # Module 1: Outline
        {"key": "RHDPCD-203", "id": "203"},  # Module 1: Content
        {"key": "RHDPCD-204", "id": "204"},  # Module 1: Automation
        {"key": "RHDPCD-205", "id": "205"},  # Module 1: Verified
        {"key": "RHDPCD-206", "id": "206"},  # Code Review
        {"key": "RHDPCD-207", "id": "207"},  # Security Review
        {"key": "RHDPCD-208", "id": "208"},  # E2E Test
        {"key": "RHDPCD-209", "id": "209"},  # Final Review
    ]

    manifest = {
        "project": {
            "name": "Test Lab",
            "deployment_mode": "rhdp_published",
            "owner_email": "tyrell@redhat.com",
        },
        "lifecycle": {
            "phases": {
                "writing": {
                    "modules": [{"id": "module-01", "title": "First Module", "status": "pending"}],
                },
            },
        },
    }

    sync_service.create_project(db_session, project_id, manifest, "RHDPCD-10")

    # Verify user search was called with owner email
    mock_jira.search_users.assert_called_once_with("tyrell@redhat.com")

    # Verify assignee set on Epic (first create_issue call)
    epic_fields = mock_jira.create_issue.call_args_list[0][0][0]
    assert epic_fields["assignee"]["accountId"] == "70121:abc123"

    # Verify assignee set on Tasks (subsequent calls)
    task_fields = mock_jira.create_issue.call_args_list[1][0][0]
    assert task_fields["assignee"]["accountId"] == "70121:abc123"


def test_create_project_no_assignee_when_user_not_found(sync_service, mock_jira, db_session):
    project_id = uuid.uuid4()
    mock_jira.search_users.return_value = []
    mock_jira.create_issue.side_effect = [
        {"key": "RHDPCD-300", "id": "300"},
        {"key": "RHDPCD-301", "id": "301"},
        {"key": "RHDPCD-302", "id": "302"},
        {"key": "RHDPCD-303", "id": "303"},
        {"key": "RHDPCD-304", "id": "304"},
        {"key": "RHDPCD-305", "id": "305"},
        {"key": "RHDPCD-306", "id": "306"},
        {"key": "RHDPCD-307", "id": "307"},
        {"key": "RHDPCD-308", "id": "308"},
        {"key": "RHDPCD-309", "id": "309"},
    ]

    manifest = {
        "project": {"name": "Test Lab", "deployment_mode": "rhdp_published"},
        "lifecycle": {"phases": {"writing": {"modules": [{"id": "module-01", "title": "First", "status": "pending"}]}}},
    }

    result = sync_service.create_project(db_session, project_id, manifest, None)
    assert result["epic_key"] == "RHDPCD-300"

    # Assignee should NOT be set when user not found
    epic_fields = mock_jira.create_issue.call_args_list[0][0][0]
    assert "assignee" not in epic_fields
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/devel/publishing-house/rhdp-publishing-house-central/src/backend && python -m pytest tests/test_jira_sync.py -v -k "assignee"
```

- [ ] **Step 3: Implement assignee lookup in `create_project`**

Modify `JiraSyncService.create_project` in `app/services/jira_sync.py`. Add after the deployment_mode check and before Epic creation:

```python
# Look up Jira account ID from owner email
owner_email = manifest.get("project", {}).get("owner_email")
assignee_account_id = None
if owner_email:
    try:
        users = self._jira.search_users(owner_email)
        if users:
            assignee_account_id = users[0].get("accountId")
            logger.info("Resolved %s to Jira accountId %s", owner_email, assignee_account_id)
        else:
            logger.warning("No Jira user found for email %s — creating issues unassigned", owner_email)
    except JiraError as e:
        logger.warning("Jira user lookup failed for %s: %s — creating issues unassigned", owner_email, e.message)
```

Then add to `epic_fields` before `create_issue`:

```python
if assignee_account_id:
    epic_fields["assignee"] = {"accountId": assignee_account_id}
```

And add to `task_fields` in the deliverable loop:

```python
if assignee_account_id:
    task_fields["assignee"] = {"accountId": assignee_account_id}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/devel/publishing-house/rhdp-publishing-house-central/src/backend && python -m pytest tests/test_jira_sync.py -v
```

- [ ] **Step 5: Commit**

---

### Task 3: Dashboard Sync Button

**Files:**
- Modify: `src/backend/app/api/projects.py` — add `POST /projects/{id}/sync-jira`
- Modify: `src/frontend/src/services/api.ts` — add `syncProjectJira` method
- Modify: `src/frontend/src/app/projects/[id]/page.tsx` — add dropdown item + handler
- Add test: `tests/test_api_projects_central.py` (or inline in existing test file)

**Dependencies:** None (uses existing `JiraSyncService.sync_project`)

- [ ] **Step 1: Add REST API endpoint**

Add to `app/api/projects.py`, after the `refresh_project` endpoint:

```python
from app.services.jira_sync import create_jira_sync_service

@router.post("/{project_id}/sync-jira")
def sync_project_jira(project_id: uuid.UUID, db: Session = Depends(get_db)):
    """Manually trigger Jira sync for a project."""
    project = db.query(Project).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project {project_id} not found")

    jira_svc = create_jira_sync_service()
    if not jira_svc:
        return {"synced": False, "reason": "jira_not_configured"}

    if not project.cached_manifest_data:
        return {"synced": False, "reason": "no_manifest_data"}

    try:
        result = jira_svc.sync_project(db, project.id, project.cached_manifest_data)
        logger.info("REST sync-jira: project=%s, changes=%d", project.name, len(result.get("changes", [])))
        return result
    except Exception:
        logger.exception("REST sync-jira failed: project=%s", project.name)
        return {"synced": False, "reason": "sync_error"}
```

- [ ] **Step 2: Add API client method**

Add to `src/frontend/src/services/api.ts`:

```typescript
syncProjectJira: (id: string) =>
  request<{ synced: boolean; changes?: Array<Record<string, unknown>>; reason?: string }>(`/projects/${id}/sync-jira`, { method: "POST" }),
```

- [ ] **Step 3: Add "Sync to Jira" to project detail dropdown**

Modify `src/frontend/src/app/projects/[id]/page.tsx`:

Add state: `const [syncing, setSyncing] = useState(false);`

Add handler after `handleRefresh`:

```typescript
const handleSyncJira = async () => {
  setKebabOpen(false);
  setSyncing(true);
  try {
    const result = await api.syncProjectJira(projectId);
    if (result.synced) {
      const count = result.changes?.length ?? 0;
      console.log(`Jira sync: ${count} task(s) updated`);
    } else {
      console.log(`Jira sync skipped: ${result.reason}`);
    }
  } catch (err) { console.error("Jira sync failed:", err); }
  finally { setSyncing(false); }
};
```

Add dropdown item after "Refresh from GitHub" (only for rhdp_published projects):

```tsx
{project.deployment_mode === "rhdp_published" && (
  <DropdownItem key="sync-jira" onClick={handleSyncJira} isDisabled={syncing}>
    {syncing ? "Syncing…" : "Sync to Jira"}
  </DropdownItem>
)}
```

- [ ] **Step 4: Write backend test**

Add to `tests/test_api_projects_central.py` (or create if needed):

```python
def test_sync_jira_endpoint_no_jira_configured(client, db_session):
    """sync-jira returns graceful response when Jira not configured."""
    # Create a project first
    project = Project(name="Test", repo_url="git@github.com:test/test.git", branch="main")
    db_session.add(project)
    db_session.commit()

    with patch("app.api.projects.create_jira_sync_service", return_value=None):
        response = client.post(f"/api/v1/projects/{project.id}/sync-jira")

    assert response.status_code == 200
    assert response.json()["synced"] is False
    assert response.json()["reason"] == "jira_not_configured"
```

- [ ] **Step 5: Run tests**

```bash
cd ~/devel/publishing-house/rhdp-publishing-house-central/src/backend && python -m pytest tests/test_api_projects_central.py -v
```

- [ ] **Step 6: Commit**

---

### Task 4: Error Edge Cases — Manifest as Truth

**Files:**
- Modify: `app/services/jira_sync.py` — `sync_project` and `_diff_and_transition` methods
- Modify: `tests/test_jira_sync.py`

**Dependencies:** Task 1 (`update_issue` method)

This is the most complex task. Three edge cases need to be handled in `sync_project`:

1. **Jira task deleted** → recreate and update mapping
2. **New module in manifest** → create missing tasks
3. **Module removed from manifest** → close with 0 points

- [ ] **Step 1: Write failing tests for deleted task detection**

Add to `tests/test_jira_sync.py`:

```python
def test_sync_recreates_deleted_task(sync_service, mock_jira, db_session):
    """When a Jira task is deleted externally, sync recreates it."""
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

    # Jira returns NO child issues — RHDPCD-101 was deleted
    mock_jira.search_jql.return_value = []
    mock_jira.create_issue.return_value = {"key": "RHDPCD-999", "id": "999"}

    manifest = {
        "project": {"deployment_mode": "rhdp_published"},
        "lifecycle": {"phases": {
            "intake": {"status": "completed"},
            "vetting": {"status": "completed"},
            "writing": {"modules": []},
        }},
    }

    result = sync_service.sync_project(db_session, project_id, manifest)

    # Task should be recreated
    mock_jira.create_issue.assert_called_once()
    assert result["synced"] is True

    # Mapping should be updated with new key
    mapping = db_session.query(JiraTaskMapping).filter_by(project_id=project_id).first()
    assert mapping.jira_issue_key == "RHDPCD-999"
```

- [ ] **Step 2: Write failing tests for missing module tasks**

```python
def test_sync_creates_tasks_for_new_module(sync_service, mock_jira, db_session):
    """When manifest has a module not in mappings, create the tasks."""
    project_id = uuid.uuid4()
    # Existing mapping: only design_doc exists
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
    # For creating new module tasks
    mock_jira.create_issue.side_effect = [
        {"key": f"RHDPCD-{500+i}", "id": str(500+i)} for i in range(20)
    ]

    manifest = {
        "project": {"deployment_mode": "rhdp_published"},
        "lifecycle": {"phases": {
            "intake": {"status": "completed"},
            "vetting": {"status": "completed"},
            "writing": {"modules": [{"id": "module-01", "title": "New Module", "status": "pending"}]},
            "automation": {"status": "pending"},
        }},
    }

    result = sync_service.sync_project(db_session, project_id, manifest)

    # New tasks should be created (module_outline, module_content, module_automation, module_verified, code_review, security_review, e2e_test, final_review)
    assert mock_jira.create_issue.call_count > 0
    assert result["synced"] is True

    # Mappings should be expanded
    mappings = db_session.query(JiraTaskMapping).filter_by(project_id=project_id).all()
    assert len(mappings) > 1
```

- [ ] **Step 3: Write failing tests for removed module**

```python
def test_sync_closes_tasks_for_removed_module(sync_service, mock_jira, db_session):
    """When manifest no longer has a module, close its tasks with 0 points."""
    project_id = uuid.uuid4()
    # Module-01 tasks exist in mappings
    for dtype in ["module_outline", "module_content", "module_automation", "module_verified"]:
        db_session.add(JiraTaskMapping(
            project_id=project_id,
            jira_epic_key="RHDPCD-100",
            deliverable_type=dtype,
            module_id="module-01",
            jira_issue_key=f"RHDPCD-{hash(dtype) % 1000 + 200}",
            manifest_path=f"lifecycle.phases.writing.modules[id=module-01].status",
            default_points=5,
        ))
    # Design doc (project-level, should NOT be removed)
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
        {"key": f"RHDPCD-{hash(dt) % 1000 + 200}", "fields": {"status": {"statusCategory": {"name": "To Do"}}}}
        for dt in ["module_outline", "module_content", "module_automation", "module_verified"]
    ] + [
        {"key": "RHDPCD-101", "fields": {"status": {"statusCategory": {"name": "Done"}}}},
    ]

    # Manifest with NO modules — module-01 was removed
    manifest = {
        "project": {"deployment_mode": "rhdp_published"},
        "lifecycle": {"phases": {
            "intake": {"status": "completed"},
            "vetting": {"status": "completed"},
            "writing": {"modules": []},
        }},
    }

    result = sync_service.sync_project(db_session, project_id, manifest)

    # Module tasks should be transitioned to Done
    assert mock_jira.transition_issue.call_count == 4
    # Comments should be added
    assert mock_jira.add_comment.call_count >= 4
    # Points should be zeroed
    assert mock_jira.update_issue.call_count == 4

    # Mapping points should be updated to 0
    module_mappings = db_session.query(JiraTaskMapping).filter_by(
        project_id=project_id, module_id="module-01"
    ).all()
    for m in module_mappings:
        assert m.default_points == 0
```

- [ ] **Step 4: Run tests to verify they fail**

```bash
cd ~/devel/publishing-house/rhdp-publishing-house-central/src/backend && python -m pytest tests/test_jira_sync.py -v -k "recreate or new_module or removed_module"
```

- [ ] **Step 5: Implement error edge cases in `sync_project`**

Modify `JiraSyncService.sync_project` in `app/services/jira_sync.py`. The structure becomes:

```python
def sync_project(self, db, project_id, manifest, gate_record=None):
    mappings = db.query(JiraTaskMapping).filter_by(project_id=project_id).all()
    if not mappings:
        return {"changes": [], "synced": False, "reason": "no_mappings"}

    epic_key = mappings[0].jira_epic_key
    deployment_mode = manifest.get("project", {}).get("deployment_mode", "rhdp_published")
    changes = []

    # 1. Handle new modules (manifest has deliverables not in mappings)
    if deployment_mode == "rhdp_published":
        new_changes = self._create_missing_tasks(db, project_id, epic_key, manifest, mappings)
        changes.extend(new_changes)
        if new_changes:
            mappings = db.query(JiraTaskMapping).filter_by(project_id=project_id).all()

    # 2. Handle removed modules (mappings have deliverables not in manifest)
    if deployment_mode == "rhdp_published":
        removed_changes = self._close_orphaned_tasks(db, manifest, mappings)
        changes.extend(removed_changes)

    # 3. Diff and transition (handles deleted task recreation internally)
    transition_changes = self._diff_and_transition(db, manifest, mappings, epic_key)
    changes.extend(transition_changes)

    if changes and gate_record:
        comment = self._format_gate_comment(gate_record, changes)
        try:
            self._jira.add_comment(epic_key, comment)
        except JiraError:
            logger.warning("Failed to add gate comment to %s", epic_key)

    return {"changes": changes, "synced": True}
```

Add the new helper methods to the class.

- [ ] **Step 6: Implement `_create_missing_tasks`**

```python
def _create_missing_tasks(self, db, project_id, epic_key, manifest, mappings):
    manifest_deliverables = build_deliverable_list(manifest, "rhdp_published")
    existing_keys = {(m.deliverable_type, m.module_id) for m in mappings}
    missing = [d for d in manifest_deliverables
               if (d["deliverable_type"], d["module_id"]) not in existing_keys]

    changes = []
    for d in missing:
        task_fields = {
            "project": {"key": self._project_key},
            "issuetype": {"id": ISSUE_TYPE_TASK},
            "summary": d["summary"],
            "parent": {"key": epic_key},
            FIELD_STORY_POINTS: float(d["points"]),
        }
        try:
            task = self._jira.create_issue(task_fields)
            db.add(JiraTaskMapping(
                project_id=project_id,
                jira_epic_key=epic_key,
                deliverable_type=d["deliverable_type"],
                module_id=d["module_id"],
                jira_issue_key=task["key"],
                manifest_path=d["manifest_path"],
                default_points=d["points"],
            ))
            changes.append({"issue_key": task["key"], "action": "created_missing",
                            "deliverable": d["deliverable_type"], "module_id": d["module_id"]})
            logger.info("Created missing task %s for %s", task["key"], d["summary"])
        except JiraError as e:
            logger.warning("Failed to create missing task: %s", e.message)

    if changes:
        db.commit()
    return changes
```

- [ ] **Step 7: Implement `_close_orphaned_tasks`**

```python
def _close_orphaned_tasks(self, db, manifest, mappings):
    manifest_deliverables = build_deliverable_list(manifest, "rhdp_published")
    manifest_keys = {(d["deliverable_type"], d["module_id"]) for d in manifest_deliverables}
    orphaned = [m for m in mappings
                if (m.deliverable_type, m.module_id) not in manifest_keys]

    changes = []
    for mapping in orphaned:
        try:
            self._jira.transition_issue(mapping.jira_issue_key, TRANSITION_CLOSED,
                                         fields={"resolution": {"name": "Done"}})
            self._jira.add_comment(mapping.jira_issue_key, "Module removed from manifest")
            self._jira.update_issue(mapping.jira_issue_key, {FIELD_STORY_POINTS: 0.0})
            mapping.default_points = 0
            changes.append({"issue_key": mapping.jira_issue_key, "action": "removed",
                            "deliverable": mapping.deliverable_type, "module_id": mapping.module_id})
            logger.info("Closed orphaned task %s (module removed)", mapping.jira_issue_key)
        except JiraError as e:
            logger.warning("Failed to close orphaned task %s: %s", mapping.jira_issue_key, e.message)

    if changes:
        db.commit()
    return changes
```

- [ ] **Step 8: Update `_diff_and_transition` for deleted task recreation**

In the existing `_diff_and_transition`, after building `jira_status_map`, add detection and recreation of deleted tasks:

```python
# Detect and recreate deleted tasks
for mapping in mappings:
    if mapping.jira_issue_key not in jira_status_map and mapping.default_points > 0:
        logger.warning("Jira task %s deleted externally — recreating", mapping.jira_issue_key)
        task_fields = {
            "project": {"key": self._project_key},
            "issuetype": {"id": ISSUE_TYPE_TASK},
            "summary": self._build_task_summary(mapping),
            "parent": {"key": epic_key},
            FIELD_STORY_POINTS: float(mapping.default_points),
        }
        try:
            new_task = self._jira.create_issue(task_fields)
            old_key = mapping.jira_issue_key
            mapping.jira_issue_key = new_task["key"]
            db.commit()
            jira_status_map[new_task["key"]] = "pending"
            changes.append({"issue_key": new_task["key"], "action": "recreated", "old_key": old_key})
        except JiraError as e:
            logger.warning("Failed to recreate task: %s", e.message)
```

Add helper method:

```python
def _build_task_summary(self, mapping: JiraTaskMapping) -> str:
    """Rebuild task summary from mapping metadata."""
    d = DELIVERABLE_DEFAULTS.get(DeliverableType(mapping.deliverable_type))
    if not d:
        return mapping.deliverable_type
    summary = d["summary"]
    if mapping.module_id and "{n}" in summary:
        # Extract module number from module_id (e.g., "module-03" → 3)
        try:
            n = int(mapping.module_id.split("-")[-1])
        except (ValueError, IndexError):
            n = 0
        summary = summary.format(n=n, title=mapping.module_id)
    return summary
```

- [ ] **Step 9: Run all sync tests**

```bash
cd ~/devel/publishing-house/rhdp-publishing-house-central/src/backend && python -m pytest tests/test_jira_sync.py -v
```

- [ ] **Step 10: Run full test suite**

```bash
cd ~/devel/publishing-house/rhdp-publishing-house-central/src/backend && python -m pytest tests/ -v --timeout=30
```

- [ ] **Step 11: Commit**

---

## Verification

After all tasks complete:

1. **All tests pass**: `python -m pytest tests/ -v --timeout=30` — all green
2. **User lookup works**: Set Jira env vars, test `search_users("nstephan@redhat.com")` returns results
3. **Assignee set on creation**: Create a test project, verify Epic and Tasks have Assignee
4. **Sync button works**: Dashboard → project detail → kebab → "Sync to Jira" → verify response
5. **Deleted task recreation**: Delete a task in Jira, run sync, verify it's recreated
6. **Missing module tasks**: Add a module to manifest, run sync, verify tasks appear
7. **Removed module closure**: Remove a module from manifest, run sync, verify tasks closed with 0 pts
