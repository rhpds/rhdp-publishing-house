#!/usr/bin/env python3
"""Submit development to Central API — validates and advances workflow.

POST /projects/development/{slug} with {"repo_url": ..., "branch": ...}

Central API validates development artifacts server-side, then advances the workflow
if validation passes.

Unified response shape for all outcomes:
  {"status": <int>, "stage": <str|null>, "error": <str|null>, "validation": <dict|null>}
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


def get_repo_url(root):
    catalog_path = root / "catalog-info.yaml"
    catalog = yaml.safe_load(catalog_path.read_text())
    slug = catalog.get("metadata", {}).get("annotations", {}).get("github.com/project-slug", "")
    if slug:
        return f"https://github.com/{slug}"
    links = catalog.get("metadata", {}).get("links", [])
    for link in links:
        if link.get("title") == "Repository":
            return link.get("url", "")
    return ""


def main():
    root = find_repo_root()
    if not root:
        print(json.dumps({"error": "catalog-info.yaml not found — not a Publishing House project"}))
        sys.exit(1)

    spec_path = root / "publishing-house" / "spec.yaml"
    if not spec_path.exists():
        print(json.dumps({"error": "publishing-house/spec.yaml not found"}))
        sys.exit(1)

    spec = yaml.safe_load(spec_path.read_text()) or {}
    project_id = spec.get("project", {}).get("slug", "")
    if not project_id:
        print(json.dumps({"error": "project.slug missing in spec.yaml"}))
        sys.exit(1)

    repo_url = get_repo_url(root)
    if not repo_url:
        print(json.dumps({"error": "Could not determine repo URL from catalog-info.yaml"}))
        sys.exit(1)

    auth_path = Path(os.path.expanduser("~/.config/publishing-house/auth.json"))
    if not auth_path.exists():
        print(json.dumps({"error": "~/.config/publishing-house/auth.json not found — run the orchestrator skill first"}))
        sys.exit(1)

    creds = json.loads(auth_path.read_text())
    api_key = creds.get("credential", "")
    if not api_key:
        print(json.dumps({"error": "No credential in auth.json"}))
        sys.exit(1)

    central_url = creds.get("central", "").rstrip("/")
    if not central_url:
        print(json.dumps({"error": "No portal URL in auth.json"}))
        sys.exit(1)

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    dev_url = f"{central_url}/api/v1/projects/development/{project_id}"
    dev_body = json.dumps({"repo_url": repo_url, "branch": "main"}).encode()
    req = urllib.request.Request(dev_url, data=dev_body, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        result = json.loads(e.read().decode())
    except Exception as e:
        result = {"status": 500, "error": f"Request failed: {e}"}

    print(json.dumps(result))

    if result.get("status", 500) >= 400:
        sys.exit(1)


if __name__ == "__main__":
    main()
