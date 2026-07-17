"""Workspace setup endpoint — auth bootstrap for DevSpaces."""
import logging
import httpx
from fastapi import APIRouter, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from ..config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workspace", tags=["Workspace"])
security = HTTPBearer()


class WorkspaceSetupRequest(BaseModel):
    username: str = Field(..., description="Username extracted from DevSpaces namespace")


class WorkspaceSetupResponse(BaseModel):
    api_key: str
    user_email: str


async def _validate_sa_token(token: str) -> bool:
    """Validate a service account token via Kubernetes TokenReview."""
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

            status = resp.json().get("status", {})
            if not status.get("authenticated", False):
                logger.warning("TokenReview: token not authenticated")
                return False

            logger.info("TokenReview OK: %s", status.get("user", {}).get("username", "?"))
            return True

    except Exception as exc:
        logger.error("TokenReview failed: %s", exc)
        return False


@router.post("/setup", response_model=WorkspaceSetupResponse)
async def workspace_setup(
    request: WorkspaceSetupRequest,
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """
    Bootstrap auth for a DevSpaces workspace.

    The devfile calls this with the devworkspace-sa token and the username
    extracted from the namespace. Returns a central-api credential the
    devfile can use for subsequent calls (e.g. LiteLLM key generation).
    """
    if not await _validate_sa_token(credentials.credentials):
        raise HTTPException(status_code=401, detail="Invalid service account token")

    settings = get_settings()
    user_email = f"{request.username}@redhat.com"

    logger.info("Workspace setup for user=%s", user_email)

    return WorkspaceSetupResponse(
        api_key=settings.ph_api_key,
        user_email=user_email,
    )
