"""Jira system endpoints — epic creation, updates, and task management."""
import base64
import json
import logging
import ssl
import urllib.parse
import urllib.request

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..config import get_settings, Settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jira", tags=["Jira"])

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


class CreateEpicRequest(BaseModel):
    project_name: str
    project_type: str = ""
    deployment_mode: str = ""


class CreateEpicResponse(BaseModel):
    epic_key: str
    jira_url: str


class UpdateEpicRequest(BaseModel):
    epic_key: str
    name: str = ""
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
    rcars_overlap_pct: float = 0.0
    rcars_top_matches: list = []


class UpdateEpicResponse(BaseModel):
    epic_key: str
    jira_url: str
    tasks_created: int


def _jira_headers(settings: Settings) -> dict:
    creds = base64.b64encode(f"{settings.jira_email}:{settings.jira_api_token}".encode()).decode()
    return {
        "Authorization": f"Basic {creds}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


@router.post("/epic", response_model=CreateEpicResponse, status_code=201)
def create_epic(
    body: CreateEpicRequest,
    settings: Settings = Depends(get_settings),
):
    """Create a minimal Jira epic for a new publishing house project.
    Called by SonataFlow during the CreateEpic state — no description yet,
    just a placeholder that gets updated after intake."""
    if not settings.jira_url:
        raise HTTPException(status_code=503, detail="Jira not configured")

    labels = ["publishing-house"]
    if body.project_type:
        labels.append(body.project_type)

    fields = {
        "project": {"key": settings.jira_project_key},
        "summary": f"[PH] {body.project_name}",
        "issuetype": {"name": "Epic"},
        "labels": labels,
        "assignee": None,
    }

    req = urllib.request.Request(
        f"{settings.jira_url}/rest/api/3/issue",
        data=json.dumps({"fields": fields}).encode(),
        headers=_jira_headers(settings),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=15) as r:
            epic_key = json.loads(r.read().decode())["key"]
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Jira epic creation failed: {e}")

    # Create an Intake child task so the board shows intake is pending
    intake_fields = {
        "project": {"key": settings.jira_project_key},
        "summary": "[PH] Intake",
        "issuetype": {"name": "Task"},
        "parent": {"key": epic_key},
        "labels": ["publishing-house"],
        "assignee": None,
        "description": {
            "type": "doc",
            "version": 1,
            "content": [
                {"type": "paragraph", "content": [{"type": "text",
                 "text": "Project intake is in progress. The project author is defining the content specification — "
                         "learning objectives, module structure, target audience, and deployment requirements. "
                         "This task will be closed automatically when the intake questionnaire is completed and approved."}]},
            ],
        },
    }
    intake_req = urllib.request.Request(
        f"{settings.jira_url}/rest/api/3/issue",
        data=json.dumps({"fields": intake_fields}).encode(),
        headers=_jira_headers(settings),
        method="POST",
    )
    try:
        with urllib.request.urlopen(intake_req, context=_SSL_CTX, timeout=10):
            logger.info("jira: created Intake task under epic %s", epic_key)
    except Exception as e:
        logger.warning("jira: Intake task creation failed for epic %s: %s", epic_key, e)

    jira_url = f"{settings.jira_url}/browse/{epic_key}"
    logger.info("jira: created epic %s for project %s", epic_key, body.project_name)
    return CreateEpicResponse(epic_key=epic_key, jira_url=jira_url)


@router.put("/epic/{epic_key}", response_model=UpdateEpicResponse)
def update_epic(
    epic_key: str,
    body: UpdateEpicRequest,
    settings: Settings = Depends(get_settings),
):
    """Update an existing Jira epic with full description and create child tasks.
    Called by central API during intake submission after spec is approved."""
    if not settings.jira_url:
        raise HTTPException(status_code=503, detail="Jira not configured")

    headers = _jira_headers(settings)

    description_adf = {
        "type": "doc",
        "version": 1,
        "content": [
            {"type": "paragraph", "content": [{"type": "text",
             "text": f"{body.name} — {body.content_type} ({body.deployment_mode}). Full spec in spec.yaml in the project repo."}]},
            {"type": "heading", "attrs": {"level": 3}, "content": [{"type": "text", "text": "Problem Statement"}]},
            {"type": "paragraph", "content": [{"type": "text", "text": body.problem_statement or "—"}]},
            {"type": "heading", "attrs": {"level": 3}, "content": [{"type": "text", "text": "Learning Objectives"}]},
            {"type": "bulletList", "content": [
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": obj}]}]}
                for obj in (body.learning_objectives or ["—"])
            ]},
            {"type": "heading", "attrs": {"level": 3}, "content": [{"type": "text", "text": "RCARS Overlap"}]},
            {"type": "paragraph", "content": [{"type": "text",
             "text": f"Overlap with existing catalog: {body.rcars_overlap_pct:.1f}%. "
                     + (f"Top match: {body.rcars_top_matches[0]['display_name']}" if body.rcars_top_matches else "No close matches found.")}]},
        ],
    }

    update_fields = {
        "summary": f"[PH] {body.name} — {body.content_type} ({body.deployment_mode})",
        "description": description_adf,
    }
    req = urllib.request.Request(
        f"{settings.jira_url}/rest/api/3/issue/{epic_key}",
        data=json.dumps({"fields": update_fields}).encode(),
        headers=headers,
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=15) as r:
            pass
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Jira epic update failed: {e}")

    tasks = [f"Write Module {i+1}: {m.get('title', '')}" for i, m in enumerate(body.modules)]
    tasks += ["Write Automation", "Write Health Check", "Write E2E Tests"]
    tasks_created = 0
    for t in tasks:
        try:
            task_req = urllib.request.Request(
                f"{settings.jira_url}/rest/api/3/issue",
                data=json.dumps({"fields": {
                    "project": {"key": settings.jira_project_key},
                    "summary": f"[PH] {t}",
                    "issuetype": {"name": "Task"},
                    "parent": {"key": epic_key},
                    "labels": ["publishing-house"],
                    "assignee": None,
                }}).encode(),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(task_req, context=_SSL_CTX, timeout=10):
                tasks_created += 1
        except Exception as e:
            logger.warning("task creation failed for '%s': %s", t, e)

    jira_url = f"{settings.jira_url}/browse/{epic_key}"
    logger.info("jira: updated epic %s — %d tasks created", epic_key, tasks_created)
    return UpdateEpicResponse(epic_key=epic_key, jira_url=jira_url, tasks_created=tasks_created)


def close_intake_task(epic_key: str, settings: Settings) -> bool:
    """Find the [PH] Intake task under an epic and transition it to Done."""
    headers = _jira_headers(settings)

    jql = (
        f'project = {settings.jira_project_key} AND issuetype = Task '
        f'AND parent = {epic_key} AND summary ~ "[PH] Intake"'
    )
    search_url = f"{settings.jira_url}/rest/api/3/search?jql={urllib.parse.quote(jql)}&fields=key"
    req = urllib.request.Request(search_url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=10) as r:
            issues = json.loads(r.read().decode()).get("issues", [])
    except Exception as e:
        logger.warning("jira: failed to search for Intake task under %s: %s", epic_key, e)
        return False

    if not issues:
        logger.info("jira: no Intake task found under epic %s", epic_key)
        return False

    task_key = issues[0]["key"]

    # Get available transitions and find Done
    trans_url = f"{settings.jira_url}/rest/api/3/issue/{task_key}/transitions"
    req = urllib.request.Request(trans_url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=10) as r:
            transitions = json.loads(r.read().decode()).get("transitions", [])
    except Exception as e:
        logger.warning("jira: failed to get transitions for %s: %s", task_key, e)
        return False

    done_id = None
    for t in transitions:
        if t["name"].lower() in ("done", "closed", "resolve", "resolved"):
            done_id = t["id"]
            break
    if not done_id:
        logger.warning("jira: no Done/Closed transition found for %s (available: %s)",
                        task_key, [t["name"] for t in transitions])
        return False

    req = urllib.request.Request(
        trans_url,
        data=json.dumps({
            "transition": {"id": done_id},
            "fields": {"resolution": {"name": "Done"}},
        }).encode(),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=10):
            logger.info("jira: closed Intake task %s (transition=%s)", task_key, done_id)
            return True
    except Exception as e:
        logger.warning("jira: failed to transition %s to Done: %s", task_key, e)
        return False
