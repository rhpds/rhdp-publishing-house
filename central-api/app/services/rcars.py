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


def rcars_overlap_check(
    products: list[str],
    audience: str = "",
    limit: int = 5,
) -> dict:
    """Check overlap with existing RCARS content by products + audience.

    Used by the intake endpoint to auto-compute rcars_overlap_pct and
    rcars_top_matches for the approval_checklist.content_lead section.

    Returns:
        {
            overlap_pct: float (0-100),
            top_matches: [{ci_name, display_name, url}]
        }
    """
    try:
        params = f"?limit={limit}"
        for p in products:
            params += f"&product={urllib.parse.quote(p)}"
        if audience:
            params += f"&audience={urllib.parse.quote(audience)}"

        url = f"{_get_base_url()}/api/v1/catalog{params}"
        req = urllib.request.Request(url, headers=_get_headers())
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=15) as r:
            data = json.loads(r.read().decode())

        items = data.get("items", [])
        total = data.get("total", len(items))

        top_matches = [
            {
                "ci_name": item.get("ci_name", ""),
                "display_name": item.get("display_name", ""),
                "url": f"https://catalog.demo.redhat.com/catalog?item={item.get('ci_name', '')}",
            }
            for item in items[:3]
        ]

        overlap_pct = min(100.0, (len(items) / max(1, total)) * 100) if items else 0.0

        return {
            "overlap_pct": round(overlap_pct, 1),
            "top_matches": top_matches,
        }
    except Exception as e:
        logger.warning("RCARS overlap check failed: %s", e)
        return {"overlap_pct": 0.0, "top_matches": [], "error": str(e)}
