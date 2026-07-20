"""LiteLLM integration service."""
import httpx
import uuid
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class LiteLLMService:
    """Service for managing LiteLLM virtual keys."""

    def __init__(self, api_url: str, master_key: str):
        self.api_url = api_url.rstrip("/")
        self.master_key = master_key
        self.headers = {
            "Authorization": f"Bearer {master_key}",
            "Content-Type": "application/json"
        }

    async def generate_key(self, project_id: str, user_email: str, max_budget: float = 10.0) -> Optional[str]:
        short_id = uuid.uuid4().hex[:8]
        alias = f"ph-{project_id}-{short_id}"

        try:
            async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
                response = await client.post(
                    f"{self.api_url}/key/generate",
                    headers=self.headers,
                    json={
                        "key_alias": alias,
                        "user_id": user_email,
                        "max_budget": max_budget,
                        "budget_duration": "monthly",
                        "metadata": {
                            "project_id": project_id,
                            "created_by": "publishing-house-central",
                            "user": user_email
                        },
                        "models": ["claude-sonnet-4-6", "claude-opus-4-6"],
                        "spend": 0.0
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    key = data.get("key")
                    logger.info(f"Generated LiteLLM key alias={alias} for {user_email}: {key[:8]}...")
                    return key

                logger.error(f"Failed to generate LiteLLM key: {response.status_code} {response.text}")
                return None

        except Exception as e:
            logger.error(f"Error generating LiteLLM key: {e}")
            return None

    async def delete_key(self, key_id: str) -> bool:
        """
        Delete a LiteLLM virtual key.

        Args:
            key_id: The key ID to delete

        Returns:
            True if deletion succeeded, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
                response = await client.post(
                    f"{self.api_url}/key/delete",
                    headers=self.headers,
                    json={"key": key_id}
                )

                if response.status_code == 200:
                    logger.info(f"Deleted LiteLLM key: {key_id[:8]}...")
                    return True
                else:
                    logger.error(f"Failed to delete LiteLLM key: {response.status_code}")
                    return False

        except Exception as e:
            logger.error(f"Error deleting LiteLLM key: {e}")
            return False

    async def get_key_info(self, key_id: str) -> Optional[dict]:
        """
        Get information about a LiteLLM key.

        Args:
            key_id: The key ID to query

        Returns:
            Key information dict, or None if not found
        """
        try:
            async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
                response = await client.get(
                    f"{self.api_url}/key/info",
                    headers=self.headers,
                    params={"key": key_id}
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    return None

        except Exception as e:
            logger.error(f"Error getting LiteLLM key info: {e}")
            return None
