#!/usr/bin/env python3
"""Advance workflow past intake by calling Central API.

Reads project slug from spec.yaml, POSTs to Central intake endpoint.
Returns {"stage": "..."} on success or {"error": "..."} on failure.
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

    spec_path = root / "publishing-house" / "spec.yaml"

    if not spec_path.exists():
        print(json.dumps({"error": "publishing-house/spec.yaml not found"}))
        sys.exit(1)

    spec = yaml.safe_load(spec_path.read_text()) or {}
    project = spec.get("project", {})

    project_id = project.get("slug", "")
    if not project_id:
        print(json.dumps({"error": "project.slug missing in spec.yaml"}))
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

    url = f"{central_url}/api/v1/projects/intake/{project_id}"
    req = urllib.request.Request(
        url,
        data=b"",
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
        print(json.dumps({"error": f"Central API returned {e.code}: {body}"}))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": f"Request failed: {e}"}))
        sys.exit(1)

    print(json.dumps(result))


if __name__ == "__main__":
    main()
