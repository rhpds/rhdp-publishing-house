# System Architecture

## Component Map

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Developer Hub (RHDH)                          │
│  ┌──────────────┐  ┌────────────────┐  ┌──────────────────────────┐ │
│  │ PH Workflows │  │ Scaffolder     │  │ Catalog                  │ │
│  │ Plugin       │  │ Backend Module │  │ (component registration) │ │
│  └──────┬───────┘  └───────┬────────┘  └──────────────────────────┘ │
└─────────┼──────────────────┼────────────────────────────────────────┘
          │ proxy            │ direct
          ▼                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        Central API (FastAPI)                         │
│  Routers: projects│validate│drift│auth│messages│jira│litellm│cleanup │
│  Services: validation│drift│github│sonataflow│litellm│rcars          │
└──────┬────────┬──────────┬──────────┬──────────┬─────────────────────┘
       │        │          │          │          │
       ▼        ▼          ▼          ▼          ▼
┌──────────┐ ┌──────┐ ┌────────┐ ┌────────┐ ┌──────┐
│SonataFlow│ │GitHub│ │Keycloak│ │  Jira  │ │RCARS │
│ Runtime  │ │ API  │ │ OIDC   │ │  Cloud │ │ API  │
└──────────┘ └──────┘ └────────┘ └────────┘ └──────┘
       │
       ▼
┌──────────────────────┐
│ SonataFlow Data Index│
│ (PostgreSQL-backed)  │
└──────────────────────┘
```

## Integration Points

| From | To | Protocol | Purpose |
|---|---|---|---|
| RHDH Plugin | Central API | HTTP (proxy) | Workflow list, detail, actions |
| Scaffolder | Central API | HTTP (direct) | Start workflow on project creation |
| Scaffolder | GitHub | REST API | Create repo from template |
| Central API | SonataFlow Runtime | CloudEvents (HTTP) | Advance workflow state |
| Central API | SonataFlow Data Index | GraphQL | Query workflow state |
| Central API | GitHub | REST API | Sparse clone for validation, file reads |
| Central API | Keycloak | OIDC | Token verification, user auth |
| Central API | Jira Cloud | REST API | Epic/task creation, sync, comments |
| Central API | RCARS | REST API | Catalog overlap advisor |
| Central API | LiteLLM/MaaS | REST API | Drift semantic analysis, virtual keys |
| SonataFlow Runtime | Central API | REST (OpenAPI) | Jira epic creation, task sync |
| CronJobs | Central API | HTTP | Drift checks, inactivity checks, cleanup |
| Claude Skills | Central API | HTTP (via tools scripts) | Intake submission, workflow data, validation |
| Claude Skills | GitHub | Git CLI | Clone, commit, push |

## Data Flow: Project Lifecycle

```
Scaffolder Template
    │
    ├─► GitHub: create repo from template + skeleton overlay
    ├─► Central API: POST /projects/{slug} → CloudEvent → SonataFlow
    └─► RHDH Catalog: register component
         │
         ▼
Claude Skill (in DevSpaces)
    │
    ├─► reads/writes repo files (spec.yaml, design.md, modules)
    ├─► tools scripts → Central API (workflow data, policy, RCARS, submit)
    └─► git push → triggers validation on submit
         │
         ▼
Central API (on submit)
    │
    ├─► sparse clone from GitHub
    ├─► run validation checks (groups A-J by stage)
    ├─► send CloudEvent to SonataFlow (advance state)
    └─► Jira sync (if rhdp_published)
         │
         ▼
RHDH Plugin (reviewer UI)
    │
    ├─► shows workflow state, approval checklist, drift status
    ├─► approve/reject → Central API → CloudEvent → SonataFlow
    └─► messaging between reviewer and author
```

## Authentication Architecture

```
┌─────────────────┐     ┌──────────┐     ┌─────────────┐
│ Backstage User  │────►│ Keycloak │────►│ Central API  │
│ (SSO login)     │     │ OIDC     │     │ Token Exchange│
└─────────────────┘     └──────────┘     └──────┬──────┘
                                                │
                                         HMAC-signed key
                                         (7-day TTL)
                                                │
                                                ▼
                                        ┌──────────────┐
                                        │ SQLite Cache │
                                        │ (PVC backup) │
                                        └──────────────┘
```

Token types:
- **Service token**: `ph_api_key` env var — used by SonataFlow, CronJobs, scaffolder
- **Signed key**: HMAC-signed, 7-day TTL — issued to users via Keycloak exchange
- **RBAC bitmask**: encoded in signed key, 6 groups (content-review=1, infra-review=2, developers=4, administrators=8, content-developers=16, operations=32)

## Persistence

| Store | Technology | What It Holds |
|---|---|---|
| SonataFlow PostgreSQL | PostgreSQL 15 (StatefulSet, 5Gi PVC) | Workflow instances, state, variables |
| RHDH PostgreSQL | PostgreSQL 15 (StatefulSet, 1Gi PVC) | Catalog entities, scaffolder history |
| Central API PVC | SQLite file (1Gi PVC) | Token cache encrypted backup |
| Vault | HashiCorp Vault (StatefulSet) | All secrets (API keys, tokens, credentials) |
| GitHub | Git repos | Project source, spec, content, catalog-info |
| Jira Cloud | Atlassian SaaS | Epics, tasks, comments |

## External Dependencies

| Service | URL | Purpose |
|---|---|---|
| GitHub API | github.com/rhpds/* | Repo management, file access |
| Jira Cloud | redhat.atlassian.net | Project tracking (RHDPCD project) |
| LiteLLM/MaaS | maas-rhdp.apps.maas.redhatworkshops.io | AI model proxy (drift analysis) |
| RCARS | rcars-api.apps.ocpv-infra01.dal12.infra.demo.redhat.com | Catalog overlap detection |
| Quay.io | quay.io/rhpds/* | Container images |
| Red Hat Registry | registry.redhat.io | RHDH, SonataFlow, PostgreSQL images |
