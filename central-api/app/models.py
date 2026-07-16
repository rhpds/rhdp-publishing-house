"""Data models for Central API."""
from pydantic import BaseModel, Field
from datetime import datetime


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    timestamp: datetime


class GenerateKeyRequest(BaseModel):
    """Request model for generating LiteLLM key."""
    project_id: str = Field(..., description="Project ID")
    user_email: str = Field(..., description="User email address")


class GenerateKeyResponse(BaseModel):
    """Response model for LiteLLM key generation."""
    project_id: str
    litellm_key: str
    litellm_endpoint: str
    litellm_model: str
    message: str
