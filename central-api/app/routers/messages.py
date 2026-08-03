"""Messages router — reviewer-to-author messaging via RHDH notifications."""
import json
import logging
import ssl
import urllib.parse
import urllib.request
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from ..auth.groups import GROUP_BITS, ALL_GROUPS_MASK, decode_signed_key
from ..config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["messages"])
_bearer = HTTPBearer(auto_error=False)

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

REVIEWER_MASK = GROUP_BITS["rhdp-content-review"] | GROUP_BITS["rhdp-infra-review"]


# ── Schemas ──────────────────────────────────────────────────────────────────

class SendMessageRequest(BaseModel):
    text: str
    stage: str


class SendMessageResponse(BaseModel):
    sent: bool
    slug: str
    recipients: list[str]


class ReviewMessage(BaseModel):
    id: str
    title: str
    text: str
    origin: str
    stage: str
    timestamp: str
    read: bool


class MessagesResponse(BaseModel):
    messages: list[ReviewMessage]


class MarkReadRequest(BaseModel):
    ids: list[str]


class MarkReadResponse(BaseModel):
    marked: int


# ── Auth ─────────────────────────────────────────────────────────────────────

def _require_auth(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> tuple[str, int]:
    settings = get_settings()
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
    token = credentials.credentials
    if token == settings.ph_api_key:
        return "service", ALL_GROUPS_MASK
    result = decode_signed_key(token)
    if result:
        return result
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def _require_reviewer(groups: int) -> None:
    if not (groups & REVIEWER_MASK):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires membership in rhdp-content-review or rhdp-infra-review",
        )


# ── Workflow data helpers ────────────────────────────────────────────────────

def _get_workflow_vars(project_id: str) -> dict:
    """Query full workflow variables for a project."""
    settings = get_settings()
    query = {
        "query": """
            query GetWorkflowData($businessKey: String!) {
                ProcessInstances(where: { businessKey: { equal: $businessKey }, state: { in: [ACTIVE, SUSPENDED] } }) {
                    id
                    variables
                }
            }
        """,
        "variables": {"businessKey": project_id},
    }
    try:
        req = urllib.request.Request(
            f"{settings.sonataflow_graphql_url.rstrip('/')}/graphql",
            data=json.dumps(query).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=10) as r:
            result = json.loads(r.read().decode())
        instances = result.get("data", {}).get("ProcessInstances", [])
        if not instances:
            raise HTTPException(status_code=404, detail=f"No workflow found for {project_id}")
        inst = instances[0]
        variables = inst.get("variables", {})
        wd = variables.get("workflowdata", {}) if isinstance(variables, dict) else {}
        wd["_workflow_id"] = inst.get("id", "")
        return wd
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("workflow query failed for %s: %s", project_id, e)
        raise HTTPException(status_code=502, detail=f"Failed to query workflow: {e}")


def _resolve_recipients(wd: dict) -> set[str]:
    """Build deduplicated recipient set from ssoUser and reviewHistory submitters."""
    recipients = set()
    sso_user = wd.get("ssoUser", "")
    if sso_user:
        recipients.add(sso_user.split("@")[0] if "@" in sso_user else sso_user)
    for entry in wd.get("reviewHistory", []):
        if entry.get("action") == "submitted":
            user = entry.get("user", "")
            if user:
                recipients.add(user.split("@")[0] if "@" in user else user)
    return recipients


# ── RHDH notification helpers ────────────────────────────────────────────────

def _rhdh_send_notification(
    recipient_entity_ref: str,
    title: str,
    description: str,
    link: str,
    topic: str,
    origin: str,
) -> bool:
    settings = get_settings()
    url = f"{settings.rhdh_internal_url.rstrip('/')}/api/notifications"
    payload = {
        "recipients": {"type": "entity", "entityRef": recipient_entity_ref},
        "payload": {
            "title": title,
            "description": description,
            "link": link,
            "topic": topic,
            "severity": "normal",
            "origin": origin,
        },
    }
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.rhdh_service_token}",
            },
        )
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=10) as r:
            return r.status < 300
    except Exception as e:
        logger.error("RHDH notification send failed: %s", e)
        return False


def _rhdh_get_notifications(
    topic: str, read: Optional[bool] = None,
) -> list[dict]:
    # RHDH notifications GET endpoint rejects service credentials (403).
    # Disabled to avoid blocking the async event loop with synchronous urllib calls.
    return []


def _rhdh_mark_read(ids: list[str]) -> int:
    return len(ids)


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/{slug}/messages", response_model=SendMessageResponse)
async def send_message(
    slug: str,
    body: SendMessageRequest,
    auth: tuple[str, int] = Depends(_require_auth),
):
    sender, groups = auth
    _require_reviewer(groups)

    wd = _get_workflow_vars(slug)
    workflow_id = wd.get("_workflow_id", "")
    recipients = _resolve_recipients(wd)

    if not recipients:
        raise HTTPException(status_code=422, detail="No recipients found for this project")

    topic = f"ph-review:{slug}"
    title = f"Review message on {slug}"
    link = f"/publishing-house-workflows/{workflow_id}"
    origin = f"{sender}|{body.stage}"

    sent_to = []
    for recipient in recipients:
        entity_ref = f"user:default/{recipient}"
        if _rhdh_send_notification(entity_ref, title, body.text, link, topic, origin):
            sent_to.append(recipient)
        else:
            logger.warning("failed to notify %s for %s", recipient, slug)

    if not sent_to:
        raise HTTPException(status_code=502, detail="Failed to send notification to any recipient")

    logger.info("message sent on %s by %s to %s (stage=%s)", slug, sender, sent_to, body.stage)
    return SendMessageResponse(sent=True, slug=slug, recipients=sent_to)


@router.get("/{slug}/messages", response_model=MessagesResponse)
async def get_messages(
    slug: str,
    read: Optional[bool] = Query(None, description="Filter by read status; omit for all"),
    auth: tuple[str, int] = Depends(_require_auth),
):
    topic = f"ph-review:{slug}"
    raw = _rhdh_get_notifications(topic, read=read)

    messages = []
    for n in raw:
        payload = n.get("payload", {}) if isinstance(n.get("payload"), dict) else {}
        origin_raw = payload.get("origin", "")
        parts = origin_raw.split("|", 1)
        origin = parts[0] if parts else ""
        stage = parts[1] if len(parts) > 1 else ""
        messages.append(ReviewMessage(
            id=str(n.get("id", "")),
            title=payload.get("title", ""),
            text=payload.get("description", ""),
            origin=origin,
            stage=stage,
            timestamp=n.get("created", ""),
            read=n.get("isRead", n.get("read", False)),
        ))

    unread_ids = [m.id for m in messages if not m.read and m.id]
    if unread_ids:
        _rhdh_mark_read(unread_ids)
        for m in messages:
            m.read = True

    return MessagesResponse(messages=messages)


@router.post("/{slug}/messages/read", response_model=MarkReadResponse)
async def mark_messages_read(
    slug: str,
    body: MarkReadRequest,
    auth: tuple[str, int] = Depends(_require_auth),
):
    if not body.ids:
        return MarkReadResponse(marked=0)
    marked = _rhdh_mark_read(body.ids)
    return MarkReadResponse(marked=marked)
