"""Drift detection — structural (spec.yaml field diff) and semantic (LLM design.md comparison)."""
import json
import logging
import time
from typing import Optional

import httpx
import yaml
from pydantic import BaseModel

from .github import GitHubService
from ..config import get_settings

logger = logging.getLogger(__name__)

SPEC_PATH = "publishing-house/spec.yaml"
DESIGN_PATH = "publishing-house/spec/design.md"
LITELLM_MODEL = "claude-haiku-4-5"

STRUCTURAL_FIELDS = [
    "project.content_type",
    "project.products",
    "spec.title",
    "spec.audience",
    "spec.learning_objectives",
    "spec.modules",
    "spec.environment.topology",
    "spec.environment.ocp_version",
    "spec.environment.cloud_provider",
    "spec.environment.cluster_type",
    "spec.environment.worker_count",
    "spec.environment.worker_cpu",
    "spec.environment.worker_ram_gb",
    "spec.environment.ai_requirement",
    "spec.environment.ai_model_tier",
]

_drift_cache: dict[tuple[str, str, str], tuple[float, dict]] = {}


def drift_cache_get(slug: str, baseline: str, head: str) -> dict | None:
    key = (slug, baseline, head)
    entry = _drift_cache.get(key)
    if not entry:
        return None
    ts, response = entry
    ttl = get_settings().drift_cache_ttl_seconds
    if time.time() - ts > ttl:
        del _drift_cache[key]
        return None
    logger.debug("drift cache hit for %s (%s..%s)", slug, baseline[:8], head[:8])
    return response


def drift_cache_set(slug: str, baseline: str, head: str, response: dict) -> None:
    _drift_cache[(slug, baseline, head)] = (time.time(), response)


def drift_cache_evict(slug: str) -> None:
    keys = [k for k in _drift_cache if k[0] == slug]
    for k in keys:
        del _drift_cache[k]
    if keys:
        logger.info("evicted %d drift cache entries for %s", len(keys), slug)


SEMANTIC_SYSTEM_PROMPT = """You are a technical document reviewer. You will receive two versions of a design document (BASELINE and CURRENT). Compare them and identify meaningful changes, organized by section.

Ignore cosmetic changes (whitespace, punctuation, rewording that preserves meaning). Only flag substantive changes: added/removed/renamed modules, changed durations, altered infrastructure requirements, changed cluster sizing, added/removed environment dependencies, changed products, etc.

Respond with valid JSON only, no markdown fencing:
{
  "has_drift": true/false,
  "summary": "one-sentence summary of what changed, or 'No meaningful drift detected'",
  "changes": [
    {
      "section": "section name (e.g. Module Map, Environment, Infrastructure Requirements)",
      "difference": "description of what changed"
    }
  ]
}

Only include sections that have meaningful changes. If no drift, return an empty changes array."""


class DriftChange(BaseModel):
    file: str
    comparing: str
    difference: str


class DriftResponse(BaseModel):
    has_drift: bool
    baseline_sha: str
    current_sha: str
    summary: str
    changes: list[DriftChange]


def _empty_response(baseline_sha: str, current_sha: str, summary: str, has_drift: bool = False) -> DriftResponse:
    return DriftResponse(
        has_drift=has_drift,
        baseline_sha=baseline_sha,
        current_sha=current_sha,
        summary=summary,
        changes=[],
    )


def _get_nested(data: dict, dotpath: str):
    keys = dotpath.split(".")
    val = data
    for k in keys:
        if not isinstance(val, dict):
            return None
        val = val.get(k)
    return val


def _format_value(val) -> str:
    if val is None:
        return "<not set>"
    if isinstance(val, list):
        if not val:
            return "<empty>"
        if isinstance(val[0], dict) and "title" in val[0]:
            return ", ".join(m.get("title", "?") for m in val)
        return ", ".join(str(v) for v in val)
    return str(val)


async def check_drift_structural(
    github: GitHubService,
    repo_url: str,
    branch: str,
    baseline_sha: str,
) -> DriftResponse:
    current_sha = await github.get_head_sha(repo_url, branch) or ""

    baseline_raw = await github.get_file_content(repo_url, SPEC_PATH, baseline_sha)
    current_raw = await github.get_file_content(repo_url, SPEC_PATH, branch)

    if not baseline_raw and not current_raw:
        return _empty_response(baseline_sha, current_sha, "spec.yaml not found in either commit")

    if not baseline_raw:
        return _empty_response(baseline_sha, current_sha, "spec.yaml was added after baseline commit", has_drift=True)

    if baseline_raw == current_raw:
        return _empty_response(baseline_sha, current_sha, "No changes to spec.yaml")

    try:
        baseline_data = yaml.safe_load(baseline_raw) or {}
        current_data = yaml.safe_load(current_raw) or {}
    except yaml.YAMLError as e:
        logger.error(f"Failed to parse spec.yaml: {e}")
        return _empty_response(baseline_sha, current_sha, f"Failed to parse spec.yaml: {e}")

    changes: list[DriftChange] = []
    for field in STRUCTURAL_FIELDS:
        old_val = _get_nested(baseline_data, field)
        new_val = _get_nested(current_data, field)
        if old_val != new_val:
            changes.append(DriftChange(
                file="spec.yaml",
                comparing=field,
                difference=f"{_format_value(old_val)} → {_format_value(new_val)}",
            ))

    if not changes:
        return _empty_response(baseline_sha, current_sha, "No structural drift in contract fields")

    field_names = [c.comparing for c in changes]
    summary = f"Structural drift in {len(changes)} field(s): {', '.join(field_names)}"
    return DriftResponse(
        has_drift=True,
        baseline_sha=baseline_sha,
        current_sha=current_sha,
        summary=summary,
        changes=changes,
    )


async def check_drift_semantic(
    github: GitHubService,
    repo_url: str,
    branch: str,
    baseline_sha: str,
    litellm_api_url: str,
    ph_internal_ai_api_key: str,
    slug: str = "",
) -> DriftResponse:
    current_sha = await github.get_head_sha(repo_url, branch) or ""

    if slug and current_sha:
        cached = drift_cache_get(slug, baseline_sha, current_sha)
        if cached is not None:
            return DriftResponse(**cached)

    baseline_md = await github.get_file_content(repo_url, DESIGN_PATH, baseline_sha)
    current_md = await github.get_file_content(repo_url, DESIGN_PATH, branch)

    if not baseline_md and not current_md:
        return _empty_response(baseline_sha, current_sha, "design.md not found in either commit")

    if not baseline_md:
        return _empty_response(baseline_sha, current_sha, "design.md was added after the baseline commit", has_drift=True)

    if baseline_md == current_md:
        resp = _empty_response(baseline_sha, current_sha, "No changes to design.md")
        if slug and current_sha:
            drift_cache_set(slug, baseline_sha, current_sha, resp.model_dump())
        return resp

    user_prompt = f"""## BASELINE VERSION (commit {baseline_sha[:8]}):

{baseline_md}

---

## CURRENT VERSION (commit {current_sha[:8]}):

{current_md}"""

    try:
        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            resp = await client.post(
                f"{litellm_api_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {ph_internal_ai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": LITELLM_MODEL,
                    "messages": [
                        {"role": "system", "content": SEMANTIC_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0,
                    "max_tokens": 1024,
                },
            )

        if resp.status_code != 200:
            logger.error(f"LLM drift check failed: {resp.status_code} {resp.text}")
            return _empty_response(baseline_sha, current_sha, f"LLM comparison failed (HTTP {resp.status_code})")

        content = resp.json()["choices"][0]["message"]["content"]
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]

        result = json.loads(content)

        changes = [
            DriftChange(
                file="design.md",
                comparing=c["section"],
                difference=c["difference"],
            )
            for c in result.get("changes", [])
        ]

        resp = DriftResponse(
            has_drift=result.get("has_drift", False),
            baseline_sha=baseline_sha,
            current_sha=current_sha,
            summary=result.get("summary", ""),
            changes=changes,
        )
        if slug and current_sha:
            drift_cache_set(slug, baseline_sha, current_sha, resp.model_dump())
        return resp

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM drift response: {e}")
        return _empty_response(baseline_sha, current_sha, "Failed to parse LLM comparison result")
    except Exception as e:
        logger.error(f"Drift detection error: {e}")
        return _empty_response(baseline_sha, current_sha, f"Drift detection error: {str(e)}")
