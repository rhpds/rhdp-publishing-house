"""Configuration settings for Central API."""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Configuration
    api_title: str = "Publishing House Central API"
    api_version: str = "1.0.0"
    api_prefix: str = "/api/v1"

    # Authentication
    ph_api_key: str  # Bearer token for write endpoints

    # SonataFlow Configuration
    sonataflow_url: str = "http://publishing-house-workflow.backstage.svc.cluster.local:8080"
    sonataflow_workflow_id: str = "publishing-house-workflow"

    # GitHub Configuration
    github_token: str

    # LiteLLM Configuration
    litellm_api_url: str = "https://maas-rhdp.apps.maas.redhatworkshops.io"
    litellm_master_key: str

    # Kubernetes
    in_cluster: bool = True
    namespace: str = "publishing-house"

    # Central API external URL (for workspace setup responses)
    central_external_url: str = ""

    # Policy defaults
    ocp_version_minimum: str = "4.20"

    # RHDH Scaffolder integration (for /projects/register)
    rhdh_url: str = ""          # https://backstage-backstage.apps...
    rhdh_token: str = ""        # Backstage automation token
    rhdh_template_ref: str = "template:default/publishing-house-project"

    # Jira integration (for /projects/{id}/intake)
    jira_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""
    jira_project_key: str = "RHDPCD"

    # OIDC/Keycloak authentication (for portal endpoints)
    oidc_issuer_url: str = ""      # https://keycloak-rhsso.apps.../auth/realms/openshift
    oidc_client_id: str = ""       # Central API client ID in Keycloak

    # RCARS integration (cross-cluster, proxy-secret auth)
    # Direct API route — NOT the oauth-proxy/frontend route
    rcars_url: str = "https://rcars-api-dev.apps.ocpv-infra01.dal12.infra.demo.redhat.com"
    rcars_proxy_secret: str = ""   # From rcars-proxy-verification secret on infra cluster
    rcars_proxy_email: str = "central@cluster.local"  # Service identity for RCARS calls

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
