#!/usr/bin/env python3
"""Validate spec then advance workflow past intake by calling Central API.

1. POST /projects/{slug}/validate?stage=intake — server-side validation
2. POST /projects/intake/{slug} — advance workflow (only if validation passes)

Returns JSON: {"stage": "..."} on success, {"validation_errors": [...]} or {"error": "..."} on failure.
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

    # Step 1: Validate
    validate_url = f"{central_url}/api/v1/validate/{project_id}?stage=intake"
    validate_body = json.dumps({"repo_url": repo_url, "branch": "main"}).encode()
    req = urllib.request.Request(validate_url, data=validate_body, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            pass
    except urllib.error.HTTPError as e:
        body = json.loads(e.read().decode())
        if e.code == 422:
            print(json.dumps({"validation_errors": body.get("results", []), "passed": False}))
        else:
            print(json.dumps({"error": f"Validation failed ({e.code}): {json.dumps(body)[:300]}"}))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": f"Validation request failed: {e}"}))
        sys.exit(1)

    # Step 2: Advance workflow
    intake_url = f"{central_url}/api/v1/projects/intake/{project_id}"
    req = urllib.request.Request(intake_url, data=b"", headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        print(json.dumps({"error": f"Intake failed ({e.code}): {body}"}))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": f"Intake request failed: {e}"}))
        sys.exit(1)

    print(json.dumps(result))


if __name__ == "__main__":
    main()
