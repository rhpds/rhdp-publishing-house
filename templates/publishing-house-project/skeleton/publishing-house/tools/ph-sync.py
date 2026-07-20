#!/usr/bin/env python3
"""Sync workflow data to local files. Used by intake/development skills.

Calls /workflow-data and /workflow-state, then writes workflow_id, epic_key,
and jira link back to spec.yaml and catalog-info.yaml.

Output: key:value pairs, one per line
  stage:intake
  workflow_id:abc-123
  epic_key:RHDPCD-456
  synced:true|false
"""
import json
import os
import re
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


def set_yaml_value(filepath, dotted_key, value):
    """Update a single value in a YAML file without rewriting the entire file."""
    text = filepath.read_text()
    keys = dotted_key.split(".")
    if len(keys) == 2:
        section, field = keys
        pattern = re.compile(
            rf'^(\s*){re.escape(field)}:\s*"?.*"?\s*$', re.MULTILINE
        )
        in_section = False
        lines = text.split("\n")
        new_lines = []
        replaced = False
        for line in lines:
            if re.match(rf'^{re.escape(section)}:\s*$', line):
                in_section = True
                new_lines.append(line)
                continue
            if in_section and not replaced:
                m = pattern.match(line)
                if m:
                    indent = m.group(1)
                    new_lines.append(f'{indent}{field}: "{value}"')
                    replaced = True
                    continue
                if line and not line[0].isspace() and line[0] != "#":
                    in_section = False
            new_lines.append(line)
        if replaced:
            filepath.write_text("\n".join(new_lines))
            return True
    return False


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

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    headers = {"Authorization": f"Bearer {api_key}"}

    synced = False

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

            if wfid:
                set_yaml_value(spec_path, "project.workflow_id", wfid)
                synced = True

            deployment_mode = project.get("deployment_mode", "self_published")
            if deployment_mode == "rhdp_published" and not epic_key and wd_epic:
                epic_key = wd_epic
                set_yaml_value(spec_path, "project.jira_ticket", epic_key)
                synced = True
        except Exception as e:
            print(json.dumps({"error": f"Failed to fetch workflow data: {e}"}))
            sys.exit(1)

    if epic_key:
        jira_url = f"https://redhat.atlassian.net/browse/{epic_key}"
        deployment_mode = project.get("deployment_mode", "self_published")
        if deployment_mode == "rhdp_published":
            ci_path = root / "catalog-info.yaml"
            ci_text = ci_path.read_text()
            if jira_url not in ci_text:
                ci = yaml.safe_load(ci_text)
                links = ci.get("metadata", {}).get("links", [])
                links.append(
                    {"url": jira_url, "title": "Jira Epic", "icon": "dashboard"}
                )
                ci.setdefault("metadata", {})["links"] = links
                with open(ci_path, "w") as f:
                    yaml.dump(ci, f, default_flow_style=False, sort_keys=False)
                synced = True

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
    print(f"synced:{str(synced).lower()}")


if __name__ == "__main__":
    main()
