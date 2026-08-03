# PH Skills Migration Plan — Marketplace → Publishing House

**Date:** 2026-06-29
**Updated:** 2026-08-03
**Status:** Draft
**Author:** Prakhar Srivastava
**Scope:** Step-by-step plan to add ftl plugin, showroom content agents, and new gitops-helper + ansible-helper skills to rhdp-publishing-house-skills. agnosticv stays in marketplace.
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

| Component | Action | Name |
|---|---|---|
| ftl plugin | Copy from marketplace — full copy | unchanged |
| `showroom:file-generator` agent | Copy + rename | `showroom:module-writing-helper` |
| `showroom:module-reviewer` agent | Copy — name unchanged | `showroom:module-reviewer` |
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

### spec.yaml is the source of truth

`publishing-house/spec.yaml` in the author's project repo contains all data needed for content generation. The development skill reads it directly and passes fields to agents — no separate payload construction interface.

Key fields consumed from spec.yaml:
- `spec.title` → lab name
- `spec.learning_objectives` → objectives passed to each module agent
- `spec.modules[]` → id, title, duration_min per module
- `approval_checklist.content.module_summaries[]` → per-module design overview
- `spec.environment` → ocp_version, topology, cloud_provider, cluster_type
- `spec.audience`, `spec.duration_hours`
- `project.content_type`, `project.showroom_type`

### Writer procedure (content authoring)

Development's `writer.md` reads spec.yaml and spawns `showroom:module-writing-helper` per module:

```
development:writer
  → reads publishing-house/spec.yaml
  → for each module in spec.modules:
      → spawns showroom:module-writing-helper with spec fields
      → spawns showroom:module-reviewer on generated .adoc
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

### Step 1.1: Copy showroom content agents

```bash
cd ~/work/code/rhdp-publishing-house-skills

mkdir -p agents/
# Rename file-generator → module-writing-helper
cp ~/work/code/rhdp-skills-marketplace/showroom/agents/file-generator.md agents/module-writing-helper.md
# module-reviewer keeps its name
cp ~/work/code/rhdp-skills-marketplace/showroom/agents/module-reviewer.md agents/module-reviewer.md

# Copy AsciiDoc rules reference
mkdir -p docs/showroom/
cp ~/work/code/rhdp-skills-marketplace/showroom/docs/SKILL-COMMON-RULES.md docs/showroom/
```

Update `module-writing-helper.md` frontmatter `description:` to reflect new name.

Update any `@showroom/docs/` references in both agent files to `@rhdp-publishing-house/docs/showroom/`.

### Step 1.2: Copy ftl plugin

```bash
cp -r ~/work/code/rhdp-skills-marketplace/ftl/ ./ftl/

# Verify
cat ftl/.claude-plugin/plugin.json
# Expected: "name": "ftl"
```

### Step 1.3: Update development writer procedure

In `skills/development/procedures/writer.md`:

- **Remove:** any invocation of a showroom sub-skill via ph_payload
- **Add:** read `publishing-house/spec.yaml` to extract spec fields
- **Add:** direct spawn of `showroom:module-writing-helper` agent, passing spec fields (title, learning_objectives, module outline, module summary, environment, audience, content_type, showroom_type)
- **Add:** direct spawn of `showroom:module-reviewer` agent on each generated .adoc file

The agent receives data directly from spec.yaml — no intermediate payload format needed.

### Step 1.4: Update development editor procedure

In `skills/development/procedures/editor.md`, replace any showroom skill invocations with direct `showroom:module-reviewer` agent calls, passing the .adoc file path and spec context.

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

Update `skills/development/procedures/automation.md` to dispatch to `gitops-helper` or `ansible-helper` based on `spec.yaml` automation approach field.

---

## Phase 3: PR and Review

**PR title:** `[RHDPCD-120] Add ftl plugin, showroom content agents, and automation skills`

PR description should:
- Explain the direct-agent integration model (spec.yaml → agent, no ph_payload sub-skill)
- Document agent rename: file-generator → module-writing-helper (module-reviewer name unchanged)
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

Content agents (now in PH repo):
  showroom:module-writing-helper  — writes AsciiDoc modules (was file-generator)
  showroom:module-reviewer        — reviews AsciiDoc content (name unchanged)

Your skills go into the showroom plugin at rhdp-publishing-house-skills/showroom/
Build config-helper and config-reviewer independently.
```

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Agent `@` reference paths break after copy | Medium | High | Verify and update all `@showroom/docs/` refs to `@rhdp-publishing-house/docs/showroom/` |
| Andrew's skills land mid-migration | Medium | Low | Coordinate timing on RHDPCD-172 |
| FTL plugin has undocumented marketplace dependencies | Low | Medium | Read ftl plugin.json and agent files before copying |
| User still has marketplace showroom in pluginDirectories | Medium | Low | Agents are not skills — no name collision risk |
