"""Publishing House projects and auth endpoints — all under /projects."""
import asyncio
import json
import logging
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from ..auth.groups import GROUP_BITS, ALL_GROUPS_MASK, decode_signed_key
from ..config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["projects"])
_bearer = HTTPBearer(auto_error=False)

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


# ── Project Schemas ───────────────────────────────────────────────────────────

class IntakeRequest(BaseModel):
    repo_url: str
    branch: str = "main"


class IntakeResponse(BaseModel):
    status: int
    stage: Optional[str] = None
    error: Optional[str] = None
    validation: Optional[dict] = None


class DevelopmentRequest(BaseModel):
    repo_url: str
    branch: str = "main"


class DevelopmentResponse(BaseModel):
    status: int
    stage: Optional[str] = None
    error: Optional[str] = None
    validation: Optional[dict] = None


class TestingRequest(BaseModel):
    repo_url: str
    branch: str = "main"


class TestingResponse(BaseModel):
    status: int
    stage: Optional[str] = None
    error: Optional[str] = None
    validation: Optional[dict] = None


class DeleteProjectResponse(BaseModel):
    slug: str
    workflow_aborted: bool = False
    db_cleaned: bool = False
    catalog_cleaned: bool = False
    litellm_keys_deleted: int = 0
    jira_archived: bool = False
    repo_deleted: bool = False
    errors: list[str] = []


# ── Auth Helpers ──────────────────────────────────────────────────────────────

def _require_auth(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> tuple[str, int]:
    """Validate auth and return (identity, groups_bitmask).

    Checks in order:
    1. Master PH_API_KEY → ("service", ALL_GROUPS_MASK)
    2. Signed bitmask token → (email, bitmask)
    """
    settings = get_settings()
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")

    token = credentials.credentials

    if token == settings.ph_api_key:
        return "service", ALL_GROUPS_MASK

    result = decode_signed_key(token)
    if result:
        return result

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")



def _require_group(groups: int, required: int, group_name: str):
    if not (groups & required):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires membership in {group_name}",
        )


def _advance_workflow(
    project_slug: str, wf_uuid: str, owner: str,
    stage: str = "intake", commit_sha: str | None = None, settings=None,
) -> None:
    """Send a stage-complete CloudEvent to SonataFlow (fire-and-forget).
    project_slug is the business key for event correlation.
    stage is the current stage being completed (e.g. 'intake', 'development').
    Raises HTTPException if the CloudEvent send fails."""
    if not settings:
        settings = get_settings()

    event_type = f"ph.{stage}.complete"
    try:
        cloud_event = {
            "specversion": "1.0",
            "type": event_type,
            "source": "publishing-house",
            "id": str(uuid.uuid4()),
            "kogitobusinesskey": project_slug,
            "projectid": project_slug,
            "datacontenttype": "application/json",
            "data": {
                "user": owner,
                "stage": stage,
                "action": "submitted",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "commitSha": commit_sha,
            }
        }
        req = urllib.request.Request(
            f"{settings.sonataflow_url.rstrip('/')}",
            data=json.dumps(cloud_event).encode(),
            headers={"Content-Type": "application/cloudevents+json"}
        )
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=30) as r:
            pass
        logger.info("sent %s for workflow=%s", event_type, project_slug)
    except Exception as e:
        logger.warning("CloudEvent send failed for workflow %s: %s", project_slug, e)
        raise HTTPException(status_code=502, detail=f"CloudEvent send failed: {e}")


def _patch_workflow_data(wf_uuid: str, data: dict, settings=None) -> None:
    """PATCH SonataFlow workflow instance data (merge, no state transition)."""
    if not settings:
        settings = get_settings()
    try:
        req = urllib.request.Request(
            f"{settings.sonataflow_url.rstrip('/')}/publishinghouseworkflow/{wf_uuid}",
            data=json.dumps({"workflowdata": data}).encode(),
            headers={"Content-Type": "application/json"},
            method="PATCH",
        )
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=10):
            pass
        logger.info("patched workflow %s with %s", wf_uuid, data)
    except Exception as e:
        logger.warning("workflow PATCH failed for %s: %s", wf_uuid, e)
        raise HTTPException(status_code=502, detail=f"Workflow PATCH failed: {e}")


# ── Project Endpoints ─────────────────────────────────────────────────────────

def _get_workflow_data(project_id: str):
    """Internal: query workflow data — no auth check."""
    settings = get_settings()
    try:
        graphql_query = {
            "query": """
                query GetWorkflowData($businessKey: String!) {
                    ProcessInstances(where: { businessKey: { equal: $businessKey }, state: { in: [ACTIVE, SUSPENDED] } }) {
                        id
                        variables
                    }
                }
            """,
            "variables": {"businessKey": project_id}
        }
        req = urllib.request.Request(
            f"{settings.sonataflow_graphql_url.rstrip('/')}/graphql",
            data=json.dumps(graphql_query).encode(),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=10) as r:
            result = json.loads(r.read().decode())
        instances = result.get("data", {}).get("ProcessInstances", [])
        if not instances:
            raise HTTPException(status_code=404, detail=f"No workflow found for {project_id}")
        inst = instances[0]
        variables = inst.get("variables", {})
        wd = variables.get("workflowdata", {}) if isinstance(variables, dict) else {}
        rejection = wd.get("rejection") or variables.get("rejection")
        result = {
            "project_id": project_id,
            "workflow_id": inst.get("id", ""),
            "epic_key": wd.get("epic_key", ""),
            "baselineSha": wd.get("baselineSha", ""),
            "hasDrift": wd.get("hasDrift", False),
            "repoUrl": wd.get("repoUrl", ""),
            "agnosticvUrls": wd.get("agnosticvUrls", []),
            "ciUrls": wd.get("ciUrls", []),
        }
        if rejection and rejection.get("isRejected"):
            result["rejection"] = rejection
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("workflow-data failed for %s: %s", project_id, e)
        raise HTTPException(status_code=502, detail=f"Failed to query workflow: {e}")


@router.get("/{project_id}/workflow-data")
def get_workflow_data(project_id: str, auth: tuple[str, int] = Depends(_require_auth)):
    """Return workflow data subset (epic_key, jira_url)."""
    _owner, groups = auth
    _require_group(groups, GROUP_BITS["rhdp-developers"], "rhdp-developers")
    return _get_workflow_data(project_id)


_STATE_MAP = {
    "intake": "intake",
    "contentreview": "content_review",
    "contentreviewdecision": "content_review",
    "infrareview": "infra_review",
    "infrareviewdecision": "infra_review",
    "jirasyncintake": "jira_sync",
    "envsetupordev": "env_setup",
    "envsetup": "env_setup",
    "jirasyncenvsetup": "jira_sync",
    "jirasyncdev": "jira_sync",
    "jirasyncfinal": "jira_sync",
    "development": "development",
    "testing": "testing",
    "published": "published",
}


def _get_workflow_state(workflow_id: str):
    """Internal: query workflow state — no auth check."""
    settings = get_settings()
    try:
        graphql_query = {
            "query": """
                query GetWorkflowById($id: String!) {
                    ProcessInstances(where: { id: { equal: $id } }) {
                        id
                        state
                        nodes { name type enter exit }
                    }
                }
            """,
            "variables": {"id": workflow_id}
        }
        req = urllib.request.Request(
            f"{settings.sonataflow_graphql_url.rstrip('/')}/graphql",
            data=json.dumps(graphql_query).encode(),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=10) as r:
            result = json.loads(r.read().decode())
        instances = result.get("data", {}).get("ProcessInstances", [])
        inst = instances[0] if instances else None
        if inst:
            process_state = inst.get("state", "")

            if process_state == "COMPLETED":
                stage = "published"
            elif process_state == "ERROR":
                stage = "error"
            else:
                stage = "intake"
                latest_enter = ""
                for node in inst.get("nodes", []):
                    if node.get("type") != "CompositeContextNode":
                        continue
                    if not node.get("enter") or node.get("exit"):
                        continue
                    candidate = _STATE_MAP.get(node.get("name", "").lower())
                    if candidate and node["enter"] > latest_enter:
                        stage = candidate
                        latest_enter = node["enter"]

            return {
                "stage": stage,
                "workflow_id": workflow_id,
                "source": "sonataflow",
            }
    except Exception as e:
        logger.warning("workflow-state fallback for %s: %s", workflow_id, e)
    return {"stage": "intake", "workflow_id": workflow_id, "source": "fallback"}


@router.get("/workflow-state/{workflow_id}")
def get_workflow_state(workflow_id: str, auth: tuple[str, int] = Depends(_require_auth)):
    """Return semantic workflow stage by process instance UUID."""
    _owner, groups = auth
    _require_group(groups, GROUP_BITS["rhdp-developers"], "rhdp-developers")
    return _get_workflow_state(workflow_id)


def _require_stage(workflow_id: str, allowed: list[str]) -> str:
    """Check the workflow stage and raise 409 if not in allowed list."""
    current = _get_workflow_state(workflow_id).get("stage", "unknown")
    if current not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Workflow '{workflow_id}' is in '{current}' stage. "
                   f"This action requires stage: {', '.join(allowed)}.",
        )
    return current


def _check_github_write_access(repo_url: str, github_user: str | None) -> None:
    """Verify the GitHub user has write or admin access to the repo. Reusable across stages."""
    logger.info("github write-access check: user=%r repo=%s", github_user, repo_url)
    if not github_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=json.dumps({"error": "GitHub username is required", "code": "github_user_missing"}),
        )
    match = re.match(r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?$", repo_url)
    if not match:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot parse owner/repo from URL: {repo_url}",
        )
    owner, repo = match.group(1), match.group(2)
    settings = get_settings()
    if not settings.github_token:
        logger.warning("GITHUB_TOKEN not set — skipping write-access check")
        return
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{owner}/{repo}/collaborators/{github_user}/permission",
            headers={
                "Authorization": f"Bearer {settings.github_token}",
                "Accept": "application/vnd.github+json",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        permission = data.get("permission", "")
        if permission not in ("write", "admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=json.dumps({
                    "error": f"User '{github_user}' does not have write access to {owner}/{repo}",
                    "code": "github_write_denied",
                }),
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("GitHub permission check failed for %s on %s/%s: %s", github_user, owner, repo, e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to verify GitHub permissions: {e}",
        )


@router.post("/intake/{project_slug}", response_model=IntakeResponse)
async def submit_intake(
    project_slug: str,
    body: IntakeRequest,
    auth: tuple[str, int] = Depends(_require_auth),
    x_github_user: str | None = Header(None, alias="X-GitHub-User"),
):
    """Validate spec, then advance workflow past intake.

    Returns a unified response shape for all outcomes:
    201 — validation passed, workflow advanced
    422 — validation failed, stage included
    409 — workflow not in intake stage
    404 — no workflow found
    500 — unexpected server error
    """
    from fastapi.responses import JSONResponse
    from ..services.github import GitHubService
    from ..services.validation.runner import run_validation

    owner, groups = auth
    _require_group(groups, GROUP_BITS["rhdp-developers"], "rhdp-developers")
    stage = None

    try:
        # Look up workflow
        try:
            wd = _get_workflow_data(project_slug)
        except HTTPException as e:
            if e.status_code == 404:
                return JSONResponse(status_code=404, content=IntakeResponse(
                    status=404, error=f"No workflow found for {project_slug}",
                ).model_dump())
            raise

        wf_uuid = wd.get("workflow_id", "")
        if not wf_uuid:
            return JSONResponse(status_code=404, content=IntakeResponse(
                status=404, error=f"No workflow found for {project_slug}",
            ).model_dump())

        # Check stage
        current = _get_workflow_state(wf_uuid).get("stage", "unknown")
        stage = current
        if current != "intake":
            return JSONResponse(status_code=409, content=IntakeResponse(
                status=409, stage=current,
                error=f"Workflow is in '{current}' stage. Intake requires 'intake'.",
            ).model_dump())

        _check_github_write_access(body.repo_url, x_github_user)

        # Validate
        settings = get_settings()
        if not settings.github_token:
            return JSONResponse(status_code=500, content=IntakeResponse(
                status=500, stage=stage, error="GITHUB_TOKEN not configured on Central API",
            ).model_dump())

        github = GitHubService(token=settings.github_token)
        result = await run_validation(github, body.repo_url, body.branch, "intake")

        if not result.passed:
            return JSONResponse(status_code=422, content=IntakeResponse(
                status=422, stage=stage, error="Validation failed",
                validation=result.model_dump(),
            ).model_dump())

        # Advance workflow (fire-and-forget)
        _advance_workflow(
            project_slug, wf_uuid, owner, stage="intake",
            commit_sha=result.commit_sha, settings=settings,
        )
        logger.info("intake: submitted for %s", project_slug)

        epic_key = wd.get("epic_key", "")
        if epic_key and settings.jira_url:
            from .jira import notify_reviewers_bg
            asyncio.get_event_loop().run_in_executor(
                None, notify_reviewers_bg,
                epic_key, "rhdp-content-review", settings,
            )

        return JSONResponse(status_code=201, content=IntakeResponse(
            status=201,
        ).model_dump())

    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content=IntakeResponse(
            status=e.status_code, stage=stage, error=e.detail,
        ).model_dump())
    except Exception as e:
        logger.exception("intake: unexpected error for %s", project_slug)
        return JSONResponse(status_code=500, content=IntakeResponse(
            status=500, stage=stage, error=f"Internal server error: {e}",
        ).model_dump())


@router.post("/development/{project_slug}", response_model=DevelopmentResponse)
async def submit_development(
    project_slug: str,
    body: DevelopmentRequest,
    auth: tuple[str, int] = Depends(_require_auth),
    x_github_user: str | None = Header(None, alias="X-GitHub-User"),
):
    """Validate development artifacts, run semantic drift check, then advance workflow.

    Returns a unified response shape for all outcomes:
    201 — validation passed, no drift, workflow advanced
    422 — validation failed OR design drift detected
    409 — workflow not in development stage
    404 — no workflow found
    500 — unexpected server error
    """
    from fastapi.responses import JSONResponse
    from ..services.github import GitHubService
    from ..services.validation.runner import run_validation
    from ..services.drift import check_drift_semantic, check_drift_infra, drift_cache_evict

    owner, groups = auth
    _require_group(groups, GROUP_BITS["rhdp-developers"], "rhdp-developers")
    stage = None

    try:
        try:
            wd = _get_workflow_data(project_slug)
        except HTTPException as e:
            if e.status_code == 404:
                return JSONResponse(status_code=404, content=DevelopmentResponse(
                    status=404, error=f"No workflow found for {project_slug}",
                ).model_dump())
            raise

        wf_uuid = wd.get("workflow_id", "")
        if not wf_uuid:
            return JSONResponse(status_code=404, content=DevelopmentResponse(
                status=404, error=f"No workflow found for {project_slug}",
            ).model_dump())

        current = _get_workflow_state(wf_uuid).get("stage", "unknown")
        stage = current
        if current != "development":
            return JSONResponse(status_code=409, content=DevelopmentResponse(
                status=409, stage=current,
                error=f"Workflow is in '{current}' stage. Development requires 'development'.",
            ).model_dump())

        _check_github_write_access(body.repo_url, x_github_user)

        settings = get_settings()
        if not settings.github_token:
            return JSONResponse(status_code=500, content=DevelopmentResponse(
                status=500, stage=stage, error="GITHUB_TOKEN not configured on Central API",
            ).model_dump())

        github = GitHubService(token=settings.github_token)
        result = await run_validation(github, body.repo_url, body.branch, "development")

        if not result.passed:
            return JSONResponse(status_code=422, content=DevelopmentResponse(
                status=422, stage=stage, error="Validation failed",
                validation=result.model_dump(),
            ).model_dump())

        # Semantic drift check against baselineSha
        baseline_sha = wd.get("baselineSha", "")
        if baseline_sha and settings.ph_internal_ai_api_key:
            drift_result = await check_drift_semantic(
                github, body.repo_url, body.branch, baseline_sha,
                settings.litellm_api_url, settings.ph_internal_ai_api_key,
                slug=project_slug,
            )
            if drift_result.has_drift:
                _patch_workflow_data(wf_uuid, {"hasDrift": True}, settings=settings)
                logger.info("development: drift detected for %s, set hasDrift", project_slug)

                # Build detailed drift message
                detailed_msg = "Design drift detected.\n\nChanges:\n"
                for i, change in enumerate(drift_result.changes[:5], 1):
                    detailed_msg += f"{i}. {change.comparing}: {change.difference}\n"
                if len(drift_result.changes) > 5:
                    detailed_msg += f"\n...and {len(drift_result.changes) - 5} more change(s)"

                return JSONResponse(status_code=422, content=DevelopmentResponse(
                    status=422, stage=stage, error=detailed_msg,
                ).model_dump())
            elif wd.get("hasDrift"):
                _patch_workflow_data(wf_uuid, {"hasDrift": False}, settings=settings)
                logger.info("development: drift cleared for %s", project_slug)

        # Infra drift check (informational — does not block)
        agnosticv_urls = wd.get("agnosticvUrls", [])
        if agnosticv_urls:
            try:
                import yaml
                spec_raw = await github.get_file_content(body.repo_url, "publishing-house/spec.yaml", body.branch)
                spec_env = {}
                if spec_raw:
                    spec_data = yaml.safe_load(spec_raw) or {}
                    spec_env = spec_data.get("spec", {}).get("environment", {})
                current_sha = await github.get_head_sha(body.repo_url, body.branch) or ""
                infra_result = await check_drift_infra(github, agnosticv_urls, spec_env, current_sha)
                if infra_result.changes:
                    logger.info("development: %d infra sizing mismatch(es) for %s", len(infra_result.changes), project_slug)
            except Exception as e:
                logger.warning("development: infra drift check failed for %s: %s", project_slug, e)

        _advance_workflow(
            project_slug, wf_uuid, owner, stage="development",
            commit_sha=result.commit_sha, settings=settings,
        )
        logger.info("development: submitted for %s", project_slug)

        return JSONResponse(status_code=201, content=DevelopmentResponse(
            status=201,
        ).model_dump())

    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content=DevelopmentResponse(
            status=e.status_code, stage=stage, error=e.detail,
        ).model_dump())
    except Exception as e:
        logger.exception("development: unexpected error for %s", project_slug)
        return JSONResponse(status_code=500, content=DevelopmentResponse(
            status=500, stage=stage, error=f"Internal server error: {e}",
        ).model_dump())


@router.post("/testing/{project_slug}", response_model=TestingResponse)
async def submit_testing(
    project_slug: str,
    body: TestingRequest,
    auth: tuple[str, int] = Depends(_require_auth),
):
    """Validate testing artifacts, run semantic drift check, then advance workflow.

    Returns a unified response shape for all outcomes:
    201 — validation passed, no drift, workflow advanced
    422 — validation failed OR design drift detected
    409 — workflow not in testing stage
    404 — no workflow found
    500 — unexpected server error
    """
    from fastapi.responses import JSONResponse
    from ..services.github import GitHubService
    from ..services.validation.runner import run_validation
    from ..services.drift import check_drift_semantic, check_drift_infra, drift_cache_evict

    owner, groups = auth
    allowed = GROUP_BITS["rhdp-operations"] | GROUP_BITS["rhdp-administrators"]
    _require_group(groups, allowed, "rhdp-operations or rhdp-administrators")
    stage = None

    try:
        try:
            wd = _get_workflow_data(project_slug)
        except HTTPException as e:
            if e.status_code == 404:
                return JSONResponse(status_code=404, content=TestingResponse(
                    status=404, error=f"No workflow found for {project_slug}",
                ).model_dump())
            raise

        wf_uuid = wd.get("workflow_id", "")
        if not wf_uuid:
            return JSONResponse(status_code=404, content=TestingResponse(
                status=404, error=f"No workflow found for {project_slug}",
            ).model_dump())

        current = _get_workflow_state(wf_uuid).get("stage", "unknown")
        stage = current
        if current != "testing":
            return JSONResponse(status_code=409, content=TestingResponse(
                status=409, stage=current,
                error=f"Workflow is in '{current}' stage. Testing requires 'testing'.",
            ).model_dump())

        settings = get_settings()
        if not settings.github_token:
            return JSONResponse(status_code=500, content=TestingResponse(
                status=500, stage=stage, error="GITHUB_TOKEN not configured on Central API",
            ).model_dump())

        github = GitHubService(token=settings.github_token)
        result = await run_validation(github, body.repo_url, body.branch, "testing")

        if not result.passed:
            return JSONResponse(status_code=422, content=TestingResponse(
                status=422, stage=stage, error="Validation failed",
                validation=result.model_dump(),
            ).model_dump())

        baseline_sha = wd.get("baselineSha", "")
        if baseline_sha and settings.ph_internal_ai_api_key:
            drift_result = await check_drift_semantic(
                github, body.repo_url, body.branch, baseline_sha,
                settings.litellm_api_url, settings.ph_internal_ai_api_key,
                slug=project_slug,
            )
            if drift_result.has_drift:
                _patch_workflow_data(wf_uuid, {"hasDrift": True}, settings=settings)
                logger.info("testing: drift detected for %s, set hasDrift", project_slug)

                # Build detailed drift message
                detailed_msg = "Design drift detected.\n\nChanges:\n"
                for i, change in enumerate(drift_result.changes[:5], 1):
                    detailed_msg += f"{i}. {change.comparing}: {change.difference}\n"
                if len(drift_result.changes) > 5:
                    detailed_msg += f"\n...and {len(drift_result.changes) - 5} more change(s)"

                return JSONResponse(status_code=422, content=TestingResponse(
                    status=422, stage=stage, error=detailed_msg,
                ).model_dump())
            elif wd.get("hasDrift"):
                _patch_workflow_data(wf_uuid, {"hasDrift": False}, settings=settings)
                logger.info("testing: drift cleared for %s", project_slug)

        # Infra drift check (informational — does not block)
        agnosticv_urls = wd.get("agnosticvUrls", [])
        if agnosticv_urls:
            try:
                import yaml
                spec_raw = await github.get_file_content(body.repo_url, "publishing-house/spec.yaml", body.branch)
                spec_env = {}
                if spec_raw:
                    spec_data = yaml.safe_load(spec_raw) or {}
                    spec_env = spec_data.get("spec", {}).get("environment", {})
                current_sha = await github.get_head_sha(body.repo_url, body.branch) or ""
                infra_result = await check_drift_infra(github, agnosticv_urls, spec_env, current_sha)
                if infra_result.changes:
                    logger.info("testing: %d infra sizing mismatch(es) for %s", len(infra_result.changes), project_slug)
            except Exception as e:
                logger.warning("testing: infra drift check failed for %s: %s", project_slug, e)

        _advance_workflow(
            project_slug, wf_uuid, owner, stage="testing",
            commit_sha=result.commit_sha, settings=settings,
        )
        logger.info("testing: submitted for %s", project_slug)

        return JSONResponse(status_code=201, content=TestingResponse(
            status=201,
        ).model_dump())

    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content=TestingResponse(
            status=e.status_code, stage=stage, error=e.detail,
        ).model_dump())
    except Exception as e:
        logger.exception("testing: unexpected error for %s", project_slug)
        return JSONResponse(status_code=500, content=TestingResponse(
            status=500, stage=stage, error=f"Internal server error: {e}",
        ).model_dump())


# ── Review Action Schemas ────────────────────────────────────────────────────

class ApproveRequest(BaseModel):
    commit_sha: str = ""
    notes: list = []


class RejectRequest(BaseModel):
    reasons: list
    reviewer_name: str = ""
    commit_sha: str = ""


class StartRequest(BaseModel):
    repo_url: str
    branch: str = "main"
    project_name: str = ""
    deployment_mode: str = ""
    content_type: str = ""
    tags: list[str] = []
    project_description: str = ""
    audit_trail_sha: str = ""
    sso_user: str = ""
    sso_email: str = ""
    showroom_type: str = ""
    intake_type: str = "new"


def _send_cloud_event(event_type: str, project_slug: str, data: dict):
    """Send a CloudEvent to SonataFlow."""
    settings = get_settings()
    cloud_event = {
        "specversion": "1.0",
        "type": event_type,
        "source": "publishing-house",
        "id": str(uuid.uuid4()),
        "kogitobusinesskey": project_slug,
        "projectid": project_slug,
        "datacontenttype": "application/json",
        "data": data,
    }
    payload = json.dumps(cloud_event).encode()
    req = urllib.request.Request(
        f"{settings.sonataflow_url.rstrip('/')}",
        data=payload,
        headers={"Content-Type": "application/cloudevents+json"},
    )
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=30) as r:
            pass
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        logger.warning("cloud event %s for %s returned %s: %s", event_type, project_slug, e.code, body[:500])
    except Exception as e:
        logger.warning("cloud event %s send error for %s: %s", event_type, project_slug, e)
    logger.info("sent %s for %s", event_type, project_slug)


# ── Content Review ──────────────────────────────────────────────────────────

@router.post("/{slug}/content-review/approve")
async def approve_content_review(
    slug: str,
    body: ApproveRequest,
    auth: tuple[str, int] = Depends(_require_auth),
):
    owner, groups = auth
    _require_group(groups, GROUP_BITS["rhdp-content-review"] | GROUP_BITS["rhdp-administrators"], "rhdp-content-review or rhdp-administrators")

    wd = _get_workflow_data(slug)
    wf_uuid = wd.get("workflow_id", "")
    if not wf_uuid:
        raise HTTPException(status_code=404, detail=f"No workflow found for {slug}")
    _require_stage(wf_uuid, ["content_review"])

    settings = get_settings()
    timestamp = datetime.now(timezone.utc).isoformat()

    # If approval notes provided, add them to workflow
    if body.notes and len(body.notes) > 0:
        query = """
          query GetWorkflow($id: String!) {
            ProcessInstances(where: { id: { equal: $id } }) {
              id
              variables
            }
          }
        """
        graphql_payload = json.dumps({"query": query, "variables": {"id": wf_uuid}}).encode()
        graphql_req = urllib.request.Request(
            f"{settings.sonataflow_graphql_url.rstrip('/')}/graphql",
            data=graphql_payload,
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(graphql_req, context=_SSL_CTX, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            instances = result.get("data", {}).get("ProcessInstances", [])
            if instances:
                variables = instances[0].get("variables", {})
                workflowdata = variables.get("workflowdata", {})
                existing_notes = workflowdata.get("notes", [])
            else:
                existing_notes = []

        approval_notes = [
            {
                "text": note,
                "user": owner,
                "stage": "content_review",
                "timestamp": timestamp,
                "type": "info"
            }
            for note in body.notes if note.strip()
        ]
        if approval_notes:
            updated_notes = existing_notes + approval_notes
            _patch_workflow_data(wf_uuid, {"notes": updated_notes}, settings=settings)

    _send_cloud_event("ph.content-review.complete", slug, {
        "user": owner,
        "stage": "content_review",
        "action": "approved",
        "timestamp": timestamp,
        "commitSha": body.commit_sha,
    })

    epic_key = wd.get("epic_key", "")
    if epic_key and settings.jira_url:
        from .jira import notify_reviewers_bg
        asyncio.get_event_loop().run_in_executor(
            None, notify_reviewers_bg,
            epic_key, "rhdp-infra-review", settings,
        )

    return {"slug": slug, "action": "approved", "stage": "content_review"}


@router.post("/{slug}/content-review/reject")
async def reject_content_review(
    slug: str,
    body: RejectRequest,
    auth: tuple[str, int] = Depends(_require_auth),
):
    owner, groups = auth
    _require_group(groups, GROUP_BITS["rhdp-content-review"] | GROUP_BITS["rhdp-administrators"], "rhdp-content-review or rhdp-administrators")

    wd = _get_workflow_data(slug)
    wf_uuid = wd.get("workflow_id", "")
    if not wf_uuid:
        raise HTTPException(status_code=404, detail=f"No workflow found for {slug}")
    _require_stage(wf_uuid, ["content_review"])

    reasons = [{**r, "id": str(uuid.uuid4()), "resolved": False} for r in body.reasons]
    timestamp = datetime.now(timezone.utc).isoformat()
    reviewer = body.reviewer_name or owner

    # Get FRESH notes via direct GraphQL query (same as add_note)
    settings = get_settings()
    query = """
      query GetWorkflow($id: String!) {
        ProcessInstances(where: { id: { equal: $id } }) {
          id
          variables
        }
      }
    """
    graphql_payload = json.dumps({"query": query, "variables": {"id": wf_uuid}}).encode()
    graphql_req = urllib.request.Request(
        f"{settings.sonataflow_graphql_url.rstrip('/')}/graphql",
        data=graphql_payload,
        headers={"Content-Type": "application/json"},
    )

    with urllib.request.urlopen(graphql_req, context=_SSL_CTX, timeout=30) as resp:
        result = json.loads(resp.read().decode())
        instances = result.get("data", {}).get("ProcessInstances", [])
        if instances:
            variables = instances[0].get("variables", {})
            workflowdata = variables.get("workflowdata", {})
            existing_notes = workflowdata.get("notes", [])
        else:
            existing_notes = []

    rejection_notes = [
        {
            "text": r["text"],
            "user": reviewer,
            "stage": "content_review",
            "timestamp": timestamp,
            "type": "rejection"
        }
        for r in body.reasons
    ]
    updated_notes = existing_notes + rejection_notes
    _patch_workflow_data(wf_uuid, {"notes": updated_notes}, settings=settings)

    # Send CloudEvent to trigger state transition
    _send_cloud_event("ph.content-review.rejected", slug, {
        "user": reviewer,
        "stage": "content_review",
        "action": "rejected",
        "timestamp": timestamp,
        "commitSha": body.commit_sha,
        "reasons": reasons,
    })
    return {"slug": slug, "action": "rejected", "stage": "content_review"}


# ── Infra Review ────────────────────────────────────────────────────────────

@router.post("/{slug}/infra-review/approve")
async def approve_infra_review(
    slug: str,
    body: ApproveRequest,
    auth: tuple[str, int] = Depends(_require_auth),
):
    owner, groups = auth
    _require_group(groups, GROUP_BITS["rhdp-infra-review"] | GROUP_BITS["rhdp-administrators"], "rhdp-infra-review or rhdp-administrators")

    wd = _get_workflow_data(slug)
    wf_uuid = wd.get("workflow_id", "")
    if not wf_uuid:
        raise HTTPException(status_code=404, detail=f"No workflow found for {slug}")
    _require_stage(wf_uuid, ["infra_review"])

    settings = get_settings()
    timestamp = datetime.now(timezone.utc).isoformat()

    # If approval notes provided, add them to workflow
    if body.notes and len(body.notes) > 0:
        query = """
          query GetWorkflow($id: String!) {
            ProcessInstances(where: { id: { equal: $id } }) {
              id
              variables
            }
          }
        """
        graphql_payload = json.dumps({"query": query, "variables": {"id": wf_uuid}}).encode()
        graphql_req = urllib.request.Request(
            f"{settings.sonataflow_graphql_url.rstrip('/')}/graphql",
            data=graphql_payload,
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(graphql_req, context=_SSL_CTX, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            instances = result.get("data", {}).get("ProcessInstances", [])
            if instances:
                variables = instances[0].get("variables", {})
                workflowdata = variables.get("workflowdata", {})
                existing_notes = workflowdata.get("notes", [])
            else:
                existing_notes = []

        approval_notes = [
            {
                "text": note,
                "user": owner,
                "stage": "infra_review",
                "timestamp": timestamp,
                "type": "info"
            }
            for note in body.notes if note.strip()
        ]
        if approval_notes:
            updated_notes = existing_notes + approval_notes
            _patch_workflow_data(wf_uuid, {"notes": updated_notes}, settings=settings)

    _send_cloud_event("ph.infra-review.complete", slug, {
        "user": owner,
        "stage": "infra_review",
        "action": "approved",
        "timestamp": timestamp,
        "commitSha": body.commit_sha,
    })
    return {"slug": slug, "action": "approved", "stage": "infra_review"}


@router.post("/{slug}/infra-review/reject")
async def reject_infra_review(
    slug: str,
    body: RejectRequest,
    auth: tuple[str, int] = Depends(_require_auth),
):
    owner, groups = auth
    _require_group(groups, GROUP_BITS["rhdp-infra-review"] | GROUP_BITS["rhdp-administrators"], "rhdp-infra-review or rhdp-administrators")

    wd = _get_workflow_data(slug)
    wf_uuid = wd.get("workflow_id", "")
    if not wf_uuid:
        raise HTTPException(status_code=404, detail=f"No workflow found for {slug}")
    _require_stage(wf_uuid, ["infra_review"])

    reasons = [{**r, "id": str(uuid.uuid4()), "resolved": False} for r in body.reasons]
    timestamp = datetime.now(timezone.utc).isoformat()
    reviewer = body.reviewer_name or owner

    # Get FRESH notes via direct GraphQL query (same as add_note)
    settings = get_settings()
    query = """
      query GetWorkflow($id: String!) {
        ProcessInstances(where: { id: { equal: $id } }) {
          id
          variables
        }
      }
    """
    graphql_payload = json.dumps({"query": query, "variables": {"id": wf_uuid}}).encode()
    graphql_req = urllib.request.Request(
        f"{settings.sonataflow_graphql_url.rstrip('/')}/graphql",
        data=graphql_payload,
        headers={"Content-Type": "application/json"},
    )

    with urllib.request.urlopen(graphql_req, context=_SSL_CTX, timeout=30) as resp:
        result = json.loads(resp.read().decode())
        instances = result.get("data", {}).get("ProcessInstances", [])
        if instances:
            variables = instances[0].get("variables", {})
            workflowdata = variables.get("workflowdata", {})
            existing_notes = workflowdata.get("notes", [])
        else:
            existing_notes = []

    rejection_notes = [
        {
            "text": r["text"],
            "user": reviewer,
            "stage": "infra_review",
            "timestamp": timestamp,
            "type": "rejection"
        }
        for r in body.reasons
    ]
    updated_notes = existing_notes + rejection_notes
    _patch_workflow_data(wf_uuid, {"notes": updated_notes}, settings=settings)

    # Send CloudEvent to trigger state transition
    _send_cloud_event("ph.infra-review.rejected", slug, {
        "user": reviewer,
        "stage": "infra_review",
        "action": "rejected",
        "timestamp": timestamp,
        "commitSha": body.commit_sha,
        "reasons": reasons,
    })
    return {"slug": slug, "action": "rejected", "stage": "infra_review"}


# ── Add Note ───────────────────────────────────────────────────────────────

class AddNoteRequest(BaseModel):
    text: str


@router.post("/{slug}/notes")
async def add_note(
    slug: str,
    body: AddNoteRequest,
    auth: tuple[str, int] = Depends(_require_auth),
):
    owner, groups = auth
    _require_group(groups, ALL_GROUPS_MASK, "any RHDP group")

    wd = _get_workflow_data(slug)
    wf_uuid = wd.get("workflow_id", "")
    if not wf_uuid:
        raise HTTPException(status_code=404, detail=f"No workflow found for {slug}")

    # Get current stage from workflow
    stage = _get_workflow_state(wf_uuid).get("stage", "unknown")

    # Get current workflow data
    query = """
      query GetWorkflow($id: String!) {
        ProcessInstances(where: { id: { equal: $id } }) {
          id
          variables
        }
      }
    """
    settings = get_settings()
    graphql_payload = json.dumps({"query": query, "variables": {"id": wf_uuid}}).encode()
    graphql_req = urllib.request.Request(
        f"{settings.sonataflow_graphql_url.rstrip('/')}/graphql",
        data=graphql_payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(graphql_req, context=_SSL_CTX, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            instances = result.get("data", {}).get("ProcessInstances", [])
            if not instances:
                raise HTTPException(status_code=404, detail=f"Workflow {wf_uuid} not found")

            variables = instances[0].get("variables", {})
            workflowdata = variables.get("workflowdata", {})
            notes = workflowdata.get("notes", [])

            # Add new note
            new_note = {
                "user": owner,
                "text": body.text,
                "type": "info",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "stage": stage,
            }
            notes.append(new_note)

            # Update workflow data using helper
            _patch_workflow_data(wf_uuid, {"notes": notes}, settings=settings)

    except HTTPException:
        raise
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors="replace")
        logger.warning("Note add failed for %s: %s %s", slug, e.code, body_text[:500])
        raise HTTPException(status_code=502, detail=f"Failed to update workflow: {e.code}")
    except Exception as e:
        logger.warning("Note add failed for %s: %s", slug, e)
        raise HTTPException(status_code=502, detail=f"Failed to update workflow: {e}")

    return {"slug": slug, "action": "note_added"}


# ── Jira CI Ticket Helpers ─────────────────────────────────────────────────


# ── Env Setup ──────────────────────────────────────────────────────────────

class EnvSetupSubmitRequest(BaseModel):
    agnosticv_urls: list[str]
    ci_urls: list[str]


@router.post("/{slug}/env-setup/submit")
async def submit_env_setup(
    slug: str,
    body: EnvSetupSubmitRequest,
    auth: tuple[str, int] = Depends(_require_auth),
):
    owner, groups = auth
    _require_group(groups, GROUP_BITS["rhdp-content-developers"], "rhdp-content-developers")

    wd = _get_workflow_data(slug)
    wf_uuid = wd.get("workflow_id", "")
    if not wf_uuid:
        raise HTTPException(status_code=404, detail=f"No workflow found for {slug}")
    _require_stage(wf_uuid, ["env_setup"])

    # Validate AgnosticV URLs — each must point to a folder with common.yaml and dev.yaml
    settings = get_settings()
    if settings.github_token:
        from ..services.drift import _parse_agnosticv_url
        from ..services.github import GitHubService
        github = GitHubService(token=settings.github_token)
        errors = []
        for url in body.agnosticv_urls:
            parsed = _parse_agnosticv_url(url)
            if not parsed:
                errors.append(f"Invalid AgnosticV URL format: {url}")
                continue
            repo_url, branch, path = parsed
            common = await github.get_file_content(repo_url, f"{path}/common.yaml", branch)
            if not common:
                errors.append(f"common.yaml not found at {path}")
            dev = await github.get_file_content(repo_url, f"{path}/dev.yaml", branch)
            if not dev:
                errors.append(f"dev.yaml not found at {path}")
        if errors:
            raise HTTPException(status_code=422, detail="; ".join(errors))

    _send_cloud_event("ph.env-setup.complete", slug, {
        "user": owner,
        "stage": "env_setup",
        "action": "submitted",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agnosticvUrls": body.agnosticv_urls,
        "ciUrls": body.ci_urls,
    })

    return {"slug": slug, "action": "submitted", "stage": "env_setup"}


# ── Drift Approve ───────────────────────────────────────────────────────────

@router.post("/{slug}/drift/approve")
async def approve_drift(
    slug: str,
    body: ApproveRequest,
    auth: tuple[str, int] = Depends(_require_auth),
):
    owner, groups = auth
    _require_group(groups, GROUP_BITS["rhdp-content-review"] | GROUP_BITS["rhdp-administrators"], "rhdp-content-review or rhdp-administrators")

    settings = get_settings()
    if not settings.github_token:
        raise HTTPException(status_code=500, detail="GITHUB_TOKEN not configured on Central API")

    wd = _get_workflow_data(slug)
    if not wd or not wd.get("workflow_id"):
        raise HTTPException(status_code=404, detail=f"No active workflow found for '{slug}'")

    repo_url = wd.get("repoUrl", "")
    if not repo_url:
        raise HTTPException(status_code=422, detail="Workflow has no repoUrl set")

    from ..services.github import GitHubService
    github = GitHubService(token=settings.github_token)
    head_sha = await github.get_head_sha(repo_url, "main")
    if not head_sha:
        raise HTTPException(status_code=502, detail="Failed to fetch HEAD SHA from GitHub")

    timestamp = datetime.now(timezone.utc).isoformat()

    # If approval notes provided, add them to workflow
    if body.notes and len(body.notes) > 0:
        query = """
          query GetWorkflow($id: String!) {
            ProcessInstances(where: { id: { equal: $id } }) {
              id
              variables
            }
          }
        """
        graphql_payload = json.dumps({"query": query, "variables": {"id": wd["workflow_id"]}}).encode()
        graphql_req = urllib.request.Request(
            f"{settings.sonataflow_graphql_url.rstrip('/')}/graphql",
            data=graphql_payload,
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(graphql_req, context=_SSL_CTX, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            instances = result.get("data", {}).get("ProcessInstances", [])
            if instances:
                variables = instances[0].get("variables", {})
                workflowdata = variables.get("workflowdata", {})
                existing_notes = workflowdata.get("notes", [])
            else:
                existing_notes = []

        approval_notes = [
            {
                "text": note,
                "user": owner,
                "stage": "drift_review",
                "timestamp": timestamp,
                "type": "info"
            }
            for note in body.notes if note.strip()
        ]
        if approval_notes:
            updated_notes = existing_notes + approval_notes
            _patch_workflow_data(wd["workflow_id"], {"notes": updated_notes}, settings=settings)

    from .drift import _get_review_history
    from ..services.drift import drift_cache_evict
    history = _get_review_history(wd["workflow_id"], settings=settings)
    history.append({
        "stage": "DriftReview",
        "action": "approved",
        "timestamp": timestamp,
        "user": owner,
        "commitSha": head_sha,
    })

    _patch_workflow_data(
        wd["workflow_id"],
        {"hasDrift": False, "baselineSha": head_sha, "reviewHistory": history},
        settings=settings,
    )
    drift_cache_evict(slug)
    logger.info("drift approved for %s by %s — baselineSha=%s", slug, owner, head_sha[:8])

    return {"slug": slug, "baselineSha": head_sha, "cleared": True}


# ── Start Workflow ──────────────────────────────────────────────────────────

@router.post("/{slug}")
async def start_workflow(
    slug: str,
    body: StartRequest,
    auth: tuple[str, int] = Depends(_require_auth),
):
    owner, groups = auth
    _require_group(groups, GROUP_BITS["rhdp-developers"], "rhdp-developers")

    settings = get_settings()
    business_key = body.project_name or slug
    wd = {
        "projectId": business_key,
        "repoUrl": body.repo_url,
        "projectName": business_key,
        "ssoUser": body.sso_user or owner,
        "ssoEmail": body.sso_email or (owner if "@" in owner else ""),
    }
    if body.deployment_mode:
        wd["deploymentMode"] = body.deployment_mode
    if body.content_type:
        wd["contentType"] = body.content_type
    if body.tags:
        wd["tags"] = body.tags
    if body.project_description:
        wd["projectDescription"] = body.project_description
    if body.audit_trail_sha:
        wd["auditTrailSha"] = body.audit_trail_sha
    if body.showroom_type:
        wd["showroomType"] = body.showroom_type
    wd["intakeType"] = body.intake_type
    start_payload = wd

    url = f"{settings.sonataflow_url.rstrip('/')}/publishinghouseworkflow?businessKey={urllib.parse.quote(business_key)}"

    async def _fire_sonataflow():
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(start_payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            await asyncio.to_thread(
                urllib.request.urlopen, req, context=_SSL_CTX, timeout=60
            )
            logger.info("workflow started for %s by %s", business_key, owner)
        except Exception as e:
            logger.error("workflow start failed for %s: %s", business_key, e)

    asyncio.create_task(_fire_sonataflow())
    return {"slug": business_key, "workflow_id": "", "started": True}


# ── Project Deletion ─────────────────────────────────────────────────────────


@router.delete("/{project_slug}", response_model=DeleteProjectResponse)
async def delete_project(
    project_slug: str,
    delete_repo: bool = False,
    auth: tuple[str, int] = Depends(_require_auth),
):
    """Delete a project and clean up all associated resources.

    Requires rhdp-administrators group. Best-effort: each step
    runs independently. Failures are reported but don't block subsequent steps.
    """
    owner, groups = auth
    _require_group(groups, GROUP_BITS["rhdp-administrators"], "rhdp-administrators")
    from ..services.litellm import LiteLLMService

    settings = get_settings()
    result = DeleteProjectResponse(slug=project_slug)

    # 1. Get workflow data — find ALL instances, prefer ACTIVE for epic_key
    epic_key = ""
    all_ids = []
    active_ids = []
    try:
        graphql_query = {
            "query": """
                query GetAllInstances($bk: String!) {
                    ProcessInstances(where: { businessKey: { equal: $bk } }) {
                        id state variables
                    }
                }
            """,
            "variables": {"bk": project_slug}
        }
        req = urllib.request.Request(
            f"{settings.sonataflow_graphql_url.rstrip('/')}/graphql",
            data=json.dumps(graphql_query).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=10) as r:
            gql_result = json.loads(r.read().decode())
        for inst in gql_result.get("data", {}).get("ProcessInstances", []):
            all_ids.append(inst["id"])
            if inst.get("state") == "ACTIVE":
                active_ids.append(inst["id"])
            wd = (inst.get("variables") or {}).get("workflowdata") or {}
            key = wd.get("epic_key", "")
            if key:
                epic_key = key
    except Exception as e:
        result.errors.append(f"Workflow query failed: {e}")

    # 2. Abort ALL active SonataFlow workflow instances
    for wf_id in active_ids:
        try:
            req = urllib.request.Request(
                f"{settings.sonataflow_url.rstrip('/')}/management/processes/publishinghouseworkflow/instances/{wf_id}",
                method="DELETE",
            )
            with urllib.request.urlopen(req, context=_SSL_CTX, timeout=10):
                pass
            result.workflow_aborted = True
            logger.info("delete: aborted workflow %s for %s", wf_id, project_slug)
        except Exception as e:
            result.errors.append(f"Workflow abort failed ({wf_id}): {e}")
            logger.warning("delete: workflow abort failed for %s/%s: %s", project_slug, wf_id, e)

    # 2a. Purge workflow and data-index DB rows
    if all_ids and settings.sonataflow_db_password:
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=settings.sonataflow_db_host,
                port=settings.sonataflow_db_port,
                dbname=settings.sonataflow_db_name,
                user=settings.sonataflow_db_user,
                password=settings.sonataflow_db_password,
            )
            try:
                with conn.cursor() as cur:
                    ids_tuple = tuple(all_ids)

                    cur.execute(
                        'SET search_path TO "publishing-house-workflow"'
                    )
                    cur.execute(
                        "DELETE FROM correlation_instances "
                        "WHERE correlated_id IN %s", (ids_tuple,)
                    )
                    cur.execute(
                        "DELETE FROM business_key_mapping "
                        "WHERE business_key = %s", (project_slug,)
                    )
                    cur.execute(
                        "DELETE FROM process_instances WHERE id IN %s",
                        (ids_tuple,),
                    )

                    cur.execute(
                        'SET search_path TO "sonataflow-platform-data-index-service"'
                    )
                    cur.execute(
                        "DELETE FROM nodes "
                        "WHERE process_instance_id IN %s", (ids_tuple,)
                    )
                    cur.execute(
                        "DELETE FROM processes_addons "
                        "WHERE process_id IN %s", (ids_tuple,)
                    )
                    cur.execute(
                        "DELETE FROM processes_roles "
                        "WHERE process_id IN %s", (ids_tuple,)
                    )
                    cur.execute(
                        "DELETE FROM processes WHERE id IN %s",
                        (ids_tuple,),
                    )
                conn.commit()
            finally:
                conn.close()
            result.db_cleaned = True
            logger.info("delete: purged %d instance(s) from DB for %s", len(all_ids), project_slug)
        except Exception as e:
            result.errors.append(f"DB cleanup failed: {e}")
            logger.warning("delete: DB cleanup failed for %s: %s", project_slug, e)

    # 2b. Delete catalog location and entity from RHDH
    if settings.rhdh_service_token:
        try:
            catalog_base = f"{settings.rhdh_internal_url.rstrip('/')}/api/catalog"
            catalog_headers = {
                "Authorization": f"Bearer {settings.rhdh_service_token}",
                "Accept": "application/json",
            }
            entity_url = f"{catalog_base}/entities/by-name/component/default/{project_slug}"
            req = urllib.request.Request(entity_url, headers=catalog_headers)
            with urllib.request.urlopen(req, context=_SSL_CTX, timeout=10) as r:
                entity = json.loads(r.read().decode())

            location_ref = entity.get("metadata", {}).get("annotations", {}).get(
                "backstage.io/managed-by-location", ""
            )
            match = re.match(r"url:(.+)", location_ref)
            if match:
                target_url = match.group(1)
                req = urllib.request.Request(f"{catalog_base}/locations", headers=catalog_headers)
                with urllib.request.urlopen(req, context=_SSL_CTX, timeout=10) as r:
                    locations = json.loads(r.read().decode())
                for loc in locations:
                    loc_target = (loc.get("data") or {}).get("target", "") or loc.get("target", "")
                    if loc_target == target_url:
                        loc_id = loc.get("data", {}).get("id") or loc.get("id")
                        req = urllib.request.Request(
                            f"{catalog_base}/locations/{loc_id}",
                            method="DELETE",
                            headers=catalog_headers,
                        )
                        urllib.request.urlopen(req, context=_SSL_CTX, timeout=10)
                        logger.info("delete: removed catalog location for %s", project_slug)
                        break

            entity_uid = entity.get("metadata", {}).get("uid", "")
            if entity_uid:
                req = urllib.request.Request(
                    f"{catalog_base}/entities/by-uid/{entity_uid}",
                    method="DELETE",
                    headers=catalog_headers,
                )
                urllib.request.urlopen(req, context=_SSL_CTX, timeout=10)
                logger.info("delete: removed catalog entity %s", project_slug)

            result.catalog_cleaned = True
        except Exception as e:
            result.errors.append(f"Catalog cleanup failed: {e}")
            logger.warning("delete: catalog cleanup failed for %s: %s", project_slug, e)

    # 3. Delete LiteLLM keys
    try:
        litellm = LiteLLMService(settings.litellm_api_url, settings.litellm_master_key)
        key_hashes = await litellm.find_keys_for_project(project_slug)
        deleted = 0
        for kh in key_hashes:
            if await litellm.delete_key(kh):
                deleted += 1
        result.litellm_keys_deleted = deleted
        logger.info("delete: removed %d LiteLLM keys for %s", deleted, project_slug)
    except Exception as e:
        result.errors.append(f"LiteLLM key cleanup failed: {e}")
        logger.warning("delete: LiteLLM cleanup failed for %s: %s", project_slug, e)

    # 4. Archive Jira epic and children
    if epic_key:
        try:
            from .jira import _jira_headers
            headers = _jira_headers(settings)
            keys_to_archive = [epic_key]

            # Find child issues (POST endpoint — GET /search is 410 Gone)
            try:
                search_url = f"{settings.jira_url}/rest/api/3/search/jql"
                search_body = json.dumps({"jql": f"parent={epic_key}", "fields": ["key"]}).encode()
                req = urllib.request.Request(search_url, data=search_body, headers=headers, method="POST")
                with urllib.request.urlopen(req, context=_SSL_CTX, timeout=10) as r:
                    children = json.loads(r.read().decode())
                    for issue in children.get("issues", []):
                        keys_to_archive.append(issue["key"])
            except Exception as e:
                logger.warning("delete: failed to query children for %s: %s", epic_key, e)

            archive_url = f"{settings.jira_url}/rest/api/3/issue/archive"
            req = urllib.request.Request(
                archive_url,
                data=json.dumps({"issueIdsOrKeys": keys_to_archive}).encode(),
                headers=headers,
                method="PUT",
            )
            with urllib.request.urlopen(req, context=_SSL_CTX, timeout=10):
                pass
            result.jira_archived = True
            logger.info("delete: archived Jira issues %s for %s", keys_to_archive, project_slug)
        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else ""
            if e.code == 400 and "No valid issue" in body:
                result.jira_archived = True
                logger.info("delete: Jira issues already archived for %s", project_slug)
            else:
                result.errors.append(f"Jira archive failed: {e} — {body}")
                logger.warning("delete: Jira archive failed for %s: %s — %s", project_slug, e, body)
        except Exception as e:
            result.errors.append(f"Jira archive failed: {e}")
            logger.warning("delete: Jira archive failed for %s: %s", project_slug, e)

    # 5. Delete GitHub repo (optional)
    if delete_repo and settings.github_token:
        try:
            req = urllib.request.Request(
                f"https://api.github.com/repos/rhpds/{project_slug}",
                headers={
                    "Authorization": f"Bearer {settings.github_token}",
                    "Accept": "application/vnd.github+json",
                },
                method="DELETE",
            )
            with urllib.request.urlopen(req, context=_SSL_CTX, timeout=15):
                pass
            result.repo_deleted = True
            logger.info("delete: deleted repo rhpds/%s", project_slug)
        except Exception as e:
            result.errors.append(f"Repo deletion failed: {e}")
            logger.warning("delete: repo deletion failed for %s: %s", project_slug, e)

    logger.info("delete: cleanup complete for %s — %s", project_slug, result.model_dump())
    return result
