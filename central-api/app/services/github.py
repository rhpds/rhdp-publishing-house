"""GitHub integration service."""
import asyncio
import httpx
import shutil
import tempfile
import yaml
from pathlib import Path
from typing import Optional, Dict, List
import base64
import logging

logger = logging.getLogger(__name__)


class ClonedRepo:
    """Handle to a shallow-cloned repo on disk."""

    def __init__(self, path: Path, head_sha: str):
        self.path = path
        self.head_sha = head_sha

    def read_file(self, relative_path: str) -> Optional[str]:
        f = self.path / relative_path
        if f.is_file():
            return f.read_text()
        return None

    def list_dir(self, relative_path: str) -> List[str]:
        d = self.path / relative_path
        if d.is_dir():
            return [p.name for p in d.iterdir()]
        return []

    def cleanup(self):
        shutil.rmtree(self.path, ignore_errors=True)


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

    async def clone_repo(self, repo_url: str, branch: str = "main") -> "ClonedRepo":
        """Shallow-clone a repo and return a ClonedRepo context manager."""
        owner, repo = self.parse_repo_url(repo_url)
        clone_url = f"https://x-access-token:{self.token}@github.com/{owner}/{repo}.git"
        tmp_dir = tempfile.mkdtemp(prefix="ph-validate-")
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "clone", "--depth", "1", "--branch", branch,
                "--single-branch", clone_url, tmp_dir,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            if proc.returncode != 0:
                raise RuntimeError(f"git clone failed: {stderr.decode().strip()}")

            proc = await asyncio.create_subprocess_exec(
                "git", "rev-parse", "HEAD",
                cwd=tmp_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()
            head_sha = stdout.decode().strip()

            return ClonedRepo(path=Path(tmp_dir), head_sha=head_sha)
        except Exception:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise

    async def get_head_sha(self, repo_url: str, branch: str = "main") -> Optional[str]:
        """Fetch the HEAD commit SHA for a branch without cloning."""
        try:
            owner, repo = self.parse_repo_url(repo_url)
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.api_base}/repos/{owner}/{repo}/commits/{branch}",
                    headers={**self.headers, "Accept": "application/vnd.github.sha"},
                )
                if response.status_code == 200:
                    return response.text.strip()
                return None
        except Exception as e:
            logger.error(f"Error fetching HEAD SHA: {e}")
            return None

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

    async def list_directory(self, repo_url: str, path: str, branch: str = "main") -> List[str]:
        """List filenames in a repository directory via the GitHub Contents API."""
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
                    if isinstance(data, list):
                        return [item["name"] for item in data]
                return []
        except Exception as e:
            logger.error(f"Error listing {path}: {e}")
            return []

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
