# PH Skills Consolidation — Architecture Spec

**Date:** 2026-06-29
**Updated:** 2026-08-04
**Status:** Draft
**Author:** Prakhar Srivastava
**Scope:** Add ftl plugin, showroom content agents, and new gitops-helper + ansible-helper skills to rhdp-publishing-house-skills. Remove marketplace dependency for PH users.
**Migration Steps:** See [PH Skills Migration Plan](2026-06-29-ph-skills-migration-plan.md) for the step-by-step execution plan, phase ordering, and cutover communication.

---

## Scope Decisions (2026-08-03)

| Component | Decision | Reason |
|---|---|---|
| **ftl plugin** | Move — full copy | Zero direct PH→FTL edges today; included for future integration |
| **showroom:module-writing-helper** (was `file-generator`) | Move — renamed | Development skill calls directly; writes .adoc content |
| **showroom:module-reviewer** | Move — name unchanged | Development skill calls directly; reviews .adoc content |
| **showroom skills** | **NOT moving** | Andrew Jones owns platform plumbing; development skill absorbs content generation directly |
| **showroom:config-helper, showroom:config-reviewer** | **NOT moving** | Andrew Jones owns (RHDPCD-172) — scaffold and config review |
| **scaffold agents** (`score-aggregator`, `format-detector`, `zero-scaffold-checker`, `zero-content-reviewer`) | **NOT moving** | Andrew's territory |
| **agnosticv plugin** | **Removed from scope** | Stays in marketplace; automation.md procedure calls it from there |
| **gitops-helper** | New skill (RHDPCD-111) | Automation phase — GitOps (Helm + ArgoCD) content authoring |
| **ansible-helper** | New skill (RHDPCD-110) | Automation phase — Ansible automation authoring |

---

## Model Policy — No Hardcoded Models

Skills and agents MUST NOT hardcode model IDs (e.g., `claude-sonnet-4-6`, `claude-opus-4-6`). The `model:` field is omitted from all frontmatter. Skills and agents inherit the model from the user's Claude Code session.

This ensures:
- Future model upgrades (Sonnet 5, Opus 5) work automatically
- Users who run on Opus get Opus everywhere; users on Sonnet get Sonnet
- No maintenance burden when model IDs change

**Migration step:** Remove `model:` lines from all existing PH skills (orchestrator, intake, development, worklog) and from all showroom/ftl agent and skill files during the copy.

---

## Complete Naming Reference

### showroom Skills — Andrew Jones (RHDPCD-172, NOT part of this migration)

| Skill | Role |
|---|---|
| `showroom:config-helper` | Scaffolds showroom structure: site.yml, ui-config.yml, tabs, nav, runtime-automation skeleton |
| `showroom:config-reviewer` | Reviews showroom config quality — validates site.yml, ui-config.yml, antora.yml |

### showroom Agents — Moving into PH repo

| Old name | New name | Role |
|---|---|---|
| `showroom:file-generator` | `showroom:module-writing-helper` | Generates one AsciiDoc file per invocation — called directly by development:writer |
| `showroom:module-reviewer` | `showroom:module-reviewer` (unchanged) | Reviews AsciiDoc quality — called directly by development:editor |

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

Add ftl, two showroom content agents, and two new automation skills directly to `rhdp-publishing-house-skills`. One `--plugin-dir` install covers the PH content lifecycle.

## Critical Constraint: Plugin Names Cannot Change

Claude Code resolves skill calls as `<plugin-name>:<skill-name>`. The plugin name comes from `.claude-plugin/plugin.json` → `"name"` field.

If skills moved into the `rhdp-publishing-house` plugin namespace, ALL call sites in PH SKILL.md files would break. Therefore: **each plugin MUST retain its original name in its own plugin.json**.

## Agent Name Resolution

Claude Code derives agent names from `<plugin-name>:<filename>` — the plugin name comes from the nearest parent `.claude-plugin/plugin.json`, and the filename is the `.md` file without extension.

This means agents MUST live inside the correct plugin directory to get the right name:
- `showroom/agents/module-writing-helper.md` → resolves to `showroom:module-writing-helper` ✅
- `agents/module-writing-helper.md` (repo root) → resolves to `rhdp-publishing-house:module-writing-helper` ❌

The showroom content agents stay inside `showroom/agents/` so their `showroom:*` names are preserved.

## Target Structure

```
rhdp-publishing-house-skills/           ← ONE repo, users clone once
├── .claude-plugin/
│   └── plugin.json                     ← name: "rhdp-publishing-house"
├── skills/                             ← PH orchestration skills
│   ├── orchestrator/SKILL.md
│   ├── intake/SKILL.md
│   ├── development/SKILL.md            ← calls showroom agents + gitops/ansible skills directly
│   │   ├── procedures/
│   │   │   ├── writer.md               ← spawns showroom:module-writing-helper agent
│   │   │   ├── editor.md               ← spawns showroom:module-reviewer agent
│   │   │   └── automation.md           ← dispatches to gitops/ansible helpers
│   │   └── references/
│   │       ├── writing-standards.md
│   │       ├── editing-checklist.md
│   │       ├── automation-patterns.md
│   │       ├── automation-manifest-format.md
│   │       ├── ansible-automation-guide.md
│   │       └── gitops-automation-guide.md
│   ├── worklog/SKILL.md
│   ├── gitops-helper/                  ← NEW (RHDPCD-111, Juliano)
│   │   ├── SKILL.md
│   │   └── references/
│   │       └── gitops-patterns.md
│   └── ansible-helper/                 ← NEW (RHDPCD-110, Mitesh)
│       ├── SKILL.md
│       └── references/
│           └── ansible-patterns.md
│
├── showroom/                           ← copied from marketplace (full plugin)
│   ├── .claude-plugin/
│   │   └── plugin.json                 ← name: "showroom" (MUST keep this name)
│   ├── agents/
│   │   ├── module-writing-helper.md    ← was file-generator.md (renamed)
│   │   ├── module-reviewer.md          ← name unchanged
│   │   ├── scaffold-checker.md         ← Andrew's — included in full copy
│   │   ├── score-aggregator.md         ← Andrew's — included in full copy
│   │   ├── doc-writer.md              ← Andrew's — included in full copy
│   │   └── diagram-generator.md       ← Andrew's — included in full copy
│   ├── skills/                         ← Andrew's skills — included in full copy
│   ├── docs/
│   │   └── SKILL-COMMON-RULES.md      ← AsciiDoc rules (@showroom/docs/ references work)
│   ├── prompts/
│   └── templates/
│
└── ftl/                                ← copied from marketplace (full plugin)
    ├── .claude-plugin/
    │   └── plugin.json                 ← name: "ftl" (MUST keep this name)
    ├── agents/
    │   ├── content-reader.md
    │   ├── solve-writer.md
    │   ├── validate-writer.md
    │   └── env-connector.md
    └── skills/
        └── rhdp-lab-validator/
```

## Development Skill Integration Model

The `development` skill is the single entry point for all content and automation work.

### Writer procedure → showroom:module-writing-helper

writer.md spawns the agent via Task tool with `subagent_type`. The agent receives all context via prompt — no file reads at spawn time.

```
Task tool:
  subagent_type: showroom:module-writing-helper
  prompt: |
    TARGET_FILE: <path to .adoc file>
    FILE_TYPE: module
    FULL_SPEC: <JSON built from spec.yaml + design.md + module outline>
    LAB_TYPE: <ocp|rhel|vm|ai>
    CONTENT_TYPE: <workshop|demo>
    REPO_PATH: <absolute repo path>
```

One agent per module, run sequentially (each depends on the previous for story continuity).

### Editor procedure → showroom:module-reviewer

editor.md spawns the agent the same way:

```
Task tool:
  subagent_type: showroom:module-reviewer
  prompt: |
    MODULE_FILE: <path to .adoc file>
    CONTENT_TYPE: <workshop|demo>
    LAB_TYPE: <ocp|rhel|vm|ai>
    SHARED_CONTEXT: <JSON with module_order, defined_attributes, etc.>
    REPO_PATH: <absolute repo path>
```

After the agent returns, editor.md runs its own spec alignment checks (SA-1 through RS-2).

### Automation procedure → skills

automation.md dispatches to skills (not agents) — skills have their own pre-flight and workflow check:

```
automation_approach: ansible  → Skill tool: rhdp-publishing-house:ansible-helper
automation_approach: gitops   → Skill tool: rhdp-publishing-house:gitops-helper
automation_approach: both     → ansible-helper first, then gitops-helper
```

No `ph_payload` sub-skill invocation anywhere. Development owns the content pipeline directly.

## Standard PH SKILL.md Skeleton

Every skill in this repo follows this structure. New skills (gitops-helper, ansible-helper) and contributor skills MUST follow this skeleton.

All metadata goes in a single frontmatter block:

```yaml
---
name: rhdp-publishing-house:<skill-name>
description: This skill should be used when the user asks to "..."
context: main
---
```

No `model:` field — skills inherit from the user's session.

```markdown
# <Skill Name>

**RULE: If any `publishing-house/tools/` script exits with a non-zero exit code, STOP immediately.**

## Tool Boundaries

**Do NOT use** Central API tools directly. You work locally: read files, write content, update spec.yaml.
**Do NOT use** MCP tools. All external interactions go through `publishing-house/tools/` scripts.

## Steps 1–3 — Pre-flight

Follow @rhdp-publishing-house/skills/common/pre-flight.md (Steps 1–3: verify project, read identity, check auth).

## Step 4 — Workflow check

**4a.** Get workflow data → extract workflow_id
**4b.** Get workflow state → verify stage is `development` (STOP if not)
**4c.** Sync → pull Central API data, commit if needed
**4d.** Handle rejections if any

## Step 5 — Read project context

Read spec.yaml, design.md, and any other inputs specific to this skill.

## Dispatch / Main work

[Skill-specific logic here]
```

## What Stays in Marketplace

The following remain in `rhdp-skills-marketplace` and are NOT part of this migration:

- `agnosticv` plugin (catalog-builder, validator, all agents)
- `health` plugin
- `sandbox-cli` plugin

## Non-Goals

- Do NOT rename `ftl` plugin name — see constraint above
- Do NOT rename `showroom` plugin name — see constraint above
- Do NOT copy agnosticv into this repo — it stays in marketplace
- Do NOT hardcode model IDs — all skills and agents inherit from session
