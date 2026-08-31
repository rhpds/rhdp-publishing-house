# AI Skills

**Plugin version:** 0.3.0
**Location:** `skills/` (git submodule → `rhdp-publishing-house-skills`)

## Skill Inventory

| Skill | Model | Purpose |
|---|---|---|
| `rhdp-publishing-house` | default | Orchestrator: checks workflow state, dispatches to correct skill |
| `rhdp-publishing-house:intake` | default | 6-phase intake: discovery → design → RCARS → modules → infrastructure → submit |
| `rhdp-publishing-house:migrate` | claude-opus-4-6 | Migration intake: reads existing Showroom content, generates PH artifacts |
| `rhdp-publishing-house:development` | default | Development dashboard: module writing, config, automation, submission |
| `rhdp-publishing-house:writer-helper` | default | Generates AsciiDoc via module-writing-helper agent |
| `rhdp-publishing-house:reviewer-helper` | default | Reviews AsciiDoc via module-reviewer agent |
| `rhdp-publishing-house:automation-helper` | default | Automation requirements, catalog config, code generation |
| `rhdp-publishing-house:gitops-helper` | default | Helm + ArgoCD generation from rhdp-gitops-patterns |
| `rhdp-publishing-house:worklog` | default | Work logging: notes, decisions, handoffs, session summaries |

## Subagent Definitions

| Agent | Tools | Purpose |
|---|---|---|
| `rhdp-publishing-house:module-reviewer` | Read, Grep, Glob | Reviews ONE .adoc module against quality standards. 5 check passes: B (structure/learning), C (formatting), D (style/terminology), E (technical correctness), F (demo-specific). Returns dimension-scored JSON |
| `rhdp-publishing-house:module-writing-helper` | Read, Write, Glob | Generates ONE AsciiDoc file from spec. Reads templates, applies writing style, humanizer pass. Returns structured JSON |

## Common Pre-flight (all skills)

| Step | What It Does | Failure |
|---|---|---|
| 0 | Detect python (`python` or `python3`) | STOP if none |
| 1 | Verify PH project (`catalog-info.yaml` + `publishing-house/spec.yaml` exist) | STOP with scaffolder instructions |
| 2 | Read `project.slug` from spec.yaml | STOP if empty |
| 3 | Check auth (`~/.config/publishing-house/auth.json` for credential + Central URL) | Prompt for API key if missing |

## Orchestrator

**Flow:** Pre-flight → `ph-workflow-data.py` → `ph-workflow-state.py` → dispatch by stage

| Stage | Dispatches To |
|---|---|
| intake (intakeType=new) | intake skill |
| intake (intakeType=migration) | migrate skill |
| development | development skill |
| content_review, infra_review, env_setup, testing, published | Show status, STOP |

**References:**
- `gate-language.md` — neutral status phrasing for each gate
- `session-protocol.md` — git pull at start, sync, commit at end
- `spec-rules.md` — spec.yaml is structured data, design.md is narrative, stage from API only

## Intake Skill (6 phases)

### Phase 1 — Discovery (`02-discovery.md`)

Conversational interview capturing:
- Goal, audience, products, content type
- Showroom type (classic vs zero_touch)
- Estimated duration

Three entry paths:
1. Build on scaffolder description
2. Import existing document
3. Already-filled spec (skip to gaps)

**Write point:** spec.yaml project/spec fields

### Phase 2 — Design Doc (`03-design-doc.md`)

- Generates `publishing-house/spec/design.md` from template
- Proposes module map table
- Inline structure check (11 required sections per spec-guidelines.md)
- Infrastructure section left as "TBD — confirmed in infrastructure phase"

**Write point:** design.md + spec.yaml modules list

### Phase 3 — RCARS Vetting (`03b-rcars-vetting.md`)

- Submits query to RCARS advisor via `ph-rcars.py submit`
- Polls for results via `ph-rcars.py poll`
- Presents catalog overlap as awareness (not a blocker)
- Writes top matches to spec.yaml `approval_checklist.content.rcars_top_matches`

**Write point:** spec.yaml rcars fields + catalog_gap

### Phase 4 — Module Outlines (`04-module-outlines.md`)

- Generates per-module outline files in `publishing-house/spec/modules/`
- Naming: `module-01-short-title.md`, `module-02-short-title.md`
- Each outline has 5 required sections: Brief Overview, Audience and Time, Learning Objectives, Lab Structure, Key Takeaways
- Auto-generates `design_overview` and `module_summaries` for spec.yaml
- Initializes module statuses to `not_started`

**Write point:** module files + spec.yaml modules/approval_checklist

### Phase 5 — Infrastructure (`05-infrastructure.md`)

- Determines platform (ocp vs rhel-vms) from products
- Derives sizing defaults from product signals
- Presents single infrastructure profile for confirmation
- Conditional follow-ups: AI/MaaS, AAP version, non-GA products, external services, concurrent users

**Fields populated:** platform, topology, cloud_provider, cluster_type, ocp_version, worker_count/cpu/ram/disk (optional), vms_per_student (if rhel-vms), ai_requirement, external_services, non_ga_products

**Write point:** spec.yaml environment + design.md Infrastructure section

### Phase 6 — Finalize + Submit (`06-finalize-and-submit.md`)

- Final review of all spec.yaml fields
- Generates `automation-manifest.yaml`
- Generates `mkdocs.yml`
- Author checkpoint (explicit confirmation)
- Commit + push
- Submit via `ph-intake.py` (calls Central API → validation → CloudEvent)
- Project structure cleanup: remove zero-touch dirs for classic, keep for zero_touch

### Rejection Handler (`00-rejection-handler.md`)

- Triggered when `unresolved_rejections > 0` (from `ph-sync.py`)
- Shows rejection context (who, when, reasons)
- Walks through each reason with author
- Updates affected files (spec, design, modules)
- Marks each reason as resolved
- Resubmits intake

## Migrate Skill

**Model:** claude-opus-4-6

**Flow:** Pre-flight → workflow check → load policy → spawn content-reader agent → present analysis → spawn migration-writer agent → RCARS → infrastructure → finalize+submit

### Content Reader Agent

Reads from existing Showroom repo:
- `site.yml` — title, nav structure
- `ui-config.yml` — UI configuration
- `content/modules/ROOT/nav.adoc` — module order
- All `.adoc` files in `content/modules/ROOT/pages/`
- `publishing-house/spec.yaml` — pre-populated fields
- `catalog-info.yaml` — migrated-repo annotation

Returns structured report: modules, products, infrastructure signals, audience signals

### Migration Writer Agent

Takes reader report + policy + spec guidelines. Two phases:
1. Fill design.md from content analysis
2. Generate module outlines from page content

Populates spec.yaml by reading inline comments (the comments ARE the schema). Only populates what the content supports — does NOT fabricate values.

**RCARS filter:** Excludes the migrated repo itself from overlap results (via `ph.rhdp.io/migrated-repo` annotation)

## Development Skill

**Flow:** Pre-flight → workflow check (must be `development` stage) → scaffold gate → dashboard → workstream dispatch → submission gate

### Dashboard

Dynamic numbered menu showing incomplete workstreams:
1. Modules (per-module sub-menu)
2. Automation (ansible/gitops/both)
3. E2E Tests (optional, gated on automation complete)
4. Health Check (optional, gated)
5. Showroom Config (always)

### Module Sub-menu

- Start module: set `in_progress`, create stub .adoc
- Options: Write myself / AI writer helper / Back
- Mark complete: set status, commit, push, `ph-task-complete.py module-NN`

### Config Helper/Reviewer

- `config-helper.md` — scaffold showroom structure, tab advisor, fix J-rule findings
- `config-reviewer.md` — validate showroom config against S/U/A/N/X/J/Z validation rules

### Submission Gate

All modules complete + automation complete → `ph-development.py` → Central API → CloudEvent

## Tools Scripts (in project repo)

| Script | Called By | Central API Endpoint |
|---|---|---|
| `ph-workflow-data.py` | orchestrator, intake, migrate, development | `GET /projects/{slug}/workflow-data` |
| `ph-workflow-state.py` | orchestrator, intake, migrate, development | `GET /projects/workflow-state/{wfid}` |
| `ph-sync.py` | intake, migrate, development | workflow-data + workflow-state + rejection sync |
| `ph-policy.py` | intake, migrate | `GET /spec/validation/policy` |
| `ph-rcars.py` | intake, migrate | `/rcars/advisor` (submit/poll), `/rcars/catalog/{ci}` |
| `ph-intake.py` | intake, migrate | `POST /projects/intake/{slug}` |
| `ph-development.py` | development | `POST /projects/development/{slug}` |
| `ph-task-complete.py` | development | `POST /jira/{epic}/task/{id}/complete` |
| `ph-check.py` | development | `POST /spec/validation/{slug}?stage=` |
| `scaffold.py` | development (config-helper) | (local only — pattern scaffold) |

All tools use 3-tier GitHub user resolution: auth.json cache → git credential fill → OAuth device flow.

## Reference Files

| Path | Content |
|---|---|
| `intake/references/spec-guidelines.md` | 11 required design.md sections, infra requirements schema, approval checklist fields, module outline sections, quality checks |
| `orchestrator/references/gate-language.md` | Neutral status phrasing for each gate |
| `orchestrator/references/session-protocol.md` | Session start/end protocol |
| `orchestrator/references/spec-rules.md` | Spec.yaml vs design.md roles, stage authority |
| `development/references/showroom-patterns.md` | Open/Guided/ZT Guided patterns with config examples |
| `development/references/config-files.md` | site.yml, ui-config.yml, antora.yml, nav.adoc, podman-compose specs |
| `development/references/validation-rules.md` | All S/U/A/N/X/J/Z validation rules with severity and auto-fix flags |
| `development/references/workflow-diagram.md` | Development phase flow diagrams |
| `writer-helper/references/writing-standards.md` | Module outline as primary input, content type routing, numbering conventions |
| `reviewer-helper/references/editing-checklist.md` | SA/RS spec alignment check definitions |
| `automation-helper/references/` | automation-patterns.md, ansible-automation-guide.md, gitops-automation-guide.md, automation-manifest-format.md |
| `gitops-helper/references/gitops-patterns.md` | Sync-wave conventions, operator quirks, S2I builders, PVC placement |
