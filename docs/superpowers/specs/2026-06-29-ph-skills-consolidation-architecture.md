# PH Skills Consolidation — Architecture Spec

**Date:** 2026-06-29
**Updated:** 2026-07-08
**Status:** Draft
**Author:** Prakhar Srivastava
**Scope:** Consolidate showroom, agnosticv, and ftl plugins from rhdp-skills-marketplace into rhdp-publishing-house-skills as a multi-plugin package. Remove marketplace dependency for PH users.
**Migration Steps:** See [PH Skills Migration Plan](2026-06-29-ph-skills-migration-plan.md) for the step-by-step execution plan, phase ordering, and cutover communication.

---

## Complete Naming Reference

All final names after this migration. Single source of truth — do not derive from other sections.

### showroom Skills

| Final name | Was | Role |
|---|---|---|
| `showroom:lab-writing-helper` | `showroom:create-lab` | Lab AsciiDoc content authoring |
| `showroom:lab-review-helper` | `showroom:verify-content` | Content quality review (classic + zero-touch) |
| `showroom:demo-writing-helper` | `showroom:create-demo` | Demo/presenter content authoring |
| `showroom:blog-writing-helper` | `showroom:blog-generate` | Blog content generation |
| `showroom:create-showroom` | (new — Andrew Jones, RHDPCD-172) | Platform plumbing — **NOT part of this migration** |

### showroom Agents — Existing (unchanged)

| Agent | Model | Role |
|---|---|---|
| `showroom:file-generator` | Sonnet | Generates one AsciiDoc file per invocation |
| `showroom:module-reviewer` | Sonnet | Reviews AsciiDoc quality (classic path) |
| `showroom:scaffold-checker` | Haiku | Validates site.yml, ui-config.yml, antora.yml (classic path) |
| `showroom:score-aggregator` | Sonnet | Aggregates review scores across modules |
| `showroom:doc-writer` | Sonnet | Updates GitHub Pages documentation |
| `showroom:diagram-generator` | — | Generates architecture diagrams |

### showroom Agents — NEW (zero-touch support)

| Agent | Model | Role |
|---|---|---|
| `showroom:format-detector` | Haiku | Standalone fallback: detects classic vs zero-touch from repo structure. NOT used in PH pipeline — PH reads `manifest.project.showroom_type` directly. |
| `showroom:zero-scaffold-checker` | Haiku | Validates ZT scaffold: `runtime-automation/`, `setup-automation/`, `config/`, per-module `solve.yml` + `validation.yml` |
| `showroom:zero-content-reviewer` | Sonnet | Classic AsciiDoc checks + ZT automation pairing (checks `runtime-automation/<slug>/` exists per module) |

### agnosticv Skills (unchanged in this migration)

| Name | Role |
|---|---|
| `agnosticv:catalog-builder` | Creates AgnosticV catalog items — currently monolithic v2.1.0, planned refactor to domain-specialist agents (see below) |
| `agnosticv:validator` | Validates AgnosticV catalog |

### agnosticv Agents — v2.15.0 (validator specialists, unchanged)

| Agent | Role |
|---|---|
| `agnosticv:schema-checker` | Validates YAML schema and file structure |
| `agnosticv:workload-checker` | Validates workload configuration and references |
| `agnosticv:ocp-infra-checker` | Validates OCP infrastructure requirements |
| `agnosticv:sandbox-checker` | Validates sandbox pool configuration |
| `agnosticv:metadata-checker` | Validates catalog metadata fields |
| `agnosticv:config-writer` | Writes catalog configuration files (common.yaml, dev.yaml) |
| `agnosticv:description-writer` | Writes catalog item descriptions |
| `agnosticv:workflow-reviewer` | Reviews catalog workflow configuration |

### agnosticv Agents — PLANNED (catalog-builder domain refactor)

> catalog-builder is currently a 1,264-line monolith. The next major agnosticv evolution refactors it into domain-specialist agents — each branch gets deep context without diluting the others. ZT support lands here.

| Agent | Model | Role |
|---|---|---|
| `agnosticv:ocp-infra-agent` | Sonnet | OCP cluster catalog creation (cloud_provider, sandbox pools, OcpSandbox) |
| `agnosticv:vm-infra-agent` | Sonnet | VM/RHEL catalog creation (cloud-vms-base, CNV, RHEL workloads) |
| `agnosticv:sandbox-api-agent` | Sonnet | Sandbox API patterns (sandbox-api.yaml includes, access control) |
| `agnosticv:metadata-agent` | Haiku | Shared metadata: labels, reportingLabels, lifespan, anarchy namespace |
| `agnosticv:zt-catalog-agent` | Sonnet | Zero-Touch catalog creation (ZT-ANSIBLE + ZT-RHEL branches, platform declaration, ZT includes, assetGroup: ZEROTOUCH, workshopLabUiRedirect) |

### ftl Agents (unchanged)

| Agent | Role |
|---|---|
| `ftl:content-reader` | Reads AsciiDoc lab content, classifies steps for FTL processing |
| `ftl:solve-writer` | Writes solve.yml Ansible playbooks from content analysis |
| `ftl:validate-writer` | Writes validate.yml Ansible playbooks from content analysis |
| `ftl:env-connector` | Connects to live RHDP showroom, runs and validates full solve/validate cycle |
| `ftl:rhdp-lab-validator` | E2E lab validator — orchestrates full solve/validate test against live lab |

---

## agnosticv: catalog-builder Domain-Specialist Refactor Plan

**Current state:** `agnosticv:catalog-builder` (v2.1.0) is a 1,264-line monolithic skill with 4 modes and complex infra branching. It runs on Sonnet, executes linearly, and uses only `agnosticv:workflow-reviewer` at the final step. It has no ph_payload or headless mode.

**Problem:** Context bleeding when the PH automation agent calls catalog-builder conversationally. Deep infrastructure knowledge for OCP, VM, and ZT domains competes in a single context window — any domain gets diluted.

**Target architecture (next major evolution after this migration):**

```
agnosticv:catalog-builder (thin orchestrator — Sonnet)
│
├── Step 0: Detect deployment type
│     ├── rhdp_published → route to infra branch
│     └── self_published → route to metadata-agent only
│
├── Infra branch (based on cloud_provider / env_type):
│     ├── OCP (cloud_provider: ec2/aws/azure/openshift) → agnosticv:ocp-infra-agent
│     ├── VM/RHEL (cloud_provider: openshift_cnv, env: cloud-vms-base) → agnosticv:vm-infra-agent
│     ├── Sandbox API pattern → agnosticv:sandbox-api-agent
│     └── Zero-Touch (platform: ZT-ANSIBLE | ZT-RHEL) → agnosticv:zt-catalog-agent
│
└── Always spawned in parallel with infra branch:
      └── agnosticv:metadata-agent (labels, reportingLabels, lifespan, anarchy namespace)
```

**ZT domain specifics (`agnosticv:zt-catalog-agent`):**

From `zt-ansiblebu-agnosticv` and `zt-rhelbu-agnosticv`:
- Injects `platform: ZT-ANSIBLE` or `ZT-RHEL`
- Auto-adds BU-specific includes (ansible control plane, sandbox-api, catalog icon, secrets)
- Sets `__meta__.catalog.reportingLabels.assetGroup: ZEROTOUCH`
- Sets `__meta__.catalog.labels.Provider: Ansible_BU` or `ZeroTouchRHELBU`
- For ZT-RHEL: sets `cloud_provider: openshift_cnv`, `env_type: zero-touch-base-rhel`
- For ZT-ANSIBLE: sets dynamic anarchy namespace pattern
- For ZT-RHEL: sets hardcoded `anarchy.namespace: babylon-anarchy-3`
- Adds `workshopLabUiRedirect: true` (Ansible BU) or access-restriction-devs-only (RHEL BU)

**This refactor is NOT part of the current showroom migration PR.** It is the next agnosticv evolution, tracked separately.

---

## Problem

Today PH users need two separate plugin installs:
1. `rhdp-publishing-house-skills` — PH orchestration skills
2. `rhdp-skills-marketplace` — showroom, agnosticv, ftl, and internal tools

PH skills hard-depend on marketplace skills by name (`showroom:lab-writing-helper`, `agnosticv:catalog-builder`). If a user installs PH without marketplace, they get silent failures during writer, editor, and automation phases. There is no version contract between the two repos — they can silently drift.

## Solution

Transform `rhdp-publishing-house-skills` into a **multi-plugin package** — a single git repo that hosts 4 independent Claude Code plugins. One `--plugin-dir` install gives users everything PH needs.

## Critical Constraint: Plugin Names Cannot Change

Claude Code resolves skill calls as `<plugin-name>:<skill-name>`. The plugin name comes from `.claude-plugin/plugin.json` → `"name"` field.

```
showroom plugin (name: "showroom")  →  showroom:lab-writing-helper  ✓
agnosticv plugin (name: "agnosticv") →  agnosticv:catalog-builder  ✓
```

If skills moved into the `rhdp-publishing-house` plugin namespace, ALL call sites in PH SKILL.md files would break. Therefore: **each plugin MUST retain its original name in its own plugin.json**.

Skill names WITHIN the showroom plugin have been renamed (see Showroom Skill Naming below). Plugin names are unchanged.

## Classic vs Zero-Touch Lab Structure

Understanding what makes a zero-touch lab different is required context for the dual-format review architecture.

| | Classic Showroom | Zero-Touch (Project Zero) |
|---|---|---|
| Content format | AsciiDoc in `content/modules/ROOT/pages/` | Same AsciiDoc — identical format |
| Scaffold | `site.yml`, `ui-config.yml`, `antora.yml` | Same scaffold files |
| Automation | None | `runtime-automation/` + `setup-automation/` |
| Infrastructure config | None | `config/` (instances.yaml, networks.yaml, firewall.yaml) |
| Per-module automation | None | `solve.yml` + `validation.yml` per `module-XX/` dir |
| Shell control scripts | None | `solve-control.sh`, `validation-control.sh` per module |
| Button placeholders in AsciiDoc | None | None — buttons injected at UI layer, not in content |
| Manifest field | `showroom_type: classic` | `showroom_type: zero_touch` |

**Reference repo for ZT structure:** `rhpds/zt-ans-bu-hashi-aap`

**ZT AgV reference repos:** `rhpds/zt-ansiblebu-agnosticv` (Ansible BU), `rhpds/zt-rhelbu-agnosticv` (RHEL BU)

**Zero-touch additional directories (not present in classic):**
```
runtime-automation/
  main.yml              ← root orchestrator (routes to module tasks)
  ansible.cfg
  inventory
  secrets.yaml
  module-01/
    solve.yml           ← Ansible solve playbook
    validation.yml      ← Ansible validation playbook (NOT validate.yml)
    solve-control.sh
    validation-control.sh
setup-automation/
  main.yml
  setup-control.sh
  setup-terraform.sh    ← environment setup (Terraform, vault, control plane)
config/
  instances.yaml        ← infrastructure configuration
  networks.yaml
  firewall.yaml
```

## Target Structure

```
rhdp-publishing-house-skills/           ← ONE repo, users clone once
├── .claude-plugin/
│   └── plugin.json                     ← name: "rhdp-publishing-house"
├── skills/                             ← PH orchestration skills
│   ├── orchestrator/SKILL.md
│   ├── intake/SKILL.md
│   ├── writer/SKILL.md                 ← calls showroom:lab-writing-helper
│   ├── editor/SKILL.md                 ← calls showroom:lab-review-helper
│   ├── automation/SKILL.md             ← calls agnosticv:catalog-builder
│   └── worklog/SKILL.md
│
├── showroom/                           ← NEW — copied from marketplace (post-rename)
│   ├── .claude-plugin/
│   │   └── plugin.json                 ← name: "showroom", version: "2.15.0"
│   ├── skills/
│   │   ├── lab-writing-helper/SKILL.md    ← was create-lab
│   │   ├── lab-review-helper/SKILL.md     ← was verify-content (dual-format: classic + zero-touch)
│   │   ├── demo-writing-helper/SKILL.md   ← was create-demo
│   │   └── blog-writing-helper/SKILL.md   ← was blog-generate
│   ├── agents/
│   │   ├── scaffold-checker.md            ← existing, classic path
│   │   ├── module-reviewer.md             ← existing, shared by classic path
│   │   ├── file-generator.md              ← existing
│   │   ├── score-aggregator.md            ← existing
│   │   ├── doc-writer.md                  ← existing
│   │   ├── format-detector.md             ← Haiku, standalone fallback only (PH reads manifest directly)
│   │   ├── zero-scaffold-checker.md       ← Haiku, zero-touch path: validates runtime-automation/, setup-automation/, config/
│   │   └── zero-content-reviewer.md       ← Sonnet, zero-touch path: classic checks + automation pairing
│   └── docs/                           ← reference files (writing guides, etc.)
│
│   Note: showroom:create-showroom (RHDPCD-172, Andrew Jones) is NOT part of this migration.
│   It will be added to this plugin independently after cutover.
│
├── agnosticv/                          ← NEW — copied from marketplace
│   ├── .claude-plugin/
│   │   └── plugin.json                 ← name: "agnosticv" (MUST keep this name)
│   ├── skills/
│   │   ├── catalog-builder/SKILL.md    ← monolith today; domain-specialist refactor is next evolution
│   │   └── validator/SKILL.md
│   ├── agents/                         ← 8 specialist agents (v2.15.0, validator path)
│   │   ├── schema-checker.md
│   │   ├── workload-checker.md
│   │   ├── ocp-infra-checker.md
│   │   ├── sandbox-checker.md
│   │   ├── metadata-checker.md
│   │   ├── config-writer.md
│   │   ├── description-writer.md
│   │   └── workflow-reviewer.md
│   └── docs/                           ← reference files (validator checks, shared context schema, etc.)
│
└── ftl/                                ← NEW — copied from marketplace
    ├── .claude-plugin/
    │   └── plugin.json                 ← name: "ftl" (MUST keep this name)
    ├── agents/                         ← all ftl components are agents
    │   ├── content-reader.md           ← ftl:content-reader
    │   ├── solve-writer.md             ← ftl:solve-writer
    │   ├── validate-writer.md          ← ftl:validate-writer
    │   ├── env-connector.md            ← ftl:env-connector
    │   └── rhdp-lab-validator/         ← ftl:rhdp-lab-validator
    └── docs/
```

## lab-review-helper: Dual-Format Architecture

`lab-review-helper` (formerly verify-content) supports both classic and zero-touch labs. The format is determined by the PH manifest — not by runtime repo sniffing.

```
showroom:lab-review-helper (orchestrator — Sonnet)
│
├── Phase 0: Read format from ph_payload.format
│             ├── Via PH: editor reads manifest.project.showroom_type → sets format in ph_payload
│             │           showroom_type: classic    → format: classic
│             │           showroom_type: zero_touch → format: project_zero
│             └── Standalone (no ph_payload): spawns showroom:format-detector (Haiku)
│                           checks for setup-automation/ and runtime-automation/main.yml
│
├── Classic path (parallel):
│     ├── showroom:scaffold-checker (Haiku)   ← checks site.yml, ui-config.yml, antora.yml
│     └── showroom:module-reviewer (Sonnet)   ← checks AsciiDoc quality (one per module)
│
└── Zero-touch path (parallel):
      ├── showroom:zero-scaffold-checker (Haiku)  ← checks runtime-automation/, setup-automation/,
      │                                              config/, per-module solve.yml + validation.yml
      └── showroom:zero-content-reviewer (Sonnet) ← classic AsciiDoc checks + automation pairing
```

ph_payload format field (set by PH editor from manifest):
```yaml
ph_payload:
  format: classic | project_zero   # derived from manifest.project.showroom_type
  content_path: content/modules/ROOT/pages/
  ...
```

Both paths produce the same JSON findings schema — orchestrator merges and presents one findings table.

## What Stays in Marketplace

Internal tools remain in `rhdp-skills-marketplace`. The marketplace is not deleted — it continues to serve tools that are not part of the PH content lifecycle.

## Plugin Version Tracking

Each subdir plugin maintains its own version in its `plugin.json`. The PH orchestrator skill checks these at session start:

```yaml
# In orchestrator SKILL.md — version gate check
Minimum required versions:
  rhdp-publishing-house: 0.2.0
  showroom: 2.15.0    ← bumped from 2.14.0 for skill renames
  agnosticv: 2.15.0   ← requires ph_payload headless mode
  ftl: (TBD)
```

If a plugin is below minimum version → orchestrator surfaces a warning and points to the update command.

## Source of Truth

Each plugin within the combined repo tracks its own version in `plugin.json`. The **version in the combined repo IS the canonical version** — there is no separate source repo that "owns" the skills.

When showroom or agnosticv skills need an update, the PR goes against `rhdp-publishing-house-skills`, not `rhdp-skills-marketplace`.

This is a **one-way migration** — after cut-over, marketplace copies of showroom/agnosticv/ftl are frozen and users are pointed to PH.

## What Changes for Users

| Before | After |
|--------|-------|
| Install `rhdp-publishing-house-skills` + `rhdp-skills-marketplace` | Install only `rhdp-publishing-house-skills` |
| Two separate git repos to pull | One `git pull` updates everything |
| Silent failure if marketplace not installed | All dependencies in one package |
| Version drift between repos | Single repo, co-versioned |
| `showroom:create-lab`, `showroom:verify-content` | `showroom:lab-writing-helper`, `showroom:lab-review-helper` |

## Non-Goals

- Do NOT rename `showroom`, `agnosticv`, or `ftl` plugin names — see constraint above
- Do NOT merge all skills into one flat `skills/` dir — loses plugin namespace isolation
- Do NOT include `showroom:create-showroom` in this migration — Andrew Jones owns it independently

---

## Showroom Skill Naming

The four showroom content-authoring skills are renamed during consolidation. The rename and the plugin copy happen in the same atomic PR (migration plan Phase 0 + Phase 1).

### Name Mapping

| Old name | New name | Role |
|---|---|---|
| `showroom:create-lab` | `showroom:lab-writing-helper` | Lab content authoring |
| `showroom:verify-content` | `showroom:lab-review-helper` | Content quality review (classic + zero-touch) |
| `showroom:create-demo` | `showroom:demo-writing-helper` | Demo content authoring |
| `showroom:blog-generate` | `showroom:blog-writing-helper` | Blog content generation |
| (new — Andrew Jones) | `showroom:create-showroom` | Platform plumbing — NOT part of this migration |

Plugin names (`showroom:`, `agnosticv:`, `ftl:`) are unchanged. Only skill names within the showroom plugin change.

### Implementation Steps (ATOMIC — all in same PR per migration plan Phase 0)

**Step 1:** Rename skill directories in marketplace (Phase 0 Step 0.1)

**Step 2:** Update each SKILL.md frontmatter `name:` field (Phase 0 Step 0.1)

**Step 3:** Update all PH SKILL.md call sites

| File | Old call | New call |
|------|----------|----------|
| `skills/writer/SKILL.md` | `showroom:create-lab` | `showroom:lab-writing-helper` |
| `skills/writer/SKILL.md` | `showroom:create-demo` | `showroom:demo-writing-helper` |
| `skills/editor/SKILL.md` | `showroom:verify-content` | `showroom:lab-review-helper` |
| `skills/writer/references/writing-standards.md` | `showroom:create-lab`, `showroom:create-demo` | update to new names |
| `skills/editor/references/editing-checklist.md` | `showroom:verify-content` | update to new name |
| `skills/automation/references/automation-patterns.md` | any showroom refs | update |

**Step 4:** Update CHANGELOG with BREAKING notice

**Step 5:** Verify no old names remain
```bash
grep -r "showroom:create-lab\|showroom:verify-content\|showroom:create-demo\|showroom:blog-generate" . --include="*.md" | grep -v ".git"
# Expected: no output
```
