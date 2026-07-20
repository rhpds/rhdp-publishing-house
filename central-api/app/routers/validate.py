"""Validate router — server-side spec validation endpoint."""
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..config import get_settings
from ..services.github import GitHubService
from ..services.validation.models import ValidationRequest, ValidationResponse
from ..services.validation.runner import run_validation

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["validate"])
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


@router.post(
    "/{slug}/validate",
    response_model=ValidationResponse,
    responses={422: {"model": ValidationResponse}},
)
async def validate_spec(
    slug: str,
    body: ValidationRequest,
    stage: str = Query("intake", description="Pipeline stage: intake, review"),
    owner: str = Depends(_require_auth),
):
    """Validate a project spec against the configured policy.

    Returns 200 if all checks pass, 422 if any check fails."""
    settings = get_settings()
    if not settings.github_token:
        raise HTTPException(status_code=500, detail="GITHUB_TOKEN not configured on Central API")

    github = GitHubService(token=settings.github_token)
    result = await run_validation(github, body.repo_url, body.branch, stage)

    if not result.passed:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=422, content=result.model_dump())

    return result
