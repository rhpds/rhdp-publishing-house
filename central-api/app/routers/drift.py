"""Drift router — structural and semantic drift detection endpoints."""
import json
import logging
import urllib.request
import ssl
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..auth.groups import decode_signed_key
from ..config import get_settings
from ..services.github import GitHubService
from ..services.drift import DriftResponse, check_drift_structural, check_drift_semantic, drift_cache_evict

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/spec/drift", tags=["drift"])
_bearer = HTTPBearer(auto_error=False)

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def _get_review_history(workflow_id: str, settings=None) -> list:
    """Fetch the current reviewHistory array from the workflow instance."""
    if not settings:
        settings = get_settings()
    try:
        query = {
            "query": """
                query ($id: String!) {
                    ProcessInstances(where: { id: { equal: $id } }) {
                        variables
                    }
                }
            """,
            "variables": {"id": workflow_id},
        }
        req = urllib.request.Request(
            f"{settings.sonataflow_graphql_url.rstrip('/')}/graphql",
            data=json.dumps(query).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=10) as r:
            result = json.loads(r.read().decode())
        instances = result.get("data", {}).get("ProcessInstances", [])
        if not instances:
            return []
        variables = instances[0].get("variables", {})
        wd = variables.get("workflowdata", {}) if isinstance(variables, dict) else {}
        return wd.get("reviewHistory", [])
    except Exception as e:
        logger.warning("failed to fetch reviewHistory for %s: %s", workflow_id, e)
        return []


def _require_auth(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> str:
    settings = get_settings()
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
    if credentials.credentials == settings.ph_api_key:
        return "service"
    result = decode_signed_key(credentials.credentials)
    if not result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return result[0]


@router.post("/{slug}", response_model=DriftResponse)
async def detect_drift(
    slug: str,
    mode: str = Query("semantic", regex="^(structural|semantic)$"),
    owner: str = Depends(_require_auth),
):
    """Look up workflow data for slug, then compare spec.yaml (structural) or design.md (semantic)
    between baselineSha and current HEAD."""
    from .projects import _get_workflow_data

    settings = get_settings()
    if not settings.github_token:
        raise HTTPException(status_code=500, detail="GITHUB_TOKEN not configured on Central API")

    wd = _get_workflow_data(slug)
    if not wd or not wd.get("workflow_id"):
        raise HTTPException(status_code=404, detail=f"No active workflow found for '{slug}'")

    repo_url = wd.get("repoUrl", "")
    baseline_sha = wd.get("baselineSha", "")
    if not repo_url:
        raise HTTPException(status_code=422, detail="Workflow has no repoUrl set")
    if not baseline_sha:
        raise HTTPException(status_code=422, detail="Workflow has no baselineSha set")

    github = GitHubService(token=settings.github_token)

    if mode == "structural":
        return await check_drift_structural(github, repo_url, "main", baseline_sha)

    if not settings.ph_internal_ai_api_key:
        raise HTTPException(status_code=500, detail="PH_INTERNAL_AI_API_KEY not configured on Central API")

    return await check_drift_semantic(
        github,
        repo_url,
        "main",
        baseline_sha,
        settings.litellm_api_url,
        settings.ph_internal_ai_api_key,
        slug=slug,
    )


