"""Group bitmask constants and Backstage catalog group lookup."""
import base64
import hashlib
import hmac
import json
import logging
import ssl
import time
import urllib.request
from typing import Optional

from ..config import get_settings

logger = logging.getLogger(__name__)

GROUP_BITS = {
    "rhdp-content-review": 1,
    "rhdp-infra-review": 2,
    "rhdp-developers": 4,
    "rhdp-administrators": 8,
}

ALL_GROUPS_MASK = 0xFF

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def compute_bitmask(group_names: list[str]) -> int:
    mask = 0
    for g in group_names:
        mask |= GROUP_BITS.get(g, 0)
    return mask


def lookup_user_groups(email: str) -> int:
    """Query Backstage catalog API for user's group memberships, return bitmask."""
    settings = get_settings()
    if not settings.rhdh_service_token or not settings.rhdh_internal_url:
        logger.warning("RHDH_SERVICE_TOKEN or RHDH_INTERNAL_URL not configured, returning 0")
        return 0

    username = email.split("@")[0]
    url = f"{settings.rhdh_internal_url.rstrip('/')}/api/catalog/entities/by-name/user/default/{username}"
    headers = {
        "Authorization": f"Bearer {settings.rhdh_service_token}",
        "Accept": "application/json",
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=10) as r:
            entity = json.loads(r.read().decode())

        relations = entity.get("relations", [])
        groups = []
        for rel in relations:
            if rel.get("type") == "memberOf":
                target = rel.get("targetRef", "")
                if target.startswith("group:default/"):
                    groups.append(target.removeprefix("group:default/"))

        mask = compute_bitmask(groups)
        logger.info("groups for %s: %s → bitmask=%d", email, groups, mask)
        return mask
    except urllib.error.HTTPError as e:
        if e.code == 404:
            logger.warning("user %s not found in Backstage catalog", username)
            return 0
        logger.error("catalog lookup failed for %s: %s", email, e)
        return 0
    except Exception as e:
        logger.error("catalog lookup failed for %s: %s", email, e)
        return 0


# ── Signed bitmask token helpers ─────────────────────────────────────────────


def create_signed_key(email: str, groups_bitmask: int) -> str:
    """Create an HMAC-signed token embedding email, groups bitmask, and expiry."""
    settings = get_settings()
    exp = int(time.time()) + settings.api_key_ttl_days * 86400
    payload = f"{email}|{groups_bitmask}|{exp}"
    payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    sig = hmac.new(
        settings.ph_api_key.encode(), payload_b64.encode(), hashlib.sha256
    ).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).decode().rstrip("=")
    return f"{payload_b64}.{sig_b64}"


def decode_signed_key(token: str) -> Optional[tuple[str, int]]:
    """Decode and verify a signed bitmask token. Returns (email, bitmask) or None."""
    settings = get_settings()
    parts = token.split(".")
    if len(parts) != 2:
        return None

    payload_b64, sig_b64 = parts

    # Verify HMAC
    expected_sig = hmac.new(
        settings.ph_api_key.encode(), payload_b64.encode(), hashlib.sha256
    ).digest()
    expected_sig_b64 = base64.urlsafe_b64encode(expected_sig).decode().rstrip("=")
    if not hmac.compare_digest(sig_b64, expected_sig_b64):
        return None

    # Decode payload (add padding back)
    padded = payload_b64 + "=" * (-len(payload_b64) % 4)
    try:
        payload = base64.urlsafe_b64decode(padded).decode()
    except Exception:
        return None

    segments = payload.split("|")
    if len(segments) != 3:
        return None

    email, mask_str, exp_str = segments
    try:
        mask = int(mask_str)
        exp = int(exp_str)
    except ValueError:
        return None

    from .token_cache import is_token_in_cache
    if not is_token_in_cache(token, email):
        return None

    return email, mask
