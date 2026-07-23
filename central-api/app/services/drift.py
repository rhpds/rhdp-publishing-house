"""Drift detection — uses LLM to compare design.md between two commits."""
import json
import logging
from typing import Any, Optional

import httpx
from pydantic import BaseModel

from .github import GitHubService

logger = logging.getLogger(__name__)

DESIGN_PATH = "publishing-house/design.md"
LITELLM_MODEL = "claude-haiku-4-5"

SYSTEM_PROMPT = """You are a technical document reviewer. You will receive two versions of a design document (APPROVED and CURRENT). Compare them and identify meaningful changes in the Module Map/Structure and Environment/Infrastructure sections.

Ignore cosmetic changes (whitespace, punctuation, rewording that preserves meaning). Only flag substantive changes: added/removed/renamed modules, changed durations, altered infrastructure requirements, changed cluster sizing, added/removed environment dependencies.

Respond with valid JSON only, no markdown fencing:
{
  "has_drift": true/false,
  "summary": "one-sentence summary of what changed, or 'No meaningful drift detected'",
  "module_changes": [
    {"change": "description of module change"}
  ],
  "environment_changes": [
    {"change": "description of environment change"}
  ]
}"""


class DriftChange(BaseModel):
    change: str


class DriftResponse(BaseModel):
    has_drift: bool
    approved_sha: str
    current_sha: str
    summary: str
    module_changes: list[DriftChange]
    environment_changes: list[DriftChange]


class DriftRequest(BaseModel):
    repo_url: str
    branch: str = "main"
    approved_sha: str


async def check_drift(
    github: GitHubService,
    repo_url: str,
    branch: str,
    approved_sha: str,
    litellm_api_url: str,
    ph_internal_ai_api_key: str,
) -> DriftResponse:
    approved_md = await github.get_file_content(repo_url, DESIGN_PATH, approved_sha)
    current_md = await github.get_file_content(repo_url, DESIGN_PATH, branch)
    current_sha = await github.get_head_sha(repo_url, branch) or ""

    if not approved_md and not current_md:
        return DriftResponse(
            has_drift=False,
            approved_sha=approved_sha,
            current_sha=current_sha,
            summary="design.md not found in either commit",
            module_changes=[],
            environment_changes=[],
        )

    if not approved_md:
        return DriftResponse(
            has_drift=True,
            approved_sha=approved_sha,
            current_sha=current_sha,
            summary="design.md was added after the approved commit",
            module_changes=[],
            environment_changes=[],
        )

    if approved_md == current_md:
        return DriftResponse(
            has_drift=False,
            approved_sha=approved_sha,
            current_sha=current_sha,
            summary="No changes to design.md",
            module_changes=[],
            environment_changes=[],
        )

    user_prompt = f"""## APPROVED VERSION (commit {approved_sha[:8]}):

{approved_md}

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
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0,
                    "max_tokens": 1024,
                },
            )

        if resp.status_code != 200:
            logger.error(f"LLM drift check failed: {resp.status_code} {resp.text}")
            return DriftResponse(
                has_drift=False,
                approved_sha=approved_sha,
                current_sha=current_sha,
                summary=f"LLM comparison failed (HTTP {resp.status_code})",
                module_changes=[],
                environment_changes=[],
            )

        content = resp.json()["choices"][0]["message"]["content"]
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]

        result = json.loads(content)

        return DriftResponse(
            has_drift=result.get("has_drift", False),
            approved_sha=approved_sha,
            current_sha=current_sha,
            summary=result.get("summary", ""),
            module_changes=[DriftChange(change=c["change"]) for c in result.get("module_changes", [])],
            environment_changes=[DriftChange(change=c["change"]) for c in result.get("environment_changes", [])],
        )

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM drift response: {e}")
        return DriftResponse(
            has_drift=False,
            approved_sha=approved_sha,
            current_sha=current_sha,
            summary="Failed to parse LLM comparison result",
            module_changes=[],
            environment_changes=[],
        )
    except Exception as e:
        logger.error(f"Drift detection error: {e}")
        return DriftResponse(
            has_drift=False,
            approved_sha=approved_sha,
            current_sha=current_sha,
            summary=f"Drift detection error: {str(e)}",
            module_changes=[],
            environment_changes=[],
        )
