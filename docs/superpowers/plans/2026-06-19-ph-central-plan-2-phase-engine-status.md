# PH Central Plan 2: PhaseEngine + ph_get_status

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Central can compute phase status from a manifest and determine the next recommended action. The PhaseEngine defines phase profiles per deployment mode with prerequisite rules.

**Architecture:** PhaseEngine is a pure logic module (no DB, no I/O) that encodes phase sequences, prerequisite rules, and gate types per deployment mode. `ph_get_status` is a new MCP tool that fetches the manifest from git and uses PhaseEngine to compute status. Builds on Plan 1's GitRepoReader and project registration.

**Tech Stack:** Python 3.11+, pytest

## Global Constraints

- Python 3.11+, all code under `src/backend/app/`
- MCP tools create their own `SessionLocal()` — no FastAPI dependency injection
- Tests use SQLite in-memory
- `yaml.safe_load` always
- Working branch: `feature/ph-central-registration`

---

### Task 1: PhaseEngine — Phase Profiles and Prerequisites

**Files:**
- Create: `src/backend/app/services/phase_engine.py`
- Create: `src/backend/tests/test_phase_engine.py`

**Interfaces:**
- Produces:
  - `PhaseEngine.get_profile(deployment_mode: str) -> list[PhaseDefinition]`
  - `PhaseEngine.get_next_action(manifest: dict) -> dict`
  - `PhaseEngine.check_prerequisites(manifest: dict, target_phase: str) -> dict`
  - `PhaseDefinition` — dataclass with name, gate_type (hard/soft), prerequisites

- [ ] **Step 1: Write failing tests**

```python
# tests/test_phase_engine.py
"""Tests for PhaseEngine — phase profiles, prerequisites, next action."""
import pytest

from app.services.phase_engine import PhaseEngine, PhaseDefinition


class TestPhaseProfiles:
    def test_onboarded_profile_has_all_required_phases(self):
        profile = PhaseEngine.get_profile("rhdp_published")
        names = [p.name for p in profile]
        assert "intake" in names
        assert "vetting" in names
        assert "approval" in names
        assert "writing" in names
        assert "editing" in names
        assert "code_security_review" in names
        assert "final_review" in names

    def test_self_published_profile_matches_onboarded(self):
        onboarded = PhaseEngine.get_profile("rhdp_published")
        self_pub = PhaseEngine.get_profile("self_published")
        assert [p.name for p in onboarded] == [p.name for p in self_pub]

    def test_self_published_has_soft_approval_gate(self):
        profile = PhaseEngine.get_profile("self_published")
        approval = next(p for p in profile if p.name == "approval")
        assert approval.gate_type == "soft"

    def test_onboarded_has_hard_approval_gate(self):
        profile = PhaseEngine.get_profile("rhdp_published")
        approval = next(p for p in profile if p.name == "approval")
        assert approval.gate_type == "hard"

    def test_express_profile_is_abbreviated(self):
        profile = PhaseEngine.get_profile("express")
        names = [p.name for p in profile]
        assert "intake" in names
        assert "vetting" in names
        assert "base_finding" in names
        assert "writing" not in names

    def test_unknown_mode_raises(self):
        with pytest.raises(ValueError, match="Unknown deployment mode"):
            PhaseEngine.get_profile("invalid_mode")


class TestPrerequisites:
    def test_vetting_requires_intake_completed(self):
        manifest = _manifest(current="vetting", intake="completed")
        result = PhaseEngine.check_prerequisites(manifest, "vetting")
        assert result["met"] is True

    def test_vetting_blocked_when_intake_pending(self):
        manifest = _manifest(current="intake", intake="pending")
        result = PhaseEngine.check_prerequisites(manifest, "vetting")
        assert result["met"] is False
        assert "intake" in result["reason"].lower()

    def test_approval_requires_vetting_completed(self):
        manifest = _manifest(current="spec_refinement", intake="completed", vetting="completed", spec_refinement="completed")
        result = PhaseEngine.check_prerequisites(manifest, "approval")
        assert result["met"] is True

    def test_editing_requires_writing_and_automation(self):
        manifest = _manifest(
            current="writing",
            intake="completed", vetting="completed", spec_refinement="completed",
            approval="completed", writing="completed", automation="completed",
        )
        result = PhaseEngine.check_prerequisites(manifest, "editing")
        assert result["met"] is True

    def test_editing_blocked_when_writing_incomplete(self):
        manifest = _manifest(
            current="writing",
            intake="completed", vetting="completed", spec_refinement="completed",
            approval="completed", writing="in_progress", automation="completed",
        )
        result = PhaseEngine.check_prerequisites(manifest, "editing")
        assert result["met"] is False


class TestNextAction:
    def test_next_action_after_intake(self):
        manifest = _manifest(current="intake", intake="completed")
        result = PhaseEngine.get_next_action(manifest)
        assert result["next_phase"] == "vetting"

    def test_next_action_during_writing(self):
        manifest = _manifest(
            current="writing",
            intake="completed", vetting="completed", spec_refinement="completed",
            approval="completed", writing="in_progress",
        )
        result = PhaseEngine.get_next_action(manifest)
        assert result["next_phase"] == "writing"
        assert result["action"] == "continue"

    def test_next_action_all_complete(self):
        manifest = _manifest(
            current="ready_for_publishing",
            intake="completed", vetting="completed", spec_refinement="completed",
            approval="completed", writing="completed", automation="completed",
            editing="completed", code_security_review="completed",
            final_review="completed", ready_for_publishing="completed",
        )
        result = PhaseEngine.get_next_action(manifest)
        assert result["action"] == "done"


def _manifest(current="intake", **phase_statuses):
    """Build a minimal manifest dict for testing."""
    phases = {}
    for name in [
        "intake", "vetting", "spec_refinement", "approval",
        "writing", "automation", "editing", "code_security_review",
        "final_review", "ready_for_publishing",
    ]:
        phases[name] = {"status": phase_statuses.get(name, "pending")}
    return {
        "project": {"deployment_mode": "rhdp_published"},
        "lifecycle": {"current_phase": current, "phases": phases},
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src/backend && source ~/.virtualenvs/ph-dashboard/bin/activate && DATABASE_URL=sqlite:///test.db python -m pytest tests/test_phase_engine.py -v`
Expected: ImportError — module doesn't exist.

- [ ] **Step 3: Implement PhaseEngine**

```python
# app/services/phase_engine.py
"""Phase profiles, prerequisite rules, and next-action logic.

Pure logic — no DB, no I/O, no external calls.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PhaseDefinition:
    name: str
    gate_type: str  # "hard" or "soft"
    prerequisites: tuple[str, ...]  # phase names that must be completed


ONBOARDED_PHASES = (
    PhaseDefinition("intake", "hard", ()),
    PhaseDefinition("vetting", "hard", ("intake",)),
    PhaseDefinition("spec_refinement", "hard", ("vetting",)),
    PhaseDefinition("approval", "hard", ("spec_refinement",)),
    PhaseDefinition("writing", "hard", ("approval",)),
    PhaseDefinition("automation", "hard", ("approval",)),
    PhaseDefinition("editing", "hard", ("writing", "automation")),
    PhaseDefinition("code_security_review", "hard", ("editing",)),
    PhaseDefinition("final_review", "hard", ("code_security_review",)),
    PhaseDefinition("ready_for_publishing", "hard", ("final_review",)),
)

SELF_PUBLISHED_PHASES = (
    PhaseDefinition("intake", "hard", ()),
    PhaseDefinition("vetting", "hard", ("intake",)),
    PhaseDefinition("spec_refinement", "hard", ("vetting",)),
    PhaseDefinition("approval", "soft", ("spec_refinement",)),
    PhaseDefinition("writing", "soft", ("approval",)),
    PhaseDefinition("automation", "soft", ("approval",)),
    PhaseDefinition("editing", "hard", ("writing", "automation")),
    PhaseDefinition("code_security_review", "soft", ("editing",)),
    PhaseDefinition("final_review", "soft", ("code_security_review",)),
    PhaseDefinition("ready_for_publishing", "soft", ("final_review",)),
)

EXPRESS_PHASES = (
    PhaseDefinition("intake", "hard", ()),
    PhaseDefinition("vetting", "hard", ("intake",)),
    PhaseDefinition("base_finding", "hard", ("vetting",)),
)

_PROFILES = {
    "rhdp_published": ONBOARDED_PHASES,
    "self_published": SELF_PUBLISHED_PHASES,
    "express": EXPRESS_PHASES,
}


class PhaseEngine:
    @staticmethod
    def get_profile(deployment_mode: str) -> tuple[PhaseDefinition, ...]:
        if deployment_mode not in _PROFILES:
            raise ValueError(f"Unknown deployment mode: {deployment_mode}")
        return _PROFILES[deployment_mode]

    @staticmethod
    def check_prerequisites(manifest: dict, target_phase: str) -> dict:
        mode = manifest.get("project", {}).get("deployment_mode", "rhdp_published")
        profile = PhaseEngine.get_profile(mode)
        phases = manifest.get("lifecycle", {}).get("phases", {})

        target_def = None
        for p in profile:
            if p.name == target_phase:
                target_def = p
                break

        if target_def is None:
            return {"met": False, "reason": f"Phase '{target_phase}' not in {mode} profile"}

        missing = []
        for prereq in target_def.prerequisites:
            prereq_status = phases.get(prereq, {}).get("status", "pending")
            if prereq_status not in ("completed", "skipped"):
                missing.append(prereq)

        if missing:
            return {"met": False, "reason": f"Prerequisites not met: {', '.join(missing)} must be completed"}

        return {"met": True, "reason": "All prerequisites satisfied", "gate_type": target_def.gate_type}

    @staticmethod
    def get_next_action(manifest: dict) -> dict:
        mode = manifest.get("project", {}).get("deployment_mode", "rhdp_published")
        profile = PhaseEngine.get_profile(mode)
        phases = manifest.get("lifecycle", {}).get("phases", {})
        current = manifest.get("lifecycle", {}).get("current_phase", "intake")

        current_status = phases.get(current, {}).get("status", "pending")
        if current_status == "in_progress":
            return {"next_phase": current, "action": "continue", "detail": f"Continue working on {current}"}

        if current_status == "completed":
            phase_names = [p.name for p in profile]
            current_idx = phase_names.index(current) if current in phase_names else -1
            if current_idx + 1 < len(phase_names):
                next_name = phase_names[current_idx + 1]
                prereq_check = PhaseEngine.check_prerequisites(manifest, next_name)
                if prereq_check["met"]:
                    return {"next_phase": next_name, "action": "advance", "detail": f"Ready to advance to {next_name}"}
                else:
                    return {"next_phase": next_name, "action": "blocked", "detail": prereq_check["reason"]}

        all_completed = all(
            phases.get(p.name, {}).get("status") in ("completed", "skipped")
            for p in profile
        )
        if all_completed:
            return {"next_phase": None, "action": "done", "detail": "All phases complete"}

        if current_status == "pending":
            prereq_check = PhaseEngine.check_prerequisites(manifest, current)
            if prereq_check["met"]:
                return {"next_phase": current, "action": "start", "detail": f"Ready to start {current}"}
            else:
                return {"next_phase": current, "action": "blocked", "detail": prereq_check["reason"]}

        return {"next_phase": current, "action": "unknown", "detail": f"Phase {current} in unexpected state: {current_status}"}
```

- [ ] **Step 4: Run tests**

Run: `cd src/backend && source ~/.virtualenvs/ph-dashboard/bin/activate && DATABASE_URL=sqlite:///test.db python -m pytest tests/test_phase_engine.py -v`
Expected: All 12 tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/services/phase_engine.py tests/test_phase_engine.py
git commit -m "feat: Add PhaseEngine with phase profiles and prerequisite logic"
```

---

### Task 2: ph_get_status MCP Tool

**Files:**
- Modify: `src/backend/app/mcp/gate_tools.py`
- Create: `src/backend/tests/test_gate_tools_status.py`

**Interfaces:**
- Consumes: `GitRepoReader.fetch_manifest()`, `PhaseEngine.get_next_action()`, `PhaseEngine.check_prerequisites()`
- Produces: `ph_get_status(repo_url: str, branch: str) -> dict` — MCP tool

- [ ] **Step 1: Write failing tests**

```python
# tests/test_gate_tools_status.py
"""Tests for ph_get_status MCP tool."""
import base64
from unittest.mock import patch

import httpx
import pytest
import yaml

from app.mcp.gate_tools import ph_get_status


def _mock_transport(manifest_dict):
    manifest_yaml = yaml.dump(manifest_dict)
    encoded = base64.b64encode(manifest_yaml.encode()).decode()
    return httpx.MockTransport(
        lambda req: httpx.Response(200, json={"content": encoded, "encoding": "base64"})
    )


def _manifest(current="intake", mode="rhdp_published", **phase_statuses):
    phases = {}
    for name in [
        "intake", "vetting", "spec_refinement", "approval",
        "writing", "automation", "editing", "code_security_review",
        "final_review", "ready_for_publishing",
    ]:
        phases[name] = {"status": phase_statuses.get(name, "pending")}
    return {
        "project": {
            "name": "Test Lab",
            "id": "test-lab",
            "owner_github": "testuser",
            "deployment_mode": mode,
        },
        "lifecycle": {"current_phase": current, "phases": phases},
    }


class TestPhGetStatus:
    def test_returns_status_for_in_progress_project(self, test_db):
        manifest = _manifest(current="writing", intake="completed", vetting="completed",
                             spec_refinement="completed", approval="completed", writing="in_progress")
        transport = _mock_transport(manifest)
        with patch("app.mcp.gate_tools._get_reader") as mock:
            from app.services.git_repo_reader import GitRepoReader
            mock.return_value = GitRepoReader(token="t", transport=transport)
            result = ph_get_status(repo_url="git@github.com:rhpds/test.git", branch="main")

        assert result["current_phase"] == "writing"
        assert result["next_action"]["action"] == "continue"
        assert result["name"] == "Test Lab"

    def test_returns_advance_when_phase_complete(self, test_db):
        manifest = _manifest(current="intake", intake="completed")
        transport = _mock_transport(manifest)
        with patch("app.mcp.gate_tools._get_reader") as mock:
            from app.services.git_repo_reader import GitRepoReader
            mock.return_value = GitRepoReader(token="t", transport=transport)
            result = ph_get_status(repo_url="git@github.com:rhpds/test.git", branch="main")

        assert result["next_action"]["action"] == "advance"
        assert result["next_action"]["next_phase"] == "vetting"

    def test_returns_error_for_missing_repo(self, test_db):
        transport = httpx.MockTransport(
            lambda req: httpx.Response(404, json={"message": "Not Found"})
        )
        with patch("app.mcp.gate_tools._get_reader") as mock:
            from app.services.git_repo_reader import GitRepoReader
            mock.return_value = GitRepoReader(token="t", transport=transport)
            result = ph_get_status(repo_url="git@github.com:rhpds/missing.git", branch="main")

        assert "error" in result

    def test_includes_phase_statuses(self, test_db):
        manifest = _manifest(current="vetting", intake="completed", vetting="in_progress")
        transport = _mock_transport(manifest)
        with patch("app.mcp.gate_tools._get_reader") as mock:
            from app.services.git_repo_reader import GitRepoReader
            mock.return_value = GitRepoReader(token="t", transport=transport)
            result = ph_get_status(repo_url="git@github.com:rhpds/test.git", branch="main")

        assert result["phase_statuses"]["intake"] == "completed"
        assert result["phase_statuses"]["vetting"] == "in_progress"
```

- [ ] **Step 2: Implement ph_get_status**

Add to `app/mcp/gate_tools.py`:

```python
from app.services.phase_engine import PhaseEngine

@mcp.tool()
def ph_get_status(repo_url: str, branch: str = "main") -> dict:
    """Get the current status of a project registered in Central.

    Fetches the manifest from git, computes phase status using
    PhaseEngine, and returns the next recommended action.

    Args:
        repo_url: Git repository URL (SSH or HTTPS format)
        branch: Git branch name (default: main)

    Returns:
        Project status including current phase, all phase statuses,
        and the recommended next action.
    """
    reader = _get_reader()
    try:
        owner, repo = parse_repo_url(repo_url)
        manifest = reader.fetch_manifest(owner, repo, branch)
    except (ValueError, GitRepoReaderError) as e:
        return {"error": str(e)}

    project_data = manifest.get("project", {})
    lifecycle = manifest.get("lifecycle", {})
    phases = lifecycle.get("phases", {})

    phase_statuses = {name: phase.get("status", "pending") for name, phase in phases.items()}
    next_action = PhaseEngine.get_next_action(manifest)

    return {
        "name": project_data.get("name", "Unknown"),
        "repo_url": repo_url,
        "branch": branch,
        "deployment_mode": project_data.get("deployment_mode"),
        "current_phase": lifecycle.get("current_phase", "intake"),
        "phase_statuses": phase_statuses,
        "next_action": next_action,
    }
```

- [ ] **Step 3: Run tests**

Run: `cd src/backend && source ~/.virtualenvs/ph-dashboard/bin/activate && DATABASE_URL=sqlite:///test.db python -m pytest tests/test_gate_tools_status.py tests/test_phase_engine.py -v`
Expected: All tests pass.

- [ ] **Step 4: Run full new test suite**

Run: `cd src/backend && source ~/.virtualenvs/ph-dashboard/bin/activate && DATABASE_URL=sqlite:///test.db python -m pytest tests/test_phase_engine.py tests/test_gate_tools_register.py tests/test_gate_tools_status.py tests/test_registration_e2e.py tests/test_git_repo_reader.py -v`
Expected: All pass, no regressions.

- [ ] **Step 5: Commit**

```bash
git add app/mcp/gate_tools.py tests/test_gate_tools_status.py
git commit -m "feat: Add ph_get_status MCP tool with PhaseEngine"
```
