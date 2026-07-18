"""GitHub integration service."""
import httpx
import yaml
from typing import Optional, Dict
import base64
import logging

logger = logging.getLogger(__name__)


class GitHubService:
    """Service for GitHub operations."""

    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.api_base = "https://api.github.com"

    def parse_repo_url(self, repo_url: str) -> tuple[str, str]:
        """
        Parse GitHub repo URL to extract owner and repo name.

        Args:
            repo_url: GitHub repository URL

        Returns:
            Tuple of (owner, repo)
        """
        # Handle formats:
        # https://github.com/owner/repo
        # git@github.com:owner/repo.git
        # owner/repo
        repo_url = repo_url.replace(".git", "")

        if "github.com/" in repo_url:
            parts = repo_url.split("github.com/")[-1].split("/")
        elif ":" in repo_url and "@" in repo_url:
            parts = repo_url.split(":")[-1].split("/")
        else:
            parts = repo_url.split("/")

        return parts[0], parts[1]

    async def get_file_content(self, repo_url: str, path: str, branch: str = "main") -> Optional[str]:
        """Fetch a file's raw content from a repository."""
        try:
            owner, repo = self.parse_repo_url(repo_url)
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.api_base}/repos/{owner}/{repo}/contents/{path}",
                    headers=self.headers,
                    params={"ref": branch}
                )
                if response.status_code == 200:
                    data = response.json()
                    return base64.b64decode(data["content"]).decode("utf-8")
                else:
                    logger.warning(f"{path} not found in {owner}/{repo}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching {path}: {e}")
            return None

    async def get_catalog_info(self, repo_url: str, branch: str = "main") -> Optional[Dict]:
        """
        Fetch catalog-info.yaml from a repository.

        Args:
            repo_url: GitHub repository URL
            branch: Branch name

        Returns:
            Parsed catalog-info dict, or None if not found
        """
        try:
            owner, repo = self.parse_repo_url(repo_url)

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.api_base}/repos/{owner}/{repo}/contents/catalog-info.yaml",
                    headers=self.headers,
                    params={"ref": branch}
                )

                if response.status_code == 200:
                    data = response.json()
                    content = base64.b64decode(data["content"]).decode("utf-8")
                    return yaml.safe_load(content)
                else:
                    logger.warning(f"catalog-info.yaml not found in {owner}/{repo}")
                    return None

        except Exception as e:
            logger.error(f"Error fetching catalog-info.yaml: {e}")
            return None

    async def update_catalog_info(
        self,
        repo_url: str,
        branch: str,
        updates: Dict,
        commit_message: str = "Update catalog-info.yaml [skip ci]"
    ) -> bool:
        """
        Update catalog-info.yaml with new annotations and metadata.

        Args:
            repo_url: GitHub repository URL
            branch: Branch name
            updates: Dict of updates to apply to catalog-info
            commit_message: Git commit message

        Returns:
            True if update succeeded, False otherwise
        """
        try:
            owner, repo = self.parse_repo_url(repo_url)

            async with httpx.AsyncClient(timeout=15.0) as client:
                # Get current file
                response = await client.get(
                    f"{self.api_base}/repos/{owner}/{repo}/contents/catalog-info.yaml",
                    headers=self.headers,
                    params={"ref": branch}
                )

                if response.status_code != 200:
                    logger.error("catalog-info.yaml not found")
                    return False

                file_data = response.json()
                sha = file_data["sha"]
                current_content = base64.b64decode(file_data["content"]).decode("utf-8")
                catalog_data = yaml.safe_load(current_content)

                # Apply updates
                if "metadata" not in catalog_data:
                    catalog_data["metadata"] = {}
                if "annotations" not in catalog_data["metadata"]:
                    catalog_data["metadata"]["annotations"] = {}

                # Merge updates into annotations
                catalog_data["metadata"]["annotations"].update(updates)

                # Convert back to YAML
                new_content = yaml.dump(catalog_data, default_flow_style=False, sort_keys=False)
                encoded_content = base64.b64encode(new_content.encode("utf-8")).decode("utf-8")

                # Commit update
                update_response = await client.put(
                    f"{self.api_base}/repos/{owner}/{repo}/contents/catalog-info.yaml",
                    headers=self.headers,
                    json={
                        "message": commit_message,
                        "content": encoded_content,
                        "sha": sha,
                        "branch": branch
                    }
                )

                if update_response.status_code == 200:
                    logger.info(f"Updated catalog-info.yaml in {owner}/{repo}")
                    return True
                else:
                    logger.error(f"Failed to update catalog-info.yaml: {update_response.status_code}")
                    return False

        except Exception as e:
            logger.error(f"Error updating catalog-info.yaml: {e}")
            return False
