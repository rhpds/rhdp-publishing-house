# PH Skills Migration Plan — Marketplace → Publishing House

**Date:** 2026-06-29
**Updated:** 2026-08-04
**Status:** Draft
**Author:** Prakhar Srivastava
**Scope:** Copy showroom content agents and ftl plugin from rhdp-skills-marketplace into rhdp-publishing-house-skills. Delete scaffold agents/skills after copy. agnosticv stays in marketplace and is NOT called by PH automation.
**Architecture:** See [PH Skills Consolidation — Architecture Spec](2026-06-29-ph-skills-consolidation-architecture.md) for plugin structure, naming reference, workflow diagram, and integration model.

---

## Goal

After this migration:
- PH users install ONE repo (`rhdp-publishing-house-skills`) and get the full content lifecycle
- showroom content agents (`module-writing-helper`, `module-reviewer`) available without marketplace
- ftl plugin available without marketplace (Mitesh owns FTL validation)
- Development skill calls showroom agents directly from spec data (no ph_payload sub-skill)
- Scaffold check uses `showroom:config-reviewer` (Andrew, RHDPCD-172) — not file existence
- Module status tracking enforces sequential writing with plan-confirm flow
- agnosticv stays in marketplace — NOT called from PH automation
- Automation dispatches to `ansible-helper` (RHDPCD-110) and `gitops-helper` (RHDPCD-111) only

---

## Current State of rhdp-publishing-house-skills (pre-migration)

```
rhdp-publishing-house-skills/
├── .claude-plugin/plugin.json       ← name: "rhdp-publishing-house", version: "0.2.0"
└── skills/
    ├── common/pre-flight.md
    ├── orchestrator/SKILL.md + references/
    ├── intake/SKILL.md + procedures/ + references/
    ├── development/
    │   ├── SKILL.md
    │   ├── procedures/
    │   │   ├── writer.md            ← calls showroom:create-lab via ph_payload (TO BE REPLACED)
    │   │   ├── editor.md            ← calls showroom:verify-content (TO BE REPLACED)
    │   │   └── automation.md
    │   └── references/
    │       ├── writing-standards.md
    │       ├── editing-checklist.md
    │       ├── automation-patterns.md
    │       ├── automation-manifest-format.md
    │       ├── ansible-automation-guide.md
    │       └── gitops-automation-guide.md
    └── worklog/SKILL.md
```

Nothing from showroom or ftl exists in this repo yet.

---

## Scope Summary

| Component | Action |
|---|---|
| `showroom/` (directory copy) | Full copy from marketplace, then delete scaffold agents + all showroom skills |
| `ftl/` (directory copy) | Full copy from marketplace — unchanged (Mitesh owns) |
| `showroom:file-generator` agent | Rename to `showroom:module-writing-helper` |
| Scaffold agents (`scaffold-checker`, `score-aggregator`, `doc-writer`, `diagram-generator`, `format-detector`, `zero-scaffold-checker`, `zero-content-reviewer`) | Delete after copy |
| `showroom/skills/` (all showroom skills) | Delete after copy — Andrew's domain |
| `skills/development/SKILL.md` | Update — add scaffold gate (config-reviewer) + module status validation |
| `skills/development/procedures/writer.md` | Replace — read spec files, plan-confirm flow, spawn module-writing-helper, status tracking |
| `skills/development/procedures/editor.md` | Replace — spawn module-reviewer directly, SA-1→RS-2 checks |
| `skills/development/procedures/automation.md` | Update — dispatch to ansible-helper + gitops-helper only (no agnosticv) |
| `.claude-plugin/plugin.json` | Bump version to 0.3.0 |
| All frontmatter `model:` lines (19 files) | Remove — skills/agents inherit from session |
| Double frontmatter in PH skills (4 files) | Fix — merge into single block |
| agnosticv plugin | **NOT moving, NOT called** — stays in marketplace |

---

## Andrew Jones Skills (RHDPCD-172 — NOT part of this migration)

Andrew delivers `showroom:config-helper` and `showroom:config-reviewer` independently after RHDPCD-120 cutover. See [How Andrew Contributes His Skills](#how-andrew-contributes-his-skills) below for the exact contribution pattern.

After Andrew's PR lands, the development skill's scaffold check (Step 1) will invoke `showroom:config-reviewer` automatically and offer `showroom:config-helper` if the user asks for help.

---

## Development Skill Integration

The PH `development` skill is the single entry point for content and automation work. After migration, it calls showroom agents directly from project spec data — no intermediate sub-skill invocation via ph_payload.

### Scaffold check (Step 1 — prerequisite)

1. Run `showroom:config-reviewer` automatically — no user prompt needed for the check
2. If PASS → proceed to module status validation
3. If FAIL → report issues to user
   - User says "help me" / "fix it" → invoke `showroom:config-helper` (Andrew, RHDPCD-172)
   - User says "I'll handle it" → STOP

### Module status validation (Step 1b)

Before dispatching to any procedure:
- Read `spec.yaml` module statuses
- Any `in_progress`? → warn user, ask to continue or mark complete
- All `complete` and user says "write"? → suggest "edit" instead
- Otherwise → proceed to dispatch

### Three data sources for content generation

The writer procedure reads three complementary files from the author's project repo:

| File | Role |
|---|---|
| `publishing-house/spec.yaml` | Machine-readable metadata: environment (ocp_version, topology, cloud_provider), module list, audience, duration, module statuses |
| `publishing-house/spec/design.md` | Human-readable narrative: overview, audience, prerequisites, products, business scenario — approved by author at intake |
| `publishing-house/spec/modules/module-NN-*.md` | Detailed step-by-step outline per module — primary input for writing .adoc content |

### Writer procedure (updated flow)

```
development:writer
  → check module status in spec.yaml (sequential enforcement)
  → read spec.yaml + design.md + module outline (3 data sources)
  → present plan to user → wait for approval
  → spawn showroom:module-writing-helper agent (Task tool)
  → update module status: in_progress → complete
  → commit result
```

Modules written sequentially — never in parallel. Module N blocked until 1..N-1 all complete.

### Editor procedure (updated flow)

```
development:editor
  → spawn showroom:module-reviewer agent (Task tool)
  → run SA-1→RS-2 spec alignment checks
  → produce review report
  → fix loop based on autonomy level
```

### Automation procedure

```
development:automation
  → dispatch to ansible-helper (Skill tool) — FUTURE, RHDPCD-110
  → dispatch to gitops-helper (Skill tool) — FUTURE, RHDPCD-111
```

No agnosticv skills called. No ph_payload.

---

## Pre-Migration Checklist

- [ ] Confirm marketplace repo is on latest main: `cd ~/work/code/rhdp-skills-marketplace && git pull`
- [ ] Get latest marketplace tag — copy from tag, not HEAD
- [ ] No in-progress PRs against showroom/ or ftl/ in marketplace
- [ ] Coordinate timing with Andrew Jones (RHDPCD-172) — his skills land after cutover

---

## Phase 1: Copy and Clean (RHDPCD-120)

**Branch:** `RHDPCD-120-showroom-ftl-migration`
**Repo:** `rhdp-publishing-house-skills`
**Execution:** 5-agent orchestration — see `~/work/RHDPCD-120-phase1-prompt.md` for full details

### Step 1.1: Create branch from master

### Step 1.2: Copy showroom plugin (full directory) from latest marketplace tag

### Step 1.3: Delete scaffold agents and ALL showroom skills

After copying, delete:
- All showroom skills (`showroom/skills/` — entire directory)
- Scaffold agents: `scaffold-checker`, `score-aggregator`, `doc-writer`, `diagram-generator`, `format-detector`, `zero-scaffold-checker`, `zero-content-reviewer`

What remains in `showroom/`:
```
showroom/
├── .claude-plugin/plugin.json      ← name: "showroom"
├── agents/
│   ├── module-writing-helper.md    ← renamed from file-generator (CONTENT)
│   └── module-reviewer.md          ← unchanged (CONTENT)
├── docs/SKILL-COMMON-RULES.md
├── prompts/                        ← content-related only
└── templates/
```

### Step 1.4: Copy ftl plugin (full directory) — unchanged

### Step 1.5: Rename file-generator → module-writing-helper

### Step 1.6: Remove all hardcoded `model:` lines (19 files)

### Step 1.7: Fix double frontmatter in 4 PH skills

### Step 1.8: Replace writer.md — spec-based, plan-confirm flow, status tracking

### Step 1.9: Replace editor.md — direct module-reviewer, spec alignment checks

### Step 1.10: Bump PH plugin.json to 0.3.0

### Step 1.11: Generate workflow diagram in references/

### Step 1.12: Do NOT push — all commits stay local for review

---

## Phase 2: PR and Review

**PR title:** `[RHDPCD-120] Add showroom content agents + ftl plugin, update development skill integration`

PR description should:
- Explain the direct-agent integration model (spec files → agent, no ph_payload sub-skill)
- Note scaffold agents and showroom skills deleted (Andrew's domain)
- List what remains in showroom/ (2 agents only)
- Include the workflow diagram
- Note: agnosticv NOT called, automation uses ansible-helper + gitops-helper only
- Note: FTL copied as-is, Mitesh owns

---

## Phase 3: Cutover Communication

After PR merges to main:

```
Publishing House skills update

rhdp-publishing-house-skills now includes showroom content agents and ftl plugin.
You no longer need rhdp-skills-marketplace for PH content work.

Update your install:
  cd ~/rhdp-publishing-house-skills && git pull

Changes:
- writer.md now reads spec files directly and spawns showroom:module-writing-helper
- editor.md now spawns showroom:module-reviewer directly
- Module status tracking enforces sequential writing
- Scaffold check uses showroom:config-reviewer (landing with RHDPCD-172)

agnosticv is unchanged — still from rhdp-skills-marketplace.
FTL validation — Mitesh owns, included in this repo.
```

---

## Phase 4: Notify Andrew Jones

Post on RHDPCD-172 after PR merges with the contribution pattern below.

---

## How Andrew Contributes His Skills

After RHDPCD-120 cutover, Andrew adds `showroom:config-helper` and `showroom:config-reviewer` via PR against `rhdp-publishing-house-skills`. The showroom plugin is already in the repo — he creates `showroom/skills/` and slots his skills into it.

### Target directory structure

```
rhdp-publishing-house-skills/
└── showroom/
    └── skills/
        ├── config-helper/        ← Andrew adds this (RHDPCD-172)
        │   └── SKILL.md
        └── config-reviewer/      ← Andrew adds this (RHDPCD-172)
            └── SKILL.md
```

Note: `showroom/skills/` does NOT exist after RHDPCD-120 migration (all marketplace showroom skills were deleted). Andrew creates it fresh.

### SKILL.md frontmatter pattern

`showroom/skills/config-helper/SKILL.md`:
```yaml
---
name: showroom:config-helper
description: This skill should be used when the user asks to "set up showroom", "configure showroom tabs", "create site.yml", "set up ui-config.yml", or "scaffold the showroom structure".
---
```

`showroom/skills/config-reviewer/SKILL.md`:
```yaml
---
name: showroom:config-reviewer
description: This skill should be used when the user asks to "review my showroom config", "check site.yml", "validate ui-config.yml", or "verify my showroom setup".
---
```

### plugin.json version bump

After adding his skills, Andrew bumps `showroom/.claude-plugin/plugin.json` version (minor bump):
```json
{
  "name": "showroom",
  "version": "2.15.0"
}
```

### PR process

1. Fork or branch `rhdp-publishing-house-skills` → branch name: `RHDPCD-172-config-helper-config-reviewer`
2. Create `showroom/skills/config-helper/SKILL.md`
3. Create `showroom/skills/config-reviewer/SKILL.md`
4. Bump `showroom/.claude-plugin/plugin.json` version
5. PR title: `[RHDPCD-172] Add showroom:config-helper and showroom:config-reviewer`
6. Reviewer: Prakhar Srivastava

### Constraints for Andrew

- **Do NOT** reference or copy existing scaffold work from marketplace — build config-helper from scratch for the new architecture
- **Do NOT** create a new repo — skills go into the existing `showroom/` directory in this repo
- **Do NOT** modify `showroom/.claude-plugin/plugin.json` `name` field — it must stay `"showroom"`
- **Do NOT** add `model:` lines — skills inherit from user session
- Agent files (`.md` in `showroom/agents/`) are owned by Prakhar — do not modify unless discussed

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `@showroom/` references in agents break (path resolution) | Low | High | Test after copy — plugin name is preserved so references should resolve |
| Andrew's skills land mid-migration | Medium | Low | Coordinate timing on RHDPCD-172 |
| User has both marketplace + PH installed (duplicate showroom plugin) | Medium | Medium | Document: remove rhdp-skills-marketplace from pluginDirectories after cutover |
| writer.md update breaks existing PH projects mid-intake | Low | Medium | writer.md only invoked during development phase — projects in intake/review are unaffected |
| Andrew modifies existing agents or scaffold files | Low | Medium | Clear constraints documented above — Prakhar reviews PR |
| config-reviewer not available yet at cutover | High | Low | Scaffold check gracefully skips if config-reviewer skill doesn't exist — user manually validates |
