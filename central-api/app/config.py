"""Configuration settings for Central API."""
from pydantic_settings import BaseSettings
from functools import lru_cache
from kubernetes import client, config as k8s_config
import logging

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Configuration
    api_title: str = "Publishing House Central API"
    api_version: str = "2.0.0"
    api_prefix: str = "/api/v1"

    # Authentication
    ph_api_key: str  # Bearer token for write endpoints

    # SonataFlow Configuration
    # Workflow proxy — routes to correct workflow based on X-Workflow-Type header
    sonataflow_url: str = "http://workflow-proxy.publishing-house:80"
    # GraphQL endpoint for workflow state queries
    # dev mode: runtime pod has embedded /graphql
    # preview mode: use platform data-index service instead
    sonataflow_graphql_url: str = "http://sonataflow-platform-data-index-service.publishing-house:80"

    # LiteLLM Configuration
    litellm_api_url: str = "https://maas-rhdp.apps.maas.redhatworkshops.io"
    litellm_master_key: str

    # Jira integration
    jira_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""
    jira_project_key: str = "RHDPCD"
    jira_default_assignee: str = ""

    # GitHub integration
    github_token: str = ""
    github_template_repo: str = "https://github.com/rhpds/rhdp-publishing-house-template"
    ph_git_ref: str = "main"  # Publishing House skills repo branch

    # OIDC/Keycloak authentication (for portal endpoints)
    oidc_issuer_url: str = ""
    oidc_client_id: str = ""

    # PH Internal AI (drift detection via MaaS)
    ph_internal_ai_api_key: str = ""

    # Signed token TTL
    api_key_ttl_days: int = 7

    # Token cache encrypted backup path
    token_cache_path: str = "/data/token-cache.db"

    # RCARS integration
    rcars_url: str = "https://rcars-api.apps.ocpv-infra01.dal12.infra.demo.redhat.com"
    rcars_api_key: str = ""

    def _get_route_url(self, route_name: str, namespace: str = "publishing-house") -> str:
        """Query OpenShift Route to get external URL."""
        k8s_config.load_incluster_config()
        custom_api = client.CustomObjectsApi()
        route = custom_api.get_namespaced_custom_object(
            group="route.openshift.io",
            version="v1",
            namespace=namespace,
            plural="routes",
            name=route_name
        )
        host = route.get("spec", {}).get("host", "")
        if not host:
            raise ValueError(f"Route {route_name} in namespace {namespace} has no host")
        return f"https://{host}"

    @property
    def devspaces_url(self) -> str:
        """Query DevSpaces route URL from cluster."""
        return self._get_route_url("devspaces", namespace="openshift-devspaces")

    @property
    def central_api_url(self) -> str:
        """Query Central API route URL from cluster."""
        return self._get_route_url("central-api", namespace="publishing-house")

    # Drift semantic cache TTL (seconds, default 3 days)
    drift_cache_ttl_seconds: int = 259200

    # AWS instance type map (JSON string: {"type": [cpu, ram_gb], ...})
    aws_instance_type_map: str = "{}"

    # CORS (comma-separated origins for direct browser→API calls)
    cors_origins: str = ""

    # RHDH catalog API (for location cleanup on project delete)
    rhdh_service_token: str = ""
    rhdh_internal_url: str = "http://backstage-developer-hub.publishing-house.svc.cluster.local"

    # SonataFlow PostgreSQL (for full cleanup on project delete)
    sonataflow_db_host: str = "sonataflow-postgresql.publishing-house.svc.cluster.local"
    sonataflow_db_port: int = 5432
    sonataflow_db_name: str = "sonataflow"
    sonataflow_db_user: str = "postgres"
    sonataflow_db_password: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
