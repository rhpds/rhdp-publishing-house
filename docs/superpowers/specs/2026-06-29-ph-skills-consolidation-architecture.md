# PH Skills Consolidation — Architecture Spec

**Date:** 2026-06-29
**Updated:** 2026-08-03
**Status:** Draft
**Author:** Prakhar Srivastava
**Scope:** Add ftl plugin, showroom content agents, and new gitops-helper + ansible-helper skills to rhdp-publishing-house-skills. Remove marketplace dependency for PH users.
**Migration Steps:** See [PH Skills Migration Plan](2026-06-29-ph-skills-migration-plan.md) for the step-by-step execution plan, phase ordering, and cutover communication.

---

## Scope Decisions (2026-08-03)

| Component | Decision | Reason |
|---|---|---|
| **ftl plugin** | Move — full copy | Zero direct PH→FTL edges today; included for future integration |
| **showroom:module-writing-helper** (`file-generator`) | Move — renamed | Development skill calls directly; writes .adoc content |
| **showroom:module-review-helper** (`module-reviewer`) | Move — renamed | Development skill calls directly; reviews .adoc content |
| **showroom skills** | **NOT moving** | Andrew Jones owns platform plumbing; development skill absorbs content generation directly |
| **showroom:config-helper, showroom:config-reviewer** | **NOT moving** | Andrew Jones owns (RHDPCD-172) — scaffold and config review |
| **scaffold agents** (`score-aggregator`, `format-detector`, `zero-scaffold-checker`, `zero-content-reviewer`) | **NOT moving** | Andrew's territory |
| **agnosticv plugin** | **Removed from scope** | Stays in marketplace; automation.md procedure calls it from there |
| **gitops-helper** | New skill (RHDPCD-111) | Automation phase — GitOps (Helm + ArgoCD) content authoring |
| **ansible-helper** | New skill (RHDPCD-110) | Automation phase — Ansible automation authoring |

---

## Complete Naming Reference

### showroom Skills — Andrew Jones (RHDPCD-172, NOT part of this migration)

| Skill | Role |
|---|---|
| `showroom:config-helper` | Scaffolds showroom structure: site.yml, ui-config.yml, tabs, nav, runtime-automation skeleton |
| `showroom:config-reviewer` | Reviews showroom config quality — validates site.yml, ui-config.yml, antora.yml |

### showroom Agents — Moving into PH repo (renamed)

| Old name | New name | Model | Role |
|---|---|---|---|
| `showroom:file-generator` | `showroom:module-writing-helper` | Sonnet | Generates one AsciiDoc file per invocation — called directly by development:writer |
| `showroom:module-reviewer` | `showroom:module-review-helper` | Sonnet | Reviews AsciiDoc quality — called directly by development:editor |

### showroom Agents — NOT moving (Andrew's domain)

| Agent | Owner | Role |
|---|---|---|
| `showroom:score-aggregator` | Andrew Jones | Aggregates review scores |
| `showroom:format-detector` | Andrew Jones | Detects classic vs zero-touch from repo structure |
| `showroom:zero-scaffold-checker` | Andrew Jones | Validates ZT scaffold |
| `showroom:zero-content-reviewer` | Andrew Jones | ZT content + automation pairing review |
| `showroom:doc-writer` | Andrew Jones | Updates GitHub Pages documentation |
| `showroom:diagram-generator` | Andrew Jones | Generates architecture diagrams |

### New Skills (added to PH repo)

| Skill | Jira | Role |
|---|---|---|
| `rhdp-publishing-house:gitops-helper` | RHDPCD-111 | GitOps (Helm + ArgoCD) automation authoring |
| `rhdp-publishing-house:ansible-helper` | RHDPCD-110 | Ansible automation authoring |

### ftl Agents (moving — full copy, unchanged)

| Agent | Role |
|---|---|
| `ftl:content-reader` | Reads AsciiDoc lab content, classifies steps for FTL processing |
| `ftl:solve-writer` | Writes solve.yml Ansible playbooks from content analysis |
| `ftl:validate-writer` | Writes validate.yml Ansible playbooks from content analysis |
| `ftl:env-connector` | Connects to live RHDP showroom, runs and validates full solve/validate cycle |
| `ftl:rhdp-lab-validator` | E2E lab validator — orchestrates full solve/validate test against live lab |

### agnosticv (NOT moving — stays in marketplace)

`agnosticv:catalog-builder` and `agnosticv:validator` remain in `rhdp-skills-marketplace`. The PH `automation.md` procedure continues to call them from there.

---

## Problem

Today PH users need two separate plugin installs:
1. `rhdp-publishing-house-skills` — PH orchestration skills
2. `rhdp-skills-marketplace` — ftl and internal tools

PH skills hard-depend on marketplace skills. If a user installs PH without marketplace, they get silent failures during automation phases.

## Solution

Add ftl, two showroom content agents (renamed), and two new automation skills directly to `rhdp-publishing-house-skills`. One `--plugin-dir` install covers the PH content lifecycle.

## Critical Constraint: Plugin Names Cannot Change

Claude Code resolves skill calls as `<plugin-name>:<skill-name>`. The plugin name comes from `.claude-plugin/plugin.json` → `"name"` field.

If skills moved into the `rhdp-publishing-house` plugin namespace, ALL call sites in PH SKILL.md files would break. Therefore: **each plugin MUST retain its original name in its own plugin.json**.

## Target Structure

```
rhdp-publishing-house-skills/           ← ONE repo, users clone once
├── .claude-plugin/
│   └── plugin.json                     ← name: "rhdp-publishing-house"
├── skills/                             ← PH orchestration skills
│   ├── orchestrator/SKILL.md
│   ├── intake/SKILL.md
│   ├── development/SKILL.md            ← calls showroom agents + gitops/ansible skills directly
│   ├── worklog/SKILL.md
│   ├── gitops-helper/SKILL.md          ← NEW (RHDPCD-111)
│   └── ansible-helper/SKILL.md         ← NEW (RHDPCD-110)
│
├── agents/
│   ├── module-writing-helper.md        ← was showroom:file-generator
│   └── module-review-helper.md         ← was showroom:module-reviewer
│
├── docs/
│   └── showroom/
│       └── SKILL-COMMON-RULES.md       ← AsciiDoc rules used by both agents
│
└── ftl/                                ← NEW — copied from marketplace
    ├── .claude-plugin/
    │   └── plugin.json                 ← name: "ftl" (MUST keep this name)
    ├── agents/
    │   ├── content-reader.md
    │   ├── solve-writer.md
    │   ├── validate-writer.md
    │   ├── env-connector.md
    │   └── rhdp-lab-validator/
    └── docs/
```

## Development Skill Integration Model

The `development` skill is the single entry point for all content and automation work. It calls agents and sub-skills directly — no intermediate showroom sub-skill invocation.

```
development skill
  └── writer procedure
        → spawns showroom:module-writing-helper (writes .adoc modules)
        → spawns showroom:module-review-helper (reviews generated .adoc)
  └── automation procedure
        → calls rhdp-publishing-house:gitops-helper (GitOps path)
        → calls rhdp-publishing-house:ansible-helper (Ansible path)
        → calls agnosticv:catalog-builder (from marketplace — unchanged)
```

No `ph_payload` sub-skill invocation. Development owns the content pipeline directly.

## What Stays in Marketplace

The following remain in `rhdp-skills-marketplace` and are NOT part of this migration:

- `agnosticv` plugin (catalog-builder, validator, all agents)
- `showroom` plugin skills and scaffold agents
- `health` plugin
- `sandbox-cli` plugin

## Non-Goals

- Do NOT rename `ftl` plugin name — see constraint above
- Do NOT copy agnosticv into this repo — it stays in marketplace
- Do NOT copy showroom skills — development absorbs orchestration directly
- Do NOT copy showroom scaffold/config agents — Andrew Jones owns those (RHDPCD-172)
