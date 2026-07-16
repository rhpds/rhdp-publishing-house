"""SonataFlow integration service."""
import httpx
from cloudevents.http import CloudEvent
from cloudevents.conversion import to_structured
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class SonataFlowService:
    """Service for SonataFlow workflow operations."""

    def __init__(self, base_url: str, workflow_id: str):
        self.base_url = base_url.rstrip("/")
        self.workflow_id = workflow_id

    async def create_instance(self, project_data: dict) -> Optional[str]:
        """
        Create a new workflow instance.

        Args:
            project_data: Initial workflow data (project_id, repo_url, etc.)

        Returns:
            Workflow instance ID, or None if creation fails
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/{self.workflow_id}",
                    json=project_data
                )

                if response.status_code in [200, 201]:
                    data = response.json()
                    instance_id = data.get("id")
                    logger.info(f"Created SonataFlow instance: {instance_id}")
                    return instance_id
                else:
                    logger.error(f"Failed to create workflow instance: {response.status_code} {response.text}")
                    return None

        except Exception as e:
            logger.error(f"Error creating workflow instance: {e}")
            return None

    async def send_event(self, project_id: str, event_type: str) -> bool:
        """
        Send a CloudEvent to advance the workflow.

        Args:
            project_id: Project identifier (used for correlation)
            event_type: CloudEvent type (e.g., ph.intake.complete)

        Returns:
            True if event was sent successfully, False otherwise
        """
        try:
            # Create CloudEvent
            event = CloudEvent(
                {
                    "type": event_type,
                    "source": "publishing-house-central",
                    "specversion": "1.0"
                },
                data={
                    "projectid": project_id,  # Correlation attribute
                    "timestamp": httpx.utils.datetime.datetime.utcnow().isoformat()
                }
            )

            # Convert to structured format
            headers, body = to_structured(event)

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/",  # CloudEvent endpoint
                    headers=headers,
                    content=body
                )

                if response.status_code in [200, 202]:
                    logger.info(f"Sent CloudEvent {event_type} for project {project_id}")
                    return True
                else:
                    logger.error(f"Failed to send CloudEvent: {response.status_code} {response.text}")
                    return False

        except Exception as e:
            logger.error(f"Error sending CloudEvent: {e}")
            return False

    async def get_instance(self, instance_id: str) -> Optional[dict]:
        """
        Get workflow instance details.

        Args:
            instance_id: Workflow instance ID

        Returns:
            Instance data, or None if not found
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/{self.workflow_id}/{instance_id}"
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    return None

        except Exception as e:
            logger.error(f"Error getting workflow instance: {e}")
            return None
