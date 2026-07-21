# Publishing House — Validation, Gates, and Intake Review

**Date:** 2026-07-21
**Author:** Nate Stephany
**References:**
- [Spec & Gate Validation Hardening Design](2026-07-03-spec-gate-validation-hardening-design.md) (RHDPCD-170)
- [Spec & Gate Validation Gap Analysis](2026-07-18-spec-gate-validation-gap-analysis.md)

---

## Purpose

Publishing House went through a major rearchitecture. The original validation hardening spec and gap analysis were written against the old architecture (multi-repo, PostgreSQL-backed Central API, MCP server, Phase Engine). The current architecture is a consolidated monorepo with a stateless FastAPI Central API, SonataFlow as the workflow state machine, and an RHDH Backstage plugin for the reviewer dashboard.

Much of the validation engine was implemented during the rearchitecture — 9 check groups, 46+ individual checks across spec fields, design structure, module outlines, cross-validation, vocabulary, and auto-computed estimates. But several critical pieces were dropped in the transition, and the intake skill has UX problems surfaced during testing.

This document covers three areas:
1. **Validation & gate enforcement gaps** — what was built, what was planned, and where to meet in the middle (primary owner: Tyrell)
2. **Intake skill question bloat** — the interview is too long and needs restructuring (shared ownership)
3. **RCARS positioning in the intake flow** — vetting results arrive too late to influence design (shared ownership)

---

## Part 1: Validation & Gate Enforcement

### What's Built and Working

The validation engine at `central-api/app/services/validation/` is the most mature piece of the system. When the intake skill calls `ph-intake.py`, it hits `POST /api/v1/projects/intake/{slug}`, which:

1. Fetches the spec from GitHub (fresh read, never cached)
2. Runs `run_validation()` across all 9 check groups (A through I)
3. If any check FAILs → returns 422 with specific failures, workflow does not advance
4. If all checks pass → sends `ph.intake.complete` CloudEvent to SonataFlow

This is exactly the "deterministic checks are blockers" model from the original spec. The validation runner (`central-api/app/services/validation/runner.py`) orchestrates check groups by stage:

| Group | Module | What It Checks |
|-------|--------|----------------|
| A | `spec_fields.py` | 10 required spec.yaml fields, OCP version minimum |
| B | `spec_conditional.py` | Worker sizing, concurrent users, AI/MaaS, AAP version, vague egress |
| C | `approval_checklist.py` | Prerequisites verifiable, assessment strategy, differentiation |
| D | `design_structure.py` | Required sections, action verbs, durations, template placeholders |
| E | `module_outlines.py` | Outline count, sections, orphans, Lab Structure, duration |
| F | `cross_validation.py` | Module count/title consistency across design and outlines |
| G | `automation_manifest.py` | Manifest exists and is non-empty |
| H | `vocabulary.py` | Controlled vocabulary for content type, audience, products |
| I | `auto_compute.py` | Peak environments, cost estimate, provisioning time |

Policy is loaded from a ConfigMap-mounted YAML (`/etc/ph-policy/policy.yaml`) rather than a database, which is fine for the current scale.

**Summary: The intake gate works.** Deterministic checks block submission, Central validates server-side, and the workflow only advances on success.

---

### What's Not Built

Seven features from the original spec are missing or need to be added. They fall into three categories: **spec locking** (protecting what was approved), **reviewer tooling** (helping humans make better decisions), and **lifecycle monitoring** (catching stalled or drifting projects proactively).

> **Note:** The "pragmatic path forward" suggestions below are starting points, not prescriptions. The team should evaluate these against the current architecture and propose alternatives where a better solution exists. The goal is to solve each problem; the specific mechanism is open.
>
> **Known structural concern:** `spec.yaml` is accumulating a lot of responsibility — discovery fields, infrastructure details, RCARS results, approval checklist, rejection history, workflow metadata. It works for now, but it's becoming unwieldy and may not be the right long-term storage model. Any solution proposed here that adds more data to spec.yaml should be considered provisional. If a better data model emerges (separate files, a lightweight database, structured workflow variables), these decisions should be revisited.

#### 1. Spec Contract Snapshot + Drift Detection

**What was planned:** When the approval gate passes, Central takes a snapshot of the spec — module count, titles, durations, products, learning objectives. This snapshot is the "contract." If the author changes the spec after approval (adds a module, swaps products), downstream gates detect the drift and block until re-approval.

**Why it matters:** Without it, someone can rewrite the spec to match whatever they delivered, making the approval gate meaningless. The spec is a contract between the author and the reviewers who approved it.

**Current obstacle:** The original design used a `SpecSnapshot` database model. Central is now stateless — no database.

**Pragmatic path forward (one suggestion — alternatives welcome):** Git-native spec contract. At approval time, extract the contract fields and commit a `publishing-house/.spec-contract.json` file to the project repo:

```json
{
  "contract_version": 1,
  "approved_at": "2026-07-21T14:30:00Z",
  "approved_by": "reviewer@redhat.com",
  "source_commit": "abc1234",
  "content_type": "lab",
  "audience": "intermediate",
  "products": ["OpenShift", "OpenShift Virtualization"],
  "learning_objectives": ["Deploy a VM on OpenShift...", "Configure live migration..."],
  "module_count": 4,
  "modules": [
    {"title": "Introduction to OCP Virt", "duration_min": 20},
    {"title": "Deploying VMs", "duration_min": 25}
  ],
  "total_duration_hours": 2.5
}
```

Drift detection = re-extract these fields from the current spec and diff against the committed contract file. Pure Python, no database, fits the manifest-as-truth principle. If drift is detected, downstream gates block with a specific message ("Module count changed from 4 to 5 since approval. Re-approval required.").

Re-approval overwrites `.spec-contract.json` with a new snapshot and a new `source_commit`. Git history preserves the full contract evolution.

#### 2. Post-Approval Gate Enforcement

**What was planned:** A `GateService` that runs the same check sequence at every gate boundary.

**What's needed now:** The lifecycle currently has three gate boundaries:

| Gate | Transition | What It Should Check |
|------|-----------|---------------------|
| **Gate 1** | Intake → Content/Infra Review | Structural validation (all 9 groups). This is the report reviewers see. |
| **Gate 2** | Development → Testing | Spec drift detection + content compliance (do the deliverables match the contract?) |
| **Gate 3** | Testing → Release | Final drift check + all test results present |

**Gate 1 is the priority.** It's the gate before human reviewers see the project. When a reviewer opens the project in RHDH, they should see the automated validation report — not have to read raw files and figure it out themselves. This gate runs the same `run_validation()` that intake uses, but its output is formatted as a report for the reviewer.

Gates 2 and 3 depend on the spec contract snapshot (feature #1 above). They compare the current state against what was approved.

**Design for extensibility.** Three gates is what we need today, but the mechanism should not be hardcoded to three. If a new phase is added to the lifecycle later, we should be able to insert a gate at that boundary and it should leverage the same validation runner, the same check group mapping, and the same report format. The architecture should be: define a stage key, map it to check groups, call the endpoint at the transition — done.

**Pragmatic path forward:** The validation runner already exists and is stage-aware (`STAGE_GROUPS` maps stage names to check groups in `runner.py`). This is the right pattern — it's already extensible. Extend it with new stages:

- `"review"` stage already exists in the runner (groups A, B, D, E, F) — this can generate the Gate 1 report
- Add `"development"` and `"release"` stages that run drift detection against the spec contract
- Adding a future gate = one new entry in `STAGE_GROUPS` + calling the existing validate endpoint at the new transition

The gate doesn't need to be a separate service. A single endpoint — `POST /api/v1/validate/{slug}?stage=review` — already exists. The work is: (a) call it at the right time (before content review), (b) store/surface the report where reviewers can see it, and (c) add drift-aware check groups.

#### 3. Reviewer-Informed Approvals

**What was planned:** Human reviewers receive both structural check results and an LLM quality report, then make their decision.

**Current state:** The RHDH plugin shows a project detail page with metadata, progress bar, and Approve/Reject buttons. Reviewers see the project name, content type, owner, and stage — but no automated analysis. They decide by going and reading the spec repo themselves.

**What's needed:** When a project enters `content_review`, the automated validation report from Gate 1 should be visible in the RHDH plugin. The reviewer sees:

- All deterministic checks: passed/failed/warned
- The advisory (soft) check results (see #6 below)
- Direct links to the spec files in the GitHub repo
- The approval checklist answers the author provided

The report doesn't need to be fancy — a structured list of check results with pass/fail status is sufficient. What matters is that it exists and is visible before the reviewer clicks Approve.

**Pragmatic path forward — multiple options, team decides:**

- **Option A — SonataFlow workflow variables.** Gate 1 produces a `ValidationResponse` (already a Pydantic model). Store the serialized result in the workflow's `workflowdata`. The RHDH plugin reads it via the existing GraphQL query and renders it on the detail page.

- **Option B — TechDocs rendering.** Generate the validation report as a Markdown file in the project repo. The project template already wires up TechDocs (`backstage.io/techdocs-ref` annotation exists, and the intake skill generates `mkdocs.yml`). The report would render directly in the RHDH TechDocs tab — no plugin changes needed.

- **Option C — Hybrid.** Store structured data in workflow variables for programmatic access (gating logic, audit), but also render a human-readable Markdown version via TechDocs for reviewers who want to read it in-context.

The team should evaluate which approach fits best given the current RHDH plugin capabilities and what's easiest to maintain.

#### 4. Audit Trail

**What was planned:** Immutable `GateRecord` database model recording every gate decision.

**Current state:** Nothing. If someone asks "who approved this spec and what did they see," there's no answer.

**Pragmatic path forward:** Two options, both git-native:

**Option A — SonataFlow workflow variables.** Gate results and approval decisions are stored in the workflow's `workflowdata`. SonataFlow's Data Index already persists these in PostgreSQL (the workflow DB, not a Central DB). The RHDH plugin already reads workflow variables via GraphQL. This is the lowest-effort path — no new infrastructure, just richer data in the existing workflow.

**Option B — Committed audit file.** Each gate decision is appended to `publishing-house/.gate-history.json` in the project repo. Git provides the immutable history. More transparent (anyone can read the repo), but requires a commit on every gate decision.

Recommendation: Option A for the MVP. The data lives where the workflow lives. Option B can be added later for transparency.

#### 5. Reviewer Access Control

**What was planned:** The person who wrote the spec cannot be the person who approves it (for `rhdp_published` mode).

**Current state:** Any authenticated user can approve anything. The RHDH plugin sends the approval CloudEvent without checking who's clicking.

**What's actually needed:** This is an ACL problem, not just a negative check. It's not enough to say "the author can't approve their own work" — only **designated reviewers** should be able to approve. The content review gate requires content reviewers; the infra review gate requires infra reviewers. The author will never be one of those people, which handles self-approval prevention as a side effect.

The approval model needs:
- A defined list of who can approve content reviews (content team)
- A defined list of who can approve infra reviews (infra team)
- Enforcement at the plugin level (hide/disable Approve for unauthorized users)
- Enforcement at the Central API level (reject approval events from unauthorized users)

**Pragmatic path forward:** Where the reviewer lists live is an open question — Keycloak groups, a ConfigMap, or hardcoded in the RHDH plugin config are all options. The team should decide based on how often the reviewer list changes and who manages it. The key requirement is that the enforcement happens in both the frontend (UX) and the backend (defense-in-depth).

#### 6. Advisory (Soft) Check — Nice to Have

> **This is a nice-to-have.** It does not block any other feature and is not on the critical path. The deterministic checks (features #1-5) are the priority. This can be added later when the gate enforcement foundation is solid.

**What was planned:** A lightweight LLM check comparing spec content against structural expectations. Advisory only — never blocks the gate, but flags potential issues for the reviewer.

**Current state:** Not implemented. All validation is deterministic.

**What it would do:** "Here's what the spec says each module should cover. Here's the module outline. For each module, does the outline appear to address the spec's learning objectives? One sentence per module."

**Pragmatic path forward (when prioritized):** Add a new check group (e.g., Group J) to the validation runner. Unlike groups A-I, this group calls an LLM via LiteLLM (already integrated into Central for key generation). Results are tagged as `status: ADVISORY` rather than `PASS`/`FAIL`, so they never block the gate but appear in the validation report.

Model choice: Use a lightweight/open-source model via LiteLLM (Granite, Llama, or similar). Not a frontier model — this is a basic alignment check. Good visibility for showing Publishing House uses appropriate model tiers.

#### 7. Inactivity Detection + Proactive Drift Flagging

**What was planned:** Not in the original spec. This is a new requirement identified during this review.

**The problem:** Two things can go wrong silently during the development phase:

1. **Stalled projects.** A project enters development and nothing happens for weeks. No one notices until someone asks "whatever happened to that lab?" There's no mechanism to flag projects with no activity.

2. **Drift without a gate trigger.** Drift detection (feature #1) runs at gate boundaries — but gates are triggered by the author requesting advancement. If someone changes the spec mid-development and never requests a gate check, the drift goes undetected until they do.

**What's needed:**
- A periodic check that examines all active workflow instances and flags projects with no git activity (commits, pushes) for a configurable period (e.g., 14 days)
- Proactive drift detection on push — when a commit lands in a project repo, compare the current spec against the contract snapshot and flag if drifted
- Notifications to the project owner and/or the content team when either condition is detected

**Pragmatic path forward:** The mechanism depends on what infrastructure is available:

- **GitHub webhooks → Central API** would allow push-triggered drift checks
- **A scheduled job** (CronJob on OpenShift, or a SonataFlow timer) could poll for stale projects
- **SonataFlow's built-in timeouts** already exist (168-hour / 7-day timeout per waiting state). These could be shortened or made configurable, with a notification sent when a timeout fires rather than silently advancing

The team should decide which approach fits. The key requirement: if a project goes quiet or its spec drifts, someone gets told about it before the next gate request.

---

### Gate Enforcement — Summary

| # | Feature | Blocked By | Priority |
|---|---------|-----------|----------|
| 1 | Spec contract snapshot | Nothing — git-native | High — everything depends on it |
| 2 | Gate 1 report (intake→review) | Nothing — validation runner exists | High — enables reviewer-informed approvals |
| 3 | Reviewer sees report in RHDH | Gate 1 report | High — the point of Gate 1 |
| 4 | Audit trail | Nothing | Medium |
| 5 | Reviewer access control (ACL) | Nothing | Medium — needs team decision on where lists live |
| 6 | Drift detection (Gates 2, 3) | Spec contract snapshot | Medium |
| 7 | Inactivity detection | Nothing | Medium — needs team decision on mechanism |
| 8 | Advisory (soft) check | Nothing | Nice to have — not blocking |

Recommended order: Spec contract snapshot (#1) → Gate 1 report + reviewer UI (#2, #3) → Audit trail (#4) → Reviewer ACL (#5) → Drift detection (#6) → Inactivity detection (#7) → Advisory check (#8, when prioritized).

---

## Part 2: Intake Skill — Question Bloat

### The Problem

The intake skill asks **18 distinct questions** (Q1-Q18 minus Q10 which is self-skipped, plus Q22-Q24), many with multi-part follow-ups. In testing, the interview became onerous — by Q15 the author is fatigued, and the infrastructure questions feel like filling out a form rather than having a conversation about their idea.

### Current Question Flow

```
Q1:  What will someone be able to DO? (goal)               ← discovery
Q2:  Who is this for? (audience)                            ← discovery
Q3:  Which products? (products)                             ← discovery
     → Fire RCARS advisor silently
Q4:  Content type? (lab/demo/workshop)                      ← often pre-set
Q5:  Showroom type? (classic/zero_touch)                    ← often pre-set
Q6:  What does the learner start with? (environment)        ← infra
Q7:  Total duration?                                        ← discovery
Q8:  Module structure? (propose + confirm)                  ← discovery
Q9:  Module relationship? (sequential/independent)          ← discovery
Q10: [skipped — covered by Q2]
Q11: OpenShift version?                                     ← infra
Q12: Infrastructure requirements? (cluster type, sizing,    ← infra (multi-part)
     cloud provider, automation approach)
Q13: Reference material?                                    ← discovery
Q14: Concurrent users? (conditional)                        ← infra
Q15: AI/MaaS requirement? (conditional, cascading)          ← infra
Q16: AAP version? (conditional)                             ← infra
Q17: External services / egress?                            ← infra
Q18: Non-GA products? (conditional)                         ← infra
Q22: Prerequisites verifiable in-lab?                       ← approval checklist
Q23: Assessment strategy?                                   ← approval checklist
Q24: Differentiation? (polls RCARS results)                 ← approval checklist
```

That's 20 interaction points (counting conditionals), asked one at a time, in a fixed order. The current skill writes to spec.yaml after every single answer.

### What's Wrong

1. **Infrastructure questions are form-filling, not conversation.** Q6, Q11, Q12, Q14-Q18 are eight separate questions about infrastructure. Most of them have predictable answers derivable from the product list. If the products are "OpenShift" and "OpenShift Virtualization," the cloud provider is almost certainly CNV, the cluster type is multinode, and MaaS is not needed. Asking each one individually wastes the author's time.

2. **Fixed order doesn't match natural conversation.** The author wants to talk about their idea, not answer a questionnaire. Discovery questions (Q1-Q3, Q7-Q9, Q13) should flow naturally. Infrastructure questions should come as a confirmation step, not interleaved.

3. **Conditional questions still interrupt.** Even though Q14-Q18 are conditional, the conditions are broad enough that most labs trigger 3-4 of them. Each interrupts the conversation flow.

4. **Per-question writes create a questionnaire rhythm.** The current instruction — "after each answer, immediately write to spec.yaml" — was a deliberate defensive choice. If the conversation crashes at Q15, Q1-Q14 are saved. But it creates a mechanical answer→write→answer→write cadence that makes the intake feel like filling out a form, not having a conversation about an idea.

### Design Principle: Write Per Phase, Not Per Question

The restructured intake uses **per-phase writes** instead of per-question writes. Within each phase, the skill has a natural conversation. At the end of the phase, it writes all captured fields to spec.yaml in one commit before moving to the next phase.

This preserves the safety benefit (each phase's work is checkpointed before the next begins) without the questionnaire cadence. And it lets the skill do things like "you mentioned AAP in your products — I'll factor that into the infrastructure profile" during discovery, without immediately having to ask and write the AAP version.

| Phase | Conversation Style | Write Point |
|-------|-------------------|-------------|
| Phase 1: Discovery | Conversational — questions flow naturally, one topic leading to the next | Write all discovery fields to spec.yaml at end of phase |
| Phase 2: Design Doc | Generative — propose structure, get feedback | Write design.md, then run inline structure check |
| Phase 3: RCARS Vetting | Discussion — present catalog overlap, adjust design if needed | Write RCARS results + any design adjustments to spec.yaml |
| Phase 4: Module Outlines | Generative — produce from validated, RCARS-adjusted design | Write module outline files |
| Phase 5: Infra Confirmation | Confirm-or-adjust — one interaction | Write all infra fields to spec.yaml |
| Phase 6: Finalize + Submit | Checklist, file generation, Central validation | Write checklist + generated files, commit, push, submit |

**Key behavioral change:**
- **Old instruction:** "After each answer, immediately write to spec.yaml"
- **New instruction:** "Within a phase, focus on the conversation. At the end of the phase, write all captured fields to spec.yaml in one commit before moving to the next phase."

### Proposed Restructure

Collapse the 20 interaction points into roughly 10, organized by conversation phase:

```
Phase 1 — Quick Discovery (5-6 questions)
  "We'll start with a few questions about your idea, then move through
  design, RCARS validation, module outlines, infrastructure, and submission.
  Six phases total."

  Q1: What will someone be able to DO?
  Q2: Who is this for?
  Q3: Which products?
  Q4: Content type (skip if pre-set)
  Q5: Showroom type (skip if pre-set)
  Q6: How long should this take?
  → WRITE: all discovery fields to spec.yaml + commit
  → "Discovery complete. Next: design doc. (4 phases remaining)"

Phase 2 — Design Generation
  → Propose module structure based on discovery (replaces Q8, Q9)
  → Author approves/adjusts — or tells the skill they already wrote
    design.md themselves ("I already filled this out, proceed")
  → WRITE: design.md + commit
  → INLINE CHECK: Run design structure validation (required sections present,
    valid action verbs in learning objectives, no template placeholders,
    durations in range). This catches structural problems before generating
    outlines. Non-blocking — show results, let author fix before proceeding.
  → "Design doc complete and validated. Next: RCARS vetting. (3 phases remaining)"

Phase 3 — RCARS Vetting (see Part 3)
  → Central generates a summary of design.md and queries RCARS advisor
  → Present advisor response: overlap, gaps, differentiation opportunities
  → Author reviews and decides whether to adjust the design
  → Author can also edit design.md directly and commit — the skill picks
    up the changes. Not everything has to go through the conversation.
  → If adjustments made → re-run inline structure check
  → WRITE: RCARS results + any design adjustments + commit
  → "RCARS vetting complete. Next: module outlines. (2 phases remaining)"

Phase 4 — Module Outlines
  → Generated from the validated, RCARS-adjusted design
  → Author reviews — or tells the skill they already wrote the outlines
  → WRITE: module outline files + commit
  → "Module outlines complete. Next: infrastructure confirmation. (1 phase remaining)"

Phase 5 — Infrastructure Confirmation (1 interaction, replaces Q6, Q11-Q18)
  → Derive defaults from products + content type:
    - OCP Virt → CNV, multinode, 6 workers
    - AAP → ansible automation approach
    - AI keywords → ask MaaS vs GPU
  → Present as a single proposed profile:
    "Based on your products, I'd suggest: CNV, multinode, OCP 4.20,
    6 workers (8 vCPU, 32GB), no AI, no external services.
    Does this look right, or should I adjust anything?"
  → Author confirms or adjusts — or edits spec.yaml directly
  → Only ask follow-ups for non-standard choices (GPU justification, non-GA access plan)
  → WRITE: all infra fields to spec.yaml + commit

Phase 6 — Finalize + Submit
  Q22: Prerequisites verifiable?
  Q23: Assessment strategy?
  Q24: Differentiation (pre-filled from Phase 3 RCARS conversation)
  → WRITE: checklist fields to spec.yaml
  → Generate jira.yaml, automation-manifest.yaml, mkdocs.yml
  → Author checkpoint: "Are you happy with this and ready to submit for review?"
  → Commit + push
  → Call Central API (ph-intake.py) — runs full deterministic validation
    (all 9 check groups server-side), advances workflow on success,
    returns specific failures to fix on 422
  → If validation fails → fix issues, re-commit, re-submit (loop)
```

### Design Template Must Ship in the Project Repo

The design.md template currently exists only as a skill reference file (`skills/intake/references/design-template.md`). It is **not** in the project template repo (`rhdp-publishing-house-template`, `rearchitecture` branch). The `publishing-house/spec/` directory contains `module-outline-template.md` and `automation-manifest.yaml`, but no design template.

This means someone doing intake without the skill — filling out the spec manually or using minimal AI assistance — has no idea what `design.md` should look like. They'd have to guess the section structure, and the deterministic validation at submission would reject them for missing sections they didn't know were required.

**Fix:** Add `design-template.md` to `publishing-house/spec/` in the project template repo. When a new project is scaffolded, the template is there for anyone to see and fill out. The skill uses it to generate design.md; manual authors use it as a reference.

**Single source of truth:** The template in the project repo is the canonical version. The skill must reference the file from the cloned project (`publishing-house/spec/design-template.md`), not maintain its own copy. The current `skills/intake/references/design-template.md` should be removed and replaced with a reference to the project file. Copies get out of sync — there must be exactly one.

### Inline Design Structure Check

The inline check at the end of Phase 2 is a critical addition. Currently, all deterministic checks run at submission (Phase 6). That means the design doc and module outlines are both generated before any structural validation happens. If the design is missing required sections or has invalid learning objective verbs, the author doesn't find out until after they've also generated all the module outlines — wasting time.

The inline check runs the same Group D checks that Central runs at submission:
- All 11 required design.md sections present
- H1 title is not a placeholder
- Learning objectives use valid action verbs (from policy)
- No unfilled template placeholders
- Module durations in 10-60 minute range
- Module Map table exists

This can be run locally (the skill reads design.md and checks against the policy it already loaded in pre-flight) or via Central's existing `POST /api/v1/validate/{slug}?stage=design` endpoint (would need a new stage entry mapping to Group D only). The local approach is faster and doesn't require an API call; the Central approach ensures the checks are identical to what runs at submission.

**This check is non-blocking.** It shows results and lets the author fix issues before proceeding. It does not gate the flow — the author can acknowledge warnings and move on. The hard gate is still at submission (Phase 6).

### Before vs. After

| Metric | Current | Proposed |
|--------|---------|----------|
| Total interaction points | ~20 | ~10-12 |
| Infrastructure questions | 8 individual | 1 confirmation step |
| Fixed question order | Yes — rigid | No — phased by conversation type |
| Write cadence | After every answer (~20 writes) | After every phase (~6 writes) |
| Structural checks | Only at submission (Phase 6) | Inline after design + full at submission |
| RCARS validates design | No — results arrive after design | Yes — RCARS reviews the design, informs adjustments |
| Author fatigue risk | High (by Q15) | Lower (confirm-or-adjust vs. answer-from-scratch) |

### What Stays the Same

- spec.yaml field coverage is identical — all the same data gets captured
- Conditional logic for AI, AAP, non-GA, concurrent users is preserved
- Deterministic validation via Central at submission is unchanged (all 9 groups)
- Approval checklist questions remain mandatory
- Each phase's work is checkpointed before the next phase begins (same safety as per-question writes, fewer interruptions)

---

## Part 3: RCARS Integration in the Intake Flow

Phase 3 of the intake flow (see Part 2) uses RCARS to validate the design doc against the existing RHDP catalog. This section covers what the RCARS interaction needs from Central and what needs to be built.

### What Changed From the Old Design

In the old intake flow, RCARS was queried early (after Q3, using just goal + audience + products as a natural-language query) and the results were presented late (at Q24 for differentiation, and in a separate spec refinement procedure as retrofit recommendations). The query was thin because the design doc didn't exist yet.

In the proposed flow, RCARS is queried after the design doc is generated (Phase 3). This means Central has the full design to work with — products, module structure, learning objectives, audience, duration — and can generate a much richer query to the RCARS advisor.

### What RCARS Provides

The RCARS advisor endpoint (`POST /api/v1/rcars/advisor`) accepts a natural-language query and returns a list of candidates, each with:

- `display_name` — catalog item title
- `ci_name` — catalog identifier
- `relevance_score` — percentage overlap
- `why_it_fits` — explanation of similarity
- `caveats` — where the match breaks down (gaps, outdated versions, different audience)

This is richer than the overlap endpoint (which only does keyword matching). The advisor is the right tool until RCARS implements semantic search by keywords or tags.

### What Central Needs to Do (Phase 3)

Central needs a new endpoint (or extension of the existing advisor endpoint) that:

1. **Accepts a project slug** (or repo URL + branch)
2. **Reads design.md from the project repo** via the GitHub API
3. **Generates a summary query** from the design doc — extracting products, learning objectives, audience, and content type into a natural-language query suitable for the RCARS advisor
4. **Submits the query to RCARS advisor** and polls for results
5. **Returns a structured response** to the intake skill containing:
   - Top candidates (relevance score, title, why it's similar, where it differs)
   - Identified gaps (what the design covers that existing content doesn't)
   - Overall overlap assessment

The skill then presents these results to the author and handles the conversation (keep the design as-is, or adjust). If the author adjusts the design, the inline structure check from Phase 2 re-runs to ensure the updated design is still valid.

### What Gets Stored in spec.yaml

After the RCARS conversation, regardless of whether the author adjusted the design:

```yaml
approval_checklist:
  content:
    rcars_overlap_pct: 78          # highest relevance_score from candidates
    rcars_top_matches:
      - title: "OCP Virt Getting Started"
        ci_name: "ocp4-virt-getting-started"
        url: "https://catalog.demo.redhat.com/catalog?item=ocp4-virt-getting-started"
        relevance_score: 78
        why_it_fits: "Covers VM deployment on OpenShift"
      - title: "CNV Workshop"
        ci_name: "cnv-workshop"
        relevance_score: 65
        why_it_fits: "Covers migration but targets OCP 4.14"
    differentiation: "Covers live migration on OCP 4.20..."  # pre-filled from conversation
```

The differentiation field is pre-filled from the Phase 3 conversation, so Q24 in Phase 6 can confirm it rather than asking the author to write it from scratch.

### Impact on Skill Files

| File | Change |
|------|--------|
| `intake/procedures/05-spec-refinement.md` | Eliminate — replaced by Phase 3 RCARS vetting |
| `intake/procedures/06-approval-and-submit.md` | Pre-fill Q24 differentiation from Phase 3 results |

New files needed:
- `intake/procedures/03b-rcars-vetting.md` — Phase 3 procedure: call Central's RCARS endpoint with the project slug, present results, handle design adjustments

---

## Next Steps

| Part | Owner | First Action |
|------|-------|-------------|
| Part 1: Gate enforcement | Tyrell | Review the pragmatic path forward proposals. Start with spec contract snapshot — everything else depends on it. |
| Part 2: Intake restructure | Shared | Review the proposed phase structure. Validate that the collapsed infra confirmation covers all edge cases. |
| Part 3: RCARS integration | Shared | Confirm Central can summarize design.md and query the RCARS advisor on behalf of the skill. Define the endpoint contract. |

### Dependencies

- Parts 2 and 3 are implemented together — RCARS vetting is Phase 3 of the intake flow.
- Part 1 is independent of Parts 2 and 3. Gate enforcement changes are Central API + RHDH plugin work. Intake skill changes don't affect them.
- The spec contract snapshot (Part 1, feature #1) should be designed before the intake restructure, because the intake submit step (Phase 6) needs to know what the contract file looks like.
- The inline design structure check (Phase 2) can use the existing policy file loaded during pre-flight — no new Central endpoint is strictly required, though one could be added for consistency.
