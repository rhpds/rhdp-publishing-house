"""Jira system endpoints — epic creation, updates, task management, and sync."""
import asyncio
import base64
import json
import logging
import ssl
import urllib.parse
import urllib.request

import yaml
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..config import get_settings, Settings
from ..services.github import GitHubService

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
             "text": f"{body.name} — {body.content_type} ({body.slug or body.name}). Full spec in spec.yaml in the project repo."}]},
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
        "summary": f"[PH] {body.name} — {body.content_type} ({body.slug or body.name})",
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


class SyncRequest(BaseModel):
    repo_url: str
    epic_key: str


class SyncResponse(BaseModel):
    epic_key: str
    tasks_created: int
    intake_closed: bool


@router.post("/sync", response_model=SyncResponse)
def sync_jira_tasks(
    body: SyncRequest,
    settings: Settings = Depends(get_settings),
):
    """Read jira.yaml from project repo, update epic, close intake, create tasks.
    Called by SonataFlow JiraSync state after reviews complete."""
    if not settings.jira_url:
        raise HTTPException(status_code=503, detail="Jira not configured")
    if not settings.github_token:
        raise HTTPException(status_code=503, detail="GitHub token not configured")

    gh = GitHubService(token=settings.github_token)
    jira_yaml_content = asyncio.get_event_loop().run_until_complete(
        gh.get_file_content(body.repo_url, "publishing-house/jira.yaml")
    )
    if not jira_yaml_content:
        raise HTTPException(status_code=404, detail="publishing-house/jira.yaml not found in repo")

    jira_data = yaml.safe_load(jira_yaml_content)
    if not jira_data:
        raise HTTPException(status_code=422, detail="jira.yaml is empty")

    headers = _jira_headers(settings)
    epic_info = jira_data.get("epic", {})

    if epic_info.get("summary"):
        req = urllib.request.Request(
            f"{settings.jira_url}/rest/api/3/issue/{body.epic_key}",
            data=json.dumps({"fields": {"summary": epic_info["summary"]}}).encode(),
            headers=headers,
            method="PUT",
        )
        try:
            with urllib.request.urlopen(req, context=_SSL_CTX, timeout=15):
                logger.info("jira sync: updated epic %s summary", body.epic_key)
        except Exception as e:
            logger.warning("jira sync: epic summary update failed for %s: %s", body.epic_key, e)

    desc_source = epic_info.get("description_source", "")
    if desc_source:
        desc_content = asyncio.get_event_loop().run_until_complete(
            gh.get_file_content(body.repo_url, desc_source)
        )
        if desc_content:
            desc_adf = {
                "type": "doc",
                "version": 1,
                "content": [
                    {"type": "paragraph", "content": [
                        {"type": "text", "text": desc_content[:30000]}
                    ]},
                ],
            }
            req = urllib.request.Request(
                f"{settings.jira_url}/rest/api/3/issue/{body.epic_key}",
                data=json.dumps({"fields": {"description": desc_adf}}).encode(),
                headers=headers,
                method="PUT",
            )
            try:
                with urllib.request.urlopen(req, context=_SSL_CTX, timeout=15):
                    logger.info("jira sync: updated epic %s description from %s", body.epic_key, desc_source)
            except Exception as e:
                logger.warning("jira sync: epic description update failed: %s", e)

    tasks = jira_data.get("tasks", [])
    tasks_created = 0
    intake_closed = False

    for task in tasks:
        summary = task.get("summary", "")
        task_status = task.get("status", "open")

        if task_status == "done":
            intake_closed = _close_task_by_summary(body.epic_key, summary, settings)
            continue

        try:
            task_req = urllib.request.Request(
                f"{settings.jira_url}/rest/api/3/issue",
                data=json.dumps({"fields": {
                    "project": {"key": settings.jira_project_key},
                    "summary": summary,
                    "issuetype": {"name": "Task"},
                    "parent": {"key": body.epic_key},
                    "labels": ["publishing-house"],
                    "assignee": None,
                }}).encode(),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(task_req, context=_SSL_CTX, timeout=10):
                tasks_created += 1
        except Exception as e:
            logger.warning("jira sync: task creation failed for '%s': %s", summary, e)

    logger.info("jira sync: epic %s — %d tasks created, intake closed: %s",
                body.epic_key, tasks_created, intake_closed)
    return SyncResponse(epic_key=body.epic_key, tasks_created=tasks_created, intake_closed=intake_closed)


def _close_task_by_summary(epic_key: str, summary: str, settings: Settings) -> bool:
    """Find a task under an epic by summary and transition it to Done."""
    headers = _jira_headers(settings)
    jql = (
        f'project = {settings.jira_project_key} AND issuetype = Task '
        f'AND parent = {epic_key} AND summary ~ "{summary}"'
    )
    search_url = f"{settings.jira_url}/rest/api/3/search?jql={urllib.parse.quote(jql)}&fields=key"
    req = urllib.request.Request(search_url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=10) as r:
            issues = json.loads(r.read().decode()).get("issues", [])
    except Exception as e:
        logger.warning("jira sync: failed to search for task '%s' under %s: %s", summary, epic_key, e)
        return False

    if not issues:
        logger.info("jira sync: no task matching '%s' found under epic %s", summary, epic_key)
        return False

    task_key = issues[0]["key"]
    trans_url = f"{settings.jira_url}/rest/api/3/issue/{task_key}/transitions"
    req = urllib.request.Request(trans_url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=10) as r:
            transitions = json.loads(r.read().decode()).get("transitions", [])
    except Exception as e:
        logger.warning("jira sync: failed to get transitions for %s: %s", task_key, e)
        return False

    done_id = None
    for t in transitions:
        if t["name"].lower() in ("done", "closed", "resolve", "resolved"):
            done_id = t["id"]
            break
    if not done_id:
        logger.warning("jira sync: no Done transition found for %s", task_key)
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
            logger.info("jira sync: closed task %s", task_key)
            return True
    except Exception as e:
        logger.warning("jira sync: failed to transition %s to Done: %s", task_key, e)
        return False


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
