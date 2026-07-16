# [Project Title]

## Problem Statement

[What gap does this fill? Who has this problem and why can't they solve it today? 2-3 sentences, specific — reference a real persona with a real need.]

## Target Audience

- **Role:** [Data scientists, platform engineers, developers, etc.]
- **Experience level:** [Beginner, intermediate, or advanced]
- **What they already know:** [Existing skills and knowledge]
- **What they don't know:** [Skills this lab teaches]

## Prerequisites

- [What the learner must know or have completed before starting]
- [Can the lab validate these automatically? Yes/No — brief explanation]

<!-- If no prerequisites, write "None" -->

## Learning Objectives

1. [Action verb] [specific, measurable outcome]
2. [Action verb] [specific, measurable outcome]
3. [Action verb] [specific, measurable outcome]

<!-- 3-7 objectives. Start with action verbs: Configure, Deploy, Create, Implement, Troubleshoot, Monitor, Scale.
Each should be testable. NOT: Understand, Learn, Know. -->

## Content Type

[Lab (hands-on) or Demo (presenter-led)]

## Products & Technologies

- [Official Red Hat product name with version if relevant]
- [Additional products/technologies]

<!-- Use official names: "Red Hat OpenShift", not "OpenShift". List upstream projects separately. -->

## Module Map

| Module | Title | Duration |
|--------|-------|----------|
| 1 | [Module title] | [XX min] |
| 2 | [Module title] | [XX min] |
| — | **Total hands-on** | **[X hours]** |
| — | Intro / presentation | [~XX min] |
| — | **Total lab** | **[~X hours]** |

<!-- Each module 10-30 min. Total: lab 1-4 hours, demo 15-45 min. Modules should build on each other. -->

## Difficulty Level

[Beginner, Intermediate, or Advanced]

## Environment

**Learner view:** [What exists when the lab starts — pre-deployed resources, what participants see and interact with. Be specific about cluster details.]

**Automation needed:** [Yes/No]

[If yes, list what automation must provision — operators, per-user resources, sample apps, data sets.]

## Infrastructure Requirements

**Base infrastructure:** [Base CI type: ocp4-cluster, ocp-workloads, cloud-vms-base, or existing CI name]
**Cloud provider:** [CNV (default), AWS, GCP, Azure]
**Automation approach:** [Ansible, GitOps (Helm + ArgoCD), or combo]

### Cluster Sizing
- Workers: [N × (X vCPU, Y GB RAM, Z GB disk)]
- GPU nodes: [none | N × type]
- RHEL nodes: [none | N × (X vCPU, Y GB RAM, Z GB disk)]

### Multi-User
- Topology: [shared-cluster | per-student | cnv-pool]
- Max concurrent users: [N — required if per-student or cnv-pool]
- Peak environments: [auto-computed by Central]

### AI / MaaS
- AI requirement: [maas | gpu | none]
- Model tier: [open-source | frontier] (if maas or gpu)
- Model name: [e.g. granite-3.1-8b — if known]
- Justification: [required if frontier or gpu — why open-source is insufficient]

### External Services
- [named-service.com — or "None"]

### AAP
- Version: [e.g. 2.5 — required if AAP in products; omit if not applicable]

### Non-GA Products
- [product name + version — or "None (all products are GA)"]
- Access plan: [how access is provided during provisioning — or "N/A"]

<!-- Not all fields must be known at intake. "TBD, estimating ~X" is fine. Spec refinement fills gaps. -->

## Assessment Strategy

[How will we know the learner successfully completed each module? Per module: verification script, visible result in UI, quiz question, or trust-based. Be specific.]

