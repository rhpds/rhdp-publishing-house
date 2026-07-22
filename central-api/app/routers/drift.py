"""Drift router — spec contract drift detection endpoint."""
import logging

from fastapi import APIRouter, Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..config import get_settings
from ..services.github import GitHubService
from ..services.drift import DriftRequest, DriftResponse, check_drift

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/spec/drift", tags=["drift"])
_bearer = HTTPBearer(auto_error=False)


def _require_auth(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> str:
    settings = get_settings()
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
    if credentials.credentials == settings.ph_api_key:
        return "service"

    from .projects import lookup_key
    rec = lookup_key(credentials.credentials)
    if not rec:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return rec.owner_email


@router.post("/{slug}", response_model=DriftResponse)
async def detect_drift(
    slug: str,
    body: DriftRequest,
    owner: str = Depends(_require_auth),
):
    """Compare spec contract fields at approved SHA vs current HEAD."""
    settings = get_settings()
    if not settings.github_token:
        raise HTTPException(status_code=500, detail="GITHUB_TOKEN not configured on Central API")

    github = GitHubService(token=settings.github_token)
    return await check_drift(github, body.repo_url, body.branch, body.approved_sha)
