#!/usr/bin/env python3
"""Shared workflow state script for all Publishing House skills.

Reads auth credentials, resolves workflow_id (calling /workflow-data if needed),
queries /workflow-state, and syncs jira_ticket to spec.yaml.

Output: key:value pairs, one per line
  stage:intake
  workflow_id:abc-123
  epic_key:RHDPCD-456
  jira_url:https://...
"""
import json
import os
import ssl
import sys
import urllib.request
from pathlib import Path

import yaml


def find_repo_root():
    p = Path.cwd()
    while p != p.parent:
        if (p / "catalog-info.yaml").exists():
            return p
        p = p.parent
    return None


def main():
    root = find_repo_root()
    if not root:
        print(json.dumps({"error": "catalog-info.yaml not found"}))
        sys.exit(1)

    auth_path = Path(os.path.expanduser("~/.config/publishing-house/auth.json"))
    if not auth_path.exists():
        print(json.dumps({"error": "~/.config/publishing-house/auth.json not found"}))
        sys.exit(1)

    creds = json.loads(auth_path.read_text())
    api_key = creds.get("credential", "")
    central = creds.get("central", "").rstrip("/")
    if not api_key or not central:
        print(json.dumps({"error": "Missing credential or central in auth.json"}))
        sys.exit(1)

    spec_path = root / "publishing-house" / "spec.yaml"
    spec = yaml.safe_load(spec_path.read_text()) or {} if spec_path.exists() else {}
    project = spec.get("project", {})

    project_id = project.get("slug", "")
    if not project_id:
        print(json.dumps({"error": "project.slug missing in spec.yaml"}))
        sys.exit(1)
    wfid = project.get("workflow_id", "")
    epic_key = project.get("jira_ticket", "")
    jira_url = ""

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    headers = {"Authorization": f"Bearer {api_key}"}

    spec_changed = False

    if not wfid:
        try:
            req = urllib.request.Request(
                f"{central}/api/v1/projects/{project_id}/workflow-data",
                headers=headers,
            )
            with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
                wd = json.loads(r.read().decode())
            wfid = wd.get("workflow_id", "")
            wd_epic = wd.get("epic_key", "")
            jira_url = wd.get("jira_url", "")

            if wfid:
                spec.setdefault("project", {})["workflow_id"] = wfid
                spec_changed = True

            deployment_mode = project.get("deployment_mode", "self_published")
            if deployment_mode == "rhdp_published" and not epic_key and wd_epic:
                epic_key = wd_epic
                spec.setdefault("project", {})["jira_ticket"] = epic_key
                spec_changed = True

            if jira_url and deployment_mode == "rhdp_published":
                ci_path = root / "catalog-info.yaml"
                ci = yaml.safe_load(ci_path.read_text())
                links = ci.get("metadata", {}).get("links", [])
                has_jira = any(l.get("url") == jira_url for l in links)
                if not has_jira:
                    ci.setdefault("metadata", {}).setdefault("links", []).append(
                        {"url": jira_url, "title": "Jira Epic", "icon": "dashboard"}
                    )
                    with open(ci_path, "w") as f:
                        yaml.dump(ci, f, default_flow_style=False, sort_keys=False)
        except Exception as e:
            print(json.dumps({"error": f"Failed to fetch workflow data: {e}"}))
            sys.exit(1)

    if spec_changed:
        with open(spec_path, "w") as f:
            yaml.dump(spec, f, default_flow_style=False, sort_keys=False)

    stage = "intake"
    if wfid:
        try:
            req = urllib.request.Request(
                f"{central}/api/v1/projects/workflow-state/{wfid}",
                headers=headers,
            )
            with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
                st = json.loads(r.read().decode())
            stage = st.get("stage", "intake")
        except Exception as e:
            print(json.dumps({"error": f"Failed to fetch workflow state: {e}"}))
            sys.exit(1)

    print(f"stage:{stage}")
    print(f"workflow_id:{wfid}")
    print(f"epic_key:{epic_key}")
    print(f"jira_url:{jira_url}")


if __name__ == "__main__":
    main()
