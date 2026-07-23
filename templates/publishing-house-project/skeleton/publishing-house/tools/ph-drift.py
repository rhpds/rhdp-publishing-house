#!/usr/bin/env python3
"""ph-drift.py — Check for spec contract drift between approved SHA and HEAD.

Usage:
  python publishing-house/tools/ph-drift.py APPROVED_SHA
"""
import json
import os
import ssl
import sys
import urllib.request
import urllib.error
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
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: ph-drift.py APPROVED_SHA"}))
        sys.exit(1)

    approved_sha = sys.argv[1]

    root = find_repo_root()
    if not root:
        print(json.dumps({"error": "Not a Publishing House project — catalog-info.yaml not found"}))
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
        print(json.dumps({"error": "~/.config/publishing-house/auth.json not found"}))
        sys.exit(1)

    creds = json.loads(auth_path.read_text())
    api_key = creds.get("credential", "")
    central_url = creds.get("central", "").rstrip("/")
    if not api_key or not central_url:
        print(json.dumps({"error": "Missing credential or central URL in auth.json"}))
        sys.exit(1)

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    url = f"{central_url}/api/v1/spec/drift/{project_id}"
    body = json.dumps({
        "repo_url": repo_url,
        "branch": "main",
        "approved_sha": approved_sha,
    }).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err = json.loads(e.read().decode())
        print(json.dumps({"error": f"Drift check failed: {err}"}))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": f"Central API unreachable: {e}"}))
        sys.exit(1)

    print(json.dumps(data))
    if data.get("has_drift"):
        sys.exit(1)


if __name__ == "__main__":
    main()
