# Skills Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update all PH skills to support deployment modes (rhdp_published/self_published), add worklog skill, reduce token waste, and clean up references for the published skills repo.

**Architecture:** All changes are to skill markdown files (SKILL.md) and one YAML template. No code, no backend, no frontend. Skills are in `~/devel/publishing-house/rhdp-publishing-house-skills/skills/`. The template is in `~/devel/publishing-house/rhdp-publishing-house-template/`. After all changes, the skills repo must be re-published (copy from dev repo to skills repo).

**Tech Stack:** Markdown (SKILL.md files), YAML (manifest template, worklog template)

**Spec:** `~/devel/publishing-house/rhdp-publishing-house/docs/superpowers/specs/2026-04-20-skills-redesign.md`

---

## File Map

**Modified:**
- `skills/orchestrator/SKILL.md` — remove PH-COMMON-RULES ref, add status path, session boundaries, deployment mode awareness
- `skills/intake/SKILL.md` — remove PH-COMMON-RULES ref, add deployment mode question, smart intake, repo setup guidance
- `skills/automation/SKILL.md` — remove PH-COMMON-RULES ref, constrain approach by deployment mode, AgnosticV access handling, simplify 7c review, update language
- `skills/automation/references/automation-patterns.md` — update Field Source Content → self-published language
- `skills/writer/SKILL.md` — remove PH-COMMON-RULES ref
- `skills/editor/SKILL.md` — remove PH-COMMON-RULES ref

**Created:**
- `skills/worklog/SKILL.md` — new worklog management skill

**Template (separate repo, updated via submodule):**
- `publishing-house/manifest.yaml` — update deployment_mode comment
- `publishing-house/worklog.yaml` — new empty worklog file

---

### Task 1: Reference Cleanup — All Skills

**Files:**
- Modify: `skills/orchestrator/SKILL.md`
- Modify: `skills/intake/SKILL.md`
- Modify: `skills/writer/SKILL.md`
- Modify: `skills/editor/SKILL.md`
- Modify: `skills/automation/SKILL.md`

- [ ] **Step 1: Remove PH-COMMON-RULES reference from orchestrator**

In `skills/orchestrator/SKILL.md`, remove line 15:
```
See @rhdp-publishing-house/docs/PH-COMMON-RULES.md for common rules that apply to all Publishing House skills.
```

And remove line 151 (the second reference):
```
This ensures every agent reads the current version of its input at execution time. See @rhdp-publishing-house/docs/PH-COMMON-RULES.md "Read Before You Act" section.
```

Replace the line 151 reference with the principle inline:
```
This ensures every agent reads the current version of its input at execution time. Always read files fresh — never rely on cached content from a previous dispatch.
```

- [ ] **Step 2: Remove PH-COMMON-RULES reference from intake**

In `skills/intake/SKILL.md`, remove line 19:
```
You MUST follow all common rules defined in `@rhdp-publishing-house/docs/PH-COMMON-RULES.md`.
```

No replacement needed — the intake skill already has its own "Before Starting" section that covers reading the manifest and checking autonomy.

- [ ] **Step 3: Remove PH-COMMON-RULES reference from writer**

In `skills/writer/SKILL.md`, remove line 17:
```
See @rhdp-publishing-house/docs/PH-COMMON-RULES.md for shared rules.
```

- [ ] **Step 4: Remove PH-COMMON-RULES reference from editor**

In `skills/editor/SKILL.md`, remove line 17:
```
See @rhdp-publishing-house/docs/PH-COMMON-RULES.md for shared rules.
```

- [ ] **Step 5: Remove PH-COMMON-RULES reference from automation**

In `skills/automation/SKILL.md`, remove line 18:
```
See @rhdp-publishing-house/docs/PH-COMMON-RULES.md for shared rules.
```

- [ ] **Step 6: Verify no remaining PH-COMMON-RULES references**

Run: `grep -r "PH-COMMON-RULES" skills/`
Expected: No results.

- [ ] **Step 7: Commit**

```bash
cd ~/devel/publishing-house/rhdp-publishing-house-skills
git add skills/
git commit -m "Remove PH-COMMON-RULES references from all skills"
```

---

### Task 2: Automation Skill — Language Updates

**Files:**
- Modify: `skills/automation/SKILL.md`
- Modify: `skills/automation/references/automation-patterns.md`

- [ ] **Step 1: Update "Field Source Content" references in automation SKILL.md**

Find and replace all "Field Source Content" references with "self-published" language. There are 5 locations. For each one, update to use the new terminology. Examples:

Line ~150: Change "If the project uses an existing Field Source Content catalog item instead" → "If the project is self-published (`deployment_mode: self_published`)"

Line ~238: Change "If the catalog item (7b) was skipped (Field Source Content path)" → "If the catalog item (7b) was skipped (self-published projects skip this step)"

Line ~402: Change "or 'skip catalog item' if using an existing Field Source Content catalog" → "Self-published projects skip this step automatically."

Line ~433: Change "Project uses an existing Field Source Content catalog item, or user manages AgV config outside Publishing House" → "Project is self-published (no catalog item needed), or user manages AgV config outside Publishing House"

Read the full file to find all 5 locations and update each one.

- [ ] **Step 2: Update automation-patterns.md**

In `skills/automation/references/automation-patterns.md`, find "field source" references and update:

Line ~29: Change "skipped for field source deployments" → "skipped for self-published projects"

- [ ] **Step 3: Verify no remaining "field source" or "Field Source Content" references in automation**

Run: `grep -ri "field.source" skills/automation/`
Expected: No results (the Field Source CI name `ocp-field-asset-cnv` is fine if referenced — that's the actual CI name, not the deployment mode label).

- [ ] **Step 4: Commit**

```bash
git add skills/automation/
git commit -m "Update automation skill: Field Source Content → self-published language"
```

---

### Task 3: Intake Skill — Deployment Mode and Smart Intake

**Files:**
- Modify: `skills/intake/SKILL.md`

- [ ] **Step 1: Read the full intake skill**

Read `skills/intake/SKILL.md` completely to understand the current question flow and manifest output structure.

- [ ] **Step 2: Add deployment mode question**

After the existing project type question (workshop/demo — find it in the Phase 1 question sequence), add a new question:

```markdown
**Question: Deployment Mode**

> "Are you building this to fully onboard to RHDP, or self-publishing?"
>
> **RHDP Published** (`rhdp_published`): Goes through the full pipeline — AgnosticV catalog, reviews, end-to-end automated testing, published as a standalone item in the RHDP catalog.
>
> **Self-Published** (`self_published`): You manage deployment yourself. Automation is built as a GitOps repo. You order the generic Field Source CI and provide your repo URL. Faster, but not in the catalog.

Record in manifest as `project.deployment_mode: rhdp_published | self_published`.
```

- [ ] **Step 3: Add repo setup guidance**

After the deployment mode question (or in the "Before Starting" section, whichever flows better), add repo setup guidance:

```markdown
**Repo Setup**

After the project repo is established, advise the user:

> "Your project repo should remain **private** by default — it may contain sensitive comments, design decisions, and internal notes. The Showroom and automation repos should be **public** (or at least accessible to anyone who needs to deploy the content)."

Prompt for Showroom and automation repos:

> "I need your Showroom content repo and automation repo URLs. These are cloned into your project workspace as subdirectories. If you haven't created them yet:
> ```
> gh repo create <org>/<project>-showroom --public --clone
> gh repo create <org>/<project>-automation --public --clone
> ```
> Or provide existing repo URLs if you have them."

Record URLs in manifest under `integrations.showroom_repo` and `integrations.automation_repo`. Clone repos into the workspace's `content/` and `automation/` directories if not already present.
```

- [ ] **Step 4: Add smart intake logic**

Before the question sequence, add a section:

```markdown
## Smart Intake — Consuming Existing Docs

If the user provides existing documents (design doc, manifest, Google Doc, outline, meeting notes, or any other format):

1. Read and parse whatever documents the user provides
2. Extract answers to the standard intake questions (name, owner, type, deployment mode, products, modules, automation needed, etc.)
3. Normalize the extracted information into PH format (design.md, module outlines, manifest fields)
4. Present what was found: "I found the following in your docs — does this look right?"
5. Only ask questions for fields that are missing or ambiguous
6. Still validate (required fields, action-verb learning objectives, etc.)

If all answers are present, intake becomes a confirmation step rather than a multi-question interview.

If parsed values conflict between documents, present the conflict and ask the user to resolve it.
```

- [ ] **Step 5: Update manifest output template**

Find the manifest output template in the intake skill (where it shows the YAML it writes after intake). Add `deployment_mode` to the project section:

```yaml
project:
  deployment_mode: "rhdp_published"  # or self_published
```

Also add `integrations.showroom_repo` and `integrations.automation_repo` to the integrations section.

- [ ] **Step 6: Verify the skill reads coherently**

Read the full modified `skills/intake/SKILL.md` from top to bottom. Check that:
- The question flow is logical (type → deployment mode → repo setup → remaining questions)
- Smart intake section is positioned before the question sequence so the skill checks for existing docs first
- Manifest output includes all new fields
- No contradictions with existing content

- [ ] **Step 7: Commit**

```bash
git add skills/intake/
git commit -m "Intake skill: add deployment mode, smart intake, repo setup guidance"
```

---

### Task 4: Automation Skill — Deployment Mode Constraints

**Files:**
- Modify: `skills/automation/SKILL.md`

- [ ] **Step 1: Read the full automation skill**

Read `skills/automation/SKILL.md` completely to understand the current approach decision logic, 7b handling, and 7c code review.

- [ ] **Step 2: Add deployment mode check to "Before Starting"**

After the existing step that reads `project.autonomy`, add:

```markdown
5. Read `project.deployment_mode` from manifest — this determines automation approach options and whether AgnosticV catalog creation is needed
```

- [ ] **Step 3: Constrain approach by deployment mode in Phase 7a**

Find the "Determine approach" section in Phase 7a (Step 7a-2). Replace the current decision logic with deployment-mode-aware logic:

```markdown
**Determine approach:**

Check `project.deployment_mode`:

**If `self_published`:**
- Approach is GitOps only. Inform the user:
  > "Self-published projects use the Field Source CI, which expects a GitOps repo. Your automation approach is GitOps (Helm + ArgoCD). If you need Ansible tasks, they can run as Ansible Runner jobs within the GitOps framework."
- Reference the field-sourced-content-template at `https://github.com/rhpds/field-sourced-content-template` for the starter pattern, including the `examples/ansible` path for Ansible Runner within GitOps.
- Set `approach: gitops` in the automation manifest.

**If `rhdp_published`:**
- Ask the user: "How should the environment be automated?"
  - **Ansible** — Ansible collections as AgnosticD workloads
  - **GitOps** — Helm charts deployed by ArgoCD
  - **Both** — Ansible for cluster-level setup, GitOps for application workloads
- If the lab teaches GitOps concepts → recommend `approach: gitops`
- If the lab needs imperative setup or complex ordering → recommend `approach: ansible`
- When in doubt, ask the user
```

- [ ] **Step 4: Update Phase 7b for deployment mode and access check**

Find the Phase 7b section. Replace the introduction with deployment-mode-aware handling:

```markdown
## Phase 7b: AgnosticV Catalog Creation

**Check deployment mode first:**

When `deployment_mode: self_published`:
- Automatically skip 7b: set `substeps.catalog_item: skipped`
- Inform user: "No AgnosticV catalog item needed for self-published projects."
- Proceed to 7c.

When `deployment_mode: rhdp_published`:
- 7b is required. Ask:
  > "An AgnosticV catalog item is required for RHDP-published projects. Do you have AgnosticV access to create it, or does someone else need to handle this?"
- **If user has access** → proceed with agnosticv:catalog-builder as documented below
- **If user doesn't have access** → set `substeps.catalog_item: pending_handoff`. Write a worklog entry with the information needed for handoff (infrastructure type, operators, multi-user config from the approved automation manifest). Proceed to 7c.
```

Keep the rest of the 7b implementation (catalog-builder invocation, validation, manifest update) unchanged — it only runs when the user has access.

- [ ] **Step 5: Simplify 7c code review**

Find the "Step 7c-2: Code Review Cycle" section. Replace the three-step process with:

```markdown
### Step 7c-2: Safety Check

After writing automation code, run a quick safety check before proceeding:

**"Don't hurt yourself" checklist:**
- [ ] No hardcoded credentials, passwords, or API keys (use variables or vault)
- [ ] Container images use pinned tags (not `latest`)
- [ ] Workload references in `common.yaml` match created roles/charts
- [ ] Collection dependencies in `requirements_content` are satisfied
- [ ] No secrets in plain text in templates or defaults
- [ ] Variables follow naming conventions (`ocp4_workload_<project>_*`)

**Re-validate catalog (if catalog item exists):**
Re-run `agnosticv:validator` to verify workload references are consistent with the catalog configuration.

**Note:** This is a safety check, not a full code review. The formal code review happens in the Code & Security Review phase — a separate gate with proper PR-based review. For `rhdp_published` projects, code review is required. For `self_published` projects, it is recommended but optional.
```

- [ ] **Step 6: Verify the skill reads coherently**

Read the full modified `skills/automation/SKILL.md`. Check that:
- Deployment mode is checked early and consistently
- Self-published path is clear: 7a → skip 7b → 7c → 7d
- RHDP-published path works with and without AgnosticV access
- 7c safety check is concrete, not vague
- No contradictions with existing content

- [ ] **Step 7: Commit**

```bash
git add skills/automation/
git commit -m "Automation skill: deployment mode constraints, access handling, simplified 7c review"
```

---

### Task 5: Worklog Skill — New

**Files:**
- Create: `skills/worklog/SKILL.md`

- [ ] **Step 1: Create the worklog skill**

Create `skills/worklog/SKILL.md`:

```markdown
---
name: rhdp-publishing-house:worklog
description: This skill should be used when the user asks to "leave a note", "what's outstanding", "worklog", "resolve item", "what did we do last session", "add a worklog entry", "squash the worklog", or "session summary". It manages the human-context layer in publishing-house/worklog.yaml.
---

---
context: main
model: claude-sonnet-4-6
---

# RHDP Publishing House — Worklog Manager

You manage `publishing-house/worklog.yaml` — the human-context layer that bridges
sessions, people, and decisions. This is NOT a task tracker (the manifest tracks
structured progress). The worklog captures what falls between the cracks: decisions
pending, things to check with people, handoff notes, session summaries.

## Before Starting

1. Read `publishing-house/worklog.yaml` — if it doesn't exist, create it with an empty `entries: []` list
2. Read `publishing-house/manifest.yaml` for project context (name, current phase, owner)

## Commands

### View Open Items

When the user asks "what's outstanding?" or "worklog":

1. Read `worklog.yaml`
2. Filter entries with `status: open`
3. Present them grouped by type (decisions first, then actions, then notes):

> **Open Items (3):**
> - **Decision:** Need to decide on DataSphere vs Parksmap for module 2 demo app (Apr 15, sborenst)
> - **Action:** Check with Prakhar on CNV pool sizing (Apr 14, sborenst)
> - **Note:** Module 3 may need a different approach for the scaling exercise (Apr 13, sborenst)

### Add a Note

When the user says "leave a note about X" or "add to worklog":

1. Take the user's terse input
2. Expand it into a readable entry using LLM — add enough context that someone else (or the same person next week) can understand it without asking follow-up questions
3. Classify the type: `note`, `decision`, `handoff`, or `action`
4. Generate a unique ID: `YYYY-MM-DD-NNN` (date + sequence number for that day)
5. Write the entry to `worklog.yaml`
6. Commit and push: `git add publishing-house/worklog.yaml && git commit -m "worklog: <brief summary>" && git push`

**Example expansion:**
- User says: "check with prakhar on pool sizing"
- Skill writes:
  ```yaml
  - id: "2026-04-14-001"
    timestamp: "2026-04-14T10:00:00Z"
    author: "<github_username from manifest>"
    status: open
    type: action
    content: "Check with Prakhar on CNV pool sizing for multi-user deployments. The current common.yaml uses default pool settings, but this workshop supports 25 concurrent users which may need larger worker nodes."
  ```

### Resolve an Item

When the user says "resolve item X" or "that's done":

1. Find the entry by ID or by content match
2. Set `status: resolved`, `resolved_at: <now>`, `resolved_by: <github_username>`
3. Commit and push

### Session Summary

When the user says "session summary" or "I'm done for today" or at session end:

1. Read the manifest to see what changed this session (compare current phase/substep status)
2. Write a summary entry:
   ```yaml
   - id: "2026-04-15-session"
     timestamp: "2026-04-15T16:30:00Z"
     author: "<github_username>"
     status: resolved
     type: note
     content: "Session summary: Completed modules 1-3 drafts. Automation manifest reviewed and approved. Next session: start automation code (7c). Open decisions: DataSphere vs Parksmap for module 2."
   ```
3. Commit and push

### Squash Old Entries

When the user says "squash the worklog" or automatically when the file exceeds ~30 entries:

1. Find all resolved entries older than 1 week
2. Group them by week
3. Compress each week's resolved entries into a single summary entry:
   ```yaml
   - id: "summary-2026-04-10"
     timestamp: "2026-04-10T00:00:00Z"
     author: "system"
     status: resolved
     type: summary
     content: "April 10-14: Project created. Intake completed — 5-module workshop design approved. Spec refinement normalized design doc. Automation catalog and requirements completed. Resolved: CNV pool sizing confirmed with Prakhar."
   ```
4. Remove the individual resolved entries that were squashed
5. Commit and push

## Worklog File Format

```yaml
# Publishing House Worklog
# Human context, decisions, and notes that bridge sessions and people.
# Not a task tracker — the manifest tracks structured progress.

entries:
  - id: "2026-04-15-001"
    timestamp: "2026-04-15T14:30:00Z"
    author: "sborenst"
    status: open          # open | resolved
    type: decision        # note | decision | handoff | action | summary
    content: "Expanded, readable description of the item."
    # resolved entries also have:
    # resolved_at: "2026-04-15T09:00:00Z"
    # resolved_by: "sborenst"
```

## Entry Types

- `note` — general observation, context for future sessions
- `decision` — something that needs to be decided (open) or was decided (resolved)
- `handoff` — work being handed to someone else, includes context they need
- `action` — something that needs to be done outside of PH (check with someone, test something)
- `summary` — compressed history from squashing (always resolved)

## What You Do NOT Do

- Do not duplicate manifest state — if a module is "drafted", the manifest tracks that
- Do not create action items for PH phases — "write module 3" is a manifest concern, not a worklog item
- Do not store sensitive data (credentials, internal URLs) in worklog entries
- Do not modify the manifest — only the worklog file
```

- [ ] **Step 2: Verify the skill is self-contained**

Run: `grep -c "@rhdp-publishing-house" skills/worklog/SKILL.md`
Expected: 0 (no external references — the worklog skill is fully self-contained)

- [ ] **Step 3: Commit**

```bash
git add skills/worklog/
git commit -m "Add worklog skill for session bridging and human context"
```

---

### Task 6: Orchestrator Skill — Token Efficiency and Session Boundaries

**Files:**
- Modify: `skills/orchestrator/SKILL.md`

- [ ] **Step 1: Read the full orchestrator skill**

Read `skills/orchestrator/SKILL.md` completely.

- [ ] **Step 2: Add token-efficient status path**

After the `## Arguments` section and before `## Step 1: Project Discovery`, add a new section:

```markdown
## Fast Path: Status Queries

**For status queries** ("what's my status?", "what's next?", "where are we?", "check project status"):

Read `publishing-house/manifest.yaml` and `publishing-house/worklog.yaml` directly. Parse the YAML. Present:

1. Current phase and substep status
2. Open worklog items (count + brief list)
3. Suggested next action based on phase status

Do NOT load reference docs or dispatch to other skills. This must be lightweight.

**Example response:**

> **OCP Getting Started Workshop** (workshop, rhdp_published)
> **Current:** Writing — 3 of 5 modules drafted
> **Automation:** Completed (requirements + catalog + code)
> **Open items (2):** Decide on DataSphere vs Parksmap; Check CNV pool sizing with Prakhar
> **Next:** Draft module 4 (Infrastructure, No Ticket Required)

**For work queries** ("start writing", "build automation", "run the editor", "write module 3"):
Proceed to the full routing logic below (Step 1 onward).
```

- [ ] **Step 3: Add session boundary integration**

After the `## Session End` section, update it to include worklog integration:

```markdown
## Session Start

When starting a session (after Project Discovery):

1. Read manifest for current phase status
2. Read `worklog.yaml` for open items
3. Present both concisely alongside the project status:
   > "Project X is in writing (3/5 modules). You have 2 open items from your worklog."
4. If there are open items, list them briefly

## Session End

Before ending a session:

1. Ensure the manifest reflects the current state
2. Invoke `rhdp-publishing-house:worklog` to write a session summary entry
3. Ask if the user wants to leave any additional notes
4. Confirm: "Manifest and worklog updated. Resume with `/rhdp-publishing-house` next time."
```

- [ ] **Step 4: Add deployment mode awareness to routing**

In the routing logic (Step 3: Route User Intent), add deployment mode awareness. Find the "Guard Rails" section and add:

```markdown
**Deployment mode behavior:**
- For `self_published`: vetting is not available (RCARS integration pending). Code & Security Review is recommended but optional — inform the user.
- For `rhdp_published`: all phases apply. Code & Security Review and Final Review are required gates.
```

- [ ] **Step 5: Update dispatch context for worklog skill**

In the "Dispatch Context" section, add:

```markdown
- **Worklog skill:** No additional context needed. The worklog skill reads `worklog.yaml` and `manifest.yaml` directly.
```

- [ ] **Step 6: Verify the skill reads coherently**

Read the full modified orchestrator. Check:
- Fast path is clearly separated from the full routing logic
- Session start/end includes worklog
- Deployment mode awareness doesn't conflict with existing routing
- No broken references

- [ ] **Step 7: Commit**

```bash
git add skills/orchestrator/
git commit -m "Orchestrator: add fast status path, session boundaries, deployment mode awareness"
```

---

### Task 7: Template Updates

**Files:**
- Modify: `~/devel/publishing-house/rhdp-publishing-house-template/publishing-house/manifest.yaml`
- Create: `~/devel/publishing-house/rhdp-publishing-house-template/publishing-house/worklog.yaml`

- [ ] **Step 1: Update deployment_mode comment in manifest template**

In `~/devel/publishing-house/rhdp-publishing-house-template/publishing-house/manifest.yaml`, change:
```yaml
  deployment_mode: ""  # onboarded | self_service
```
to:
```yaml
  deployment_mode: ""  # rhdp_published | self_published
```

- [ ] **Step 2: Create worklog.yaml template**

Create `~/devel/publishing-house/rhdp-publishing-house-template/publishing-house/worklog.yaml`:

```yaml
# Publishing House Worklog
# Human context, decisions, and notes that bridge sessions and people.
# Not a task tracker — the manifest tracks structured progress.

entries: []
```

- [ ] **Step 3: Commit template changes**

```bash
cd ~/devel/publishing-house/rhdp-publishing-house-template
git add publishing-house/manifest.yaml publishing-house/worklog.yaml
git commit -m "rhdp-publishing-house-template: Add worklog.yaml, update deployment_mode values"
git push
```

- [ ] **Step 4: Update submodule in dev repo**

```bash
cd ~/devel/publishing-house/rhdp-publishing-house
git submodule update --remote template
git add template
git commit -m "rhdp-publishing-house: Update template submodule to latest"
git push
```

---

### Task 8: Publish Updated Skills to Skills Repo

**Files:**
- All files in `~/devel/publishing-house/rhdp-publishing-house-skills/skills/`

- [ ] **Step 1: Copy updated skills from dev repo to skills repo**

The dev repo (`rhdp-publishing-house/skills/`) is the source. The skills repo (`rhdp-publishing-house-skills/skills/`) is the published artifact. Copy all skill files:

```bash
# Remove old skills (clean copy)
rm -rf ~/devel/publishing-house/rhdp-publishing-house-skills/skills/

# Copy from dev repo
cp -r ~/devel/publishing-house/rhdp-publishing-house/skills/ ~/devel/publishing-house/rhdp-publishing-house-skills/skills/
```

Wait — the dev repo's `skills/` directory may have the same content as the skills repo since we've been editing the skills repo directly in earlier tasks. Check which location has the latest changes before copying.

If tasks 1-6 were executed against the skills repo (`rhdp-publishing-house-skills/skills/`), then the skills repo already has the changes and this step is: verify the dev repo's `skills/` matches, then push the skills repo.

If tasks 1-6 were executed against the dev repo (`rhdp-publishing-house/skills/`), then copy to the skills repo.

**The canonical workflow:** All skill edits happen in the skills repo. The dev repo's `skills/` directory should be kept in sync (manual copy or symlink, per the architecture decision).

- [ ] **Step 2: Verify no PH-COMMON-RULES references remain**

```bash
cd ~/devel/publishing-house/rhdp-publishing-house-skills
grep -r "PH-COMMON-RULES" skills/
```
Expected: No results.

- [ ] **Step 3: Verify no "Field Source Content" references remain**

```bash
grep -ri "field.source.content" skills/
```
Expected: No results. (References to the CI name `ocp-field-asset-cnv` or the template repo are fine.)

- [ ] **Step 4: Verify the worklog skill exists**

```bash
ls skills/worklog/SKILL.md
```
Expected: File exists.

- [ ] **Step 5: Commit and push skills repo**

```bash
cd ~/devel/publishing-house/rhdp-publishing-house-skills
git add -A
git commit -m "rhdp-publishing-house-skills: Publish redesigned skills

- Remove PH-COMMON-RULES references (all skills)
- Add deployment mode (rhdp_published/self_published) to intake
- Smart intake consumes existing docs
- Repo setup guidance in intake
- Automation constrained by deployment mode
- AgnosticV access handling at 7b
- Simplified 7c safety check
- New worklog skill
- Token-efficient orchestrator status path
- Session boundary worklog integration"
git push
```

---

### Task 9: Update Architecture Memory

**Files:**
- Modify: `~/.claude/projects/-Users-nstephan-devel/memory/ph-architecture-direction.md`

- [ ] **Step 1: Update deployment mode values in architecture memory**

Replace all `onboarded` / `self_service` / `field_source` references with `rhdp_published` / `self_published` in the architecture memory file.

- [ ] **Step 2: Add worklog and token efficiency notes**

Add a brief section on the worklog (git-based, skill manages, portal caches) and the token efficiency approach (lightweight status path in orchestrator, heavy loading only for creative work).

- [ ] **Step 3: No commit needed**

Memory files are not in git.
