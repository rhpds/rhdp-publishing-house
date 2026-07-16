# Phase 1: Plugin Structure + Orchestrator + Intake Agent — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the foundational RHDP Publishing House plugin with orchestrator (state management + dispatch) and intake agent (spec generation + RCARS vetting), deployable to the RHDP Skills Marketplace.

**Architecture:** Hub + Spoke Claude Code plugin. Orchestrator SKILL.md reads YAML manifest, presents project state, and dispatches agent skills. Intake agent SKILL.md handles spec creation through three paths (full spec, rough idea, RCARS gap), RCARS vetting, and spec refinement. All state persisted in `publishing-house/manifest.yaml`.

**Tech Stack:** Claude Code plugin (SKILL.md markdown files), YAML (manifest), Markdown (specs, references, docs)

---

## File Structure

### Plugin files (in this repo — later added to marketplace)

```
rhdp-publishing-house/
├── .claude-plugin/
│   └── plugin.json                              # Plugin metadata
├── README.md                                    # Plugin overview + skill list
├── docs/
│   ├── PH-COMMON-RULES.md                      # Shared rules for all PH skills
│   └── getting-started.md                       # Concise usage guide
├── skills/
│   ├── orchestrator/
│   │   └── SKILL.md                             # Entry point — state + dispatch
│   └── intake/
│       ├── SKILL.md                             # Spec generation + RCARS vetting
│       └── references/
│           ├── spec-guidelines.md               # What makes a good spec
│           └── module-outline-template.md        # Per-module outline template
```

### Template repo files (created here, moved to template repo later)

```
template/
├── publishing-house/
│   ├── manifest.yaml                            # Empty/initial manifest
│   ├── journal.md                               # Empty work journal
│   ├── spec/
│   │   ├── design.md                            # Blank design placeholder
│   │   ├── modules/
│   │   │   └── .gitkeep
│   │   └── SPEC-TEMPLATE.md                     # Reference template
│   ├── reviews/
│   │   └── .gitkeep
│   └── decisions/
│       └── .gitkeep
├── content/
│   └── .gitkeep
├── automation/
│   └── .gitkeep
├── agnosticv/
│   └── .gitkeep
├── CLAUDE.md
├── .gitignore
└── README.md
```

---

### Task 1: Plugin Scaffold

**Files:**
- Create: `.claude-plugin/plugin.json`
- Create: `README.md` (plugin-level, replace current empty)

- [ ] **Step 1: Create plugin directory**

```bash
mkdir -p .claude-plugin
```

- [ ] **Step 2: Write plugin.json**

Create `.claude-plugin/plugin.json`:

```json
{
  "name": "rhdp-publishing-house",
  "version": "0.1.0",
  "description": "AI-powered content lifecycle management for RHDP — from idea to ready-for-publishing",
  "author": {
    "name": "RHDP Team",
    "email": "rhdp-team@redhat.com"
  }
}
```

- [ ] **Step 3: Validate plugin.json is valid JSON**

Run: `python3 -c "import json; json.load(open('.claude-plugin/plugin.json')); print('Valid JSON')"`
Expected: `Valid JSON`

- [ ] **Step 4: Write plugin README.md**

Create `README.md`:

```markdown
# RHDP Publishing House

AI-powered content lifecycle management for Red Hat Demo Platform.

## Overview

One command — `/rhdp-publishing-house` — provides a persistent, state-aware orchestrator
that manages the entire content lifecycle through specialized AI agents. Content developers
become content architects: design the architecture, agents handle the writing, editing,
automation, and review.

## Skills

### /rhdp-publishing-house (orchestrator)

Entry point. Reads project manifest, presents current state, recommends next action,
dispatches agent skills. Supports three autonomy levels: supervised (default), semi, full.

### /rhdp-publishing-house:intake

Spec generation and RCARS vetting. Three intake paths:
- Full spec provided — agent fills gaps
- Rough idea — agent builds spec through conversation
- RCARS gap — gap description becomes seed for new spec

### /rhdp-publishing-house:writer *(Phase 2)*
### /rhdp-publishing-house:editor *(Phase 2)*
### /rhdp-publishing-house:automation *(Phase 3)*
### /rhdp-publishing-house:security *(Phase 4)*
### /rhdp-publishing-house:review *(Phase 4)*

## Getting Started

See [docs/getting-started.md](docs/getting-started.md).

## Autonomy Levels

| Level | Behavior |
|-------|----------|
| **supervised** (default) | Review every artifact before commit |
| **semi** | Review at phase gates only |
| **full** | Review at phase completion |

## Content Lifecycle

```
Intake → Vetting → Spec Refinement → [Approval] → Writing → Editing
  → Automation → Security Review → Final Review → Ready for Publishing
```
```

- [ ] **Step 5: Commit**

```bash
git add .claude-plugin/plugin.json README.md
git commit -m "Add plugin scaffold with plugin.json and README"
```

---

### Task 2: Common Rules Document

**Files:**
- Create: `docs/PH-COMMON-RULES.md`

- [ ] **Step 1: Write PH-COMMON-RULES.md**

Create `docs/PH-COMMON-RULES.md`:

```markdown
# Publishing House Common Rules

Rules that apply to ALL Publishing House skills. Read this before working on any PH skill.

## Manifest is Source of Truth

- Always read `publishing-house/manifest.yaml` before taking action
- Update manifest after completing any phase or substep
- Never modify manifest fields outside your agent's scope
- Use ISO 8601 dates (YYYY-MM-DD) for all timestamps

## Autonomy Levels

The manifest's `project.autonomy` field controls agent behavior:

- **supervised**: Present every artifact to user for approval before writing to disk or committing. Ask "Does this look right?" after each output. Do not commit without explicit approval.
- **semi**: Write artifacts to disk and commit to a WIP branch. Run validation skills automatically. Only pause for user input at phase gates (transitions between lifecycle phases) and decision points (e.g., RCARS vetting results).
- **full**: Work through the entire current phase end-to-end. Present completed output at the phase gate for review before transitioning to the next phase.

## Phase Transitions

- Only the orchestrator transitions between phases
- Agents report completion back to the user; the orchestrator updates the manifest
- Never skip the approval gate (phase 4) — it always requires explicit human approval

## File Conventions

- Specs go in `publishing-house/spec/`
- Module outlines go in `publishing-house/spec/modules/`
- Review artifacts go in `publishing-house/reviews/`
- Decision records go in `publishing-house/decisions/`
- Content output goes in `content/`
- Automation output goes in `automation/`
- AgnosticV config goes in `agnosticv/`

## Sensitive Content

Publishing house project repos are private. However:
- Never include real credentials, API keys, or tokens in any file
- Use `<placeholder>` syntax for sensitive values
- Content that will eventually move to a public Showroom repo must follow
  Red Hat's public repository guidelines (no internal hostnames, customer data, etc.)

## Communication Style

- Be concise and direct
- Lead with the answer or action, not the reasoning
- When presenting status, use structured format:
  - Current phase, what's done, what's next
  - Module-level progress where applicable
- Ask one question at a time when gathering information

## Referencing Other Skills

When dispatching to existing RHDP skills, inform the user which skill is being used:
"Using showroom:create-lab to write Module 1 content."

Do not re-implement logic that exists in other skills. Wrap and invoke them.
```

- [ ] **Step 2: Commit**

```bash
git add docs/PH-COMMON-RULES.md
git commit -m "Add common rules document for all PH skills"
```

---

### Task 3: Manifest Template + Spec Template

**Files:**
- Create: `template/publishing-house/manifest.yaml`
- Create: `template/publishing-house/journal.md`
- Create: `template/publishing-house/spec/design.md`
- Create: `template/publishing-house/spec/SPEC-TEMPLATE.md`
- Create: `template/publishing-house/spec/modules/.gitkeep`
- Create: `template/publishing-house/reviews/.gitkeep`
- Create: `template/publishing-house/decisions/.gitkeep`
- Create: `template/content/.gitkeep`
- Create: `template/automation/.gitkeep`
- Create: `template/agnosticv/.gitkeep`
- Create: `template/CLAUDE.md`
- Create: `template/.gitignore`
- Create: `template/README.md`

- [ ] **Step 1: Create template directory structure**

```bash
mkdir -p template/publishing-house/spec/modules
mkdir -p template/publishing-house/reviews
mkdir -p template/publishing-house/decisions
mkdir -p template/content
mkdir -p template/automation
mkdir -p template/agnosticv
touch template/publishing-house/spec/modules/.gitkeep
touch template/publishing-house/reviews/.gitkeep
touch template/publishing-house/decisions/.gitkeep
touch template/content/.gitkeep
touch template/automation/.gitkeep
touch template/agnosticv/.gitkeep
```

- [ ] **Step 2: Write initial manifest.yaml**

Create `template/publishing-house/manifest.yaml`:

```yaml
# RHDP Publishing House — Project Manifest
# This file is the source of truth for project state.
# The orchestrator reads and updates it every session.

project:
  name: ""          # Project name (e.g., "Getting Started with OpenShift")
  id: ""            # Short identifier (e.g., "ocp-getting-started")
  created: ""       # ISO 8601 date (YYYY-MM-DD)
  owner: ""         # GitHub username of project owner
  type: ""          # workshop | demo
  autonomy: supervised  # supervised | semi | full

lifecycle:
  current_phase: intake
  phases:
    intake:
      status: pending       # pending | in_progress | completed | skipped
      completed_at: null
      artifacts: []
    vetting:
      status: pending
      completed_at: null
      result: null           # approved | revise | rejected
      rcars_response: null
    spec_refinement:
      status: pending
      completed_at: null
    approval:
      status: pending
      approved_by: null
      completed_at: null
    writing:
      status: pending
      modules: []            # Populated during intake
      # Example module entry:
      # - name: "Module 1: Overview"
      #   status: pending    # pending | in_progress | drafted | approved
    editing:
      status: pending
    automation:
      status: pending
      needs_automation: null  # true | false — asked during intake
      substeps:
        catalog_item: pending
        requirements: pending
        automation_code: pending
        e2e_checks: deferred     # Future phase
    security_review:
      status: pending
    final_review:
      status: pending
    ready_for_publishing:
      status: pending

integrations:
  rcars_api: null            # URL to RCARS REST API (e.g., https://rcars.apps.example.com/api/v1)
  showroom_repo: null        # URL to public Showroom repo (set when content moves)
  automation_repo: null      # URL to automation repo (set when created)
```

- [ ] **Step 3: Validate manifest YAML parses correctly**

Run: `python3 -c "import yaml; yaml.safe_load(open('template/publishing-house/manifest.yaml')); print('Valid YAML')"`
Expected: `Valid YAML`

- [ ] **Step 4: Write empty journal.md**

Create `template/publishing-house/journal.md`:

```markdown
# Work Journal

<!-- Experimental: human-readable session log. The manifest is the source of truth. -->
<!-- Add entries in reverse chronological order (newest first). -->
<!-- Format:
## YYYY-MM-DD

### What was done
- Item

### Key decisions
- Decision

### Next up
- Item
-->
```

- [ ] **Step 5: Write blank design.md placeholder**

Create `template/publishing-house/spec/design.md`:

```markdown
# Project Design

<!-- This file is populated by the intake agent during the intake phase. -->
<!-- Run /rhdp-publishing-house to get started. -->
```

- [ ] **Step 6: Write SPEC-TEMPLATE.md**

Create `template/publishing-house/spec/SPEC-TEMPLATE.md`:

```markdown
# Spec Template Reference

This is a reference template. Do not edit this file directly.
The intake agent uses this format when generating your design and module outlines.

---

## Master Design (design.md)

### Project Name
<!-- Clear, descriptive name -->

### Problem Statement
<!-- What gap does this content fill? Why is it needed? 2-3 sentences. -->

### Target Audience
<!-- Who is this for? Role, experience level, what they already know. -->

### Learning Objectives
<!-- What will the learner be able to do after completing this? Bulleted list. -->

### Content Type
<!-- workshop | demo -->

### Products & Technologies
<!-- Official Red Hat product names. Bulleted list. -->

### Module Map
<!-- High-level overview of modules with estimated duration per module.
| Module | Title | Duration |
|--------|-------|----------|
| 1      | ...   | 15 min   |
-->

### Design Principles
<!-- Any specific pedagogical approach, constraints, or differentiators. -->

### Prerequisites
<!-- What the learner needs before starting. -->

### Success Criteria
<!-- How do we know the content is effective? -->

### Infrastructure Requirements
<!-- OCP cluster, RHEL VMs, specific operators, etc. -->

### Automation Needed
<!-- Yes/No. If yes, brief description of what needs to be automated. -->

---

## Module Outline (spec/modules/module-NN-title.md)

### Brief Overview
<!-- 3-4 sentences setting context for this module. -->

### Audience and Time
<!-- Target personas, prerequisites for this module, estimated duration. -->

### What You Will See, Learn, and Do

**See:**
- <!-- What the learner will observe -->

**Learn:**
- <!-- Concepts the learner will understand -->

**Do:**
- <!-- Hands-on activities the learner will perform -->

### Lab Structure
<!-- Named sections with time estimates.
| Section | Title | Duration |
|---------|-------|----------|
| 1       | ...   | 5 min    |
-->

### Detailed Steps
<!-- Numbered steps, granular enough for the writer agent.
1. Navigate to...
2. Click...
3. Run the command...
4. Observe that...
-->

### Key Takeaways
<!-- Concepts reinforced by this module. Bulleted list. -->

### Infrastructure Notes
<!-- Module-specific requirements, configuration details, tuning parameters. Optional. -->
```

- [ ] **Step 7: Write template CLAUDE.md**

Create `template/CLAUDE.md`:

```markdown
# Publishing House Project

## State
Project state tracked in [publishing-house/manifest.yaml](publishing-house/manifest.yaml).
Read it first every session.

## Journal (Experimental)
Human-readable progress in [publishing-house/journal.md](publishing-house/journal.md).

## Spec
Design spec in [publishing-house/spec/design.md](publishing-house/spec/design.md).
Module outlines in [publishing-house/spec/modules/](publishing-house/spec/modules/).

## Invoke
Run `/rhdp-publishing-house` to start or continue work.
```

- [ ] **Step 8: Write template .gitignore**

Create `template/.gitignore`:

```
.superpowers/
```

- [ ] **Step 9: Write template README.md**

Create `template/README.md`:

```markdown
# [Project Name]

<!-- Replace with your project name and brief description. -->

## Getting Started

1. Install the RHDP Publishing House plugin in Claude Code
2. Run `/rhdp-publishing-house` in this directory
3. Follow the orchestrator's guidance

## Structure

- `publishing-house/` — Project state, specs, reviews, decisions
- `content/` — Showroom AsciiDoc content (populated by writer agent)
- `automation/` — Ansible/Helm automation (populated by automation agent)
- `agnosticv/` — AgnosticV catalog config (populated by automation agent)
```

- [ ] **Step 10: Commit**

```bash
git add template/
git commit -m "Add template repo structure for publishing house projects"
```

---

### Task 4: Orchestrator SKILL.md

**Files:**
- Create: `skills/orchestrator/SKILL.md`

- [ ] **Step 1: Create skills directory**

```bash
mkdir -p skills/orchestrator
```

- [ ] **Step 2: Write orchestrator SKILL.md**

Create `skills/orchestrator/SKILL.md`:

```markdown
---
name: rhdp-publishing-house:orchestrator
description: This skill should be used when the user asks to "start a publishing house project", "continue my lab project", "check project status", "what's next on my lab", or invokes "/rhdp-publishing-house". It is the main entry point for RHDP Publishing House — reads project state and orchestrates the content lifecycle.
---

---
context: main
model: claude-opus-4-6
---

# RHDP Publishing House — Orchestrator

You are the orchestrator for RHDP Publishing House. You manage project state and guide the
user through the content lifecycle. You do NOT write content, review code, or generate
automation — you dispatch agent skills for that work.

See @rhdp-publishing-house/docs/PH-COMMON-RULES.md for shared rules.

## Arguments

```
/rhdp-publishing-house                  # Default: supervised autonomy
/rhdp-publishing-house supervised       # Explicit supervised
/rhdp-publishing-house semi             # Semi-autonomous
/rhdp-publishing-house full             # Fully autonomous within phases
```

If an argument is provided, update `project.autonomy` in the manifest.

## Step 1: Project Discovery (Silent)

Look for `publishing-house/manifest.yaml` in the current working directory.

**If found:** Read it and proceed to Step 2.

**If not found:** Ask the user:
> "I don't see a Publishing House project in this directory. Where is your project located?"

If the user provides a path, read the manifest from that path. Remember the path for this session.

**If no manifest exists anywhere:** Tell the user:
> "No Publishing House project found. To start a new project, clone the template repo and run this command from within it:
> `gh repo create <your-repo-name> --template rhpds/rhdp-publishing-house-template --private --clone`
> Then run `/rhdp-publishing-house` again from inside the cloned directory."

Stop here — do not proceed without a manifest.

## Step 2: Read State and Present Status

Read `publishing-house/manifest.yaml`. Parse:
- `project.name`, `project.owner`, `project.type`, `project.autonomy`
- `lifecycle.current_phase`
- Status of each phase in `lifecycle.phases`
- Module-level progress if in writing phase

**If manifest is fresh** (all phases pending, `project.name` is empty):
Present:
> "New Publishing House project detected. Let's get started.
> Do you have a spec or design document already, or would you like help creating one?"

Then invoke the intake agent: tell the user you are starting the intake phase and invoke `/rhdp-publishing-house:intake`.

**If project is in progress:**
Present a concise status summary. Format:

> "**[Project Name]** — [content type]
> **Current phase:** [phase name]
> **Autonomy:** [level]
>
> **Progress:**
> - Intake: [status]
> - Vetting: [status]
> - ...
> - [Current phase details — e.g., module-level progress for writing]
>
> **Suggested next:** [specific recommended action]
>
> What would you like to do?"

## Step 3: Route User Intent

Listen for the user's request and route to the appropriate action:

### Phase-specific commands
| User says (or similar) | Action |
|------------------------|--------|
| "start intake" / "create spec" / "I have an idea" | Invoke `/rhdp-publishing-house:intake` |
| "write module N" / "start writing" | Invoke `/rhdp-publishing-house:writer` *(Phase 2 — not yet available)* |
| "edit" / "review content" / "technical edit" | Invoke `/rhdp-publishing-house:editor` *(Phase 2 — not yet available)* |
| "create catalog" / "write automation" | Invoke `/rhdp-publishing-house:automation` *(Phase 3 — not yet available)* |
| "security review" | Invoke `/rhdp-publishing-house:security` *(Phase 4 — not yet available)* |
| "final review" | Invoke `/rhdp-publishing-house:review` *(Phase 4 — not yet available)* |

### State management commands
| User says | Action |
|-----------|--------|
| "what's next" / "next" | Re-read manifest, recommend next action based on current phase |
| "status" / "where are we" | Re-read manifest, present full status summary |
| "switch to supervised/semi/full" | Update `project.autonomy` in manifest, confirm |
| "approve" / "looks good" / "proceed" | If at approval gate, update manifest and advance phase |

### Guard Rails

- **Phase ordering:** Do not allow out-of-order operations. If the user asks to write content but intake isn't complete, say: "Intake phase needs to complete first. Would you like to continue with intake?"
- **Unavailable agents:** If user requests an agent that doesn't exist yet (Phase 2-4), say: "The [agent name] agent isn't available yet — it's coming in a future phase. Here's what you can do now: [list available actions]."
- **Approval gate:** The approval phase (phase 4) always requires explicit human approval. Never auto-advance past it.

## Step 4: Post-Agent Update

After an agent skill completes its work:

1. Re-read the manifest (the agent may have updated it)
2. Present a brief summary of what was accomplished
3. Recommend the next action
4. If the completed phase has a gate, pause for user decision

## Manifest Update Rules

When updating the manifest:
- Set `lifecycle.current_phase` to the active phase
- Set phase `status` to `in_progress` when starting, `completed` when done
- Set `completed_at` to today's date (YYYY-MM-DD) when completing a phase
- Add artifact paths to the phase's `artifacts` list when files are created
- Never delete or overwrite data from completed phases

## Session End

When the user ends the session or conversation:
- Ensure the manifest reflects the current state
- Update the work journal (`publishing-house/journal.md`) with a brief session summary if the experimental journal exists
```

- [ ] **Step 3: Validate SKILL.md frontmatter**

Run: `python3 -c "
content = open('skills/orchestrator/SKILL.md').read()
blocks = content.split('---')
# blocks[0] is empty (before first ---), blocks[1] is first frontmatter, blocks[2] is between, blocks[3] is second frontmatter
import yaml
fm1 = yaml.safe_load(blocks[1])
fm2 = yaml.safe_load(blocks[3])
assert fm1['name'] == 'rhdp-publishing-house:orchestrator', f'Bad name: {fm1[\"name\"]}'
assert 'description' in fm1, 'Missing description'
assert fm2['context'] == 'main', f'Bad context: {fm2[\"context\"]}'
assert fm2['model'] == 'claude-opus-4-6', f'Bad model: {fm2[\"model\"]}'
print('Orchestrator SKILL.md frontmatter: VALID')
"`
Expected: `Orchestrator SKILL.md frontmatter: VALID`

- [ ] **Step 4: Commit**

```bash
git add skills/orchestrator/SKILL.md
git commit -m "Add orchestrator skill — entry point and state management"
```

---

### Task 5: Intake Agent SKILL.md

**Files:**
- Create: `skills/intake/SKILL.md`

- [ ] **Step 1: Create intake directory**

```bash
mkdir -p skills/intake/references
```

- [ ] **Step 2: Write intake SKILL.md**

Create `skills/intake/SKILL.md`:

```markdown
---
name: rhdp-publishing-house:intake
description: This skill should be used when the user asks to "create a spec", "write a design doc", "start a new lab project", "I have an idea for a lab", "vet this against existing content", or "refine the spec". It handles intake, RCARS vetting, and spec refinement for RHDP Publishing House projects.
---

---
context: main
model: claude-opus-4-6
---

# RHDP Publishing House — Intake Agent

You handle the first three phases of the Publishing House lifecycle:
1. **Intake** — Generate or ingest the project spec
2. **Vetting** — Check against existing RHDP content via RCARS
3. **Spec Refinement** — Clean up and standardize for downstream agents

See @rhdp-publishing-house/docs/PH-COMMON-RULES.md for shared rules.

## Before Starting

Read `publishing-house/manifest.yaml` to understand current state.
Read @rhdp-publishing-house/skills/intake/references/spec-guidelines.md for spec quality criteria.
Read @rhdp-publishing-house/skills/intake/references/module-outline-template.md for the module outline format.

Check `project.autonomy` and adjust your behavior accordingly (see common rules).

## Phase 1: Intake

### Detect Entry Path

Ask the user ONE question:

> "How would you like to start?
> 1. **I have a spec/design doc** — provide a file path or paste it
> 2. **I have an idea** — describe it and I'll help build the spec
> 3. **Fill a content gap** — provide a topic or gap description"

### Path A: Full Spec Provided

1. Read the provided document (file path, pasted content, or Google Doc via `gws cat <url>`)
2. Parse it against the spec template format (see references/spec-guidelines.md)
3. Identify any missing sections or gaps
4. Ask the user about each gap, ONE question at a time:
   - "The spec doesn't mention target audience. Who is this content for?"
   - "What products/technologies does this cover?"
   - "Do you need automation for the lab environment, or do you already have that handled?"
5. Write the normalized spec to `publishing-house/spec/design.md`
6. Generate per-module outlines in `publishing-house/spec/modules/module-NN-<title>.md`
7. Update manifest: set `lifecycle.phases.intake.status: completed`, add artifacts list

### Path B: Rough Idea

Ask questions ONE at a time to build the spec. Follow this order:

1. "What's the main goal? What should someone be able to do after completing this?"
2. "Who is the target audience? (e.g., platform engineers, developers, operations)"
3. "Which Red Hat products or technologies does this involve?"
4. "Is this a hands-on workshop or a presenter-led demo?"
5. "How long should the total experience be? (e.g., 30 min, 1 hour, 2 hours)"
6. "How many modules do you envision? Give me a rough outline — even just titles."
7. "What difficulty level? (beginner, intermediate, advanced)"
8. "Do you need automation to set up the lab environment, or will you provide that?"

After gathering answers, generate:
- `publishing-house/spec/design.md` — master design doc
- `publishing-house/spec/modules/module-NN-<title>.md` — per-module outlines

Present the design to the user for initial feedback before writing files (in supervised mode)
or write directly and present a summary (in semi/full mode).

Update manifest: set intake status to completed, add artifact paths.

### Path C: RCARS Gap / Topic Seed

The user provides a brief description (could be a single sentence from RCARS gap analysis).

1. Take the gap description as the seed
2. Ask clarifying questions to fill out the spec, same as Path B but starting from the gap:
   - "RCARS identified a gap in '[topic]'. Let's build a spec for this."
   - Then follow Path B questions, pre-filling what can be inferred from the gap description
3. Generate design.md and module outlines as in Path B

### Spec Output Rules

When writing `publishing-house/spec/design.md`:
- Follow the template format from @rhdp-publishing-house/skills/intake/references/spec-guidelines.md
- Be specific and concrete — no vague objectives like "understand the basics"
- Learning objectives must start with action verbs (Configure, Deploy, Create, Troubleshoot)
- Include infrastructure requirements section
- Include the `needs_automation` decision

When writing module outlines in `publishing-house/spec/modules/`:
- File naming: `module-01-<short-title>.md`, `module-02-<short-title>.md`, etc.
- Follow the format from @rhdp-publishing-house/skills/intake/references/module-outline-template.md
- Include See/Learn/Do breakdown
- Include time estimates per section
- Include numbered detailed steps — granular enough for the writer agent
- Scale granularity with complexity (80 lines for simple modules, up to 300 for complex)

### Manifest Update After Intake

```yaml
lifecycle:
  current_phase: vetting
  phases:
    intake:
      status: completed
      completed_at: "2026-04-09"  # Today's date
      artifacts:
        - publishing-house/spec/design.md
        - publishing-house/spec/modules/module-01-<title>.md
        - publishing-house/spec/modules/module-02-<title>.md
```

Also populate:
- `project.name` — from the spec
- `project.id` — short kebab-case identifier derived from name
- `project.created` — today's date
- `project.type` — workshop or demo
- `lifecycle.phases.writing.modules` — list of modules with status: pending
- `lifecycle.phases.automation.needs_automation` — from user's answer

## Phase 2: Vetting (RCARS)

After intake is complete, move to vetting.

### Check RCARS Availability

Read `integrations.rcars_api` from manifest.

**If null or empty:** Ask the user:
> "RCARS API URL is not configured. Would you like to:
> 1. Provide the RCARS API URL
> 2. Skip vetting and proceed to spec refinement"

If they provide a URL, update `integrations.rcars_api` in the manifest.
If they skip, set `lifecycle.phases.vetting.status: skipped` and proceed to Phase 3.

### Call RCARS API

Construct a request to the RCARS API:

```bash
curl -s -X POST "${RCARS_API}/recommend" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "<learning objectives + topics + products from spec>",
    "limit": 10
  }'
```

Parse the response. Extract:
- `recommendations` — existing content that overlaps
- `content_gaps` — topics not covered by existing content
- `overall_assessment` — summary of coverage

### Present Vetting Results

Write the raw results to `publishing-house/reviews/rcars-vetting.md` in a readable format.

Present to the user:

> "**RCARS Vetting Results:**
>
> **Overlap:** [list any overlapping content with similarity notes]
> **Gaps confirmed:** [list gaps that validate this project]
> **Assessment:** [1-2 sentence summary]
>
> **Recommendation:** [proceed / differentiate / reconsider]"

### Determine Outcome

- **Gap confirmed** (no significant overlap): Set vetting result to `approved`, proceed
- **Partial overlap** (similar content exists): Set result to `revise`, note what needs differentiation. Proceed to spec refinement with specific guidance on how to differentiate.
- **Already covered** (existing content handles this): Set result to `rejected`, recommend enhancing existing content instead. Ask user how to proceed.

### Manifest Update After Vetting

```yaml
lifecycle:
  current_phase: spec_refinement
  phases:
    vetting:
      status: completed
      completed_at: "2026-04-09"
      result: approved  # or revise or rejected
      rcars_response: publishing-house/reviews/rcars-vetting.md
```

## Phase 3: Spec Refinement

After vetting, refine the spec and module outlines.

### Refinement Goals

1. **Incorporate RCARS feedback** — if vetting found partial overlap, adjust the spec to differentiate
2. **Clarity for downstream agents** — rewrite any ambiguous sections so the writer agent can produce content without guessing
3. **Standardize format** — ensure all module outlines follow the See/Learn/Do format with timing and numbered steps
4. **Conciseness** — remove redundancy, tighten language, make instructions machine-actionable

### Refinement Process

1. Re-read `publishing-house/spec/design.md` and all module outlines
2. If RCARS flagged overlap, revise the spec to sharpen differentiation:
   - Adjust learning objectives to focus on unique angles
   - Note in design.md what existing content covers and how this project differs
3. Review each module outline for:
   - Missing See/Learn/Do sections → add them
   - Vague steps ("configure the application") → make specific ("run `oc apply -f config.yaml`")
   - Missing time estimates → add them
   - Missing infrastructure notes → add if applicable
4. Update the files in place
5. Present a summary of changes to the user

### Autonomy Behavior

- **Supervised:** Present each proposed change and ask for approval before writing
- **Semi:** Make all changes, present a summary, ask if anything needs revision
- **Full:** Make all changes, present a brief summary, proceed

### Manifest Update After Refinement

```yaml
lifecycle:
  current_phase: approval
  phases:
    spec_refinement:
      status: completed
      completed_at: "2026-04-09"
```

## After Refinement: Hand Back to Orchestrator

After completing spec refinement, inform the user:

> "Spec refinement complete. The project is now ready for approval.
> Please review:
> - Design: `publishing-house/spec/design.md`
> - Module outlines: `publishing-house/spec/modules/`
>
> When you're satisfied, tell the orchestrator to approve and proceed to writing."

Do not advance past approval — that is a human gate managed by the orchestrator.
```

- [ ] **Step 3: Validate SKILL.md frontmatter**

Run: `python3 -c "
content = open('skills/intake/SKILL.md').read()
blocks = content.split('---')
import yaml
fm1 = yaml.safe_load(blocks[1])
fm2 = yaml.safe_load(blocks[3])
assert fm1['name'] == 'rhdp-publishing-house:intake', f'Bad name: {fm1[\"name\"]}'
assert 'description' in fm1, 'Missing description'
assert fm2['context'] == 'main', f'Bad context: {fm2[\"context\"]}'
assert fm2['model'] == 'claude-opus-4-6', f'Bad model: {fm2[\"model\"]}'
print('Intake SKILL.md frontmatter: VALID')
"`
Expected: `Intake SKILL.md frontmatter: VALID`

- [ ] **Step 4: Commit**

```bash
git add skills/intake/SKILL.md
git commit -m "Add intake agent skill — spec generation, RCARS vetting, refinement"
```

---

### Task 6: Intake Agent Reference Documents

**Files:**
- Create: `skills/intake/references/spec-guidelines.md`
- Create: `skills/intake/references/module-outline-template.md`

- [ ] **Step 1: Write spec-guidelines.md**

Create `skills/intake/references/spec-guidelines.md`:

```markdown
# Spec Quality Guidelines

Guidelines for evaluating and generating project specs. Used by the intake agent.

## Required Sections in design.md

A complete spec MUST have all of these:

1. **Project Name** — clear, descriptive
2. **Problem Statement** — what gap this fills, why it's needed (2-3 sentences)
3. **Target Audience** — role, experience level, what they already know
4. **Learning Objectives** — action-verb list (Configure, Deploy, Create, Troubleshoot)
5. **Content Type** — workshop or demo
6. **Products & Technologies** — official Red Hat product names
7. **Module Map** — table with module number, title, estimated duration
8. **Prerequisites** — what the learner needs before starting
9. **Infrastructure Requirements** — cluster type, operators, VMs, etc.
10. **Automation Needed** — yes/no with brief description if yes

## Optional Sections

- Design Principles — pedagogical approach, constraints
- Success Criteria — how to measure effectiveness
- Differentiation — how this differs from existing content (especially after RCARS vetting)

## Quality Checks

### Learning Objectives
- Start with action verbs: Configure, Deploy, Create, Implement, Troubleshoot, Monitor, Scale
- NOT: Understand, Learn, Know, Be familiar with (too vague)
- Each objective should be testable — could you write a validation check for it?

### Problem Statement
- Specific, not generic — "Platform engineers need to configure ServiceMesh mTLS but existing docs only cover Istio basics" NOT "People need to learn ServiceMesh"
- References a real persona with a real need

### Module Map
- Each module should be 10-30 minutes
- Total duration should match content type (workshop: 1-4 hours, demo: 15-45 minutes)
- Modules should build on each other logically

### Products & Technologies
- Use official Red Hat product names (Red Hat OpenShift, not just OpenShift)
- Include version if relevant to the content
- List upstream projects separately if the content covers them

### Infrastructure Requirements
- Be specific: "OCP 4.14+ cluster with 3 worker nodes" not just "OpenShift cluster"
- List operators needed
- Note any cloud provider requirements
- Note any minimum resource requirements
```

- [ ] **Step 2: Write module-outline-template.md**

Create `skills/intake/references/module-outline-template.md`:

```markdown
# Module Outline Template

Template for per-module outlines in `publishing-house/spec/modules/`. Each module gets its
own file: `module-01-<short-title>.md`, `module-02-<short-title>.md`, etc.

Granularity scales with complexity:
- Simple module (single concept, guided walkthrough): ~80-120 lines
- Medium module (multiple sections, some exploration): ~120-200 lines
- Complex module (multiple demos, infrastructure changes): ~200-300 lines

---

## Template

```markdown
# Module N: [Title]

## Brief Overview

[3-4 sentences setting context. What problem does this module address?
How does it connect to previous modules? What will the learner accomplish?]

## Audience and Time

- **Target personas:** [e.g., platform engineers, developers]
- **Prerequisites:** [what they need from prior modules or general knowledge]
- **Estimated duration:** [total time for this module]

## What You Will See, Learn, and Do

**See:**
- [What the learner will observe — outputs, dashboards, behaviors]

**Learn:**
- [Concepts the learner will understand after this module]

**Do:**
- [Hands-on activities the learner will perform]

## Lab Structure

| Section | Title | Duration |
|---------|-------|----------|
| 1       | [Name] | [X min] |
| 2       | [Name] | [X min] |
| 3       | [Name] | [X min] |

## Detailed Steps

### Section 1: [Title]

1. [Specific step — what to do, where to go]
2. [Next step — include commands if applicable]
3. [Observation step — what they should see]
4. ...

### Section 2: [Title]

5. [Steps continue numbering across sections]
6. ...

## Key Takeaways

- [Concept 1 reinforced by this module]
- [Concept 2]
- [How this connects to the next module]

## Infrastructure Notes

<!-- Optional — only include if this module has specific infrastructure requirements,
     tuning parameters, or configuration details beyond the project-level requirements. -->

- [Requirement or configuration detail]
```

---

## Examples of Good Step Granularity

**Too vague (bad):**
> 3. Configure the application for high availability

**Right level (good):**
> 3. Open the deployment configuration:
>    `oc edit deployment/my-app -n demo`
> 4. Set replicas to 3 under `spec.replicas`
> 5. Save and exit. Verify pods are scaling:
>    `oc get pods -n demo -w`
> 6. Observe 3 pods reaching Ready state (takes ~30 seconds)

**Too detailed (also bad for an outline — save this for actual content):**
> 3. Click the terminal icon in the top-right corner of the Showroom interface
> 4. In the terminal, type `oc` and press Enter to verify the CLI is available
> 5. You should see the OpenShift CLI help text starting with "OpenShift Client"

The outline should give the writer agent enough to work with, but not write the
actual AsciiDoc content. The writer agent handles prose, formatting, and pedagogy.
```

- [ ] **Step 3: Commit**

```bash
git add skills/intake/references/
git commit -m "Add intake agent reference docs — spec guidelines and module outline template"
```

---

### Task 7: Getting Started Guide

**Files:**
- Create: `docs/getting-started.md`

- [ ] **Step 1: Write getting-started.md**

Create `docs/getting-started.md`:

```markdown
# Getting Started with RHDP Publishing House

## Prerequisites

- Claude Code with the RHDP Skills Marketplace installed
- The `rhdp-publishing-house` plugin enabled
- A GitHub account with access to the `rhpds` org (for creating project repos)

## Quick Start

### 1. Create a project repo

Clone the template:

```bash
gh repo create my-new-lab \
  --template rhpds/rhdp-publishing-house-template \
  --private --clone
cd my-new-lab
```

### 2. Start the orchestrator

```bash
# In Claude Code, from inside your project directory:
/rhdp-publishing-house
```

The orchestrator detects a fresh project and walks you through intake.

### 3. Follow the orchestrator

The orchestrator guides you through each phase:
- **Intake** — build your spec (bring one or create from scratch)
- **Vetting** — check against existing RHDP content via RCARS
- **Spec Refinement** — clean up for downstream agents
- **Approval** — you review and approve the spec
- **Writing → Editing → Automation → Security → Review → Ready**

At any point, ask "what's next" and the orchestrator tells you where you are
and what to do.

### 4. Collaborate

Push your repo. A colleague clones it, runs `/rhdp-publishing-house`, and picks
up exactly where you left off. The manifest tracks everything.

## Autonomy Levels

Control how much review you want:

```
/rhdp-publishing-house              # supervised (default) — review everything
/rhdp-publishing-house semi         # review at phase gates only
/rhdp-publishing-house full         # review at phase completion
```

Switch mid-session: "switch to semi"

## Tips

- The manifest (`publishing-house/manifest.yaml`) is the source of truth — don't edit it manually
- Module outlines in `publishing-house/spec/modules/` drive the writing phase — invest time making them good
- If RCARS API isn't available, you can skip vetting and come back to it later
```

- [ ] **Step 2: Commit**

```bash
git add docs/getting-started.md
git commit -m "Add getting started guide"
```

---

### Task 8: Smoke Test — End-to-End Structure Validation

**Files:**
- None created — validation only

- [ ] **Step 1: Validate complete plugin structure**

Run: `find . -not -path './.git/*' -not -path './.superpowers/*' -not -name '.DS_Store' | sort`

Expected output should include:
```
.
./.claude-plugin/plugin.json
./.gitignore
./README.md
./docs/PH-COMMON-RULES.md
./docs/executive-summary.md
./docs/getting-started.md
./docs/superpowers/specs/2026-04-09-rhdp-publishing-house-design.md
./skills/intake/SKILL.md
./skills/intake/references/module-outline-template.md
./skills/intake/references/spec-guidelines.md
./skills/orchestrator/SKILL.md
./template/...
```

- [ ] **Step 2: Validate all YAML files parse**

Run: `python3 -c "
import yaml, json, pathlib
errors = []
for f in pathlib.Path('.').rglob('*.yaml'):
    if '.git' in str(f): continue
    try:
        yaml.safe_load(f.read_text())
    except Exception as e:
        errors.append(f'{f}: {e}')
for f in pathlib.Path('.').rglob('*.json'):
    if '.git' in str(f): continue
    try:
        json.loads(f.read_text())
    except Exception as e:
        errors.append(f'{f}: {e}')
if errors:
    print('ERRORS:')
    for e in errors: print(f'  {e}')
else:
    print('All YAML/JSON files: VALID')
"`
Expected: `All YAML/JSON files: VALID`

- [ ] **Step 3: Validate SKILL.md frontmatter for all skills**

Run: `python3 -c "
import yaml, pathlib
for skill_file in pathlib.Path('skills').rglob('SKILL.md'):
    content = skill_file.read_text()
    blocks = content.split('---')
    fm1 = yaml.safe_load(blocks[1])
    fm2 = yaml.safe_load(blocks[3])
    assert 'name' in fm1, f'{skill_file}: missing name'
    assert 'description' in fm1, f'{skill_file}: missing description'
    assert fm1['name'].startswith('rhdp-publishing-house:'), f'{skill_file}: bad namespace'
    assert fm2.get('context') == 'main', f'{skill_file}: bad context'
    assert fm2.get('model') == 'claude-opus-4-6', f'{skill_file}: bad model'
    print(f'{skill_file}: VALID ({fm1[\"name\"]})')
"`
Expected:
```
skills/orchestrator/SKILL.md: VALID (rhdp-publishing-house:orchestrator)
skills/intake/SKILL.md: VALID (rhdp-publishing-house:intake)
```

- [ ] **Step 4: Verify git history is clean**

Run: `git status && git log --oneline`
Expected: Clean working tree, commits for each task.

- [ ] **Step 5: Tag Phase 1 complete**

```bash
git tag v0.1.0-phase1 -m "Phase 1: Plugin scaffold, orchestrator, intake agent"
```

---

## Phase 1 Deliverables Summary

| Deliverable | Status | Notes |
|------------|--------|-------|
| Plugin scaffold (plugin.json, README) | Task 1 | Marketplace-compatible |
| Common rules document | Task 2 | Shared across all PH skills |
| Template repo structure | Task 3 | Ready to move to GitHub template repo |
| Orchestrator SKILL.md | Task 4 | Entry point, state management, routing |
| Intake agent SKILL.md | Task 5 | Three intake paths, RCARS vetting, spec refinement |
| Intake references | Task 6 | Spec guidelines + module outline template |
| Getting started guide | Task 7 | Concise user-facing docs |
| Structure validation | Task 8 | All files valid, clean git history |

## What's Next (Phase 2)

- Writer agent SKILL.md (wraps `showroom:create-lab`, `showroom:create-demo`)
- Editor agent SKILL.md (wraps `showroom:verify-content`)
- End-to-end test: intake through writing on a real project
