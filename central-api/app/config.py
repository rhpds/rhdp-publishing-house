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

    # LiteLLM Configuration
    litellm_api_url: str = "https://maas-rhdp.apps.maas.redhatworkshops.io"
    litellm_master_key: str

    # Policy defaults
    ocp_version_minimum: str = "4.20"

    # Jira integration
    jira_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""
    jira_project_key: str = "RHDPCD"

    # OIDC/Keycloak authentication (for portal endpoints)
    oidc_issuer_url: str = ""
    oidc_client_id: str = ""

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
