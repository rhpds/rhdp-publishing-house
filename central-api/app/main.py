"""Publishing House Central API - Main application."""
import logging
from pathlib import Path
from datetime import datetime

from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from .config import get_settings, Settings
from .models import HealthResponse
from .routers import litellm, projects, jira, workspace, validate, drift
from .services.rcars import rcars_overlap_check, rcars_health, rcars_advisor_submit, rcars_advisor_result
from .auth import init_oidc

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()

    if settings.oidc_issuer_url and settings.oidc_client_id:
        init_oidc(settings.oidc_issuer_url, settings.oidc_client_id)
        logger.info("OIDC authentication initialized: %s", settings.oidc_issuer_url)
    else:
        logger.warning("OIDC not configured - portal endpoints will fail")

    app = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        description="Central API for Publishing House workflow orchestration"
    )

    @app.get(f"{settings.api_prefix}/health", response_model=HealthResponse)
    async def health_check():
        """Health check endpoint."""
        return HealthResponse(
            status="healthy",
            version=settings.api_version,
            timestamp=datetime.utcnow()
        )

    @app.get(f"{settings.api_prefix}/auth/config")
    async def auth_config():
        """Public endpoint returning OIDC config for the portal UI."""
        issuer = settings.oidc_issuer_url.rstrip("/")
        # Extract base URL and realm from issuer URL (e.g. https://host/realms/my-realm)
        parts = issuer.rsplit("/realms/", 1)
        base_url = parts[0] if len(parts) == 2 else issuer
        realm = parts[1] if len(parts) == 2 else ""
        return {
            "url": base_url,
            "realm": realm,
            "clientId": settings.oidc_client_id,
        }

    @app.get(f"{settings.api_prefix}/spec/ocp-policy")
    async def get_ocp_policy():
        """Get OCP version policy (no auth required)."""
        return {"ocp_version_minimum": settings.ocp_version_minimum}

    @app.get(f"{settings.api_prefix}/rcars/overlap")
    async def get_rcars_overlap(
        products: Optional[str] = Query(None, description="Comma-separated product names"),
        audience: Optional[str] = Query(None, description="Target audience (beginner/intermediate/advanced)"),
        limit: int = Query(5, description="Max number of matches to return"),
    ):
        """Query RCARS for existing catalog overlap by products and audience."""
        product_list = [p.strip() for p in products.split(",")] if products else []
        return rcars_overlap_check(
            products=product_list,
            audience=audience or "",
            limit=limit,
        )

    @app.post(f"{settings.api_prefix}/rcars/advisor")
    async def submit_advisor_query(
        query: str = Query(..., description="Natural-language query describing the lab content"),
    ):
        """Submit an advisor query to RCARS. Returns {job_id} to poll for results."""
        return rcars_advisor_submit(query)

    @app.get(f"{settings.api_prefix}/rcars/advisor/{{job_id}}")
    async def get_advisor_result(job_id: str):
        """Poll for advisor query result. Returns {status, result, error}."""
        return rcars_advisor_result(job_id)

    @app.get(f"{settings.api_prefix}/rcars/health")
    async def get_rcars_health():
        """Check RCARS connectivity."""
        return rcars_health()

    # Projects router (includes auth key management, intake, workflow-data)
    # IMPORTANT: Must be included BEFORE other routers to avoid path conflicts
    app.include_router(projects.router, prefix=settings.api_prefix)

    # Validate router — spec validation endpoint
    app.include_router(validate.router, prefix=settings.api_prefix)

    # Drift router — spec contract drift detection
    app.include_router(drift.router, prefix=settings.api_prefix)

    # Workspace setup — SA token auth, no static API key required
    app.include_router(workspace.router, prefix=settings.api_prefix)

    app.include_router(litellm.router, prefix=settings.api_prefix)
    app.include_router(jira.router, prefix=settings.api_prefix)

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
        logger.info("Portal UI mounted at /")
    else:
        logger.warning("Static directory not found: %s", static_dir)

    return app


app = create_app()
