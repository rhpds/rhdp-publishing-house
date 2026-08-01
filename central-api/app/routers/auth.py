"""Auth router — key management, token exchange, workspace setup, token management."""
import base64
import json
import logging
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from ..auth.oidc import get_oidc_validator
from ..auth.groups import (
    GROUP_BITS, ALL_GROUPS_MASK,
    compute_bitmask, lookup_user_groups, create_signed_key, decode_signed_key,
)
from ..auth.token_cache import (
    cache_token, get_cached_token,
    revoke_token, revoke_all_tokens, list_tokens, search_tokens,
)
from ..config import get_settings

logger = logging.getLogger(__name__)
audit = logging.getLogger("ph.audit")
router = APIRouter(prefix="/auth", tags=["auth"])
_bearer = HTTPBearer(auto_error=False)


def _token_expiry_iso(token: str) -> str:
    padded = token.split(".")[0] + "=" * (-len(token.split(".")[0]) % 4)
    payload = base64.urlsafe_b64decode(padded).decode()
    exp = int(payload.split("|")[2])
    return datetime.fromtimestamp(exp, tz=timezone.utc).isoformat()


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
    cache_token(email, token, mask, "oidc")

    return ExchangeResponse(
        token=token, email=email,
        groups_bitmask=mask, expires_at=_token_expiry_iso(token),
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

    cached = get_cached_token(email)
    if cached is not None:
        audit.info(json.dumps({
            "audit": "token_cached_hit", "email": email,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))
        return ExchangeResponse(
            token=cached.token, email=email,
            groups_bitmask=cached.groups_bitmask,
            expires_at=_token_expiry_iso(cached.token),
        )

    token = create_signed_key(email, mask)
    cache_token(email, token, mask, "exchange")

    return ExchangeResponse(
        token=token, email=email,
        groups_bitmask=mask, expires_at=_token_expiry_iso(token),
    )


# ── Workspace setup (SA token → signed key, replaces /workspace/setup) ──────

def _extract_namespace_from_jwt(token: str) -> str | None:
    """Decode SA JWT and return the namespace claim."""
    try:
        padded = token.split(".")[1] + "=" * (-len(token.split(".")[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded))
        return claims.get("kubernetes.io/serviceaccount/namespace") or claims.get("kubernetes.io", {}).get("namespace")
    except Exception:
        return None


async def _resolve_devspaces_user(token: str) -> str | None:
    """Extract namespace from SA token, read user-profile secret using caller's token."""
    namespace = _extract_namespace_from_jwt(token)
    if not namespace:
        logger.warning("could not extract namespace from token")
        return None

    logger.info("SA token namespace: %s", namespace)
    try:
        async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
            resp = await client.get(
                f"https://kubernetes.default.svc/api/v1/namespaces/{namespace}/secrets/user-profile",
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code != 200:
                logger.warning("user-profile secret lookup returned %s", resp.status_code)
                return None

            import base64 as b64mod
            data = resp.json().get("data", {})
            raw = data.get("name") or data.get("email")
            if not raw:
                logger.warning("user-profile secret has no name/email field")
                return None

            email = b64mod.b64decode(raw).decode().strip()
            if email.endswith("@che"):
                email = email.removesuffix("@che")
            logger.info("DevSpaces user-profile: %s", email)
            return email
    except Exception as exc:
        logger.error("user-profile lookup failed: %s", exc)
        return None


@router.post("/keys/anonymous", response_model=WorkspaceResponse)
async def anonymous_key(
    credentials: HTTPAuthorizationCredentials = Security(HTTPBearer()),
):
    token = credentials.credentials
    email = await _resolve_devspaces_user(token)
    if not email:
        raise HTTPException(status_code=401, detail="Invalid OpenShift token")

    cached = get_cached_token(email)
    if cached is not None:
        audit.info(json.dumps({
            "audit": "token_cached_hit", "email": email,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))
        logger.info("workspace key cache hit for %s", email)
        return WorkspaceResponse(api_key=cached.token, user_email=email)

    mask = lookup_user_groups(email)
    signed = create_signed_key(email, mask)
    cache_token(email, signed, mask, "anonymous")

    logger.info("workspace key created for %s (mask=%d)", email, mask)
    return WorkspaceResponse(api_key=signed, user_email=email)


# ── Token management (admin-only) ─────────────────────────────────────────


def _require_auth(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> tuple[str, int]:
    settings = get_settings()
    if not credentials:
        raise HTTPException(status_code=401, detail="Bearer token required")
    token = credentials.credentials
    if token == settings.ph_api_key:
        return "service", ALL_GROUPS_MASK
    result = decode_signed_key(token)
    if result:
        return result
    raise HTTPException(status_code=401, detail="Invalid API key")


def _require_group(groups: int, required: int, group_name: str):
    if not (groups & required):
        raise HTTPException(status_code=403, detail=f"Requires membership in {group_name}")


class TokenInfo(BaseModel):
    email: str
    groups_bitmask: int
    group_names: list[str]
    issued_at: str
    expires_at: str
    source: str


class TokenListResponse(BaseModel):
    tokens: list[TokenInfo]
    count: int


class RevokeResponse(BaseModel):
    revoked: bool
    email: str | None = None


class RevokeAllResponse(BaseModel):
    revoked_count: int


def _to_token_info(entry: dict) -> TokenInfo:
    names = [g for g, b in GROUP_BITS.items() if entry["groups_bitmask"] & b]
    return TokenInfo(
        email=entry["email"],
        groups_bitmask=entry["groups_bitmask"],
        group_names=names,
        issued_at=datetime.fromtimestamp(entry["issued_at"], tz=timezone.utc).isoformat(),
        expires_at=datetime.fromtimestamp(entry["expires"], tz=timezone.utc).isoformat(),
        source=entry.get("source", "unknown"),
    )


@router.get("/tokens", response_model=TokenListResponse)
async def get_active_tokens(auth: tuple[str, int] = Depends(_require_auth)):
    _, groups = auth
    _require_group(groups, GROUP_BITS["rhdp-administrators"], "rhdp-administrators")
    entries = list_tokens()
    tokens = [_to_token_info(e) for e in entries]
    return TokenListResponse(tokens=tokens, count=len(tokens))


@router.get("/tokens/search", response_model=TokenListResponse)
async def search_active_tokens(
    q: str = Query(..., min_length=1),
    auth: tuple[str, int] = Depends(_require_auth),
):
    _, groups = auth
    _require_group(groups, GROUP_BITS["rhdp-administrators"], "rhdp-administrators")
    entries = search_tokens(q)
    tokens = [_to_token_info(e) for e in entries]
    return TokenListResponse(tokens=tokens, count=len(tokens))


@router.delete("/tokens/{email}", response_model=RevokeResponse)
async def revoke_user_token(
    email: str,
    auth: tuple[str, int] = Depends(_require_auth),
):
    _, groups = auth
    _require_group(groups, GROUP_BITS["rhdp-administrators"], "rhdp-administrators")
    removed = revoke_token(email)
    return RevokeResponse(revoked=removed, email=email)


@router.delete("/tokens", response_model=RevokeAllResponse)
async def revoke_all_active_tokens(auth: tuple[str, int] = Depends(_require_auth)):
    _, groups = auth
    _require_group(groups, GROUP_BITS["rhdp-administrators"], "rhdp-administrators")
    count = revoke_all_tokens()
    return RevokeAllResponse(revoked_count=count)
