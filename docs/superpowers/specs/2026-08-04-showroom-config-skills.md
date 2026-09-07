# Showroom Config Skills — Spec

**Date:** 2026-08-04
**Status:** Draft
**Author:** Andrew Jones
**Ticket:** RHDPCD-172
**Related:** [PH Skills Migration Plan](2026-06-29-ph-skills-migration-plan.md) (RHDPCD-120), [PH Skills Architecture](2026-06-29-ph-skills-consolidation-architecture.md)

---

## Context

The showroom platform has two content modes (`type: showroom` and `type: zerotouch`), two UI themes (`rhdp_showroom_theme` and `nookbag-bundle`), and three lab patterns (Open, Guided, ZT Guided). Choosing the wrong combination — or misconfiguring the files that wire them together — is the most common source of broken Showroom deployments.

Today, config setup is handled ad-hoc: authors copy a template, edit YAML by hand, and discover mistakes only after deploying. The `showroom:create-lab` skill in the marketplace bundles scaffolding with content generation, mixing two concerns. The [architecture spec](2026-06-29-ph-skills-consolidation-architecture.md) separates them: PH development skills own content writing; these two new skills own configuration scaffolding and validation.

These skills go into `showroom/skills/` within `rhdp-publishing-house-skills` (the `showroom` plugin namespace). They resolve as `showroom:config-helper` and `showroom:config-reviewer`. They work for **any** showroom content repo — standalone or PH-managed.

---

## Dependency: RHDPCD-120

RHDPCD-120 copies the `showroom/` plugin from `rhdp-skills-marketplace` into `rhdp-publishing-house-skills`, then **deletes all showroom skills and scaffold agents** — only the two content agents (`module-writing-helper`, `module-reviewer`) remain. After RHDPCD-120 merges, `showroom/skills/` does not exist. Andrew creates it fresh for config-helper and config-reviewer.

## Integration with Development Skill

Per the [updated architecture spec](2026-06-29-ph-skills-consolidation-architecture.md), scaffold validation is **Step 1 inside the development phase** — not a separate phase:

1. Development skill runs `showroom:config-reviewer` automatically at the start of every session
2. If PASS — proceed to module status validation and dispatch
3. If FAIL — report issues to the user
   - User says "help me" / "fix it" — invoke `showroom:config-helper`
   - User says "I'll handle it" — STOP

---

## Two Content Modes

Set via the `type` field in `ui-config.yml` ([Confluence: Showroom - For Content Developers](https://redhat.atlassian.net/wiki/spaces/RHPDS/pages/410124758/Showroom+-+For+Content+Developers)). This is the first decision for any showroom repo.

| Aspect | `type: showroom` | `type: zerotouch` |
|--------|-------------------|---------------------|
| Navigation | Free-form — users browse via TOC and next/prev links from the Antora theme | Guided linear — sequential via Next/Previous buttons provided by Nookbag |
| Nookbag role | Simple iframe wrapper — displays Antora content alongside tab services | Full lab orchestrator — progress bar, module tracking, Next/Previous, Solve, Skip, and Exit buttons |
| Antora UI theme | `rhdp_showroom_theme` | `nookbag-bundle` |
| Lab automation | Not applicable | Optional solve/validate per module via the automation runner |
| Best for | Self-paced workshops, demos, reference environments | Instructor-led or structured labs requiring sequential completion and validation |

The theme **must** match the content mode. Using `rhdp_showroom_theme` with `type: zerotouch` (or vice versa) produces duplicate or missing navigation controls.

---

## Two UI Themes

These are separate projects with different capabilities.

**rhdp_showroom_theme** ([rhpds/rhdp_showroom_theme](https://github.com/rhpds/rhdp_showroom_theme)) — for `type: showroom`:
- Standard split-pane: content left, tabs right
- TOC, next/prev page links in the content pane
- Navbar branding via `site.keys.navbar_logo` in site.yml
- Page-links dropdown and user display via antora.yml attributes
- No module tracking, no solve/validate buttons
- Bundle URL: `https://github.com/rhpds/rhdp_showroom_theme/releases/download/<version>/ui-bundle.zip`

**nookbag-bundle** ([rhpds/nookbag-bundle](https://github.com/rhpds/nookbag-bundle)) — for `type: zerotouch`:
- Minimal Antora theme — Nookbag handles all navigation externally
- Progress bar, module tracking, Next/Previous, Solve, Skip, Exit buttons
- `antora:` block in ui-config.yml with module name/label mappings
- Requires `runtime-automation/` directory with solve.yml/validate.yml per module
- Dev-mode extension support (injected at build time by the container, not in the content repo)
- Bundle URL: `https://github.com/rhpds/nookbag-bundle/releases/download/<version>/ui-bundle.zip`

---

## Three Patterns

| Pattern | `type` | Theme | ui-config extras | Automation dirs |
|---------|--------|-------|------------------|-----------------|
| **Open** | `showroom` | rhdp_showroom_theme | `view_switcher` + `tabs` | None (qa-automation only) |
| **Guided** (AgD v2) | `zerotouch` | nookbag-bundle | `antora:` module labels + `tabs` | `runtime-automation/` (setup, solve, validate per module) |
| **ZT Guided** | `zerotouch` | nookbag-bundle | `antora:` module labels + `tabs` | `runtime-automation/` + `setup-automation/` + `config/` |

Tab syntax differs by infrastructure type:
- **AgD (OCP/VM):** terminal tab uses `path: /wetty` + `port: 443`
- **ZT:** terminal tab uses `url: /wetty` (no port — ZT networking differs)

---

## Directory Structure

```
rhdp-publishing-house-skills/
└── showroom/
    └── skills/
        ├── config-helper/
        │   ├── SKILL.md
        │   └── references/
        │       ├── showroom-patterns.md
        │       └── config-files.md
        └── config-reviewer/
            ├── SKILL.md
            └── references/
                └── validation-rules.md
```

---

## Skill 1: config-helper (RHDPCD-172)

### Responsibility

Helps authors set up and configure showroom content repos — choosing the content mode, generating config files, configuring tabs, and creating automation directory skeletons.

### SKILL.md frontmatter

```yaml
---
name: showroom:config-helper
description: This skill should be used when the user asks to "set up showroom", "configure showroom tabs", "create site.yml", "set up ui-config.yml", or "scaffold the showroom structure".
context: main
---
```

### Procedure

**Step 1 — Detect repo context:**
- Check for `publishing-house/spec.yaml` → PH project
- Check for `_scaffolds/` directory → un-scaffolded PH project
- Check for existing `site.yml`, `ui-config.yml` → already configured
- Check for `content/antora.yml` → Antora component present

**Step 2 — Route based on state:**
- PH + `_scaffolds/` exists → read `project.showroom_type` from spec.yaml, map to scaffold pattern, call `scaffold.py`, then adjust/verify
- No config files exist → full setup flow (Step 3)
- Config files exist → modification flow (Step 4)

**PH scaffold pattern mapping** (from `project.showroom_type` in `publishing-house/spec.yaml`):

| `project.showroom_type` | scaffold.py `--pattern` | Notes |
|--------------------------|-------------------------|-------|
| `classic` | `agd-open` | Self-paced, rhdp_showroom_theme |
| `zero_touch` | `zt-guided` | Guided linear, nookbag-bundle, Project Zero infra |
| `guided` | `agd-guided` | Not currently offered during intake |
| Empty/unset | Fall back to asking the user | |

**Step 3 — Full setup flow (new repo):**
- Ask: content mode (showroom or zerotouch), infrastructure type (OCP, VM, or ZT)
- Determine pattern from answers
- Generate `site.yml` (select bundle, register extensions, set title)
- Generate `ui-config.yml` (select format, configure tabs based on infra type)
- Configure `content/antora.yml` (title, nav, default attributes)
- Create `content/modules/ROOT/nav.adoc` and `pages/index.adoc` stub
- If zerotouch: create `runtime-automation/` skeleton with setup/solve/validate stubs
- If ZT: also create `config/` (instances, networks, firewall) and `setup-automation/`

**Step 4 — Modification flow (existing repo):**
- Read existing config, detect current pattern
- Understand what user wants to change (add tab, adjust width, change title, etc.)
- Apply changes preserving format consistency
- Run config-reviewer validation after changes

### References

- `references/showroom-patterns.md` — pattern catalog with example configs
- `references/config-files.md` — site.yml, ui-config.yml, antora.yml reference; tab properties and variable substitution (`${DOMAIN}`, `${GUID}`); common tab patterns (wetty, OCP console, split terminal, external URL, placeholder)

---

## Skill 2: config-reviewer (RHDPCD-172)

### Responsibility

Validates showroom config quality and consistency — checks each config file against known rules and detects cross-file mismatches (wrong theme for the content mode, missing automation dirs, etc.).

### SKILL.md frontmatter

```yaml
---
name: showroom:config-reviewer
description: This skill should be used when the user asks to "review my showroom config", "check site.yml", "validate ui-config.yml", or "verify my showroom setup".
context: main
---
```

### Procedure

**Step 1 — Read config files:** `site.yml`, `ui-config.yml`, `content/antora.yml`, `content/modules/ROOT/nav.adoc`

**Step 2 — Detect pattern** from config clues (bundle URL, ui-config format, presence of `runtime-automation/`)

**Step 3 — Per-file validation:**

site.yml (S-rules):

| Rule | Check | Severity |
|------|-------|----------|
| S-1 | Bundle URL is a known valid theme | CRITICAL |
| S-2 | `start_page` matches antora.yml component name | HIGH |
| S-3 | Content source `start_path: content` | HIGH |
| S-4 | Mermaid and tabs extensions registered | MEDIUM |
| S-5 | Output dir is `./www` | MEDIUM |
| S-6 | Title is not a placeholder | LOW |
| S-7 | rhdp_showroom_theme: `navbar_logo` is a known value (if set) | LOW |
| S-8 | nookbag-bundle: dev-mode extension NOT registered in site.yml (injected by container) | MEDIUM |

ui-config.yml (U-rules):

| Rule | Check | Severity |
|------|-------|----------|
| U-1 | Format matches content mode (`type: showroom` or `antora:` block) | CRITICAL |
| U-2 | At least one tab defined | HIGH |
| U-3 | `name` present on all tabs | HIGH |
| U-4 | Tab has `url` or `path` (not both, not neither) | HIGH |
| U-5 | No placeholder tabs remain | LOW |
| U-6 | Variable substitution uses `${VAR}` not `{VAR}` | MEDIUM |
| U-7 | Zerotouch: `antora.modules` entries match nav.adoc pages | HIGH |

antora.yml (A-rules):

| Rule | Check | Severity |
|------|-------|----------|
| A-1 | `name` is set | HIGH |
| A-2 | `title` is not a placeholder | MEDIUM |
| A-3 | `nav` path is correct | HIGH |
| A-4 | Common attributes have defaults (`guid`, `ssh_user`, `ssh_password`) | MEDIUM |
| A-5 | `experimental: true` set (enables UI macros) | MEDIUM |
| A-6 | `page-pagination: true` set | LOW |

nav.adoc (N-rules):

| Rule | Check | Severity |
|------|-------|----------|
| N-1 | All pages in `pages/` listed in nav (warn on missing) | MEDIUM |
| N-2 | All xref targets exist as files | HIGH |
| N-3 | `index.adoc` is first entry | LOW |

**Step 4 — Cross-file validation (X-rules):**

| Rule | Check | Severity |
|------|-------|----------|
| X-1 | site.yml `start_page` component matches antora.yml `name` | HIGH |
| X-2 | Zerotouch ui-config `antora.modules` match page filenames | HIGH |
| X-3 | Zerotouch repos have `runtime-automation/` with solve.yml + validate.yml per module | HIGH |
| X-4 | Theme/mode consistency — rhdp_showroom_theme requires `type: showroom`; nookbag-bundle requires zerotouch format | CRITICAL |
| X-5 | ZT Guided repos have `config/` and `setup-automation/` directories | MEDIUM |
| X-6 | Tab terminal syntax matches infra type (AgD: `path`+`port`, ZT: `url`) | MEDIUM |

**Step 5 — Report** with severity (CRITICAL / HIGH / MEDIUM / LOW) and auto-fix capability flag

**Step 6 — Fix loop** — offer to fix issues, apply with user confirmation

---

## Constraints

- Do NOT reference or copy existing scaffold work from marketplace — build config-helper from scratch for the new architecture
- Do NOT modify `showroom/.claude-plugin/plugin.json` `name` field — must stay `"showroom"`
- Do NOT modify agent files in `showroom/agents/` — Prakhar owns those
- Do NOT add `model:` lines — skills inherit from the user's session
- These are showroom plugin skills (not PH skills) — they do not require PH pre-flight auth or workflow stage gating
- `showroom/skills/` is created fresh by this PR — it does not exist after RHDPCD-120 (all marketplace showroom skills are deleted)

---

## Contribution Pattern

### Repo and branch

- **Target repo:** `rhdp-publishing-house-skills` (not a new repo)
- **Branch:** `RHDPCD-172-config-helper-config-reviewer`

### What to create

```
showroom/skills/config-helper/
  ├── SKILL.md
  └── references/
      ├── showroom-patterns.md
      └── config-files.md

showroom/skills/config-reviewer/
  ├── SKILL.md
  └── references/
      └── validation-rules.md
```

### PR process

1. Branch from `main` (after RHDPCD-120 merges)
2. Add skill directories with SKILL.md + references
3. Bump `showroom/.claude-plugin/plugin.json` version (minor)
4. PR title: `[RHDPCD-172] Add showroom:config-helper and showroom:config-reviewer`
5. Reviewer: Prakhar Srivastava

---

## Reference Sources

1. **showroom-template repo** — 6 branches (`main`, `open-ocp`, `open-vm`, `guided-ocp`, `guided-vm`, `zt-guided`) as pattern reference implementations
2. **rhdp-publishing-house-template** — `_scaffolds/` directory (agd-open, agd-guided, zt-guided), `scaffold.py`
3. **Showroom docs** — [UI Configuration](https://rhpds.github.io/showroom_template_nookbag/modules/ui-config.html), [Content Repo](https://rhpds.github.io/showroom_template_nookbag/modules/content-repo.html), [User Data](https://rhpds.github.io/showroom_template_nookbag/modules/user-data.html)
4. **rhdp_showroom_theme** — [rhpds/rhdp_showroom_theme](https://github.com/rhpds/rhdp_showroom_theme) (navbar branding, page-links, user display)
5. **nookbag-bundle** — [rhpds/nookbag-bundle](https://github.com/rhpds/nookbag-bundle) (module navigation, solve/validate buttons)
6. **Confluence** — [Showroom - For Content Developers](https://redhat.atlassian.net/wiki/spaces/RHPDS/pages/410124758/Showroom+-+For+Content+Developers)
7. **Showroom Ansible collection** — [rhpds/showroom](https://github.com/rhpds/showroom) (deployment roles, variable injection)
8. **Real-world repos** — [rhads-ols-modernize](https://github.com/rhpds/rhads-ols-modernize-showroom), [openshift-days-ops](https://github.com/rhpds/openshift-days-ops-showroom)
9. **PH architecture spec** — [content vs scaffolding boundary](2026-06-29-ph-skills-consolidation-architecture.md)
