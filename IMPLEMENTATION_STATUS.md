# RHDH Publishing House - Implementation Status

**Last Updated**: 2026-07-08  
**Session**: Initial SonataFlow Workflow Implementation

## Overview

This document tracks the implementation progress of migrating Publishing House to RHDH + SonataFlow orchestration.

## Implementation Plan

### ✅ Phase 1: SonataFlow Workflow Orchestration (IN PROGRESS)

**Status**: Foundation complete, ready for testing

**What's Implemented**:

1. **Main Workflow** (`workflows/main-publishing-workflow.sw.yaml`)
   - 12-phase lifecycle orchestration
   - Event-driven state management
   - CloudEvents integration for skill communication
   - GraphQL integration for state queries
   - Parallel execution for Writing+Automation and Code+Security reviews
   - Proper error handling and timeouts
   - Validation gates between phases

2. **Sub-Workflows**:
   - ✅ `write-content-workflow.sw.yaml` - Writing phase orchestration
   - ⏳ `automation-workflow.sw.yaml` - TODO
   - ⏳ `code-review-workflow.sw.yaml` - TODO
   - ⏳ `security-review-workflow.sw.yaml` - TODO
   - ⏳ `e2e-testing-workflow.sw.yaml` - TODO

3. **Ansible Deployment Automation**:
   - ✅ `ansible/roles/operators/` - Operator installation (SonataFlow, RHDH, PostgreSQL)
   - ✅ `ansible/roles/infrastructure/` - PostgreSQL, Data Index, SonataFlow Platform
   - ✅ `ansible/roles/workflows/` - Workflow deployment
   - ⏳ `ansible/roles/services/` - Integration services - TODO
   - ⏳ `ansible/roles/skills/` - MCP skills server - TODO
   - ⏳ `ansible/roles/rhdh-plugin/` - RHDH dashboard plugin - TODO
   - ⏳ `ansible/roles/monitoring/` - Prometheus/Grafana - TODO

**Next Steps for Phase 1**:

1. Create remaining sub-workflows:
   ```bash
   workflows/sub-workflows/
   ├── automation-workflow.sw.yaml
   ├── code-review-workflow.sw.yaml
   ├── security-review-workflow.sw.yaml
   └── e2e-testing-workflow.sw.yaml
   ```

2. Create JSON schemas for workflow validation:
   ```bash
   workflows/schemas/
   ├── project-state-schema.json
   ├── intake-data-schema.json
   ├── spec-schema.json
   └── phase-data-schema.json
   ```

3. Test deployment:
   ```bash
   cd ansible
   ansible-playbook deploy.yml -e env=dev --tags operators
   ansible-playbook deploy.yml -e env=dev --tags infrastructure
   ansible-playbook deploy.yml -e env=dev --tags workflows
   ```

### ⏳ Phase 2: RHDH Software Catalog Integration (PENDING)

**Status**: Not started

**What Needs to be Built**:

1. **RHDH Software Templates**:
   - `templates/publishing-house-project/template.yaml`
   - Creates new project repository
   - Triggers workflow instance creation
   - Provisions DevSpaces workspace

2. **RHDH Dashboard Plugin**:
   - `plugins/publishing-dashboard/` (frontend)
   - `plugins/publishing-dashboard-backend/` (backend)
   - Real-time workflow state display via GraphQL
   - Approval workflow UI (Phase 4, Phase 11)
   - Phase progression timeline
   - Project list view

3. **Integration**:
   - catalog-info.yaml generation
   - Entity registration
   - Dashboard routing
   - GraphQL client for Data Index

**Dependencies**:
- Phase 1 complete (workflows deployed and tested)
- Data Index GraphQL API accessible

### ⏳ Phase 3: DevSpaces Workspace Provisioning (PENDING)

**Status**: Not started

**What Needs to be Built**:

1. **PublishingHouseClient Library**:
   - `skills/src/lib/PublishingHouseClient.ts`
   - GraphQL queries for state reads
   - CloudEvents sending for state updates
   - ServiceAccount token authentication
   - Workflow ID discovery (from Vault or env var)

2. **Claude Code Skills**:
   - `skills/src/intake.md` - Interactive intake skill
   - `skills/src/spec-refiner.md` - Spec improvement skill
   - `skills/src/writer.md` - Content writing wrapper
   - `skills/src/editor.md` - Content review wrapper
   - `skills/src/automator.md` - Catalog generation wrapper

3. **DevWorkspace API Integration**:
   - ServiceAccount with DevWorkspace RBAC
   - Workspace provisioning endpoints
   - LiteLLM key provisioning
   - Custom UDI with Claude Code

4. **Security**:
   - RBAC manifests (`infrastructure/security/rbac/`)
   - NetworkPolicies
   - ServiceAccount token handling

**Dependencies**:
- Phase 1 complete (workflows running)
- Phase 2 in progress (RHDH templates can provision workspaces)

## Architecture Decisions

### Workflow State Management

**Decision**: PostgreSQL + GraphQL (not git-based manifest.yaml)

**Rationale**:
- Transactional updates
- No git commit overhead
- Standard workflow tooling
- Built-in monitoring via Data Index
- Real-time GraphQL queries

### Skills Communication Pattern

**Read State**: Skills → GraphQL → Data Index → PostgreSQL
```typescript
const state = await client.getState();
```

**Update State**: Skills → CloudEvents → SonataFlow
```typescript
await client.update({ spec: {...} });
await client.completePhase('intake', { spec: {...} });
```

### Authentication

**Decision**: ServiceAccount tokens + Kubernetes TokenReview

**Rationale**:
- Native Kubernetes auth
- Auto-mounted at `/var/run/secrets/kubernetes.io/serviceaccount/token`
- No credential management
- Audit trail via K8s
- RBAC-controlled access

## Deployment Guide

### Prerequisites

```bash
# OpenShift cluster (4.14+)
oc login https://api.cluster.example.com:6443

# Ansible dependencies
pip install -r requirements.txt
ansible-galaxy collection install -r ansible/requirements.yml

# Configuration
cp ansible/inventory/group_vars/all.yml.example ansible/inventory/group_vars/all.yml
cp ansible/inventory/group_vars/vault.yml.example ansible/inventory/group_vars/vault.yml
# Edit all.yml and vault.yml with your settings
```

### Phase 1 Deployment (SonataFlow Workflows)

```bash
cd ansible

# Install operators (one-time)
ansible-playbook deploy.yml -e env=dev --tags operators

# Deploy infrastructure
ansible-playbook deploy.yml -e env=dev --tags infrastructure

# Deploy workflows
ansible-playbook deploy.yml -e env=dev --tags workflows

# Verify
oc get sonataflows -n backstage
oc get pods -n backstage
```

### Access Data Index GraphQL

```bash
# Get Route URL
oc get route data-index-graphql -n backstage

# Or port-forward
oc port-forward svc/sonataflow-platform-data-index-service 8080:80 -n backstage

# Visit http://localhost:8080/graphql
```

## File Structure

```
rhdp-publishing-house/
├── workflows/                             ✅ Created
│   ├── main-publishing-workflow.sw.yaml  ✅ Complete
│   ├── sub-workflows/
│   │   ├── write-content-workflow.sw.yaml ✅ Complete
│   │   ├── automation-workflow.sw.yaml    ⏳ TODO
│   │   ├── code-review-workflow.sw.yaml   ⏳ TODO
│   │   ├── security-review-workflow.sw.yaml ⏳ TODO
│   │   └── e2e-testing-workflow.sw.yaml   ⏳ TODO
│   └── schemas/                           ⏳ TODO
│       └── project-state-schema.json
├── ansible/                               ✅ Created
│   ├── deploy.yml                         ✅ Exists
│   ├── roles/
│   │   ├── operators/                     ✅ Complete
│   │   ├── infrastructure/                ✅ Complete
│   │   ├── workflows/                     ✅ Complete
│   │   ├── services/                      ⏳ TODO
│   │   ├── skills/                        ⏳ TODO
│   │   ├── rhdh-plugin/                   ⏳ TODO
│   │   └── monitoring/                    ⏳ TODO
│   └── inventory/
│       └── group_vars/
│           ├── all.yml.example            ✅ Exists
│           └── vault.yml.example          ✅ Exists
├── skills/                                ⏳ TODO
│   └── src/
│       ├── lib/PublishingHouseClient.ts
│       ├── intake.md
│       ├── spec-refiner.md
│       ├── writer.md
│       ├── editor.md
│       └── automator.md
├── plugins/                               ⏳ TODO
│   ├── publishing-dashboard/
│   └── publishing-dashboard-backend/
├── services/                              ⏳ TODO
│   ├── jira-sync/
│   ├── rcars-client/
│   └── github-ops/
├── infrastructure/                        ⏳ TODO
│   ├── security/
│   │   ├── rbac/
│   │   └── networkpolicies/
│   └── monitoring/
└── templates/                             ⏳ TODO
    └── publishing-house-project/
```

## Key Concepts

### 12-Phase Lifecycle

1. **intake** - Interactive spec definition (human via skill)
2. **vetting** - RCARS overlap check (automated)
3. **spec_refinement** - Spec quality improvement (human via skill)
4. **approval** - Manager approval (human via dashboard)
5. **writing** - Content generation (parallel, human via skill)
6. **automation** - Catalog generation (parallel, human via skill)
7. **editing** - Content review (human via skill)
8. **code_review** - Automated linting (parallel, automated)
9. **security_review** - Security scanning (parallel, automated)
10. **e2e_testing** - End-to-end tests (automated)
11. **final_review** - Quality gate (human via dashboard)
12. **ready_for_publishing** - Deployment ready (automated)

### Event Types

**Consumed by Workflow**:
- `ph.project.created` - Project registration
- `ph.intake.update` - Incremental intake updates
- `ph.intake.complete` - Intake phase completion
- `ph.spec_refinement.update`
- `ph.spec_refinement.complete`
- `ph.approval.granted`
- `ph.approval.rejected`
- `ph.editing.update`
- `ph.editing.complete`
- `ph.final_review.approved`
- `ph.final_review.rejected`

**Produced by Workflow**:
- `ph.writing.phase_complete`
- `ph.automation.phase_complete`
- Etc.

## Testing Strategy

### Unit Tests
- Workflow validation (YAML syntax, Serverless Workflow spec compliance)
- Schema validation
- Function contract tests

### Integration Tests
- Deploy to test cluster
- Trigger workflow via CloudEvent
- Query state via GraphQL
- Verify phase transitions

### End-to-End Tests
- Full project lifecycle
- Skills integration (mocked human input)
- Service integrations (Jira, RCARS, GitHub)

## Troubleshooting

### Check Workflow Status

```bash
oc get sonataflows -n backstage
oc describe sonataflow main-publishing-workflow -n backstage
```

### Query Workflow State (GraphQL)

```graphql
query {
  ProcessInstances {
    id
    processId
    state
    variables
    nodes {
      name
      definitionId
      enter
      exit
    }
  }
}
```

### Check Data Index Logs

```bash
oc logs -n backstage deployment/sonataflow-platform-data-index-service
```

### Send Test CloudEvent

```bash
curl -X POST http://sonataflow-platform-data-index-service.backstage.svc/cloudevents \
  -H "Content-Type: application/cloudevents+json" \
  -d '{
    "specversion": "1.0",
    "type": "ph.intake.complete",
    "source": "test",
    "id": "test-1",
    "data": {
      "spec": {...}
    }
  }'
```

## Next Session Tasks

1. **Complete remaining sub-workflows** (automation, reviews, testing)
2. **Create JSON schemas** for workflow validation
3. **Test Phase 1 deployment** on real cluster
4. **Begin Phase 2** (RHDH templates and dashboard plugin)

## References

- [SonataFlow Documentation](https://sonataflow.org/serverlessworkflow/latest/index.html)
- [CNCF Serverless Workflow Spec](https://serverlessworkflow.io/)
- [RHDH Documentation](https://developers.redhat.com/rhdh)
- [Original Publishing House](https://github.com/rhpds/rhdp-publishing-house)
