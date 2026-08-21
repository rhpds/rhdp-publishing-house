# Deployment

**Playbook:** `deployment/deploy.yml`
**Inventory:** localhost
**Pre-tasks:** Validate `ocp_apps_domain`, verify OCP connection

## Roles (in order)

### 1. Vault

**Tags:** `vault`, `vault-deploy`, `vault-secrets`

**Deploy phase:**
- Creates vault namespace
- ServiceAccount, RBAC (ClusterRoleBinding for token review)
- ConfigMaps (server config, agent config)
- Services (internal + active)
- StatefulSet (1 replica)
- Auto-unseal CronJob
- Route (edge TLS)
- Agent Injector (Deployment, MutatingWebhookConfiguration, NetworkPolicy)

**Post-deploy:**
- Waits for vault initialization
- Copies unseal keys to local file
- Logs in with root token
- Creates `rhdh-policy` (read access to kv/data/*)
- Enables Kubernetes auth backend
- Creates `rhdh-role` bound to publishing-house namespace
- Enables KV v2 secrets engine

**Secrets phase:**
- Creates app namespace (`publishing-house`)
- Writes secrets to Vault at `kv/{base_path}/`:
  - `api` — PH API key, OIDC settings
  - `github` — GitHub token
  - `jira` — Jira URL, email, API token
  - `litellm` — LiteLLM master key
  - `ph-internal-ai` — Internal AI API key
  - `rcars` — RCARS API key
  - `devspaces-github-oauth` — GitHub OAuth client ID/secret

### 2. External Secrets Operator

**Tags:** `external-secrets`, `eso`

- Installs ESO via Helm chart (OCI registry)
- Waits for controller, webhook, cert-controller pods
- Creates `ClusterSecretStore` pointing to Vault (Kubernetes auth)
- Creates `ExternalSecret` → `publishing-house-credentials` in app namespace
- Refresh interval: 1h

### 3. DevSpaces

**Tags:** `devspaces`

- Creates `openshift-devspaces` namespace
- Installs DevSpaces operator subscription (channel: stable)
- Writes GitHub OAuth secret to Vault
- Creates ExternalSecret for GitHub OAuth
- Deploys CheCluster CR
- Waits for Active phase

### 4. Keycloak

**Tags:** `keycloak`

- Creates keycloak namespace
- Installs RHBK operator subscription (channel: stable-v26)
- Deploys PostgreSQL StatefulSet for Keycloak
- Creates Keycloak instance CR
- Imports realm with clients:
  - `central-api` — for API authentication
  - `rhdh` — for Developer Hub SSO
  - `publishing-house-portal` — for portal UI

### 5. RHDH (Red Hat Developer Hub)

**Tags:** `rhdh`

- Creates namespace
- Installs RHDH operator subscription (channel: fast-1.10)
- Creates Kubernetes plugin SA + ClusterRoleBinding + long-lived token
- Creates env secret (OIDC, GitHub, Jira credentials)
- Generates service token for API access
- Creates app-config ConfigMap (catalog, proxy, auth, CORS, plugins)
- Creates RBAC policy ConfigMap
- Creates dynamic plugins ConfigMap (PH workflows, readme, scaffolder module)
- Deploys Backstage CR
- Creates custom Route
- Creates dynamic plugins PVC (5Gi)

### 6. Central API

**Tags:** `central-api`

- Creates ServiceAccount
- Creates TokenReview ClusterRoleBinding
- Creates validation policy ConfigMap (`ph-validation-policy`)
- Creates config ConfigMap (`central-api-config`, 15 keys)
- Deploys Deployment (1 replica, 500m CPU / 1Gi memory limits)
- Creates Service (port 8000)
- Creates Route (edge TLS)
- Waits for ready
- URL: `https://central-api-{namespace}.{domain}`

### 7. SonataFlow

**Tags:** `sonataflow`

- Deploys PostgreSQL StatefulSet (1 replica, 5Gi PVC)
- Creates `sonataflow` database
- Creates SonataFlowPlatform CR (manages data-index + jobs-service)
- Creates workflow input schema ConfigMap
- Creates central-api OpenAPI spec ConfigMap
- Deploys SonataFlow workflow CR (the full state machine)
- Deploys Management Console:
  - Deployment with oauth2-proxy sidecar (v7.7.1)
  - Service
  - Route (edge TLS)
- Build resources: 4 CPU / 4Gi memory

### 8. Jobs (CronJobs)

**Tags:** `jobs`

Creates 3 CronJobs with associated script ConfigMaps:

| CronJob | Schedule | Image | Purpose |
|---|---|---|---|
| `drift-checker` | `0 6 * * *` (daily 06:00 UTC) | python:3.11-slim | Queries active workflows, checks spec drift via Central API, patches `hasDrift` |
| `inactivity-checker` | `0 7 * * *` (daily 07:00 UTC) | python:3.11-slim | Finds stale workflows (7+ days no commits), posts Jira comment |
| `workflow-cleanup` | `0 5 * * *` (daily 05:00 UTC) | python:3.11-slim | Cleans up completed/errored workflows older than threshold |

## Key Deployment Variables

| Variable | Purpose | Example |
|---|---|---|
| `ocp_apps_domain` | Cluster apps domain | `apps.ocpv-infra02.wdc07.infra.demo.redhat.com` |
| `namespace` | Target namespace | `publishing-house` |
| `vault_namespace` | Vault namespace | `vault` |
| `central_api_image` | Central API image | `quay.io/rhpds/central-api` |
| `central_api_tag` | Central API tag | `1.21.9` |
| `workflow_image` | Workflow image | `quay.io/rhpds/publishing-house-workflow` |
| `workflow_tag` | Workflow tag | `1.5` |
