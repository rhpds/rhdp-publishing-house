"""Spec drift detection — compares contract fields at approved SHA vs HEAD."""
import logging
from typing import Any, Optional

import yaml
from pydantic import BaseModel

from .github import GitHubService

logger = logging.getLogger(__name__)

SPEC_PATH = "publishing-house/spec.yaml"

CONTRACT_FIELDS = [
    ("content_type", ("project", "content_type")),
    ("audience", ("spec", "audience")),
    ("products", ("project", "products")),
    ("learning_objectives", ("spec", "learning_objectives")),
    ("modules", ("spec", "modules")),
    ("total_duration_hours", ("spec", "total_duration_hours")),
]


class DriftField(BaseModel):
    field: str
    approved_value: Any = None
    current_value: Any = None
    changed: bool


class DriftResponse(BaseModel):
    has_drift: bool
    approved_sha: str
    current_sha: str
    fields: list[DriftField]


class DriftRequest(BaseModel):
    repo_url: str
    branch: str = "main"
    approved_sha: str


def _extract_contract_fields(spec_data: Optional[dict]) -> dict[str, Any]:
    if not spec_data:
        return {name: None for name, _ in CONTRACT_FIELDS}
    result = {}
    for name, (section, key) in CONTRACT_FIELDS:
        val = spec_data.get(section, {}).get(key)
        if name == "modules" and isinstance(val, list):
            val = [{"title": m.get("title", ""), "id": m.get("id", "")} for m in val]
        result[name] = val
    return result


def _normalize(val: Any) -> Any:
    if isinstance(val, list):
        return sorted([str(v) for v in val])
    return val


async def check_drift(
    github: GitHubService,
    repo_url: str,
    branch: str,
    approved_sha: str,
) -> DriftResponse:
    approved_raw = await github.get_file_content(repo_url, SPEC_PATH, approved_sha)
    current_raw = await github.get_file_content(repo_url, SPEC_PATH, branch)
    current_sha = await github.get_head_sha(repo_url, branch) or ""

    approved_spec = yaml.safe_load(approved_raw) if approved_raw else None
    current_spec = yaml.safe_load(current_raw) if current_raw else None

    approved_fields = _extract_contract_fields(approved_spec)
    current_fields = _extract_contract_fields(current_spec)

    drift_fields = []
    for name, _ in CONTRACT_FIELDS:
        av = approved_fields[name]
        cv = current_fields[name]
        changed = _normalize(av) != _normalize(cv)
        drift_fields.append(DriftField(
            field=name,
            approved_value=av,
            current_value=cv,
            changed=changed,
        ))

    return DriftResponse(
        has_drift=any(f.changed for f in drift_fields),
        approved_sha=approved_sha,
        current_sha=current_sha,
        fields=drift_fields,
    )
