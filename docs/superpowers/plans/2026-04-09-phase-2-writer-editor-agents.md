# Phase 2: Writer Agent + Editor Agent — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Writer agent (wraps `showroom:create-lab` and `showroom:create-demo`) and Editor agent (wraps `showroom:verify-content`) for the RHDP Publishing House plugin, enabling the writing and technical editing lifecycle phases.

**Architecture:** Two new spoke agents join the existing Hub + Spoke plugin. The Writer agent reads approved module outlines from `publishing-house/spec/modules/` and invokes the appropriate showroom skill to generate AsciiDoc content in `content/`. The Editor agent invokes `showroom:verify-content` against the generated content, then produces review notes in `publishing-house/reviews/`. Both agents respect the manifest's autonomy level and update module status. The orchestrator is updated to dispatch to these agents instead of showing "not yet available" messages.

**Tech Stack:** Claude Code plugin (SKILL.md markdown files), YAML (manifest), Markdown (references, docs)

---

## File Structure

### New files

```
rhdp-publishing-house/
├── skills/
│   ├── writer/
│   │   ├── SKILL.md                         # Content writing agent (wraps showroom skills)
│   │   └── references/
│   │       └── writing-standards.md         # PH-specific writing rules and showroom integration
│   └── editor/
│       ├── SKILL.md                         # Technical editing agent (wraps verify-content)
│       └── references/
│           └── editing-checklist.md         # PH-specific editing criteria beyond showroom checks
```

### Modified files

```
├── skills/
│   └── orchestrator/
│       └── SKILL.md                         # Update dispatch table — writer/editor now available
├── README.md                                # Remove "Phase 2" markers from writer/editor entries
```

---

### Task 1: Writer Agent Reference Document

**Files:**
- Create: `skills/writer/references/writing-standards.md`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p skills/writer/references
```

- [ ] **Step 2: Write writing-standards.md**

Create `skills/writer/references/writing-standards.md`:

```markdown
# Publishing House Writing Standards

Standards for the writer agent when generating content via showroom skills.
These supplement the showroom skill's own rules — do not duplicate them.

## Module Outline as Contract

The approved module outline in `publishing-house/spec/modules/module-NN-*.md` is the
writer's contract. Every section in the outline must appear in the generated content.
Do not add sections not in the outline. Do not skip sections that are in the outline.

If the outline is ambiguous or incomplete, ask the user for clarification rather than
guessing. In `full` autonomy mode, make reasonable assumptions and note them in the
module's review notes for the editor to validate.

## Content Type Routing

The writer agent uses the manifest's `project.type` field to determine which
showroom skill to invoke:

| `project.type` | Showroom Skill | Content Structure |
|----------------|----------------|-------------------|
| `workshop`     | `showroom:create-lab` | Exercises with verification sections |
| `demo`         | `showroom:create-demo` | Know/Show presenter-led format |

## Showroom Skill Invocation

When invoking showroom skills, provide these inputs derived from the PH context:

### For `showroom:create-lab`
- **Directory:** `content/modules/ROOT/pages/` (or from manifest's showroom_repo path)
- **Reference materials:** The module outline file path — the showroom skill reads it as reference
- **Learning objectives:** Extracted from the module outline's "Learn" section
- **Business scenario:** Extracted from `publishing-house/spec/design.md` problem statement
- **Target duration:** From the module outline's "Audience and Time" section
- **Audience level:** From design.md's target audience
- **New vs continue:** First module uses `--new`, subsequent modules use `--continue <previous-module-path>`

### For `showroom:create-demo`
- **Directory:** `content/modules/ROOT/pages/`
- **Demo materials:** The module outline file path
- **Demo objective:** From the module outline's "Brief Overview"
- **Customer scenario:** From design.md's problem statement
- **Value proposition:** From design.md's learning objectives
- **Target duration:** From the module outline
- **Audience:** From design.md's target audience

## Module Numbering

Modules are numbered sequentially in the Showroom content directory:
- First module in the lab: `03-module-01-<title>.adoc` (after index, overview, details)
- Second module: `04-module-02-<title>.adoc`
- Pattern: `0{N+2}-module-{NN}-<title>.adoc`

The showroom skills handle this numbering. The writer agent provides the module
outline and lets the skill determine the correct file numbers.

## Post-Generation Checklist

After the showroom skill generates content, verify:

1. All sections from the module outline are represented in the generated content
2. Navigation (`nav.adoc`) was updated with the new module
3. The generated file exists at the expected path
4. No hardcoded credentials, URLs, or environment-specific values (use `{attributes}`)

## Manifest Module Status

Update the module's status in the manifest as work progresses:

| Status | When |
|--------|------|
| `pending` | Not yet started |
| `in_progress` | Showroom skill invoked, writing underway |
| `drafted` | Content generated and initial checks passed |
| `approved` | User approved the draft (or editor approved in semi/full) |

## What the Writer Does NOT Do

- Does not set up the Showroom scaffold (site.yml, ui-config.yml) — the showroom skill handles this on the first module
- Does not run editorial review — that is the editor agent's job
- Does not generate conclusion modules — generated after all modules are drafted, as the final writing step
- Does not update the manifest's phase-level status — only module-level status. The orchestrator manages phase transitions.
```

- [ ] **Step 3: Commit**

```bash
git add skills/writer/references/writing-standards.md
git commit -m "Add writer agent reference — writing standards and showroom integration"
```

---

### Task 2: Writer Agent SKILL.md

**Files:**
- Create: `skills/writer/SKILL.md`

- [ ] **Step 1: Write writer SKILL.md**

Create `skills/writer/SKILL.md`:

```markdown
---
name: rhdp-publishing-house:writer
description: This skill should be used when the user asks to "write a module", "draft content", "write module 2", "start writing", "generate lab content", or "create the workshop content". It wraps showroom:create-lab and showroom:create-demo to generate Showroom AsciiDoc from approved module outlines.
---

---
context: main
model: claude-sonnet-4-6
---

# RHDP Publishing House — Writer Agent

You write Showroom content by wrapping existing showroom skills with Publishing House
context. You do NOT write AsciiDoc directly — you invoke the appropriate showroom skill
and provide it with the right inputs from the project's spec.

See @rhdp-publishing-house/docs/PH-COMMON-RULES.md for shared rules.
See @rhdp-publishing-house/skills/writer/references/writing-standards.md for writing standards.

## Before Starting

1. Read `publishing-house/manifest.yaml` to understand project state
2. Confirm the project is in the `writing` phase (or that approval is completed)
3. Check `project.type` to determine content type (workshop or demo)
4. Check `project.autonomy` for behavior mode

## Step 1: Determine Which Module to Write

Check what the user requested:

- If user said "write module N" → write that specific module
- If user said "write all" or "start writing" → write the next pending module
- If user said "write conclusion" → generate the conclusion module (only after all other modules are drafted)

Read `lifecycle.phases.writing.modules` from the manifest to find module status.

**If the requested module is already `drafted` or `approved`:**
> "Module N is already drafted. Would you like to re-draft it (this will overwrite the current content) or move to the next pending module?"

**If a prior module is still `pending` (not in order):**
> "Module [N-1] hasn't been written yet. Modules should be written in order for story continuity. Write Module [N-1] first, or proceed with Module N anyway?"

## Step 2: Read the Module Outline

Read the module's outline file from `publishing-house/spec/modules/`.

The manifest's `lifecycle.phases.writing.modules[N].name` maps to the outline filename.
Module outlines are named `module-NN-<title>.md` (e.g., `module-01-overview.md`).

Read the full outline. Extract:
- **Brief Overview** → used as context for the showroom skill
- **Audience and Time** → duration and audience level
- **What You Will See, Learn, and Do** → learning objectives
- **Lab Structure** → section breakdown
- **Detailed Steps** → step-by-step content for the showroom skill to expand
- **Key Takeaways** → used for module conclusion/summary
- **Infrastructure Notes** → environment-specific details

Also read `publishing-house/spec/design.md` for:
- Problem statement (business scenario)
- Target audience
- Products and technologies

## Step 3: Invoke the Showroom Skill

Based on `project.type` in the manifest:

### Workshop (`project.type: workshop`)

Inform the user:
> "Using `showroom:create-lab` to write Module N: [title]."

Invoke `showroom:create-lab` with:
- **Directory:** `content/` (or the Showroom content root if different)
- **Mode:** `--new` for the first module, `--continue <previous-module-path>` for subsequent
- **Reference:** Point it to the module outline file as the primary reference material
- **Context answers** (pre-fill the showroom skill's questions from PH spec):
  - Lab story/business context → from design.md problem statement
  - Target audience → from design.md
  - Learning objectives → from module outline See/Learn/Do
  - Duration → from module outline Audience and Time
  - Module name → from module outline title
  - UserInfo variables → from module outline Infrastructure Notes (if any)

The showroom skill will ask its own follow-up questions. Answer them from the module
outline and design spec. If the outline doesn't cover something the skill asks, ask
the user.

### Demo (`project.type: demo`)

Inform the user:
> "Using `showroom:create-demo` to write Module N: [title]."

Invoke `showroom:create-demo` with:
- **Directory:** `content/`
- **Mode:** `--new` for first module, `--continue <previous-module-path>` for subsequent
- **Reference:** The module outline file
- **Context answers:**
  - Business message → from design.md problem statement
  - Customer challenge → from design.md problem statement
  - Audience → from design.md target audience
  - Duration → from module outline
  - Demo objective → from module outline Brief Overview
  - Value proposition → from module outline Key Takeaways

## Step 4: Post-Generation Verification

After the showroom skill finishes generating content:

1. Verify the generated file exists in `content/modules/ROOT/pages/`
2. Check that `content/modules/ROOT/nav.adoc` includes the new module
3. Cross-check the generated content sections against the module outline:
   - Every section in the outline should have a corresponding section in the content
   - Flag any outline sections that were not covered
4. Check for hardcoded values that should use `{attribute}` placeholders

### Autonomy Behavior

- **Supervised:** Present the generated content summary to the user. Ask: "Module N draft complete. Review the content at [file path]. Does this look good, or would you like changes?"
- **Semi:** Write content, present a brief summary. Only pause if outline sections were missed.
- **Full:** Write content, note completion, move on.

## Step 5: Update Manifest

Update the module's status in `lifecycle.phases.writing.modules`:

```yaml
writing:
  modules:
    - name: "Module 1: [Title]"
      status: drafted
      content_file: content/modules/ROOT/pages/03-module-01-title.adoc
```

Add the content file path so the editor agent knows where to find it.

**Do not change `lifecycle.phases.writing.status` or `lifecycle.current_phase`.**
Phase-level transitions are managed by the orchestrator.

## Step 6: Report Back

After updating the manifest, inform the user:

> "Module N: [Title] — drafted.
> Content: `content/modules/ROOT/pages/[filename]`
>
> [If outline sections were missed: "Note: The following outline sections were not fully covered: [list]. Consider revising or flagging for the editor."]
>
> Next pending module: Module [N+1] — or say 'edit' to start technical editing."

## Writing the Conclusion Module

When the user requests "write conclusion" or all modules are drafted:

1. Verify ALL modules have `drafted` or `approved` status
2. If any are still `pending`, inform the user and do not proceed
3. Invoke the showroom skill one more time to generate the conclusion module
   - The showroom skill generates `0X-conclusion.adoc` that consolidates references
     and learning outcomes from all modules
4. Update manifest: add conclusion to the modules list with status `drafted`

## What You Do NOT Do

- Do not write AsciiDoc directly — always invoke the showroom skill
- Do not review or edit content — that is the editor agent's responsibility
- Do not set up Showroom scaffold manually — the showroom skill handles `site.yml`, `ui-config.yml`, `antora.yml` on first invocation
- Do not advance the lifecycle phase — only update module-level status
- Do not skip the module outline — if it doesn't exist, stop and inform the user
```

- [ ] **Step 2: Validate SKILL.md frontmatter**

Run: `python3 -c "
content = open('skills/writer/SKILL.md').read()
blocks = content.split('---')
import yaml
fm1 = yaml.safe_load(blocks[1])
fm2 = yaml.safe_load(blocks[3])
assert fm1['name'] == 'rhdp-publishing-house:writer', f'Bad name: {fm1[\"name\"]}'
assert 'description' in fm1, 'Missing description'
assert fm2['context'] == 'main', f'Bad context: {fm2[\"context\"]}'
assert fm2['model'] == 'claude-sonnet-4-6', f'Bad model: {fm2[\"model\"]}'
print('Writer SKILL.md frontmatter: VALID')
"`
Expected: `Writer SKILL.md frontmatter: VALID`

- [ ] **Step 3: Commit**

```bash
git add skills/writer/SKILL.md
git commit -m "Add writer agent skill — wraps showroom:create-lab and create-demo"
```

---

### Task 3: Editor Agent Reference Document

**Files:**
- Create: `skills/editor/references/editing-checklist.md`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p skills/editor/references
```

- [ ] **Step 2: Write editing-checklist.md**

Create `skills/editor/references/editing-checklist.md`:

```markdown
# Publishing House Editing Checklist

Additional editorial checks the editor agent performs beyond what `showroom:verify-content`
covers. These are PH-specific quality gates.

## Spec Alignment Checks

These checks verify the content matches the approved spec. `showroom:verify-content`
does not know about the PH spec — only the editor agent does.

### SA-1: Outline Coverage
- Every section in the module outline has a corresponding section in the content
- No major content was added that isn't in the outline (scope creep)
- Section ordering follows the outline's lab structure

### SA-2: Learning Objectives Match
- The module's learning objectives (from outline See/Learn/Do) are reflected in the content
- Each "Do" item has a corresponding hands-on exercise
- Each "Learn" item has explanatory content
- Each "See" item has a visual or observable outcome described

### SA-3: Duration Alignment
- Content depth is appropriate for the estimated duration in the outline
- A 15-minute module should not have 45 minutes of content (or vice versa)
- Flag modules that seem significantly over/under the time estimate

### SA-4: Cross-Module Consistency
- Terminology is consistent across modules (same term for the same concept)
- Prerequisites mentioned in later modules were covered in earlier modules
- Story/scenario continuity — the business context flows between modules
- No contradictions between modules

## Red Hat Style Additions

Beyond the Red Hat style checks in `showroom:verify-content`:

### RS-1: Product Name Accuracy
- Official Red Hat product names used consistently
- Cross-reference against products listed in `publishing-house/spec/design.md`
- First mention in each module should use the full product name

### RS-2: Version Consistency
- Version references match the spec's infrastructure requirements
- No mixed version references (e.g., OCP 4.14 in one module, 4.15 in another)

## Review Output Format

The editor produces a review report at `publishing-house/reviews/editing-review-module-NN.md`:

```markdown
# Editorial Review — Module N: [Title]

## showroom:verify-content Results

[Findings table from verify-content, grouped by severity]

## Spec Alignment

| Check | Status | Notes |
|-------|--------|-------|
| SA-1: Outline Coverage | PASS/FAIL | [details] |
| SA-2: Learning Objectives | PASS/FAIL | [details] |
| SA-3: Duration Alignment | PASS/FAIL | [details] |
| SA-4: Cross-Module Consistency | PASS/FAIL | [details] |

## Red Hat Style

| Check | Status | Notes |
|-------|--------|-------|
| RS-1: Product Names | PASS/FAIL | [details] |
| RS-2: Version Consistency | PASS/FAIL | [details] |

## Summary

- Critical issues: N
- High issues: N
- Medium issues: N
- Low issues: N

## Recommended Actions

1. [Specific action with file and line reference]
2. ...
```

## Fix Loop

After presenting the review, the editor enters a fix loop:

1. Present the findings sorted by severity (critical first)
2. Ask: "Which issue would you like to fix first? Or say 'fix all' to address them sequentially."
3. For each fix:
   - Show the before/after change
   - Apply the fix (in supervised mode, ask first)
   - Mark the finding as resolved
4. After all fixes, re-run the spec alignment checks to verify
5. Update the review file with final status
```

- [ ] **Step 3: Commit**

```bash
git add skills/editor/references/editing-checklist.md
git commit -m "Add editor agent reference — editing checklist with spec alignment checks"
```

---

### Task 4: Editor Agent SKILL.md

**Files:**
- Create: `skills/editor/SKILL.md`

- [ ] **Step 1: Write editor SKILL.md**

Create `skills/editor/SKILL.md`:

```markdown
---
name: rhdp-publishing-house:editor
description: This skill should be used when the user asks to "edit my content", "review the modules", "technical edit", "check content quality", "run editorial review", or "verify my workshop content". It wraps showroom:verify-content and adds spec alignment checks for RHDP Publishing House projects.
---

---
context: main
model: claude-sonnet-4-6
---

# RHDP Publishing House — Editor Agent

You perform technical editing by wrapping `showroom:verify-content` and adding
Publishing House-specific spec alignment checks. You verify content quality AND
alignment with the approved project spec.

See @rhdp-publishing-house/docs/PH-COMMON-RULES.md for shared rules.
See @rhdp-publishing-house/skills/editor/references/editing-checklist.md for the full editing checklist.

## Before Starting

1. Read `publishing-house/manifest.yaml` to understand project state
2. Confirm the project has drafted modules (at least one module with status `drafted`)
3. Check `project.autonomy` for behavior mode

## Step 1: Determine Scope

Check what the user requested:

- **"edit module N"** → review that specific module
- **"edit all" / "review content" / "technical edit"** → review all drafted modules
- **"edit"** with no qualifier → review the next un-reviewed drafted module

Read `lifecycle.phases.writing.modules` from the manifest.

**If no modules are drafted:**
> "No drafted modules found. The writing phase needs to produce content before editing can begin. Would you like to write a module first?"

**If a specific module is requested but its status is `pending`:**
> "Module N hasn't been drafted yet. Would you like to write it first, or edit a different module?"

## Step 2: Run showroom:verify-content

Inform the user:
> "Using `showroom:verify-content` to review Module N: [title]."

Invoke `showroom:verify-content` against the content directory. The skill:
1. Auto-detects the content type (workshop vs demo)
2. Runs all quality checks silently (scaffold, structure, AsciiDoc, Red Hat style, technical accuracy)
3. Presents a consolidated findings table sorted by severity
4. Offers a fix loop for each issue

**Let the verify-content skill complete its full check cycle.** Do not interrupt or
skip its checks. Capture the findings — they become part of the editorial review report.

## Step 3: Run Spec Alignment Checks

After `showroom:verify-content` completes, run the PH-specific checks that the
showroom skill cannot perform (it doesn't know about the PH spec).

Read the module outline from `publishing-house/spec/modules/module-NN-*.md`.
Read the generated content from the path in the manifest (`content_file` field).
Read `publishing-house/spec/design.md` for project-level context.

### SA-1: Outline Coverage

Compare the outline's sections against the generated content:
- List each section from the outline
- Check if the generated content has a corresponding section
- Flag missing sections as HIGH severity
- Flag sections in content that aren't in the outline as MEDIUM severity (scope creep)

### SA-2: Learning Objectives Match

From the outline's "What You Will See, Learn, and Do":
- Each "Do" item should have a hands-on exercise in the content
- Each "Learn" item should have explanatory content
- Each "See" item should have a described observable outcome
- Flag unmatched objectives as HIGH severity

### SA-3: Duration Alignment

Compare the outline's estimated duration against content depth:
- Count the number of exercises/steps in the content
- Estimate reading + execution time based on content volume
- Flag significant mismatches (>50% over or under) as MEDIUM severity

### SA-4: Cross-Module Consistency (only when reviewing multiple modules)

If reviewing more than one module:
- Check terminology consistency across modules
- Verify prerequisites in later modules were covered in earlier ones
- Check story/scenario continuity
- Flag contradictions as HIGH severity

### RS-1: Product Name Accuracy

Cross-reference product names in the content against the design spec:
- Check for unofficial abbreviations (e.g., "OCP" without prior "Red Hat OpenShift Container Platform")
- Flag inconsistent product naming as MEDIUM severity

### RS-2: Version Consistency

Check version references against the spec's infrastructure requirements:
- Flag mixed versions as HIGH severity
- Flag hardcoded versions that should use `{attribute}` placeholders as MEDIUM severity

## Step 4: Produce Review Report

Write the review report to `publishing-house/reviews/editing-review-module-NN.md`.

Follow the format in @rhdp-publishing-house/skills/editor/references/editing-checklist.md.

The report combines:
1. `showroom:verify-content` findings (grouped by severity)
2. Spec alignment check results (SA-1 through SA-4)
3. Red Hat style additions (RS-1, RS-2)
4. Summary with issue counts by severity
5. Recommended actions list

## Step 5: Fix Loop

### Autonomy Behavior

- **Supervised:** Present the full review report. Ask: "Which issue would you like to fix first? Or say 'fix all' to address them sequentially."
  - For each fix, show before/after and ask for approval
  - Apply approved fixes to the content files
  - Mark findings as resolved in the review report

- **Semi:** Automatically fix all MEDIUM and LOW severity issues. Present CRITICAL and HIGH issues for user decision. Apply fixes, update review report.

- **Full:** Automatically fix all issues that have clear, unambiguous fixes. Present any issues requiring judgment (e.g., outline coverage gaps that might need spec revision). Apply fixes, update review report.

### After Fixes

1. Re-run spec alignment checks to verify fixes resolved the issues
2. Update the review report with final status
3. If all CRITICAL and HIGH issues are resolved, the module passes editorial review

## Step 6: Update Manifest

After the review is complete (all fixes applied or user chooses to defer):

If the module passed (no unresolved CRITICAL or HIGH issues):
```yaml
writing:
  modules:
    - name: "Module 1: [Title]"
      status: approved
      content_file: content/modules/ROOT/pages/03-module-01-title.adoc
      review_file: publishing-house/reviews/editing-review-module-01.md
```

If the module has unresolved issues:
- Keep status as `drafted`
- Add the review file path so the user can track what needs fixing
- Inform the user what remains

**Do not change `lifecycle.phases.editing.status` or `lifecycle.current_phase`.**
Phase-level transitions are managed by the orchestrator.

## Step 7: Report Back

After updating the manifest:

> "Editorial review complete for Module N: [Title].
>
> Results: [X critical, Y high, Z medium, W low] issues found.
> [If passed:] All critical/high issues resolved. Module approved.
> [If not passed:] [N] unresolved issues remain. See `publishing-house/reviews/editing-review-module-NN.md`.
>
> Review: `publishing-house/reviews/editing-review-module-NN.md`
> [Next un-reviewed module, if any]"

## Reviewing Multiple Modules

When reviewing all drafted modules:

1. Run `showroom:verify-content` once against the full content directory (it checks all files)
2. Run spec alignment checks per-module (each module against its outline)
3. Run cross-module consistency check (SA-4) across all modules
4. Produce one review report per module, plus a summary report if reviewing 3+ modules
5. Enter fix loop per module, starting with the module that has the most critical issues

## What You Do NOT Do

- Do not write new content — that is the writer agent's responsibility
- Do not modify the module outlines — if the content doesn't match the outline, flag it; don't change the spec
- Do not advance the lifecycle phase — only update module-level status
- Do not re-implement checks that `showroom:verify-content` already performs — wrap and extend, not duplicate
```

- [ ] **Step 2: Validate SKILL.md frontmatter**

Run: `python3 -c "
content = open('skills/editor/SKILL.md').read()
blocks = content.split('---')
import yaml
fm1 = yaml.safe_load(blocks[1])
fm2 = yaml.safe_load(blocks[3])
assert fm1['name'] == 'rhdp-publishing-house:editor', f'Bad name: {fm1[\"name\"]}'
assert 'description' in fm1, 'Missing description'
assert fm2['context'] == 'main', f'Bad context: {fm2[\"context\"]}'
assert fm2['model'] == 'claude-sonnet-4-6', f'Bad model: {fm2[\"model\"]}'
print('Editor SKILL.md frontmatter: VALID')
"`
Expected: `Editor SKILL.md frontmatter: VALID`

- [ ] **Step 3: Commit**

```bash
git add skills/editor/SKILL.md
git commit -m "Add editor agent skill — wraps showroom:verify-content with spec alignment"
```

---

### Task 5: Update Orchestrator for Writer/Editor Dispatch

**Files:**
- Modify: `skills/orchestrator/SKILL.md`

- [ ] **Step 1: Read current orchestrator SKILL.md**

Read `skills/orchestrator/SKILL.md` to understand the current dispatch table and guard rails.

- [ ] **Step 2: Update the dispatch table**

In `skills/orchestrator/SKILL.md`, find the routing table under "## Step 3: Route User Intent" and update the writer and editor rows.

Replace:
```
| "write module N", "draft content"              | Dispatch `rhdp-publishing-house:writer` (Phase 2, not yet implemented) |
| "edit module N", "review content"              | Dispatch `rhdp-publishing-house:editor` (Phase 2, not yet implemented) |
```

With:
```
| "write module N", "draft content", "start writing" | Dispatch `rhdp-publishing-house:writer` with the module number |
| "edit module N", "review content", "technical edit" | Dispatch `rhdp-publishing-house:editor` with the module number (or "all") |
```

- [ ] **Step 3: Update the guard rails section**

In the Guard Rails section, remove or update the reference to Phase 2 agents not being available. The writer and editor are now available; automation (Phase 3) and security/review (Phase 4) are still unavailable.

Find the guard rail text about unavailable agents. Update it to only mention Phase 3-4 agents:
```
- If user requests an agent that hasn't been implemented yet (automation, security, review agents), inform them: "The [agent name] agent is not yet available. It will be built in a future phase of the Publishing House plugin. For now, you can complete [phase] manually and update the manifest when done."
```

- [ ] **Step 4: Update the Dispatch Context section**

In the "## Dispatch Context" section, update the writer and editor dispatch context to include the specific inputs they need:

Find:
```
- **Writer agent:** Provide path to the specific module outline (e.g., `publishing-house/spec/modules/module-02-deploy.md`)
- **Editor agent:** Provide paths to both the module outline and the generated content file
```

Replace with:
```
- **Writer agent:** Provide the module number to write. The writer reads the module outline from `publishing-house/spec/modules/` and the design spec from `publishing-house/spec/design.md`. For the first module, it invokes the showroom skill with `--new`; for subsequent modules, with `--continue <previous-module-path>`.
- **Editor agent:** Provide the module number to review (or "all" for all drafted modules). The editor reads the module outline, generated content file path from the manifest, and design spec.
```

- [ ] **Step 5: Validate updated SKILL.md frontmatter still parses**

Run: `python3 -c "
content = open('skills/orchestrator/SKILL.md').read()
blocks = content.split('---')
import yaml
fm1 = yaml.safe_load(blocks[1])
fm2 = yaml.safe_load(blocks[3])
assert fm1['name'] == 'rhdp-publishing-house', f'Bad name: {fm1[\"name\"]}'
assert fm2['model'] == 'claude-opus-4-6', f'Bad model: {fm2[\"model\"]}'
print('Orchestrator SKILL.md frontmatter: VALID (post-update)')
"`
Expected: `Orchestrator SKILL.md frontmatter: VALID (post-update)`

- [ ] **Step 6: Commit**

```bash
git add skills/orchestrator/SKILL.md
git commit -m "Update orchestrator — enable writer and editor agent dispatch"
```

---

### Task 6: Update README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Read current README.md**

Read `README.md` to find the Phase 2 markers.

- [ ] **Step 2: Update writer and editor entries**

Find:
```
### /rhdp-publishing-house:writer *(Phase 2)*
### /rhdp-publishing-house:editor *(Phase 2)*
```

Replace with:
```
### /rhdp-publishing-house:writer

Content writing agent. Wraps `showroom:create-lab` (workshops) and `showroom:create-demo`
(demos) to generate Showroom AsciiDoc from approved module outlines. Works module-by-module.

### /rhdp-publishing-house:editor

Technical editing agent. Wraps `showroom:verify-content` and adds Publishing House-specific
spec alignment checks. Reviews content against Red Hat quality standards and the approved
project spec. Produces review reports and offers interactive fix loops.
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "Update README — writer and editor agents now available"
```

---

### Task 7: Smoke Test — Phase 2 Structure Validation

**Files:**
- None created — validation only

- [ ] **Step 1: Validate complete plugin structure**

Run: `find . -not -path './.git/*' -not -path './.superpowers/*' -not -name '.DS_Store' | sort`

Expected output should include all Phase 1 files plus:
```
./skills/editor/SKILL.md
./skills/editor/references/editing-checklist.md
./skills/writer/SKILL.md
./skills/writer/references/writing-standards.md
```

- [ ] **Step 2: Validate all YAML/JSON files parse**

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
expected = {
    'skills/orchestrator/SKILL.md': ('rhdp-publishing-house', 'claude-opus-4-6'),
    'skills/intake/SKILL.md': ('rhdp-publishing-house:intake', 'claude-opus-4-6'),
    'skills/writer/SKILL.md': ('rhdp-publishing-house:writer', 'claude-sonnet-4-6'),
    'skills/editor/SKILL.md': ('rhdp-publishing-house:editor', 'claude-sonnet-4-6'),
}
for skill_path, (exp_name, exp_model) in expected.items():
    content = pathlib.Path(skill_path).read_text()
    blocks = content.split('---')
    fm1 = yaml.safe_load(blocks[1])
    fm2 = yaml.safe_load(blocks[3])
    assert fm1['name'] == exp_name, f'{skill_path}: expected name {exp_name}, got {fm1[\"name\"]}'
    assert 'description' in fm1, f'{skill_path}: missing description'
    assert fm2.get('context') == 'main', f'{skill_path}: bad context'
    assert fm2.get('model') == exp_model, f'{skill_path}: expected model {exp_model}, got {fm2.get(\"model\")}'
    print(f'{skill_path}: VALID ({fm1[\"name\"]}, {fm2[\"model\"]})')
"`
Expected:
```
skills/orchestrator/SKILL.md: VALID (rhdp-publishing-house, claude-opus-4-6)
skills/intake/SKILL.md: VALID (rhdp-publishing-house:intake, claude-opus-4-6)
skills/writer/SKILL.md: VALID (rhdp-publishing-house:writer, claude-sonnet-4-6)
skills/editor/SKILL.md: VALID (rhdp-publishing-house:editor, claude-sonnet-4-6)
```

- [ ] **Step 4: Verify orchestrator no longer blocks writer/editor**

Run: `python3 -c "
content = open('skills/orchestrator/SKILL.md').read()
assert 'Phase 2, not yet implemented' not in content, 'Orchestrator still has Phase 2 block for writer/editor'
assert 'Phase 3' in content or 'automation' in content.lower(), 'Orchestrator should still mention Phase 3/4 agents as unavailable'
print('Orchestrator dispatch: writer/editor enabled, automation/security/review still gated')
"`
Expected: `Orchestrator dispatch: writer/editor enabled, automation/security/review still gated`

- [ ] **Step 5: Verify git history is clean**

Run: `git status && git log --oneline -10`
Expected: Clean working tree with commits for each task.

- [ ] **Step 6: Tag Phase 2 complete**

```bash
git tag v0.2.0-phase2 -m "Phase 2: Writer agent + Editor agent"
```

---

## Phase 2 Deliverables Summary

| Deliverable | Task | Notes |
|------------|------|-------|
| Writer reference doc (writing-standards.md) | Task 1 | Content routing, showroom invocation rules, post-generation checklist |
| Writer agent SKILL.md | Task 2 | Wraps `showroom:create-lab` and `showroom:create-demo`, Sonnet 4.6 |
| Editor reference doc (editing-checklist.md) | Task 3 | Spec alignment checks (SA-1 to SA-4), Red Hat style additions (RS-1, RS-2) |
| Editor agent SKILL.md | Task 4 | Wraps `showroom:verify-content` + spec alignment, Sonnet 4.6 |
| Orchestrator update | Task 5 | Writer/editor dispatch enabled, Phase 3-4 agents still gated |
| README update | Task 6 | Writer/editor descriptions added, Phase 2 markers removed |
| Structure validation | Task 7 | All files valid, frontmatter verified, dispatch table correct |

## What's Next (Phase 3)

- Automation agent SKILL.md (wraps `agnosticv:catalog-builder`, `agnosticv:validator`)
- Automation writing capability (Ansible roles/playbooks, Argo+Helm manifests)
- End-to-end test: full lifecycle from intake through editing on a real project
