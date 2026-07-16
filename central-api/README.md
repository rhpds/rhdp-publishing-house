# Publishing House Central API

Integration layer for Publishing House workflow orchestration with RHDH and SonataFlow.

## Architecture

**Central API** serves as the bridge between:
- **GitHub**: Project repositories with `catalog-info.yaml`
- **SonataFlow**: Workflow instances and gate approvals
- **LiteLLM**: AI key management for content creators
- **Vault**: Secure secret storage

## Key Features

### Project Registration
- Creates SonataFlow workflow instances
- Supports both Path A (Claude Code) and Path B (RHDH Template)
- Stores project metadata

### Workflow Advancement
- Sends CloudEvents to SonataFlow for gate transitions
- Generates LiteLLM virtual keys (on first advance)
- Updates `catalog-info.yaml` with workflow metadata and stage annotations

### All Logic in Central API
- LiteLLM key generation happens in `/advance` endpoint
- Catalog-info.yaml updates happen in `/advance` endpoint
- No logic in SonataFlow workflow - it's just a state machine

## API Endpoints

### Health
```bash
GET /api/v1/health
```

### Register Project (Auth Required)
```bash
POST /api/v1/projects
Authorization: Bearer <PH_API_KEY>
Content-Type: application/json

{
  "repo_url": "https://github.com/owner/repo",
  "branch": "main",
  "workflow_instance_id": "optional-uuid-from-path-b"
}
```

### Advance Workflow (Auth Required)
```bash
POST /api/v1/projects/{project_id}/advance
Authorization: Bearer <PH_API_KEY>
Content-Type: application/json

{
  "event_type": "ph.intake.complete"
}
```

This endpoint:
1. Generates LiteLLM key (if not already created)
2. Sends CloudEvent to SonataFlow
3. Updates catalog-info.yaml with:
   - `ph.rhdp.io/stage`: New workflow stage
   - `ph.rhdp.io/workflow-instance`: SonataFlow instance ID
   - `ph.rhdp.io/project-id`: Project ID
   - `ph.rhdp.io/litellm-key`: Truncated key (for reference)

### List Projects (No Auth)
```bash
GET /api/v1/projects
```

### Get Project (No Auth)
```bash
GET /api/v1/projects/{project_id}
```

### Policy Reference (No Auth)
```bash
GET /api/v1/reference/ocp-policy
GET /api/v1/reference/vocabulary
```

## Event → Stage Mapping

| CloudEvent Type | Next Stage |
|----------------|------------|
| `ph.intake.complete` | review |
| `ph.approval.granted` | development |
| `ph.writing.complete` | ready |
| `ph.final_review.complete` | published |

## Environment Variables

All secrets are sourced from Vault via ExternalSecrets:

- `PH_API_KEY`: API authentication token (from Vault)
- `GITHUB_TOKEN`: GitHub token for repo access (from Vault)
- `LITELLM_MASTER_KEY`: LiteLLM master key (from Vault)
- `SONATAFLOW_URL`: SonataFlow service URL (default: internal service)
- `LITELLM_API_URL`: LiteLLM proxy URL (default: internal service)

## Deployment

### Prerequisites
1. Create PH_API_KEY secret in Vault:
```bash
oc exec vault-0 -n vault -- vault kv put kv/secrets/ph/central/secrets/api-key token="<generate-secure-token>"
```

2. Create LiteLLM master key in Vault:
```bash
oc exec vault-0 -n vault -- vault kv put kv/secrets/ph/central/secrets/litellm-master-key master-key="<litellm-master-key>"
```

### Build and Deploy
```bash
# Build image
podman build -t quay.io/rhpds/central-api:latest central-api/

# Push image
podman push quay.io/rhpds/central-api:latest

# Deploy to cluster
oc apply -f central-api/k8s/
```

### Verify Deployment
```bash
# Check pods
oc get pods -n backstage | grep central-api

# Check route
oc get route central-api -n backstage

# Test health endpoint
curl https://$(oc get route central-api -n backstage -o jsonpath='{.spec.host}')/api/v1/health
```

## Development

### Local Development
```bash
cd central-api

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export PH_API_KEY=test-key
export GITHUB_TOKEN=<your-token>
export LITELLM_MASTER_KEY=<master-key>
export SONATAFLOW_URL=http://localhost:8080
export IN_CLUSTER=false

# Run server
uvicorn app.main:app --reload --port 8000
```

### Testing
```bash
# Register a project
curl -X POST http://localhost:8000/api/v1/projects \
  -H "Authorization: Bearer test-key" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/test/repo",
    "branch": "main"
  }'

# Advance workflow
curl -X POST http://localhost:8000/api/v1/projects/<project-id>/advance \
  -H "Authorization: Bearer test-key" \
  -H "Content-Type: application/json" \
  -d '{"event_type": "ph.intake.complete"}'
```

## Integration with RHDH Template

The RHDH Template should call Central API after scaffolding:

```yaml
steps:
  # ... scaffolding steps ...

  - id: register-with-central
    name: Register with Central API
    action: http:backstage:request
    input:
      method: POST
      url: https://central-api-backstage.apps.cluster.example.com/api/v1/projects
      headers:
        Authorization: Bearer ${{ secrets.PH_CENTRAL_KEY }}
        Content-Type: application/json
      body:
        repo_url: ${{ parameters.repoUrl }}
        branch: main
        workflow_instance_id: ${{ steps['trigger-workflow'].output.workflowId }}
```

## Architecture Notes

### Why All Logic in Central API?

The SonataFlow workflow is just a state machine waiting for CloudEvents. All business logic happens in Central API:

1. **LiteLLM key generation**: Happens in `/advance` endpoint (not in workflow)
2. **Catalog updates**: Happen in `/advance` endpoint (not in workflow)
3. **CloudEvent sending**: Central API sends events to advance workflow
4. **Stage transitions**: Mapped in Central API based on event types

This design:
- ✅ Keeps workflow simple and declarative
- ✅ Centralizes business logic in one place
- ✅ Makes testing easier (API vs workflow)
- ✅ Allows logic changes without redeploying workflow
