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

SYSTEM_PROMPT = """You are a technical document reviewer. You will receive two versions of a design document (APPROVED and CURRENT). Compare them and identify meaningful changes, organized by section.

Ignore cosmetic changes (whitespace, punctuation, rewording that preserves meaning). Only flag substantive changes: added/removed/renamed modules, changed durations, altered infrastructure requirements, changed cluster sizing, added/removed environment dependencies, changed products, etc.

Respond with valid JSON only, no markdown fencing:
{
  "has_drift": true/false,
  "summary": "one-sentence summary of what changed, or 'No meaningful drift detected'",
  "sections": [
    {
      "section": "section name (e.g. Module Map, Environment, Infrastructure Requirements)",
      "changes": ["description of change 1", "description of change 2"]
    }
  ]
}

Only include sections that have meaningful changes. If no drift, return an empty sections array."""


class DriftSectionChanges(BaseModel):
    section: str
    changes: list[str]


class DriftFileChanges(BaseModel):
    file: str
    sections: list[DriftSectionChanges]


class DriftResponse(BaseModel):
    has_drift: bool
    approved_sha: str
    current_sha: str
    summary: str
    changes: list[DriftFileChanges]


class DriftRequest(BaseModel):
    repo_url: str
    branch: str = "main"
    approved_sha: str


def _empty_response(approved_sha: str, current_sha: str, summary: str, has_drift: bool = False) -> DriftResponse:
    return DriftResponse(
        has_drift=has_drift,
        approved_sha=approved_sha,
        current_sha=current_sha,
        summary=summary,
        changes=[],
    )


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
        return _empty_response(approved_sha, current_sha, "design.md not found in either commit")

    if not approved_md:
        return _empty_response(approved_sha, current_sha, "design.md was added after the approved commit", has_drift=True)

    if approved_md == current_md:
        return _empty_response(approved_sha, current_sha, "No changes to design.md")

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
            return _empty_response(approved_sha, current_sha, f"LLM comparison failed (HTTP {resp.status_code})")

        content = resp.json()["choices"][0]["message"]["content"]
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]

        result = json.loads(content)

        sections = [
            DriftSectionChanges(section=s["section"], changes=s["changes"])
            for s in result.get("sections", [])
        ]

        file_changes = []
        if sections:
            file_changes.append(DriftFileChanges(file="design.md", sections=sections))

        return DriftResponse(
            has_drift=result.get("has_drift", False),
            approved_sha=approved_sha,
            current_sha=current_sha,
            summary=result.get("summary", ""),
            changes=file_changes,
        )

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM drift response: {e}")
        return _empty_response(approved_sha, current_sha, "Failed to parse LLM comparison result")
    except Exception as e:
        logger.error(f"Drift detection error: {e}")
        return _empty_response(approved_sha, current_sha, f"Drift detection error: {str(e)}")
