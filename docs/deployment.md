# RHDH Publishing House Deployment Guide

## Overview

This guide explains how to deploy RHDH Publishing House to an OpenShift cluster using Ansible automation.

## Development Workflow

**IMPORTANT**: The development workflow follows this pattern:

1. **Make changes directly on the cluster** - Test and iterate quickly
2. **Update the automation** - Once changes work, update Ansible roles to mimic what you did
3. **Update the specs** - Document the changes in the specification docs

### Example Workflow

```bash
# 1. Make changes directly on cluster
oc edit deployment/jira-sync -n backstage
# Update image, environment variables, etc.
# Test the changes

# 2. Once working, update Ansible automation
cd ansible/roles/services/tasks
# Edit jira-sync.yml to match what you just did on cluster

# 3. Update specification docs
cd ../../..  # Back to repo root
# Edit docs matching the changes

# 4. Commit everything together
git add -A
git commit -m "Update jira-sync service with new feature

- Changed image to include new API endpoint
- Added environment variable for timeout config
- Updated Ansible role to deploy these changes
- Updated spec documentation"
```

## Prerequisites

### Tools Required

- **OpenShift CLI (`oc`)**: Version 4.14+
  ```bash
  oc version
  ```

- **Ansible**: Version 2.15+
  ```bash
  ansible --version
  ```

- **Python**: Version 3.11+
  ```bash
  python --version
  ```

- **Ansible Collections**:
  ```bash
  ansible-galaxy collection install kubernetes.core
  ansible-galaxy collection install community.general
  ```

### Cluster Requirements

- **OpenShift**: Version 4.14+
- **Storage**: Dynamic provisioning enabled
- **Resources**:
  - CPU: 16 cores minimum
  - Memory: 32 GB minimum
  - Storage: 200 GB minimum
- **Operators**: Cluster admin access to install operators

### Access Requirements

- OpenShift cluster admin credentials
- GitHub App credentials (for repository operations)
- Jira API token
- RCARS API key
- LiteLLM API keys (OpenAI, Anthropic, etc.)

## Initial Setup

### 1. Clone Repository

```bash
git clone https://github.com/rhpds/rhdh-publishing-house-central.git
cd rhdh-publishing-house-central
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Install Ansible Collections

```bash
ansible-galaxy collection install -r ansible/requirements.yml
```

### 4. Configure Deployment

```bash
cd ansible/inventory/group_vars

# Copy example configs
cp all.yml.example all.yml
cp vault.yml.example vault.yml

# Edit configuration
vi all.yml
# Update: namespace, cluster URL, service URLs, etc.

# Edit secrets
vi vault.yml
# Add: API tokens, passwords, private keys

# Encrypt secrets
ansible-vault encrypt vault.yml
# Enter vault password when prompted
```

### 5. Login to OpenShift

```bash
oc login https://api.cluster.example.com:6443
# Enter credentials
```

## Full Deployment

Deploy entire RHDH Publishing House system:

```bash
cd ansible
ansible-playbook -i inventory deploy.yml --ask-vault-pass
```

This will:
1. Install operators (SonataFlow, RHDH, PostgreSQL)
2. Deploy infrastructure (PostgreSQL, SonataFlow platform, Data Index)
3. Deploy workflows (main workflow + sub-workflows)
4. Deploy integration services (Jira sync, RCARS, GitHub ops)
5. Deploy RHDH plugin
6. Deploy monitoring (Prometheus, Grafana)

### Estimated Time

- **Fresh cluster**: 30-45 minutes
- **Updating existing**: 5-10 minutes

## Partial Deployment

Deploy only specific components using tags:

### Deploy Only Operators

```bash
ansible-playbook -i inventory deploy.yml --tags operators --ask-vault-pass
```

### Deploy Only Infrastructure

```bash
ansible-playbook -i inventory deploy.yml --tags infrastructure --ask-vault-pass
```

### Deploy Only Workflows

```bash
ansible-playbook -i inventory deploy.yml --tags workflows --ask-vault-pass
```

### Deploy Only Services

```bash
ansible-playbook -i inventory deploy.yml --tags services --ask-vault-pass
```

### Deploy Only RHDH Plugin

```bash
ansible-playbook -i inventory deploy.yml --tags plugin --ask-vault-pass
```

### Deploy Only Monitoring

```bash
ansible-playbook -i inventory deploy.yml --tags monitoring --ask-vault-pass
```

## Iterative Development

### Workflow: Make Changes → Test → Update Automation

#### Example: Update Jira Sync Service

**Step 1: Make changes directly on cluster**

```bash
# Edit deployment
oc edit deployment jira-sync -n backstage

# Update image
# spec:
#   template:
#     spec:
#       containers:
#       - name: jira-sync
#         image: quay.io/rhpds/jira-sync:v1.2.0  # Changed from v1.1.0

# Add environment variable
#         env:
#         - name: JIRA_TIMEOUT
#           value: "30000"

# Save and exit

# Watch rollout
oc rollout status deployment/jira-sync -n backstage

# Test the changes
curl -X POST http://jira-sync.backstage.svc/api/jira/create-epic -d '{"spec": {...}}'
```

**Step 2: Update Ansible automation**

```bash
# Edit Ansible role
cd ansible/roles/services/tasks
vi jira-sync.yml
```

Update the task to match what you did:

```yaml
# Before
- name: Deploy Jira Sync service
  kubernetes.core.k8s:
    state: present
    definition:
      apiVersion: apps/v1
      kind: Deployment
      metadata:
        name: jira-sync
        namespace: "{{ namespace }}"
      spec:
        template:
          spec:
            containers:
            - name: jira-sync
              image: "{{ jira_sync_image }}"  # Was: quay.io/rhpds/jira-sync:v1.1.0
              env:
              - name: JIRA_URL
                value: "{{ jira_url }}"

# After
- name: Deploy Jira Sync service
  kubernetes.core.k8s:
    state: present
    definition:
      apiVersion: apps/v1
      kind: Deployment
      metadata:
        name: jira-sync
        namespace: "{{ namespace }}"
      spec:
        template:
          spec:
            containers:
            - name: jira-sync
              image: "{{ jira_sync_image }}"  # Update to: quay.io/rhpds/jira-sync:v1.2.0
              env:
              - name: JIRA_URL
                value: "{{ jira_url }}"
              - name: JIRA_TIMEOUT  # Added
                value: "30000"
```

Update the variable:

```bash
vi ../vars/main.yml
```

```yaml
# Update image version
jira_sync_image: quay.io/rhpds/jira-sync:v1.2.0  # Was v1.1.0
```

**Step 3: Update documentation**

```bash
# Update spec document
cd ../../../..  # Back to repo root
vi docs/specs/phase-6-integration-services.md
```

Add notes about the timeout configuration.

**Step 4: Test automation**

```bash
# Delete existing deployment
oc delete deployment jira-sync -n backstage

# Re-deploy using Ansible
cd ansible
ansible-playbook -i inventory deploy.yml --tags services --ask-vault-pass

# Verify deployment matches what you did manually
oc get deployment jira-sync -n backstage -o yaml | grep -A5 "image:"
oc get deployment jira-sync -n backstage -o yaml | grep "JIRA_TIMEOUT"
```

**Step 5: Commit changes**

```bash
git add -A
git commit -m "Add timeout configuration to Jira sync service

- Updated image to v1.2.0 with timeout support
- Added JIRA_TIMEOUT environment variable (30s default)
- Updated Ansible role to deploy these changes
- Updated documentation"

git push origin main
```

## Verification

### Check All Pods Running

```bash
oc get pods -n backstage
```

Expected output:
```
NAME                                         READY   STATUS    RESTARTS   AGE
backstage-developer-hub-xyz                  1/1     Running   0          5m
postgres-instance1-0                         1/1     Running   0          10m
sonataflow-platform-data-index-xyz           1/1     Running   0          8m
publishing-house-main-xyz                    1/1     Running   0          5m
jira-sync-xyz                                1/1     Running   0          3m
rcars-client-xyz                             1/1     Running   0          3m
github-ops-xyz                               1/1     Running   0          3m
```

### Check Workflows Deployed

```bash
oc get sonataflows -n backstage
```

Expected output:
```
NAME                      STATUS   AGE
publishing-house-main     Ready    5m
write-module-workflow     Ready    5m
automation-workflow       Ready    5m
code-review-workflow      Ready    5m
security-review-workflow  Ready    5m
e2e-testing-workflow      Ready    5m
```

### Test Data Index GraphQL

```bash
oc port-forward svc/sonataflow-platform-data-index-service 8080:80 -n backstage &

curl -X POST http://localhost:8080/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ ProcessInstances { id processId state } }"}'
```

Expected: `{"data": {"ProcessInstances": []}}`

### Access RHDH

```bash
oc port-forward svc/backstage 7007:7007 -n backstage &
```

Visit: http://localhost:7007

### Access Grafana

```bash
oc port-forward svc/grafana 3000:3000 -n backstage &
```

Visit: http://localhost:3000  
Login: admin / `<grafana_admin_password from vault.yml>`

## Updating Existing Deployment

### Update Workflows

After editing workflow YAML files:

```bash
cd ansible
ansible-playbook -i inventory deploy.yml --tags workflows --ask-vault-pass
```

### Update Services

After building new service images:

```bash
# Update image tag in all.yml
vi inventory/group_vars/all.yml
# Change: jira_sync_image: quay.io/rhpds/jira-sync:v1.2.0

# Re-deploy
ansible-playbook -i inventory deploy.yml --tags services --ask-vault-pass
```

### Update RHDH Plugin

After building new plugin:

```bash
# Update plugin image
vi inventory/group_vars/all.yml
# Change: plugin_image: quay.io/rhpds/publishing-dashboard:v1.1.0

# Re-deploy
ansible-playbook -i inventory deploy.yml --tags plugin --ask-vault-pass
```

## Rollback

### Rollback Deployment

```bash
oc rollout undo deployment/<deployment-name> -n backstage
```

### Rollback via Ansible

```bash
# Change image tag to previous version in all.yml
vi inventory/group_vars/all.yml

# Re-deploy
ansible-playbook -i inventory deploy.yml --tags <component> --ask-vault-pass
```

## Cleanup

### Remove Entire System

```bash
cd ansible
ansible-playbook -i inventory undeploy.yml --ask-vault-pass
```

### Remove Specific Components

```bash
# Remove workflows
ansible-playbook -i inventory undeploy.yml --tags workflows

# Remove services
ansible-playbook -i inventory undeploy.yml --tags services

# Remove RHDH plugin
ansible-playbook -i inventory undeploy.yml --tags plugin
```

## Troubleshooting

### Deployment Hangs

```bash
# Check operator status
oc get operators | grep -E 'sonataflow|rhdh|postgresql'

# Check events
oc get events -n backstage --sort-by='.lastTimestamp'

# Check specific pod logs
oc logs -n backstage <pod-name>
```

### Workflow Not Deploying

```bash
# Check SonataFlow platform status
oc get sonataflowplatform -n backstage

# Check workflow validation
oc describe sonataflow <workflow-name> -n backstage

# Check operator logs
oc logs -n openshift-operators deployment/sonataflow-operator
```

### Service Not Starting

```bash
# Check pod status
oc get pod <pod-name> -n backstage

# Check pod logs
oc logs <pod-name> -n backstage

# Check pod events
oc describe pod <pod-name> -n backstage

# Check secrets
oc get secrets -n backstage
```

### Database Connection Issues

```bash
# Check PostgreSQL cluster
oc get postgrescluster -n backstage

# Check PostgreSQL pods
oc get pods -n backstage -l postgres-operator.crunchydata.com/cluster=postgres

# Check connection from Data Index
oc exec -it deployment/sonataflow-platform-data-index-service -n backstage -- \
  curl -v telnet://postgres-primary.backstage.svc:5432
```

## Best Practices

### 1. Always Test Changes on Cluster First

```bash
# ✅ Good: Test directly
oc edit deployment/jira-sync -n backstage
# Test, verify it works

# ❌ Bad: Change Ansible first without testing
# You don't know if it will work
```

### 2. Update Automation Immediately

```bash
# ✅ Good: Update Ansible role while changes are fresh
vi ansible/roles/services/tasks/jira-sync.yml

# ❌ Bad: Wait days/weeks to update automation
# You'll forget what you changed
```

### 3. Commit Changes Together

```bash
# ✅ Good: Commit spec + code + automation together
git add docs/specs/ services/jira-sync/ ansible/roles/services/
git commit -m "Add timeout to Jira sync"

# ❌ Bad: Separate commits for spec, code, automation
# Hard to track what changed together
```

### 4. Use Descriptive Commit Messages

```bash
# ✅ Good commit message
git commit -m "Add timeout configuration to Jira sync service

- Updated image to v1.2.0 with timeout support
- Added JIRA_TIMEOUT environment variable (30s default)
- Updated Ansible role to deploy these changes
- Updated phase-6 spec documentation"

# ❌ Bad commit message
git commit -m "update jira"
```

### 5. Version Everything

```bash
# ✅ Good: Tag releases
git tag -a v1.2.0 -m "Release 1.2.0: Jira timeout support"
git push origin v1.2.0

# Use versioned images
jira_sync_image: quay.io/rhpds/jira-sync:v1.2.0

# ❌ Bad: Use :latest tag
jira_sync_image: quay.io/rhpds/jira-sync:latest
```

## Next Steps

After successful deployment:

1. **Test end-to-end workflow**: Create a test project via RHDH
2. **Configure monitoring alerts**: Set up PagerDuty/Slack integration
3. **Set up backups**: Configure PostgreSQL backup schedule
4. **Document customizations**: Update this guide with your changes

## References

- [Architecture Documentation](../rhdh-publishing-house/docs/architecture.md)
- [Phase Specifications](../rhdh-publishing-house/docs/specs/)
- [Troubleshooting Guide](troubleshooting.md)
- [Ansible Best Practices](https://docs.ansible.com/ansible/latest/user_guide/playbooks_best_practices.html)
