# Publishing House Central Repository Structure

**Last Updated**: 2026-07-10  
**Purpose**: Source of truth for Publishing House infrastructure, workflows, and automation

---

## Directory Structure

```
rhdp-publishing-house/
├── ansible/                    # Deployment automation
├── central-api/               # Publishing House Central API (FastAPI)
├── devspaces/                 # OpenShift DevSpaces configuration
├── external-secrets/          # External Secrets Operator configuration
├── infrastructure/            # Base infrastructure manifests
├── templates/                 # Red Hat Developer Hub (Backstage) templates
└── workflows/                 # SonataFlow workflow definitions
```

---

## Key Files by Category

### 🚀 Deployment & Automation

| File | Purpose | Status |
|------|---------|--------|
| `ansible/deploy-devspaces-config.yml` | Deploy DevSpaces automation (ClusterRole, Project Template, CheCluster patch) | ✅ Active |
| `ansible/deploy-central-api.yml` | Deploy Central API service | ✅ Active |
| `ansible/deploy-vault.yml` | Deploy Vault configuration | ✅ Active |
| `ansible/deploy-workflow.yml` | Deploy SonataFlow workflow | ✅ Active |
| `ansible/deploy.yml` | Main deployment playbook | 🔍 Check if used |

---

### 🔧 DevSpaces Configuration

| File | Purpose | Deployed? |
|------|---------|-----------|
| `devspaces/project-template.yaml` | **SOURCE** - OpenShift Project Template for auto-creating RoleBindings | ✅ Template |
| `devspaces/project-template-deployed.yaml` | **REFERENCE** - Actual deployed state from cluster | 📸 Snapshot |
| `devspaces/checluster-patch.yaml` | **SOURCE** - CheCluster configuration (static SA, ClusterRole) | ✅ Template |
| `devspaces/checluster-deployed.yaml` | **REFERENCE** - Actual deployed state from cluster | 📸 Snapshot |
| `devspaces/README.md` | Complete DevSpaces setup documentation | 📖 Docs |

**How it works**:
1. `checluster-patch.yaml` sets static ServiceAccount name (`devworkspace-sa`)
2. `project-template.yaml` automatically creates RoleBinding when user namespace is created
3. Workspace pods can create ExternalSecrets to pull credentials from Vault

---

### 🔒 External Secrets Configuration

| File | Purpose | Deployed? |
|------|---------|-----------|
| `external-secrets/devworkspace-externalsecret-clusterrole.yaml` | **SOURCE** - ClusterRole for ExternalSecret management | ✅ Template |
| `external-secrets/devworkspace-externalsecret-clusterrole-deployed.yaml` | **REFERENCE** - Actual deployed state | 📸 Snapshot |
| `external-secrets/github-credentials-externalsecret.yaml` | GitHub credentials for RHDH | ✅ Active |

---

### 🌊 Workflow Definitions

| File | Purpose | Status |
|------|---------|--------|
| `workflows/publishinghouseworkflow.yaml` | **DEPLOYED** - Main 12-phase workflow on cluster | ✅ Deployed |
| `workflows/central-api-openapi.yaml` | OpenAPI spec for Central API (used by workflow) | ✅ Active |
| `workflows/workflow-input-schema-configmap.yaml` | Input validation schema ConfigMap | ✅ Active |
| `workflows/workflow-rest-config.properties` | REST client configuration | ✅ Active |
| `workflows/clean-workflow.sh` | Script to clean/redeploy workflow | 🛠️ Tool |
| `workflows/README.md` | Workflow documentation | 📖 Docs |

**Important**: 
- `publishinghouseworkflow.yaml` is the **ACTUAL** deployed workflow (no hyphens in name)
- Includes Central API integration (`generateKey`, `storeWorkflowMetadata` functions)
- Profile: `dev` (not `preview`)
- **Contains REDACTED_API_KEY** - replace with proper secret reference before deploying

---

### 🏗️ Central API

| Directory | Purpose |
|-----------|---------|
| `central-api/app/` | FastAPI application source |
| `central-api/k8s/` | Kubernetes manifests (Deployment, Service, Route, ExternalSecrets) |
| `central-api/Dockerfile` | Container image definition |
| `central-api/build.sh` | Build script |

**Endpoints**:
- `POST /api/v1/projects/{project_id}/litellm/generate` - Generate LiteLLM virtual key
- `POST /api/v1/workflow/metadata` - Store workflow metadata in Vault
- `GET /api/v1/health` - Health check

---

### 📝 RHDH Templates

| File | Purpose |
|------|---------|
| `templates/publishing-house-project/template.yaml` | Main scaffolder template for creating PH projects |
| `templates/publishing-house-project/skeleton/.devfile.yaml` | DevSpaces workspace definition |
| `templates/publishing-house-project/skeleton/.devspaces/externalsecret-claude-config.yaml` | ExternalSecret template for workspace credentials |
| `templates/publishing-house-location.yaml` | Catalog location registration | 

**Template Flow**:
1. User fills out form in RHDH
2. Template creates GitHub repo (or uses existing)
3. Template triggers workflow via `/proxy/sonataflow/publishinghouseworkflow`
4. Template registers catalog-info.yaml
5. User clicks factory URL → DevSpaces workspace opens
6. PostStart creates ExternalSecret → credentials from Vault
7. Claude CLI ready to use

---

## Deployment Order

### Initial Cluster Setup (One-Time)

```bash
# 1. Deploy Vault
ansible-playbook ansible/deploy-vault.yml

# 2. Deploy DevSpaces configuration
ansible-playbook ansible/deploy-devspaces-config.yml

# 3. Deploy Central API
ansible-playbook ansible/deploy-central-api.yml

# 4. Deploy Workflow
ansible-playbook ansible/deploy-workflow.yml
```

### Verify Deployment

```bash
# DevSpaces
oc get checluster devspaces -n openshift-devspaces
oc get template devspaces-project-request -n openshift-config
oc get clusterrole devworkspace-externalsecret-manager

# Central API
oc get deployment central-api -n backstage
curl https://central-api-backstage.apps.cluster.example.com/api/v1/health

# Workflow
oc get sonataflow publishinghouseworkflow -n backstage
```

---

## Source of Truth vs Reference Files

### 📦 SOURCE (Deploy These)
Files you deploy to the cluster:
- `devspaces/project-template.yaml`
- `devspaces/checluster-patch.yaml`
- `external-secrets/devworkspace-externalsecret-clusterrole.yaml`
- `workflows/publishinghouseworkflow.yaml`
- `central-api/k8s/*.yaml`

### 📸 REFERENCE (Don't Deploy)
Snapshots of deployed state (for comparison):
- `devspaces/*-deployed.yaml`
- `external-secrets/*-deployed.yaml`

**To sync**: Run cluster extraction script and compare

---

## Configuration Dependencies

```
┌─────────────────────────────────────────────────────┐
│ External Secrets Operator (prerequisite)            │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│ Vault (with paths configured)                       │
│ - secrets/ph/central/projects/*/maas               │
│ - secrets/ph/central/projects/*/workflow           │
│ - secrets/ph/central/secrets/api-key               │
└────────────────────┬────────────────────────────────┘
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
┌──────────────────┐   ┌────────────────────┐
│ DevSpaces        │   │ Central API        │
│ Configuration    │   │ (uses Vault)       │
└────────┬─────────┘   └────────┬───────────┘
         │                      │
         │                      ▼
         │              ┌────────────────────┐
         │              │ SonataFlow         │
         │              │ (calls Central API)│
         │              └────────┬───────────┘
         │                       │
         └───────────┬───────────┘
                     ▼
          ┌─────────────────────┐
          │ RHDH Template        │
          │ (orchestrates all)   │
          └─────────────────────┘
```

---

## Common Operations

### Update Workflow

```bash
# Edit workflow
vi workflows/publishinghouseworkflow.yaml

# Redeploy
oc apply -f workflows/publishinghouseworkflow.yaml

# Or use clean script
./workflows/clean-workflow.sh
```

### Update DevSpaces Config

```bash
# Edit patches
vi devspaces/checluster-patch.yaml
vi devspaces/project-template.yaml

# Deploy
ansible-playbook ansible/deploy-devspaces-config.yml
```

### Sync Cluster State to Repo

```bash
# Extract deployed state
oc get sonataflow publishinghouseworkflow -n backstage -o yaml > workflows/publishinghouseworkflow.yaml
oc get checluster devspaces -n openshift-devspaces -o yaml > devspaces/checluster-deployed.yaml
oc get template devspaces-project-request -n openshift-config -o yaml > devspaces/project-template-deployed.yaml

# Clean up (remove runtime fields)
# ... manual editing or script ...

# Commit
git add -A && git commit -m "Sync with cluster state" && git push
```

---

## Security Notes

### 🔴 Never Commit

- API keys / tokens in plaintext
- Vault root tokens
- Database passwords
- SSH keys

### ✅ Use Instead

- ExternalSecrets pointing to Vault paths
- Secret references: `$SECRET.secret-name.key`
- ConfigMaps for non-sensitive config

### 🛡️ Vault Paths

All secrets stored in Vault:
- LiteLLM API keys: `secrets/ph/central/projects/{project_name}/maas`
- Workflow IDs: `secrets/ph/central/projects/{project_name}/workflow`
- Central API token: `secrets/ph/central/secrets/api-key`

---

## Related Repositories

| Repo | Purpose |
|------|---------|
| `rhdp-publishing-house-nate` | Original Python-based implementation (legacy) |
| `rhdp-publishing-house` | **THIS REPO** - Infrastructure & automation |
| `ocp-getting-started-test` | Test project created by template |

---

## Next Steps After Cloning

1. **Review deployed state**:
   ```bash
   diff devspaces/project-template.yaml devspaces/project-template-deployed.yaml
   ```

2. **Check if Central API is accessible**:
   ```bash
   curl https://central-api-backstage.apps.cluster.example.com/api/v1/health
   ```

3. **Test workflow trigger**:
   - Go to RHDH → Create Component
   - Select "Publishing House Content Project"
   - Fill out form and create

4. **Test workspace creation**:
   - Click factory URL from template output
   - Verify workspace opens
   - Open terminal and check: `echo $ANTHROPIC_API_KEY`

---

## Troubleshooting

See detailed troubleshooting in:
- `devspaces/README.md` - DevSpaces issues
- `docs/specs/devspaces-integration-handover.md` - Complete handover doc
- `workflows/README.md` - Workflow issues
- `central-api/README.md` - API issues

---

**Document Status**: Complete as of 2026-07-10  
**Maintainer**: RHDP Team  
**Questions**: Check handover doc or RHDH Publishing House project
