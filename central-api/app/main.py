"""Publishing House Central API - Main application."""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime

from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings, Settings
from .models import HealthResponse
from .routers import litellm, projects, jira, validate, drift, auth as auth_router, messages
from .services.rcars import rcars_health, rcars_advisor_submit, rcars_advisor_result
from .auth import init_oidc
from .auth.groups import decode_signed_key
from .auth.token_cache import load_backup, save_backup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


_BACKUP_INTERVAL = 86400  # 24 hours


async def _backup_loop():
    """Save token cache backup every 24 hours."""
    while True:
        await asyncio.sleep(_BACKUP_INTERVAL)
        save_backup()


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Startup: restore cache from backup. Shutdown: save final backup."""
    loaded = load_backup()
    logger.info("token cache startup: restored %d entries", loaded)
    task = asyncio.create_task(_backup_loop())
    yield
    task.cancel()
    save_backup()
    logger.info("token cache shutdown: backup saved")


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
        description="Central API for Publishing House workflow orchestration",
        lifespan=_lifespan,
    )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
            allow_methods=["*"],
            allow_headers=["*"],
            allow_credentials=True,
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

    _bearer = HTTPBearer(auto_error=False)

    def _require_token(
        credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
    ) -> str:
        if not credentials:
            raise HTTPException(status_code=401, detail="Bearer token required")
        if credentials.credentials == settings.ph_api_key:
            return "service"
        result = decode_signed_key(credentials.credentials)
        if not result:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return result[0]

    @app.post(f"{settings.api_prefix}/rcars/advisor")
    async def submit_advisor_query(
        query: str = Query(..., description="Natural-language query describing the lab content"),
        _caller: str = Depends(_require_token),
    ):
        """Submit an advisor query to RCARS. Returns {job_id} to poll for results."""
        return rcars_advisor_submit(query)

    @app.get(f"{settings.api_prefix}/rcars/advisor/{{job_id}}")
    async def get_advisor_result(job_id: str, _caller: str = Depends(_require_token)):
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

    # Auth router — key management, token exchange, workspace setup
    app.include_router(auth_router.router, prefix=settings.api_prefix)

    app.include_router(messages.router, prefix=settings.api_prefix)
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
