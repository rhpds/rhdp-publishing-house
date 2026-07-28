"""Auth router — key management, token exchange, workspace setup."""
import base64
import json
import logging

import httpx
from fastapi import APIRouter, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from ..auth.oidc import get_oidc_validator
from ..auth.groups import (
    GROUP_BITS, ALL_GROUPS_MASK,
    compute_bitmask, lookup_user_groups, create_signed_key, decode_signed_key,
)
from ..config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
_bearer = HTTPBearer(auto_error=False)


# ── Schemas ──────────────────────────────────────────────────────────────────

class ExchangeRequest(BaseModel):
    keycloak_token: str | None = None
    backstage_token: str | None = None


class ExchangeResponse(BaseModel):
    token: str
    email: str
    groups_bitmask: int
    expires_at: str


class WorkspaceResponse(BaseModel):
    api_key: str
    user_email: str


# ── Token exchange (plugin sends Keycloak token, gets signed bitmask key) ───

def _decode_jwt_payload(token: str) -> dict:
    """Decode a JWT payload without signature verification."""
    parts = token.split(".")
    if len(parts) < 2:
        raise HTTPException(status_code=400, detail="Malformed token")
    padded = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(padded))
    except Exception:
        raise HTTPException(status_code=400, detail="Cannot decode token payload")


@router.post("/keys/exchange", response_model=ExchangeResponse)
async def exchange_token(
    body: ExchangeRequest,
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
):
    settings = get_settings()
    if not credentials or credentials.credentials != settings.ph_api_key:
        raise HTTPException(status_code=401, detail="Master key required")

    if not body.keycloak_token and not body.backstage_token:
        raise HTTPException(status_code=400, detail="keycloak_token or backstage_token required")

    if body.keycloak_token:
        validator = get_oidc_validator()
        if not validator:
            raise HTTPException(status_code=503, detail="OIDC not configured")
        result = await validator.validate_token_string(body.keycloak_token)
        email = result["email"]
        mask = compute_bitmask(result["groups"])
    else:
        claims = _decode_jwt_payload(body.backstage_token)
        sub = claims.get("sub", "")
        ent = claims.get("ent", [])

        if not sub.startswith("user:default/"):
            raise HTTPException(status_code=400, detail="Invalid backstage token sub claim")

        username = sub.removeprefix("user:default/")
        email = f"{username}@redhat.com"
        groups = [ref.removeprefix("group:default/") for ref in ent if ref.startswith("group:default/")]
        mask = compute_bitmask(groups)
        logger.info("backstage exchange for %s: groups=%s mask=%d", email, groups, mask)

    token = create_signed_key(email, mask)

    padded = token.split(".")[0] + "=" * (-len(token.split(".")[0]) % 4)
    payload = base64.urlsafe_b64decode(padded).decode()
    expiry = payload.split("|")[2]

    from datetime import datetime, timezone
    exp_dt = datetime.fromtimestamp(int(expiry), tz=timezone.utc)

    return ExchangeResponse(
        token=token,
        email=email,
        groups_bitmask=mask,
        expires_at=exp_dt.isoformat(),
    )


# ── Workspace setup (SA token → signed key, replaces /workspace/setup) ──────

async def _validate_sa_token(token: str) -> bool:
    try:
        with open("/var/run/secrets/kubernetes.io/serviceaccount/token", "r") as f:
            server_token = f.read().strip()
    except FileNotFoundError:
        logger.error("No service account token found — not running in-cluster")
        return False

    try:
        async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
            resp = await client.post(
                "https://kubernetes.default.svc/apis/authentication.k8s.io/v1/tokenreviews",
                headers={
                    "Authorization": f"Bearer {server_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "apiVersion": "authentication.k8s.io/v1",
                    "kind": "TokenReview",
                    "spec": {"token": token},
                },
            )
            if resp.status_code != 201:
                logger.error("TokenReview HTTP %s: %s", resp.status_code, resp.text)
                return False

            tr_status = resp.json().get("status", {})
            if not tr_status.get("authenticated", False):
                logger.warning("TokenReview: token not authenticated")
                return False

            logger.info("TokenReview OK: %s", tr_status.get("user", {}).get("username", "?"))
            return True
    except Exception as exc:
        logger.error("TokenReview failed: %s", exc)
        return False


def _extract_namespace_from_jwt(token: str) -> str:
    """Decode SA token JWT payload (no verification) and extract namespace."""
    parts = token.split(".")
    if len(parts) < 2:
        raise HTTPException(status_code=400, detail="Malformed SA token")
    padded = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(padded))
    except Exception:
        raise HTTPException(status_code=400, detail="Cannot decode SA token payload")
    ns = payload.get("kubernetes.io/serviceaccount/namespace", "")
    if not ns:
        raise HTTPException(status_code=400, detail="SA token missing namespace claim")
    return ns


@router.post("/keys/anonymous", response_model=WorkspaceResponse)
async def anonymous_key(
    credentials: HTTPAuthorizationCredentials = Security(HTTPBearer()),
):
    token = credentials.credentials
    if not await _validate_sa_token(token):
        raise HTTPException(status_code=401, detail="Invalid service account token")

    ns = _extract_namespace_from_jwt(token)
    # Namespace format: treddy-redhat-com-devspaces
    username = ns.removesuffix("-devspaces").removesuffix("-redhat-com")
    email = f"{username}@redhat.com"

    mask = lookup_user_groups(email)
    signed = create_signed_key(email, mask)

    logger.info("workspace key created for %s (ns=%s, mask=%d)", email, ns, mask)
    return WorkspaceResponse(api_key=signed, user_email=email)
