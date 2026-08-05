"""Jira system endpoints — epic creation, updates, task management, and sync."""
import asyncio
import base64
import json
import logging
import re
import ssl
import urllib.parse
import urllib.request

import yaml
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..config import get_settings, Settings
from ..services.github import GitHubService
from .projects import _require_auth

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jira", tags=["Jira"])

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


class CreateEpicRequest(BaseModel):
    project_name: str
    content_type: str = ""
    deployment_mode: str = ""
    project_description: str = ""


class CreateEpicResponse(BaseModel):
    epic_key: str
    jira_url: str



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
    _caller: str = Depends(_require_auth),
    settings: Settings = Depends(get_settings),
):
    """Create a minimal Jira epic for a new publishing house project.
    Called by SonataFlow during the CreateEpic state — no description yet,
    just a placeholder that gets updated after intake."""
    if not settings.jira_url:
        raise HTTPException(status_code=503, detail="Jira not configured")

    labels = ["publishing-house"]
    if body.content_type:
        labels.append(body.content_type)

    fields: dict = {
        "project": {"key": settings.jira_project_key},
        "summary": f"[PH] {body.project_name}",
        "issuetype": {"name": "Epic"},
        "labels": labels,
        "assignee": None,
    }
    if body.project_description:
        fields["description"] = {
            "type": "doc",
            "version": 1,
            "content": [
                {"type": "paragraph", "content": [
                    {"type": "text", "text": body.project_description},
                ]},
            ],
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
        "labels": ["publishing-house", "ph:intake"],
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



class SyncRequest(BaseModel):
    repo_url: str
    epic_key: str
    agnosticv_url: str = ""
    ci_url: str = ""


class SyncResponse(BaseModel):
    epic_key: str
    tasks_created: int = 0
    tasks_updated: int = 0
    tasks_closed: int = 0
    intake_closed: bool = False


FIXED_TASKS = [
    {"id": "write-automation", "summary": "[PH] Write Automation"},
    {"id": "write-health-check", "summary": "[PH] Write Health Check"},
    {"id": "write-e2e-tests", "summary": "[PH] Write E2E Tests"},
]

SPEC_PATH = "publishing-house/spec.yaml"
DESIGN_PATH = "publishing-house/spec/design.md"
MODULES_DIR = "publishing-house/spec/modules"


def _extract_brief_overview(content: str) -> str:
    """Extract the Brief Overview section from a module outline file."""
    m = re.search(r'## Brief Overview\s*\n(.*?)(?=\n##|\Z)', content, re.DOTALL)
    return m.group(1).strip() if m else ""


def _get_epic_tasks(epic_key: str, settings: Settings) -> list[dict]:
    """Fetch all tasks under an epic with key, summary, labels, and status."""
    headers = _jira_headers(settings)
    jql = (
        f"project = {settings.jira_project_key} AND issuetype = Task "
        f"AND parent = {epic_key}"
    )
    req = urllib.request.Request(
        f"{settings.jira_url}/rest/api/3/search/jql",
        data=json.dumps({
            "jql": jql,
            "fields": ["key", "summary", "labels", "status"],
            "maxResults": 100,
        }).encode(),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=15) as r:
            issues = json.loads(r.read().decode()).get("issues", [])
    except Exception as e:
        logger.warning("jira sync: failed to fetch tasks under %s: %s", epic_key, e)
        return []

    result = []
    for issue in issues:
        fields = issue.get("fields", {})
        result.append({
            "key": issue["key"],
            "summary": fields.get("summary", ""),
            "labels": fields.get("labels", []),
            "status": fields.get("status", {}).get("name", ""),
        })
    return result


def _transition_to_done(task_key: str, settings: Settings) -> bool:
    """Transition a Jira task to Done."""
    headers = _jira_headers(settings)
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
            logger.info("jira sync: transitioned %s to Done", task_key)
            return True
    except Exception as e:
        logger.warning("jira sync: failed to transition %s to Done: %s", task_key, e)
        return False


def _update_task_fields(task_key: str, summary: str, description: str, settings: Settings) -> bool:
    """Update a Jira task's summary and description."""
    headers = _jira_headers(settings)
    fields: dict = {"summary": summary}
    if description:
        fields["description"] = {
            "type": "doc",
            "version": 1,
            "content": [
                {"type": "paragraph", "content": [
                    {"type": "text", "text": description[:30000]},
                ]},
            ],
        }
    req = urllib.request.Request(
        f"{settings.jira_url}/rest/api/3/issue/{task_key}",
        data=json.dumps({"fields": fields}).encode(),
        headers=headers,
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=10):
            logger.info("jira sync: updated task %s", task_key)
            return True
    except Exception as e:
        logger.warning("jira sync: failed to update %s: %s", task_key, e)
        return False


def _create_task(
    epic_key: str, summary: str, description: str, ph_label: str, settings: Settings,
) -> bool:
    """Create a Jira task under an epic with a ph:{id} label."""
    headers = _jira_headers(settings)
    fields: dict = {
        "project": {"key": settings.jira_project_key},
        "summary": summary,
        "issuetype": {"name": "Task"},
        "parent": {"key": epic_key},
        "labels": ["publishing-house", ph_label],
        "assignee": None,
    }
    if description:
        fields["description"] = {
            "type": "doc",
            "version": 1,
            "content": [
                {"type": "paragraph", "content": [
                    {"type": "text", "text": description[:30000]},
                ]},
            ],
        }
    req = urllib.request.Request(
        f"{settings.jira_url}/rest/api/3/issue",
        data=json.dumps({"fields": fields}).encode(),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=10):
            return True
    except Exception as e:
        logger.warning("jira sync: task creation failed for '%s': %s", summary, e)
        return False


@router.post("/sync", response_model=SyncResponse)
async def sync_jira_tasks(
    body: SyncRequest,
    _caller: str = Depends(_require_auth),
    settings: Settings = Depends(get_settings),
):
    """Accept a sync request and run the heavy Jira work in the background."""
    if not settings.jira_url:
        raise HTTPException(status_code=503, detail="Jira not configured")
    if not settings.github_token:
        raise HTTPException(status_code=503, detail="GitHub token not configured")

    asyncio.get_event_loop().run_in_executor(
        None, _sync_jira_tasks_bg, body.repo_url, body.epic_key, settings,
        body.agnosticv_url, body.ci_url,
    )
    logger.info("jira sync: accepted for epic %s — running in background", body.epic_key)
    return SyncResponse(epic_key=body.epic_key)


def _sync_jira_tasks_bg(repo_url: str, epic_key: str, settings: Settings,
                        agnosticv_url: str = "", ci_url: str = ""):
    """Background thread: sync Jira tasks from spec.yaml, design.md, and module outlines."""
    try:
        gh = GitHubService(token=settings.github_token)
        loop = asyncio.new_event_loop()

        spec_content = loop.run_until_complete(gh.get_file_content(repo_url, SPEC_PATH))
        if not spec_content:
            logger.warning("jira sync bg: spec.yaml not found in %s", repo_url)
            return
        spec_data = yaml.safe_load(spec_content) or {}
        project = spec_data.get("project", {})
        spec_section = spec_data.get("spec", {})

        design_content = loop.run_until_complete(gh.get_file_content(repo_url, DESIGN_PATH))

        module_files = loop.run_until_complete(gh.list_directory(repo_url, MODULES_DIR))
        module_briefs: dict[str, str] = {}
        for fname in sorted(module_files):
            if not fname.endswith(".md"):
                continue
            m = re.match(r"module-(\d+)", fname)
            if not m:
                continue
            content = loop.run_until_complete(gh.get_file_content(repo_url, f"{MODULES_DIR}/{fname}"))
            if content:
                module_briefs[int(m.group(1))] = _extract_brief_overview(content)
        loop.close()

        headers = _jira_headers(settings)
        title = spec_section.get("title", "") or project.get("slug", "")
        content_type = project.get("content_type", "lab")
        slug = project.get("slug", "")
        epic_summary = f"[PH] {title} — {content_type} ({slug})"

        req = urllib.request.Request(
            f"{settings.jira_url}/rest/api/3/issue/{epic_key}",
            data=json.dumps({"fields": {"summary": epic_summary}}).encode(),
            headers=headers,
            method="PUT",
        )
        try:
            with urllib.request.urlopen(req, context=_SSL_CTX, timeout=15):
                logger.info("jira sync bg: updated epic %s summary", epic_key)
        except Exception as e:
            logger.warning("jira sync bg: epic summary update failed for %s: %s", epic_key, e)

        if design_content:
            desc_content = [
                {"type": "paragraph", "content": [
                    {"type": "text", "text": design_content[:30000]}
                ]},
            ]
            if agnosticv_url or ci_url:
                links_parts = []
                if agnosticv_url:
                    links_parts.append({"type": "text", "text": "AgnosticV: "})
                    links_parts.append({"type": "text", "text": agnosticv_url, "marks": [{"type": "link", "attrs": {"href": agnosticv_url}}]})
                if agnosticv_url and ci_url:
                    links_parts.append({"type": "text", "text": " | "})
                if ci_url:
                    links_parts.append({"type": "text", "text": "CI: "})
                    links_parts.append({"type": "text", "text": ci_url, "marks": [{"type": "link", "attrs": {"href": ci_url}}]})
                desc_content.insert(0, {"type": "paragraph", "content": links_parts})
            desc_adf = {
                "type": "doc",
                "version": 1,
                "content": desc_content,
            }
            req = urllib.request.Request(
                f"{settings.jira_url}/rest/api/3/issue/{epic_key}",
                data=json.dumps({"fields": {"description": desc_adf}}).encode(),
                headers=headers,
                method="PUT",
            )
            try:
                with urllib.request.urlopen(req, context=_SSL_CTX, timeout=15):
                    logger.info("jira sync bg: updated epic %s description", epic_key)
            except Exception as e:
                logger.warning("jira sync bg: epic description update failed: %s", e)

        existing_tasks = _get_epic_tasks(epic_key, settings)
        label_to_task: dict[str, dict] = {}
        for task in existing_tasks:
            for label in task["labels"]:
                if label.startswith("ph:"):
                    label_to_task[label] = task
                    break

        intake_task = label_to_task.get("ph:intake")
        if intake_task and intake_task["status"].lower() != "done":
            _transition_to_done(intake_task["key"], settings)

        modules = spec_section.get("modules", [])
        desired: dict[str, dict] = {}
        for i, mod in enumerate(modules, 1):
            mod_id = mod.get("id", f"module-{i:02d}")
            mod_title = mod.get("title", f"Module {i}")
            brief = module_briefs.get(i, "")
            desired[f"ph:{mod_id}"] = {
                "summary": f"[PH] Write Module {i}: {mod_title}",
                "description": brief,
            }

        for ft in FIXED_TASKS:
            desired[f"ph:{ft['id']}"] = {
                "summary": ft["summary"],
                "description": "",
            }

        tasks_created = 0
        tasks_updated = 0
        tasks_closed = 0

        for ph_label, want in desired.items():
            existing = label_to_task.get(ph_label)
            if not existing:
                if _create_task(epic_key, want["summary"], want["description"], ph_label, settings):
                    tasks_created += 1
            elif ph_label.startswith("ph:module-") and existing["summary"] != want["summary"]:
                if _update_task_fields(existing["key"], want["summary"], want["description"], settings):
                    tasks_updated += 1

        for ph_label, task in label_to_task.items():
            if (
                ph_label.startswith("ph:module-")
                and ph_label not in desired
                and task["status"].lower() != "done"
            ):
                if _transition_to_done(task["key"], settings):
                    tasks_closed += 1

        logger.info(
            "jira sync bg: epic %s — created=%d updated=%d closed=%d",
            epic_key, tasks_created, tasks_updated, tasks_closed,
        )
    except Exception as e:
        logger.error("jira sync bg: failed for epic %s: %s", epic_key, e, exc_info=True)


