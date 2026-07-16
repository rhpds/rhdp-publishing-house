# RHDH Publishing House Central

**Central repository for RHDH Publishing House deployment automation and source code**

This repository contains all source code, workflows, services, skills, and Ansible playbooks for deploying the RHDH Publishing House system to OpenShift clusters.

## Overview

The RHDH Publishing House is deployed as a complete system using Ansible automation. When you get a new cluster, you run the deployment playbooks from this repository to install and configure all components.

## Repository Structure

```
rhdh-publishing-house-central/
├── ansible/                           # Ansible deployment automation
│   ├── deploy.yml                     # Main deployment playbook
│   ├── undeploy.yml                   # Cleanup playbook
│   ├── roles/
│   │   ├── operators/                 # Install operators (SonataFlow, RHDH, PostgreSQL)
│   │   ├── infrastructure/            # Deploy infrastructure (PostgreSQL, Data Index, SonataFlow platform)
│   │   ├── workflows/                 # Deploy SonataFlow workflows
│   │   ├── services/                  # Deploy integration services
│   │   ├── skills/                    # Deploy MCP skills server
│   │   ├── rhdh-plugin/               # Deploy RHDH dashboard plugin
│   │   └── monitoring/                # Deploy Prometheus/Grafana
│   ├── inventory/
│   │   ├── group_vars/
│   │   └── host_vars/
│   └── files/                         # Static files (manifests, configs)
├── workflows/                         # SonataFlow workflow definitions
│   ├── main-publishing-workflow.sw.yaml
│   └── sub-workflows/
│       ├── parallel-work-workflow.sw.yaml
│       ├── write-module-workflow.sw.yaml
│       ├── automation-workflow.sw.yaml
│       ├── code-review-workflow.sw.yaml
│       ├── security-review-workflow.sw.yaml
│       └── e2e-testing-workflow.sw.yaml
├── services/                          # Integration microservices
│   ├── jira-sync/
│   │   ├── src/
│   │   ├── Dockerfile
│   │   └── package.json
│   ├── rcars-client/
│   │   ├── src/
│   │   ├── Dockerfile
│   │   └── package.json
│   └── github-ops/
│       ├── src/
│       ├── Dockerfile
│       └── package.json
├── skills/                            # Claude Code MCP skills
│   ├── src/
│   │   ├── intake/
│   │   ├── spec-refiner/
│   │   ├── writer/
│   │   ├── editor/
│   │   ├── automator/
│   │   └── lib/
│   ├── mcp-server.ts
│   ├── Dockerfile
│   └── package.json
├── plugins/                           # RHDH plugins
│   ├── publishing-dashboard/
│   │   ├── src/
│   │   ├── package.json
│   │   └── README.md
│   └── publishing-dashboard-backend/
│       ├── src/
│       └── package.json
├── infrastructure/                    # Kubernetes/OpenShift manifests
│   ├── operators/
│   │   ├── sonataflow-operator.yaml
│   │   ├── rhdh-operator.yaml
│   │   └── postgresql-operator.yaml
│   ├── manifests/
│   │   ├── namespace.yaml
│   │   ├── sonataflow-platform.yaml
│   │   ├── data-index.yaml
│   │   ├── postgresql.yaml
│   │   └── rhdh-instance.yaml
│   ├── monitoring/
│   │   ├── prometheus/
│   │   └── grafana/
│   └── security/
│       ├── networkpolicies/
│       └── rbac/
├── docs/                              # Documentation
│   ├── deployment.md                  # Deployment guide
│   ├── development.md                 # Development guide
│   └── troubleshooting.md             # Troubleshooting guide
├── tests/                             # Integration tests
│   ├── integration/
│   └── e2e/
└── requirements.txt                   # Python dependencies (for Ansible)
```

## Quick Start

### Prerequisites

- OpenShift cluster (4.14+)
- `oc` CLI logged into the cluster
- Ansible 2.15+
- Python 3.11+

### Deploy Full System

```bash
# 1. Clone this repository
git clone https://github.com/rhpds/rhdh-publishing-house-central.git
cd rhdh-publishing-house-central

# 2. Install Ansible dependencies
pip install -r requirements.txt
ansible-galaxy collection install -r ansible/requirements.yml

# 3. Configure deployment
cp ansible/inventory/group_vars/all.yml.example ansible/inventory/group_vars/all.yml
# Edit ansible/inventory/group_vars/all.yml with your settings

# 4. Run deployment
cd ansible
ansible-playbook -i inventory deploy.yml
```

### Deployment Phases

The `deploy.yml` playbook runs these phases in order:

1. **Operators** - Install SonataFlow, RHDH, PostgreSQL operators
2. **Infrastructure** - Deploy PostgreSQL, SonataFlow platform, Data Index
3. **Workflows** - Deploy all SonataFlow workflow definitions
4. **Services** - Deploy integration services (Jira sync, RCARS, GitHub ops)
5. **Skills** - Deploy MCP skills server (optional, for DevSpaces)
6. **RHDH Plugin** - Deploy Publishing House dashboard plugin
7. **Monitoring** - Deploy Prometheus/Grafana stack

### Undeploy

```bash
cd ansible
ansible-playbook -i inventory undeploy.yml
```

## Development Workflow

### Local Development

Each component can be developed and tested locally:

**Workflows**:
```bash
cd workflows
# Edit workflow YAML
# Validate with SonataFlow CLI
swf-parser validate main-publishing-workflow.sw.yaml
```

**Services**:
```bash
cd services/jira-sync
npm install
npm run dev
# Test locally
curl -X POST http://localhost:3000/api/jira/create-epic -d '{"spec": {...}}'
```

**Skills**:
```bash
cd skills
npm install
npm run dev
# Test with Claude Code in DevSpaces
```

**RHDH Plugin**:
```bash
cd plugins/publishing-dashboard
yarn install
yarn dev
```

### Deploy Changes

After making changes:

```bash
# Build and deploy specific component
cd ansible
ansible-playbook -i inventory deploy.yml --tags workflows  # Deploy only workflows
ansible-playbook -i inventory deploy.yml --tags services   # Deploy only services
ansible-playbook -i inventory deploy.yml --tags skills     # Deploy only skills
ansible-playbook -i inventory deploy.yml --tags plugin     # Deploy only RHDH plugin
```

## Configuration

### Ansible Variables

Key variables in `ansible/inventory/group_vars/all.yml`:

```yaml
# OpenShift/Kubernetes
openshift_cluster_url: https://api.cluster.example.com:6443
namespace: backstage

# PostgreSQL
postgres_storage_size: 50Gi
postgres_replicas: 2

# External Integrations
jira_url: https://issues.redhat.com
jira_token: "{{ vault_jira_token }}"  # Stored in Ansible Vault

rcars_url: https://rcars.internal.example.com
rcars_api_key: "{{ vault_rcars_api_key }}"

litellm_url: https://litellm.example.com
litellm_api_keys:
  - "{{ vault_openai_key }}"
  - "{{ vault_anthropic_key }}"

github_app_id: 12345
github_app_private_key: "{{ vault_github_private_key }}"

# RHDH
rhdh_image: quay.io/rhdh/rhdh-hub-rhel9:1.2-latest

# SonataFlow
sonataflow_platform_image: quay.io/kiegroup/kogito-swf-platform:latest
```

### Secrets Management

Secrets are managed using Ansible Vault:

```bash
# Encrypt secrets file
ansible-vault encrypt ansible/inventory/group_vars/vault.yml

# Edit secrets
ansible-vault edit ansible/inventory/group_vars/vault.yml

# Deploy with vault password
ansible-playbook -i inventory deploy.yml --ask-vault-pass
```

## Component Details

### Workflows (SonataFlow)

Located in `workflows/`, these define the orchestration logic:

- **main-publishing-workflow.sw.yaml**: 12-phase lifecycle orchestration
- **Sub-workflows**: Parallel execution for writing, automation, reviews, testing

### Services (Node.js/TypeScript)

Located in `services/`, these provide integrations:

- **jira-sync**: Jira epic/task creation and status sync
- **rcars-client**: Content overlap detection via RCARS API
- **github-ops**: Repository creation, file commits, PR management

### Skills (MCP Server)

Located in `skills/`, these provide interactive capabilities:

- **intake**: Project onboarding conversation
- **spec-refiner**: Spec quality improvement
- **writer**: Content generation wrapper
- **editor**: Content review wrapper
- **automator**: Catalog generation wrapper

### RHDH Plugin

Located in `plugins/publishing-dashboard/`, provides:

- Project list view
- Project detail view with real-time updates
- Approval workflow interface
- Phase progression timeline

## Testing

### Integration Tests

```bash
cd tests/integration
pytest test_workflow_execution.py
pytest test_skills_integration.py
pytest test_services.py
```

### End-to-End Tests

```bash
cd tests/e2e
# Deploy to test cluster
ansible-playbook -i ../ansible/inventory deploy.yml -e namespace=test

# Run E2E test
./test_full_lifecycle.sh
```

## Monitoring

Access monitoring dashboards:

```bash
# Port-forward Grafana
oc port-forward svc/grafana 3000:3000 -n backstage

# Visit http://localhost:3000
# Dashboards:
# - Publishing House Overview
# - Workflow Performance
# - Skills Usage
# - Integration Health
```

## Troubleshooting

See [docs/troubleshooting.md](docs/troubleshooting.md) for common issues and solutions.

### Quick Diagnostics

```bash
# Check all pods
oc get pods -n backstage

# Check workflow status
oc get sonataflows -n backstage

# Check Data Index
oc logs -n backstage deployment/sonataflow-platform-data-index-service

# Check PostgreSQL
oc get postgrescluster -n backstage
```

## Related Repositories

- [rhdh-publishing-house](https://github.com/rhpds/rhdh-publishing-house) - Architecture documentation and specifications
- [rhdp-publishing-house](https://github.com/rhpds/rhdp-publishing-house) - Original Python-based implementation (legacy)

## Contributing

1. Create feature branch: `git checkout -b feature-name`
2. Make changes and test locally
3. Deploy to test cluster: `ansible-playbook -i inventory deploy.yml -e namespace=test`
4. Run tests: `pytest tests/`
5. Create pull request

## License

Apache 2.0

## Support

- **Issues**: https://github.com/rhpds/rhdh-publishing-house-central/issues
- **Slack**: #rhdp-publishing-house
- **Email**: rhdp-team@redhat.com
