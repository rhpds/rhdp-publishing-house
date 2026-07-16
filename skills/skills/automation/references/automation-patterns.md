# Publishing House Automation Patterns

Guidance for the automation agent when creating AgnosticV catalogs and developing
environment automation. These supplement the agnosticv skill rules — do not duplicate them.

## Sub-Phase Ordering

Automation has four sub-phases:

| Sub-Phase | Description |
|-----------|-------------|
| 7a: Automation Requirements | Reviewable scope document (what to automate) |
| 7b: Catalog Item | AgnosticV catalog configuration (skipped for self_published) |
| 7c: Automation Code | Ansible collection or GitOps automation |
| 7d: Testing | Human deploys and verifies automation works |

Sub-phases run in order.

## Infrastructure Type Routing

| Infrastructure | AgnosticV Config | Automation Pattern |
|---------------|-----------------|-------------------|
| OCP cluster (CNV) | `config: openshift-workloads`, `cloud_provider: cnv` | OCP workloads via Ansible roles |
| OCP cluster (AWS) | `config: openshift-workloads`, `cloud_provider: ec2` | OCP workloads via Ansible roles |
| RHEL/AAP VMs | `config: cloud-vms-base` | Cloud VM provisioning + Ansible roles |
| Sandbox (Cluster) | `config: openshift-cluster` | Namespace-scoped workloads |
| Sandbox (Tenant) | `config: namespace` | Tenant-scoped workloads |

## Automation Code Standards

Two automation approaches are supported:

- **Ansible collections:** See `@rhdp-publishing-house/skills/automation/references/ansible-automation-guide.md`
- **GitOps (Helm + ArgoCD):** See `@rhdp-publishing-house/skills/automation/references/gitops-automation-guide.md`

## What the Automation Agent Does NOT Do

- Does not write Showroom content
- Does not review content quality
- Does not implement ZT grading or health checks
- Does not manage the AgnosticV repository git operations
- Does not deploy or test the catalog
- Does not advance the lifecycle phase
