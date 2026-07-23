# Intake Skill Refactor

**Date:** 2026-07-23
**Author:** Nate Stephany
**References:**
- [Validation, Gates, and Intake Review](2026-07-21-validation-and-intake-review.md) — Parts 2 and 3
- [Platform Review Findings](../feedback/2026-07-22-platform-review-findings.md) — Findings #9, #10, #13

---

## Why This Refactor

The intake skill works, but testing revealed three problems:

1. **It's a questionnaire, not a conversation.** 20 interaction points asked one at a time in a fixed order. By question 15, the author is fatigued. Infrastructure questions feel like filling out a form. The skill should be a conversational interview with suggestions and confirmations, not a sequential data-entry tool.

2. **RCARS vetting comes too late.** RCARS is queried early (after products are known) but results aren't used until after the design doc is written. By then, retrofitting RCARS insights feels like rework. RCARS should validate the design, not be a footnote after it.

3. **The skill is tightly coupled to its own templates and the platform.** The skill has its own copy of the design template (already diverged from the project template). It hardcodes field lists, valid values, and question wording. If the platform is down, the skill is completely unusable. The skill should be template-driven — reading what it needs to fill in from the project files themselves.

---

## Design Principles

### 1. Template-Driven, Not Hardcoded

The skill learns what to fill in by reading the project files — not from internal copies or hardcoded lists.

**spec.yaml** has inline comments that describe valid values:
```yaml
cloud_provider: cnv    # cnv | aws | azure
cluster_type: sno      # sno | multinode
ai_requirement: ""     # maas | gpu | none
```

**design.md** has placeholder text that describes what goes in each section:
```markdown
## Content Type

[Lab (hands-on) or Demo (presenter-led)]
```

The skill reads these files, understands the structure and constraints from the comments/placeholders, and fills them in based on the conversation. When we add a new field to spec.yaml or a new section to design.md, the skill picks it up automatically — no skill code changes needed.

**Central's validation policy** (fetched via `ph-policy.py` or bundled as a static fallback) is the authoritative dictionary for controlled vocabulary: valid action verbs, product names with aliases, content types. The spec.yaml comments are guidance for the conversation; the policy is enforcement at submission.

**What the skill should NOT do:**
- Invent values not in the template comments or policy. If the author says "GCP" but the spec.yaml comment says `# cnv | aws | azure`, the skill flags it: "The supported providers are CNV, AWS, and Azure — which fits best?"
- Refuse to continue on unexpected input. Flag it, suggest alternatives, let the author decide.
- Maintain its own copy of any template file. One source of truth: the project repo.

### 2. Conversational Interview, Not Questionnaire

The skill suggests and confirms. It does not interrogate.

**Instead of:** "What is the cluster type?" → "What is the worker count?" → "What is the RAM per worker?" → "What is the cloud provider?"

**Do this:** "Based on your products (OpenShift and OCP Virt), I'd suggest: CNV, multinode, OCP 4.20, 6 workers with 8 vCPU and 32GB RAM. Does this look right, or should I adjust anything?"

Within each phase, the conversation flows naturally. The skill may ask follow-up questions, probe for clarity, or push back on vague answers — but it never reads from a script.

### 3. Write Per Phase, Not Per Question

Each phase is a checkpoint. Within a phase, the skill has a conversation. At the end of the phase, it writes all captured fields to both design.md and spec.yaml in one commit.

**Why phases exist:** If someone's session ends — they walk away, the connection drops, the tool crashes — everything up to the last completed phase is saved. When they come back, the skill reads what exists and picks up at the next incomplete phase. Per-phase writes give the same safety as per-question writes without the mechanical answer→write→answer→write cadence.

### 4. Two Outputs, Same Data

The intake produces two representations of the same information:

| File | Purpose | Format |
|------|---------|--------|
| `design.md` | Human-readable design document. This is what reviewers read, what the author approves, and what represents the full, thorough design. | Markdown — prose, tables, structured sections. Full detail. |
| `spec.yaml` | Machine-readable structured data. This is what Central validates programmatically at the submission gate. | YAML — typed fields, enums, lists. |

Both should be thorough. The design.md is not a simplified version of spec.yaml — it's the same information in a format humans can review without reading YAML. The skill fills in both at each phase write.

### 5. Single Source of Truth for Templates

Every template file exists in exactly one place — the project repo. The skill reads from there.

| File | Lives in | Skill reads from |
|------|----------|-----------------|
| `design.md` | Template repo → cloned project at `publishing-house/spec/design.md` | The project's copy |
| `spec.yaml` | Scaffolder skeleton → cloned project at `publishing-house/spec.yaml` | The project's copy |
| `module-outline-template.md` | Template repo → `publishing-house/spec/module-outline-template.md` | The project's copy |

The skill must NOT have its own copies of these files. The current `skills/intake/references/design-template.md` must be removed — it has already diverged from the project template.

**Edge case — template drift on idle projects:** If the template changes after a project is created (new required section, changed field), the author's project won't have it. The deterministic validation at submission catches this — if a new section is required, validation fails with a specific message. The skill can also notice during intake and offer to add the missing section. But it never silently rewrites the author's files.

---

## Entry Paths

The skill must handle three starting scenarios, plus a resume path.

### Path A — "I have an idea"

Fresh conversational interview. Full Phase 1 through Phase 6. This is the default path.

### Path B — "I have something written up"

The author has an existing document — Google Doc, meeting notes, a rough outline, a Jira issue — that is NOT in Publishing House format. The skill reads it (pasted content, file path, or URL), extracts what it can into design.md and spec.yaml format, asks follow-up questions for gaps, and proceeds through the remaining phases.

### Path C — "I already filled this out"

The author already filled in `publishing-house/spec/design.md` and possibly the module outlines directly in the repo. The skill reads what's there, validates completeness, fills spec.yaml from the design content, asks about any gaps (missing fields, empty sections), and moves toward approval. No full interview — just gap-fill and validation.

**Detection:** The skill checks whether design.md still has `[placeholder]` markers or contains real content. If mostly filled in → Path C. If the author explicitly says "I already did this" → Path C.

### Resume — "I started this before"

The author started intake in a previous session. Some phases are already done. The skill detects which phases have output:

- design.md exists and isn't placeholders → Phase 2 is done
- Module outline files exist in `publishing-house/spec/modules/` → Phase 4 is done
- spec.yaml infrastructure fields are populated → Phase 5 is done
- RCARS results in spec.yaml → Phase 3 is done

The skill picks up at the next incomplete phase. It shows a summary of what's already captured and confirms before continuing.

---

## Phase Flow

Six phases. Each ends with a write checkpoint (commit to both design.md and spec.yaml as appropriate). Each phase ends with a progress indicator telling the author how many phases remain.

### Phase 1 — Discovery

**Goal:** Understand the author's idea, audience, and scope.

**How it starts:**
> "We'll start with a conversation about your idea, then move through design, RCARS validation, module outlines, infrastructure, and submission. Six phases total."

**What the skill learns:** Project goal (what will someone be able to DO?), target audience (who is this for, what level), products and technologies involved, content type (lab or demo — skip if pre-set by RHDH), Showroom type (classic or zero-touch — skip if pre-set), estimated duration.

**Conversation style:** Open-ended. The skill asks "tell me about your idea" and extracts answers from the freeform response. Follow-up questions fill gaps — one at a time, not a list. If the author's initial description already covers audience, products, and duration, don't re-ask those.

**Write point:** All discovery fields to spec.yaml + commit.

**Progress:** "Discovery complete. Next: design doc. (4 phases remaining)"

### Phase 2 — Design Generation

**Goal:** Produce a complete, validated design.md.

**How it works:**
1. The skill reads the design.md template from the project repo
2. It fills in each section using what it learned in Phase 1
3. It proposes module structure based on the conversation (titles, durations, relationships)
4. It presents the design to the author for review

**The author can:**
- Approve the design as-is
- Give feedback → skill updates the design
- Say "I already filled this out" → skill reads the existing design.md (Path C)
- Edit design.md directly in their editor and commit → skill picks up the changes

**Write point:** design.md + corresponding spec.yaml fields + commit.

**Inline structure check:** After writing, run the Group D validation checks (required sections present, valid action verbs, no template placeholders, durations in range). Non-blocking — show results, let the author fix issues. The hard gate is at submission.

**Progress:** "Design doc complete and validated. Next: RCARS vetting. (3 phases remaining)"

### Phase 3 — RCARS Vetting

**Goal:** Validate the design against the existing RHDP catalog. Identify overlap, gaps, and differentiation opportunities.

**How it works:**
1. Central generates a summary of design.md and queries the RCARS advisor
2. The skill presents the advisor response alongside the design
3. The author reviews and decides whether to adjust

**If RCARS is unavailable (offline mode):** Skip with a warning. "RCARS vetting is unavailable offline. This will run when you submit for review."

**If adjustments are made:** Update design.md, re-run the inline structure check.

**What gets stored:** RCARS overlap percentage, top matches (title, CI name, relevance score, similarity explanation), differentiation notes from the conversation. These go into spec.yaml under `approval_checklist.content`.

**Write point:** RCARS results + any design changes to spec.yaml + commit.

**Progress:** "RCARS vetting complete. Next: module outlines. (2 phases remaining)"

### Phase 4 — Module Outlines

**Goal:** Generate detailed outlines for each module defined in the design.

**How it works:**
1. The skill reads design.md (the Module Map table) and the module-outline-template from the project repo
2. For each module, it generates an outline file following the template structure
3. It presents the outlines to the author for review

**The author can:**
- Approve the outlines as-is
- Give feedback on specific modules
- Say they already wrote the outlines → skill validates what exists

**Write point:** Module outline files to `publishing-house/spec/modules/` + commit.

**Progress:** "Module outlines complete. Next: infrastructure confirmation. (1 phase remaining)"

### Phase 5 — Infrastructure Confirmation

**Goal:** Capture infrastructure requirements as a single confirm-or-adjust interaction.

**How it works:** The skill derives defaults from what it already knows (products, content type, topology from Phase 1) and proposes a complete infrastructure profile:

> "Based on your products, I'd suggest: CNV, multinode, OCP 4.20, 6 workers (8 vCPU, 32GB RAM), no AI, no external services. Does this look right, or should I adjust anything?"

The skill reads the valid values from spec.yaml's inline comments (`# cnv | aws | azure`) to constrain its suggestions.

**Conditional follow-ups** — only asked if triggered by the conversation:
- AI/MaaS: only if products include AI keywords. Suggest MaaS (open-source) by default.
- AAP version: only if AAP is in the products list.
- Non-GA products: only if any product is labeled beta/tech preview.
- External services: ask once, accept "none."
- Concurrent users: only if topology is per-student or cnv-pool.

**The author can:** Confirm, adjust specific values, or edit spec.yaml directly.

**Write point:** All infrastructure fields to spec.yaml + update design.md Infrastructure section + commit.

### Phase 6 — Finalize + Submit

**Goal:** Complete the approval checklist, generate supporting files, validate, and submit.

**What happens:**
1. Ask remaining approval checklist questions (prerequisites verifiable, assessment strategy)
2. Confirm differentiation (pre-filled from Phase 3 RCARS conversation)
3. Generate `jira.yaml` (task structure for Jira sync)
4. Generate `automation-manifest.yaml` draft
5. Generate `mkdocs.yml` for TechDocs rendering
6. Author checkpoint: "Are you happy with this and ready to submit for review?"
7. Commit + push
8. Call Central API (`ph-intake.py`) — runs full deterministic validation (all 9 check groups server-side), advances workflow on success, returns specific failures on 422
9. If validation fails → show failures, help author fix, re-commit, re-submit (loop)

**If offline:** "Your spec is complete and committed locally. When the platform is available, run the submission step to pass through the review gate."

---

## Offline Mode

> **Post-MVP.** Offline mode is important but not required for the initial implementation. The MVP assumes the platform is available. This section documents the target design for a follow-up iteration.

The skill must work without Central API or SonataFlow. Platform outages should not block spec authoring.

| Capability | Needs Platform? | Offline Behavior |
|-----------|----------------|-----------------|
| Interview (Phases 1-2) | No | Works as-is |
| Validation policy | Yes — fetched from Central | Use static fallback bundled in the project (`publishing-house/policy.json`) |
| RCARS vetting (Phase 3) | Yes — Central is the RCARS gateway | Skip with warning |
| Module outlines (Phase 4) | No | Works as-is |
| Infra confirmation (Phase 5) | No | Works as-is |
| Approval checklist (Phase 6) | No | Works as-is |
| Submission (Phase 6) | Yes — runs validation + advances workflow | Defer with warning |
| Workflow state check | Yes — queries SonataFlow | Assume `intake` stage |

**Detection:** The skill detects offline mode when pre-flight Step 4 (`ph-workflow-data.py`) fails. Instead of stopping, it warns the author and continues.

---

## Template Repo Changes

These changes are needed in the template repo (`rhdp-publishing-house-template`, `rearchitecture` branch):

| Change | Reason |
|--------|--------|
| Update `design.md` — change "Workshop" to "Lab" throughout | Only two content types: lab and demo |
| Add `spec.yaml` with empty fields and inline comments | Allows manual authors to fill it in; RHDH Scaffolder overwrites with pre-populated values on project creation |
| Remove `manifest.yaml` | Legacy lifecycle file — SonataFlow manages state now |
| Review `design.md` structure — ensure full detail, human readable | The design is the thorough document. Same data as spec.yaml, different format. Don't simplify it. |

---

## Skill Repo Changes

These changes are needed in the skills repo (`rhdp-publishing-house-skills`):

| Change | Reason |
|--------|--------|
| Delete `intake/references/design-template.md` | Skill reads from the project repo's `design.md`, not its own copy |
| Rewrite `intake/SKILL.md` | New phase-based dispatch, entry path detection, resume logic |
| Rewrite `intake/procedures/02-interview.md` | Conversational phases, not rigid question list |
| Rewrite `intake/references/intake-questions.md` | Organize by phase, collapse infra into confirm-or-adjust |
| Update `intake/procedures/03-design-doc.md` | Read template from project, fill in sections, run inline check |
| Add `intake/procedures/03b-rcars-vetting.md` | Phase 3: call Central, present results, handle adjustments |
| Update `intake/procedures/04-module-outlines.md` | Read template from project, generate from design |
| Delete `intake/procedures/05-spec-refinement.md` | Eliminated — RCARS vetting in Phase 3 replaces it |
| Rename `intake/procedures/06-approval-and-submit.md` to `06-finalize-and-submit.md` | Clarify what it does: generate files, validate, submit |
| Add offline mode detection to pre-flight | Degrade gracefully when Central is unreachable |
| Add progress indicators at phase boundaries | Author always knows where they are and how much is left |

---

## RCARS Integration

Phase 3 of the intake flow uses RCARS to validate the design doc. This requires Central API support.

**What Central needs:**
1. Accept a project slug (or repo URL + branch)
2. Read design.md from the project repo via the GitHub API
3. Generate a summary query from the design — products, learning objectives, audience, content type
4. Submit the query to RCARS advisor and poll for results
5. Return a structured response: top candidates with relevance scores, similarity explanations, identified gaps

**Current state:** The skill uses `ph-rcars.py` to hit the RCARS advisor endpoint directly. This works for the current flow but doesn't leverage the full design doc. The refactored flow needs Central to generate the query from design.md — a richer input than just goal + audience + products.

**RCARS results stored in spec.yaml:**
```yaml
approval_checklist:
  content:
    rcars_overlap_pct: 78
    rcars_top_matches:
      - title: "OCP Virt Getting Started"
        ci_name: "ocp4-virt-getting-started"
        relevance_score: 78
        why_it_fits: "Covers VM deployment on OpenShift"
    differentiation: "Covers live migration on OCP 4.20..."
```

---

## What This Does NOT Cover

- **Development phase skills** (writer, editor, automation) — separate workstream
- **Gate enforcement and spec contract snapshots** — Part 1 of the validation spec, owned by Tyrell
- **RHDH Scaffolder template changes** — related but separate (template form UX, GitHub template repo integration)
- **Central API validation engine changes** — the 9 check groups are already built; this spec doesn't change them
