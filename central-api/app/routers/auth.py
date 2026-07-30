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


# ── OIDC config (static page fetches Keycloak params for JS SDK) ─────────────

@router.get("/keys/oidc/config")
async def oidc_config():
    settings = get_settings()
    if not settings.oidc_issuer_url or not settings.oidc_client_id:
        raise HTTPException(status_code=503, detail="OIDC not configured")
    url = settings.oidc_issuer_url.rstrip("/")
    parts = url.rsplit("/realms/", 1)
    base_url = parts[0] if len(parts) == 2 else url
    realm = parts[1] if len(parts) == 2 else ""
    return {"url": base_url, "realm": realm, "clientId": settings.oidc_client_id}


# ── OIDC direct key (browser sends Keycloak token, gets signed key) ──────────

@router.post("/keys/oidc")
async def oidc_key(
    credentials: HTTPAuthorizationCredentials = Security(HTTPBearer()),
):
    validator = get_oidc_validator()
    if not validator:
        raise HTTPException(status_code=503, detail="OIDC not configured")

    result = await validator.validate_token_string(credentials.credentials)
    email = result["email"]
    mask = compute_bitmask(result["groups"])
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
@router.post("/keys/exchange/", response_model=ExchangeResponse, include_in_schema=False)
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

async def _validate_ocp_token(token: str) -> str | None:
    """Verify an OCP user token via the User API and return the username (email)."""
    try:
        async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
            resp = await client.get(
                "https://kubernetes.default.svc/apis/user.openshift.io/v1/users/~",
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code != 200:
                logger.warning("OCP User API returned %s", resp.status_code)
                return None

            username = resp.json().get("metadata", {}).get("name", "")
            if not username or username.startswith("system:"):
                logger.warning("OCP User API: rejected non-user identity %s", username)
                return None
            logger.info("OCP User API OK: %s", username)
            return username
    except Exception as exc:
        logger.error("OCP User API failed: %s", exc)
        return None


@router.post("/keys/anonymous", response_model=WorkspaceResponse)
async def anonymous_key(
    credentials: HTTPAuthorizationCredentials = Security(HTTPBearer()),
):
    token = credentials.credentials
    email = await _validate_ocp_token(token)
    if not email:
        raise HTTPException(status_code=401, detail="Invalid OpenShift token")

    mask = lookup_user_groups(email)
    signed = create_signed_key(email, mask)

    logger.info("workspace key created for %s (mask=%d)", email, mask)
    return WorkspaceResponse(api_key=signed, user_email=email)
