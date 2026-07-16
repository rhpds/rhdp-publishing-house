---
title: Overview
description: What Publishing House is, why it exists, and how it works
---

# Publishing House — Overview

## What is Publishing House?

Publishing House is an AI-powered content lifecycle management system for Red Hat Demo Platform — a Claude Code plugin that gives content developers a persistent, state-aware orchestrator managing the entire content lifecycle through specialized AI agent skills. Run `/rhdp-publishing-house` in a project repo and you have an assistant that knows where your project is, what's been done, and what needs to happen next.

Say you're building a new OpenShift workshop. Instead of manually writing AsciiDoc modules, creating catalog configurations, developing automation, and tracking progress in Jira — you tell Publishing House what you want to build, and it dispatches specialized agents to handle each phase while you focus on the design decisions that matter.

## The Problem It Solves

Building an RHDP workshop or demo means juggling multiple tools and skill sets — AsciiDoc for lab content, YAML for catalog configuration, Ansible or GitOps for automation, security reviews for compliance, Jira for tracking. Each step requires different expertise. Most time is spent on toil — formatting, boilerplate, configuration syntax — not on designing the learning experience.

There's also no single system that tracks where a project stands. Progress lives in scattered places: partially written modules in a git repo, a Jira ticket that may or may not be current, tribal knowledge about which reviews have happened. When someone picks up a project after a break, the first hour goes to figuring out where things left off.

## How It Works

### Hub + Spoke Architecture

Publishing House uses a thin orchestrator as its hub. When you invoke `/rhdp-publishing-house`, the orchestrator discovers your project, reads the manifest, determines which lifecycle phase you're in, and dispatches the appropriate skill. Each skill is a focused agent that reads its inputs from the manifest, produces its outputs, and hands control back.

```mermaid
graph TD
    U["Content Developer"] -->|"/rhdp-publishing-house"| O["Orchestrator (Hub)"]
    O --> I["Intake"]
    O --> W["Writer"]
    O --> E["Editor"]
    O --> A["Automation"]
    O --> WL["Worklog"]
    O -.-> R["Review Agents"]

    I -->|"content vetting"| RCARS["RCARS"]
    O -->|"state, gates, Jira"| C["Central Backend"]
    C -->|"tickets"| J["Jira Cloud"]

    style O fill:#1a73e8,color:#fff
    style C fill:#1a73e8,color:#fff
```

Six skills run today: the orchestrator itself, intake (project onboarding and scoping), writer (lab and demo content generation), editor (content quality review), automation (environment and deployment configuration), and worklog (session bridging). Code review, security review, and final review phases exist in the lifecycle but rely on review agents that are not yet implemented.

### Manifest as Truth

All project state flows from a single YAML file: `publishing-house/manifest.yaml` in the project's git repository. It records metadata, current lifecycle phase, phase completion status, and configuration. Every skill reads from it. Every phase transition updates it. Central and Jira are downstream consumers — they reflect the manifest, never the other way around.

Project state is versioned, portable, and auditable. Open the manifest to see exactly which phases are complete, who approved them, and what's next. There is no database that disagrees with the code.

### Central Backend

Central is the backend that ties the system together, deployed on OpenShift. It serves four roles:

**Gate authority.** When a project requests phase advancement, Central validates prerequisites and records the decision. For example, the writing phase cannot start until the approval gate passes — Central checks that spec refinement is complete and the spec meets structural and quality requirements before allowing the project to advance.

**Jira sync engine.** For onboarded projects, Central creates and updates Jira tickets automatically as work progresses. Developers never touch Jira — tickets update as a side effect of doing the work.

**RCARS gateway.** Central proxies content advisory requests to RCARS, so skills query RCARS through MCP tools rather than connecting directly.

**Project dashboard.** A web frontend gives visibility into all active projects — pipeline board, project detail views, gate decisions, and validation results.

See [Central Backend](architecture/central.md) for the full technical architecture.

### RCARS Integration

During intake, Publishing House queries RCARS to check whether similar content already exists in the RHDP catalog. RCARS understands what each catalog item teaches — not just titles, but the actual lab content — so it detects semantic overlap that keyword searches would miss. If your proposed workshop covers the same ground as an existing one, PH surfaces that early. Reuse is always better than duplicate work.

See [RCARS Integration](architecture/rcars-integration.md) for the gateway architecture and auth model.

### Deployment Modes

Publishing House supports three deployment modes, each with different levels of process and oversight:

**Onboarded** is the full RHDP publishing lifecycle. The project gets a git repo from the PH template, a manifest, Jira tracking, RCARS vetting, all review gates, and a path to production in the RHDP catalog. This is the mode for content that will be maintained long-term.

**Self-published** uses the same lifecycle and quality tools, but the content is not intended for the RHDP catalog. Teams use this mode to develop internal demos, training materials, or content they will host themselves. Gates are advisory rather than enforced — the author decides when to advance.

**Express** is for one-off demo environments without the full publishing lifecycle — quick deployments where the infrastructure matters more than polished lab content. Express mode is currently in design.

See [Deployment Modes](user/deployment-modes.md) for a detailed comparison.

### Session Continuity

Pick up where you left off any day, any session. The manifest preserves project state in git, and the worklog skill records what was accomplished and what should happen next. Run `/rhdp-publishing-house` after a month-long break and the orchestrator reads the manifest, checks Central, and tells you exactly where things stand.

## Who Uses It

**Content developers** are the primary users. They run `/rhdp-publishing-house` in a project repository and work through the lifecycle with AI assistance. The orchestrator guides each phase, dispatches the right skill, and tracks progress automatically.

!!! note "Local tool required"
    A hosted solution is in development, but for now you must have [Claude Code](https://docs.anthropic.com/en/docs/claude-code) or [Cursor](https://www.cursor.com/) installed locally to use Publishing House.

**Content managers and PMs** view progress across projects in the Central dashboard and Jira — which projects are in which phase, gate decisions, velocity across the content portfolio. They don't need Claude Code.

See [System Design](architecture/system-design.md) for the end-to-end technical architecture and [Getting Started](user/getting-started.md) for installation instructions.
