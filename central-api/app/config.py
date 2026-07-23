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
    # Runtime pod — receives CloudEvents
    sonataflow_url: str = "http://publishinghouseworkflow.publishing-house:80"
    # GraphQL endpoint for workflow state queries
    # dev mode: runtime pod has embedded /graphql
    sonataflow_graphql_url: str = "http://publishinghouseworkflow.publishing-house:80"
    # preview mode: use platform data-index service instead
    # sonataflow_graphql_url: str = "http://sonataflow-platform-data-index-service.publishing-house:80"

    # LiteLLM Configuration
    litellm_api_url: str = "https://maas-rhdp.apps.maas.redhatworkshops.io"
    litellm_master_key: str

    # Jira integration
    jira_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""
    jira_project_key: str = "RHDPCD"

    # GitHub integration
    github_token: str = ""

    # OIDC/Keycloak authentication (for portal endpoints)
    oidc_issuer_url: str = ""
    oidc_client_id: str = ""

    # PH Internal AI (drift detection via MaaS)
    ph_internal_ai_api_key: str = ""

    # RCARS integration
    rcars_url: str = "https://rcars-api.apps.ocpv-infra01.dal12.infra.demo.redhat.com"
    rcars_api_key: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
