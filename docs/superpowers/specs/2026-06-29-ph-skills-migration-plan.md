# PH Skills Migration Plan — Marketplace → Publishing House

**Date:** 2026-06-29
**Updated:** 2026-08-03
**Status:** Draft
**Author:** Prakhar Srivastava
**Scope:** Step-by-step plan to add ftl plugin, showroom content agents (renamed), and new gitops-helper + ansible-helper skills to rhdp-publishing-house-skills. agnosticv stays in marketplace.
**Architecture:** See [PH Skills Consolidation — Architecture Spec](2026-06-29-ph-skills-consolidation-architecture.md) for plugin structure, naming reference, and integration model.

---

## Goal

After this migration:
- PH users install ONE repo (`rhdp-publishing-house-skills`) and get the full content lifecycle
- ftl plugin available without separate marketplace install
- Development skill calls showroom content agents directly — no intermediate sub-skill
- New gitops-helper and ansible-helper skills available for automation phase
- agnosticv stays in marketplace (no change for agnosticv users)

---

## Scope Summary

| Component | Action | New name |
|---|---|---|
| ftl plugin | Copy from marketplace — full copy | unchanged |
| `showroom:file-generator` agent | Copy + rename | `showroom:module-writing-helper` |
| `showroom:module-reviewer` agent | Copy + rename | `showroom:module-review-helper` |
| `showroom/docs/SKILL-COMMON-RULES.md` | Copy — AsciiDoc rules used by both agents | unchanged |
| `gitops-helper` skill | Create new (RHDPCD-111) | `rhdp-publishing-house:gitops-helper` |
| `ansible-helper` skill | Create new (RHDPCD-110) | `rhdp-publishing-house:ansible-helper` |
| agnosticv plugin | **NOT moving** — stays in marketplace | — |
| showroom skills | **NOT moving** — development absorbs directly | — |
| showroom scaffold/config agents | **NOT moving** — Andrew Jones owns (RHDPCD-172) | `showroom:config-helper`, `showroom:config-reviewer` |

---

## Andrew Jones Skills (RHDPCD-172 — NOT part of this migration)

Andrew delivers these independently after cutover:

| Skill | Role |
|---|---|
| `showroom:config-helper` | Scaffolds showroom structure: site.yml, ui-config.yml, tabs, nav |
| `showroom:config-reviewer` | Reviews showroom config quality |

---

## Development Skill Integration

The PH `development` skill is the single entry point for content and automation work. It calls agents directly — no `ph_payload` sub-skill invocation.

### Writer procedure (content authoring)

Development's `writer.md` spawns `showroom:module-writing-helper` directly:

```
development:writer
  → spawns showroom:module-writing-helper (writes one .adoc module)
  → spawns showroom:module-review-helper (reviews generated .adoc)
  → commits result
```

Modules are written sequentially — never in parallel. Each module depends on the previous one for narrative continuity and nav.adoc ordering.

### Automation procedure

Development's `automation.md` calls:
- `rhdp-publishing-house:gitops-helper` — for GitOps (Helm + ArgoCD) automation authoring
- `rhdp-publishing-house:ansible-helper` — for Ansible automation authoring
- `agnosticv:catalog-builder` (from marketplace) — for AgnosticV catalog creation

---

## Pre-Migration Checklist

Before starting:
- [ ] No in-progress PRs against showroom/agents/ or ftl/ in marketplace
- [ ] Coordinate timing with Andrew Jones (RHDPCD-172) — his showroom:config-helper and showroom:config-reviewer land independently
- [ ] ftl current version documented: `cat ~/work/code/rhdp-skills-marketplace/ftl/.claude-plugin/plugin.json`

---

## Phase 1: Add Content Agents and FTL

**Branch:** `RHDPCD-120-content-agents-and-ftl`
**Repo:** `rhdp-publishing-house-skills`

### Step 1.1: Copy and rename showroom content agents

```bash
cd ~/work/code/rhdp-publishing-house-skills

mkdir -p agents/
# Copy and rename
cp ~/work/code/rhdp-skills-marketplace/showroom/agents/file-generator.md agents/module-writing-helper.md
cp ~/work/code/rhdp-skills-marketplace/showroom/agents/module-reviewer.md agents/module-review-helper.md

# Copy AsciiDoc rules reference
mkdir -p docs/showroom/
cp ~/work/code/rhdp-skills-marketplace/showroom/docs/SKILL-COMMON-RULES.md docs/showroom/
```

Update frontmatter in each agent file:
- `module-writing-helper.md` → update `description:` to reflect new name
- `module-review-helper.md` → update `description:` to reflect new name

Update any `@showroom/docs/` references in the agent files to `@rhdp-publishing-house/docs/showroom/`.

### Step 1.2: Copy ftl plugin

```bash
cp -r ~/work/code/rhdp-skills-marketplace/ftl/ ./ftl/

# Verify
cat ftl/.claude-plugin/plugin.json
# Expected: "name": "ftl"
```

### Step 1.3: Update development writer procedure

In `skills/development/procedures/writer.md`, replace any `showroom:create-lab` or `showroom:lab-writing-helper` invocations with direct agent calls:

- Remove: invocation of showroom skill via ph_payload
- Add: direct spawn of `showroom:module-writing-helper` agent with spec data
- Add: direct spawn of `showroom:module-review-helper` agent on each generated file

### Step 1.4: Update development editor procedure

In `skills/development/procedures/editor.md`, replace any showroom skill invocations with direct `showroom:module-review-helper` agent calls.

### Step 1.5: Update PH plugin.json

```json
{
  "name": "rhdp-publishing-house",
  "version": "0.3.0",
  "description": "AI-powered content lifecycle management for RHDP — includes ftl skill plugin",
  "bundledPlugins": ["ftl"]
}
```

### Step 1.6: Verify all plugins load

```bash
claude --plugin-dir ~/work/code/rhdp-publishing-house-skills

# Verify expected skills:
# /rhdp-publishing-house:orchestrator
# /rhdp-publishing-house:intake
# /rhdp-publishing-house:development
# /ftl:content-reader
# /ftl:solve-writer
# /ftl:validate-writer
# /ftl:rhdp-lab-validator
```

---

## Phase 2: Add New Automation Skills

**Jira:** RHDPCD-111 (gitops-helper), RHDPCD-110 (ansible-helper)

### Step 2.1: Create gitops-helper skill

Create `skills/gitops-helper/SKILL.md` — tracked in RHDPCD-111.

### Step 2.2: Create ansible-helper skill

Create `skills/ansible-helper/SKILL.md` — tracked in RHDPCD-110.

### Step 2.3: Wire automation procedure

Update `skills/development/procedures/automation.md` to dispatch to `gitops-helper` or `ansible-helper` based on the automation approach in `spec.yaml`.

---

## Phase 3: PR and Review

**PR title:** `[RHDPCD-120] Add ftl plugin, showroom content agents, and automation skills`

PR description should:
- Explain the direct-agent integration model (no ph_payload sub-skill)
- Document agent renames: file-generator → module-writing-helper, module-reviewer → module-review-helper
- List all new files added
- Include test evidence (Phase 1 Step 1.6 output)
- Note: agnosticv stays in marketplace

---

## Phase 4: Notify Andrew Jones

After PR merges, post on RHDPCD-172 with the final skill namespace map:

```
Andrew — final naming for your RHDPCD-172 skills:
  showroom:config-helper    — showroom scaffolding (site.yml, ui-config.yml, tabs, nav)
  showroom:config-reviewer  — showroom config quality review

Content agents (now in PH repo, not showroom plugin):
  showroom:module-writing-helper  — writes AsciiDoc modules
  showroom:module-review-helper   — reviews AsciiDoc content

Your skills go into the showroom plugin at rhdp-publishing-house-skills/showroom/
Build config-helper and config-reviewer independently — do not reference existing scaffold work.
```

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Agent `@` reference paths break after copy | Medium | High | Verify and update all `@showroom/docs/` refs in agent files to `@rhdp-publishing-house/docs/showroom/` |
| Andrew's skills land mid-migration | Medium | Low | Coordinate timing on RHDPCD-172 |
| FTL plugin has undocumented marketplace dependencies | Low | Medium | Read ftl plugin.json and agent files before copying |
| User still has marketplace showroom in pluginDirectories | Medium | Low | Agents are not skills — no name collision risk |
