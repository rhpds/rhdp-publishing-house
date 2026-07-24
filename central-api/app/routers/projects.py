"""Publishing House projects and auth endpoints — all under /projects."""
import hashlib
import json
import logging
import secrets
import ssl
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from ..auth.oidc import require_oidc_auth
from ..config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["projects"])
_bearer = HTTPBearer(auto_error=False)

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# Simple in-memory key store - one key per user (email)
# Structure: {email: KeyRecord}
keys_db: dict = {}


# ── Auth Schemas ──────────────────────────────────────────────────────────────

class KeyRecord:
    def __init__(self, owner_email: str, label: str, raw_key: str):
        self.id = str(uuid.uuid4())
        self.key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        self.owner_email = owner_email
        self.label = label
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.last_used_at = None
        self.is_active = True

    def masked(self) -> str:
        return f"{self.key_hash[:8]}...{self.key_hash[-8:]}"


class KeyResponse(BaseModel):
    id: str
    label: Optional[str]
    owner_email: str
    created_at: str
    last_used_at: Optional[str]
    masked: str


class KeyCreatedResponse(BaseModel):
    id: str
    raw_key: str   # shown ONCE — never stored
    owner_email: str
    label: Optional[str]


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


class DeleteProjectResponse(BaseModel):
    slug: str
    workflow_aborted: bool = False
    litellm_keys_deleted: int = 0
    jira_archived: bool = False
    repo_deleted: bool = False
    errors: list[str] = []


# ── Auth Helpers ──────────────────────────────────────────────────────────────

def _create_key(email: str, label: str = "API Key") -> tuple:
    """Create/replace key for user. One key per user. Returns (record, raw_key)."""
    raw_key = secrets.token_hex(32)
    rec = KeyRecord(owner_email=email, label=label, raw_key=raw_key)
    keys_db[email] = rec  # Store by email (one key per user)
    return rec, raw_key


def lookup_key(raw_key: str) -> Optional[KeyRecord]:
    """Used by other endpoints to validate a Bearer token."""
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    # Search all users for matching key hash
    for rec in keys_db.values():
        if rec.key_hash == key_hash and rec.is_active:
            rec.last_used_at = datetime.now(timezone.utc).isoformat()
            return rec
    return None


def _require_auth(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> str:
    """Validate PH API key (single key from PH_API_KEY env var or per-user keys)."""
    settings = get_settings()
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
    if credentials.credentials == settings.ph_api_key:
        return "service"
    rec = lookup_key(credentials.credentials)
    if not rec:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return rec.owner_email


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


# ── Auth Endpoints (Portal key management) ────────────────────────────────────

@router.get("/keys", response_model=list[KeyResponse])
def list_keys(email: str = Depends(require_oidc_auth)):
    """List key for the authenticated user (one key per user)."""
    rec = keys_db.get(email)
    if rec and rec.is_active:
        return [KeyResponse(id=rec.id, label=rec.label, owner_email=rec.owner_email,
                            created_at=rec.created_at, last_used_at=rec.last_used_at,
                            masked=rec.masked())]
    return []


@router.post("/keys", response_model=KeyCreatedResponse, status_code=201)
def create_key(email: str = Depends(require_oidc_auth)):
    """Generate/regenerate key for user. One key per user. Auto-generates on first portal login."""
    rec, raw_key = _create_key(email, label="Central API Key")
    logger.info("projects/keys: created key for %s", email)
    return KeyCreatedResponse(id=rec.id, raw_key=raw_key, owner_email=email, label=rec.label)


@router.delete("/keys/{key_id}", status_code=204)
def revoke_key(key_id: str, email: str = Depends(require_oidc_auth)):
    """Revoke user's key."""
    rec = keys_db.get(email)
    if not rec or rec.id != key_id:
        raise HTTPException(status_code=404, detail="Key not found")
    rec.is_active = False


@router.post("/keys/{key_id}/refresh", response_model=KeyCreatedResponse)
def refresh_key(key_id: str, email: str = Depends(require_oidc_auth)):
    """Rotate user's key."""
    old = keys_db.get(email)
    if not old or old.id != key_id:
        raise HTTPException(status_code=404, detail="Key not found")
    rec, raw_key = _create_key(email, label=old.label or "Central API Key")
    return KeyCreatedResponse(id=rec.id, raw_key=raw_key, owner_email=email, label=rec.label)


# ── Project Endpoints ─────────────────────────────────────────────────────────

def _get_workflow_data(project_id: str):
    """Internal: query workflow data — no auth check."""
    settings = get_settings()
    try:
        graphql_query = {
            "query": """
                query GetWorkflowData($businessKey: String!) {
                    ProcessInstances(where: { businessKey: { equal: $businessKey } }) {
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
        }
        if rejection:
            result["rejection"] = rejection
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("workflow-data failed for %s: %s", project_id, e)
        raise HTTPException(status_code=502, detail=f"Failed to query workflow: {e}")


@router.get("/{project_id}/workflow-data")
def get_workflow_data(project_id: str, _caller: str = Depends(_require_auth)):
    """Return workflow data subset (epic_key, jira_url)."""
    return _get_workflow_data(project_id)


_STATE_MAP = {
    "intake": "intake",
    "contentreview": "content_review",
    "contentreviewdecision": "content_review",
    "infrareview": "infra_review",
    "infrareviewdecision": "infra_review",
    "jirasync": "jira_sync",
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
def get_workflow_state(workflow_id: str, _caller: str = Depends(_require_auth)):
    """Return semantic workflow stage by process instance UUID."""
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


@router.post("/intake/{project_slug}", response_model=IntakeResponse)
async def submit_intake(
    project_slug: str,
    body: IntakeRequest,
    owner: str = Depends(_require_auth),
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
    owner: str = Depends(_require_auth),
):
    """Validate development artifacts, then advance workflow past development.

    Returns a unified response shape for all outcomes:
    201 — validation passed, workflow advanced
    422 — validation failed
    409 — workflow not in development stage
    404 — no workflow found
    500 — unexpected server error
    """
    from fastapi.responses import JSONResponse
    from ..services.github import GitHubService
    from ..services.validation.runner import run_validation

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


# ── Project Deletion ─────────────────────────────────────────────────────────

def _require_service_auth(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> str:
    """Only accept the master PH_API_KEY — not per-user keys."""
    settings = get_settings()
    if not credentials or credentials.credentials != settings.ph_api_key:
        raise HTTPException(status_code=403, detail="This endpoint requires the service API key")
    return "service"


@router.delete("/{project_slug}", response_model=DeleteProjectResponse)
async def delete_project(
    project_slug: str,
    delete_repo: bool = False,
    owner: str = Depends(_require_service_auth),
):
    """Delete a project and clean up all associated resources.

    Requires the master service key (PH_API_KEY). Best-effort: each step
    runs independently. Failures are reported but don't block subsequent steps.
    """
    from ..services.litellm import LiteLLMService

    settings = get_settings()
    result = DeleteProjectResponse(slug=project_slug)

    # 1. Get workflow data — find ALL instances, prefer ACTIVE for epic_key
    epic_key = ""
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
            if inst.get("state") == "ACTIVE":
                active_ids.append(inst["id"])
            if not epic_key:
                wd = (inst.get("variables") or {}).get("workflowdata") or {}
                epic_key = wd.get("epic_key", "")
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

            # Find child issues
            try:
                jql = urllib.parse.quote(f"parent={epic_key}")
                search_url = f"{settings.jira_url}/rest/api/3/search?jql={jql}&fields=key"
                req = urllib.request.Request(search_url, headers=headers)
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
