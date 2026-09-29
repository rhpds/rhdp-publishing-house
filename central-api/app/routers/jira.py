"""Jira system endpoints — epic creation, updates, task management, and sync."""
import asyncio
import base64
import json
import logging
import re
import ssl
import time
import urllib.parse
import urllib.request
import uuid

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
    workflow_id: str  # Workflow instance ID


class CreateEpicResponse(BaseModel):
    epic_key: str
    jira_url: str


class UpdateEpicRequest(BaseModel):
    workflow_id: str  # Workflow instance ID


class UpdateEpicResponse(BaseModel):
    epic_key: str
    jira_url: str


class PreIntakeDataResponse(BaseModel):
    epic_key: str
    description: str



def _jira_headers(settings: Settings) -> dict:
    creds = base64.b64encode(f"{settings.jira_email}:{settings.jira_api_token}".encode()).decode()
    return {
        "Authorization": f"Basic {creds}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _send_cloud_event(event_type: str, project_slug: str, data: dict, settings: Settings):
    """Send a CloudEvent to SonataFlow."""
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


# ── ADF Builder Helpers ─────────────────────────────────────────────────────

def _build_adf_heading(level: int, text: str) -> dict:
    """Build ADF heading node."""
    return {
        "type": "heading",
        "attrs": {"level": level},
        "content": [{"type": "text", "text": text}]
    }


def _build_adf_paragraph(content: list[dict]) -> dict:
    """Build ADF paragraph node from content list."""
    return {
        "type": "paragraph",
        "content": content
    }


def _build_adf_text(text: str, strong: bool = False, em: bool = False) -> dict:
    """Build ADF text node."""
    marks = []
    if strong:
        marks.append({"type": "strong"})
    if em:
        marks.append({"type": "em"})
    node = {"type": "text", "text": text}
    if marks:
        node["marks"] = marks
    return node


def _build_adf_bullet_list(items: list[str]) -> dict:
    """Build ADF bullet list."""
    return {
        "type": "bulletList",
        "content": [
            {
                "type": "listItem",
                "content": [{
                    "type": "paragraph",
                    "content": [{"type": "text", "text": item}]
                }]
            }
            for item in items
        ]
    }


def _build_adf_rule() -> dict:
    """Build ADF horizontal rule."""
    return {"type": "rule"}


# ── Epic Description Formatters ─────────────────────────────────────────────

def _format_onboarded_epic(fields: dict) -> tuple[str, dict]:
    """Build onboarded epic summary and ADF description."""
    asset_title = fields.get("assetTitle", fields.get("projectId", "Untitled"))

    # Epic summary
    summary = f"[PH] {asset_title}"

    # Build ADF content
    content = [
        _build_adf_heading(1, asset_title),
        _build_adf_heading(2, "Overview"),
        _build_adf_paragraph([_build_adf_text(fields.get("projectDescription", ""))]),
        _build_adf_heading(2, "Content Plan"),
        _build_adf_paragraph([
            _build_adf_text("Type: ", strong=True),
            _build_adf_text(fields.get("contentType", "lab")),
            {"type": "hardBreak"},
            _build_adf_text("Showroom Type: ", strong=True),
            _build_adf_text(fields.get("showroomType", "classic"))
        ]),
    ]

    # Content Outline
    if fields.get("contentOutline"):
        content.extend([
            _build_adf_heading(3, "Content Outline"),
            _build_adf_paragraph([_build_adf_text(fields["contentOutline"])])
        ])

    # Learning Objectives
    if fields.get("learningObjectives"):
        content.extend([
            _build_adf_heading(3, "Learning Objectives"),
            _build_adf_paragraph([_build_adf_text(fields["learningObjectives"])])
        ])

    # Environment Requirements
    content.append(_build_adf_heading(2, "Environment Requirements"))
    env_lines = [
        _build_adf_text("Platform: ", strong=True),
        _build_adf_text("OpenShift"),
        {"type": "hardBreak"},
        _build_adf_text("Cloud Provider: ", strong=True),
        _build_adf_text(fields.get("cloudProvider", "cnv")),
        {"type": "hardBreak"},
        _build_adf_text("Cluster Type: ", strong=True),
        _build_adf_text(fields.get("clusterType", "sno")),
        {"type": "hardBreak"},
        _build_adf_text("OCP Version: ", strong=True),
        _build_adf_text(fields.get("ocpVersion", "4.21"))
    ]
    content.append(_build_adf_paragraph(env_lines))

    # Business Context
    content.append(_build_adf_heading(2, "Business Context"))
    biz_lines = [
        _build_adf_text("Sales Play / TDP: ", strong=True),
        _build_adf_text(fields.get("salesPlayTdp", "N/A")),
        {"type": "hardBreak"},
        _build_adf_text("Associated Opportunities: ", strong=True),
        _build_adf_text(fields.get("associatedOpportunities", "N/A"))
    ]
    content.append(_build_adf_paragraph(biz_lines))

    # Team
    content.append(_build_adf_heading(2, "Team"))
    content.append(_build_adf_paragraph([
        _build_adf_text("Owner: ", strong=True),
        _build_adf_text(fields.get("ssoEmail", ""))
    ]))

    team_members = fields.get("teamMembers", [])
    if team_members:
        content.append(_build_adf_paragraph([_build_adf_text("Collaborators:", strong=True)]))
        collab_items = [f"@{m.get('user', '')}" for m in team_members if m.get('user')]
        content.append(_build_adf_bullet_list(collab_items))

    # Technical Details
    ai_req = "None"
    if fields.get("aiRelated"):
        can_use_maas = fields.get("canUseMaas", True)
        if not can_use_maas:
            gpu_just = fields.get("gpuJustification", "")
            ai_req = f"GPU: {gpu_just}" if gpu_just else "GPU (no justification provided)"
        else:
            models = fields.get("maasModels", "")
            ai_req = f"MaaS: {models}" if models else "MaaS (models not specified)"
    else:
        ai_req = "None"

    content.append(_build_adf_heading(2, "Technical Details"))
    tech_lines = [
        _build_adf_text("Automation Type: ", strong=True),
        _build_adf_text(fields.get("automationType", "ansible")),
        {"type": "hardBreak"},
        _build_adf_text("AI Requirements: ", strong=True),
        _build_adf_text(ai_req),
        {"type": "hardBreak"},
        _build_adf_text("Initiative: ", strong=True),
        _build_adf_text(fields.get("initiativeKey", "rh1_2027")),
        {"type": "hardBreak"},
        _build_adf_text("Tags: ", strong=True),
        _build_adf_text(", ".join(fields.get("tags", [])) if fields.get("tags") else "None")
    ]
    content.append(_build_adf_paragraph(tech_lines))

    # Footer
    content.append(_build_adf_rule())
    content.append(_build_adf_paragraph([
        _build_adf_text("Created via Publishing House Template", em=True)
    ]))

    description = {
        "type": "doc",
        "version": 1,
        "content": content
    }

    return summary, description


def _format_field_source_epic(fields: dict) -> tuple[str, dict]:
    """Build field source epic summary and ADF description."""
    asset_title = fields.get("assetTitle", fields.get("projectId", "Untitled"))

    summary = f"[PH] {asset_title} — Field Source"

    content = [
        _build_adf_paragraph([_build_adf_text("🏷️ Field Source Content", strong=True)]),
        _build_adf_heading(1, asset_title),
        _build_adf_heading(2, "Overview"),
        _build_adf_paragraph([_build_adf_text(fields.get("description", fields.get("projectDescription", "")))]),
        _build_adf_heading(2, "Content Plan"),
        _build_adf_paragraph([
            _build_adf_text("Type: ", strong=True),
            _build_adf_text(fields.get("contentType", "lab"))
        ]),
    ]

    if fields.get("contentOutline"):
        content.extend([
            _build_adf_heading(3, "Content Outline"),
            _build_adf_paragraph([_build_adf_text(fields["contentOutline"])])
        ])

    if fields.get("learningObjectives"):
        content.extend([
            _build_adf_heading(3, "Learning Objectives"),
            _build_adf_paragraph([_build_adf_text(fields["learningObjectives"])])
        ])

    # Environment Configuration
    content.append(_build_adf_heading(2, "Environment Configuration"))
    env_lines = [
        _build_adf_text("Platform: ", strong=True),
        _build_adf_text(fields.get("platform", "ocp")),
        {"type": "hardBreak"},
        _build_adf_text("Cloud Provider: ", strong=True),
        _build_adf_text(fields.get("cloudProvider", "cnv"))
    ]

    if fields.get("cloudProvider") != "cnv" and fields.get("cloudProviderJustification"):
        env_lines.extend([
            {"type": "hardBreak"},
            _build_adf_text("Justification: ", strong=True),
            _build_adf_text(fields["cloudProviderJustification"])
        ])

    # Add platform-specific fields
    platform = fields.get("platform", "ocp")
    if platform == "rhel-vms":
        # RHEL-specific fields
        env_lines.extend([
            {"type": "hardBreak"},
            _build_adf_text("RHEL Version: ", strong=True),
            _build_adf_text(fields.get("rhelVersion", "9"))
        ])
    else:
        # OCP-specific fields
        env_lines.extend([
            {"type": "hardBreak"},
            _build_adf_text("Cluster Type: ", strong=True),
            _build_adf_text(fields.get("clusterType", "sno")),
            {"type": "hardBreak"},
            _build_adf_text("OCP Version: ", strong=True),
            _build_adf_text(fields.get("ocpVersion", "4.21"))
        ])

        if fields.get("clusterType") == "multinode":
            worker_count = fields.get("workerCount", 2)
            worker_cpu = fields.get("workerCpu", 16)
            worker_ram = fields.get("workerMemoryGb", 64)
            env_lines.extend([
                {"type": "hardBreak"},
                _build_adf_text("Workers: ", strong=True),
                _build_adf_text(f"{worker_count} x {worker_cpu} vCPU, {worker_ram} GB RAM")
            ])

    content.append(_build_adf_paragraph(env_lines))

    # Base Workloads
    if fields.get("baseWorkloads"):
        content.append(_build_adf_paragraph([_build_adf_text("Base Workloads:", strong=True)]))
        content.append(_build_adf_bullet_list(fields["baseWorkloads"]))

    # Multi-user
    if fields.get("multiUser"):
        content.append(_build_adf_paragraph([
            _build_adf_text("Multi-User: ", strong=True),
            _build_adf_text(f"Yes ({fields.get('userCount', 1)} users)")
        ]))

    # Business Context
    if fields.get("salesPlayTdp"):
        content.append(_build_adf_heading(2, "Business Context"))
        content.append(_build_adf_paragraph([
            _build_adf_text("Sales Play / TDP: ", strong=True),
            _build_adf_text(fields["salesPlayTdp"])
        ]))

    # Team
    content.append(_build_adf_heading(2, "Team"))
    content.append(_build_adf_paragraph([
        _build_adf_text("Owner: ", strong=True),
        _build_adf_text(fields.get("ssoEmail", ""))
    ]))

    team_members = fields.get("teamMembers", [])
    if team_members:
        content.append(_build_adf_paragraph([_build_adf_text("Collaborators:", strong=True)]))
        collab_items = [f"@{m.get('user', '')}" for m in team_members if m.get('user')]
        content.append(_build_adf_bullet_list(collab_items))

    # Automation
    content.append(_build_adf_heading(2, "Automation"))
    auto_lines = [
        _build_adf_text("Automation Location: ", strong=True),
        _build_adf_text("PH Monorepo" if fields.get("automationLocation") == "ph_repo" else "External Repo")
    ]

    if fields.get("automationLocation") == "existing_repo" and fields.get("existingRepoUrl"):
        auto_lines.extend([
            {"type": "hardBreak"},
            _build_adf_text("Repo URL: ", strong=True),
            _build_adf_text(fields["existingRepoUrl"])
        ])

    auto_lines.extend([
        {"type": "hardBreak"},
        _build_adf_text("Tags: ", strong=True),
        _build_adf_text(", ".join(fields.get("tags", [])) if fields.get("tags") else "None")
    ])

    content.append(_build_adf_paragraph(auto_lines))

    # Footer
    content.append(_build_adf_rule())
    content.append(_build_adf_paragraph([
        _build_adf_text("Field Source — Created via Publishing House Template", em=True)
    ]))

    description = {
        "type": "doc",
        "version": 1,
        "content": content
    }

    return summary, description


# ── ProForma Form Creation ──────────────────────────────────────────────────

def _create_proforma_form(epic_key: str, epic_type: str, fields: dict, settings: Settings) -> str:
    """Create ProForma form on epic. Returns form_id or empty string on failure."""
    auth_str = base64.b64encode(f"{settings.jira_email}:{settings.jira_api_token}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_str}",
        "Content-Type": "application/json",
    }

    # Build ProForma form template with onboarding fields
    form_data = {
        "name": "Pre-Intake Onboarding",
        "description": "Pre-intake onboarding questions for content creation",
        "questions": [
            {
                "id": "asset_title",
                "label": "Asset Title",
                "type": "text",
                "required": True,
                "value": fields.get("assetTitle", "")
            },
            {
                "id": "project_description",
                "label": "Description / Abstract",
                "type": "paragraph",
                "required": True,
                "value": fields.get("projectDescription", "")
            },
            {
                "id": "content_outline",
                "label": "Content Outline",
                "type": "paragraph",
                "required": True,
                "value": fields.get("contentOutline", "")
            },
            {
                "id": "learning_objectives",
                "label": "Learning Objectives",
                "type": "paragraph",
                "required": True,
                "value": fields.get("learningObjectives", "")
            },
            {
                "id": "content_type",
                "label": "Is this a lab or a demo?",
                "type": "radio",
                "required": True,
                "options": ["lab", "demo"],
                "value": fields.get("contentType", "lab")
            },
            {
                "id": "associated_opportunities",
                "label": "Associated opportunities",
                "type": "paragraph",
                "required": False,
                "value": fields.get("associatedOpportunities", "")
            },
            {
                "id": "sales_play_tdp",
                "label": "Sales Play / TDP relevance",
                "type": "paragraph",
                "required": False,
                "value": fields.get("salesPlayTdp", "")
            },
            {
                "id": "automation_type",
                "label": "How will you automate?",
                "type": "radio",
                "required": True,
                "options": ["ansible", "gitops", "both"],
                "value": fields.get("automationType", "ansible")
            },
            {
                "id": "ai_related",
                "label": "Is this related to AI?",
                "type": "radio",
                "required": False,
                "options": ["yes", "no"],
                "value": "yes" if fields.get("aiRelated") else "no"
            },
            {
                "id": "gpu_needed",
                "label": "Do you need direct GPU access?",
                "type": "radio",
                "required": False,
                "options": ["yes", "no"],
                "value": "yes" if fields.get("gpuNeeded") else "no"
            },
            {
                "id": "maas_instead",
                "label": "Can you use MaaS instead?",
                "type": "radio",
                "required": False,
                "options": ["yes", "no"],
                "value": "yes" if fields.get("maasInstead") else "no"
            },
            {
                "id": "partners_access",
                "label": "Should it be available to Partners?",
                "type": "radio",
                "required": False,
                "options": ["yes", "no"],
                "value": "yes" if fields.get("partnersAccess") else "no"
            }
        ]
    }

    try:
        req = urllib.request.Request(
            f"{settings.jira_url.rstrip('/')}/rest/api/1/form/{epic_key}",
            data=json.dumps(form_data).encode(),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=20) as r:
            response_data = json.loads(r.read().decode())
            form_id = response_data.get("id", "")
            logger.info("ProForma form created for epic %s: %s", epic_key, form_id)
            return form_id
    except Exception as e:
        logger.error("ProForma form creation failed for epic %s: %s", epic_key, e)
        return ""


def _get_workflow_data_by_business_key(business_key: str, deployment_mode: str, settings: Settings) -> dict:
    """Query SonataFlow runtime API to get workflow data by business key.
    This is instant - no Data Index sync lag."""
    # deploymentMode is already in correct format (rhdp-published)
    workflow_name = deployment_mode

    # Build workflow URL - same namespace, so just use service name
    # e.g., http://rhdp-published/rhdp-published?businessKey=ph-test
    try:
        # Query SonataFlow runtime API by business key
        url = f"http://{workflow_name}/{workflow_name}?businessKey={business_key}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")

        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=10) as r:
            response_data = json.loads(r.read().decode())

            # Response is an array of workflow instances matching the business key
            if not response_data or not isinstance(response_data, list) or len(response_data) == 0:
                raise HTTPException(
                    status_code=404,
                    detail=f"Workflow not found for business key: {business_key}"
                )

            # Get the most recent instance (last in array)
            instance = response_data[-1]
            workflow_data = instance.get("workflowdata", instance)

            logger.info("Retrieved workflow data for business key %s from %s (instant)", business_key, workflow_name)
            return workflow_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to query SonataFlow runtime API for business key %s: %s", business_key, e)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to query workflow runtime API: {e}"
        )


def _get_workflow_data(workflow_instance_id: str, settings: Settings) -> dict:
    """Query Data Index to get workflow data from workflow instance ID.
    Retries up to 5 times with 1-second delay to handle Data Index sync lag."""
    query = """
    query GetWorkflowData($id: String!) {
      ProcessInstances(where: { id: { equal: $id } }) {
        variables
      }
    }
    """

    max_retries = 30
    retry_delay = 2  # seconds

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                f"{settings.sonataflow_graphql_url}/graphql",
                data=json.dumps({
                    "query": query,
                    "variables": {"id": workflow_instance_id}
                }).encode(),
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            with urllib.request.urlopen(req, context=_SSL_CTX, timeout=10) as r:
                response_data = json.loads(r.read().decode())
                instances = response_data.get("data", {}).get("ProcessInstances", [])

                if not instances:
                    if attempt < max_retries - 1:
                        logger.warning(
                            "Workflow instance %s not found in Data Index (attempt %d/%d), retrying in %ds...",
                            workflow_instance_id, attempt + 1, max_retries, retry_delay
                        )
                        time.sleep(retry_delay)
                        continue
                    else:
                        raise HTTPException(
                            status_code=404,
                            detail=f"Workflow instance {workflow_instance_id} not found after {max_retries} attempts"
                        )

                variables = instances[0].get("variables", {})
                workflow_data = variables.get("workflowdata", {})

                logger.info("Workflow instance %s has deploymentMode: %s (found on attempt %d)",
                           workflow_instance_id, workflow_data.get("deploymentMode"), attempt + 1)
                return workflow_data

        except HTTPException:
            raise
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(
                    "Failed to query Data Index for workflow %s (attempt %d/%d): %s, retrying...",
                    workflow_instance_id, attempt + 1, max_retries, e
                )
                time.sleep(retry_delay)
                continue
            else:
                logger.error("Failed to query Data Index for workflow %s after %d attempts: %s",
                           workflow_instance_id, max_retries, e)
                raise HTTPException(
                    status_code=502,
                    detail=f"Failed to query workflow metadata: {e}"
                )


@router.post("/epic", response_model=CreateEpicResponse, status_code=201)
def create_epic(
    body: CreateEpicRequest,
    _caller: str = Depends(_require_auth),
    settings: Settings = Depends(get_settings),
):
    """Create Jira epic with rich description and optional ProForma form.
    Called by SonataFlow during the CreateEpic state with all template fields."""
    if not settings.jira_url:
        raise HTTPException(status_code=503, detail="Jira not configured")

    # Import here to avoid circular dependency
    from .projects import _get_workflow_by_id

    # Query Runtime API by workflow ID
    workflow_instance = _get_workflow_by_id(body.workflow_id)
    workflow_data = workflow_instance.get("workflowdata", {})
    workflow_type = workflow_data.get("deploymentMode", "rhdp-published")

    # Format epic summary and description based on type
    if workflow_type in ("rhdp-published", "onboarded"):
        summary, description_adf = _format_onboarded_epic(workflow_data)
        labels = ["publishing-house", "ph-onboarded"]
    elif workflow_type == "field-source":
        summary, description_adf = _format_field_source_epic(workflow_data)
        labels = ["publishing-house", "ph-field-source"]
    else:
        raise HTTPException(status_code=400, detail=f"Unknown workflow type: {workflow_type}")

    # Add content type label
    if workflow_data.get("contentType"):
        labels.append(workflow_data["contentType"])

    # Lookup assignee
    assignee = None
    if settings.jira_default_assignee:
        jira_user = _lookup_jira_account_id(settings.jira_default_assignee, settings)
        if jira_user and jira_user["accountId"]:
            assignee = {"accountId": jira_user["accountId"]}

    # Resolve initiative to Jira parent key
    from ..services.validation.policy import load_policy
    initiative_slug = workflow_data.get("initiativeKey", "none")
    initiative_map = load_policy().get("initiative_jira_keys", {})
    parent_key = initiative_map.get(initiative_slug) or initiative_map.get("_default")

    # Build Jira issue fields
    jira_fields: dict = {
        "project": {"key": settings.jira_project_key},
        "summary": summary,
        "issuetype": {"name": "Epic"},
        "labels": labels,
        "assignee": assignee,
        "description": description_adf,
    }
    if parent_key:
        jira_fields["parent"] = {"key": parent_key}

    # Create epic
    req = urllib.request.Request(
        f"{settings.jira_url}/rest/api/3/issue",
        data=json.dumps({"fields": jira_fields}).encode(),
        headers=_jira_headers(settings),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=15) as r:
            epic_key = json.loads(r.read().decode())["key"]
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Jira epic creation failed: {e}")

    # ProForma form creation removed - all fields stored in epic description
    # Description format is driven by epic_type (onboarded vs field_source)
    jira_url = f"{settings.jira_url}/browse/{epic_key}"
    project_id = workflow_data.get("projectId", "unknown")
    logger.info("jira: created epic %s for project %s", epic_key, project_id)

    return CreateEpicResponse(
        epic_key=epic_key,
        jira_url=jira_url
    )


@router.post("/epic/update", response_model=UpdateEpicResponse)
def update_epic(
    body: UpdateEpicRequest,
    _caller: str = Depends(_require_auth),
    settings: Settings = Depends(get_settings),
):
    """Update Jira epic description after pre-intake approval.
    Reads ProForma form if available, otherwise uses workflow fields."""
    if not settings.jira_url:
        raise HTTPException(status_code=503, detail="Jira not configured")

    # Import here to avoid circular dependency
    from .projects import _get_workflow_by_id

    # Query Runtime API by workflow ID
    workflow_instance = _get_workflow_by_id(body.workflow_id)
    workflow_data = workflow_instance.get("workflowdata", {})
    workflow_type = workflow_data.get("deploymentMode", "rhdp-published")

    # Get epic_key from workflow data
    epic_key = workflow_data.get("epic_key", "")
    if not epic_key:
        raise HTTPException(status_code=400, detail="Epic key not found in workflow data")

    # Rebuild epic description with final values from workflow data
    if workflow_type in ("rhdp-published", "onboarded"):
        summary, description_adf = _format_onboarded_epic(workflow_data)
    elif workflow_type == "field-source":
        summary, description_adf = _format_field_source_epic(workflow_data)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown workflow type: {workflow_type}")

    # Update epic
    update_fields = {
        "summary": summary,
        "description": description_adf
    }

    req = urllib.request.Request(
        f"{settings.jira_url}/rest/api/3/issue/{epic_key}",
        data=json.dumps({"fields": update_fields}).encode(),
        headers=_jira_headers(settings),
        method="PUT",
    )

    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=15):
            logger.info("jira: updated epic %s after pre-intake approval", epic_key)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Jira epic update failed: {e}")

    # Create initial tasks: Intake, Testing, and Dev CI (if not zero_touch)
    showroom_type = workflow_data.get("showroomType", "classic")

    # Create Intake task
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
    try:
        intake_req = urllib.request.Request(
            f"{settings.jira_url}/rest/api/3/issue",
            data=json.dumps({"fields": intake_fields}).encode(),
            headers=_jira_headers(settings),
            method="POST",
        )
        with urllib.request.urlopen(intake_req, context=_SSL_CTX, timeout=10):
            logger.info("jira: created Intake task under epic %s", epic_key)
    except Exception as e:
        logger.warning("jira: Intake task creation failed for epic %s: %s", epic_key, e)

    # Create Testing task
    testing_fields = {
        "project": {"key": settings.jira_project_key},
        "summary": "[PH] Testing",
        "issuetype": {"name": "Task"},
        "parent": {"key": epic_key},
        "labels": ["publishing-house", "ph:testing", "rhdp_ops"],
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
        testing_req = urllib.request.Request(
            f"{settings.jira_url}/rest/api/3/issue",
            data=json.dumps({"fields": testing_fields}).encode(),
            headers=_jira_headers(settings),
            method="POST",
        )
        with urllib.request.urlopen(testing_req, context=_SSL_CTX, timeout=10):
            logger.info("jira: created Testing task under epic %s", epic_key)
    except Exception as e:
        logger.warning("jira: Testing task creation failed for epic %s: %s", epic_key, e)

    # Create Development CI task only if not zero_touch
    if showroom_type != "zero_touch":
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
            dev_ci_req = urllib.request.Request(
                f"{settings.jira_url}/rest/api/3/issue",
                data=json.dumps({"fields": dev_ci_fields}).encode(),
                headers=_jira_headers(settings),
                method="POST",
            )
            with urllib.request.urlopen(dev_ci_req, context=_SSL_CTX, timeout=10):
                logger.info("jira: created Dev CI task under epic %s", epic_key)
        except Exception as e:
            logger.warning("jira: Dev CI task creation failed for epic %s: %s", epic_key, e)
    else:
        logger.info("jira: skipping Dev CI task for zero_touch showroom type")

    jira_url = f"{settings.jira_url}/browse/{epic_key}"
    return UpdateEpicResponse(epic_key=epic_key, jira_url=jira_url)


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
    workflow_id: str
    status: str = ""


class SyncResponse(BaseModel):
    epic_key: str
    tasks_created: int = 0
    tasks_updated: int = 0
    tasks_closed: int = 0
    intake_closed: bool = False


STORY_POINTS_FIELD = "customfield_10028"
POINTS = {
    "intake": 3,
    "module": 10,
    "dev-ci": 5,
    "write-automation": 8,
    "write-health-check": 3,
    "write-e2e-tests": 8,
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

    # Import here to avoid circular dependency
    from .projects import _get_workflow_by_id

    # Query Runtime API for workflow data
    workflow_instance = _get_workflow_by_id(body.workflow_id)
    # Runtime API returns workflowdata directly, not under variables
    wd = workflow_instance.get("workflowdata", {})

    repo_url = wd.get("repoUrl", "")
    epic_key = wd.get("epic_key", "")
    slug = wd.get("projectId", "")

    if not repo_url:
        raise HTTPException(status_code=422, detail="Workflow has no repoUrl")
    if not epic_key:
        raise HTTPException(status_code=422, detail="Workflow has no epic_key")

    asyncio.get_event_loop().run_in_executor(
        None, _sync_jira_tasks_bg, repo_url, epic_key, settings, body.status, slug,
    )
    logger.info("jira sync: accepted for epic %s (status=%s) — running in background", epic_key, body.status)
    return SyncResponse(epic_key=epic_key)


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
                        agnosticv_urls = wd.get("agnosticvUrls", [])
                        ci_urls = wd.get("ciUrls", [])
                        if agnosticv_urls or ci_urls:
                            desc_lines = []
                            for url in agnosticv_urls:
                                desc_lines.append(f"AgnosticV Catalog Item: {url}")
                            for url in ci_urls:
                                desc_lines.append(f"CI Catalog Item: {url}")
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

            dev = spec_data.get("development", {})

            automation = dev.get("automation", {})
            if any(isinstance(v, dict) and v.get("status") == "complete" for v in automation.values()):
                task = label_to_task.get("ph:write-automation")
                if task and task["status"].lower() != "done":
                    if _transition_to_done(task["key"], settings):
                        tasks_closed += 1

            if dev.get("e2e", {}).get("status") == "complete":
                task = label_to_task.get("ph:write-e2e-tests")
                if task and task["status"].lower() != "done":
                    if _transition_to_done(task["key"], settings):
                        tasks_closed += 1

            if dev.get("healthCheck", {}).get("status") == "complete":
                task = label_to_task.get("ph:write-health-check")
                if task and task["status"].lower() != "done":
                    if _transition_to_done(task["key"], settings):
                        tasks_closed += 1

        if status == "TestingComplete":
            testing_task = label_to_task.get("ph:testing")
            if testing_task and testing_task["status"].lower() != "done":
                if _transition_to_done(testing_task["key"], settings):
                    tasks_closed += 1

        if status == "Published":
            if _transition_to_done(epic_key, settings):
                logger.info("jira sync bg: closed epic %s", epic_key)

        logger.info(
            "jira sync bg: epic %s — created=%d updated=%d closed=%d",
            epic_key, tasks_created, tasks_updated, tasks_closed,
        )
    except Exception as e:
        logger.error("jira sync bg: failed for epic %s: %s", epic_key, e, exc_info=True)


# ── Testing Comments ─────────────────────────────────────────────────────────


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


@router.get("/epic/{epic_key}/preintake-data", response_model=PreIntakeDataResponse)
async def get_preintake_data(
    epic_key: str,
    settings: Settings = Depends(get_settings),
    auth: tuple[str, int] = Depends(_require_auth),
):
    """Fetch pre-intake data from workflow.
    Returns structured onboarding fields for intake skill.
    Fields are stored in workflow data and synced to Jira epic description."""
    owner, groups = auth
    _require_group(groups, GROUP_BITS["rhdp-developers"], "rhdp-developers")

    # Get project_id from epic via Jira
    if not settings.jira_url or not settings.jira_email or not settings.jira_api_token:
        raise HTTPException(status_code=503, detail="Jira not configured")

    # Fetch epic to get project ID from labels or summary
    auth_str = base64.b64encode(f"{settings.jira_email}:{settings.jira_api_token}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_str}",
        "Content-Type": "application/json",
    }

    try:
        req = urllib.request.Request(
            f"{settings.jira_url.rstrip('/')}/rest/api/3/issue/{epic_key}",
            headers=headers,
        )
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=10) as r:
            epic_data = json.loads(r.read().decode())
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch epic {epic_key}: {e}")

    # Convert ADF description to plain text for skill to parse
    description_adf = epic_data.get("fields", {}).get("description", {})

    def adf_to_text(adf: dict) -> str:
        """Convert ADF to plain text."""
        if not isinstance(adf, dict):
            return ""

        lines = []
        for node in adf.get("content", []):
            node_type = node.get("type", "")

            if node_type == "heading":
                level = node.get("attrs", {}).get("level", 1)
                text = "".join([c.get("text", "") for c in node.get("content", [])])
                lines.append(f"{'#' * level} {text}")
            elif node_type == "paragraph":
                text = ""
                for c in node.get("content", []):
                    if c.get("type") == "text":
                        text += c.get("text", "")
                    elif c.get("type") == "hardBreak":
                        text += "\n"
                if text.strip():
                    lines.append(text)
            elif node_type == "bulletList":
                for item in node.get("content", []):
                    if item.get("type") == "listItem":
                        for para in item.get("content", []):
                            item_text = "".join([c.get("text", "") for c in para.get("content", [])])
                            lines.append(f"- {item_text}")

        return "\n".join(lines)

    description_text = adf_to_text(description_adf)

    # Return just the description text - skill will parse it
    return {"epic_key": epic_key, "description": description_text}

