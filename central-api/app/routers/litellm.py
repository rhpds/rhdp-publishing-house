"""LiteLLM system endpoints."""
import logging
from fastapi import APIRouter, Depends, HTTPException

from ..models import GenerateKeyRequest, GenerateKeyResponse
from ..services.litellm import LiteLLMService
from ..config import get_settings, Settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/litellm", tags=["LiteLLM"])


def get_litellm_service(settings: Settings = Depends(get_settings)) -> LiteLLMService:
    """Dependency to get LiteLLM service."""
    return LiteLLMService(settings.litellm_api_url, settings.litellm_master_key)


@router.post("/keys/generate", response_model=GenerateKeyResponse)
async def generate_litellm_key(
    request: GenerateKeyRequest,
    litellm: LiteLLMService = Depends(get_litellm_service),
    settings: Settings = Depends(get_settings)
):
    """Generate LiteLLM virtual key for a project."""
    litellm_key = await litellm.generate_key(request.project_id, request.user_email)
    if not litellm_key:
        raise HTTPException(status_code=503, detail="Failed to generate LiteLLM key")

    model = "claude-opus-4-6"

    return GenerateKeyResponse(
        project_id=request.project_id,
        litellm_key=litellm_key,
        litellm_endpoint=settings.litellm_api_url,
        litellm_model=model,
        message=f"LiteLLM key generated for {request.user_email}"
    )
