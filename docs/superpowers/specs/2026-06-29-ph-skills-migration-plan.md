# PH Skills Migration Plan — Marketplace → Publishing House

**Date:** 2026-06-29
**Updated:** 2026-07-08
**Status:** Draft
**Author:** Prakhar Srivastava
**Scope:** Step-by-step plan to migrate showroom, agnosticv, and ftl plugins from rhdp-skills-marketplace into rhdp-publishing-house-skills. Covers pre-migration skill renames, transition period, backward compatibility, and marketplace cleanup.
**Architecture:** See [PH Skills Consolidation — Architecture Spec](2026-06-29-ph-skills-consolidation-architecture.md) for plugin structure, naming reference, and dual-format agent design.

---

## Goal

After this migration:
- PH users install ONE repo (`rhdp-publishing-house-skills`) and get all skills
- `rhdp-skills-marketplace` continues to serve `health` and `sandbox-cli` only
- showroom, agnosticv, ftl frozen in marketplace (no new features there)
- All future skill development for these 3 plugins happens in `rhdp-publishing-house-skills`

---

## PH Integration — How Showroom Skills Fit In the Pipeline

> **Ground truth:** This section is derived directly from reading `skills/orchestrator/SKILL.md`, `skills/writer/SKILL.md`, `skills/editor/SKILL.md`, and `skills/automation/SKILL.md` in `rhdp-publishing-house-skills`. Nothing here is speculative.

### Full Lifecycle

```
Intake → Vetting ⇄ Spec Refinement → Approval → Writing ↔ Automation → Editing → Code Review ↔ Security Review → E2E Testing → Final Review → Ready for Publishing
```

All phases are required. Central enforces every gate — the orchestrator calls `ph_request_gate()` and waits for Central's verdict before proceeding. After every gate, the orchestrator stops and waits for the user to confirm — no auto-advancing.

### The Approval Gate

The approval gate falls **between Spec Refinement and Writing**. Central runs a spec quality reviewer against the design spec and module outlines. If approved, both Writing and Automation phases become active simultaneously — they can run in parallel. If rejected, Central returns specific reasons and the author returns to spec refinement.

Gate call: `ph_request_gate(repo_url, branch, target_phase="approval", requested_by=email)`

### After Approval: Writing Phase → showroom:lab-writing-helper

Source: `skills/writer/SKILL.md`

The PH writer skill wraps `showroom:lab-writing-helper` (formerly `create-lab`). It **cannot write AsciiDoc directly** — every `.adoc` file must be produced by the showroom skill.

**Invocation method:** ph_payload headless mode only. No interactive questions.

**First module (`mode: new`):**
```yaml
showroom:lab-writing-helper content/
ph_payload:
  target_dir: content/modules/ROOT/pages/
  mode: new
  spec:
    lab_name: <from design.md>
    audience: <from design.md>
    learning_objectives: <from module outline>
    business_scenario: <from design.md problem statement>
    duration: <from module outline>
    module_outline: |
      <full module outline detailed steps>
    env:
      ocp_version: <from manifest>
      attributes: {user, password, openshift_console_url, ...}
```

`mode: new` triggers scaffold creation: `site.yml`, `ui-config.yml`, `nav.adoc`. These are only created on the first module call.

**Subsequent modules (`mode: continue`):**
Same payload with `mode: continue` and `previous_module: <filename>` for narrative continuity.

**Modules are written sequentially — never in parallel.** Each module depends on the previous one for `--continue` context and `nav.adoc` ordering. Concurrent writes would cause conflicts.

**Return value (JSON):**
```json
{
  "files_created": ["03-module-01-pipelines.adoc"],
  "nav_updated": true,
  "quality": {"critical": 0, "high": 0, "warnings": 2},
  "warnings": ["..."]
}
```

The writer verifies scaffold was created (first module only), checks nav.adoc includes the new module, and updates the manifest with `status: drafted` and `content_file` path.

**For demos:** same flow, calls `showroom:demo-writing-helper` (formerly `create-demo`) instead.

### After Approval: Automation Phase (Parallel with Writing)

Source: `skills/automation/SKILL.md`

Automation runs in parallel with writing. It does NOT call showroom skills — it wraps `agnosticv:catalog-builder` and `agnosticv:validator`.

**Sub-phases:**
- **7a — Requirements:** Reads drafted content or module outlines, generates `publishing-house/spec/automation-manifest.yaml`. Human-approved gate.
- **7b — Catalog item:** Calls `agnosticv:catalog-builder` (Mode 1: Full Catalog Creation), then immediately validates with `agnosticv:validator` (Level 2). Skipped for `self_published` projects.
- **7c — Automation code:** Writes Ansible roles or GitOps Helm charts from approved manifest.
- **7d — Testing gate:** Human deploys and tests on a real environment. The agent does not deploy or test itself.

### After Writing gate → Editing Phase → showroom:lab-review-helper

Source: `skills/editor/SKILL.md`

The PH editor skill wraps `showroom:lab-review-helper` (formerly `verify-content`) and adds PH-specific spec alignment checks on top.

**Invocation method:** ph_payload, with `format` derived from `manifest.project.showroom_type`.

**What the editor does:**

1. **Reads `manifest.project.showroom_type`** to determine lab format, then invokes `showroom:lab-review-helper` via ph_payload with `format` set:
   - `showroom_type: classic` (or empty/unset) → `format: classic`
   - `showroom_type: zero_touch` → `format: project_zero`

2. **`showroom:lab-review-helper` routes internally** based on `format`:
   - `classic` → spawns `showroom:scaffold-checker` (Haiku) + `showroom:module-reviewer` (Sonnet, one per .adoc file, in parallel)
   - `project_zero` → spawns `showroom:zero-scaffold-checker` (Haiku) + `showroom:zero-content-reviewer` (Sonnet, in parallel)
   - Returns consolidated findings JSON

3. **Runs PH-specific spec alignment checks** that lab-review-helper cannot perform (it has no knowledge of the PH spec):
   - **SA-1:** Outline coverage — every section in the module outline should have corresponding content
   - **SA-2:** Learning objectives match — each objective needs hands-on content
   - **SA-3:** Duration alignment — content depth vs. estimated duration
   - **SA-4:** Cross-module consistency — terminology, prerequisites, story continuity (multi-module reviews only)
   - **RS-1:** Product name accuracy — no unofficial abbreviations without prior expansion
   - **RS-2:** Version consistency — mixed versions or hardcoded values that should use `{attribute}` placeholders

4. **Produces review report** at `publishing-house/reviews/editing-review-module-NN.md`

5. **Submits results to Central** via `ph_submit_results(repo_url, branch, phase, result_type, results, submitted_by)` — Central stores these for gate decisions.

After fixes, module status advances from `drafted` → `approved` in the manifest.

### ph_payload: The Interface Between PH and Showroom/Agnosticv Skills

`ph_payload` is the headless invocation contract. When PH passes a `ph_payload` block:
- Showroom skills skip ALL interactive questions
- Skills run deterministically from the payload data
- Results return as structured JSON only (no conversational prose)

This is the only way PH calls showroom and agnosticv skills. Direct interactive invocation is not used from within PH phases.

### Autonomy Modes

The orchestrator supports three autonomy levels (set in `project.autonomy`):
- **guided (default):** Every output shown to user for approval before proceeding
- **semi:** Auto-fix medium/low issues, pause for critical/high
- **full:** Auto-fix all clear issues, pause only for judgment calls

Autonomy affects writer, editor, and automation behavior — not gate enforcement. Gates are always Central-enforced regardless of autonomy level.

### Single Subagent Per Phase Rule

The orchestrator dispatches each skill ONCE per phase and stores the agent ID. Every subsequent user message in that phase goes to the SAME agent via `SendMessage` — not a new dispatch. This preserves conversational context across multi-turn phases (especially critical for intake where the user's story builds across many turns).

### Impact of Skill Rename on PH Integration

After the migration:

| PH skill | Was calling | Will call |
|---|---|---|
| `rhdp-publishing-house:writer` | `showroom:create-lab` | `showroom:lab-writing-helper` |
| `rhdp-publishing-house:writer` | `showroom:create-demo` | `showroom:demo-writing-helper` |
| `rhdp-publishing-house:editor` | `showroom:verify-content` | `showroom:lab-review-helper` |

These call sites are updated in Phase 1 Step 1.6 (atomic with the plugin copy). The ph_payload interface itself does not change — only the skill name in the invocation changes.

The `lab-review-helper` ph_payload adds two new fields after this migration:

```yaml
ph_payload:
  format: classic | project_zero   # derived from manifest.project.showroom_type
  content_path: content/modules/ROOT/pages/
  ...
```

**PH editor derives `format` from `manifest.project.showroom_type`** (set at intake, committed to git):
- `showroom_type: classic` (or empty/unset) → `format: classic`
- `showroom_type: zero_touch` → `format: project_zero`

The PH editor always sets `format` explicitly from the manifest. The `classic` default exists only for standalone invocations outside PH. When PH is the caller, the manifest is the source of truth — `showroom:format-detector` is not spawned.

---

## Pre-Migration Checklist

Before starting:
- [ ] agnosticv v2.15.0 is merged to marketplace main ✅ (done 2026-06-29)
- [ ] showroom v2.14.0 is merged to marketplace main ✅ (done 2026-05-31)
- [ ] ftl current version documented (run `cat ~/work/code/rhdp-skills-marketplace/ftl/.claude-plugin/plugin.json`)
- [ ] **Phase 0 complete and merged to marketplace main** — skill renames must land before Phase 1 copy
- [ ] Confirm no in-progress PRs against showroom/, agnosticv/, or ftl/ in marketplace
- [ ] PH plugin owner briefed — consolidation changes the repo structure
- [ ] Coordinate timing with Andrew Jones (RHDPCD-172) — his `create-showroom` lands in showroom plugin separately
- [ ] Decide cutover date (suggestion: after current Sprint ends)

---

## Phase 0: Pre-Migration Showroom Prep (marketplace, BEFORE copying)

**Branch:** `feature/showroom-rename-and-cleanup`
**Repo:** `rhdp-skills-marketplace`

This phase must complete and merge to marketplace main BEFORE Phase 1 begins. The copy in Phase 1 picks up the already-renamed skills.

### Step 0.1: Rename showroom skills (ATOMIC — all in one commit)

Rename skill directories:

```bash
cd ~/work/code/rhdp-skills-marketplace/showroom/skills/

mv create-lab/     lab-writing-helper/
mv verify-content/ lab-review-helper/
mv create-demo/    demo-writing-helper/
mv blog-generate/  blog-writing-helper/
```

Update `name:` field in each SKILL.md frontmatter:
- `lab-writing-helper/SKILL.md` → `name: showroom:lab-writing-helper`
- `lab-review-helper/SKILL.md` → `name: showroom:lab-review-helper`
- `demo-writing-helper/SKILL.md` → `name: showroom:demo-writing-helper`
- `blog-writing-helper/SKILL.md` → `name: showroom:blog-writing-helper`

Update `description:` trigger phrases in each SKILL.md to match new names.

Verify no old names remain:
```bash
grep -r "name: showroom:create-lab\|name: showroom:verify-content\|name: showroom:create-demo\|name: showroom:blog-generate" . --include="*.md"
# Expected: no output
```

### Step 0.2: Remove Phase 2.5 from lab-writing-helper

In `lab-writing-helper/SKILL.md`, remove the entire Phase 2.5 block:

```
### Phase 2.5 — Showroom Setup (NEW lab only)
...
Create/update `site.yml` and `ui-config.yml` in repo root.
```

Replace with a single cross-reference line:

```markdown
### Phase 2.5 — Platform Setup

For platform setup (tabs, navigation, site.yml, ui-config.yml), run `showroom:create-showroom` first.
This skill handles lab guide content only.
```

### Step 0.3: Remove showroom-scaffold.md from lab-writing-helper

```bash
rm showroom/skills/lab-writing-helper/references/showroom-scaffold.md
```

This reference belongs to `showroom:create-showroom` (RHDPCD-172, Andrew Jones). He builds it independently — do not seed his work.

### Step 0.4: Add zero-touch agents for dual-format review

In `showroom/agents/`, create three agent files. These are complete implementations — see `rhdp-skills-marketplace` for the actual agent content already committed:

- **`format-detector.md`** (Haiku) — standalone fallback only. NOT used when ph_payload is present. Detects classic vs zero-touch from repo structure (checks for `setup-automation/` and `runtime-automation/main.yml`).
- **`zero-scaffold-checker.md`** (Haiku) — validates ZT scaffold: `runtime-automation/`, `setup-automation/`, `config/`, per-module `solve.yml` + `validation.yml`, shell scripts.
- **`zero-content-reviewer.md`** (Sonnet) — runs classic AsciiDoc checks + ZT automation pairing (checks `runtime-automation/<slug>/` exists per module).

### Step 0.5: Update lab-review-helper to use dual-format architecture

In `lab-review-helper/SKILL.md`, add Phase 0 (format routing) before spawning agents:

```markdown
## Phase 0 — Determine Lab Format

**When called via ph_payload (PH editor):**
Read `format` field from ph_payload — set by PH editor from `manifest.project.showroom_type`:
- `showroom_type: classic` (or empty/unset) → `format: classic`
- `showroom_type: zero_touch` → `format: project_zero`
Manifest is the source of truth. Do NOT spawn format-detector.

**When called standalone (no ph_payload):**
Spawn `showroom:format-detector` (Haiku) to detect format from repo structure.
Returns `"classic"` or `"project_zero"`.

Both paths then route to:
- `format: classic` → scaffold-checker (Haiku) + module-reviewer (Sonnet) in parallel
- `format: project_zero` → zero-scaffold-checker (Haiku) + zero-content-reviewer (Sonnet) in parallel
```

### Step 0.6: Bump showroom plugin version to v2.15.0

In `showroom/.claude-plugin/plugin.json`:
- Bump version: `2.14.0` → `2.15.0`
- Update description to reflect new skill names

### Step 0.7: Verify showroom plugin after rename

```bash
claude --plugin-dir ~/work/code/rhdp-skills-marketplace/showroom

# Expected:
# /showroom:lab-writing-helper
# /showroom:lab-review-helper
# /showroom:demo-writing-helper
# /showroom:blog-writing-helper
```

---

## Phase 1: Set Up Multi-Plugin Structure

**Branch:** `feature/consolidate-marketplace-plugins`
**Repo:** `rhdp-publishing-house-skills` (the skills-plugin submodule)

> **Prerequisite:** Phase 0 must be merged to marketplace main before running these steps.

### Step 1.1: Copy showroom plugin

```bash
cd ~/work/code/rhdp-publishing-house/skills-plugin

# Copy showroom plugin directory structure (already renamed in Phase 0)
cp -r ~/work/code/rhdp-skills-marketplace/showroom/ ./showroom/

# Verify plugin.json name and version
cat showroom/.claude-plugin/plugin.json
# Expected: "name": "showroom", "version": "2.15.0"
```

### Step 1.2: Copy agnosticv plugin

```bash
cp -r ~/work/code/rhdp-skills-marketplace/agnosticv/ ./agnosticv/

# Verify
cat agnosticv/.claude-plugin/plugin.json
# Expected: "name": "agnosticv"
```

### Step 1.3: Copy ftl plugin

```bash
cp -r ~/work/code/rhdp-skills-marketplace/ftl/ ./ftl/

# Verify
cat ftl/.claude-plugin/plugin.json
# Expected: "name": "ftl"
```

### Step 1.4: Update PH plugin.json with new version

```json
{
  "name": "rhdp-publishing-house",
  "version": "0.2.0",
  "description": "AI-powered content lifecycle management for RHDP — includes showroom, agnosticv, and ftl skill plugins",
  "author": {
    "name": "RHDP Team",
    "url": "https://github.com/rhpds/rhdp-publishing-house"
  },
  "bundledPlugins": [
    "showroom",
    "agnosticv",
    "ftl"
  ]
}
```

Note: `bundledPlugins` is a documentation field only — Claude Code doesn't read it. It's for human reference.

### Step 1.5: Add version gate to PH orchestrator

In `skills/orchestrator/SKILL.md`, add at the very top (before any routing):

```markdown
## Session Start — Plugin Version Check

Before doing anything, verify all required plugins are installed at the correct version.

Read each plugin's version:
- `<skills-dir>/.claude-plugin/plugin.json` → rhdp-publishing-house version
- `<skills-dir>/showroom/.claude-plugin/plugin.json` → showroom version
- `<skills-dir>/agnosticv/.claude-plugin/plugin.json` → agnosticv version
- `<skills-dir>/ftl/.claude-plugin/plugin.json` → ftl version

Minimum required versions:
- rhdp-publishing-house: 0.2.0
- showroom: 2.15.0
- agnosticv: 2.15.0
- ftl: 2.14.0

If any plugin is missing or below minimum:
→ Print: "❌ [plugin name] not found / below minimum version. Update: cd ~/rhdp-publishing-house-skills && git pull"
→ STOP — do not continue the session.

If all plugins are present and at correct versions → continue as normal.
```

### Step 1.6: Update all PH SKILL.md call sites (ATOMIC — same commit as copy)

These files reference old showroom skill names and must be updated:

| File | Old call | New call |
|------|----------|----------|
| `skills/writer/SKILL.md` | `showroom:create-lab` | `showroom:lab-writing-helper` |
| `skills/writer/SKILL.md` | `showroom:create-demo` | `showroom:demo-writing-helper` |
| `skills/editor/SKILL.md` | `showroom:verify-content` | `showroom:lab-review-helper` |
| `skills/writer/references/writing-standards.md` | `showroom:create-lab`, `showroom:create-demo` | update to new names |
| `skills/editor/references/editing-checklist.md` | `showroom:verify-content` | update to new name |
| `skills/automation/references/automation-patterns.md` | any showroom refs | update |

Also update `skills/editor/SKILL.md` to read `manifest.project.showroom_type` and pass `format` in the ph_payload when invoking `showroom:lab-review-helper`.

After updating, verify no old names remain:
```bash
grep -r "showroom:create-lab\|showroom:verify-content\|showroom:create-demo\|showroom:blog-generate" . --include="*.md" | grep -v ".git"
# Expected: no output
```

### Step 1.7: Update README.md

New install instructions and plugin table:

```markdown
## Installation

git clone git@github.com:rhpds/rhdp-publishing-house-skills.git ~/rhdp-publishing-house-skills

Add to Claude Code settings (~/.claude/settings.json):
  "pluginDirectories": ["~/rhdp-publishing-house-skills"]

This installs 4 plugins in one step: rhdp-publishing-house, showroom, agnosticv, ftl.

Updating: cd ~/rhdp-publishing-house-skills && git pull

## Included Plugins

| Plugin | Skills | Purpose |
|--------|--------|---------|
| rhdp-publishing-house | orchestrator, intake, writer, editor, automation, worklog | PH content lifecycle |
| showroom | lab-writing-helper, lab-review-helper, demo-writing-helper, blog-writing-helper, create-showroom* | Showroom content authoring |
| agnosticv | catalog-builder, validator | AgnosticV catalog management |
| ftl | content-reader, solve-writer, validate-writer, rhdp-lab-validator | FTL E2E automation |

*create-showroom is owned by Andrew Jones (RHDPCD-172) — platform plumbing, added independently.
```

### Step 1.8: Verify all 4 plugins load

```bash
claude --plugin-dir ~/work/code/rhdp-publishing-house/skills-plugin

# Verify all expected skills are available:
# /showroom:lab-writing-helper
# /showroom:lab-review-helper
# /showroom:demo-writing-helper
# /showroom:blog-writing-helper
# /agnosticv:catalog-builder
# /agnosticv:validator
# /ftl:content-reader
# etc.
```

---

## Phase 2: PR and Review

**PR target:** `rhdp-publishing-house-skills` repo (the published skills repo)
**PR title:** `[RHDPCD-120] Consolidate showroom + agnosticv + ftl into PH skills plugin (v0.2.0)`

PR description should:
- Explain the multi-plugin architecture
- List all new directories added
- Document showroom skill renames (BREAKING: users must update any personal scripts)
- Include test evidence (Phase 1 Step 1.8 output)

Reviewers:
- PH platform owner — PH plugin structure review
- AgnosticV skill domain reviewer — agnosticv skills review

---

## Phase 3: Cutover Communication

After PR merges to main:

### User communication (Slack + README)

```
📢 Publishing House skills update

rhdp-publishing-house-skills now includes showroom, agnosticv, and ftl plugins.
You no longer need a separate rhdp-skills-marketplace install for PH.

⚠️ BREAKING: showroom skill names have changed:
  create-lab       → lab-writing-helper
  verify-content   → lab-review-helper
  create-demo      → demo-writing-helper
  blog-generate    → blog-writing-helper

If you reference these names in personal scripts or notes, update them.

If you have BOTH installed, remove rhdp-skills-marketplace from your
Claude Code pluginDirectories to avoid plugin name conflicts.

Update your install:
  cd ~/rhdp-publishing-house-skills && git pull
```

### What users need to do
1. Pull the latest `rhdp-publishing-house-skills` → `git pull`
2. Remove `rhdp-skills-marketplace` from their Claude Code `pluginDirectories`
3. Update any personal scripts or workflows referencing old skill names
4. Test: run `/rhdp-publishing-house` and verify session starts without version gate errors

### What stays the same
- Plugin name `showroom:` unchanged — only skill names within the plugin changed
- agnosticv and ftl skill syntax unchanged: `agnosticv:catalog-builder`, `ftl:solve-writer`, etc.
- All existing PH projects continue to work (PH SKILL.md call sites updated in Step 1.6)
- PH manifest, MCP tools, portal — all unchanged

---

## Phase 4: Freeze Marketplace Plugins

After cutover is confirmed stable (suggest: 2 weeks after Phase 3):

### In rhdp-skills-marketplace:
1. Add deprecation notice to `showroom/README.md`, `agnosticv/README.md`, `ftl/README.md`:
   ```
   ⚠️  This plugin has moved to rhdp-publishing-house-skills.
   No new features will be added here. See: github.com/rhpds/rhdp-publishing-house-skills
   ```

2. Pin versions in marketplace (no further bumps to these plugins):
   - showroom: frozen at v2.15.x (post-rename)
   - agnosticv: frozen at v2.15.x
   - ftl: frozen at current version

3. Marketplace `README.md` updated to redirect PH users to `rhdp-publishing-house-skills`

4. Marketplace `install.sh` updated to warn PH users

### What stays in marketplace (active, not frozen):
- `health/` plugin
- `sandbox-cli/` plugin

---

## Phase 5: Future FTL Alignment

FTL is moved in this migration but its role in PH is evolving:
- Today: FTL writes solve.yml/validate.yml (automation phase 7c)
- Graphify showed: no direct PH→FTL edges yet (FTL runs on content PH produces, not called by PH skills directly)
- Future: When PH automation skill starts directly invoking `ftl:rhdp-lab-validator`, the call path will be in-repo and version-safe

Track this as a separate spec once PH automation phase 7c→7d integration is designed.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| User has both marketplace + PH installed → plugin name conflict | High | Medium | Clear docs + orchestrator warning at session start |
| User has scripts referencing old skill names (create-lab, verify-content) | High | Low | Phase 3 BREAKING communication + CHANGELOG entry |
| Phase 0 rename PR and Phase 1 consolidation PR merged out of order | Medium | High | Phase 1 PR description must state Phase 0 as prerequisite |
| PR reviewer requests structural changes mid-migration | Medium | Medium | Pre-align with PH platform owner before opening PR |
| FTL plugin has undocumented dependencies on marketplace infra | Low | Medium | Read ftl plugin.json and SKILL.md before copying |
| agnosticv PRs now go to a different repo | Medium | Low | Update CODEOWNERS, brief domain reviewers |
| Claude Code plugin resolution order with same-named plugins in sub-dirs | Low | High | Test Phase 1 Step 1.8 carefully before any cutover |
| Andrew's create-showroom lands in showroom plugin while migration is in progress | Medium | Low | Coordinate timing with Andrew on RHDPCD-172 |
