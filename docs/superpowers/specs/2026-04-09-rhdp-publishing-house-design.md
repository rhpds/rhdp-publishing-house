# RHDP Publishing House — Design Specification

**Date:** 2026-04-09
**Author:** nstephan
**Status:** Draft

---

## Overview

RHDP Publishing House is a Claude Code plugin that manages the full content lifecycle for Red Hat Demo Platform (RHDP) content — from initial idea through ready-for-publishing. It enables content developers to become content architects by orchestrating specialized AI agents that handle writing, editing, automation development, and security review.

One entry point. One manifest. Pick up where you left off, any day, any session. Hand off to a colleague across timezones or skill levels — they see exactly where things stand and what's next.

## Problem

Content development for RHDP is labor-intensive. A single workshop involves writing AsciiDoc modules, building AgnosticV catalogs, developing Ansible/GitOps automation, running security checks, and coordinating technical reviews. Each step requires different skills and tools. Content developers spend most of their time on toil rather than architecture and design.

## Solution

A Hub + Spoke plugin where a thin orchestrator manages project state and dispatches specialized agent skills for each lifecycle phase. The content owner stays in control — orchestrating agents, reviewing outputs, and making decisions at gates — while the bulk writing, validation, and automation work is handled by agents backed by existing RHDP skills.

## Architecture

### Hub + Spoke Model

```
/rhdp-publishing-house [autonomy-level]
         |
    Orchestrator (reads manifest, determines phase, presents options)
         |
    +----+----+--------+----------+---------+--------+
    |         |        |          |         |        |
 Intake    Writer   Editor   Automation  Security  Review
 Agent     Agent    Agent     Agent       Agent    Agent
    |         |        |          |
  RCARS    showroom  showroom  agnosticv
  API      :create-  :verify-  :catalog-
           lab/demo  content   builder
```

**Why Hub + Spoke over monolithic:** Each agent is a separate skill file — focused, testable, independently iterable. Adding a new phase means adding a new spoke, not rewriting the monolith. Only relevant context loads per phase, reducing token pressure.

### Plugin Namespace

- **Namespace:** `rhdp-publishing-house`
- **Entry point:** `/rhdp-publishing-house` (aliases to `rhdp-publishing-house:orchestrator`)
- **Future migration path:** `/rhdp` namespace when RHDP skills consolidate

### Autonomy Levels

Passed as argument to entry point. Stored in manifest, persists across sessions. Default: `supervised`.

| Level | Behavior |
|-------|----------|
| **supervised** (default) | Agent produces draft, presents to user, user approves before commit. Every artifact reviewed. |
| **semi** | Agent commits WIP to branch, runs validation automatically. Flags user at phase gates and decision points only. |
| **full** | Agent works through entire phase end-to-end. Presents completed output at phase gate for review. |

Invocation:
- `/rhdp-publishing-house` — supervised (default)
- `/rhdp-publishing-house semi` — semi-autonomous
- `/rhdp-publishing-house full` — fully autonomous within phases

User can change autonomy mid-session by saying "switch to semi" or re-invoking.

## Content Lifecycle

```
Intake* → Vetting → Spec Refinement → Approval → Writing° → Technical Editing*
  → Automation° (catalog → environment → grading†) → Security Review*
  → Final Review → Ready for Publishing

* = required (but intake can be shortcut with a pre-existing spec)
° = optional (can skip if done manually)
† = grading/health checks deferred to future phase
```

### Flexible Adoption

Publishing House does not require end-to-end usage. Teams adopt the phases that help them:

| Phase | Required? | Can Skip If... |
|-------|-----------|----------------|
| Intake | Yes, but shortcuttable | User provides a pre-existing design doc; agent validates format and fills gaps |
| Vetting | No | RCARS unavailable or user has already validated uniqueness |
| Spec Refinement | No | Spec is already clean and agent-ready |
| Approval | Yes (gate) | Always requires explicit human sign-off |
| Writing | No | Content already exists (written manually or in a prior tool) |
| Technical Editing | Yes | — always runs; catches quality issues regardless of how content was produced |
| Automation | No | Environment setup handled externally or not needed |
| Security Review | Yes | — always runs; non-negotiable for publishing readiness |
| Final Review | Yes | — holistic check before marking ready |

**Skipping a phase** means setting its status to `skipped` in the manifest. The orchestrator
still tracks it — skipped phases show in the status summary so reviewers know what was
and wasn't done. Skipped phases can be un-skipped later if the user changes their mind.

**Shortcutting intake** means the user provides an existing design doc (file, paste, or
Google Doc). The intake agent validates it against the spec template, fills gaps, and
generates module outlines — but skips the conversational spec-building workflow.

### Phase Details

#### 1. Intake (required — shortcuttable)
- **Agent:** Intake Agent
- **Required** because downstream agents need a normalized spec and module outlines to work from
- **Shortcut:** If the user already has a design doc, the agent validates and normalizes it rather than building from scratch
- **Three entry paths:**
  - Experienced content dev brings mostly-complete spec — agent fills gaps
  - Someone with an idea ("I need a lab on X") — agent builds spec through conversation
  - RCARS gap — single sentence gap description becomes seed for spec generation
- **Produces:** `publishing-house/spec/design.md` (master) + `publishing-house/spec/modules/*.md` (per-module outlines)

#### 2. Vetting (optional)
- **Agent:** Intake Agent (continues)
- **Action:** Calls RCARS REST API with spec content (learning objectives, topics, products, audience)
- **Possible outcomes:**
  - Gap confirmed — nothing covers this, proceed
  - Partial overlap — similar content exists, spec refinement should differentiate
  - Already covered — recommend enhancement over new project
- **Produces:** `publishing-house/reviews/rcars-vetting.md`
- **Skip if:** RCARS unavailable or user has already validated content uniqueness

#### 3. Spec Refinement (optional)
- **Agent:** Intake Agent (continues)
- **Action:** Rewrites/cleans up spec and module outlines based on:
  - RCARS feedback (if available)
  - Clarity and precision for downstream agent consumption
  - Standard format with See/Learn/Do, timing, numbered steps
- **Goal:** Spec and module outlines sufficient for writer agent to produce content without ambiguity
- **Skip if:** Spec is already clean and detailed enough for downstream agents

#### 4. Approval (required — gate)
- **Human decision gate**
- **Owner reviews** master design + individual module outlines
- **Outcome:** Proceed / revise specific modules / reject
- **Manifest updated** with approval decision and approver

#### 5. Writing (optional)
- **Agent:** Writer Agent
- **Wraps:** `showroom:create-lab`, `showroom:create-demo`
- **Works module-by-module** based on approved outlines in `spec/modules/`
- **Owner triggers** which module to write: "write module 2"
- **Produces:** AsciiDoc files in `content/`
- **Skip if:** Content was written manually or with another tool. The editor agent
  still reviews whatever content exists in `content/` regardless of how it got there.

#### 6. Technical Editing (required)
- **Agent:** Editor Agent
- **Wraps:** `showroom:verify-content` + Red Hat style guide references
- **Reviews:** Accuracy, style, consistency, clarity, Red Hat standards compliance
- **Produces:** Review notes in `publishing-house/reviews/`, edits to `content/`
- **Always runs** — catches quality issues regardless of whether content was agent-generated
  or hand-written. This is a quality gate, not an optional polish step.

#### 7. Automation (optional)
Four sub-phases, first three active, fourth deferred:

**7a. Catalog Item**
- **Agent:** Automation Agent
- **Wraps:** `agnosticv:catalog-builder`, `agnosticv:validator`
- **Produces:** AgnosticV catalog configuration (identifies infrastructure and existing workloads)

**7b. Automation Requirements**
- **Agent:** Automation Agent (continues)
- **Action:** Analyzes content to determine what needs to be pre-configured vs what the learner does
- **Produces:** `publishing-house/spec/automation-manifest.yaml` — reviewable scope document
- **Always a review gate** — automation scope must be explicitly approved

**7c. Automation Code**
- **Agent:** Automation Agent (continues)
- **Action:** Creates Ansible collections or GitOps repos (Helm + ArgoCD) from approved requirements
- **Determines approach** (Ansible vs GitOps) from automation manifest
- **Includes its own code review + catalog re-validation cycle** (separate from phase 8)
- **Wraps:** `code-review:code-review` for automation code review
- **Produces:** Automation in `automation/`

**Skip if:** Environment setup is handled externally, or `needs_automation: false` in manifest

**7d. Testing (gate)**
- **Human responsibility** — deploy the catalog item to a dev environment and verify it works
- **Always a gate** — must be explicitly completed or skipped before automation phase closes
- **Agent tracks status** but does not deploy or test itself

**7e. E2E Checks** *(deferred — future phase)*
- Would wrap: `ftl:rhdp-lab-validator`, `health:deployment-validator`

#### 8. Security Review
- **Agent:** Security Agent
- **Focus:** Content-level security (separate from automation code review in 7b)
- **Checks:** Exposed credentials in docs, hardcoded URLs, sensitive info in public-facing content, Red Hat sensitive data policy compliance
- **Produces:** `publishing-house/reviews/security-review.md`

#### 9. Final Review
- **Agent:** Review Agent
- **Holistic check:** Spec alignment, completeness, cross-module consistency, all prior review items addressed
- **Produces:** Final review report

#### 10. Ready for Publishing
- **Manifest updated** to `ready_for_publishing`
- **Not "Published"** — actual publication is a separate process outside this tool's scope (for now)

## Collaboration & Handoff

The manifest-driven design makes Publishing House inherently collaborative:

- **Timezone handoff** — Developer A in one timezone works through intake and spec refinement, pushes to the repo. Developer B in a later timezone runs `/rhdp-publishing-house`, immediately sees "Spec approved. Writing phase — 3 modules pending. Suggested next: write Module 1."
- **Role-based handoff** — A content architect designs the spec and overall structure, then hands the project to a developer who runs the writing, editing, and automation phases with agent assistance. The spec provides guardrails; the agents provide expertise. Each person works to their strengths.
- **One-person show** — Solo content developers benefit equally. The orchestrator tracks progress across sessions, agents handle the bulk work, and the manifest ensures nothing falls through the cracks.
- **Review distribution** — Different team members can own different review phases. One person writes, another edits, a third handles security review. The manifest tracks who did what and when.

All collaboration happens through the repo (push/pull) and the manifest. No external coordination tool needed — the project state is the coordination.

## State Management

### Manifest (`publishing-house/manifest.yaml`)

Structured YAML — single source of truth. Orchestrator reads/writes this every session.

```yaml
project:
  name: "Configuring ServiceMesh on OpenShift"
  id: "servicemesh-ocp-lab"
  created: 2026-04-09
  owner: "nstephan"
  type: workshop  # workshop | demo
  autonomy: supervised  # supervised | semi | full

lifecycle:
  current_phase: writing
  phases:
    intake:
      status: completed  # pending | in_progress | completed | skipped
      completed_at: 2026-04-09
      artifacts:
        - publishing-house/spec/design.md
        - publishing-house/spec/modules/module-01-overview.md
        - publishing-house/spec/modules/module-02-deploy.md
    vetting:
      status: completed
      completed_at: 2026-04-09
      result: approved  # approved | revise | rejected
      rcars_response: publishing-house/reviews/rcars-vetting.md
    spec_refinement:
      status: completed
      completed_at: 2026-04-10
    approval:
      status: completed
      approved_by: nstephan
      completed_at: 2026-04-10
    writing:
      status: in_progress
      modules:
        - name: "Module 1: Installing ServiceMesh"
          status: drafted  # pending | in_progress | drafted | approved
        - name: "Module 2: Traffic Management"
          status: pending
        - name: "Module 3: Observability"
          status: pending
    editing:
      status: pending
    automation:
      status: pending
      needs_automation: true
      substeps:
        catalog_item: pending
        requirements: pending
        automation_code: pending
        testing: pending
        e2e_checks: deferred
    security_review:
      status: pending
    final_review:
      status: pending
    ready_for_publishing:
      status: pending

integrations:
  rcars_api: "https://rcars.apps.example.com/api/v1"
  showroom_repo: null
  automation_repo: null
```

### Work Journal (`publishing-house/journal.md`) — Experimental

Human-readable session log. Updated alongside manifest but not the source of truth.

```markdown
# Work Journal

## 2026-04-10

### What was done
- Completed spec refinement for all 3 modules
- Owner approved design and module outlines

### Key decisions
- Module 2 split into two sub-modules per owner feedback

### Next up
- Begin writing Module 1
```

### Session Flow

```
Session start → Orchestrator reads manifest.yaml
  → Presents: current phase, what's done, what's next
  → User directs: "write module 2" / "what's next" / "switch to semi"
  → Orchestrator dispatches appropriate agent
  → Agent works (per autonomy level)
  → Agent completes → Orchestrator updates manifest
  → Loop until user ends session
  → Journal updated with session summary
```

## Plugin Package Structure

Lives in the RHDP Skills Marketplace (`rhpds/rhdp-skills-marketplace`):

```
rhdp-publishing-house/
├── .claude-plugin/
│   └── plugin.json
├── README.md
├── docs/
│   ├── PH-COMMON-RULES.md           # Shared rules across all PH skills
│   └── getting-started.md           # Concise usage guide
├── skills/
│   ├── orchestrator/
│   │   ├── SKILL.md                 # Entry point — state mgmt + dispatch
│   │   └── workflow.svg
│   ├── intake/
│   │   ├── SKILL.md                 # Spec generation + RCARS vetting
│   │   ├── workflow.svg
│   │   └── references/
│   │       └── spec-guidelines.md
│   ├── writer/
│   │   ├── SKILL.md                 # Content writing (wraps showroom skills)
│   │   ├── workflow.svg
│   │   └── references/
│   │       └── writing-standards.md
│   ├── editor/
│   │   ├── SKILL.md                 # Technical editing (wraps verify-content)
│   │   ├── workflow.svg
│   │   └── references/
│   │       └── editing-checklist.md
│   ├── automation/
│   │   ├── SKILL.md                 # AgnosticV + Ansible/Helm automation
│   │   ├── workflow.svg
│   │   └── references/
│   │       └── automation-patterns.md
│   ├── security/
│   │   ├── SKILL.md                 # Content security review
│   │   ├── workflow.svg
│   │   └── references/
│   │       └── security-checklist.md
│   └── review/
│       ├── SKILL.md                 # Final holistic review
│       ├── workflow.svg
│       └── references/
│           └── review-criteria.md
```

## Template Repo

Separate GitHub template repo: `rhpds/rhdp-publishing-house-template`

User creates their project repo from this template, clones it locally, then invokes `/rhdp-publishing-house`.

```
my-new-lab/
├── publishing-house/
│   ├── manifest.yaml                 # Pre-populated with empty phases
│   ├── journal.md                    # Empty work journal
│   ├── spec/
│   │   ├── design.md                 # Blank — intake agent populates
│   │   ├── modules/                  # Per-module outlines land here
│   │   └── SPEC-TEMPLATE.md          # Reference template (don't edit)
│   ├── reviews/                      # Agent review artifacts
│   └── decisions/                    # Decision records
├── content/                          # Showroom AsciiDoc (writer agent output)
│   └── .gitkeep
├── automation/                       # Ansible/Helm (automation agent output)
│   └── .gitkeep
├── CLAUDE.md                         # Points to publishing-house/ context
├── .gitignore
└── README.md
```

### Module Outline Format

Per-module outlines in `spec/modules/` follow the pattern from `ocp4-getting-started-workspace`:

- **Brief Overview** — 3-4 sentences setting context
- **Audience and Time** — Target personas, prerequisites, duration
- **What You Will See, Learn, and Do** — Bulleted lists organized by verb
- **Lab Structure** — Named sections with time estimates
- **Detailed Steps** — Numbered, granular enough for writer agent
- **Key Takeaways** — Concepts reinforced
- **Infrastructure Notes** — Requirements, config details (if applicable)

Granularity scales with complexity: simple module ~80 lines, complex multi-demo module ~300 lines.

## RCARS Integration

- **Protocol:** REST API (HTTP)
- **Endpoint:** `POST /api/v1/recommend`
- **Payload:** Spec content — learning objectives, topics, products, audience
- **Response:** Recommendations for existing overlapping content + identified gaps
- **Config:** API URL stored in `manifest.yaml` under `integrations.rcars_api`
- **Fallback:** If RCARS unavailable, vetting phase skippable with explicit user acknowledgment

## Agent Details

### Orchestrator
- **Invoked by:** User via `/rhdp-publishing-house [autonomy]`
- **Does:** Reads manifest, presents state summary + recommended next action, dispatches agents, updates manifest after agent completion
- **Does NOT contain:** Agent logic — purely state management and routing
- **Project discovery:** On invocation, orchestrator looks for `publishing-house/manifest.yaml` in the current directory. If not found, prompts user for the project directory path. Remembers this path for the session.
- **First-time flow:** If manifest found but empty/fresh (from template), asks if user has a spec or needs help creating one, kicks off intake.
- **No template detected:** If invoked in a directory with no manifest and no template structure, instructs user to clone the template repo first and provides the repo URL.

### Intake Agent
- **Handles:** Intake, vetting, spec refinement phases
- **Three paths:** Full spec provided, rough idea, RCARS gap
- **All converge to:** Normalized master design.md + per-module outlines
- **RCARS call:** During vetting substep

### Writer Agent
- **Wraps:** `showroom:create-lab`, `showroom:create-demo`
- **Input:** Approved module outline from `spec/modules/`
- **Output:** AsciiDoc in `content/`
- **Works per-module** — owner triggers which module

### Editor Agent
- **Wraps:** `showroom:verify-content` + style guide references
- **Reviews:** After all modules drafted (or per-module in semi/full autonomy)
- **Output:** Review notes + direct edits to content

### Automation Agent
- **Wraps:** `agnosticv:catalog-builder`, `agnosticv:validator`, `code-review:code-review`
- **7a:** Creates AgnosticV catalog from spec
- **7b:** Writes Ansible roles/playbooks or Argo+Helm manifests for environment setup
- **Includes own code + security review cycle** for automation code
- **Optional:** Only runs if `needs_automation: true`
- **New skill needed:** Automation writing (Ansible + Argo/Helm generation)

### Security Agent
- **Focus:** Content-level security (NOT automation code — that's covered in 7b)
- **Checks:** Credentials in docs, hardcoded URLs, sensitive info in public content, Red Hat data policy
- **Output:** `publishing-house/reviews/security-review.md`

### Review Agent
- **Holistic final check:** Spec alignment, completeness, cross-module consistency
- **Verifies:** All prior review items addressed
- **Output:** Final review report, manifest updated to `ready_for_publishing`

## Model Selection

Different agents use different models based on task complexity:

| Agent | Model | Reasoning |
|-------|-------|-----------|
| **Orchestrator** | Opus 4.6 | Needs to understand project state and route intent |
| **Intake** | Opus 4.6 | Deep exploration, thorough spec generation |
| **Writer** | Sonnet 4.6 | Module outlines provide sufficient guardrails |
| **Editor** | Sonnet 4.6 | Checklist-driven review against standards |
| **Automation** | Opus 4.6 | Complex reasoning for Ansible/Helm generation |
| **Security** | Sonnet 4.6 | Pattern-matching against security checks |
| **Review** | Sonnet 4.6 | Structured holistic review |

For simple 5-10 minute labs, Sonnet handles all phases well. For large multi-module workshops, Opus on intake and automation pays off in spec quality and automation correctness.

## Existing Skills Reused

| Skill | Used By | Phase |
|-------|---------|-------|
| `showroom:create-lab` | Writer Agent | Writing |
| `showroom:create-demo` | Writer Agent | Writing |
| `showroom:verify-content` | Editor Agent | Technical Editing |
| `agnosticv:catalog-builder` | Automation Agent | Automation (7a) |
| `agnosticv:validator` | Automation Agent | Automation (7a) |
| `code-review:code-review` | Automation Agent, Security Agent | Automation (7b), Security Review |

## New Skills/Capabilities Needed

| Capability | Agent | Notes |
|-----------|-------|-------|
| Spec generation + RCARS integration | Intake Agent | New skill |
| Automation writing (Ansible) | Automation Agent | New skill or sourced |
| Automation writing (Argo + Helm) | Automation Agent | New skill or sourced |
| Content security audit | Security Agent | New skill |
| Holistic review criteria | Review Agent | New skill |

## Open Items

- [ ] **[PRIORITY] Self-service deployment pathway** — Publishing House must support content developers who don't have access to agnosticV (or prefer not to use it) by targeting the generic Field Source CI (`agd_v2/ocp-field-asset-cnv`). This CI provisions an OpenShift cluster with the gitops bootstrap role pre-installed and prompts the user to supply their GitOps repo at order time — no AgnosticV catalog item is needed.

  **Intake change:** During the intake interview, the agent must ask: *"Are you building this to fully onboard to RHDP, or do you want to build self-service content?"* Record the answer in the manifest as `deployment_mode: onboarded | self_service`.

  **Automation phase change:** When `deployment_mode: self_service` is set:
  - **Skip substep 7b (Catalog Item)** — there is no AgnosticV catalog to create.
  - **Run substeps 7a (requirements) and 7c (code) as normal** — produce the GitOps automation (Helm charts + ArgoCD manifests) in `automation/`.
  - The completed GitOps repo is what the content developer provides when ordering the generic CI.
  - Orchestrator should surface a reminder at the end of automation phase: *"Automation complete. Order the Field Source CI and provide your GitOps repo URL. Ensure your automation/ directory is pushed to a public or accessible Git remote."*

  **Manifest schema additions:**
  ```yaml
  project:
    deployment_mode: self_service  # onboarded | self_service
  integrations:
    field_source_ci: agd_v2/ocp-field-asset-cnv  # populated when self_service mode selected
  ```

  **Affected skills:** Intake agent (question + manifest write), Automation agent (7b skip logic + reminder), Orchestrator (route automation dispatch differently when self_service mode is active). See portal redesign spec for launch instructions design.

- [ ] **GitHub template repo** — Create `rhpds/rhdp-publishing-house-template` with proper structure
- [ ] **RCARS API contract** — Finalize endpoint spec when RCARS REST API is ready
- [ ] **Automation skill sourcing** — Determine if existing Ansible/Helm generation tools exist or need full development
- [ ] **Namespace migration** — Plan for moving from `rhdp-publishing-house` to `/rhdp` namespace
- [ ] **ZT grading + health checks** — Design phase 7c when ready to implement
- [ ] **Infosec review of project structure** — Validate that keeping design docs in private repo addresses sensitivity concerns
- [ ] **Polish GitHub Pages docs** — Refine the Jekyll site at `docs/` (index, executive summary, getting started, how it works). Consider a better theme (just-the-docs or minimal-mistakes), add screenshots/diagrams, improve navigation, add a changelog page.
- [ ] **Red Hat style guide reference** — Add a condensed Red Hat writing style reference (`docs/redhat-style-guide.md` or shared in `references/`) for writer and editor agents. Currently the showroom skills enforce style at invocation time, but the PH agents have no independent style awareness. A lightweight reference would help the writer generate style-compliant content upfront (fewer editor findings) and give the editor explicit criteria beyond RS-1/RS-2.
- [ ] **Vision document** — Write a forward-looking vision for Publishing House. Where we are today (structured agent pipeline for content teams) and where this goes. The key insight: this is the content "Babylon moment." Today RHDP users browse and select only pre-created content. Publishing House enables **content on demand** — users describe what they need and the system generates bespoke labs/demos aligned to their specific use case. This creates a second tier of content: vetted/supported labs remain first-class, but on-demand generated content fills the long tail of customer-specific needs. The vision doc should cover: the on-demand content model, quality tiers (curated vs generated), how RCARS feeds gap analysis into automatic content generation, the path from internal tool to platform capability, and what "self-service content creation" looks like for field teams, partners, and eventually customers.
