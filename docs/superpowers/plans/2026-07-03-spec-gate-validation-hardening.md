# Spec & Gate Validation Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden deterministic validation checks across the intake-to-review pipeline — phase integrity, controlled vocabulary, module spec validation, spec contract snapshots, drift detection, and content compliance.

**Architecture:** Extend PhaseEngine (phase profile validation) and SpecValidator (vocabulary + module specs). Create new SpecContractService for snapshot lifecycle. New DB models for SpecSnapshot and VocabularyList. GateService and RefreshService call into these services at appropriate points.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL 16 (JSONB), pytest, SQLite for tests

## Global Constraints

- All validation is deterministic Python. No LLM in the validation chain (LLM quality review is advisory only, handled separately by existing SpecReviewer).
- Error messages must include: file name, expected heading, what was found instead, line number where applicable.
- Tests use SQLite via `DATABASE_URL=sqlite:///./test.db` and the existing conftest.py fixtures.
- All new models must be registered in `app/models/__init__.py` AND imported in `alembic/env.py`.
- Follow existing patterns: `@dataclass` for pure logic results, SQLAlchemy `Mapped[]` for DB models, `JSONBType` for JSONB columns.
- Run tests from `src/backend/`: `DATABASE_URL=sqlite:///./test.db python -m pytest tests/ -x -v --timeout=30`

---

### Task 1: Phase Integrity Check in PhaseEngine

**Files:**
- Modify: `src/backend/app/services/phase_engine.py`
- Test: `src/backend/tests/test_phase_engine.py`

**Interfaces:**
- Consumes: Nothing new — uses existing `_PROFILES` dict and manifest dict
- Produces: `PhaseEngine.validate_phase_profile(manifest) -> PhaseProfileResult` used by GateService (Task 6) and RefreshService (Task 7)

- [ ] **Step 1: Write failing tests for validate_phase_profile**

Add to `tests/test_phase_engine.py`:

```python
from app.services.phase_engine import PhaseEngine


class TestPhaseProfileValidation:
    def test_valid_onboarded_manifest_passes(self):
        manifest = _manifest(current="intake", intake="pending")
        result = PhaseEngine.validate_phase_profile(manifest)
        assert result["valid"] is True
        assert result["extra_phases"] == []
        assert result["missing_phases"] == []

    def test_extra_phase_detected(self):
        manifest = _manifest(current="intake", intake="pending")
        manifest["lifecycle"]["phases"]["custom_review"] = {"status": "pending"}
        result = PhaseEngine.validate_phase_profile(manifest)
        assert result["valid"] is False
        assert "custom_review" in result["extra_phases"]
        assert "custom_review" in result["message"]

    def test_missing_phase_detected(self):
        manifest = _manifest(current="intake", intake="pending")
        del manifest["lifecycle"]["phases"]["security_review"]
        result = PhaseEngine.validate_phase_profile(manifest)
        assert result["valid"] is False
        assert "security_review" in result["missing_phases"]

    def test_skipped_phase_still_expected(self):
        manifest = _manifest(current="intake", intake="pending")
        manifest["lifecycle"]["phases"]["vetting"]["status"] = "skipped"
        result = PhaseEngine.validate_phase_profile(manifest)
        assert result["valid"] is True

    def test_express_profile_validates_three_phases(self):
        manifest = {
            "project": {"deployment_mode": "express"},
            "lifecycle": {
                "current_phase": "intake",
                "phases": {
                    "intake": {"status": "pending"},
                    "vetting": {"status": "pending"},
                    "base_finding": {"status": "pending"},
                },
            },
        }
        result = PhaseEngine.validate_phase_profile(manifest)
        assert result["valid"] is True

    def test_express_with_onboarded_phases_fails(self):
        manifest = {
            "project": {"deployment_mode": "express"},
            "lifecycle": {
                "current_phase": "intake",
                "phases": {
                    "intake": {"status": "pending"},
                    "vetting": {"status": "pending"},
                    "base_finding": {"status": "pending"},
                    "writing": {"status": "pending"},
                },
            },
        }
        result = PhaseEngine.validate_phase_profile(manifest)
        assert result["valid"] is False
        assert "writing" in result["extra_phases"]

    def test_message_includes_deployment_mode(self):
        manifest = _manifest(current="intake", intake="pending")
        manifest["lifecycle"]["phases"]["custom_review"] = {"status": "pending"}
        result = PhaseEngine.validate_phase_profile(manifest)
        assert "rhdp_published" in result["message"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd src/backend
DATABASE_URL=sqlite:///./test.db python -m pytest tests/test_phase_engine.py::TestPhaseProfileValidation -v
```

Expected: FAIL — `AttributeError: type object 'PhaseEngine' has no attribute 'validate_phase_profile'`

- [ ] **Step 3: Implement validate_phase_profile**

Add to `PhaseEngine` class in `src/backend/app/services/phase_engine.py`:

```python
@staticmethod
def validate_phase_profile(manifest: dict) -> dict:
    """Validate that manifest phases match the expected profile for the deployment mode.

    Returns dict with: valid (bool), extra_phases (list), missing_phases (list), message (str).
    """
    mode = manifest.get("project", {}).get("deployment_mode", "rhdp_published")
    profile = PhaseEngine.get_profile(mode)
    expected_names = {p.name for p in profile}
    manifest_phases = set(manifest.get("lifecycle", {}).get("phases", {}).keys())

    extra = sorted(manifest_phases - expected_names)
    missing = sorted(expected_names - manifest_phases)

    if extra or missing:
        parts = [f"Manifest lifecycle does not match the '{mode}' profile:"]
        if extra:
            parts.append(f"unexpected phase(s) {', '.join(repr(p) for p in extra)}")
        if extra and missing:
            parts.append(";")
        if missing:
            parts.append(f"missing phase(s) {', '.join(repr(p) for p in missing)}")
        return {
            "valid": False,
            "extra_phases": extra,
            "missing_phases": missing,
            "message": " ".join(parts),
        }

    return {"valid": True, "extra_phases": [], "missing_phases": [], "message": "Phase profile matches"}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd src/backend
DATABASE_URL=sqlite:///./test.db python -m pytest tests/test_phase_engine.py -v
```

Expected: ALL PASS (both old and new tests)

- [ ] **Step 5: Commit**

```bash
git add src/backend/app/services/phase_engine.py src/backend/tests/test_phase_engine.py
git commit -m "[RHDPCD-170] Add phase integrity validation to PhaseEngine"
```

---

### Task 2: VocabularyList DB Model and Seed Data

**Files:**
- Create: `src/backend/app/models/vocabulary.py`
- Create: `src/backend/app/services/vocabulary.py`
- Modify: `src/backend/app/models/__init__.py`
- Create: `src/backend/alembic/versions/f4g5h6i7j8k9_add_vocabulary_spec_snapshot.py`
- Test: `src/backend/tests/test_vocabulary.py`

**Interfaces:**
- Consumes: Database session
- Produces: `VocabularyService.get_list(db, list_type) -> list[VocabularyEntry]`, `VocabularyService.validate_value(db, list_type, value) -> ValidationResult` — used by SpecValidator (Task 3)

- [ ] **Step 1: Write failing tests for VocabularyList model and VocabularyService**

Create `tests/test_vocabulary.py`:

```python
"""Tests for VocabularyList model and VocabularyService."""
import pytest

from app.models.vocabulary import VocabularyEntry
from app.services.vocabulary import VocabularyService


class TestVocabularyModel:
    def test_create_content_type_entry(self, db_session):
        entry = VocabularyEntry(
            list_type="content_type",
            canonical_name="lab",
        )
        db_session.add(entry)
        db_session.commit()
        db_session.refresh(entry)
        assert entry.id is not None
        assert entry.list_type == "content_type"
        assert entry.canonical_name == "lab"

    def test_create_product_with_abbreviations(self, db_session):
        entry = VocabularyEntry(
            list_type="product_name",
            canonical_name="Red Hat OpenShift",
            abbreviations=["OCP"],
        )
        db_session.add(entry)
        db_session.commit()
        db_session.refresh(entry)
        assert entry.abbreviations == ["OCP"]


class TestVocabularyService:
    def test_seed_creates_entries(self, db_session):
        VocabularyService.seed_defaults(db_session)
        content_types = VocabularyService.get_list(db_session, "content_type")
        assert len(content_types) >= 2
        names = [e.canonical_name for e in content_types]
        assert "lab" in names
        assert "demo" in names

    def test_seed_is_idempotent(self, db_session):
        VocabularyService.seed_defaults(db_session)
        VocabularyService.seed_defaults(db_session)
        content_types = VocabularyService.get_list(db_session, "content_type")
        assert len(content_types) == 2

    def test_validate_exact_match(self, db_session):
        VocabularyService.seed_defaults(db_session)
        result = VocabularyService.validate_value(db_session, "content_type", "lab")
        assert result["valid"] is True

    def test_validate_case_insensitive(self, db_session):
        VocabularyService.seed_defaults(db_session)
        result = VocabularyService.validate_value(db_session, "content_type", "Lab")
        assert result["valid"] is True

    def test_validate_invalid_content_type(self, db_session):
        VocabularyService.seed_defaults(db_session)
        result = VocabularyService.validate_value(db_session, "content_type", "hands-on micro lab")
        assert result["valid"] is False
        assert "hands-on micro lab" in result["message"]

    def test_validate_difficulty_levels(self, db_session):
        VocabularyService.seed_defaults(db_session)
        for level in ["beginner", "intermediate", "advanced"]:
            result = VocabularyService.validate_value(db_session, "difficulty_level", level)
            assert result["valid"] is True, f"{level} should be valid"

    def test_validate_product_canonical(self, db_session):
        VocabularyService.seed_defaults(db_session)
        result = VocabularyService.validate_value(db_session, "product_name", "Red Hat OpenShift")
        assert result["valid"] is True

    def test_validate_product_without_redhat_prefix(self, db_session):
        VocabularyService.seed_defaults(db_session)
        result = VocabularyService.validate_value(db_session, "product_name", "OpenShift")
        assert result["valid"] is True

    def test_validate_product_abbreviation(self, db_session):
        VocabularyService.seed_defaults(db_session)
        result = VocabularyService.validate_value(db_session, "product_name", "OCP")
        assert result["valid"] is True

    def test_validate_product_case_insensitive(self, db_session):
        VocabularyService.seed_defaults(db_session)
        result = VocabularyService.validate_value(db_session, "product_name", "openshift")
        assert result["valid"] is True

    def test_validate_unknown_product_fails(self, db_session):
        VocabularyService.seed_defaults(db_session)
        result = VocabularyService.validate_value(db_session, "product_name", "Cloud Nexus Platform")
        assert result["valid"] is False
        assert "Cloud Nexus Platform" in result["message"]

    def test_normalize_strips_redhat_prefix(self):
        assert VocabularyService._normalize("Red Hat OpenShift") == "openshift"

    def test_normalize_strips_version(self):
        assert VocabularyService._normalize("OpenShift 4.20") == "openshift"

    def test_normalize_collapses_whitespace(self):
        assert VocabularyService._normalize("OpenShift  Virtualization") == "openshift virtualization"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd src/backend
DATABASE_URL=sqlite:///./test.db python -m pytest tests/test_vocabulary.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.models.vocabulary'`

- [ ] **Step 3: Create VocabularyEntry model**

Create `src/backend/app/models/vocabulary.py`:

```python
import uuid
from typing import Optional
from sqlalchemy import String, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.core.types import JSONBType


class VocabularyEntry(Base):
    __tablename__ = "vocabulary_entries"
    __table_args__ = (
        Index("ix_vocabulary_list_type", "list_type"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    list_type: Mapped[str] = mapped_column(String(50), nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    abbreviations: Mapped[Optional[list]] = mapped_column(JSONBType, nullable=True)
```

- [ ] **Step 4: Create VocabularyService with normalization and seed data**

Create `src/backend/app/services/vocabulary.py`:

```python
"""Controlled vocabulary validation — content types, difficulty levels, product names.

DB-backed lists with two-layer product name matching:
  Layer 1: Normalize (strip 'Red Hat' prefix, lowercase, strip versions)
  Layer 2: Abbreviation map (OCP, AAP, RHEL, etc.)
"""
from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.models.vocabulary import VocabularyEntry

_VERSION_SUFFIX = re.compile(r"\s+\d+[\d.]*\s*$")
_REDHAT_PREFIX = re.compile(r"^red\s+hat\s+", re.IGNORECASE)
_WHITESPACE = re.compile(r"\s+")

SEED_DATA = {
    "content_type": [
        {"canonical_name": "lab"},
        {"canonical_name": "demo"},
    ],
    "difficulty_level": [
        {"canonical_name": "beginner"},
        {"canonical_name": "intermediate"},
        {"canonical_name": "advanced"},
    ],
    "product_name": [
        {"canonical_name": "Red Hat OpenShift", "abbreviations": ["OCP"]},
        {"canonical_name": "Red Hat OpenShift AI", "abbreviations": ["RHOAI"]},
        {"canonical_name": "Red Hat OpenShift Virtualization", "abbreviations": ["CNV"]},
        {"canonical_name": "Red Hat OpenShift Data Foundation", "abbreviations": ["ODF"]},
        {"canonical_name": "Red Hat OpenShift Service Mesh", "abbreviations": ["OSSM"]},
        {"canonical_name": "Red Hat OpenShift Serverless", "abbreviations": []},
        {"canonical_name": "Red Hat OpenShift Pipelines", "abbreviations": []},
        {"canonical_name": "Red Hat OpenShift GitOps", "abbreviations": []},
        {"canonical_name": "Red Hat OpenShift Lightspeed", "abbreviations": []},
        {"canonical_name": "Red Hat Advanced Cluster Management", "abbreviations": ["ACM", "RHACM"]},
        {"canonical_name": "Red Hat Advanced Cluster Security", "abbreviations": ["ACS", "RHACS"]},
        {"canonical_name": "Red Hat Ansible Automation Platform", "abbreviations": ["AAP"]},
        {"canonical_name": "Red Hat Enterprise Linux", "abbreviations": ["RHEL"]},
        {"canonical_name": "Red Hat Developer Hub", "abbreviations": ["RHDH"]},
        {"canonical_name": "Red Hat Quay", "abbreviations": []},
        {"canonical_name": "Red Hat build of Keycloak", "abbreviations": ["RHSSO"]},
        {"canonical_name": "Red Hat Trusted Profile Analyzer", "abbreviations": ["TPA"]},
        {"canonical_name": "Red Hat Trusted Artifact Signer", "abbreviations": ["TAS", "RHTAS"]},
        {"canonical_name": "Red Hat Connectivity Link", "abbreviations": []},
        {"canonical_name": "Red Hat OpenShift Container Platform", "abbreviations": []},
        {"canonical_name": "Red Hat Satellite", "abbreviations": []},
        {"canonical_name": "Red Hat Insights", "abbreviations": []},
        {"canonical_name": "Red Hat 3scale API Management", "abbreviations": ["3scale"]},
        {"canonical_name": "Red Hat Integration", "abbreviations": []},
        {"canonical_name": "Red Hat Fuse", "abbreviations": []},
        {"canonical_name": "Red Hat AMQ", "abbreviations": ["AMQ"]},
        {"canonical_name": "Red Hat Data Grid", "abbreviations": []},
        {"canonical_name": "Red Hat build of Apache Camel", "abbreviations": ["Camel"]},
        {"canonical_name": "Red Hat JBoss Enterprise Application Platform", "abbreviations": ["JBoss EAP", "EAP"]},
    ],
}


class VocabularyService:
    @staticmethod
    def _normalize(value: str) -> str:
        """Normalize a product name: strip 'Red Hat' prefix, lowercase, strip trailing versions."""
        result = _REDHAT_PREFIX.sub("", value)
        result = _VERSION_SUFFIX.sub("", result)
        result = _WHITESPACE.sub(" ", result).strip().lower()
        return result

    @staticmethod
    def seed_defaults(db: Session) -> None:
        """Seed vocabulary entries from SEED_DATA. Idempotent — skips existing entries."""
        for list_type, entries in SEED_DATA.items():
            for entry_data in entries:
                existing = db.query(VocabularyEntry).filter(
                    VocabularyEntry.list_type == list_type,
                    VocabularyEntry.canonical_name == entry_data["canonical_name"],
                ).first()
                if not existing:
                    db.add(VocabularyEntry(
                        list_type=list_type,
                        canonical_name=entry_data["canonical_name"],
                        abbreviations=entry_data.get("abbreviations"),
                    ))
        db.commit()

    @staticmethod
    def get_list(db: Session, list_type: str) -> list[VocabularyEntry]:
        """Get all entries for a vocabulary list type."""
        return db.query(VocabularyEntry).filter(
            VocabularyEntry.list_type == list_type,
        ).order_by(VocabularyEntry.canonical_name).all()

    @staticmethod
    def validate_value(db: Session, list_type: str, value: str) -> dict:
        """Validate a value against a vocabulary list.

        For content_type and difficulty_level: exact case-insensitive match.
        For product_name: two-layer normalization + abbreviation map.
        """
        entries = VocabularyService.get_list(db, list_type)
        value_lower = value.strip().lower()

        if list_type != "product_name":
            for entry in entries:
                if entry.canonical_name.lower() == value_lower:
                    return {"valid": True, "matched": entry.canonical_name}
            valid_values = [e.canonical_name for e in entries]
            return {
                "valid": False,
                "message": (
                    f"'{value}' is not a valid {list_type.replace('_', ' ')}. "
                    f"Must be one of: {', '.join(valid_values)}."
                ),
            }

        normalized_input = VocabularyService._normalize(value)
        for entry in entries:
            if entry.canonical_name.lower() == value_lower:
                return {"valid": True, "matched": entry.canonical_name}
            normalized_canonical = VocabularyService._normalize(entry.canonical_name)
            if normalized_canonical == normalized_input:
                return {"valid": True, "matched": entry.canonical_name}
            if entry.abbreviations:
                for abbr in entry.abbreviations:
                    if abbr.lower() == value_lower:
                        return {"valid": True, "matched": entry.canonical_name}

        return {
            "valid": False,
            "message": (
                f"Product '{value}' is not recognized. "
                f"If this is a valid Red Hat product, add it via the Publishing House dashboard."
            ),
        }
```

- [ ] **Step 5: Register model in __init__.py**

Add to `src/backend/app/models/__init__.py`:

```python
from app.models.vocabulary import VocabularyEntry
```

And add `"VocabularyEntry"` to the `__all__` list.

- [ ] **Step 6: Run tests to verify they pass**

```bash
cd src/backend
DATABASE_URL=sqlite:///./test.db python -m pytest tests/test_vocabulary.py -v
```

Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add src/backend/app/models/vocabulary.py src/backend/app/services/vocabulary.py src/backend/app/models/__init__.py src/backend/tests/test_vocabulary.py
git commit -m "[RHDPCD-170] Add VocabularyEntry model and VocabularyService with seed data"
```

---

### Task 3: Module Spec Validation and Vocabulary Integration in SpecValidator

**Files:**
- Modify: `src/backend/app/services/spec_validator.py`
- Test: `src/backend/tests/test_spec_validator.py`

**Interfaces:**
- Consumes: `VocabularyService.validate_value(db, list_type, value)` from Task 2
- Produces: `SpecValidator.validate_module_spec(content, filename) -> SpecValidationResult`, `SpecValidator.validate_vocabulary(spec_content, db) -> SpecValidationResult` — used by GateService (Task 6)

- [ ] **Step 1: Write failing tests for module spec validation**

Add to `tests/test_spec_validator.py`:

```python
GOOD_MODULE = """\
# Module 1: Deploying VMs

## Brief Overview
This module covers deploying virtual machines on OpenShift Virtualization.

## Audience and Time
- **Target personas:** Platform engineers
- **Prerequisites:** Basic OpenShift knowledge
- **Estimated duration:** 25 min

## What You Will See, Learn, and Do

**See:**
- A VM running on OpenShift

**Learn:**
- How VM scheduling works

**Do:**
- Deploy a VM from a template

## Lab Structure
| Section | Title | Duration |
|---------|-------|----------|
| 1 | Create a VM | 10 min |
| 2 | Access the console | 15 min |

## Key Takeaways
- VMs run as pods on OpenShift
- Templates simplify VM creation
"""

MODULE_MISSING_SECTION = """\
# Module 2: Live Migration

## Brief Overview
This module covers live migration of VMs.

## Audience and Time
- **Estimated duration:** 20 min

## What You Will See, Learn, and Do

**See:**
- A VM migrating between nodes

**Learn:**
- How live migration works

**Do:**
- Trigger a live migration

## Lab Structure
| Section | Title | Duration |
|---------|-------|----------|
| 1 | Trigger migration | 20 min |
"""

MODULE_NO_TABLE_ROWS = """\
# Module 3: Troubleshooting

## Brief Overview
Troubleshooting module.

## Audience and Time
- **Estimated duration:** 20 min

## What You Will See, Learn, and Do
See, Learn, Do items here.

## Lab Structure
| Section | Title | Duration |
|---------|-------|----------|

## Key Takeaways
- Takeaway here
"""


class TestModuleSpecValidation:
    def test_good_module_passes(self):
        result = SpecValidator.validate_module_spec(GOOD_MODULE, "module-01-deploying-vms.md")
        assert result.passed is True

    def test_missing_key_takeaways_fails(self):
        result = SpecValidator.validate_module_spec(MODULE_MISSING_SECTION, "module-02-live-migration.md")
        assert result.passed is False
        assert any("Key Takeaways" in i["message"] for i in result.issues)

    def test_error_includes_filename(self):
        result = SpecValidator.validate_module_spec(MODULE_MISSING_SECTION, "module-02-live-migration.md")
        assert any("module-02-live-migration.md" in i["message"] for i in result.issues)

    def test_error_lists_found_sections(self):
        result = SpecValidator.validate_module_spec(MODULE_MISSING_SECTION, "module-02-live-migration.md")
        failing = [i for i in result.issues if "Key Takeaways" in i["message"]]
        assert len(failing) == 1
        assert "Brief Overview" in failing[0]["message"]

    def test_no_table_rows_fails(self):
        result = SpecValidator.validate_module_spec(MODULE_NO_TABLE_ROWS, "module-03-troubleshooting.md")
        assert any("Lab Structure" in i["message"] and "no" in i["message"].lower() for i in result.issues)

    def test_placeholder_in_module_fails(self):
        content = GOOD_MODULE.replace("Deploying VMs", "[Module title]")
        result = SpecValidator.validate_module_spec(content, "module-01-test.md")
        assert any("placeholder" in i["message"].lower() for i in result.issues)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd src/backend
DATABASE_URL=sqlite:///./test.db python -m pytest tests/test_spec_validator.py::TestModuleSpecValidation -v
```

Expected: FAIL — `AttributeError: type object 'SpecValidator' has no attribute 'validate_module_spec'`

- [ ] **Step 3: Implement validate_module_spec**

Add to `SpecValidator` class in `src/backend/app/services/spec_validator.py`:

```python
MODULE_REQUIRED_SECTIONS = {
    "brief_overview": "## Brief Overview",
    "audience_and_time": "## Audience and Time",
    "see_learn_do": "## What You Will See, Learn, and Do",
    "lab_structure": "## Lab Structure",
    "key_takeaways": "## Key Takeaways",
}

# Alternate heading for see_learn_do
_SEE_LEARN_DO_ALT = "## see/learn/do"

@staticmethod
def validate_module_spec(content: str, filename: str) -> SpecValidationResult:
    """Validate a module spec file against required sections."""
    issues = []
    checks = {}
    content_lower = content.lower()
    found_sections = []

    for check_name, heading in SpecValidator.MODULE_REQUIRED_SECTIONS.items():
        if check_name == "see_learn_do":
            found = heading.lower() in content_lower or _SEE_LEARN_DO_ALT in content_lower
        else:
            found = heading.lower() in content_lower
        checks[check_name] = found
        if found:
            found_sections.append(heading.split("## ", 1)[1])
        if not found:
            issues.append({
                "check": check_name,
                "severity": "high",
                "message": (
                    f"{filename}: Missing required section '{heading.split('## ', 1)[1]}'. "
                    f"Found sections: {', '.join(found_sections) or 'none'}."
                ),
            })

    if checks.get("lab_structure"):
        table_rows = re.findall(r"\|\s*\d+\s*\|", content)
        checks["lab_structure_rows"] = len(table_rows) >= 1
        if not table_rows:
            issues.append({
                "check": "lab_structure_rows",
                "severity": "high",
                "message": f"{filename}: Lab Structure section has no data rows in table.",
            })

    if checks.get("audience_and_time"):
        duration_match = re.search(r"duration.*?(\d+\s*(?:min|hour|hr))", content, re.IGNORECASE)
        checks["duration_specified"] = duration_match is not None
        if not duration_match:
            issues.append({
                "check": "duration_specified",
                "severity": "medium",
                "message": f"{filename}: No duration found in Audience and Time section.",
            })

    placeholders = SpecValidator.PLACEHOLDER_PATTERN.findall(content)
    if placeholders:
        checks["no_placeholders"] = False
        issues.append({
            "check": "no_placeholders",
            "severity": "high",
            "message": f"{filename}: Unfilled placeholders found: {', '.join(placeholders[:5])}",
        })
    else:
        checks["no_placeholders"] = True

    passed = not any(i["severity"] == "high" for i in issues)
    return SpecValidationResult(passed=passed, issues=issues, checks=checks)
```

Note: `_SEE_LEARN_DO_ALT` should be defined as a module-level constant next to `MODULE_REQUIRED_SECTIONS`.

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd src/backend
DATABASE_URL=sqlite:///./test.db python -m pytest tests/test_spec_validator.py -v
```

Expected: ALL PASS

- [ ] **Step 5: Write failing tests for vocabulary validation**

Add to `tests/test_spec_validator.py`:

```python
class TestVocabularyValidation:
    def test_valid_content_type_passes(self, db_session):
        from app.services.vocabulary import VocabularyService
        VocabularyService.seed_defaults(db_session)
        result = SpecValidator.validate_vocabulary(GOOD_SPEC.replace("Hands-on lab", "lab"), db_session)
        assert result.passed is True

    def test_invalid_content_type_fails(self, db_session):
        from app.services.vocabulary import VocabularyService
        VocabularyService.seed_defaults(db_session)
        spec = GOOD_SPEC.replace("Hands-on lab", "hands-on micro lab")
        result = SpecValidator.validate_vocabulary(spec, db_session)
        assert result.passed is False
        assert any("content type" in i["message"].lower() for i in result.issues)

    def test_valid_difficulty_passes(self, db_session):
        from app.services.vocabulary import VocabularyService
        VocabularyService.seed_defaults(db_session)
        result = SpecValidator.validate_vocabulary(GOOD_SPEC, db_session)
        # GOOD_SPEC has "Intermediate" — should pass
        assert all("difficulty" not in i.get("check", "") for i in result.issues)

    def test_valid_products_pass(self, db_session):
        from app.services.vocabulary import VocabularyService
        VocabularyService.seed_defaults(db_session)
        result = SpecValidator.validate_vocabulary(GOOD_SPEC, db_session)
        assert all("product" not in i.get("check", "") for i in result.issues)

    def test_unknown_product_fails(self, db_session):
        from app.services.vocabulary import VocabularyService
        VocabularyService.seed_defaults(db_session)
        spec = GOOD_SPEC.replace("Red Hat OpenShift AI", "Cloud Nexus Platform")
        result = SpecValidator.validate_vocabulary(spec, db_session)
        assert any("Cloud Nexus Platform" in i["message"] for i in result.issues)
```

- [ ] **Step 6: Implement validate_vocabulary**

Add to `SpecValidator` class:

```python
@staticmethod
def validate_vocabulary(spec_content: str, db: "Session") -> SpecValidationResult:
    """Validate spec content type, difficulty, and products against vocabulary lists."""
    from app.services.vocabulary import VocabularyService
    issues = []
    checks = {}

    # Extract and validate content type
    ct_match = re.search(r"##\s*Content\s+Type\s*\n+(.+)", spec_content, re.IGNORECASE)
    if ct_match:
        raw_type = ct_match.group(1).strip().rstrip(".")
        result = VocabularyService.validate_value(db, "content_type", raw_type)
        checks["content_type_valid"] = result["valid"]
        if not result["valid"]:
            issues.append({"check": "content_type_valid", "severity": "high", "message": result["message"]})

    # Extract and validate difficulty
    diff_match = re.search(r"##\s*Difficulty\s+Level\s*\n+(.+)", spec_content, re.IGNORECASE)
    if diff_match:
        raw_diff = diff_match.group(1).strip().rstrip(".")
        result = VocabularyService.validate_value(db, "difficulty_level", raw_diff)
        checks["difficulty_valid"] = result["valid"]
        if not result["valid"]:
            issues.append({"check": "difficulty_valid", "severity": "high", "message": result["message"]})

    # Extract and validate products
    prod_match = re.search(
        r"##\s*Products?\s*(?:&|and)?\s*Technologies?\s*\n((?:[-*]\s+.+\n?)+)",
        spec_content, re.IGNORECASE,
    )
    if prod_match:
        products = re.findall(r"[-*]\s+(.+)", prod_match.group(1))
        all_valid = True
        for product in products:
            product = product.strip()
            result = VocabularyService.validate_value(db, "product_name", product)
            if not result["valid"]:
                all_valid = False
                issues.append({"check": "product_valid", "severity": "high", "message": result["message"]})
        checks["products_valid"] = all_valid

    passed = not any(i["severity"] == "high" for i in issues)
    return SpecValidationResult(passed=passed, issues=issues, checks=checks)
```

- [ ] **Step 7: Run all tests**

```bash
cd src/backend
DATABASE_URL=sqlite:///./test.db python -m pytest tests/test_spec_validator.py -v
```

Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add src/backend/app/services/spec_validator.py src/backend/tests/test_spec_validator.py
git commit -m "[RHDPCD-170] Add module spec validation and vocabulary checks to SpecValidator"
```

---

### Task 4: SpecSnapshot Model and SpecContractService

**Files:**
- Create: `src/backend/app/models/spec_snapshot.py`
- Modify: `src/backend/app/models/__init__.py`
- Create: `src/backend/app/services/spec_contract.py`
- Test: `src/backend/tests/test_spec_contract.py`

**Interfaces:**
- Consumes: Design.md content (str), module spec content (dict of filename→content), db session
- Produces: `SpecContractService.create_snapshot(db, project_id, design_md, module_specs, source_commit) -> SpecSnapshot`, `SpecContractService.extract_contract_fields(design_md, module_specs) -> dict`, `SpecContractService.check_spec_drift(db, project_id, design_md, module_specs) -> dict`, `SpecContractService.check_content_compliance(snapshot_data, nav_content, module_files) -> dict` — used by GateService (Task 6)

- [ ] **Step 1: Write failing tests for contract field extraction**

Create `tests/test_spec_contract.py`:

```python
"""Tests for SpecContractService — snapshot creation, drift detection, content compliance."""
import uuid
import pytest

from app.models.spec_snapshot import SpecSnapshot
from app.services.spec_contract import SpecContractService


DESIGN_MD = """\
# OCP Virtualization Workshop

## Problem Statement
Platform engineers need hands-on experience with OpenShift Virtualization.

## Target Audience
Intermediate platform engineers

## Learning Objectives
1. Deploy a VM on OpenShift Virtualization
2. Configure live migration between nodes
3. Troubleshoot VM boot failures

## Content Type
lab

## Products & Technologies
- Red Hat OpenShift
- Red Hat OpenShift Virtualization

## Module Map
| # | Module | Duration |
|---|--------|----------|
| 1 | Introduction to OCP Virt | 20 min |
| 2 | Deploying VMs | 25 min |
| 3 | Live Migration | 20 min |
| 4 | Troubleshooting VMs | 25 min |

| — | **Total hands-on** | **90 min** |

## Difficulty Level
intermediate

## Environment
OpenShift 4.20 cluster with CNV operator.

## Infrastructure Requirements
- Base: ocp4-cluster
"""

MODULE_01 = """\
# Module 1: Introduction to OCP Virt

## Brief Overview
Introduction to OpenShift Virtualization concepts.
"""

MODULE_02 = """\
# Module 2: Deploying VMs

## Brief Overview
Deploying virtual machines on OpenShift.
"""


class TestContractFieldExtraction:
    def test_extracts_content_type(self):
        fields = SpecContractService.extract_contract_fields(DESIGN_MD, {})
        assert fields["content_type"] == "lab"

    def test_extracts_difficulty(self):
        fields = SpecContractService.extract_contract_fields(DESIGN_MD, {})
        assert fields["difficulty"] == "intermediate"

    def test_extracts_products(self):
        fields = SpecContractService.extract_contract_fields(DESIGN_MD, {})
        assert "Red Hat OpenShift" in fields["products"]
        assert "Red Hat OpenShift Virtualization" in fields["products"]

    def test_extracts_learning_objectives(self):
        fields = SpecContractService.extract_contract_fields(DESIGN_MD, {})
        assert len(fields["learning_objectives"]) == 3
        assert any("Deploy" in obj for obj in fields["learning_objectives"])

    def test_extracts_module_count(self):
        fields = SpecContractService.extract_contract_fields(DESIGN_MD, {})
        assert fields["module_count"] == 4

    def test_extracts_module_titles(self):
        fields = SpecContractService.extract_contract_fields(DESIGN_MD, {})
        titles = [m["title"] for m in fields["modules"]]
        assert "Introduction to OCP Virt" in titles
        assert "Deploying VMs" in titles

    def test_extracts_module_durations(self):
        fields = SpecContractService.extract_contract_fields(DESIGN_MD, {})
        durations = [m["duration"] for m in fields["modules"]]
        assert "20 min" in durations
        assert "25 min" in durations

    def test_extraction_error_for_missing_content_type(self):
        bad_spec = DESIGN_MD.replace("## Content Type\nlab", "## Content Type\n")
        fields = SpecContractService.extract_contract_fields(bad_spec, {})
        assert fields.get("content_type") is None
        assert len(fields["extraction_errors"]) > 0


class TestSnapshotCreation:
    def test_create_snapshot(self, db_session):
        project_id = uuid.uuid4()
        snapshot = SpecContractService.create_snapshot(
            db_session, project_id, DESIGN_MD,
            {"module-01.md": MODULE_01, "module-02.md": MODULE_02},
            source_commit="abc123def456",
        )
        assert snapshot.id is not None
        assert snapshot.is_current is True
        assert snapshot.snapshot_data["module_count"] == 4
        assert snapshot.source_commit == "abc123def456"

    def test_new_snapshot_supersedes_old(self, db_session):
        project_id = uuid.uuid4()
        first = SpecContractService.create_snapshot(
            db_session, project_id, DESIGN_MD, {}, source_commit="aaa",
        )
        second = SpecContractService.create_snapshot(
            db_session, project_id, DESIGN_MD, {}, source_commit="bbb",
        )
        db_session.refresh(first)
        assert first.is_current is False
        assert first.superseded_by == second.id
        assert second.is_current is True

    def test_get_current_snapshot(self, db_session):
        project_id = uuid.uuid4()
        SpecContractService.create_snapshot(db_session, project_id, DESIGN_MD, {}, source_commit="aaa")
        SpecContractService.create_snapshot(db_session, project_id, DESIGN_MD, {}, source_commit="bbb")
        current = SpecContractService.get_current_snapshot(db_session, project_id)
        assert current is not None
        assert current.source_commit == "bbb"


class TestSpecDrift:
    def test_no_drift_returns_clean(self, db_session):
        project_id = uuid.uuid4()
        SpecContractService.create_snapshot(db_session, project_id, DESIGN_MD, {}, source_commit="aaa")
        result = SpecContractService.check_spec_drift(db_session, project_id, DESIGN_MD, {})
        assert result["drifted"] is False

    def test_module_count_change_detected(self, db_session):
        project_id = uuid.uuid4()
        SpecContractService.create_snapshot(db_session, project_id, DESIGN_MD, {}, source_commit="aaa")
        modified = DESIGN_MD + "| 5 | Bonus Module | 15 min |\n"
        result = SpecContractService.check_spec_drift(db_session, project_id, modified, {})
        assert result["drifted"] is True
        assert any("module_count" in c.get("field", "") for c in result["changes"])

    def test_product_change_detected(self, db_session):
        project_id = uuid.uuid4()
        SpecContractService.create_snapshot(db_session, project_id, DESIGN_MD, {}, source_commit="aaa")
        modified = DESIGN_MD.replace("Red Hat OpenShift Virtualization", "Red Hat OpenShift AI")
        result = SpecContractService.check_spec_drift(db_session, project_id, modified, {})
        assert result["drifted"] is True
        assert any("products" in c.get("field", "") for c in result["changes"])

    def test_no_snapshot_returns_no_contract(self, db_session):
        result = SpecContractService.check_spec_drift(db_session, uuid.uuid4(), DESIGN_MD, {})
        assert result.get("no_snapshot") is True


class TestContentCompliance:
    def test_matching_modules_pass(self):
        snapshot_data = {
            "module_count": 2,
            "modules": [
                {"title": "Introduction to OCP Virt", "duration": "20 min"},
                {"title": "Deploying VMs", "duration": "25 min"},
            ],
        }
        module_files = ["03-module-01-intro.adoc", "04-module-02-deploying.adoc"]
        result = SpecContractService.check_content_compliance(snapshot_data, module_files)
        assert result["compliant"] is True

    def test_missing_module_detected(self):
        snapshot_data = {
            "module_count": 3,
            "modules": [
                {"title": "Intro", "duration": "20 min"},
                {"title": "Deploy", "duration": "25 min"},
                {"title": "Migrate", "duration": "20 min"},
            ],
        }
        module_files = ["03-module-01-intro.adoc", "04-module-02-deploy.adoc"]
        result = SpecContractService.check_content_compliance(snapshot_data, module_files)
        assert result["compliant"] is False
        assert "Expected 3 modules, found 2" in result["message"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd src/backend
DATABASE_URL=sqlite:///./test.db python -m pytest tests/test_spec_contract.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create SpecSnapshot model**

Create `src/backend/app/models/spec_snapshot.py`:

```python
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, DateTime, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.core.types import JSONBType


class SpecSnapshot(Base):
    __tablename__ = "spec_snapshots"
    __table_args__ = (
        Index("ix_spec_snapshots_project_current", "project_id", "is_current"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    snapshot_data: Mapped[dict] = mapped_column(JSONBType, nullable=False)
    source_commit: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    superseded_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

Register in `app/models/__init__.py` — add `from app.models.spec_snapshot import SpecSnapshot` and add to `__all__`.

- [ ] **Step 4: Create SpecContractService**

Create `src/backend/app/services/spec_contract.py`:

```python
"""Spec contract lifecycle — snapshot creation, drift detection, content compliance.

Pure Python extraction from markdown. No LLM in the extraction chain.
"""
from __future__ import annotations

import logging
import re
import uuid

from sqlalchemy.orm import Session

from app.models.spec_snapshot import SpecSnapshot

logger = logging.getLogger(__name__)


class SpecContractService:
    @staticmethod
    def extract_contract_fields(design_md: str, module_specs: dict[str, str]) -> dict:
        """Extract contract fields from design.md + module specs using pure Python.

        Returns a dict of fields suitable for storage as snapshot_data.
        Includes 'extraction_errors' list for any fields that couldn't be parsed.
        """
        fields: dict = {"extraction_errors": []}

        # Content type
        ct_match = re.search(r"##\s*Content\s+Type\s*\n+(.+)", design_md, re.IGNORECASE)
        if ct_match:
            val = ct_match.group(1).strip().rstrip(".")
            fields["content_type"] = val if val else None
            if not val:
                fields["extraction_errors"].append(
                    "design.md: Content Type section is empty."
                )
        else:
            fields["content_type"] = None
            fields["extraction_errors"].append(
                "design.md: Could not find '## Content Type' section."
            )

        # Difficulty
        diff_match = re.search(r"##\s*Difficulty\s+Level\s*\n+(.+)", design_md, re.IGNORECASE)
        if diff_match:
            fields["difficulty"] = diff_match.group(1).strip().rstrip(".")
        else:
            fields["difficulty"] = None
            fields["extraction_errors"].append(
                "design.md: Could not find '## Difficulty Level' section."
            )

        # Products
        prod_match = re.search(
            r"##\s*Products?\s*(?:&|and)?\s*Technologies?\s*\n((?:[-*]\s+.+\n?)+)",
            design_md, re.IGNORECASE,
        )
        if prod_match:
            fields["products"] = [p.strip() for p in re.findall(r"[-*]\s+(.+)", prod_match.group(1))]
        else:
            fields["products"] = []
            fields["extraction_errors"].append(
                "design.md: Could not extract products. Expected bulleted list under '## Products & Technologies'."
            )

        # Learning objectives
        obj_match = re.search(
            r"##\s*Learning\s+Objectives\s*\n((?:\d+\.\s+.+\n?)+)",
            design_md, re.IGNORECASE,
        )
        if obj_match:
            fields["learning_objectives"] = re.findall(r"\d+\.\s+(.+)", obj_match.group(1))
        else:
            # Try bullet list format
            obj_match_bullet = re.search(
                r"##\s*Learning\s+Objectives\s*\n((?:[-*]\s+.+\n?)+)",
                design_md, re.IGNORECASE,
            )
            if obj_match_bullet:
                fields["learning_objectives"] = [o.strip() for o in re.findall(r"[-*]\s+(.+)", obj_match_bullet.group(1))]
            else:
                fields["learning_objectives"] = []
                fields["extraction_errors"].append(
                    "design.md: Could not extract learning objectives. "
                    "Expected numbered or bulleted list under '## Learning Objectives'."
                )

        # Module map — extract from table rows
        module_rows = re.findall(
            r"\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|",
            design_md,
        )
        modules = []
        for num, title, duration in module_rows:
            title = title.strip()
            duration = duration.strip()
            if title.startswith("**") or title.startswith("—") or title == "":
                continue
            modules.append({"title": title, "duration": duration})
        fields["modules"] = modules
        fields["module_count"] = len(modules)

        # Total duration
        total_match = re.search(r"Total.*?(\d+\s*(?:min|hour|hr|hours))", design_md, re.IGNORECASE)
        fields["total_duration"] = total_match.group(1).strip() if total_match else None

        # Section counts
        fields["section_counts"] = {
            "design_md": len(re.findall(r"^##\s+", design_md, re.MULTILINE)),
            "module_specs": len(module_specs),
        }

        if not fields["extraction_errors"]:
            del fields["extraction_errors"]

        return fields

    @staticmethod
    def create_snapshot(
        db: Session,
        project_id: uuid.UUID,
        design_md: str,
        module_specs: dict[str, str],
        source_commit: str | None = None,
    ) -> SpecSnapshot:
        """Create a new spec snapshot, superseding any current one."""
        fields = SpecContractService.extract_contract_fields(design_md, module_specs)

        # Supersede existing current snapshot
        current = SpecContractService.get_current_snapshot(db, project_id)

        new_snapshot = SpecSnapshot(
            project_id=project_id,
            snapshot_data=fields,
            source_commit=source_commit,
            is_current=True,
        )
        db.add(new_snapshot)
        db.flush()

        if current:
            current.is_current = False
            current.superseded_by = new_snapshot.id

        db.commit()
        db.refresh(new_snapshot)
        return new_snapshot

    @staticmethod
    def get_current_snapshot(db: Session, project_id: uuid.UUID) -> SpecSnapshot | None:
        """Get the current (active) snapshot for a project."""
        return db.query(SpecSnapshot).filter(
            SpecSnapshot.project_id == project_id,
            SpecSnapshot.is_current == True,  # noqa: E712
        ).first()

    @staticmethod
    def check_spec_drift(
        db: Session,
        project_id: uuid.UUID,
        design_md: str,
        module_specs: dict[str, str],
    ) -> dict:
        """Check if spec has drifted from the approved snapshot.

        Compares contract fields extracted from current spec against stored snapshot.
        Returns drifted=True with specific changes if fields differ.
        """
        current = SpecContractService.get_current_snapshot(db, project_id)
        if not current:
            return {"drifted": False, "no_snapshot": True, "message": "No approved snapshot exists."}

        new_fields = SpecContractService.extract_contract_fields(design_md, module_specs)
        old_fields = current.snapshot_data
        changes = []

        CONTRACT_KEYS = [
            "content_type", "difficulty", "products", "learning_objectives",
            "module_count", "modules", "total_duration",
        ]
        for key in CONTRACT_KEYS:
            old_val = old_fields.get(key)
            new_val = new_fields.get(key)
            if old_val != new_val:
                changes.append({
                    "field": key,
                    "old": old_val,
                    "new": new_val,
                })

        if changes:
            parts = ["Spec has been modified since approval. Changed fields:"]
            for c in changes:
                parts.append(f"  - {c['field']}: {c['old']} → {c['new']}")
            parts.append("Re-approval required before proceeding.")
            return {
                "drifted": True,
                "changes": changes,
                "message": "\n".join(parts),
            }

        return {"drifted": False, "changes": [], "message": "Spec matches approved snapshot."}

    @staticmethod
    def check_content_compliance(
        snapshot_data: dict,
        module_files: list[str],
    ) -> dict:
        """Check that delivered AsciiDoc content matches the snapshot structurally.

        Compares module count (file count vs snapshot module_count).
        """
        expected_count = snapshot_data.get("module_count", 0)
        actual_count = len(module_files)

        if actual_count < expected_count:
            return {
                "compliant": False,
                "message": (
                    f"Content does not match the approved spec. "
                    f"Expected {expected_count} modules, found {actual_count}."
                ),
                "expected": expected_count,
                "actual": actual_count,
            }

        return {
            "compliant": True,
            "message": f"Content structure matches: {actual_count} module(s) found.",
            "expected": expected_count,
            "actual": actual_count,
        }
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd src/backend
DATABASE_URL=sqlite:///./test.db python -m pytest tests/test_spec_contract.py -v
```

Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/backend/app/models/spec_snapshot.py src/backend/app/models/__init__.py src/backend/app/services/spec_contract.py src/backend/tests/test_spec_contract.py
git commit -m "[RHDPCD-170] Add SpecSnapshot model and SpecContractService"
```

---

### Task 5: Alembic Migration for New Tables

**Files:**
- Create: `src/backend/alembic/versions/f4g5h6i7j8k9_add_vocabulary_spec_snapshot.py`
- Modify: `src/backend/alembic/env.py`

**Interfaces:**
- Consumes: SpecSnapshot and VocabularyEntry models from Tasks 2 and 4
- Produces: Database tables `vocabulary_entries` and `spec_snapshots`

- [ ] **Step 1: Update alembic/env.py to import new models**

Add after the existing model imports:

```python
from app.models.spec_snapshot import SpecSnapshot  # noqa: F401
from app.models.vocabulary import VocabularyEntry  # noqa: F401
```

- [ ] **Step 2: Generate migration**

```bash
cd src/backend
DATABASE_URL=sqlite:///./test.db alembic revision --autogenerate -m "add_vocabulary_spec_snapshot"
```

Verify the generated migration creates two tables: `vocabulary_entries` and `spec_snapshots` with the correct columns and indexes.

- [ ] **Step 3: Run migration forward and backward**

```bash
cd src/backend
DATABASE_URL=sqlite:///./test.db alembic upgrade head
DATABASE_URL=sqlite:///./test.db alembic downgrade -1
DATABASE_URL=sqlite:///./test.db alembic upgrade head
```

Expected: No errors on upgrade or downgrade.

- [ ] **Step 4: Run full test suite**

```bash
cd src/backend
DATABASE_URL=sqlite:///./test.db python -m pytest tests/ -x -v --timeout=30
```

Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/backend/alembic/
git commit -m "[RHDPCD-170] Add Alembic migration for vocabulary_entries and spec_snapshots"
```

---

### Task 6: Integrate Validation into GateService and Gate Tools

**Files:**
- Modify: `src/backend/app/services/gate_service.py`
- Modify: `src/backend/app/mcp/gate_tools.py`
- Test: `src/backend/tests/test_gate_validation_hardening.py`

**Interfaces:**
- Consumes: `PhaseEngine.validate_phase_profile()` (Task 1), `SpecValidator.validate_module_spec()` + `SpecValidator.validate_vocabulary()` (Task 3), `SpecContractService.create_snapshot()` + `check_spec_drift()` + `check_content_compliance()` (Task 4)
- Produces: Updated gate evaluation flow with all new checks integrated

- [ ] **Step 1: Write failing tests for integrated gate validation**

Create `tests/test_gate_validation_hardening.py`:

```python
"""Tests for RHDPCD-170 gate validation hardening — integration of all new checks."""
import uuid
import pytest

from app.models.gate_record import GateRecord
from app.models.spec_snapshot import SpecSnapshot
from app.services.gate_service import GateService
from app.services.phase_engine import PhaseEngine
from app.services.spec_contract import SpecContractService
from app.services.vocabulary import VocabularyService


def _onboarded_manifest(**phase_overrides):
    phases = {name: {"status": phase_overrides.get(name, "pending")}
              for name in ["intake", "vetting", "spec_refinement", "approval",
                           "writing", "automation", "editing", "code_review",
                           "security_review", "e2e_testing", "final_review",
                           "ready_for_publishing"]}
    return {
        "project": {
            "deployment_mode": "rhdp_published",
            "owner_github": "author",
            "owner_email": "author@redhat.com",
        },
        "lifecycle": {"current_phase": "approval", "phases": phases},
    }


class TestPhaseIntegrityAtGate:
    def test_extra_phase_blocks_gate(self, db_session):
        manifest = _onboarded_manifest(intake="completed", vetting="completed", spec_refinement="completed")
        manifest["lifecycle"]["phases"]["custom_review"] = {"status": "pending"}
        result = PhaseEngine.validate_phase_profile(manifest)
        assert result["valid"] is False
        assert "custom_review" in result["extra_phases"]

    def test_valid_phases_pass(self, db_session):
        manifest = _onboarded_manifest(intake="completed", vetting="completed", spec_refinement="completed")
        result = PhaseEngine.validate_phase_profile(manifest)
        assert result["valid"] is True


class TestSnapshotAtApproval:
    def test_snapshot_created_on_approval(self, db_session):
        project_id = uuid.uuid4()
        from tests.test_spec_contract import DESIGN_MD
        snapshot = SpecContractService.create_snapshot(
            db_session, project_id, DESIGN_MD, {}, source_commit="abc123",
        )
        assert snapshot.is_current is True
        assert snapshot.snapshot_data["module_count"] == 4

    def test_drift_detected_after_modification(self, db_session):
        project_id = uuid.uuid4()
        from tests.test_spec_contract import DESIGN_MD
        SpecContractService.create_snapshot(
            db_session, project_id, DESIGN_MD, {}, source_commit="abc123",
        )
        modified = DESIGN_MD.replace("intermediate", "advanced")
        result = SpecContractService.check_spec_drift(db_session, project_id, modified, {})
        assert result["drifted"] is True
        assert any(c["field"] == "difficulty" for c in result["changes"])
```

- [ ] **Step 2: Run tests to verify they pass** (these use already-implemented services)

```bash
cd src/backend
DATABASE_URL=sqlite:///./test.db python -m pytest tests/test_gate_validation_hardening.py -v
```

Expected: PASS — these tests verify the integration is wired correctly.

- [ ] **Step 3: Add phase integrity check to ph_request_gate**

In `src/backend/app/mcp/gate_tools.py`, in `ph_request_gate()`, after fetching the manifest and before the existing spec validation block, add:

```python
# Phase integrity check — before any other validation
profile_check = PhaseEngine.validate_phase_profile(manifest)
if not profile_check["valid"]:
    record = GateRecord(
        project_id=project_id,
        phase=target_phase,
        result="rejected",
        reason=profile_check["message"],
        findings={"extra_phases": profile_check["extra_phases"],
                  "missing_phases": profile_check["missing_phases"]},
        requested_by=requested_by,
        created_at=datetime.now(timezone.utc),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {
        "approved": False,
        "reason": profile_check["message"],
        "gate_id": str(record.id),
    }
```

- [ ] **Step 4: Add vocabulary + module spec validation at approval gate**

In `ph_request_gate()`, in the `target_phase in ("spec_refinement", "approval")` block, after the existing `SpecValidator.validate_structure()` call, add vocabulary and module spec validation for the approval gate:

```python
if target_phase == "approval" and gate_type == "hard":
    # Vocabulary validation
    from app.services.vocabulary import VocabularyService
    VocabularyService.seed_defaults(db)
    vocab_result = SpecValidator.validate_vocabulary(design_spec, db)
    if not vocab_result.passed:
        record = GateRecord(
            project_id=project_id,
            phase=target_phase,
            result="rejected",
            reason="Vocabulary validation failed",
            findings={"issues": vocab_result.issues, "checks": vocab_result.checks},
            requested_by=requested_by,
            created_at=datetime.now(timezone.utc),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return {
            "approved": False,
            "reason": "Vocabulary validation failed",
            "findings": vocab_result.issues,
            "gate_id": str(record.id),
        }

    # Module spec validation
    module_files = _list_module_outlines(reader, owner, repo, branch)
    module_issues = []
    for module_filename in module_files:
        module_content = reader.fetch_file(
            owner, repo,
            f"publishing-house/spec/modules/{module_filename}",
            branch,
        )
        if module_content:
            mod_result = SpecValidator.validate_module_spec(module_content, module_filename)
            if not mod_result.passed:
                module_issues.extend(mod_result.issues)

    if module_issues:
        record = GateRecord(
            project_id=project_id,
            phase=target_phase,
            result="rejected",
            reason="Module spec validation failed",
            findings={"issues": module_issues},
            requested_by=requested_by,
            created_at=datetime.now(timezone.utc),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return {
            "approved": False,
            "reason": "Module spec validation failed",
            "findings": module_issues,
            "gate_id": str(record.id),
        }
```

- [ ] **Step 5: Create snapshot after approval gate passes**

In `ph_request_gate()`, after the `GateService.evaluate_gate()` call returns approved for the approval gate, add:

```python
if result.get("approved") and target_phase == "approval":
    from app.services.spec_contract import SpecContractService
    try:
        module_specs = {}
        for mf in _list_module_outlines(reader, owner, repo, branch):
            content = reader.fetch_file(owner, repo, f"publishing-house/spec/modules/{mf}", branch)
            if content:
                module_specs[mf] = content
        snapshot = SpecContractService.create_snapshot(
            db, project_id, design_spec or "", module_specs, source_commit=spec_commit,
        )
        result["spec_snapshot_id"] = str(snapshot.id)
        logger.info("Spec snapshot created: project=%s, snapshot_id=%s", reg["name"], snapshot.id)
    except Exception:
        logger.warning("Failed to create spec snapshot — non-blocking", exc_info=True)
```

- [ ] **Step 6: Add drift + compliance checks at downstream gates**

In `ph_request_gate()`, for the `editing` and `code_review` target phases, add spec drift and content compliance checks before `GateService.evaluate_gate()`:

```python
if target_phase in ("editing", "code_review") and gate_type == "hard":
    from app.services.spec_contract import SpecContractService
    design_spec = reader.fetch_file(owner, repo, "publishing-house/spec/design.md", branch)
    module_specs = {}
    for mf in _list_module_outlines(reader, owner, repo, branch):
        content = reader.fetch_file(owner, repo, f"publishing-house/spec/modules/{mf}", branch)
        if content:
            module_specs[mf] = content

    if design_spec:
        drift = SpecContractService.check_spec_drift(db, project_id, design_spec, module_specs)
        if drift.get("drifted"):
            record = GateRecord(
                project_id=project_id,
                phase=target_phase,
                result="rejected",
                reason=drift["message"],
                findings={"drift_changes": drift["changes"]},
                requested_by=requested_by,
                created_at=datetime.now(timezone.utc),
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            return {
                "approved": False,
                "reason": drift["message"],
                "findings": drift["changes"],
                "gate_id": str(record.id),
            }

    # Content compliance (check AsciiDoc module count)
    snapshot = SpecContractService.get_current_snapshot(db, project_id)
    if snapshot:
        try:
            client = reader._client
            response = client.get(
                f"/repos/{owner}/{repo}/contents/content/modules/ROOT/pages",
                params={"ref": branch},
            )
            if response.status_code == 200:
                items = response.json()
                adoc_files = [i["name"] for i in items
                              if i.get("name", "").endswith(".adoc")
                              and re.match(r"\d+-module-", i["name"])]
                compliance = SpecContractService.check_content_compliance(
                    snapshot.snapshot_data, adoc_files,
                )
                if not compliance["compliant"]:
                    record = GateRecord(
                        project_id=project_id,
                        phase=target_phase,
                        result="rejected",
                        reason=compliance["message"],
                        findings=compliance,
                        requested_by=requested_by,
                        created_at=datetime.now(timezone.utc),
                    )
                    db.add(record)
                    db.commit()
                    db.refresh(record)
                    return {
                        "approved": False,
                        "reason": compliance["message"],
                        "gate_id": str(record.id),
                    }
        except Exception:
            logger.warning("Content compliance check failed — non-blocking", exc_info=True)
```

- [ ] **Step 7: Run full test suite**

```bash
cd src/backend
DATABASE_URL=sqlite:///./test.db python -m pytest tests/ -x -v --timeout=30
```

Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add src/backend/app/services/gate_service.py src/backend/app/mcp/gate_tools.py src/backend/tests/test_gate_validation_hardening.py
git commit -m "[RHDPCD-170] Integrate phase integrity, vocabulary, module spec, snapshot, and drift checks into gate flow"
```

---

### Task 7: Drift Detection in RefreshService and On-Demand MCP Tool

**Files:**
- Modify: `src/backend/app/services/refresh.py`
- Modify: `src/backend/app/mcp/gate_tools.py`
- Test: `src/backend/tests/test_refresh_drift.py`

**Interfaces:**
- Consumes: `PhaseEngine.validate_phase_profile()` (Task 1), `SpecContractService.check_spec_drift()` (Task 4)
- Produces: Updated refresh with drift detection, new `ph_check_content_alignment` MCP tool

- [ ] **Step 1: Write failing test for refresh drift detection**

Create `tests/test_refresh_drift.py`:

```python
"""Tests for drift detection during refresh cycle."""
import uuid
import pytest

from app.services.spec_contract import SpecContractService
from app.services.phase_engine import PhaseEngine


class TestRefreshDriftDetection:
    def test_phase_integrity_runs_during_refresh(self):
        """Phase integrity check should work standalone (used by refresh)."""
        manifest = {
            "project": {"deployment_mode": "rhdp_published"},
            "lifecycle": {
                "current_phase": "writing",
                "phases": {
                    name: {"status": "pending"}
                    for name in ["intake", "vetting", "spec_refinement", "approval",
                                 "writing", "automation", "editing", "code_review",
                                 "security_review", "e2e_testing", "final_review",
                                 "ready_for_publishing"]
                },
            },
        }
        result = PhaseEngine.validate_phase_profile(manifest)
        assert result["valid"] is True

    def test_drift_detection_standalone(self, db_session):
        """Drift detection should work standalone (used by refresh)."""
        from tests.test_spec_contract import DESIGN_MD
        project_id = uuid.uuid4()
        SpecContractService.create_snapshot(
            db_session, project_id, DESIGN_MD, {}, source_commit="abc",
        )
        result = SpecContractService.check_spec_drift(
            db_session, project_id, DESIGN_MD, {},
        )
        assert result["drifted"] is False
```

- [ ] **Step 2: Add phase integrity + drift detection to refresh_project**

In `src/backend/app/services/refresh.py`, in `refresh_project()`, after the `PhaseEngine.get_next_action()` call, add:

```python
# Phase integrity check (cheap Python, runs every refresh)
profile_check = PhaseEngine.validate_phase_profile(manifest)
if not profile_check["valid"]:
    logger.warning(
        "Phase integrity issue for %s@%s: %s",
        project.repo_url, project.branch, profile_check["message"],
    )

# Spec drift detection (if project has an approved snapshot)
from app.models.spec_snapshot import SpecSnapshot
has_snapshot = db.query(SpecSnapshot).filter(
    SpecSnapshot.project_id == project.id,
    SpecSnapshot.is_current == True,  # noqa: E712
).first()
if has_snapshot:
    from app.services.git_repo_reader import GitRepoReader
    from app.services.spec_contract import SpecContractService
    try:
        design_spec = reader.fetch_file(owner, repo, "publishing-house/spec/design.md", project.branch)
        if design_spec:
            drift = SpecContractService.check_spec_drift(db, project.id, design_spec, {})
            if drift.get("drifted"):
                logger.warning(
                    "Spec drift detected for %s@%s: %s",
                    project.repo_url, project.branch, drift["message"],
                )
    except Exception:
        logger.debug("Spec drift check failed during refresh for %s", project.repo_url)
```

- [ ] **Step 3: Add on-demand content alignment check MCP tool**

Add to `src/backend/app/mcp/gate_tools.py`:

```python
@mcp.tool()
def ph_check_content_alignment(repo_url: str, branch: str = "main") -> dict:
    """Check content alignment against the approved spec — on-demand.

    Runs the same deterministic checks as the writing→editing gate:
    spec drift detection and content compliance. Can be called at any
    point during writing, even with incomplete modules.

    Args:
        repo_url: Git repository URL
        branch: Git branch name

    Returns:
        Alignment report with drift status and content compliance.
    """
    logger.info("ph_check_content_alignment called: repo_url=%s, branch=%s", repo_url, branch)
    reader = _get_reader()
    try:
        owner, repo = parse_repo_url(repo_url)
    except ValueError as e:
        return {"error": str(e)}

    db = SessionLocal()
    try:
        project = db.query(Project).filter(
            Project.repo_url == repo_url,
            Project.branch == branch,
        ).first()
        if not project:
            return {"error": f"Project not registered: {repo_url}@{branch}"}

        from app.services.spec_contract import SpecContractService

        design_spec = reader.fetch_file(owner, repo, "publishing-house/spec/design.md", branch)
        if not design_spec:
            return {"error": "Could not read design.md from repo"}

        module_specs = {}
        for mf in _list_module_outlines(reader, owner, repo, branch):
            content = reader.fetch_file(owner, repo, f"publishing-house/spec/modules/{mf}", branch)
            if content:
                module_specs[mf] = content

        # Spec drift check
        drift = SpecContractService.check_spec_drift(db, project.id, design_spec, module_specs)

        # Content compliance check
        snapshot = SpecContractService.get_current_snapshot(db, project.id)
        compliance = None
        if snapshot:
            try:
                client = reader._client
                response = client.get(
                    f"/repos/{owner}/{repo}/contents/content/modules/ROOT/pages",
                    params={"ref": branch},
                )
                if response.status_code == 200:
                    items = response.json()
                    adoc_files = [i["name"] for i in items
                                  if i.get("name", "").endswith(".adoc")
                                  and re.match(r"\d+-module-", i["name"])]
                    compliance = SpecContractService.check_content_compliance(
                        snapshot.snapshot_data, adoc_files,
                    )
            except Exception:
                logger.debug("Content compliance check failed for %s", repo_url)

        return {
            "spec_drift": drift,
            "content_compliance": compliance,
            "snapshot_exists": snapshot is not None,
        }
    except Exception:
        logger.exception("ph_check_content_alignment failed: %s", repo_url)
        return {"error": "Internal error — check Central logs"}
    finally:
        db.close()
```

- [ ] **Step 4: Run tests**

```bash
cd src/backend
DATABASE_URL=sqlite:///./test.db python -m pytest tests/ -x -v --timeout=30
```

Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/backend/app/services/refresh.py src/backend/app/mcp/gate_tools.py src/backend/tests/test_refresh_drift.py
git commit -m "[RHDPCD-170] Add drift detection to refresh cycle and on-demand content alignment MCP tool"
```

---

### Task 8: Template Rename and Writing Mode

**Files:**
- Rename: `rhdp-publishing-house-template/publishing-house/spec/SPEC-TEMPLATE.md` → `module-outline-template.md` (template repo)
- Modify: Skills that reference `SPEC-TEMPLATE.md` (search and replace across skills repo)

**Interfaces:**
- Consumes: Nothing
- Produces: Renamed template file, updated references

- [ ] **Step 1: Rename template file**

```bash
cd /Users/nstephan/devel/publishing-house/rhdp-publishing-house-template
git mv publishing-house/spec/SPEC-TEMPLATE.md publishing-house/spec/module-outline-template.md
```

- [ ] **Step 2: Search for references to old name across all PH repos**

```bash
cd /Users/nstephan/devel/publishing-house
grep -r "SPEC-TEMPLATE" rhdp-publishing-house-skills/ rhdp-publishing-house-central/ rhdp-publishing-house-template/ --include="*.md" --include="*.py" --include="*.yaml" -l
```

Update every file that references `SPEC-TEMPLATE.md` to use `module-outline-template.md`.

- [ ] **Step 3: Commit template rename**

```bash
cd /Users/nstephan/devel/publishing-house/rhdp-publishing-house-template
git add -A
git commit -m "[RHDPCD-170] Rename SPEC-TEMPLATE.md to module-outline-template.md"
git push
```

- [ ] **Step 4: Commit reference updates in skills repo**

```bash
cd /Users/nstephan/devel/publishing-house/rhdp-publishing-house-skills
git add -A
git commit -m "[RHDPCD-170] Update references from SPEC-TEMPLATE.md to module-outline-template.md"
git push
```

- [ ] **Step 5: Verify writing_mode is handled in manifest**

The `writing_mode` field (`self_provided | assisted`) is recorded in the manifest by the orchestrator skill after the approval gate passes. Central reads it from `cached_manifest_data` during refresh. No Central code changes needed — the field is part of the manifest's `lifecycle.phases.writing` section and is handled by the existing manifest parsing (plain dict, no schema enforcement).

Verify this works by checking that `cached_manifest_data` includes writing phase data:

```bash
cd src/backend
python -c "
import yaml
manifest = yaml.safe_load(open('/dev/stdin'))
writing = manifest.get('lifecycle', {}).get('phases', {}).get('writing', {})
print('writing_mode:', writing.get('writing_mode', 'not set'))
" <<< "
lifecycle:
  phases:
    writing:
      status: in_progress
      writing_mode: self_provided
"
```

Expected output: `writing_mode: self_provided`

- [ ] **Step 6: Run full test suite one final time**

```bash
cd /Users/nstephan/devel/publishing-house/rhdp-publishing-house-central/src/backend
DATABASE_URL=sqlite:///./test.db python -m pytest tests/ -x -v --timeout=30
```

Expected: ALL PASS

- [ ] **Step 7: Commit any remaining changes**

```bash
cd /Users/nstephan/devel/publishing-house/rhdp-publishing-house-central
git add -A
git commit -m "[RHDPCD-170] Final cleanup — writing mode support and template rename references"
```

---

## Task Summary

| Task | Component | Complexity |
|------|-----------|------------|
| 1 | Phase integrity in PhaseEngine | Low |
| 2 | VocabularyEntry model + VocabularyService | Medium |
| 3 | Module spec + vocabulary validation in SpecValidator | Medium |
| 4 | SpecSnapshot model + SpecContractService | High |
| 5 | Alembic migration | Low |
| 6 | Gate integration (all checks wired into gate flow) | High |
| 7 | Refresh drift detection + on-demand MCP tool | Medium |
| 8 | Template rename + writing mode | Low |
