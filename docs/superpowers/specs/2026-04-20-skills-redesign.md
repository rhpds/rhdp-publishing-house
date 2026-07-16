# Publishing House Skills Redesign

**Date:** 2026-04-20
**Status:** Draft
**Author:** Nate Stephany + Claude

## Summary

Redesign the PH skills to support deployment modes (rhdp_published vs self_published), add worklog management, reduce token waste for status queries, and clean up references for the published skills repo. These changes affect all five skills (orchestrator, intake, writer, editor, automation) plus a new worklog skill.

## Goals

1. **Deployment mode awareness** — Skills know whether a project is `rhdp_published` or `self_published` and constrain options accordingly.
2. **Smart intake** — Don't ask questions that are already answered in provided docs.
3. **Worklog management** — Read, write, expand, and squash worklog entries across sessions.
4. **Token efficiency** — Status queries read local files directly; heavy prompts load only for creative work.
5. **Clean published skills** — No broken references, no dev-repo dependencies, self-contained plugin.

## Non-Goals

- Portal/MCP implementation (separate spec and plan)
- RCARS vetting API integration
- New automation approaches for self_published (Ansible Runner within GitOps is the pattern for now)
- Full code review in automation phase (separate phase gate)

## Deployment Modes

Two deployment modes set during intake, stored in `project.deployment_mode`:

| Mode | Meaning | Automation Approach | AgnosticV | Code Review |
|------|---------|-------------------|-----------|-------------|
| `rhdp_published` | Full RHDP onboarding. Published in catalog with its own CI. Must be fully approved and have end-to-end automated testing of environment and all user activities. | Ansible, GitOps, or both (user chooses) | Required at 7b (access permitting) | Required (separate phase) |
| `self_published` | Self-managed. Deployed via generic Field Source CI (`agd_v2/ocp-field-asset-cnv`). | GitOps only (Helm + ArgoCD). Ansible Runner jobs available within GitOps. | Skipped (no catalog item) | Recommended, not required |

## Changes by Skill

### 1. All Skills — Reference Cleanup

**Remove all `@rhdp-publishing-house/docs/PH-COMMON-RULES.md` references.** The principles in PH-COMMON-RULES are already reflected in each skill's own instructions. Any missing principles are added directly to the skill that needs them. The file stays in the dev repo as a development guideline for skill authors.

**Files affected:**
- `skills/orchestrator/SKILL.md` — lines 15, 151
- `skills/intake/SKILL.md` — line 19
- `skills/writer/SKILL.md` — line 17
- `skills/editor/SKILL.md` — line 17
- `skills/automation/SKILL.md` — line 18

**`@rhdp-publishing-house/skills/...` references are fine** — the plugin name in `plugin.json` is `rhdp-publishing-house`, so these resolve correctly within the published skills repo.

### 2. Intake Skill

**Add deployment mode question:**

After the existing project type question (workshop/demo), add:

> "Are you building this to fully onboard to RHDP (`rhdp_published`) or self-publishing (`self_published`)?"
>
> **RHDP Published:** Goes through the full pipeline — AgnosticV catalog, reviews, published as a standalone item in the RHDP catalog.
>
> **Self-Published:** You manage deployment yourself. Automation is built as a GitOps repo. You order the generic Field Source CI and provide your repo URL. Faster, but not in the catalog.

Record in manifest as `project.deployment_mode: rhdp_published | self_published`.

**Repo setup guidance during intake:**

After the project repo is established (cloned from template), the intake skill should:

1. Advise the user: "Your project repo should remain **private** by default — it may contain sensitive comments, design decisions, and internal notes. The Showroom and automation repos should be **public** (or at least accessible to anyone who needs to deploy the content)."

2. Prompt the user to create or provide the Showroom and automation repos:
   > "I need your Showroom content repo and automation repo URLs. These are cloned into your project workspace as subdirectories. If you haven't created them yet, you can do so now:
   > ```
   > gh repo create <org>/<project>-showroom --public --clone
   > gh repo create <org>/<project>-automation --public --clone
   > ```
   > Or provide existing repo URLs if you have them."

3. Record the URLs in the manifest under `integrations.showroom_repo` and `integrations.automation_repo`.

4. Clone the repos into the workspace's `content/` and `automation/` directories if not already present.

**Smart intake — consume whatever the user provides:**

The user may provide a `design.md`, a `manifest.yaml`, a Google Doc, a rough outline, meeting notes, or anything else. The intake skill should handle whatever it gets:

1. Read and parse whatever documents the user provides (any format)
2. Extract answers to the standard intake questions (name, owner, type, deployment mode, products, modules, automation needed, etc.)
3. Normalize the extracted information into the proper PH format (design.md, module outlines, manifest fields)
4. Present what was found: "I found the following in your docs — does this look right?"
5. Only ask questions for fields that are missing or ambiguous
6. Still validate (required fields present, learning objectives use action verbs, etc.)

If all answers are present in the provided docs, intake becomes a confirmation step, not a 9+ question interview.

If parsed values conflict between documents (e.g., one doc says "workshop" but another says "demo"), present the conflict and ask the user to resolve it.

**Manifest output update:**

The intake manifest template adds:

```yaml
project:
  deployment_mode: ""  # rhdp_published | self_published
```

### 3. Automation Skill

**Three changes:**

#### 3a. Approach constrained by deployment mode

When `deployment_mode: self_published`:
- Approach is GitOps only. The skill explains why:
  > "Self-published projects use the Field Source CI, which expects a GitOps repo. Your automation approach is GitOps (Helm + ArgoCD). If you need Ansible tasks, they can run as Ansible Runner jobs within the GitOps framework."
- Reference the field-sourced-content-template at `https://github.com/rhpds/field-sourced-content-template` for the starter pattern, including the `examples/ansible` path for Ansible Runner within GitOps.

When `deployment_mode: rhdp_published`:
- Ask the user: "How should the environment be automated?"
  - **Ansible** — Ansible collections as AgnosticD workloads
  - **GitOps** — Helm charts deployed by ArgoCD
  - **Both** — Ansible for cluster-level setup, GitOps for application workloads

#### 3b. AgnosticV handling at 7b

When `deployment_mode: self_published`:
- 7b is automatically skipped: `substeps.catalog_item: skipped`
- Skill informs user: "No AgnosticV catalog item needed for self-published projects."

When `deployment_mode: rhdp_published`:
- 7b is required. When the skill reaches it, ask:
  > "An AgnosticV catalog item is required for RHDP-published projects. Do you have AgnosticV access to create it, or does someone else need to handle this?"
- If user has access → proceed with agnosticv:catalog-builder as today
- If user doesn't have access → set `substeps.catalog_item: pending_handoff` with a worklog entry noting who needs to create it. The skill provides the information needed for handoff (infrastructure type, operators, multi-user config from the approved automation manifest).

#### 3c. Code review in 7c simplified

Remove the conditional `code-review:code-review` PR-based review from 7c. Replace with a concrete safety checklist:

**"Don't hurt yourself" checklist:**
- No hardcoded credentials, passwords, or API keys (use variables or vault)
- Container images use pinned tags (not `latest`)
- Workload references in `common.yaml` match created roles/charts
- Collection dependencies in `requirements_content` are satisfied
- No secrets in plain text in templates or defaults
- Variables follow naming conventions (`ocp4_workload_<project>_*`)

Plus: re-run `agnosticv:validator` (if catalog item exists) to verify consistency.

The real code review happens in the Code & Security Review phase — a separate gate with proper PR-based review.

#### 3d. Language updates

Replace all "Field Source Content" references with "self-published" language:
- `skills/automation/SKILL.md` — 5 locations
- `skills/automation/references/automation-patterns.md` — 1 location

### 4. Worklog Skill (New)

**New skill:** `skills/worklog/SKILL.md`

**Invocation:** `/rhdp-publishing-house:worklog`

**Purpose:** Manage the human-context layer between sessions and people. Read, write, expand, resolve, and squash worklog entries in `publishing-house/worklog.yaml`.

**Trigger phrases:** "leave a note", "what's outstanding", "worklog", "resolve item", "what did we do last session"

**Capabilities:**

| Command | Action |
|---------|--------|
| View open items | Read `worklog.yaml`, filter entries with `status: open`, present list |
| Add a note | User provides terse input, skill expands with LLM into a readable entry with timestamp, author, type classification |
| Resolve an item | Mark an entry as `status: resolved` with `resolved_at` and `resolved_by` |
| Session summary | Write a summary entry capturing what was accomplished and what's open |
| Squash | Compress old resolved entries (>1 week, or when file exceeds ~30 entries) into summary entries |

**Worklog file format:**

```yaml
# Publishing House Worklog
# Human context, decisions, and notes that bridge sessions and people.
# Not a task tracker — the manifest tracks structured progress.

entries:
  - id: "2026-04-15-001"
    timestamp: "2026-04-15T14:30:00Z"
    author: "sborenst"
    status: open          # open | resolved
    type: decision        # note | decision | handoff | action
    content: "Need to decide on DataSphere vs Parksmap for module 2 demo app. DataSphere is newer but Parksmap has more community examples."

  - id: "2026-04-14-001"
    timestamp: "2026-04-14T10:00:00Z"
    author: "sborenst"
    status: resolved
    type: action
    content: "Check with Prakhar on CNV pool sizing for multi-user deployments."
    resolved_at: "2026-04-15T09:00:00Z"
    resolved_by: "sborenst"

  # Squashed summary
  - id: "summary-2026-04-10"
    timestamp: "2026-04-10T00:00:00Z"
    author: "system"
    status: resolved
    type: summary
    content: "April 10: Project created. Intake completed — 5-module workshop design approved. Spec refinement normalized design doc. Automation catalog and requirements completed."
```

**Entry type classification:**
- `note` — general observation, context for future sessions
- `decision` — something that needs to be decided (open) or was decided (resolved)
- `handoff` — work being handed to someone else, includes context they need
- `action` — something that needs to be done outside of PH (check with someone, test something)
- `summary` — compressed history from squashing

**Design principle:** The worklog skill is lightweight. It reads/writes a YAML file. The LLM assistance is in expanding terse notes and writing good summaries — not in complex logic.

**Git workflow:** After writing entries, the skill commits and pushes `worklog.yaml`. The portal's refresh engine picks it up on the next cycle.

### 5. Orchestrator Skill

**Two changes:**

#### 5a. Token-efficient status path

Add explicit instructions at the top of the orchestrator:

> **For status queries** ("what's my status?", "what's next?", "where are we?"):
> Read `publishing-house/manifest.yaml` and `publishing-house/worklog.yaml` directly. Parse the YAML. Present the current phase, substep status, open worklog items, and suggested next action. Do NOT load reference docs or dispatch to other skills. This must be cheap.

> **For work queries** ("start writing", "build automation", "run the editor"):
> Load the full routing logic, check phase dependencies, and dispatch to the appropriate skill.

This creates two tiers of orchestrator invocation — lightweight for status, full for work.

#### 5b. Session boundary integration

At session start:
- Read manifest for current phase status
- Read worklog for open items
- Present both: "Project X is in writing (3/5 modules). You have 2 open items."
- If there are open items, show them briefly

At session end (when user indicates they're done):
- Invoke the worklog skill to write a session summary
- Confirm manifest is up to date

#### 5c. Deployment mode awareness

The orchestrator's routing logic should be aware of `deployment_mode`:
- For `self_published`: skip vetting recommendation (RCARS not applicable yet), note that code review is recommended but optional
- For `rhdp_published`: standard pipeline with all gates

### 6. Writer and Editor Skills

**Minimal changes:**
- Remove `@rhdp-publishing-house/docs/PH-COMMON-RULES.md` reference
- No other changes needed — writer and editor don't interact with deployment mode or automation

### 7. Template Updates

**`publishing-house/manifest.yaml` template:**
- `deployment_mode` field already added (previous work)
- Update comment: `# rhdp_published | self_published`

**New file in template: `publishing-house/worklog.yaml`:**

```yaml
# Publishing House Worklog
# Human context, decisions, and notes that bridge sessions and people.
# Not a task tracker — the manifest tracks structured progress.

entries: []
```

## Post-Implementation Review Flags

- **Worklog UX:** Does the structured YAML format work in practice? Do people actually use it? Is the squashing threshold right?
- **Smart intake:** How often do people provide docs upfront vs starting from scratch? Is the parsing reliable enough?
- **Token efficiency:** Measure actual token usage for status queries before and after the orchestrator change. Are we hitting the goal?
- **AgnosticV handoff:** Does the `pending_handoff` status work for teams where one person writes content and another creates the catalog item?
