"""RCARS catalog client for cross-cluster access.

Uses permanent API key auth (X-API-Key header).
Key is stored in RCARS_API_KEY env var, sourced from the rcars-api-key K8s secret.

Production API route (direct, no oauth-proxy):
  rcars-api.apps.ocpv-infra01.dal12.infra.demo.redhat.com

Create/manage API keys at:
  https://rcars.apps.ocpv-infra01.dal12.infra.demo.redhat.com/system/api-keys
"""
import json
import logging
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

from ..config import get_settings

logger = logging.getLogger(__name__)

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def _get_headers() -> dict:
    """Build auth headers for RCARS API calls using permanent API key."""
    settings = get_settings()
    headers = {"Content-Type": "application/json"}
    if settings.rcars_api_key:
        headers["X-API-Key"] = settings.rcars_api_key
    return headers


def _get_base_url() -> str:
    return get_settings().rcars_url.rstrip("/")


def rcars_health() -> dict:
    """Check RCARS health. Returns {status: ok} or {status: unavailable, error: ...}."""
    try:
        url = f"{_get_base_url()}/api/v1/health"
        req = urllib.request.Request(url, headers=_get_headers())
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=5) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        logger.warning("RCARS health check failed: %s", e)
        return {"status": "unavailable", "error": str(e)}


def rcars_catalog_search(
    query: Optional[str] = None,
    products: Optional[list[str]] = None,
    limit: int = 10,
    offset: int = 0,
) -> dict:
    """Search RCARS catalog. Returns {items: [...], total: N}."""
    params = f"?limit={limit}&offset={offset}"
    if query:
        params += f"&q={urllib.parse.quote(query)}"
    if products:
        for p in products:
            params += f"&product={urllib.parse.quote(p)}"

    url = f"{_get_base_url()}/api/v1/catalog{params}"
    req = urllib.request.Request(url, headers=_get_headers())
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=15) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        logger.error("RCARS catalog search failed %s: %s", e.code, e.read().decode()[:200])
        return {"items": [], "total": 0, "error": f"HTTP {e.code}"}
    except Exception as e:
        logger.error("RCARS catalog search error: %s", e)
        return {"items": [], "total": 0, "error": str(e)}


def rcars_advisor_submit(query: str, stages: list[str] | None = None) -> dict:
    """Submit an advisor query to RCARS. Returns {job_id} or {error}."""
    try:
        body = {"query": query}
        if stages:
            body["stages"] = stages
        url = f"{_get_base_url()}/api/v1/advisor/query"
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode(),
            headers=_get_headers(),
            method="POST",
        )
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        logger.warning("RCARS advisor submit failed: %s", e)
        return {"error": str(e)}


def rcars_advisor_result(job_id: str) -> dict:
    """Poll for advisor query result. Returns {status, result, error}."""
    try:
        url = f"{_get_base_url()}/api/v1/advisor/query/{urllib.parse.quote(job_id)}/result"
        req = urllib.request.Request(url, headers=_get_headers())
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        logger.warning("RCARS advisor result failed for %s: %s", job_id, e)
        return {"status": "failed", "error": str(e)}


def rcars_catalog_item(ci_name: str) -> dict:
    """Fetch a single catalog item by identifier. Returns full item including workloads."""
    try:
        url = f"{_get_base_url()}/api/v1/catalog/{urllib.parse.quote(ci_name)}"
        req = urllib.request.Request(url, headers=_get_headers())
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=15) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        logger.error("RCARS catalog item fetch failed %s: %s", e.code, e.read().decode()[:200])
        return {"error": f"HTTP {e.code}"}
    except Exception as e:
        logger.error("RCARS catalog item error for %s: %s", ci_name, e)
        return {"error": str(e)}


