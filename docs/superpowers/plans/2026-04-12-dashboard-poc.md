# Publishing House Dashboard POC — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone web dashboard that provides cross-project visibility into Publishing House content lifecycle, with project registration, manifest caching, kanban pipeline view, projects table, and project detail.

**Architecture:** FastAPI backend serves a REST API backed by PostgreSQL. Next.js 15 frontend with PatternFly 6 renders three views (pipeline kanban, projects table, project detail) plus a registration form. Backend fetches `manifest.yaml` from GitHub repos, parses lifecycle phases, and caches structured data. Nightly scheduler + on-demand refresh keep data current.

**Tech Stack:** Python 3.11+ / FastAPI / SQLAlchemy 2.0 / Alembic / PostgreSQL 16 / Next.js 15 / React 19 / PatternFly 6 / TypeScript

**Spec:** `docs/superpowers/specs/2026-04-12-publishing-house-dashboard-design.md`

---

## File Structure

```
publishing-house-dashboard/
├── src/
│   ├── backend/
│   │   ├── app/
│   │   │   ├── __init__.py
│   │   │   ├── main.py                    # FastAPI app, router registration, CORS
│   │   │   ├── core/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── config.py              # Pydantic Settings (env-based)
│   │   │   │   └── database.py            # SQLAlchemy engine, session, Base
│   │   │   ├── models/
│   │   │   │   ├── __init__.py            # Import all models for Alembic
│   │   │   │   ├── project.py             # Project registration model
│   │   │   │   ├── manifest.py            # Cached manifest model
│   │   │   │   └── phase.py               # Denormalized phase model
│   │   │   ├── schemas/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── project.py             # Project create/response schemas
│   │   │   │   └── phase.py               # Phase response schema
│   │   │   ├── services/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── github_client.py       # Fetch manifest.yaml via GitHub API
│   │   │   │   ├── manifest_parser.py     # Parse YAML → phases + metadata
│   │   │   │   └── refresh.py             # Orchestrate fetch → parse → store
│   │   │   └── api/
│   │   │       ├── __init__.py
│   │   │       ├── health.py              # Health check endpoint
│   │   │       └── projects.py            # Project CRUD + refresh endpoints
│   │   ├── alembic/
│   │   │   ├── env.py
│   │   │   ├── script.py.mako
│   │   │   └── versions/                  # Migration files
│   │   ├── alembic.ini
│   │   ├── tests/
│   │   │   ├── __init__.py
│   │   │   ├── conftest.py                # Fixtures: test DB, client, sample manifest
│   │   │   ├── test_manifest_parser.py
│   │   │   ├── test_github_client.py
│   │   │   ├── test_refresh.py
│   │   │   └── test_api_projects.py
│   │   ├── pyproject.toml
│   │   └── requirements.txt
│   └── frontend/
│       ├── src/
│       │   ├── app/
│       │   │   ├── layout.tsx             # PatternFly Page shell + nav
│       │   │   ├── page.tsx               # Redirect to /pipeline
│       │   │   ├── pipeline/
│       │   │   │   └── page.tsx           # Kanban board
│       │   │   ├── projects/
│       │   │   │   ├── page.tsx           # Projects table
│       │   │   │   └── [id]/
│       │   │   │       └── page.tsx       # Project detail
│       │   │   ├── register/
│       │   │   │   └── page.tsx           # Registration form
│       │   │   └── api/
│       │   │       └── v1/
│       │   │           └── [[...path]]/
│       │   │               └── route.ts   # Proxy to backend
│       │   ├── components/
│       │   │   ├── PhaseProgressBar.tsx    # 7-segment progress indicator
│       │   │   ├── ProjectCard.tsx         # Kanban card
│       │   │   ├── KanbanColumn.tsx        # Column wrapper
│       │   │   ├── PhaseAccordion.tsx      # Detail view phase section
│       │   │   └── RefreshButton.tsx       # Refresh with loading state
│       │   ├── services/
│       │   │   └── api.ts                 # Centralized API client
│       │   └── types/
│       │       └── index.ts               # Shared TypeScript types
│       ├── public/
│       ├── next.config.ts
│       ├── tsconfig.json
│       └── package.json
├── dev-services.sh                        # Local dev service manager
├── CLAUDE.md
└── README.md
```

---

## Task 1: Project Scaffolding + Dev Services

**Files:**
- Create: `publishing-house-dashboard/dev-services.sh`
- Create: `publishing-house-dashboard/CLAUDE.md`
- Create: `publishing-house-dashboard/src/backend/pyproject.toml`
- Create: `publishing-house-dashboard/src/backend/requirements.txt`
- Create: `publishing-house-dashboard/src/backend/app/__init__.py`
- Create: `publishing-house-dashboard/src/backend/app/core/__init__.py`
- Create: `publishing-house-dashboard/src/backend/app/models/__init__.py`
- Create: `publishing-house-dashboard/src/backend/app/schemas/__init__.py`
- Create: `publishing-house-dashboard/src/backend/app/services/__init__.py`
- Create: `publishing-house-dashboard/src/backend/app/api/__init__.py`
- Create: `publishing-house-dashboard/src/backend/tests/__init__.py`

Working directory: `~/devel/working/`

- [ ] **Step 1: Create the project directory and backend package files**

```bash
mkdir -p ~/devel/working/publishing-house-dashboard/src/backend/app/{core,models,schemas,services,api}
mkdir -p ~/devel/working/publishing-house-dashboard/src/backend/tests
mkdir -p ~/devel/working/publishing-house-dashboard/src/frontend
touch ~/devel/working/publishing-house-dashboard/src/backend/app/__init__.py
touch ~/devel/working/publishing-house-dashboard/src/backend/app/core/__init__.py
touch ~/devel/working/publishing-house-dashboard/src/backend/app/models/__init__.py
touch ~/devel/working/publishing-house-dashboard/src/backend/app/schemas/__init__.py
touch ~/devel/working/publishing-house-dashboard/src/backend/app/services/__init__.py
touch ~/devel/working/publishing-house-dashboard/src/backend/app/api/__init__.py
touch ~/devel/working/publishing-house-dashboard/src/backend/tests/__init__.py
```

- [ ] **Step 2: Create pyproject.toml**

Write to `src/backend/pyproject.toml`:

```toml
[project]
name = "publishing-house-dashboard"
version = "0.1.0"
description = "Cross-project visibility dashboard for Publishing House content lifecycle"
requires-python = ">=3.11"

[tool.ruff]
line-length = 120
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 3: Create requirements.txt**

Write to `src/backend/requirements.txt`:

```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
sqlalchemy>=2.0
alembic>=1.13
psycopg2-binary>=2.9
pydantic>=2.0
pydantic-settings>=2.0
httpx>=0.27.0
pyyaml>=6.0
apscheduler>=3.10
pytest>=8.0
pytest-cov>=5.0
ruff>=0.5
```

- [ ] **Step 4: Create dev-services.sh**

Write to `dev-services.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

PROJECT_NAME="ph-dashboard"
DB_NAME="ph_dashboard"
DB_USER="ph_dashboard"
DB_PASS="ph_dashboard"
DB_PORT=5433
BACKEND_PORT=8081
FRONTEND_PORT=3001

# Use the agnosticd podman machine
export CONTAINER_HOST="unix://$HOME/.local/share/containers/podman/machine/agnosticd/podman.sock"

usage() {
    echo "Usage: $0 {start|stop|status|restart} [postgres|backend|frontend|all]"
    exit 1
}

start_postgres() {
    if podman ps --format '{{.Names}}' | grep -q "^${PROJECT_NAME}-postgres$"; then
        echo "PostgreSQL already running"
        return
    fi
    echo "Starting PostgreSQL on port ${DB_PORT}..."
    podman run -d --name "${PROJECT_NAME}-postgres" \
        -e POSTGRES_USER="${DB_USER}" \
        -e POSTGRES_PASSWORD="${DB_PASS}" \
        -e POSTGRES_DB="${DB_NAME}" \
        -p "${DB_PORT}:5432" \
        postgres:16
    echo "Waiting for PostgreSQL..."
    sleep 3
    echo "PostgreSQL ready on port ${DB_PORT}"
}

stop_postgres() {
    echo "Stopping PostgreSQL..."
    podman stop "${PROJECT_NAME}-postgres" 2>/dev/null || true
    podman rm "${PROJECT_NAME}-postgres" 2>/dev/null || true
}

start_backend() {
    echo "Starting backend on port ${BACKEND_PORT}..."
    cd src/backend
    DATABASE_URL="postgresql://${DB_USER}:${DB_PASS}@localhost:${DB_PORT}/${DB_NAME}" \
    GITHUB_TOKEN="${GITHUB_TOKEN:-}" \
    uvicorn app.main:app --reload --port "${BACKEND_PORT}" &
    echo $! > /tmp/${PROJECT_NAME}-backend.pid
    cd ../..
    echo "Backend running on http://localhost:${BACKEND_PORT}"
}

stop_backend() {
    echo "Stopping backend..."
    if [ -f /tmp/${PROJECT_NAME}-backend.pid ]; then
        kill "$(cat /tmp/${PROJECT_NAME}-backend.pid)" 2>/dev/null || true
        rm /tmp/${PROJECT_NAME}-backend.pid
    fi
}

start_frontend() {
    echo "Starting frontend on port ${FRONTEND_PORT}..."
    cd src/frontend
    BACKEND_URL="http://localhost:${BACKEND_PORT}" \
    PORT="${FRONTEND_PORT}" \
    npm run dev &
    echo $! > /tmp/${PROJECT_NAME}-frontend.pid
    cd ../..
    echo "Frontend running on http://localhost:${FRONTEND_PORT}"
}

stop_frontend() {
    echo "Stopping frontend..."
    if [ -f /tmp/${PROJECT_NAME}-frontend.pid ]; then
        kill "$(cat /tmp/${PROJECT_NAME}-frontend.pid)" 2>/dev/null || true
        rm /tmp/${PROJECT_NAME}-frontend.pid
    fi
}

status() {
    echo "=== ${PROJECT_NAME} services ==="
    if podman ps --format '{{.Names}}' | grep -q "^${PROJECT_NAME}-postgres$"; then
        echo "PostgreSQL: RUNNING (port ${DB_PORT})"
    else
        echo "PostgreSQL: STOPPED"
    fi
    if [ -f /tmp/${PROJECT_NAME}-backend.pid ] && kill -0 "$(cat /tmp/${PROJECT_NAME}-backend.pid)" 2>/dev/null; then
        echo "Backend:    RUNNING (port ${BACKEND_PORT})"
    else
        echo "Backend:    STOPPED"
    fi
    if [ -f /tmp/${PROJECT_NAME}-frontend.pid ] && kill -0 "$(cat /tmp/${PROJECT_NAME}-frontend.pid)" 2>/dev/null; then
        echo "Frontend:   RUNNING (port ${FRONTEND_PORT})"
    else
        echo "Frontend:   STOPPED"
    fi
}

SERVICE="${2:-all}"
case "${1:-}" in
    start)
        case "$SERVICE" in
            postgres)  start_postgres ;;
            backend)   start_backend ;;
            frontend)  start_frontend ;;
            all)       start_postgres; start_backend; start_frontend ;;
            *)         usage ;;
        esac
        ;;
    stop)
        case "$SERVICE" in
            postgres)  stop_postgres ;;
            backend)   stop_backend ;;
            frontend)  stop_frontend ;;
            all)       stop_frontend; stop_backend; stop_postgres ;;
            *)         usage ;;
        esac
        ;;
    restart)
        case "$SERVICE" in
            postgres)  stop_postgres; start_postgres ;;
            backend)   stop_backend; start_backend ;;
            frontend)  stop_frontend; start_frontend ;;
            all)       stop_frontend; stop_backend; stop_postgres; start_postgres; start_backend; start_frontend ;;
            *)         usage ;;
        esac
        ;;
    status)  status ;;
    *)       usage ;;
esac
```

Make executable: `chmod +x dev-services.sh`

- [ ] **Step 5: Create CLAUDE.md**

Write to `CLAUDE.md`:

```markdown
# Publishing House Dashboard

Cross-project visibility dashboard for the Publishing House content lifecycle.

## Architecture
- Backend: FastAPI + SQLAlchemy + PostgreSQL (port 8081)
- Frontend: Next.js 15 + PatternFly 6 (port 3001)
- Database: PostgreSQL 16 via Podman (port 5433)

## Local Dev
```bash
./dev-services.sh start          # Start all services
./dev-services.sh status         # Check status
./dev-services.sh restart backend  # Restart backend only
```

## Backend
```bash
cd src/backend
pip install -r requirements.txt
alembic upgrade head             # Run migrations
pytest                           # Run tests
```

## Frontend
```bash
cd src/frontend
npm install
npm run dev                      # Start dev server
```

## Environment Variables
- `DATABASE_URL` — PostgreSQL connection string
- `GITHUB_TOKEN` — GitHub personal access token for reading manifests from private repos
- `BACKEND_URL` — Backend URL for frontend proxy (default: http://localhost:8081)

## Spec
See `docs/superpowers/specs/2026-04-12-publishing-house-dashboard-design.md`
```

- [ ] **Step 6: Initialize git repo**

```bash
cd ~/devel/working/publishing-house-dashboard
git init
echo -e "node_modules/\n__pycache__/\n*.pyc\n.env\n*.egg-info/\ndist/\nbuild/\n.next/\n.superpowers/\n.pytest_cache/\n.ruff_cache/" > .gitignore
```

- [ ] **Step 7: Create Python virtualenv**

```bash
python3 -m venv ~/.virtualenvs/ph-dashboard
source ~/.virtualenvs/ph-dashboard/bin/activate
pip install -r src/backend/requirements.txt
```

- [ ] **Step 8: Commit**

```bash
git add .
git commit -m "Scaffold project structure with dev services and backend dependencies"
```

---

## Task 2: Backend Core — Config + Database

**Files:**
- Create: `src/backend/app/core/config.py`
- Create: `src/backend/app/core/database.py`
- Create: `src/backend/app/main.py`
- Create: `src/backend/app/api/health.py`
- Create: `src/backend/tests/conftest.py`

- [ ] **Step 1: Write the config module**

Write to `src/backend/app/core/config.py`:

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str  # Required — set via DATABASE_URL env var
    github_token: str = ""
    debug: bool = False
    refresh_hour: int = 2  # Nightly refresh at 2 AM

    model_config = {"env_prefix": "", "env_file": ".env"}


settings = Settings()
```

- [ ] **Step 2: Write the database module**

Write to `src/backend/app/core/database.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, echo=settings.debug)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 3: Write the health check endpoint**

Write to `src/backend/app/api/health.py`:

```python
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    return {"status": "ok"}
```

- [ ] **Step 4: Write the FastAPI app**

Write to `src/backend/app/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health

app = FastAPI(title="Publishing House Dashboard", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1")
```

- [ ] **Step 5: Write test conftest with fixtures**

Write to `src/backend/tests/conftest.py`:

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.main import app

from fastapi.testclient import TestClient

SQLALCHEMY_TEST_URL = "sqlite:///./test.db"

engine = create_engine(SQLALCHEMY_TEST_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(bind=engine)


@pytest.fixture(autouse=True)
def test_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(test_db):
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(test_db):
    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


SAMPLE_MANIFEST_YAML = """\
project:
  name: "Test Workshop"
  id: "test-workshop"
  created: "2026-04-01"
  owner: "testuser"
  type: "workshop"
  autonomy: supervised

lifecycle:
  current_phase: writing
  phases:
    intake:
      status: completed
      completed_at: "2026-04-01"
      assignees: ["testuser"]
      artifacts: ["publishing-house/spec/design.md"]
    vetting:
      status: skipped
      completed_at: null
      assignees: []
      result: null
      rcars_response: null
    spec_refinement:
      status: completed
      completed_at: "2026-04-01"
      assignees: ["testuser"]
    approval:
      status: completed
      approved_by: "manager1"
      completed_at: "2026-04-02"
    writing:
      status: in_progress
      assignees: ["testuser", "writer1"]
      modules:
        - id: "module-01"
          title: "Introduction"
          status: drafted
          content_path: "content/modules/ROOT/pages/01-intro.adoc"
        - id: "module-02"
          title: "Getting Started"
          status: in_progress
          content_path: null
        - id: "module-03"
          title: "Advanced Topics"
          status: pending
          content_path: null
    editing:
      status: pending
      assignees: []
    automation:
      status: pending
      assignees: []
      needs_automation: true
      substeps:
        catalog_item: pending
        requirements: pending
        automation_code: pending
        testing: pending
        e2e_checks: deferred
    code_security_review:
      status: pending
      assignees: []
    final_review:
      status: pending
      assignees: []
    ready_for_publishing:
      status: pending

integrations:
  rcars_api: null
  showroom_repo: null
  automation_repo: null
"""
```

- [ ] **Step 6: Run the health check test**

```bash
cd src/backend
source ~/.virtualenvs/ph-dashboard/bin/activate
python -c "from fastapi.testclient import TestClient; from app.main import app; c = TestClient(app); r = c.get('/api/v1/health'); print(r.json()); assert r.status_code == 200"
```

Expected: `{'status': 'ok'}`

- [ ] **Step 7: Commit**

```bash
git add src/backend/app/core/ src/backend/app/main.py src/backend/app/api/health.py src/backend/tests/conftest.py
git commit -m "Add backend core: config, database, health endpoint, test fixtures"
```

---

## Task 3: Database Models + Alembic Migrations

**Files:**
- Create: `src/backend/app/models/project.py`
- Create: `src/backend/app/models/manifest.py`
- Create: `src/backend/app/models/phase.py`
- Modify: `src/backend/app/models/__init__.py`
- Create: `src/backend/alembic.ini`
- Create: `src/backend/alembic/env.py`
- Create: `src/backend/alembic/script.py.mako`

- [ ] **Step 1: Write the Project model**

Write to `src/backend/app/models/project.py`:

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    repo_url: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refresh_status: Mapped[str] = mapped_column(String(20), default="pending")
    refresh_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    manifest = relationship("Manifest", back_populates="project", uselist=False, cascade="all, delete-orphan")
    phases = relationship("Phase", back_populates="project", cascade="all, delete-orphan")
```

- [ ] **Step 2: Write the Manifest model**

Write to `src/backend/app/models/manifest.py`:

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Manifest(Base):
    __tablename__ = "manifests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    raw_yaml: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    project = relationship("Project", back_populates="manifest")
```

- [ ] **Step 3: Write the Phase model**

Write to `src/backend/app/models/phase.py`:

```python
import uuid

from sqlalchemy import String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Phase(Base):
    __tablename__ = "phases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    phase_name: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    assignees: Mapped[dict] = mapped_column(JSONB, default=list)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    project = relationship("Project", back_populates="phases")
```

- [ ] **Step 4: Update models __init__.py to import all models**

Write to `src/backend/app/models/__init__.py`:

```python
from app.models.project import Project
from app.models.manifest import Manifest
from app.models.phase import Phase

__all__ = ["Project", "Manifest", "Phase"]
```

- [ ] **Step 5: Initialize Alembic**

```bash
cd src/backend
source ~/.virtualenvs/ph-dashboard/bin/activate
alembic init alembic
```

- [ ] **Step 6: Configure alembic.ini**

Edit `src/backend/alembic.ini` — set the `sqlalchemy.url` line:

```ini
sqlalchemy.url =  # Set via DATABASE_URL env var — see alembic/env.py
```

- [ ] **Step 7: Configure alembic/env.py**

Replace `src/backend/alembic/env.py` with:

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.database import Base
from app.models import Project, Manifest, Phase  # noqa: F401 — register models

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 8: Start PostgreSQL and generate initial migration**

```bash
cd ~/devel/working/publishing-house-dashboard
./dev-services.sh start postgres
cd src/backend
alembic revision --autogenerate -m "Initial schema: projects, manifests, phases"
```

- [ ] **Step 9: Apply migration**

```bash
alembic upgrade head
```

- [ ] **Step 10: Verify tables exist**

```bash
PGPASSWORD=ph_dashboard psql -h localhost -p 5433 -U ph_dashboard -d ph_dashboard -c "\dt"
```

Expected: tables `projects`, `manifests`, `phases`, `alembic_version`.

- [ ] **Step 11: Commit**

```bash
cd ~/devel/working/publishing-house-dashboard
git add src/backend/app/models/ src/backend/alembic/ src/backend/alembic.ini
git commit -m "Add database models and initial Alembic migration"
```

---

## Task 4: Manifest Parser Service

**Files:**
- Create: `src/backend/app/services/manifest_parser.py`
- Create: `src/backend/tests/test_manifest_parser.py`

- [ ] **Step 1: Write the failing tests**

Write to `src/backend/tests/test_manifest_parser.py`:

```python
import yaml
from tests.conftest import SAMPLE_MANIFEST_YAML
from app.services.manifest_parser import parse_manifest, extract_phases, get_kanban_column

PARSED = yaml.safe_load(SAMPLE_MANIFEST_YAML)


def test_parse_manifest_returns_project_metadata():
    result = parse_manifest(SAMPLE_MANIFEST_YAML)
    assert result["project"]["name"] == "Test Workshop"
    assert result["project"]["id"] == "test-workshop"
    assert result["project"]["owner"] == "testuser"
    assert result["project"]["type"] == "workshop"


def test_extract_phases_returns_all_phases():
    phases = extract_phases(PARSED)
    phase_names = [p["phase_name"] for p in phases]
    assert "intake" in phase_names
    assert "writing" in phase_names
    assert "code_security_review" in phase_names
    assert "ready_for_publishing" in phase_names
    assert len(phases) == 10  # All 10 manifest phases


def test_extract_phases_captures_status():
    phases = extract_phases(PARSED)
    intake = next(p for p in phases if p["phase_name"] == "intake")
    assert intake["status"] == "completed"
    writing = next(p for p in phases if p["phase_name"] == "writing")
    assert writing["status"] == "in_progress"


def test_extract_phases_captures_assignees():
    phases = extract_phases(PARSED)
    writing = next(p for p in phases if p["phase_name"] == "writing")
    assert writing["assignees"] == ["testuser", "writer1"]


def test_extract_phases_captures_module_metadata():
    phases = extract_phases(PARSED)
    writing = next(p for p in phases if p["phase_name"] == "writing")
    assert "modules" in writing["metadata"]
    assert len(writing["metadata"]["modules"]) == 3
    assert writing["metadata"]["modules"][0]["title"] == "Introduction"
    assert writing["metadata"]["modules"][0]["status"] == "drafted"


def test_extract_phases_captures_automation_substeps():
    phases = extract_phases(PARSED)
    automation = next(p for p in phases if p["phase_name"] == "automation")
    assert "substeps" in automation["metadata"]
    assert automation["metadata"]["substeps"]["catalog_item"] == "pending"
    assert automation["metadata"]["substeps"]["e2e_checks"] == "deferred"


def test_extract_phases_captures_approval_info():
    phases = extract_phases(PARSED)
    approval = next(p for p in phases if p["phase_name"] == "approval")
    assert approval["metadata"]["approved_by"] == "manager1"


def test_get_kanban_column_maps_correctly():
    assert get_kanban_column("intake") == "intake"
    assert get_kanban_column("vetting") == "intake"
    assert get_kanban_column("spec_refinement") == "intake"
    assert get_kanban_column("approval") == "approval"
    assert get_kanban_column("writing") == "content"
    assert get_kanban_column("editing") == "content"
    assert get_kanban_column("automation") == "automation"
    assert get_kanban_column("code_security_review") == "code_security_review"
    assert get_kanban_column("final_review") == "final_review"
    assert get_kanban_column("ready_for_publishing") == "ready"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd src/backend
pytest tests/test_manifest_parser.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.manifest_parser'`

- [ ] **Step 3: Implement the manifest parser**

Write to `src/backend/app/services/manifest_parser.py`:

```python
import yaml

# Maps manifest phase names to kanban column identifiers
KANBAN_COLUMN_MAP = {
    "intake": "intake",
    "vetting": "intake",
    "spec_refinement": "intake",
    "approval": "approval",
    "writing": "content",
    "editing": "content",
    "automation": "automation",
    "code_security_review": "code_security_review",
    "final_review": "final_review",
    "ready_for_publishing": "ready",
}

# Phase-specific metadata keys to extract (beyond status and assignees)
PHASE_METADATA_KEYS = {
    "intake": ["completed_at", "artifacts"],
    "vetting": ["completed_at", "result", "rcars_response"],
    "spec_refinement": ["completed_at"],
    "approval": ["approved_by", "completed_at"],
    "writing": ["modules"],
    "editing": [],
    "automation": ["needs_automation", "substeps"],
    "code_security_review": [],
    "final_review": [],
    "ready_for_publishing": [],
}


def parse_manifest(raw_yaml: str) -> dict:
    """Parse raw YAML manifest string into structured data."""
    return yaml.safe_load(raw_yaml)


def extract_phases(parsed: dict) -> list[dict]:
    """Extract phase records from a parsed manifest for storage in the phases table."""
    phases_data = parsed.get("lifecycle", {}).get("phases", {})
    result = []

    for phase_name, phase_info in phases_data.items():
        if not isinstance(phase_info, dict):
            continue

        status = phase_info.get("status", "pending")
        assignees = phase_info.get("assignees", [])
        if assignees is None:
            assignees = []

        # Extract phase-specific metadata
        metadata = {}
        meta_keys = PHASE_METADATA_KEYS.get(phase_name, [])
        for key in meta_keys:
            if key in phase_info:
                metadata[key] = phase_info[key]

        result.append({
            "phase_name": phase_name,
            "status": status,
            "assignees": assignees,
            "metadata": metadata,
        })

    return result


def get_kanban_column(phase_name: str) -> str:
    """Map a manifest phase name to its kanban column identifier."""
    return KANBAN_COLUMN_MAP.get(phase_name, phase_name)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_manifest_parser.py -v
```

Expected: All 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/devel/working/publishing-house-dashboard
git add src/backend/app/services/manifest_parser.py src/backend/tests/test_manifest_parser.py
git commit -m "Add manifest parser service with phase extraction and kanban mapping"
```

---

## Task 5: GitHub Client Service

**Files:**
- Create: `src/backend/app/services/github_client.py`
- Create: `src/backend/tests/test_github_client.py`

- [ ] **Step 1: Write the failing tests**

Write to `src/backend/tests/test_github_client.py`:

```python
import pytest
from unittest.mock import patch, MagicMock

from app.services.github_client import fetch_manifest, parse_repo_url, GitHubFetchError


def test_parse_repo_url_ssh():
    owner, repo = parse_repo_url("git@github.com:rhpds/my-project.git")
    assert owner == "rhpds"
    assert repo == "my-project"


def test_parse_repo_url_https():
    owner, repo = parse_repo_url("https://github.com/rhpds/my-project")
    assert owner == "rhpds"
    assert repo == "my-project"


def test_parse_repo_url_https_with_git_suffix():
    owner, repo = parse_repo_url("https://github.com/rhpds/my-project.git")
    assert owner == "rhpds"
    assert repo == "my-project"


def test_parse_repo_url_invalid():
    with pytest.raises(ValueError, match="Cannot parse GitHub repo URL"):
        parse_repo_url("not-a-github-url")


@patch("app.services.github_client.httpx")
def test_fetch_manifest_success(mock_httpx):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "content": "cHJvamVjdDoKICBuYW1lOiAiVGVzdCI=",  # base64 of "project:\n  name: \"Test\""
        "encoding": "base64",
    }
    mock_httpx.get.return_value = mock_response

    result = fetch_manifest("rhpds", "my-project", token="fake-token")
    assert "project:" in result
    assert 'name: "Test"' in result


@patch("app.services.github_client.httpx")
def test_fetch_manifest_not_found(mock_httpx):
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Not Found"
    mock_httpx.get.return_value = mock_response

    with pytest.raises(GitHubFetchError, match="404"):
        fetch_manifest("rhpds", "missing-repo", token="fake-token")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd src/backend
pytest tests/test_github_client.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement the GitHub client**

Write to `src/backend/app/services/github_client.py`:

```python
import base64
import re

import httpx


class GitHubFetchError(Exception):
    pass


def parse_repo_url(repo_url: str) -> tuple[str, str]:
    """Extract owner and repo name from a GitHub URL (SSH or HTTPS)."""
    # SSH: git@github.com:owner/repo.git
    ssh_match = re.match(r"git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$", repo_url)
    if ssh_match:
        return ssh_match.group(1), ssh_match.group(2)

    # HTTPS: https://github.com/owner/repo[.git]
    https_match = re.match(r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", repo_url)
    if https_match:
        return https_match.group(1), https_match.group(2)

    raise ValueError(f"Cannot parse GitHub repo URL: {repo_url}")


def fetch_manifest(
    owner: str,
    repo: str,
    token: str,
    path: str = "publishing-house/manifest.yaml",
    ref: str = "main",
) -> str:
    """Fetch a file from GitHub via the Contents API. Returns raw file content."""
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"Bearer {token}",
    }
    params = {"ref": ref}

    response = httpx.get(url, headers=headers, params=params, timeout=30)

    if response.status_code != 200:
        raise GitHubFetchError(
            f"GitHub API returned {response.status_code} for {owner}/{repo}/{path}: {response.text}"
        )

    data = response.json()
    if data.get("encoding") == "base64":
        return base64.b64decode(data["content"]).decode("utf-8")

    raise GitHubFetchError(f"Unexpected encoding: {data.get('encoding')}")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_github_client.py -v
```

Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/devel/working/publishing-house-dashboard
git add src/backend/app/services/github_client.py src/backend/tests/test_github_client.py
git commit -m "Add GitHub client service for fetching manifest files"
```

---

## Task 6: Refresh Service — Fetch, Parse, Store

**Files:**
- Create: `src/backend/app/services/refresh.py`
- Create: `src/backend/tests/test_refresh.py`
- Create: `src/backend/app/schemas/project.py`
- Create: `src/backend/app/schemas/phase.py`

- [ ] **Step 1: Write the Pydantic schemas**

Write to `src/backend/app/schemas/project.py`:

```python
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProjectCreate(BaseModel):
    name: str
    repo_url: str


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    repo_url: str
    registered_at: datetime
    last_refreshed_at: datetime | None
    refresh_status: str
    refresh_error: str | None


class ProjectWithPhases(ProjectResponse):
    phases: list["PhaseResponse"] = []
    manifest_raw: str | None = None
    project_data: dict | None = None


from app.schemas.phase import PhaseResponse  # noqa: E402

ProjectWithPhases.model_rebuild()
```

Write to `src/backend/app/schemas/phase.py`:

```python
import uuid

from pydantic import BaseModel, ConfigDict


class PhaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    phase_name: str
    status: str
    assignees: list
    metadata_: dict
```

- [ ] **Step 2: Write the failing tests**

Write to `src/backend/tests/test_refresh.py`:

```python
from unittest.mock import patch

from tests.conftest import SAMPLE_MANIFEST_YAML
from app.services.refresh import refresh_project
from app.models import Project, Manifest, Phase


def test_refresh_project_creates_manifest_and_phases(db_session):
    project = Project(name="Test", repo_url="https://github.com/rhpds/test-project")
    db_session.add(project)
    db_session.commit()

    with patch("app.services.refresh.fetch_manifest", return_value=SAMPLE_MANIFEST_YAML):
        with patch("app.services.refresh.parse_repo_url", return_value=("rhpds", "test-project")):
            refresh_project(db_session, project, github_token="fake")

    db_session.refresh(project)
    assert project.refresh_status == "success"
    assert project.last_refreshed_at is not None
    assert project.refresh_error is None

    manifest = db_session.query(Manifest).filter_by(project_id=project.id).first()
    assert manifest is not None
    assert "Test Workshop" in manifest.raw_yaml
    assert manifest.parsed_data["project"]["name"] == "Test Workshop"

    phases = db_session.query(Phase).filter_by(project_id=project.id).all()
    assert len(phases) == 10
    phase_names = {p.phase_name for p in phases}
    assert "intake" in phase_names
    assert "code_security_review" in phase_names


def test_refresh_project_replaces_existing_manifest(db_session):
    project = Project(name="Test", repo_url="https://github.com/rhpds/test-project")
    db_session.add(project)
    db_session.commit()

    # First refresh
    with patch("app.services.refresh.fetch_manifest", return_value=SAMPLE_MANIFEST_YAML):
        with patch("app.services.refresh.parse_repo_url", return_value=("rhpds", "test-project")):
            refresh_project(db_session, project, github_token="fake")

    # Second refresh — should replace, not duplicate
    with patch("app.services.refresh.fetch_manifest", return_value=SAMPLE_MANIFEST_YAML):
        with patch("app.services.refresh.parse_repo_url", return_value=("rhpds", "test-project")):
            refresh_project(db_session, project, github_token="fake")

    manifests = db_session.query(Manifest).filter_by(project_id=project.id).all()
    assert len(manifests) == 1

    phases = db_session.query(Phase).filter_by(project_id=project.id).all()
    assert len(phases) == 10


def test_refresh_project_handles_fetch_error(db_session):
    project = Project(name="Test", repo_url="https://github.com/rhpds/bad-repo")
    db_session.add(project)
    db_session.commit()

    with patch("app.services.refresh.fetch_manifest", side_effect=Exception("GitHub API timeout")):
        with patch("app.services.refresh.parse_repo_url", return_value=("rhpds", "bad-repo")):
            refresh_project(db_session, project, github_token="fake")

    db_session.refresh(project)
    assert project.refresh_status == "error"
    assert "GitHub API timeout" in project.refresh_error
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd src/backend
pytest tests/test_refresh.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement the refresh service**

Write to `src/backend/app/services/refresh.py`:

```python
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Project, Manifest, Phase
from app.services.github_client import fetch_manifest, parse_repo_url
from app.services.manifest_parser import parse_manifest, extract_phases


def refresh_project(db: Session, project: Project, github_token: str) -> None:
    """Fetch manifest from GitHub, parse it, and update the database."""
    try:
        owner, repo = parse_repo_url(project.repo_url)
        raw_yaml = fetch_manifest(owner, repo, token=github_token)
        parsed = parse_manifest(raw_yaml)
        phases = extract_phases(parsed)

        # Delete existing manifest and phases for this project
        db.query(Manifest).filter_by(project_id=project.id).delete()
        db.query(Phase).filter_by(project_id=project.id).delete()

        # Store new manifest
        manifest = Manifest(
            project_id=project.id,
            raw_yaml=raw_yaml,
            parsed_data=parsed,
            fetched_at=datetime.now(timezone.utc),
        )
        db.add(manifest)

        # Store denormalized phases
        for phase_data in phases:
            phase = Phase(
                project_id=project.id,
                phase_name=phase_data["phase_name"],
                status=phase_data["status"],
                assignees=phase_data["assignees"],
                metadata_=phase_data["metadata"],
            )
            db.add(phase)

        project.last_refreshed_at = datetime.now(timezone.utc)
        project.refresh_status = "success"
        project.refresh_error = None
        db.commit()

    except Exception as e:
        db.rollback()
        project.refresh_status = "error"
        project.refresh_error = str(e)
        db.commit()


def refresh_all_projects(db: Session, github_token: str) -> None:
    """Refresh manifests for all registered projects."""
    projects = db.query(Project).all()
    for project in projects:
        refresh_project(db, project, github_token)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_refresh.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
cd ~/devel/working/publishing-house-dashboard
git add src/backend/app/services/refresh.py src/backend/app/schemas/ src/backend/tests/test_refresh.py
git commit -m "Add refresh service and Pydantic schemas for project registration"
```

---

## Task 7: Projects API Endpoints

**Files:**
- Create: `src/backend/app/api/projects.py`
- Create: `src/backend/tests/test_api_projects.py`
- Modify: `src/backend/app/main.py`

- [ ] **Step 1: Write the failing tests**

Write to `src/backend/tests/test_api_projects.py`:

```python
from unittest.mock import patch

from tests.conftest import SAMPLE_MANIFEST_YAML


def test_register_project(client):
    with patch("app.api.projects.fetch_manifest", return_value=SAMPLE_MANIFEST_YAML):
        with patch("app.api.projects.parse_repo_url", return_value=("rhpds", "test")):
            response = client.post("/api/v1/projects", json={
                "name": "Test Workshop",
                "repo_url": "https://github.com/rhpds/test-project",
            })

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Workshop"
    assert data["repo_url"] == "https://github.com/rhpds/test-project"
    assert data["refresh_status"] == "success"
    assert len(data["phases"]) == 10


def test_register_duplicate_project(client):
    with patch("app.api.projects.fetch_manifest", return_value=SAMPLE_MANIFEST_YAML):
        with patch("app.api.projects.parse_repo_url", return_value=("rhpds", "test")):
            client.post("/api/v1/projects", json={
                "name": "Test",
                "repo_url": "https://github.com/rhpds/test-project",
            })
            response = client.post("/api/v1/projects", json={
                "name": "Test Again",
                "repo_url": "https://github.com/rhpds/test-project",
            })

    assert response.status_code == 409


def test_list_projects(client):
    with patch("app.api.projects.fetch_manifest", return_value=SAMPLE_MANIFEST_YAML):
        with patch("app.api.projects.parse_repo_url", return_value=("rhpds", "test")):
            client.post("/api/v1/projects", json={
                "name": "Test",
                "repo_url": "https://github.com/rhpds/test-project",
            })

    response = client.get("/api/v1/projects")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Test"
    assert len(data[0]["phases"]) == 10


def test_get_project_detail(client):
    with patch("app.api.projects.fetch_manifest", return_value=SAMPLE_MANIFEST_YAML):
        with patch("app.api.projects.parse_repo_url", return_value=("rhpds", "test")):
            create_resp = client.post("/api/v1/projects", json={
                "name": "Test",
                "repo_url": "https://github.com/rhpds/test-project",
            })

    project_id = create_resp.json()["id"]
    response = client.get(f"/api/v1/projects/{project_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test"
    assert data["manifest_raw"] is not None
    assert data["project_data"] is not None
    assert data["project_data"]["project"]["name"] == "Test Workshop"


def test_get_project_not_found(client):
    response = client.get("/api/v1/projects/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_refresh_project(client):
    with patch("app.api.projects.fetch_manifest", return_value=SAMPLE_MANIFEST_YAML):
        with patch("app.api.projects.parse_repo_url", return_value=("rhpds", "test")):
            create_resp = client.post("/api/v1/projects", json={
                "name": "Test",
                "repo_url": "https://github.com/rhpds/test-project",
            })

    project_id = create_resp.json()["id"]

    with patch("app.api.projects.refresh_project_service") as mock_refresh:
        response = client.post(f"/api/v1/projects/{project_id}/refresh")

    assert response.status_code == 200
    mock_refresh.assert_called_once()


def test_delete_project(client):
    with patch("app.api.projects.fetch_manifest", return_value=SAMPLE_MANIFEST_YAML):
        with patch("app.api.projects.parse_repo_url", return_value=("rhpds", "test")):
            create_resp = client.post("/api/v1/projects", json={
                "name": "Test",
                "repo_url": "https://github.com/rhpds/test-project",
            })

    project_id = create_resp.json()["id"]
    response = client.delete(f"/api/v1/projects/{project_id}")
    assert response.status_code == 204

    response = client.get(f"/api/v1/projects/{project_id}")
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd src/backend
pytest tests/test_api_projects.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement the projects API**

Write to `src/backend/app/api/projects.py`:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models import Project, Manifest, Phase
from app.schemas.project import ProjectCreate, ProjectWithPhases
from app.services.github_client import fetch_manifest, parse_repo_url, GitHubFetchError
from app.services.manifest_parser import parse_manifest, extract_phases
from app.services.refresh import refresh_project as refresh_project_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", status_code=201, response_model=ProjectWithPhases)
def register_project(data: ProjectCreate, db: Session = Depends(get_db)):
    # Check for duplicate
    existing = db.query(Project).filter_by(repo_url=data.repo_url).first()
    if existing:
        raise HTTPException(status_code=409, detail="Project with this repo URL already registered")

    # Validate repo URL and fetch manifest
    try:
        owner, repo = parse_repo_url(data.repo_url)
        raw_yaml = fetch_manifest(owner, repo, token=settings.github_token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except GitHubFetchError as e:
        raise HTTPException(status_code=400, detail=f"Cannot access manifest: {e}")

    # Create project
    project = Project(name=data.name, repo_url=data.repo_url)
    db.add(project)
    db.flush()

    # Parse and store manifest
    parsed = parse_manifest(raw_yaml)
    phases_data = extract_phases(parsed)

    from datetime import datetime, timezone

    manifest = Manifest(
        project_id=project.id,
        raw_yaml=raw_yaml,
        parsed_data=parsed,
        fetched_at=datetime.now(timezone.utc),
    )
    db.add(manifest)

    for phase_data in phases_data:
        phase = Phase(
            project_id=project.id,
            phase_name=phase_data["phase_name"],
            status=phase_data["status"],
            assignees=phase_data["assignees"],
            metadata_=phase_data["metadata"],
        )
        db.add(phase)

    project.refresh_status = "success"
    project.last_refreshed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(project)

    return _project_with_phases(project, db)


@router.get("", response_model=list[ProjectWithPhases])
def list_projects(db: Session = Depends(get_db)):
    projects = db.query(Project).order_by(Project.name).all()
    return [_project_with_phases(p, db) for p in projects]


@router.get("/{project_id}", response_model=ProjectWithPhases)
def get_project(project_id: uuid.UUID, db: Session = Depends(get_db)):
    project = db.query(Project).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return _project_with_phases(project, db, include_manifest=True)


@router.post("/{project_id}/refresh")
def refresh_project_endpoint(project_id: uuid.UUID, db: Session = Depends(get_db)):
    project = db.query(Project).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    refresh_project_service(db, project, github_token=settings.github_token)
    db.refresh(project)
    return _project_with_phases(project, db)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: uuid.UUID, db: Session = Depends(get_db)):
    project = db.query(Project).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()


def _project_with_phases(project: Project, db: Session, include_manifest: bool = False) -> dict:
    phases = db.query(Phase).filter_by(project_id=project.id).all()
    manifest = db.query(Manifest).filter_by(project_id=project.id).first() if include_manifest else None
    return {
        "id": project.id,
        "name": project.name,
        "repo_url": project.repo_url,
        "registered_at": project.registered_at,
        "last_refreshed_at": project.last_refreshed_at,
        "refresh_status": project.refresh_status,
        "refresh_error": project.refresh_error,
        "phases": [
            {
                "id": p.id,
                "phase_name": p.phase_name,
                "status": p.status,
                "assignees": p.assignees,
                "metadata_": p.metadata_,
            }
            for p in phases
        ],
        "manifest_raw": manifest.raw_yaml if manifest else None,
        "project_data": manifest.parsed_data if manifest else None,
    }
```

- [ ] **Step 4: Register the projects router in main.py**

Add to `src/backend/app/main.py` after the health router import:

```python
from app.api import health, projects

# ... after existing include_router:
app.include_router(projects.router, prefix="/api/v1")
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_api_projects.py -v
```

Expected: All 7 tests PASS.

- [ ] **Step 6: Run all backend tests**

```bash
pytest -v
```

Expected: All tests PASS (manifest parser + github client + refresh + api).

- [ ] **Step 7: Commit**

```bash
cd ~/devel/working/publishing-house-dashboard
git add src/backend/app/api/projects.py src/backend/app/main.py src/backend/tests/test_api_projects.py
git commit -m "Add projects API: registration, list, detail, refresh, delete"
```

---

## Task 8: Nightly Refresh Scheduler

**Files:**
- Modify: `src/backend/app/main.py`

- [ ] **Step 1: Add the scheduler to main.py**

Add to `src/backend/app/main.py`:

```python
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.refresh import refresh_all_projects


def _nightly_refresh():
    db = SessionLocal()
    try:
        refresh_all_projects(db, github_token=settings.github_token)
    finally:
        db.close()


scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(_nightly_refresh, "cron", hour=settings.refresh_hour, id="nightly_refresh")
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="Publishing House Dashboard", version="0.1.0", lifespan=lifespan)
```

Remove the old `app = FastAPI(...)` line and replace with the lifespan version. Keep all middleware and router registrations after it.

- [ ] **Step 2: Verify the app still starts**

```bash
cd src/backend
timeout 5 uvicorn app.main:app --port 8081 || true
```

Expected: App starts without errors (timeout kills it after 5s).

- [ ] **Step 3: Commit**

```bash
cd ~/devel/working/publishing-house-dashboard
git add src/backend/app/main.py
git commit -m "Add APScheduler nightly refresh job"
```

---

## Task 9: Frontend Scaffolding — Next.js + PatternFly

**Files:**
- Create: `src/frontend/package.json`
- Create: `src/frontend/next.config.ts`
- Create: `src/frontend/tsconfig.json`
- Create: `src/frontend/src/app/layout.tsx`
- Create: `src/frontend/src/app/page.tsx`
- Create: `src/frontend/src/app/globals.css`
- Create: `src/frontend/src/app/api/v1/[[...path]]/route.ts`

- [ ] **Step 1: Initialize Next.js project**

```bash
cd ~/devel/working/publishing-house-dashboard/src/frontend
npx create-next-app@latest . --typescript --app --src-dir --no-tailwind --no-eslint --import-alias "@/*"
```

When prompted, accept defaults. This creates the base Next.js structure.

- [ ] **Step 2: Install PatternFly and dependencies**

```bash
npm install @patternfly/react-core@^6 @patternfly/react-icons@^6 @patternfly/react-table@^6
```

- [ ] **Step 3: Write next.config.ts**

Replace `src/frontend/next.config.ts`:

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  skipTrailingSlashRedirect: true,
};

export default nextConfig;
```

- [ ] **Step 4: Write the API proxy route**

Write to `src/frontend/src/app/api/v1/[[...path]]/route.ts`:

```typescript
import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8081";

async function proxyRequest(request: NextRequest) {
  const path = request.nextUrl.pathname;
  const search = request.nextUrl.search;
  const targetUrl = `${BACKEND_URL}${path}${search}`;

  const headers: Record<string, string> = {
    "content-type": request.headers.get("content-type") || "application/json",
  };

  const forwardedUser = request.headers.get("x-forwarded-user");
  if (forwardedUser) {
    headers["x-forwarded-user"] = forwardedUser;
  }

  const body = request.method !== "GET" && request.method !== "HEAD"
    ? await request.text()
    : undefined;

  const response = await fetch(targetUrl, {
    method: request.method,
    headers,
    body,
    redirect: "manual",
  });

  const responseHeaders = new Headers();
  response.headers.forEach((value, key) => {
    if (key.toLowerCase() !== "transfer-encoding") {
      responseHeaders.set(key, value);
    }
  });

  const responseBody = await response.arrayBuffer();
  return new NextResponse(responseBody, {
    status: response.status,
    headers: responseHeaders,
  });
}

export const GET = proxyRequest;
export const POST = proxyRequest;
export const PUT = proxyRequest;
export const PATCH = proxyRequest;
export const DELETE = proxyRequest;
```

- [ ] **Step 5: Write globals.css**

Replace `src/frontend/src/app/globals.css`:

```css
@import "@patternfly/react-core/dist/styles/base.css";

body {
  margin: 0;
  padding: 0;
}
```

- [ ] **Step 6: Write the root layout with PatternFly shell**

Write to `src/frontend/src/app/layout.tsx`:

```tsx
"use client";

import "./globals.css";
import { usePathname } from "next/navigation";
import Link from "next/link";
import {
  Page,
  Masthead,
  MastheadMain,
  MastheadBrand,
  MastheadContent,
  PageSidebar,
  PageSidebarBody,
  Nav,
  NavList,
  NavItem,
  PageSection,
  Brand,
  Content,
} from "@patternfly/react-core";

const NAV_ITEMS = [
  { label: "Pipeline", href: "/pipeline" },
  { label: "Projects", href: "/projects" },
  { label: "Register", href: "/register" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  const masthead = (
    <Masthead>
      <MastheadMain>
        <MastheadBrand>
          <Content component="h3" style={{ color: "white", margin: 0 }}>
            Publishing House
          </Content>
        </MastheadBrand>
      </MastheadMain>
      <MastheadContent>
        <Content component="small" style={{ color: "var(--pf-t--global--color--nonstatus--gray--default)" }}>
          Content Lifecycle Dashboard
        </Content>
      </MastheadContent>
    </Masthead>
  );

  const sidebar = (
    <PageSidebar>
      <PageSidebarBody>
        <Nav>
          <NavList>
            {NAV_ITEMS.map((item) => (
              <NavItem key={item.href} isActive={pathname.startsWith(item.href)}>
                <Link href={item.href}>{item.label}</Link>
              </NavItem>
            ))}
          </NavList>
        </Nav>
      </PageSidebarBody>
    </PageSidebar>
  );

  return (
    <html lang="en">
      <body suppressHydrationWarning>
        <Page masthead={masthead} sidebar={sidebar}>
          <PageSection>{children}</PageSection>
        </Page>
      </body>
    </html>
  );
}
```

- [ ] **Step 7: Write the root page (redirect to /pipeline)**

Write to `src/frontend/src/app/page.tsx`:

```tsx
import { redirect } from "next/navigation";

export default function Home() {
  redirect("/pipeline");
}
```

- [ ] **Step 8: Verify the frontend starts**

```bash
cd src/frontend
npm run dev &
sleep 5
curl -s http://localhost:3000 | head -20
kill %1
```

Expected: HTML output with PatternFly page shell.

- [ ] **Step 9: Commit**

```bash
cd ~/devel/working/publishing-house-dashboard
git add src/frontend/
git commit -m "Scaffold Next.js frontend with PatternFly layout and API proxy"
```

---

## Task 10: Frontend Types + API Client

**Files:**
- Create: `src/frontend/src/types/index.ts`
- Create: `src/frontend/src/services/api.ts`

- [ ] **Step 1: Write TypeScript types**

Write to `src/frontend/src/types/index.ts`:

```typescript
export interface Phase {
  id: string;
  phase_name: string;
  status: "pending" | "in_progress" | "completed" | "skipped";
  assignees: string[];
  metadata_: Record<string, unknown>;
}

export interface Project {
  id: string;
  name: string;
  repo_url: string;
  registered_at: string;
  last_refreshed_at: string | null;
  refresh_status: "success" | "error" | "pending";
  refresh_error: string | null;
  phases: Phase[];
  manifest_raw?: string | null;
  project_data?: Record<string, unknown> | null;
}

export interface ProjectCreate {
  name: string;
  repo_url: string;
}

// Kanban column definitions
export const KANBAN_COLUMNS = [
  { id: "intake", label: "Intake", color: "#4dabf7", phases: ["intake", "vetting", "spec_refinement"] },
  { id: "approval", label: "Approval", color: "#ffd43b", phases: ["approval"] },
  { id: "content", label: "Content", color: "#69db7c", phases: ["writing", "editing"] },
  { id: "automation", label: "Automation", color: "#ff8787", phases: ["automation"] },
  { id: "code_security_review", label: "Code & Security", color: "#e599f7", phases: ["code_security_review"] },
  { id: "final_review", label: "Final Review", color: "#da77f2", phases: ["final_review"] },
  { id: "ready", label: "Ready", color: "#20c997", phases: ["ready_for_publishing"] },
] as const;

export type KanbanColumnId = (typeof KANBAN_COLUMNS)[number]["id"];

export interface Module {
  id: string;
  title: string;
  status: "pending" | "in_progress" | "drafted" | "approved";
  content_path?: string | null;
}

export interface AutomationSubsteps {
  catalog_item: string;
  requirements: string;
  automation_code: string;
  testing: string;
  e2e_checks: string;
}
```

- [ ] **Step 2: Write the API client**

Write to `src/frontend/src/services/api.ts`:

```typescript
import type { Project, ProjectCreate } from "@/types";

const API_BASE = "/api/v1";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`API error ${response.status}: ${errorText}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

export const api = {
  listProjects: () => request<Project[]>("/projects"),

  getProject: (id: string) => request<Project>(`/projects/${id}`),

  registerProject: (data: ProjectCreate) =>
    request<Project>("/projects", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  refreshProject: (id: string) =>
    request<Project>(`/projects/${id}/refresh`, { method: "POST" }),

  deleteProject: (id: string) =>
    request<void>(`/projects/${id}`, { method: "DELETE" }),
};
```

- [ ] **Step 3: Commit**

```bash
cd ~/devel/working/publishing-house-dashboard
git add src/frontend/src/types/ src/frontend/src/services/
git commit -m "Add TypeScript types and API client"
```

---

## Task 11: Shared Components — PhaseProgressBar + RefreshButton

**Files:**
- Create: `src/frontend/src/components/PhaseProgressBar.tsx`
- Create: `src/frontend/src/components/RefreshButton.tsx`

- [ ] **Step 1: Write the PhaseProgressBar component**

Write to `src/frontend/src/components/PhaseProgressBar.tsx`:

```tsx
"use client";

import { KANBAN_COLUMNS } from "@/types";
import type { Phase } from "@/types";
import { Tooltip } from "@patternfly/react-core";

interface PhaseProgressBarProps {
  phases: Phase[];
  size?: "sm" | "md";
}

function getPhaseStatus(phases: Phase[], phaseNames: readonly string[]): "completed" | "in_progress" | "skipped" | "pending" {
  const matchingPhases = phases.filter((p) => phaseNames.includes(p.phase_name));
  if (matchingPhases.length === 0) return "pending";

  const hasActive = matchingPhases.some((p) => p.status === "in_progress");
  if (hasActive) return "in_progress";

  const allDone = matchingPhases.every((p) => p.status === "completed" || p.status === "skipped");
  if (allDone) return "completed";

  return "pending";
}

export default function PhaseProgressBar({ phases, size = "sm" }: PhaseProgressBarProps) {
  const height = size === "sm" ? 8 : 28;

  return (
    <div style={{ display: "flex", gap: 3, alignItems: "center" }}>
      {KANBAN_COLUMNS.map((col) => {
        const status = getPhaseStatus(phases, col.phases);
        const isActive = status === "in_progress";
        const isComplete = status === "completed";

        const bgColor = isComplete || isActive ? col.color : "#333";
        const outline = isActive ? `2px solid ${col.color}` : "none";

        return (
          <Tooltip key={col.id} content={`${col.label}: ${status}`}>
            <div
              style={{
                width: size === "sm" ? 20 : undefined,
                flex: size === "md" ? 1 : undefined,
                height,
                borderRadius: size === "sm" ? 2 : 4,
                background: bgColor,
                outline,
                outlineOffset: 1,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "0.6rem",
                fontWeight: 600,
                color: isComplete || isActive ? "#1a1a2e" : "#666",
                cursor: "default",
              }}
            >
              {size === "md" && (isComplete ? `${col.label} ✓` : isActive ? `${col.label} ●` : col.label)}
            </div>
          </Tooltip>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Write the RefreshButton component**

Write to `src/frontend/src/components/RefreshButton.tsx`:

```tsx
"use client";

import { useState } from "react";
import { Button, Spinner } from "@patternfly/react-core";
import SyncAltIcon from "@patternfly/react-icons/dist/esm/icons/sync-alt-icon";
import { api } from "@/services/api";

interface RefreshButtonProps {
  projectId: string;
  onRefreshed?: () => void;
  variant?: "plain" | "secondary";
  label?: string;
}

export default function RefreshButton({ projectId, onRefreshed, variant = "plain", label }: RefreshButtonProps) {
  const [loading, setLoading] = useState(false);

  const handleRefresh = async () => {
    setLoading(true);
    try {
      await api.refreshProject(projectId);
      onRefreshed?.();
    } catch (error) {
      console.error("Refresh failed:", error);
    } finally {
      setLoading(false);
    }
  };

  if (variant === "plain") {
    return (
      <Button variant="plain" onClick={handleRefresh} isDisabled={loading} aria-label="Refresh project">
        {loading ? <Spinner size="sm" /> : <SyncAltIcon />}
      </Button>
    );
  }

  return (
    <Button variant="secondary" onClick={handleRefresh} isLoading={loading} icon={<SyncAltIcon />}>
      {label || "Refresh"}
    </Button>
  );
}
```

- [ ] **Step 3: Commit**

```bash
cd ~/devel/working/publishing-house-dashboard
git add src/frontend/src/components/
git commit -m "Add PhaseProgressBar and RefreshButton components"
```

---

## Task 12: Register Page

**Files:**
- Create: `src/frontend/src/app/register/page.tsx`

- [ ] **Step 1: Write the Register page**

Write to `src/frontend/src/app/register/page.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  PageSection,
  Content,
  Form,
  FormGroup,
  TextInput,
  Button,
  Alert,
  Card,
  CardBody,
} from "@patternfly/react-core";
import { api } from "@/services/api";

export default function RegisterPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [repoUrl, setRepoUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const project = await api.registerProject({ name, repo_url: repoUrl });
      router.push(`/projects/${project.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  const isValid = name.trim().length > 0 && repoUrl.trim().length > 0;

  return (
    <>
      <PageSection>
        <Content>
          <Content component="h1">Register Project</Content>
          <Content component="p">
            Register a Publishing House project by providing its GitHub repository URL. The dashboard
            will fetch the manifest and track lifecycle progress.
          </Content>
        </Content>
      </PageSection>
      <PageSection>
        <Card style={{ maxWidth: 600 }}>
          <CardBody>
            {error && (
              <Alert variant="danger" title="Registration failed" isInline style={{ marginBottom: "1rem" }}>
                {error}
              </Alert>
            )}
            <Form onSubmit={handleSubmit}>
              <FormGroup label="Project Name" isRequired fieldId="name">
                <TextInput
                  id="name"
                  value={name}
                  onChange={(_e, val) => setName(val)}
                  placeholder="e.g., DataSphere Workshop"
                  isRequired
                />
              </FormGroup>
              <FormGroup
                label="GitHub Repository URL"
                isRequired
                fieldId="repo-url"
                helperText="SSH or HTTPS URL. Must contain publishing-house/manifest.yaml."
              >
                <TextInput
                  id="repo-url"
                  value={repoUrl}
                  onChange={(_e, val) => setRepoUrl(val)}
                  placeholder="e.g., git@github.com:rhpds/my-workshop.git"
                  isRequired
                />
              </FormGroup>
              <Button type="submit" isDisabled={!isValid} isLoading={loading}>
                Register
              </Button>
            </Form>
          </CardBody>
        </Card>
      </PageSection>
    </>
  );
}
```

- [ ] **Step 2: Verify the page renders**

Start both services and open http://localhost:3001/register in a browser. Verify:
- Form renders with Name and Repo URL fields
- Submit button is disabled until both fields have content
- PatternFly styling is applied

- [ ] **Step 3: Commit**

```bash
cd ~/devel/working/publishing-house-dashboard
git add src/frontend/src/app/register/
git commit -m "Add project registration page"
```

---

## Task 13: Projects Table Page

**Files:**
- Create: `src/frontend/src/app/projects/page.tsx`

- [ ] **Step 1: Write the Projects table page**

Write to `src/frontend/src/app/projects/page.tsx`:

```tsx
"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  PageSection,
  Content,
  Toolbar,
  ToolbarContent,
  ToolbarItem,
  SearchInput,
  Label,
  Spinner,
  EmptyState,
  EmptyStateBody,
  Button,
} from "@patternfly/react-core";
import {
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  OuterScrollContainer,
  InnerScrollContainer,
} from "@patternfly/react-table";
import { api } from "@/services/api";
import type { Project } from "@/types";
import PhaseProgressBar from "@/components/PhaseProgressBar";
import RefreshButton from "@/components/RefreshButton";

function getModuleCount(project: Project): number {
  const writing = project.phases.find((p) => p.phase_name === "writing");
  const modules = writing?.metadata_?.modules as Array<unknown> | undefined;
  return modules?.length ?? 0;
}

function getAllAssignees(project: Project): string[] {
  const all = new Set<string>();
  for (const phase of project.phases) {
    for (const a of phase.assignees || []) {
      all.add(a);
    }
  }
  return Array.from(all);
}

function getProjectType(project: Project): string {
  return (project.project_data as Record<string, Record<string, string>> | undefined)?.project?.type ?? "—";
}

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  const loadProjects = useCallback(async () => {
    try {
      const data = await api.listProjects();
      setProjects(data);
    } catch (error) {
      console.error("Failed to load projects:", error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  const filtered = projects.filter((p) =>
    p.name.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) {
    return (
      <PageSection>
        <Spinner />
      </PageSection>
    );
  }

  if (projects.length === 0) {
    return (
      <PageSection>
        <EmptyState>
          <Content>
            <Content component="h1">No projects registered</Content>
          </Content>
          <EmptyStateBody>
            Register a Publishing House project to start tracking its lifecycle.
          </EmptyStateBody>
          <Link href="/register">
            <Button variant="primary">Register Project</Button>
          </Link>
        </EmptyState>
      </PageSection>
    );
  }

  return (
    <>
      <PageSection>
        <Content>
          <Content component="h1">Projects</Content>
        </Content>
      </PageSection>
      <PageSection>
        <Toolbar>
          <ToolbarContent>
            <ToolbarItem>
              <SearchInput
                placeholder="Search projects..."
                value={search}
                onChange={(_e, val) => setSearch(val)}
                onClear={() => setSearch("")}
              />
            </ToolbarItem>
            <ToolbarItem align={{ default: "alignEnd" }}>
              <Label>{filtered.length} projects</Label>
            </ToolbarItem>
          </ToolbarContent>
        </Toolbar>

        <OuterScrollContainer style={{ maxHeight: "calc(100vh - 280px)" }}>
          <InnerScrollContainer>
            <Table variant="compact" isStriped>
              <Thead>
                <Tr>
                  <Th width={25}>Project</Th>
                  <Th width={10}>Type</Th>
                  <Th width={10}>Modules</Th>
                  <Th width={15}>Assignees</Th>
                  <Th width={30} style={{ textAlign: "center" }}>Phase Progress</Th>
                  <Th width={10} style={{ textAlign: "center" }}>Actions</Th>
                </Tr>
              </Thead>
              <Tbody>
                {filtered.map((project) => (
                  <Tr key={project.id}>
                    <Td>
                      <Link href={`/projects/${project.id}`} style={{ fontWeight: 500 }}>
                        {project.name}
                      </Link>
                    </Td>
                    <Td>{getProjectType(project)}</Td>
                    <Td>{getModuleCount(project)}</Td>
                    <Td>{getAllAssignees(project).join(", ") || "—"}</Td>
                    <Td style={{ textAlign: "center" }}>
                      <PhaseProgressBar phases={project.phases} />
                    </Td>
                    <Td style={{ textAlign: "center" }}>
                      <RefreshButton projectId={project.id} onRefreshed={loadProjects} />
                    </Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          </InnerScrollContainer>
        </OuterScrollContainer>
      </PageSection>
    </>
  );
}
```

- [ ] **Step 2: Verify the page renders**

Start services, register a test project (using the publishing-house-example repo), then open http://localhost:3001/projects. Verify:
- Table shows the registered project
- Phase progress bar renders with correct colors
- Search filter works
- Refresh button triggers a re-fetch
- Project name links to detail page

- [ ] **Step 3: Commit**

```bash
cd ~/devel/working/publishing-house-dashboard
git add src/frontend/src/app/projects/page.tsx
git commit -m "Add projects table page with phase progress bars and search"
```

---

## Task 14: Pipeline Kanban Page

**Files:**
- Create: `src/frontend/src/components/ProjectCard.tsx`
- Create: `src/frontend/src/components/KanbanColumn.tsx`
- Create: `src/frontend/src/app/pipeline/page.tsx`

- [ ] **Step 1: Write the ProjectCard component**

Write to `src/frontend/src/components/ProjectCard.tsx`:

```tsx
"use client";

import Link from "next/link";
import type { Project, Phase } from "@/types";
import { KANBAN_COLUMNS } from "@/types";

interface ProjectCardProps {
  project: Project;
  columnId: string;
}

function getSubPhaseLabel(project: Project, columnId: string): string | null {
  const column = KANBAN_COLUMNS.find((c) => c.id === columnId);
  if (!column || column.phases.length <= 1) return null;

  const activePhase = project.phases.find(
    (p) => column.phases.includes(p.phase_name) && p.status === "in_progress"
  );
  return activePhase ? activePhase.phase_name.replace(/_/g, " ") : null;
}

function getModuleProgress(project: Project): string | null {
  const writing = project.phases.find((p) => p.phase_name === "writing");
  if (!writing || writing.status !== "in_progress") return null;
  const modules = writing.metadata_?.modules as Array<{ status: string }> | undefined;
  if (!modules) return null;
  const done = modules.filter((m) => m.status === "drafted" || m.status === "approved").length;
  return `${done}/${modules.length}`;
}

function getModuleCount(project: Project): number {
  const writing = project.phases.find((p) => p.phase_name === "writing");
  const modules = writing?.metadata_?.modules as Array<unknown> | undefined;
  return modules?.length ?? 0;
}

function getAssignees(project: Project, columnId: string): string[] {
  const column = KANBAN_COLUMNS.find((c) => c.id === columnId);
  if (!column) return [];
  const assignees = new Set<string>();
  for (const phase of project.phases) {
    if (column.phases.includes(phase.phase_name)) {
      for (const a of phase.assignees || []) {
        assignees.add(a);
      }
    }
  }
  return Array.from(assignees);
}

function hasContentActive(project: Project): boolean {
  const writing = project.phases.find((p) => p.phase_name === "writing");
  const editing = project.phases.find((p) => p.phase_name === "editing");
  return writing?.status === "in_progress" || editing?.status === "in_progress";
}

export default function ProjectCard({ project, columnId }: ProjectCardProps) {
  const column = KANBAN_COLUMNS.find((c) => c.id === columnId);
  const color = column?.color || "#888";
  const subPhase = getSubPhaseLabel(project, columnId);
  const moduleProgress = getModuleProgress(project);
  const moduleCount = getModuleCount(project);
  const assignees = getAssignees(project, columnId);
  const contentAlsoActive = columnId === "automation" && hasContentActive(project);

  return (
    <Link href={`/projects/${project.id}`} style={{ textDecoration: "none" }}>
      <div
        style={{
          background: "#252540",
          borderRadius: 6,
          padding: "0.5rem 0.6rem",
          marginBottom: "0.4rem",
          borderLeft: `3px solid ${color}`,
          cursor: "pointer",
        }}
      >
        <div style={{ fontSize: "0.8rem", fontWeight: 500, color: "#e0e0e0" }}>
          {project.name}
        </div>
        <div style={{ fontSize: "0.7rem", color: "#888", marginTop: "0.2rem" }}>
          {moduleCount > 0 ? `${moduleCount} mod` : ""}{assignees.length > 0 ? ` · ${assignees.join(", ")}` : ""}
        </div>
        {subPhase && (
          <div style={{ fontSize: "0.65rem", color, marginTop: "0.15rem" }}>
            ↳ {subPhase}{moduleProgress ? ` (${moduleProgress})` : ""}
          </div>
        )}
        {contentAlsoActive && (
          <div style={{ fontSize: "0.6rem", color: "#69db7c", marginTop: "0.1rem" }}>
            + content active
          </div>
        )}
      </div>
    </Link>
  );
}
```

- [ ] **Step 2: Write the KanbanColumn component**

Write to `src/frontend/src/components/KanbanColumn.tsx`:

```tsx
"use client";

import type { Project } from "@/types";
import ProjectCard from "./ProjectCard";

interface KanbanColumnProps {
  id: string;
  label: string;
  color: string;
  phaseNames: readonly string[];
  projects: Project[];
}

export default function KanbanColumn({ id, label, color, phaseNames, projects }: KanbanColumnProps) {
  return (
    <div
      style={{
        flex: 1,
        minWidth: 140,
        background: "#1a1a2e",
        borderRadius: 8,
        padding: "0.5rem",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        style={{
          fontSize: "0.75rem",
          fontWeight: 600,
          color,
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          padding: "0.25rem 0.5rem",
          marginBottom: "0.5rem",
        }}
      >
        {label}{" "}
        <span
          style={{
            background: `${color}22`,
            borderRadius: 10,
            padding: "0 6px",
            marginLeft: 4,
            fontSize: "0.7rem",
          }}
        >
          {projects.length}
        </span>
      </div>
      {phaseNames.length > 1 && (
        <div style={{ fontSize: "0.65rem", color: "#555", padding: "0 0.5rem 0.4rem", fontStyle: "italic" }}>
          {phaseNames.map((p) => p.replace(/_/g, " ")).join(" · ")}
        </div>
      )}
      <div style={{ flex: 1, overflowY: "auto" }}>
        {projects.length === 0 ? (
          <div style={{ color: "#444", fontSize: "0.75rem", fontStyle: "italic", textAlign: "center", padding: "1rem 0" }}>
            No projects
          </div>
        ) : (
          projects.map((p) => <ProjectCard key={p.id} project={p} columnId={id} />)
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Write the Pipeline page**

Write to `src/frontend/src/app/pipeline/page.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import {
  PageSection,
  Content,
  Spinner,
  EmptyState,
  EmptyStateBody,
  Button,
} from "@patternfly/react-core";
import Link from "next/link";
import { api } from "@/services/api";
import type { Project } from "@/types";
import { KANBAN_COLUMNS } from "@/types";
import KanbanColumn from "@/components/KanbanColumn";

function getKanbanColumn(project: Project): string {
  // Find the furthest-along active or completed column
  // Walk columns in reverse; return the first one that has an active or completed phase
  for (let i = KANBAN_COLUMNS.length - 1; i >= 0; i--) {
    const col = KANBAN_COLUMNS[i];
    const hasActive = project.phases.some(
      (p) => col.phases.includes(p.phase_name) && (p.status === "in_progress" || p.status === "completed")
    );
    if (hasActive) {
      // Special case: if this is "ready" and it's completed, keep it in ready
      // If it's just completed (not the current active work), check if something later is active
      const isActive = project.phases.some(
        (p) => col.phases.includes(p.phase_name) && p.status === "in_progress"
      );
      if (isActive) return col.id;
      // If completed but nothing later is active, this is the current column
      return col.id;
    }
  }
  return "intake"; // Default: nothing started
}

export default function PipelinePage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.listProjects().then(setProjects).catch(console.error).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <PageSection>
        <Spinner />
      </PageSection>
    );
  }

  if (projects.length === 0) {
    return (
      <PageSection>
        <EmptyState>
          <Content>
            <Content component="h1">No projects in the pipeline</Content>
          </Content>
          <EmptyStateBody>Register a project to see it on the board.</EmptyStateBody>
          <Link href="/register">
            <Button variant="primary">Register Project</Button>
          </Link>
        </EmptyState>
      </PageSection>
    );
  }

  // Assign each project to its kanban column
  const columnProjects: Record<string, Project[]> = {};
  for (const col of KANBAN_COLUMNS) {
    columnProjects[col.id] = [];
  }
  for (const project of projects) {
    const colId = getKanbanColumn(project);
    columnProjects[colId]?.push(project);
  }

  return (
    <>
      <PageSection>
        <Content>
          <Content component="h1">Pipeline</Content>
        </Content>
      </PageSection>
      <PageSection>
        <div style={{ display: "flex", gap: "0.75rem", minHeight: 400, overflowX: "auto" }}>
          {KANBAN_COLUMNS.map((col) => (
            <KanbanColumn
              key={col.id}
              id={col.id}
              label={col.label}
              color={col.color}
              phaseNames={col.phases}
              projects={columnProjects[col.id]}
            />
          ))}
        </div>
      </PageSection>
    </>
  );
}
```

- [ ] **Step 4: Verify the kanban renders**

Start services, ensure at least one project is registered, then open http://localhost:3001/pipeline. Verify:
- 7 kanban columns render with correct labels and colors
- Project cards appear in the correct column based on their phase status
- Cards show project name, module count, assignees
- Sub-phase labels show for grouped columns
- Clicking a card navigates to the project detail page

- [ ] **Step 5: Commit**

```bash
cd ~/devel/working/publishing-house-dashboard
git add src/frontend/src/components/ProjectCard.tsx src/frontend/src/components/KanbanColumn.tsx src/frontend/src/app/pipeline/
git commit -m "Add pipeline kanban page with project cards and column layout"
```

---

## Task 15: Project Detail Page

**Files:**
- Create: `src/frontend/src/components/PhaseAccordion.tsx`
- Create: `src/frontend/src/app/projects/[id]/page.tsx`

- [ ] **Step 1: Write the PhaseAccordion component**

Write to `src/frontend/src/components/PhaseAccordion.tsx`:

```tsx
"use client";

import { useState } from "react";
import type { Phase, Module, AutomationSubsteps } from "@/types";
import { KANBAN_COLUMNS } from "@/types";
import { Label } from "@patternfly/react-core";
import CheckCircleIcon from "@patternfly/react-icons/dist/esm/icons/check-circle-icon";

interface PhaseAccordionProps {
  phase: Phase;
  /** Map of phase_name → kanban column label for display */
  kanbanLabel: string;
  color: string;
}

const DEPENDENCY_HINTS: Record<string, string> = {
  writing: "Requires approval to be completed",
  editing: "Requires approval to be completed",
  automation: "Requires approval to be completed",
  code_security_review: "Requires content + automation to be completed",
  final_review: "Requires code & security review to be completed",
  ready_for_publishing: "Requires final review to be completed",
};

export default function PhaseAccordion({ phase, kanbanLabel, color }: PhaseAccordionProps) {
  const isActive = phase.status === "in_progress";
  const isComplete = phase.status === "completed" || phase.status === "skipped";
  const isPending = phase.status === "pending";

  const [expanded, setExpanded] = useState(isActive);

  const hasDetails = phase.metadata_ && Object.keys(phase.metadata_).length > 0;
  const canExpand = hasDetails && !isPending;

  const borderColor = isComplete || isActive ? color : "#333";
  const bgColor = isPending ? "#1e1e30" : "#252540";

  return (
    <div style={{ background: bgColor, borderRadius: 6, marginBottom: "0.5rem", borderLeft: `3px solid ${borderColor}` }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          padding: "0.6rem 0.75rem",
          cursor: canExpand ? "pointer" : "default",
        }}
        onClick={() => canExpand && setExpanded(!expanded)}
      >
        <div style={{ fontSize: "0.85rem", color: isPending ? "#555" : isActive ? "#e0e0e0" : "#aaa", fontWeight: isActive ? 500 : 400 }}>
          {isComplete && <span style={{ color, marginRight: "0.4rem" }}>✓</span>}
          {isActive && <span style={{ color, marginRight: "0.4rem" }}>●</span>}
          {isPending && <span style={{ marginRight: "0.4rem" }}>○</span>}
          {phase.phase_name.replace(/_/g, " ")}
          {isComplete && phase.metadata_?.approved_by && (
            <span style={{ fontSize: "0.7rem", color: "#666", marginLeft: "0.5rem" }}>
              approved by {String(phase.metadata_.approved_by)}
            </span>
          )}
          {isPending && DEPENDENCY_HINTS[phase.phase_name] && (
            <span style={{ fontSize: "0.7rem", color: "#444", marginLeft: "0.5rem" }}>
              {DEPENDENCY_HINTS[phase.phase_name]}
            </span>
          )}
          {isActive && phase.phase_name === "writing" && phase.metadata_?.modules && (
            <span style={{ fontSize: "0.7rem", color, marginLeft: "0.5rem" }}>
              {(phase.metadata_.modules as Module[]).filter((m) => m.status === "drafted" || m.status === "approved").length}
              {" of "}
              {(phase.metadata_.modules as Module[]).length} modules
            </span>
          )}
        </div>
        {canExpand && (
          <span style={{ color: "#666", fontSize: "0.75rem" }}>{expanded ? "▾" : "▸"}</span>
        )}
      </div>

      {expanded && phase.phase_name === "writing" && phase.metadata_?.modules && (
        <div style={{ padding: "0 0.75rem 0.75rem", paddingLeft: "1.75rem" }}>
          <div style={{ fontSize: "0.75rem", color: "#888", marginBottom: "0.4rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Modules
          </div>
          {(phase.metadata_.modules as Module[]).map((mod) => (
            <div key={mod.id} style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem", marginBottom: "0.2rem" }}>
              <span style={{ color: mod.status === "pending" ? "#666" : "#aaa" }}>
                {(mod.status === "drafted" || mod.status === "approved") && <span style={{ color: "#69db7c", marginRight: "0.3rem" }}>✓</span>}
                {mod.status === "in_progress" && <span style={{ color: "#4dabf7", marginRight: "0.3rem" }}>●</span>}
                {mod.status === "pending" && <span style={{ marginRight: "0.3rem" }}>○</span>}
                {mod.title}
              </span>
              <Label isCompact color={mod.status === "approved" ? "green" : mod.status === "drafted" ? "blue" : mod.status === "in_progress" ? "cyan" : "grey"}>
                {mod.status}
              </Label>
            </div>
          ))}
        </div>
      )}

      {expanded && phase.phase_name === "automation" && phase.metadata_?.substeps && (
        <div style={{ padding: "0 0.75rem 0.75rem", paddingLeft: "1.75rem" }}>
          <div style={{ fontSize: "0.75rem", color: "#888", marginBottom: "0.4rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Substeps
          </div>
          {Object.entries(phase.metadata_.substeps as AutomationSubsteps).map(([key, status]) => (
            <div key={key} style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem", marginBottom: "0.2rem" }}>
              <span style={{ color: status === "pending" || status === "deferred" ? "#666" : "#aaa" }}>
                {status === "completed" && <span style={{ color: "#69db7c", marginRight: "0.3rem" }}>✓</span>}
                {status === "in_progress" && <span style={{ color: "#4dabf7", marginRight: "0.3rem" }}>●</span>}
                {(status === "pending" || status === "deferred") && <span style={{ marginRight: "0.3rem" }}>○</span>}
                {key.replace(/_/g, " ")}
              </span>
              <Label isCompact color={status === "completed" ? "green" : status === "in_progress" ? "cyan" : status === "deferred" ? "orange" : "grey"}>
                {status}
              </Label>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Write the Project Detail page**

Write to `src/frontend/src/app/projects/[id]/page.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  PageSection,
  Content,
  Spinner,
  Label,
  Card,
  CardBody,
  Split,
  SplitItem,
} from "@patternfly/react-core";
import { api } from "@/services/api";
import type { Project } from "@/types";
import { KANBAN_COLUMNS } from "@/types";
import PhaseProgressBar from "@/components/PhaseProgressBar";
import PhaseAccordion from "@/components/PhaseAccordion";
import RefreshButton from "@/components/RefreshButton";

const PHASE_ORDER = [
  "intake", "vetting", "spec_refinement", "approval",
  "writing", "editing", "automation",
  "code_security_review", "final_review", "ready_for_publishing",
];

function phaseToKanbanColumn(phaseName: string): { label: string; color: string } {
  for (const col of KANBAN_COLUMNS) {
    if ((col.phases as readonly string[]).includes(phaseName)) {
      return { label: col.label, color: col.color };
    }
  }
  return { label: phaseName, color: "#888" };
}

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

function getProjectMeta(project: Project): Record<string, string> {
  const pd = project.project_data as Record<string, Record<string, string>> | undefined;
  return {
    type: pd?.project?.type ?? "—",
    owner: pd?.project?.owner ?? "—",
    autonomy: pd?.project?.autonomy ?? "—",
    created: pd?.project?.created ?? "—",
  };
}

function getIntegrations(project: Project): Record<string, string | null> {
  const pd = project.project_data as Record<string, Record<string, string | null>> | undefined;
  return pd?.integrations ?? {};
}

function getAllAssignees(project: Project): Array<{ name: string; phase: string }> {
  const result: Array<{ name: string; phase: string }> = [];
  const seen = new Set<string>();
  for (const phase of project.phases) {
    for (const a of phase.assignees || []) {
      const key = `${a}:${phase.phase_name}`;
      if (!seen.has(key)) {
        seen.add(key);
        result.push({ name: a, phase: phase.phase_name.replace(/_/g, " ") });
      }
    }
  }
  return result;
}

export default function ProjectDetailPage() {
  const params = useParams();
  const projectId = params.id as string;
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);

  const loadProject = async () => {
    try {
      const data = await api.getProject(projectId);
      setProject(data);
    } catch (error) {
      console.error("Failed to load project:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProject();
  }, [projectId]);

  if (loading) {
    return <PageSection><Spinner /></PageSection>;
  }

  if (!project) {
    return (
      <PageSection>
        <Content>
          <Content component="h1">Project not found</Content>
        </Content>
      </PageSection>
    );
  }

  const meta = getProjectMeta(project);
  const integrations = getIntegrations(project);
  const assignees = getAllAssignees(project);
  const sortedPhases = [...project.phases].sort(
    (a, b) => PHASE_ORDER.indexOf(a.phase_name) - PHASE_ORDER.indexOf(b.phase_name)
  );

  return (
    <>
      <PageSection>
        <div style={{ marginBottom: "1rem" }}>
          <Link href="/projects" style={{ fontSize: "0.85rem" }}>← Projects</Link>
        </div>
        <Split hasGutter>
          <SplitItem isFilled>
            <Content>
              <Content component="h1" style={{ marginBottom: "0.25rem" }}>{project.name}</Content>
            </Content>
            <div style={{ display: "flex", gap: "0.75rem", fontSize: "0.85rem", color: "#888" }}>
              <Label isCompact>{meta.type}</Label>
              <span>Owner: {meta.owner}</span>
            </div>
          </SplitItem>
          <SplitItem>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span style={{ fontSize: "0.75rem", color: "#666" }}>
                Last refreshed: {formatDate(project.last_refreshed_at)}
              </span>
              <RefreshButton projectId={project.id} variant="secondary" label="Refresh" onRefreshed={loadProject} />
            </div>
          </SplitItem>
        </Split>
      </PageSection>

      <PageSection>
        <div style={{ marginBottom: "1.5rem" }}>
          <PhaseProgressBar phases={project.phases} size="md" />
        </div>

        <Split hasGutter>
          {/* Left pane: Phase details */}
          <SplitItem isFilled style={{ flex: 3 }}>
            {sortedPhases.map((phase) => {
              const { label, color } = phaseToKanbanColumn(phase.phase_name);
              return (
                <PhaseAccordion
                  key={phase.id}
                  phase={phase}
                  kanbanLabel={label}
                  color={color}
                />
              );
            })}
          </SplitItem>

          {/* Right pane: Project info */}
          <SplitItem style={{ flex: 2, minWidth: 250 }}>
            <Card isFlat style={{ marginBottom: "0.75rem" }}>
              <CardBody>
                <div style={{ fontSize: "0.75rem", color: "#888", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.5rem" }}>
                  Project Info
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem", fontSize: "0.85rem" }}>
                  {Object.entries(meta).map(([key, val]) => (
                    <div key={key} style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ color: "#888" }}>{key}</span>
                      <span>{val}</span>
                    </div>
                  ))}
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "#888" }}>registered</span>
                    <span>{formatDate(project.registered_at)}</span>
                  </div>
                </div>
              </CardBody>
            </Card>

            <Card isFlat style={{ marginBottom: "0.75rem" }}>
              <CardBody>
                <div style={{ fontSize: "0.75rem", color: "#888", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.5rem" }}>
                  Links
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem", fontSize: "0.85rem" }}>
                  <a href={project.repo_url.replace("git@github.com:", "https://github.com/").replace(/\.git$/, "")} target="_blank" rel="noopener">
                    GitHub Repo ↗
                  </a>
                  {integrations.showroom_repo ? (
                    <a href={String(integrations.showroom_repo)} target="_blank" rel="noopener">Showroom ↗</a>
                  ) : (
                    <span style={{ color: "#555" }}>Showroom — not set</span>
                  )}
                  {integrations.automation_repo ? (
                    <a href={String(integrations.automation_repo)} target="_blank" rel="noopener">Automation ↗</a>
                  ) : (
                    <span style={{ color: "#555" }}>Automation — not set</span>
                  )}
                </div>
              </CardBody>
            </Card>

            {assignees.length > 0 && (
              <Card isFlat>
                <CardBody>
                  <div style={{ fontSize: "0.75rem", color: "#888", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.5rem" }}>
                    Assignees
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem", fontSize: "0.85rem" }}>
                    {assignees.map((a) => (
                      <div key={`${a.name}-${a.phase}`} style={{ display: "flex", justifyContent: "space-between" }}>
                        <span>{a.name}</span>
                        <Label isCompact color="blue">{a.phase}</Label>
                      </div>
                    ))}
                  </div>
                </CardBody>
              </Card>
            )}
          </SplitItem>
        </Split>
      </PageSection>
    </>
  );
}
```

- [ ] **Step 3: Verify the detail page renders**

Start services, navigate to a registered project from the projects table. Verify:
- Progress bar shows at the top with labeled phases
- Completed phases are collapsed with checkmarks
- Active phases are expanded (writing shows module list, automation shows substeps)
- Pending phases are greyed out with dependency hints
- Sidebar shows project info, links, and assignees
- Layout is responsive and balanced between left/right panes
- Refresh button works and reloads the page data

- [ ] **Step 4: Commit**

```bash
cd ~/devel/working/publishing-house-dashboard
git add src/frontend/src/components/PhaseAccordion.tsx src/frontend/src/app/projects/\[id\]/
git commit -m "Add project detail page with phase accordions and project sidebar"
```

---

## Task 16: End-to-End Smoke Test

**Files:** None (testing only)

- [ ] **Step 1: Start all services**

```bash
cd ~/devel/working/publishing-house-dashboard
./dev-services.sh start
```

Wait for all services to be ready.

- [ ] **Step 2: Run backend tests**

```bash
cd src/backend
source ~/.virtualenvs/ph-dashboard/bin/activate
pytest -v
```

Expected: All tests pass.

- [ ] **Step 3: Manual smoke test in browser**

Open http://localhost:3001 and verify:

1. **Pipeline page** loads (redirected from `/`). Shows empty state with "Register Project" button.
2. Navigate to **Register**. Enter:
   - Name: `Publishing House Example`
   - Repo URL: `git@github.com:rhpds/rhdp-publishing-house-example.git`
   - Submit. Should redirect to project detail page.
3. **Project detail** page shows:
   - Progress bar with completed phases highlighted
   - Accordion sections with module and substep details
   - Sidebar with project info and links
4. Navigate to **Projects** table. Verify:
   - Registered project appears in the table
   - Phase progress bar renders correctly
   - Refresh button works
5. Navigate to **Pipeline**. Verify:
   - Project card appears in the correct kanban column
   - Card shows name, module count, assignee

- [ ] **Step 4: Final commit if any cleanup was needed**

```bash
cd ~/devel/working/publishing-house-dashboard
git add -A
git status  # Review what changed
git commit -m "Polish from end-to-end smoke test"
```

Only commit if there were fixes. If the smoke test passed clean, skip this step.

- [ ] **Step 5: Create GitHub repo and push**

```bash
cd ~/devel/working/publishing-house-dashboard
gh repo create rhpds/publishing-house-dashboard --private --source=. --push
```

---

## Summary

| Task | Component | Tests |
|------|-----------|-------|
| 1 | Project scaffolding, dev services, virtualenv | — |
| 2 | Backend core: config, database, health endpoint | 1 |
| 3 | Database models + Alembic migration | — |
| 4 | Manifest parser service | 8 |
| 5 | GitHub client service | 6 |
| 6 | Refresh service + schemas | 3 |
| 7 | Projects API endpoints | 7 |
| 8 | Nightly refresh scheduler | — |
| 9 | Frontend scaffolding: Next.js + PatternFly | — |
| 10 | TypeScript types + API client | — |
| 11 | Shared components: PhaseProgressBar, RefreshButton | — |
| 12 | Register page | visual |
| 13 | Projects table page | visual |
| 14 | Pipeline kanban page | visual |
| 15 | Project detail page | visual |
| 16 | End-to-end smoke test | manual |

**Total: 16 tasks, 25 automated tests, 4 visual verification steps, 1 end-to-end smoke test.**
