# Central API

**Version:** 1.21.9 (code), 1.21.9 (deployed on infra02)
**Image:** `quay.io/rhpds/central-api:1.21.9`
**Runtime:** Python 3.11-slim, uvicorn, 4 workers, port 8000
**Framework:** FastAPI 0.115.0 + pydantic-settings 2.5.2

## Endpoints

All endpoints are prefixed with `/api/v1`.

### Projects Router (`routers/projects.py`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/projects/{slug}` | Bearer | Start new workflow (creates SonataFlow instance, sends CloudEvent) |
| GET | `/projects/{project_id}/workflow-data` | Bearer | Get workflow data (variables) from data index |
| GET | `/projects/workflow-state/{workflow_id}` | Bearer | Get current stage from process nodes |
| POST | `/projects/intake/{slug}` | Bearer | Submit intake (validates spec, sends IntakeCompleteEvent) |
| POST | `/projects/development/{slug}` | Bearer | Submit development (validates, sends DevelopmentCompleteEvent) |
| POST | `/projects/testing/{slug}` | Bearer | Submit testing (validates, sends TestingCompleteEvent) |
| POST | `/projects/{slug}/content-review/approve` | Bearer (content-review group) | Approve content review |
| POST | `/projects/{slug}/content-review/reject` | Bearer (content-review group) | Reject content review with reasons |
| POST | `/projects/{slug}/infra-review/approve` | Bearer (infra-review group) | Approve infra review |
| POST | `/projects/{slug}/infra-review/reject` | Bearer (infra-review group) | Reject infra review with reasons |
| POST | `/projects/{slug}/env-setup/submit` | Bearer | Submit env setup completion |
| POST | `/projects/{slug}/drift/approve` | Bearer | Approve drift (updates baselineSha) |
| DELETE | `/projects/{project_slug}` | Bearer (administrators group) | Delete project (workflow, catalog, Jira) |

### Auth Router (`routers/auth.py`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/auth/config` | None | Public OIDC config (Keycloak URL, realm, clientId) |
| POST | `/keys/oidc` | Keycloak token | Exchange Keycloak token for signed API key |
| POST | `/keys/exchange` | Backstage identity JWT | Exchange Backstage JWT for signed API key |
| POST | `/keys/anonymous` | Bearer (service) | Generate anonymous key (for workspace setup) |
| GET | `/tokens` | Bearer (administrators) | List all cached tokens |
| GET | `/tokens/search` | Bearer (administrators) | Search tokens by email |
| DELETE | `/tokens/{email}` | Bearer (administrators) | Revoke token for specific user |
| DELETE | `/tokens` | Bearer (administrators) | Revoke all tokens |

### Validate Router (`routers/validate.py`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/spec/validation/policy` | Bearer | Get validation policy (products, verbs, content types) |
| POST | `/spec/validation/{slug}` | Bearer | Run validation checks on repo (stage-aware) |

### Drift Router (`routers/drift.py`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/drift/{slug}` | Bearer | Run drift detection (structural + semantic + infra) |

### Jira Router (`routers/jira.py`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/jira/epic` | Bearer | Create Jira epic for project |
| POST | `/jira/sync` | Bearer | Sync Jira tasks for stage |
| POST | `/jira/{epic_key}/comment` | Bearer | Add comment to epic |
| GET | `/jira/{epic_key}/comments` | Bearer | Get epic comments |
| POST | `/jira/{epic_key}/task/{task_id}/complete` | Bearer | Transition task to Done |

### Messages Router (`routers/messages.py`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/messages/{slug}/messages` | Bearer | Post review message |
| GET | `/messages/{slug}/messages` | Bearer | Get messages for project |
| POST | `/messages/{slug}/messages/read` | Bearer | Mark messages as read |

### LiteLLM Router (`routers/litellm.py`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/litellm/keys/generate` | Bearer | Generate LiteLLM virtual key for MaaS proxy |

### Cleanup Router (`routers/cleanup.py`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/cleanup/completed` | Bearer (service) | Clean up completed/errored workflows |

### Inline Endpoints (main.py)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/health` | None | Health check (returns version, timestamp) |
| POST | `/rcars/advisor` | Bearer | Submit RCARS advisor query |
| GET | `/rcars/advisor/{job_id}` | Bearer | Poll RCARS advisor result |
| GET | `/rcars/catalog/{ci_name}` | Bearer | Get RCARS catalog item by name |
| GET | `/rcars/health` | None | RCARS connectivity check |

## Services

### Validation (`services/validation/`)

Validation runs check groups A-J, selected by stage.

#### Check Groups

| Group | Module | Checks | What It Validates |
|---|---|---|---|
| A | `spec_fields.py` | A-01 to A-11 | Required spec.yaml fields |
| B | `spec_conditional.py` | B-01 to B-07 | Conditional field consistency |
| C | `design_structure.py` | dynamic | design.md structure (11 sections) |
| D | `module_outlines.py` | dynamic | Module outline required sections |
| E | `cross_validation.py` | dynamic | Design-to-spec cross-checks |
| F | `approval_checklist.py` | dynamic | Approval checklist completeness |
| H | `vocabulary.py` | H-01 to H-05 | Values against policy vocabulary |
| I | `auto_compute.py` | I-01 to I-03 | Auto-computed fields (peak envs, cost) |
| J | `development_checks.py` | J-01 to J-09 | Development artifacts completeness |

#### Stage-to-Group Mapping

| Stage | Groups |
|---|---|
| intake | A, B, C, D, E, F, H, I |
| review | A, B, C, D, E, F |
| development | A, B, C, D, E, F, H, I, J |
| testing | A, B, C, D, E, F, H, I, J |

#### Required Fields (Group A)

| Check | Field | Required When |
|---|---|---|
| A-01 | `spec.title` | Always |
| A-02 | `spec.learning_objectives` | Always (non-empty list) |
| A-03 | `spec.modules` | Always (non-empty list) |
| A-04 | `spec.duration_hours` | Always |
| A-05 | `project.content_type` | Always |
| A-06 | `spec.audience` | Always |
| A-07 | `spec.environment.topology` | Always |
| A-08 | `spec.environment.ocp_version` | platform = ocp |
| A-10 | `spec.environment.cluster_type` | platform = ocp |
| A-11 | `spec.environment.platform` | Always |

#### Conditional Checks (Group B)

| Check | Rule |
|---|---|
| B-01 | Sizing consistency: if worker_count > 0, worker_cpu/ram/disk required. If rhel-vms, vms_per_student required with cpu/ram per VM |
| B-02 | max_concurrent_users required if topology = shared-cluster |
| B-03 | AI fields: if ai_requirement = maas or gpu, ai_model_tier required. If frontier or gpu, ai_justification required |
| B-04 | AAP version required if AAP in products |
| B-05 | External services must not contain vague entries |
| B-06 | Non-GA access plan required if non_ga_products non-empty |
| B-07 | GPU type required if gpu_nodes > 0 |

### Drift Detection (`services/drift.py`)

Three drift dimensions:

| Dimension | Method | What It Compares |
|---|---|---|
| Structural | Field diff | spec.yaml fields at auditTrailSha vs HEAD |
| Semantic | LLM (Claude Haiku via MaaS) | design.md content drift summary |
| Infrastructure | Field diff | spec.environment changes affecting sizing/cost |

Cache: drift results cached with configurable TTL (default 3 days / 259200s).

### GitHub Service (`services/github.py`)

- Sparse clone (shallow, filtered) for validation
- File content fetch via API
- Directory listing
- Catalog-info.yaml management
- HEAD SHA resolution

### SonataFlow Service (`services/sonataflow.py`)

- Create workflow instance
- Send CloudEvent (typed, with correlation by projectid)
- Get instance by ID

## Auth / RBAC

### Token Types

| Type | How Issued | TTL | Use |
|---|---|---|---|
| Service token | `PH_API_KEY` env var | Permanent | SonataFlow, CronJobs, scaffolder |
| Signed key | HMAC-signed via `/keys/oidc` or `/keys/exchange` | 7 days | User API access |

### RBAC Groups (Bitmask)

| Group | Bit | Can Do |
|---|---|---|
| rhdp-content-review | 1 | Approve/reject content review |
| rhdp-infra-review | 2 | Approve/reject infra review |
| rhdp-developers | 4 | Standard developer access |
| rhdp-administrators | 8 | Delete projects, manage tokens, maintenance |
| rhdp-content-developers | 16 | Content developer access |
| rhdp-operations | 32 | Operations access |

### Token Cache

- In-memory dict with SQLite encrypted backup on PVC (`/data/token-cache.db`)
- Backup loop: every 24 hours
- Restored on startup, saved on shutdown

## Configuration (`config.py`)

| Setting | Default | Notes |
|---|---|---|
| `api_version` | `1.21.9` | |
| `sonataflow_url` | `http://publishinghouseworkflow.publishing-house:80` | Runtime pod |
| `sonataflow_graphql_url` | `http://publishinghouseworkflow.publishing-house:80` | Dev mode (runtime). Preview mode uses data-index service |
| `litellm_api_url` | `https://maas-rhdp.apps.maas.redhatworkshops.io` | |
| `rcars_url` | `https://rcars-api.apps.ocpv-infra01.dal12.infra.demo.redhat.com` | |
| `rhdh_internal_url` | `http://backstage-developer-hub.publishing-house.svc.cluster.local` | |
| `sonataflow_db_host` | `sonataflow-postgresql.publishing-house.svc.cluster.local` | |
| `api_key_ttl_days` | 7 | |
| `drift_cache_ttl_seconds` | 259200 (3 days) | |
| `token_cache_path` | `/data/token-cache.db` | |

## Python Dependencies

fastapi 0.115.0, uvicorn 0.32.0, pydantic 2.9.2, pydantic-settings 2.5.2, httpx 0.27.2, pyyaml 6.0.2, cloudevents 1.11.0, kubernetes 31.0.0, python-jose 3.3.0, python-keycloak 4.2.2, psycopg2-binary 2.9.10
