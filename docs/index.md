# Publishing House — RHDP Content Lifecycle Management

Publishing House is an AI-powered content lifecycle tool for Red Hat Demo Platform — one command provides an orchestrator that manages intake, writing, editing, automation, review, and publishing through specialized AI agent skills.

## Documentation

| Document | Description |
|---|---|
| [Overview](overview.md) | What PH is, why it exists, and how it works |
| [Getting Started](user/getting-started.md) | Install the plugin, create a project, run your first session |
| [Deployment Modes](user/deployment-modes.md) | Onboarded, self-published, and express modes compared |
| [System Design](architecture/system-design.md) | End-to-end technical architecture |
| [Central Backend](architecture/central.md) | MCP gateway, gate service, Jira sync, dashboard |
| [Skills System](architecture/skills.md) | Orchestrator, skill dispatch, agent boundaries |
| [Lifecycle & Phases](architecture/lifecycle-phases.md) | Phase engine, gates, manifest-as-truth |
| [RCARS Integration](architecture/rcars-integration.md) | Content advisory gateway and auth model |
| [Jira Integration](architecture/jira-integration.md) | Automatic Jira sync, ticket hierarchy, points model |
| [Deployment Guide](admin/deployment.md) | OpenShift deployment via Ansible |
| [MCP Authentication](admin/mcp-auth.md) | API key and service account token management |
| [Operations](admin/operations.md) | Troubleshooting, common tasks, skill development rules |
