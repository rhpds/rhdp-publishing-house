# Publishing House — As-Is Implementation Spec

Internal reference documenting the current state of every Publishing House component. Generated 2026-08-21 from live scans of the repo, skills, templates, and the infra02 cluster.

## Documents

| Spec | Covers |
|---|---|
| [System Architecture](architecture.md) | Component map, data flow, integration points |
| [Central API](central-api.md) | Every endpoint, service, validation check, auth/RBAC |
| [SonataFlow Workflow](workflow.md) | States, transitions, events, data model, rejection loops |
| [Backstage Plugins](plugins.md) | UI components, scaffolder actions, routes |
| [AI Skills](skills.md) | Orchestrator, intake, migrate, development, helpers, agents |
| [Scaffolder Templates](templates.md) | Parameters, steps, skeleton files, template repo |
| [Deployment](deployment.md) | Ansible roles, Vault, ESO, DevSpaces, Keycloak, RHDH, SonataFlow |
| [Infrastructure (infra02)](infrastructure.md) | Deployed resources, images, routes, PVCs, CronJobs |

## Conventions

- Version numbers and image tags reflect what is deployed on infra02 as of 2026-08-21
- "Required" means validation will fail without it; "optional" means it passes if empty
- Stage names use snake_case: `intake`, `content_review`, `infra_review`, `env_setup`, `development`, `testing`, `published`
