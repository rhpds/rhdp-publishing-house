"""Publishing House projects and auth endpoints — all under /projects."""
import hashlib
import json
import logging
import secrets
import ssl
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from ..auth.oidc import require_oidc_auth
from ..config import get_settings
from ..services.rcars import rcars_overlap_check

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

class IntakeAnswers(BaseModel):
    name: str
    slug: str = ""
    content_type: str = "lab"
    deployment_mode: str = "self_published"
    owner_email: str = ""
    problem_statement: str = ""
    audience_role: str = ""
    learning_objectives: list[str] = []
    modules: list[dict] = []
    ocp_version: str = ""
    topology: str = "shared-cluster"
    duration_hours: float = 0
    epic_key: str = ""


class IntakeResponse(BaseModel):
    epic_key: str
    jira_url: str
    jira_ticket: str            # same as epic_key — explicit field for skill to read
    stage: str                  # new stage after advancing the workflow
    rcars_overlap_pct: float    # AUTO-COMPUTED: RCARS catalog overlap percentage (0-100)
    rcars_top_matches: list     # AUTO-COMPUTED: top 3 RCARS matches [{ci_name, display_name, url}]


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


def _advance_workflow(workflow_id: str, epic_key: str, jira_url: str, settings=None) -> str:
    """Send IntakeCompleteEvent CloudEvent to SonataFlow.
    Uses kogitoprocinstanceid for direct instance routing.
    Returns the new stage name."""
    if not settings:
        settings = get_settings()

    try:
        cloud_event = {
            "specversion": "1.0",
            "type": "ph.intake.complete",
            "source": "claude-skill",
            "id": str(uuid.uuid4()),
            "kogitoprocinstanceid": workflow_id,
            "datacontenttype": "application/json",
            "data": {
                "epic_key": epic_key,
                "jira_url": jira_url
            }
        }
        req = urllib.request.Request(
            f"{settings.sonataflow_url.rstrip('/')}",
            data=json.dumps(cloud_event).encode(),
            headers={"Content-Type": "application/cloudevents+json"}
        )
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=10) as r:
            pass
        logger.info("sent IntakeCompleteEvent for workflow=%s", workflow_id)
        return "review"
    except Exception as e:
        logger.warning("CloudEvent send failed for workflow %s: %s", workflow_id, e)
        return "intake"


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

@router.get("/{project_id}/workflow-data")
def get_workflow_data(project_id: str):
    """Return workflow data subset (epic_key, jira_url).
    Stage is NOT returned here — use /workflow-state for stage."""
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
            f"{settings.sonataflow_url.rstrip('/')}/graphql",
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
        return {
            "project_id": project_id,
            "workflow_id": inst.get("id", ""),
            "epic_key": wd.get("epic_key", ""),
            "jira_url": wd.get("jira_url", ""),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("workflow-data failed for %s: %s", project_id, e)
        raise HTTPException(status_code=502, detail=f"Failed to query workflow: {e}")


@router.get("/workflow-state/{workflow_id}")
def get_workflow_state(workflow_id: str):
    """Return semantic workflow stage via direct ProcessInstanceById lookup."""
    settings = get_settings()
    try:
        graphql_query = {
            "query": """
                query GetWorkflowById($id: String!) {
                    ProcessInstanceById(id: $id) {
                        id
                        state
                        nodes { name enter exit }
                    }
                }
            """,
            "variables": {"id": workflow_id}
        }
        req = urllib.request.Request(
            f"{settings.sonataflow_url.rstrip('/')}/graphql",
            data=json.dumps(graphql_query).encode(),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=10) as r:
            result = json.loads(r.read().decode())
        inst = result.get("data", {}).get("ProcessInstanceById")
        if inst:
            process_state = inst.get("state", "")

            if process_state == "COMPLETED":
                stage = "published"
            elif process_state == "ERROR":
                stage = "error"
            else:
                stage = "intake"
                for node in inst.get("nodes", []):
                    if node.get("enter") and not node.get("exit"):
                        node_name = node.get("name", "").lower()
                        if node_name == "contentreview":
                            stage = "content_review"
                        elif node_name == "infrareview":
                            stage = "infra_review"
                        elif node_name == "jirasync":
                            stage = "jira_sync"
                        elif "createepic" in node_name:
                            stage = "setup"
                        elif "development" in node_name or "writing" in node_name:
                            stage = "development"
                        elif "ready" in node_name or "final" in node_name:
                            stage = "ready"
                        elif "publish" in node_name:
                            stage = "published"
                        break

            return {
                "stage": stage,
                "workflow_id": workflow_id,
                "source": "sonataflow",
            }
    except Exception as e:
        logger.warning("workflow-state fallback for %s: %s", workflow_id, e)
    return {"stage": "intake", "workflow_id": workflow_id, "source": "fallback"}


def _require_stage(workflow_id: str, allowed: list[str]) -> str:
    """Check the workflow stage and raise 409 if not in allowed list."""
    current = get_workflow_state(workflow_id).get("stage", "unknown")
    if current not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Workflow '{workflow_id}' is in '{current}' stage. "
                   f"This action requires stage: {', '.join(allowed)}.",
        )
    return current


@router.post("/intake/{workflow_id}", response_model=IntakeResponse, status_code=201)
def submit_intake(
    workflow_id: str,
    answers: IntakeAnswers,
    owner: str = Depends(_require_auth),
):
    """After author approves spec — create Jira Epic + Tasks (rhdp_published only),
    advance SonataFlow to next stage, and auto-compute RCARS overlap.
    One atomic call — no back-and-forth."""
    _require_stage(workflow_id, ["intake"])
    settings = get_settings()
    epic_key = answers.epic_key
    jira_url = f"{settings.jira_url}/browse/{epic_key}" if epic_key else ""

    # Auto-compute RCARS overlap
    rcars_products = [answers.name] if answers.name else []
    if answers.content_type:
        rcars_products.append(answers.content_type)
    overlap_result = rcars_overlap_check(
        products=rcars_products,
        audience=answers.audience_role,
        limit=5,
    )
    rcars_overlap_pct = overlap_result.get("overlap_pct", 0.0)
    rcars_top_matches = overlap_result.get("top_matches", [])
    slug = answers.slug or answers.name
    logger.info(
        "intake: RCARS overlap for %s = %.1f%% (%d top matches)",
        slug, rcars_overlap_pct, len(rcars_top_matches)
    )

    new_stage = _advance_workflow(workflow_id, epic_key, jira_url, settings)
    logger.info("intake: workflow advanced to %s for %s", new_stage, slug)

    return IntakeResponse(
        epic_key=epic_key,
        jira_url=jira_url,
        jira_ticket=epic_key,
        stage=new_stage,
        rcars_overlap_pct=rcars_overlap_pct,
        rcars_top_matches=rcars_top_matches,
    )
