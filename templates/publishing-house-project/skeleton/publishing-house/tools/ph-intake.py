#!/usr/bin/env python3
"""Submit intake to Publishing House Central API.

Reads project data from catalog-info.yaml and spec.yaml,
builds the IntakeAnswers payload, POSTs to Central API,
and updates spec.yaml with the returned Jira ticket.
"""
import json
import os
import ssl
import sys
import urllib.request
from pathlib import Path

import yaml


def find_repo_root():
    """Walk up from cwd to find directory containing catalog-info.yaml."""
    p = Path.cwd()
    while p != p.parent:
        if (p / "catalog-info.yaml").exists():
            return p
        p = p.parent
    return None


def main():
    root = find_repo_root()
    if not root:
        print(json.dumps({"error": "catalog-info.yaml not found — not a Publishing House project"}))
        sys.exit(1)

    ci_path = root / "catalog-info.yaml"
    spec_path = root / "publishing-house" / "spec.yaml"

    if not spec_path.exists():
        print(json.dumps({"error": "publishing-house/spec.yaml not found"}))
        sys.exit(1)

    ci = yaml.safe_load(ci_path.read_text())
    project_id = ci.get("metadata", {}).get("name", "")
    if not project_id:
        print(json.dumps({"error": "metadata.name missing in catalog-info.yaml"}))
        sys.exit(1)

    spec = yaml.safe_load(spec_path.read_text()) or {}
    project = spec.get("project", {})
    spec_data = spec.get("spec", {})
    env = spec_data.get("environment", {})

    auth_path = Path(os.path.expanduser("~/.config/publishing-house/ph.json"))
    if not auth_path.exists():
        print(json.dumps({"error": "~/.config/publishing-house/ph.json not found — run the orchestrator skill first"}))
        sys.exit(1)

    creds = json.loads(auth_path.read_text())
    api_key = creds.get("credential", "")
    if not api_key:
        print(json.dumps({"error": "No credential in ph.json"}))
        sys.exit(1)

    central_url = creds.get("central", "").rstrip("/")
    if not central_url:
        print(json.dumps({"error": "No portal URL in ph.json"}))
        sys.exit(1)

    design_path = root / "publishing-house" / "spec" / "design.md"
    problem_statement = ""
    if design_path.exists():
        problem_statement = design_path.read_text()[:500]

    modules = []
    spec_modules = spec_data.get("modules", [])
    modules_dir = root / "publishing-house" / "spec" / "modules"
    if spec_modules:
        for m in spec_modules:
            modules.append({
                "title": m.get("title", ""),
                "duration_min": m.get("duration_min", 20),
            })
    elif modules_dir.exists():
        for i, f in enumerate(sorted(modules_dir.glob("module-*.md")), 1):
            title = f.stem.split("-", 2)[-1].replace("-", " ").title() if "-" in f.stem else f.stem
            modules.append({"title": title, "duration_min": 20})

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    deployment_mode = project.get("deployment_mode", "self_published")
    epic_key = project.get("jira_ticket", "")
    if not epic_key and deployment_mode == "rhdp_published":
        try:
            wd_url = f"{central_url}/api/v1/projects/{project_id}/workflow-data"
            wd_req = urllib.request.Request(wd_url, headers={"Authorization": f"Bearer {api_key}"})
            with urllib.request.urlopen(wd_req, context=ctx, timeout=10) as wd_resp:
                wd = json.loads(wd_resp.read().decode())
                epic_key = wd.get("epic_key", "")
        except Exception:
            pass

    payload = {
        "name": spec_data.get("title", "") or project.get("slug", project_id),
        "slug": project_id,
        "content_type": project.get("content_type", "lab"),
        "deployment_mode": project.get("deployment_mode", "self_published"),
        "owner_email": project.get("owner_email", ""),
        "problem_statement": problem_statement,
        "audience_role": spec_data.get("audience", ""),
        "learning_objectives": spec_data.get("learning_objectives", []),
        "modules": modules,
        "ocp_version": env.get("ocp_version", ""),
        "topology": env.get("topology", "shared-cluster"),
        "duration_hours": spec_data.get("duration_hours") or 0,
        "epic_key": epic_key,
    }

    url = f"{central_url}/api/v1/projects/{project_id}/intake"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        if e.code == 409:
            import re
            m = re.search(r"in '(\w+)' stage", body)
            if m:
                actual_stage = m.group(1)
                creds["stage"] = actual_stage
                with open(auth_path, "w") as f:
                    json.dump(creds, f, indent=2)
        print(json.dumps({"error": f"Central API returned {e.code}: {body}"}))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": f"Request failed: {e}"}))
        sys.exit(1)

    jira_ticket = result.get("jira_ticket", "") or result.get("epic_key", "")
    if jira_ticket:
        spec["project"]["jira_ticket"] = jira_ticket
        with open(spec_path, "w") as f:
            yaml.dump(spec, f, default_flow_style=False, sort_keys=False)

    print(json.dumps(result))


if __name__ == "__main__":
    main()
