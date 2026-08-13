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

from ..auth.groups import GROUP_BITS, lookup_group_members
from ..config import get_settings, Settings
from ..services.github import GitHubService
from .projects import _require_auth, _require_group

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
    showroom_type: str = ""
    sso_email: str = ""


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

    assignee = None
    if body.sso_email:
        jira_user = _lookup_jira_account_id(body.sso_email, settings)
        if jira_user and jira_user["accountId"]:
            assignee = {"accountId": jira_user["accountId"]}

    fields: dict = {
        "project": {"key": settings.jira_project_key},
        "summary": f"[PH] {body.project_name}",
        "issuetype": {"name": "Epic"},
        "labels": labels,
        "assignee": assignee,
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
        STORY_POINTS_FIELD: float(POINTS["intake"]),
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

    testing_fields = {
        "project": {"key": settings.jira_project_key},
        "summary": "[PH] Testing",
        "issuetype": {"name": "Task"},
        "parent": {"key": epic_key},
        "labels": ["publishing-house", "ph:testing"],
        "assignee": None,
        STORY_POINTS_FIELD: float(POINTS["testing"]),
        "description": {
            "type": "doc",
            "version": 1,
            "content": [
                {"type": "paragraph", "content": [{"type": "text",
                 "text": "Testing phase tracker. Testers post comments here during testing. "
                         "This task will be closed automatically when testing is marked complete."}]},
            ],
        },
    }
    try:
        req = urllib.request.Request(
            f"{settings.jira_url}/rest/api/3/issue",
            data=json.dumps({"fields": testing_fields}).encode(),
            headers=_jira_headers(settings),
            method="POST",
        )
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=10):
            logger.info("jira: created Testing task under epic %s", epic_key)
    except Exception as e:
        logger.warning("jira: Testing task creation failed for epic %s: %s", epic_key, e)

    if body.showroom_type != "zero_touch":
        dev_ci_fields = {
            "project": {"key": settings.jira_project_key},
            "summary": "[PH] Development CI",
            "issuetype": {"name": "Task"},
            "parent": {"key": epic_key},
            "labels": ["publishing-house", "ph:dev-ci"],
            "assignee": None,
            STORY_POINTS_FIELD: float(POINTS["dev-ci"]),
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {"type": "paragraph", "content": [{"type": "text",
                     "text": "Development CI tracker for catalog item setup. "
                             "Updated with AgnosticV and CI URLs during env setup, "
                             "then closed automatically."}]},
                ],
            },
        }
        try:
            req = urllib.request.Request(
                f"{settings.jira_url}/rest/api/3/issue",
                data=json.dumps({"fields": dev_ci_fields}).encode(),
                headers=_jira_headers(settings),
                method="POST",
            )
            with urllib.request.urlopen(req, context=_SSL_CTX, timeout=10):
                logger.info("jira: created Dev CI task under epic %s", epic_key)
        except Exception as e:
            logger.warning("jira: Dev CI task creation failed for epic %s: %s", epic_key, e)

    for ft in FIXED_TASKS:
        _create_task(
            epic_key, ft["summary"], "", f"ph:{ft['id']}", settings,
            points=POINTS.get(ft["id"]),
        )

    jira_url = f"{settings.jira_url}/browse/{epic_key}"
    logger.info("jira: created epic %s for project %s", epic_key, body.project_name)
    return CreateEpicResponse(epic_key=epic_key, jira_url=jira_url)



def _lookup_jira_account_id(email: str, settings: Settings) -> dict | None:
    """Look up a Jira user by email. Returns {accountId, displayName} or None."""
    headers = _jira_headers(settings)
    search_url = f"{settings.jira_url}/rest/api/3/user/search?query={urllib.parse.quote(email)}"
    req = urllib.request.Request(search_url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=10) as r:
            users = json.loads(r.read().decode())
    except Exception as e:
        logger.warning("jira: user search failed for %s: %s", email, e)
        return None

    if not users:
        return None
    return {
        "accountId": users[0].get("accountId", ""),
        "displayName": users[0].get("displayName", email),
    }


_GROUP_LABELS = {
    "rhdp-content-review": "Content Review",
    "rhdp-infra-review": "Infra Review",
}


def notify_reviewers_bg(epic_key: str, group_name: str, settings: Settings) -> None:
    """Background: look up group members, resolve Jira IDs, post a comment with @mentions."""
    review_label = _GROUP_LABELS.get(group_name, group_name)
    try:
        emails = lookup_group_members(group_name)
        if not emails:
            logger.warning("notify_reviewers: no members found in group %s", group_name)
            return

        mention_nodes = []
        for email in emails:
            jira_user = _lookup_jira_account_id(email, settings)
            if not jira_user or not jira_user["accountId"]:
                continue
            if mention_nodes:
                mention_nodes.append({"type": "text", "text": " "})
            mention_nodes.append({
                "type": "mention",
                "attrs": {
                    "id": jira_user["accountId"],
                    "text": f"@{jira_user['displayName']}",
                    "accessLevel": "",
                },
            })

        if not mention_nodes:
            logger.warning("notify_reviewers: no Jira users resolved for group %s", group_name)
            return

        content = [
            {"type": "paragraph", "content": mention_nodes + [
                {"type": "text", "text": f" this project is ready for {review_label}."},
            ]},
        ]

        headers = _jira_headers(settings)
        comment_body = {"body": {"type": "doc", "version": 1, "content": content}}
        req = urllib.request.Request(
            f"{settings.jira_url}/rest/api/3/issue/{epic_key}/comment",
            data=json.dumps(comment_body).encode(),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=10):
            logger.info("notify_reviewers: posted %s comment on %s", review_label, epic_key)
    except Exception as e:
        logger.error("notify_reviewers: failed for %s: %s", epic_key, e, exc_info=True)


class SyncRequest(BaseModel):
    repo_url: str
    epic_key: str
    slug: str = ""
    status: str = ""


class SyncResponse(BaseModel):
    epic_key: str
    tasks_created: int = 0
    tasks_updated: int = 0
    tasks_closed: int = 0
    intake_closed: bool = False


STORY_POINTS_FIELD = "customfield_10028"
POINTS = {
    "intake": 8,
    "module": 13,
    "dev-ci": 13,
    "write-automation": 5,
    "write-health-check": 3,
    "write-e2e-tests": 5,
    "testing": 3,
}

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


def _update_task_fields(task_key: str, summary: str, description: str, settings: Settings, points: float | None = None) -> bool:
    """Update a Jira task's summary and description."""
    headers = _jira_headers(settings)
    fields: dict = {"summary": summary}
    if points is not None:
        fields[STORY_POINTS_FIELD] = float(points)
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


def _find_task_by_label(epic_key: str, ph_label: str, settings: Settings) -> dict | None:
    """Find a single task under an epic by its ph:* label. Returns {key, assignee} or None."""
    headers = _jira_headers(settings)
    jql = (
        f"project = {settings.jira_project_key} AND issuetype = Task "
        f"AND parent = {epic_key} AND labels = \"{ph_label}\""
    )
    req = urllib.request.Request(
        f"{settings.jira_url}/rest/api/3/search/jql",
        data=json.dumps({
            "jql": jql,
            "fields": ["key", "assignee", "status"],
            "maxResults": 1,
        }).encode(),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=15) as r:
            issues = json.loads(r.read().decode()).get("issues", [])
    except Exception as e:
        logger.warning("jira: failed to find task %s under %s: %s", ph_label, epic_key, e)
        return None

    if not issues:
        return None
    issue = issues[0]
    fields = issue.get("fields", {})
    assignee = fields.get("assignee")
    return {
        "key": issue["key"],
        "assignee": assignee.get("emailAddress", "") if assignee else "",
        "status": fields.get("status", {}).get("name", ""),
    }


def _assign_ticket(ticket_key: str, email: str, settings: Settings) -> bool:
    """Assign a Jira ticket to a user by email lookup."""
    headers = _jira_headers(settings)
    search_url = f"{settings.jira_url}/rest/api/3/user/search?query={urllib.parse.quote(email)}"
    req = urllib.request.Request(search_url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=10) as r:
            users = json.loads(r.read().decode())
    except Exception as e:
        logger.warning("jira: user search failed for %s: %s", email, e)
        return False

    if not users:
        logger.warning("jira: no Jira user found for email %s", email)
        return False

    account_id = users[0].get("accountId", "")
    if not account_id:
        return False

    req = urllib.request.Request(
        f"{settings.jira_url}/rest/api/3/issue/{ticket_key}",
        data=json.dumps({"fields": {"assignee": {"accountId": account_id}}}).encode(),
        headers=headers,
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=10):
            logger.info("jira: assigned %s to %s", ticket_key, email)
            return True
    except Exception as e:
        logger.warning("jira: failed to assign %s to %s: %s", ticket_key, email, e)
        return False


def _add_comment(ticket_key: str, text: str, author_name: str, settings: Settings) -> bool:
    """Post a comment to a Jira issue."""
    headers = _jira_headers(settings)
    body_text = f"[{author_name}] {text}" if author_name else text
    comment_body = {
        "body": {
            "type": "doc",
            "version": 1,
            "content": [
                {"type": "paragraph", "content": [
                    {"type": "text", "text": body_text[:30000]},
                ]},
            ],
        },
    }
    req = urllib.request.Request(
        f"{settings.jira_url}/rest/api/3/issue/{ticket_key}/comment",
        data=json.dumps(comment_body).encode(),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=10):
            logger.info("jira: added comment to %s", ticket_key)
            return True
    except Exception as e:
        logger.warning("jira: failed to add comment to %s: %s", ticket_key, e)
        return False


def _get_comments(ticket_key: str, settings: Settings) -> list[dict]:
    """Fetch comments from a Jira issue."""
    headers = _jira_headers(settings)
    req = urllib.request.Request(
        f"{settings.jira_url}/rest/api/3/issue/{ticket_key}/comment?orderBy=created",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=15) as r:
            data = json.loads(r.read().decode())
    except Exception as e:
        logger.warning("jira: failed to get comments for %s: %s", ticket_key, e)
        return []

    result = []
    for c in data.get("comments", []):
        author_data = c.get("author", {})
        body_content = c.get("body", {}).get("content", [])
        text_parts = []
        for block in body_content:
            for inline in block.get("content", []):
                if inline.get("type") == "text":
                    text_parts.append(inline.get("text", ""))
        result.append({
            "author": author_data.get("displayName", author_data.get("emailAddress", "")),
            "text": " ".join(text_parts),
            "created": c.get("created", ""),
        })
    return result


def _create_task(
    epic_key: str, summary: str, description: str, ph_label: str, settings: Settings,
    points: float | None = None,
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
    if points is not None:
        fields[STORY_POINTS_FIELD] = float(points)
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
        None, _sync_jira_tasks_bg, body.repo_url, body.epic_key, settings, body.status, body.slug,
    )
    logger.info("jira sync: accepted for epic %s (status=%s) — running in background", body.epic_key, body.status)
    return SyncResponse(epic_key=body.epic_key)


def _sync_jira_tasks_bg(repo_url: str, epic_key: str, settings: Settings, status: str = "", slug: str = ""):
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
        slug = slug or project.get("slug", "")
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
            desc_adf = {
                "type": "doc",
                "version": 1,
                "content": [
                    {"type": "paragraph", "content": [
                        {"type": "text", "text": design_content[:30000]}
                    ]},
                ],
            }
            update_fields: dict = {"description": desc_adf}
            req = urllib.request.Request(
                f"{settings.jira_url}/rest/api/3/issue/{epic_key}",
                data=json.dumps({"fields": update_fields}).encode(),
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

        tasks_created = 0
        tasks_updated = 0
        tasks_closed = 0

        modules = spec_section.get("modules", [])
        desired: dict[str, dict] = {}
        for i, mod in enumerate(modules, 1):
            mod_id = mod.get("id", f"module-{i:02d}")
            mod_title = mod.get("title", f"Module {i}")
            brief = module_briefs.get(i, "")
            desired[f"ph:{mod_id}"] = {
                "summary": f"[PH] Write Module {i}: {mod_title}",
                "description": brief,
                "points": POINTS["module"],
            }

        if status == "IntakeComplete":
            intake_task = label_to_task.get("ph:intake")
            if intake_task and intake_task["status"].lower() != "done":
                _transition_to_done(intake_task["key"], settings)
                logger.info("jira sync bg: closed Intake task %s", intake_task["key"])
            for ph_label, want in desired.items():
                if not label_to_task.get(ph_label):
                    if _create_task(epic_key, want["summary"], want["description"], ph_label, settings, points=want.get("points")):
                        tasks_created += 1

        if status == "EnvSetupComplete":
            dev_ci_task = label_to_task.get("ph:dev-ci")
            if dev_ci_task and dev_ci_task["status"].lower() != "done":
                if slug:
                    try:
                        from .projects import _get_workflow_data
                        wd = _get_workflow_data(slug)
                        agnosticv_url = wd.get("agnosticvUrl", "")
                        ci_url = wd.get("ciUrl", "")
                        if agnosticv_url or ci_url:
                            desc_lines = []
                            if agnosticv_url:
                                desc_lines.append(f"AgnosticV Catalog Item: {agnosticv_url}")
                            if ci_url:
                                desc_lines.append(f"CI Catalog Item: {ci_url}")
                            _update_task_fields(dev_ci_task["key"], dev_ci_task["summary"], "\n".join(desc_lines), settings)
                    except Exception as e:
                        logger.warning("jira sync bg: failed to update Dev CI description: %s", e)
                _transition_to_done(dev_ci_task["key"], settings)
                logger.info("jira sync bg: closed Dev CI task %s", dev_ci_task["key"])

        if status in ("DevelopmentComplete", "TestingComplete"):
            newly_created_labels = []
            for ph_label, want in desired.items():
                existing = label_to_task.get(ph_label)
                if not existing:
                    if _create_task(epic_key, want["summary"], want["description"], ph_label, settings, points=want.get("points")):
                        tasks_created += 1
                        newly_created_labels.append(ph_label)
                elif existing["summary"] != want["summary"]:
                    if _update_task_fields(existing["key"], want["summary"], want["description"], settings):
                        tasks_updated += 1

            if newly_created_labels:
                existing_tasks = _get_epic_tasks(epic_key, settings)
                label_to_task = {}
                for task in existing_tasks:
                    for label in task["labels"]:
                        if label.startswith("ph:"):
                            label_to_task[label] = task
                            break

            for ph_label, task in label_to_task.items():
                if (
                    ph_label.startswith("ph:module-")
                    and ph_label not in desired
                    and task["status"].lower() != "done"
                ):
                    _update_task_fields(task["key"], f"{task['summary']} [Removed]", "", settings, points=0)
                    if _transition_to_done(task["key"], settings):
                        tasks_closed += 1

            for mod in modules:
                mod_id = mod.get("id", "")
                if mod.get("status") == "complete" and mod_id:
                    task = label_to_task.get(f"ph:{mod_id}")
                    if task and task["status"].lower() != "done":
                        if _transition_to_done(task["key"], settings):
                            tasks_closed += 1

        logger.info(
            "jira sync bg: epic %s — created=%d updated=%d closed=%d",
            epic_key, tasks_created, tasks_updated, tasks_closed,
        )
    except Exception as e:
        logger.error("jira sync bg: failed for epic %s: %s", epic_key, e, exc_info=True)


# ── Testing Comments ─────────────────────────────────────────────────────────


class CommentRequest(BaseModel):
    text: str


@router.post("/{epic_key}/comment")
def post_testing_comment(
    epic_key: str,
    body: CommentRequest,
    auth: tuple[str, int] = Depends(_require_auth),
    settings: Settings = Depends(get_settings),
):
    owner, groups = auth
    allowed = GROUP_BITS["rhdp-operations"] | GROUP_BITS["rhdp-administrators"]
    _require_group(groups, allowed, "rhdp-operations or rhdp-administrators")

    if not settings.jira_url:
        raise HTTPException(status_code=503, detail="Jira not configured")

    task = _find_task_by_label(epic_key, "ph:testing", settings)
    if not task:
        raise HTTPException(status_code=404, detail=f"Testing ticket not found under {epic_key}")

    if not task["assignee"]:
        _assign_ticket(task["key"], owner, settings)

    if not _add_comment(task["key"], body.text, owner, settings):
        raise HTTPException(status_code=502, detail="Failed to post comment to Jira")

    return {"posted": True, "ticket_key": task["key"]}


@router.get("/{epic_key}/comments")
def get_testing_comments(
    epic_key: str,
    auth: tuple[str, int] = Depends(_require_auth),
    settings: Settings = Depends(get_settings),
):
    owner, groups = auth
    has_ops = groups & GROUP_BITS["rhdp-operations"]
    has_dev = groups & GROUP_BITS["rhdp-developers"]
    if not (has_ops or has_dev):
        raise HTTPException(status_code=403, detail="Requires rhdp-operations or rhdp-developers")

    if not settings.jira_url:
        raise HTTPException(status_code=503, detail="Jira not configured")

    task = _find_task_by_label(epic_key, "ph:testing", settings)
    if not task:
        return {"comments": [], "ticket_key": ""}

    comments = _get_comments(task["key"], settings)
    return {"comments": comments, "ticket_key": task["key"]}


# ── Task Complete ────────────────────────────────────────────────────────────


@router.post("/{epic_key}/task/{task_id}/complete")
def complete_task(
    epic_key: str,
    task_id: str,
    auth: tuple[str, int] = Depends(_require_auth),
    settings: Settings = Depends(get_settings),
):
    owner, groups = auth
    _require_group(groups, GROUP_BITS["rhdp-developers"], "rhdp-developers")

    if not settings.jira_url:
        return {"closed": False, "ticket_key": "", "detail": "Jira not configured"}

    task = _find_task_by_label(epic_key, f"ph:{task_id}", settings)
    if not task:
        return {"closed": False, "ticket_key": "", "detail": f"No ticket found for {task_id}"}

    if task["status"].lower() == "done":
        return {"closed": True, "ticket_key": task["key"], "detail": "Already closed"}

    closed = _transition_to_done(task["key"], settings)
    return {"closed": closed, "ticket_key": task["key"]}

