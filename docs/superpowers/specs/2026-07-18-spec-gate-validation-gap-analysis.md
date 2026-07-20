# Spec & Gate Validation Hardening — Gap Analysis

**Date:** 2026-07-18
**Reference:** [Spec & Gate Validation Hardening Design](2026-07-03-spec-gate-validation-hardening-design.md) (RHDPCD-170)
**Purpose:** Map the design spec against the current implementation — what's already built, what needs new work, and in what order.

---

## The Process Today vs What the Spec Wants

### Step 1: Author Creates a Project (RHDH Template)

**Today:** Author fills out the RHDH template form (name, type, deployment mode, tags). It creates a repo, scaffolds the files, and kicks off the SonataFlow workflow. The spec.yaml already has placeholders for all the Part 3 and Part 5 fields.

**Spec wants:** Same thing. No changes needed here.

**Verdict: Done.**

---

### Step 2: Author Runs Intake (Claude Skill in DevSpaces)

**Today:** The intake skill asks Q1–Q24 one at a time, writes design.md, module outlines, spec.yaml, jira.yaml, and automation-manifest.yaml. It validates everything client-side (structural checks, infra field checks, cross-validation, approval checklist completeness) before letting the author submit.

**Spec wants:** Same thing. The intake skill already asks every question the spec defines, in the right order, with the right conditional logic (Q14 only if per-student, Q15 only if AI keywords, etc.). It already does all the cross-validation (CV-1 through CV-5) and checks approval checklist fields (Q22–Q24).

**What's missing:** One thing — the skill validates content type, difficulty, and product names by accepting whatever the author types. The spec wants those checked against a **managed list** so "OpenShift Foobar" gets rejected. That list doesn't exist yet (see Step 2b).

**Verdict: 95% done.** The skill does all the right work. The vocabulary enforcement piece needs a backend to check against.

---

### Step 2b: Vocabulary Validation (NEW — doesn't exist)

**Today:** If the author says their product is "Red Hat Cloud Nexus Platform," the skill writes it to spec.yaml without complaint. Nothing validates it's a real product.

**Spec wants:** Central API maintains three lists — valid content types, difficulty levels, and product names — stored in a database. The skill (or ph-check.py) calls Central to validate. Product names get normalized ("Red Hat OpenShift Virtualization" and "CNV" both match). An admin dashboard lets you add new products without code changes.

**What needs building:**

- A database in Central (Central is currently 100% stateless — no DB at all)
- Database tables for vocabulary lists
- API endpoints to query and manage the lists
- Product name normalization logic (strip "Red Hat", lowercase, match abbreviations like OCP -> OpenShift)
- A dashboard page for admins to manage the lists

**Verdict: Not started. Significant new infrastructure.**

---

### Step 3: Author Submits Intake (API Call)

**Today:** The skill calls `ph-intake.py`, which hits `POST /projects/intake/{workflow_id}`. Central computes RCARS overlap, sends a CloudEvent to advance SonataFlow from Intake to ContentReview.

**Spec wants:** Same flow, but Central should also compute three additional fields before advancing:

- `peak_environments` (trivial — concurrent users x topology factor)
- `cost_per_run_est` (sizing x concurrency x hourly rates — needs a formula/lookup table)
- `provisioning_time_est` (standard CNV sizing -> known times — needs a lookup table)

These get written back to spec.yaml so reviewers can see them.

**Verdict: Mostly done.** The three auto-computed fields are small additions to the existing endpoint. No architectural change needed.

---

### Step 4: Reviews (Content Review + Infra Review)

**Today:** Both are manual. SonataFlow sits in the ContentReview and InfraReview event states waiting for a human to send an approval CloudEvent from the RHDH plugin. The reviewer looks at whatever they choose to look at. There's no structured gate check.

**Spec wants two big changes here:**

#### 4a: Server-Side Validation at the Gate (NEW)

Before a reviewer can approve, Central should re-read the spec from GitHub and run structural checks server-side. This prevents someone from editing spec.yaml after client-side validation passed and submitting a broken spec. Today, if you edit spec.yaml directly on GitHub after the skill validated it, nothing catches it.

**What needs building:**

- A `GateService` in Central that runs validation on every gate request
- A `SpecValidator` service that reads files from GitHub and checks structure (same logic as ph-check.py, but server-side and un-skippable)
- Phase integrity checks (does the manifest match the expected deployment mode profile?)

#### 4b: Infra Review Auto-Approve (NEW)

For standard setups (CNV, no GPU, no external services, no non-GA products, open-source AI, reasonable sizing), the infra review should auto-approve without a human. Only non-standard requests get routed to a person.

**What needs building:**

- Decision logic: evaluate spec.yaml fields against auto-approve criteria
- Integration with SonataFlow to auto-send the InfraReview approval event when criteria are met

#### 4c: Approver Portal Views (NEW)

Today the RHDH plugin shows a progress bar and an Approve button. The spec wants three distinct views — one per persona (Content Manager, Content Lead, Infra Team) — each linking directly to the relevant spec files so reviewers know exactly what to read.

**What needs building:**

- Plugin UI work for persona-specific review views
- Decision capture (approved / denied / needs_info per persona)
- Write decisions back to spec.yaml's approval_checklist section

**Verdict: Not started. This is the biggest gap — gate enforcement, auto-approve logic, and reviewer UX.**

---

### Step 5: Spec Contract Snapshot (NEW — doesn't exist)

**Today:** Once reviews pass, we move on. There's no record of "what was approved."

**Spec wants:** When approval passes, Central takes a snapshot of the spec — module count, titles, durations, products, learning objectives, difficulty. This snapshot is the "contract." If the author changes the spec later (adds a module, changes products), downstream gates detect the drift and block until re-approval.

**What needs building:**

- Database model for snapshots (requires the database from Step 2b)
- Extraction logic to pull contract fields from design.md and module outlines
- Drift detection: re-extract at every downstream gate, compare against snapshot
- Re-approval flow when drift is detected

**Verdict: Not started. Depends on database infrastructure.**

---

### Step 6: JiraSync (After Reviews)

**Today:** SonataFlow hits the JiraSync state, calls `POST /jira/sync`, which reads `jira.yaml` from the repo, updates the epic, closes the intake task, and creates child tasks. Then transitions to Development.

**Spec wants:** Same thing. Already implemented.

**Verdict: Done.**

---

### Step 7: Development (Writing Content)

**Today:** Author writes content. The SonataFlow workflow sits in the Development state.

**Spec wants:** At the writing-to-editing gate, Central should:

1. Check spec drift (has the spec changed since approval?)
2. Check content compliance (do the AsciiDoc files match the approved module count/titles?)
3. Run an advisory LLM content alignment check (non-blocking)

**Verdict: Not started. Depends on Step 5 (snapshots) and Step 4a (GateService).**

---

## Summary Table

| Process Step | Skill-Side (Intake) | Central-Side (API/Platform) |
|---|---|---|
| Project creation | Done | Done |
| Intake questions & file generation | Done (Q1-Q24, all files) | N/A |
| Client-side validation | Done (ph-check.py + skill) | N/A |
| Vocabulary enforcement | N/A | Not built (needs DB) |
| Intake submission + RCARS | N/A | Done |
| Auto-computed fields (peak, cost, time) | N/A | Not built (small addition) |
| Server-side validation at gates | N/A | Not built |
| Infra auto-approve | N/A | Not built |
| Approver portal views | N/A | Not built (plugin work) |
| Spec contract snapshots | N/A | Not built (needs DB) |
| Spec drift detection | N/A | Not built (needs DB + snapshots) |
| JiraSync | Done | Done |
| Content compliance at dev gates | N/A | Not built (needs snapshots + GateService) |

---

## Prioritized Build Order

If tackling this incrementally, here is a recommended sequence:

### Quick Wins (no database required)

1. **Auto-computed fields** — Add `peak_environments`, `cost_per_run_est`, `provisioning_time_est` computation to the `submit_intake` endpoint. Small code change, adds visible value to reviewers immediately.

2. **Server-side validation endpoint** — Port ph-check.py logic into a Central endpoint that reads from GitHub and validates. Call it at intake submission to double-check client-side work. Catches tampered specs.

### Infrastructure Unlock

3. **Database + Vocabulary lists** — Add PostgreSQL to Central (can share SonataFlow's existing PostgreSQL). Create `VocabularyList` model, seed with starter data, add CRUD endpoints and product name normalization. This unblocks everything below.

### Gate Enforcement

4. **Infra auto-approve** — Evaluate spec.yaml fields against auto-approve criteria. Auto-send approval event for standard setups. Immediately reduces reviewer load.

5. **GateService + SpecValidator** — Full gate enforcement at every transition. Fresh git read, structural validation, phase integrity check, gate record logging.

### Approval Locking

6. **SpecContractService + snapshots** — Snapshot creation at approval, drift detection at downstream gates. Prevents unreviewed spec changes from reaching production.

### Reviewer Experience

7. **Portal approver views** — Persona-specific review UX in the RHDH plugin. Three views, structured decisions, links to spec files.

Items 1-2 are quick wins that can ship independently. Item 3 is the infrastructure unlock for everything else. Items 4-7 build on top in order of impact.

---

## Components Reference

| Component | Exists? | What It Does |
|---|---|---|
| `PhaseEngine` | No | Validates manifest phases against deployment mode profile |
| `SpecValidator` (Central) | No | Server-side structural validation (design.md, module outlines, spec.yaml) |
| `SpecContractService` | No | Snapshot creation, drift detection, content compliance |
| `GateService` | No | Orchestrates all checks at every gate transition |
| `VocabularyList` model | No | DB model for managed content type, difficulty, product name lists |
| `SpecSnapshot` model | No | DB model for approved spec contract snapshots |
| `GateRecord` model | No | DB model for gate decision audit trail |
| Intake skill (SKILL.md) | Yes | Q1-Q24, file generation, client-side validation |
| ph-check.py | Yes | Client-side structural + infra + cross-validation checks |
| spec.yaml template | Yes | All Part 3 + Part 5 fields present |
| intake-questions.md | Yes | All questions with exact wording and conditional logic |
| JiraSync endpoint | Yes | Reads jira.yaml, updates epic, creates tasks |
| RCARS overlap computation | Yes | Computed at intake submission |
