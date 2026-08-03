# PH Skills Migration Plan — Marketplace → Publishing House

**Date:** 2026-06-29
**Updated:** 2026-08-03
**Status:** Draft
**Author:** Prakhar Srivastava
**Scope:** Full copy of showroom and ftl plugins from rhdp-skills-marketplace into rhdp-publishing-house-skills. agnosticv stays in marketplace.
**Architecture:** See [PH Skills Consolidation — Architecture Spec](2026-06-29-ph-skills-consolidation-architecture.md) for plugin structure, naming reference, and integration model.

---

## Goal

After this migration:
- PH users install ONE repo (`rhdp-publishing-house-skills`) and get the full content lifecycle
- showroom and ftl plugins available without separate marketplace install
- Development skill calls showroom agents directly from spec data (no ph_payload sub-skill)
- agnosticv stays in marketplace (no change for agnosticv users)

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
    │   │   ├── writer.md            ← calls showroom:create-lab via ph_payload (TO BE UPDATED)
    │   │   ├── editor.md            ← calls showroom:verify-content (TO BE UPDATED)
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
| `showroom/` (entire directory) | Full copy from marketplace — all skills, agents, docs, prompts, templates |
| `ftl/` (entire directory) | Full copy from marketplace — all skills and agents |
| `skills/development/procedures/writer.md` | Update — read spec files directly, call showroom agents instead of sub-skill |
| `skills/development/procedures/editor.md` | Update — call showroom:module-reviewer agent directly |
| `.claude-plugin/plugin.json` | Bump version to 0.3.0 |
| agnosticv plugin | **NOT moving** — stays in marketplace |

---

## Andrew Jones Skills (RHDPCD-172 — NOT part of this migration)

Andrew delivers these independently into the showroom plugin after cutover:

| Skill | Role |
|---|---|
| `showroom:config-helper` | Scaffolds showroom structure: site.yml, ui-config.yml, tabs, nav |
| `showroom:config-reviewer` | Reviews showroom config quality |

---

## Development Skill Integration

The PH `development` skill is the single entry point for content and automation work. After migration, it calls showroom agents directly from project spec data — no intermediate sub-skill invocation via ph_payload.

### Three data sources for content generation

The writer procedure reads three complementary files from the author's project repo:

| File | Role |
|---|---|
| `publishing-house/spec.yaml` | Machine-readable metadata: environment (ocp_version, topology, cloud_provider), module list, audience, duration |
| `publishing-house/spec/design.md` | Human-readable narrative: overview, audience, prerequisites, products, business scenario — approved by author at intake |
| `publishing-house/spec/modules/module-NN-*.md` | Detailed step-by-step outline per module — primary input for writing .adoc content |

### Writer procedure (updated flow)

```
development:writer
  → reads publishing-house/spec.yaml          (env attributes, module list)
  → reads publishing-house/spec/design.md     (narrative context, audience, products)
  → reads publishing-house/spec/modules/NN    (detailed step outline for this module)
  → spawns showroom:file-generator agent with combined context
  → spawns showroom:module-reviewer agent on generated .adoc
  → commits result
```

Modules written sequentially — never in parallel.

---

## Pre-Migration Checklist

- [ ] Confirm marketplace repo is on latest main: `cd ~/work/code/rhdp-skills-marketplace && git pull`
- [ ] No in-progress PRs against showroom/ or ftl/ in marketplace
- [ ] Coordinate timing with Andrew Jones (RHDPCD-172) — his skills land after cutover

---

## Phase 1: Copy showroom and ftl plugins

**Branch:** `RHDPCD-120-showroom-ftl-migration`
**Repo:** `rhdp-publishing-house-skills`

### Step 1.1: Create branch

```bash
cd ~/work/code/rhdp-publishing-house-skills
git checkout -b RHDPCD-120-showroom-ftl-migration
```

### Step 1.2: Copy showroom plugin (full)

```bash
cp -r ~/work/code/rhdp-skills-marketplace/showroom/ ./showroom/

# Verify plugin.json preserved
cat showroom/.claude-plugin/plugin.json
# Expected: "name": "showroom"
```

### Step 1.3: Copy ftl plugin (full)

```bash
cp -r ~/work/code/rhdp-skills-marketplace/ftl/ ./ftl/

# Verify plugin.json preserved
cat ftl/.claude-plugin/plugin.json
# Expected: "name": "ftl"
```

### Step 1.4: Update development writer procedure

In `skills/development/procedures/writer.md`:
- Remove: invocation of `showroom:create-lab` via ph_payload
- Add: read `publishing-house/spec.yaml`, `publishing-house/spec/design.md`, `publishing-house/spec/modules/module-NN-*.md`
- Add: spawn `showroom:file-generator` agent with combined context from all three sources
- Add: spawn `showroom:module-reviewer` agent on each generated .adoc

### Step 1.5: Update development editor procedure

In `skills/development/procedures/editor.md`:
- Remove: invocation of `showroom:verify-content` via ph_payload
- Add: spawn `showroom:module-reviewer` agent directly on .adoc files

### Step 1.6: Bump PH plugin.json version

```json
{
  "name": "rhdp-publishing-house",
  "version": "0.3.0",
  "description": "AI-powered content lifecycle management for RHDP — includes showroom and ftl skill plugins"
}
```

### Step 1.7: Verify all plugins load

```bash
claude --plugin-dir ~/work/code/rhdp-publishing-house-skills

# Verify expected skills/agents are available:
# showroom:create-lab, showroom:verify-content, showroom:create-demo
# showroom:file-generator, showroom:module-reviewer, showroom:scaffold-checker
# ftl:content-reader, ftl:solve-writer, ftl:validate-writer, ftl:rhdp-lab-validator
```

### Step 1.8: Commit and push

```bash
git add showroom/ ftl/ skills/development/ .claude-plugin/plugin.json
git commit -m "feat: RHDPCD-120 add showroom + ftl plugins, update development skill integration"
git push -u origin RHDPCD-120-showroom-ftl-migration
```

---

## Phase 2: PR and Review

**PR title:** `[RHDPCD-120] Add showroom + ftl plugins to PH skills repo`

PR description should:
- Explain the direct-agent integration model (spec files → agent, no ph_payload sub-skill)
- List all directories added
- Include test evidence (Phase 1 Step 1.7 output)
- Note: agnosticv stays in marketplace

---

## Phase 3: Cutover Communication

After PR merges to main:

```
📢 Publishing House skills update

rhdp-publishing-house-skills now includes showroom and ftl plugins.
You no longer need rhdp-skills-marketplace for PH content work.

Update your install:
  cd ~/rhdp-publishing-house-skills && git pull

agnosticv is unchanged — still from rhdp-skills-marketplace.
```

---

## Phase 4: Notify Andrew Jones

Post on RHDPCD-172 after PR merges:

```
Andrew — final naming for your RHDPCD-172 skills:
  showroom:config-helper    — showroom scaffolding (site.yml, ui-config.yml, tabs, nav)
  showroom:config-reviewer  — showroom config quality review

These go into the showroom plugin at rhdp-publishing-house-skills/showroom/skills/
Build independently — do not reference existing scaffold work.
```

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `@showroom/` references in agents break (path resolution) | Low | High | Test after copy — plugin name is preserved so references should resolve |
| Andrew's skills land mid-migration | Medium | Low | Coordinate timing on RHDPCD-172 |
| User has both marketplace + PH installed (duplicate showroom plugin) | Medium | Medium | Document: remove rhdp-skills-marketplace from pluginDirectories after cutover |
| writer.md update breaks existing PH projects mid-intake | Low | Medium | writer.md only invoked during development phase — projects in intake/review are unaffected |
