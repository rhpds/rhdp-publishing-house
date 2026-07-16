"""LiteLLM integration service."""
import httpx
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
        alias = f"ph-{project_id}-{user_email.split('@')[0]}"

        existing = await self._get_key_by_alias(alias)
        if existing:
            logger.info(f"Returning existing key for alias {alias}: {existing[:8]}...")
            return existing

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
                        "models": ["claude-opus-4-6"],
                        "spend": 0.0
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    key_id = data.get("key")
                    logger.info(f"Generated LiteLLM key for project {project_id}: {key_id[:8]}...")
                    return key_id

                if response.status_code == 400 and "already exists" in response.text:
                    logger.info(f"Key alias {alias} created between check and generate, retrieving")
                    return await self._get_key_by_alias(alias)

                logger.error(f"Failed to generate LiteLLM key: {response.status_code} {response.text}")
                return None

        except Exception as e:
            logger.error(f"Error generating LiteLLM key: {e}")
            return None

    async def _get_key_by_alias(self, alias: str) -> Optional[str]:
        """Retrieve an existing key token by its alias."""
        try:
            async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
                response = await client.get(
                    f"{self.api_url}/key/info",
                    headers=self.headers,
                    params={"key_alias": alias}
                )
                if response.status_code == 200:
                    data = response.json()
                    token = data.get("info", {}).get("token") or data.get("key")
                    if token:
                        logger.info(f"Retrieved existing key for alias {alias}: {token[:8]}...")
                        return token
                return None
        except Exception as e:
            logger.error(f"Error retrieving key by alias {alias}: {e}")
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
