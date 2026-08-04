# PH Skills Consolidation — Architecture Spec

**Date:** 2026-06-29
**Updated:** 2026-08-04
**Status:** Draft
**Author:** Prakhar Srivastava
**Scope:** Add showroom content agents, Andrew's showroom config skills (RHDPCD-172), and new gitops-helper + ansible-helper skills to rhdp-publishing-house-skills. Remove marketplace dependency for PH users.
**Migration Steps:** See [PH Skills Migration Plan](2026-06-29-ph-skills-migration-plan.md) for the step-by-step execution plan, phase ordering, and cutover communication.

---

## Scope Decisions (2026-08-04)

| Component | Decision | Reason |
|---|---|---|
| **rhdp-publishing-house:module-writing-helper** | Move — renamed + namespace change | Agents live at top-level `agents/` under `rhdp-publishing-house` plugin; writes .adoc content |
| **rhdp-publishing-house:module-reviewer** | Move — namespace change | Agents live at top-level `agents/`; reviews .adoc content |
| **showroom skills** (`create-lab`, `create-demo`, `verify-content`, `blog-generate`) | **Delete after copy** | Andrew Jones owns platform plumbing; PH development calls agents directly |
| **scaffold agents** (`scaffold-checker`, `score-aggregator`, `doc-writer`, `diagram-generator`, `format-detector`, `zero-scaffold-checker`, `zero-content-reviewer`) | **Delete after copy** | Andrew's territory (RHDPCD-172) |
| **rhdp-publishing-house:config-helper** | **Delivered** (RHDPCD-172) | Andrew Jones — skill at `skills/config-helper/`, sets up showroom repos |
| **rhdp-publishing-house:config-reviewer** | **Delivered** (RHDPCD-172) | Andrew Jones — skill at `skills/config-reviewer/`, validates showroom config |
| **ftl plugin** | **Removed** | Mitesh owns FTL validation separately — not part of PH install |
| **agnosticv plugin** | **NOT in scope** | Stays in marketplace; NOT called by PH automation |
| **gitops-helper** | New skill (RHDPCD-111) | Automation phase — GitOps (Helm + ArgoCD) content authoring |
| **ansible-helper** | New skill (RHDPCD-110) | Automation phase — Ansible automation authoring |

---

## Workflow Diagram (AUTHORITATIVE)

Scaffold is Step 1 INSIDE the development phase — NOT a separate phase. Module status tracking enforces sequential writing.

```
User
  |
  +-- /rhdp-publishing-house (SKILL)
      |
      +-- intake phase --------------------------------------------+
      |   rhdp-publishing-house:intake                             |
      |   +-- 02-discovery -> 03-design-doc -> 04-module-outlines  |
      |      -> 05-infrastructure -> 06-finalize                   |
      +------------------------------------------------------------+
      |
      +-- development phase ----------------------------------------+
      |   rhdp-publishing-house:development                         |
      |                                                             |
      |   Step 1: Scaffold check (PREREQUISITE)                     |
      |   +-- [Skill] rhdp-publishing-house:config-reviewer         |
      |      +-- PASS -> proceed to Step 1b                         |
      |      +-- FAIL -> report issues to user                      |
      |               +-- User says "help me" / "fix it"            |
      |                  -> [Skill] rhdp-publishing-house:config-helper
      |                    (Andrew, RHDPCD-172)                      |
      |               +-- User says "I'll handle it"                |
      |                  -> STOP. User scaffolds manually.           |
      |                                                             |
      |   Step 1b: Module status validation                         |
      |   +-- Read spec.yaml module statuses                        |
      |      +-- Any in_progress? -> warn user, ask to continue     |
      |      +-- All complete + "write"? -> "All done, edit instead?"|
      |      +-- Otherwise -> proceed to Step 2                     |
      |                                                             |
      |   Step 2: Dispatch                                          |
      |   +-- "write"  -> writer.md                                 |
      |   |   +-- reads: spec.yaml + design.md + module outline     |
      |   |   +-- presents plan -> waits for approval               |
      |   |   +-- [Task] rhdp-publishing-house:module-writing-helper |
      |   |   +-- auto-run [Task] module-reviewer (HARD STOP)       |
      |   |   +-- status: not_started -> in_progress -> complete    |
      |   |       +-- Sequential: N blocked until 1..N-1 complete   |
      |   |                                                         |
      |   +-- "edit"   -> editor.md                                 |
      |   |   +-- [Task] rhdp-publishing-house:module-reviewer      |
      |   |   +-- SA-1->RS-2 spec alignment checks                  |
      |   |                                                         |
      |   +-- "automate" -> automation.md                           |
      |       +-- [Skill] ansible-helper  (FUTURE -- RHDPCD-110)    |
      |       +-- [Skill] gitops-helper   (FUTURE -- RHDPCD-111)    |
      +-------------------------------------------------------------+

Legend:
  [Task]  = agent invocation (Task tool + subagent_type)
  [Skill] = skill invocation (Skill tool)
  FUTURE  = not yet built, dispatch path wired but destination missing
```

---

## Content vs Scaffolding Boundary

PH development skills handle **content** — writing and reviewing `.adoc` module files inside an already-scaffolded showroom repo. They never touch showroom infrastructure files.

Showroom **scaffolding** — the repo structure, config files, and platform plumbing — is Andrew Jones's domain (RHDPCD-172).

### What is CONTENT (PH development owns)

- Writing `.adoc` module files (`content/modules/ROOT/pages/*.adoc`)
- Updating `nav.adoc` with module entries
- Reviewing `.adoc` quality (spec alignment, Red Hat style, AsciiDoc correctness)
- Generating automation code (Ansible roles, GitOps manifests)

Agents involved: `rhdp-publishing-house:module-writing-helper`, `rhdp-publishing-house:module-reviewer`

### What is SCAFFOLDING (Andrew owns — RHDPCD-172, delivered)

- Creating/configuring `site.yml` (showroom title, lab_type, tabs, consoles)
- Creating/configuring `ui-config.yml` (theme, branding, custom CSS)
- Creating/configuring `antora.yml` (component name, version, nav)
- Setting up `runtime-automation/` skeleton (buttons.js, solve/validate structure)
- Creating directory structure (`content/modules/ROOT/pages/`, `assets/`, etc.)
- Tab and console configuration (terminal, IDE, web consoles)
- GitHub Pages deployment (`gh-pages.yml`, `supplemental-ui/`)

Skills involved: `rhdp-publishing-house:config-reviewer` (validates), `rhdp-publishing-house:config-helper` (creates/fixes)

### Scaffold check flow (Step 1 of development)

1. Development skill invokes `rhdp-publishing-house:config-reviewer` via **Skill tool** automatically — no user prompt needed
2. config-reviewer checks config files (`site.yml`, `ui-config.yml`, `antora.yml`, `nav.adoc`) with 30 rules across 5 categories, severity-rated findings
3. If PASS — proceed to module status check and dispatch
4. If FAIL — report the specific issues to the user. Do NOT auto-fix.
   - If user says "help me" / "fix it" — invoke `rhdp-publishing-house:config-helper` via **Skill tool**
   - If user says "I'll handle it" — STOP. User scaffolds manually.

### Why this boundary matters

The existing `showroom:create-lab` skill mixes both concerns — Phase 2.5 does scaffolding, Phase 3 does content generation. In the new architecture:

- **PH development:writer** spawns `rhdp-publishing-house:module-writing-helper` directly — content only, no scaffolding
- **PH development:editor** spawns `rhdp-publishing-house:module-reviewer` directly — content review only
- Scaffolding is a prerequisite check (Step 1) inside development, not a separate phase

This means a showroom repo must already be scaffolded (by Andrew's config-helper, manually, or via `showroom:create-lab` from the marketplace) before PH development skills can write content into it.

---

## Module Status Tracking

Modules have a `status` field in `spec.yaml` under each module entry:
- **`not_started`** — module hasn't been written yet
- **`in_progress`** — module writing has begun but isn't finished
- **`complete`** — module is done

### Sequential enforcement

Module N cannot start until modules 1 through N-1 are ALL `complete`. writer.md checks this before spawning the agent.

### Development SKILL.md validation gate

Before dispatching to any procedure, development skill checks if any module has `status: in_progress`. If so, it warns the user and asks whether to continue that module before starting new work.

### Writer interaction flow (human-in-the-loop)

1. Read spec.yaml, design.md, and module outlines (3 data sources)
2. Present a plan: "Here's what I'll write for module N: [summary]. Ready to proceed?"
3. Wait for user approval — never auto-generate
4. Spawn `rhdp-publishing-house:module-writing-helper` agent — set module status to `in_progress`
5. After write completes, auto-run `rhdp-publishing-house:module-reviewer` (mandatory, not user-triggered)
6. Present reviewer findings as guidance — not all findings need fixing, author uses judgment
7. **HARD STOP** — do NOT mark complete. Author reviews the file and chooses:
   - **"review again"** — re-run reviewer on current file (loop back to step 5)
   - **"module N is done"** — mark status `complete`, unlock next module
   - Ask AI to fix specific items — apply changes, then back to step 5

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

### Andrew Jones Skills (RHDPCD-172 — delivered)

Skills at `skills/config-helper/` and `skills/config-reviewer/` with reference docs:

| Skill | Role | References |
|---|---|---|
| `rhdp-publishing-house:config-helper` | Sets up showroom repos: site.yml, ui-config.yml, tabs, antora.yml, runtime-automation. Detects `project.showroom_type` from spec.yaml. Supports Open, Guided, ZT Guided. | `showroom-patterns.md`, `config-files.md` |
| `rhdp-publishing-house:config-reviewer` | Validates showroom config with 30 rules across 5 categories (site.yml, ui-config.yml, antora.yml, nav.adoc, cross-file), severity levels, auto-fix suggestions | `validation-rules.md` |

### Content Agents — In PH repo (top-level `agents/`)

| Agent | Role |
|---|---|
| `rhdp-publishing-house:module-writing-helper` | Generates one AsciiDoc file per invocation — called directly by development:writer |
| `rhdp-publishing-house:module-reviewer` | Reviews AsciiDoc quality — called directly by development:editor |

### Scaffold Agents — NOT moving (Andrew's domain, deleted from copy)

| Agent | Owner | Role |
|---|---|---|
| `showroom:scaffold-checker` | Andrew Jones | Validates scaffold structure |
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

---

## Problem

Today PH users need two separate plugin installs:
1. `rhdp-publishing-house-skills` — PH orchestration skills
2. `rhdp-skills-marketplace` — ftl and internal tools

PH skills hard-depend on marketplace skills. If a user installs PH without marketplace, they get silent failures during automation phases.

## Solution

Add two showroom content agents, two config skills, and two new automation skills directly to `rhdp-publishing-house-skills`. One `--plugin-dir` install covers the PH content lifecycle.

## Agent Name Resolution

Claude Code derives agent names from `<plugin-name>:<filename>` — the plugin name comes from the nearest parent `.claude-plugin/plugin.json`, and the filename is the `.md` file without extension.

Agents live at the top-level `agents/` directory alongside `.claude-plugin/plugin.json` (name: `rhdp-publishing-house`):
- `agents/module-writing-helper.md` resolves to `rhdp-publishing-house:module-writing-helper`
- `agents/module-reviewer.md` resolves to `rhdp-publishing-house:module-reviewer`

Skills resolve by frontmatter `name:` field in SKILL.md:
- `skills/config-helper/SKILL.md` has `name: rhdp-publishing-house:config-helper`
- `skills/config-reviewer/SKILL.md` has `name: rhdp-publishing-house:config-reviewer`

The showroom sub-plugin (`showroom/.claude-plugin/`) has been removed — all content agents live at the top level.

## Target Structure

```
rhdp-publishing-house-skills/           <-- ONE repo, users clone once
+-- .claude-plugin/
|   +-- plugin.json                     <-- name: "rhdp-publishing-house"
+-- agents/                             <-- content agents at top level
|   +-- module-writing-helper.md        <-- rhdp-publishing-house:module-writing-helper
|   +-- module-reviewer.md              <-- rhdp-publishing-house:module-reviewer
+-- skills/                             <-- PH orchestration + config skills
|   +-- orchestrator/SKILL.md
|   +-- intake/SKILL.md
|   +-- development/SKILL.md            <-- calls agents + config/automation skills
|   |   +-- procedures/
|   |   |   +-- writer.md               <-- spawns module-writing-helper agent
|   |   |   +-- editor.md               <-- spawns module-reviewer agent
|   |   |   +-- automation.md           <-- dispatches to ansible-helper / gitops-helper
|   |   +-- references/
|   +-- config-helper/                  <-- Andrew (RHDPCD-172)
|   |   +-- SKILL.md
|   |   +-- references/
|   |       +-- showroom-patterns.md
|   |       +-- config-files.md
|   +-- config-reviewer/                <-- Andrew (RHDPCD-172)
|   |   +-- SKILL.md
|   |   +-- references/
|   |       +-- validation-rules.md
|   +-- worklog/SKILL.md
|   +-- gitops-helper/                  <-- FUTURE (RHDPCD-111, Juliano)
|   |   +-- SKILL.md
|   |   +-- references/
|   |       +-- gitops-patterns.md
|   +-- ansible-helper/                 <-- FUTURE (RHDPCD-110, Mitesh)
|       +-- SKILL.md
|       +-- references/
|           +-- ansible-patterns.md
|
+-- showroom/                           <-- content resources only (no sub-plugin, no agents)
    +-- docs/
    |   +-- SKILL-COMMON-RULES.md
    +-- prompts/
    +-- templates/
```

**What is NOT in showroom/ after migration:**
- No `showroom/.claude-plugin/` — sub-plugin removed; agents are at top-level `agents/`
- No `showroom/agents/` — agents moved to top-level
- No `showroom/skills/` directory — all showroom skills deleted (Andrew's domain)
- No scaffold agents

## Development Skill Integration Model

The `development` skill is the single entry point for all content and automation work.

### Scaffold check (Skill tool)

development SKILL.md invokes `rhdp-publishing-house:config-reviewer` via Skill tool as Step 1. If FAIL, offers `rhdp-publishing-house:config-helper` via Skill tool. config-helper and config-reviewer skip pre-flight/workflow check since the development skill already runs pre-flight before the scaffold gate.

### Writer procedure (agent + human-in-the-loop)

writer.md spawns the agent via Task tool with `subagent_type`. The agent receives all context via prompt — no file reads at spawn time.

```
Task tool:
  subagent_type: rhdp-publishing-house:module-writing-helper
  prompt: |
    TARGET_FILE: <path to .adoc file>
    FILE_TYPE: module
    FULL_SPEC: <JSON built from spec.yaml + design.md + module outline>
    LAB_TYPE: <ocp|rhel|vm|ai>
    CONTENT_TYPE: <workshop|demo>
    REPO_PATH: <absolute repo path>
```

One agent per module, run sequentially (each depends on the previous for story continuity). After write, reviewer runs automatically (mandatory). Author reviews findings and says "module N is done" to mark complete.

### Editor procedure (agent)

editor.md spawns `rhdp-publishing-house:module-reviewer` via Task tool. After the agent returns, editor.md runs its own spec alignment checks (SA-1 through RS-2). For standalone re-reviews after manual edits.

### Automation procedure (skills)

automation.md dispatches to skills (not agents) — skills have their own pre-flight and workflow check:

```
automation_approach: ansible  -> Skill tool: rhdp-publishing-house:ansible-helper
automation_approach: gitops   -> Skill tool: rhdp-publishing-house:gitops-helper
automation_approach: both     -> ansible-helper first, then gitops-helper
```

No `ph_payload` sub-skill invocation anywhere. No agnosticv skills called. Development owns the content pipeline directly.

## Standard PH SKILL.md Skeleton

Every skill in this repo follows this structure. New skills and contributor skills MUST follow this skeleton.

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

## Steps 1-3 -- Pre-flight

Follow @rhdp-publishing-house/skills/common/pre-flight.md (Steps 1-3: verify project, read identity, check auth).

## Step 4 -- Workflow check

**4a.** Get workflow data -> extract workflow_id
**4b.** Get workflow state -> verify stage is `development` (STOP if not)
**4c.** Sync -> pull Central API data, commit if needed
**4d.** Handle rejections if any

## Step 5 -- Read project context

Read spec.yaml, design.md, and any other inputs specific to this skill.

## Dispatch / Main work

[Skill-specific logic here]
```

Note: config-helper and config-reviewer skip pre-flight/workflow check since they are invoked by the development skill which already runs pre-flight before the scaffold gate.

## What Stays in Marketplace

The following remain in `rhdp-skills-marketplace` and are NOT part of this migration:

- `agnosticv` plugin (catalog-builder, validator, all agents)
- `health` plugin
- `sandbox-cli` plugin
- All showroom skills (create-lab, create-demo, verify-content, blog-generate)
- All scaffold agents (Andrew's domain)

## Non-Goals

- Do NOT copy agnosticv into this repo — it stays in marketplace
- Do NOT call agnosticv skills from PH automation — automation uses ansible-helper and gitops-helper only
- Do NOT hardcode model IDs — all skills and agents inherit from session
- Do NOT mix scaffolding into PH development skills — scaffolding is Andrew's domain (RHDPCD-172)
- Do NOT include FTL in the workflow diagram — Mitesh owns FTL validation separately
