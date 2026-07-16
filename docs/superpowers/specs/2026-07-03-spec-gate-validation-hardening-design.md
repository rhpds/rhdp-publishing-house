# Spec & Gate Validation Hardening — Intake Through Writing

**Jira:** RHDPCD-170
**Date:** 2026-07-03
**Author:** Nate Stephany
**Status:** Design

---

## Overview

Harden the deterministic (Python, no LLM) validation checks across the full intake-to-review pipeline. Ensure the approved spec is structurally correct, locked at approval, and enforced at every downstream gate.

The work splits into two parts: Part 1 hardens the intake and approval gate with structural checks and controlled vocabulary. Part 2 adds a spec contract snapshot at approval and enforces it at every downstream gate.

### Architecture: Approach B — New SpecContractService

Extend existing services where the work naturally fits (PhaseEngine for phase validation, SpecValidator for structural checks). Create one new service — `SpecContractService` — that owns the full spec contract lifecycle: snapshot creation, drift detection, and content compliance comparison. GateService orchestrates by calling the right services at each gate.

### Design Principles

- Deterministic Python checks are the default. LLM evaluation is advisory, never a gate blocker on its own.
- The approval gate creates a locked contract. Downstream gates enforce it at every checkpoint.
- How content gets written is the author's choice. What gets validated is identical regardless.
- Error messages are specific and actionable: file name, expected heading, what was found instead, line number.
- Fresh read from git (via GitHub API) at every gate request. Cached data is for status display and early warnings only.

---

## Part 1: Intake & Approval Gate

### 1. Phase Integrity Check

**Where:** `PhaseEngine` — new method `validate_phase_profile(manifest, deployment_mode)`

Compares phases in `manifest.lifecycle.phases` against the expected phase profile for the deployment mode. Returns extra phases (in manifest but not in profile) and missing phases (in profile but not in manifest).

**Runs at:**
- Every gate request in GateService, before any other checks
- Every manifest sync in RefreshService

**Behavior:** Gate rejects with a specific message if phases don't match:

> "Manifest lifecycle does not match the 'rhdp_published' profile: unexpected phase 'custom_review', missing phase 'security_review'."

**Edge case:** Phases with `status: skipped` must still be present in the manifest. Skipping is a valid state; removing the phase entirely is not. The profile defines the shape; status defines progress.

### 2. Controlled Vocabulary

**Where:** `SpecValidator` — vocabulary validation methods. Database-backed lists managed via Central API and dashboard.

**Three vocabulary lists:**

| List | Initial Values | Matching |
|------|---------------|----------|
| **Content type** | `lab`, `demo` | Exact, case-insensitive |
| **Difficulty level** | `beginner`, `intermediate`, `advanced` | Exact, case-insensitive |
| **Product names** | ~30 official Red Hat products | Normalization + abbreviation map |

All three are expandable lists stored in the database, seeded from a starter set on first deployment, and managed via the Central dashboard after that.

#### Product name matching — two-layer normalization

Product names use a two-layer matching approach to accept common shorthand without maintaining exhaustive alias lists:

**Layer 1 — Normalization:** Strip "Red Hat" prefix, lowercase, collapse whitespace, strip trailing version numbers. This handles the majority of naming variations automatically:
- "Red Hat OpenShift Virtualization" → `openshift virtualization`
- "OpenShift Virtualization" → `openshift virtualization`
- Both match. No aliases needed.

**Layer 2 — Abbreviation map:** Small, stable set of well-known acronyms (~15-20 entries):
- `OCP` → OpenShift
- `AAP` → Ansible Automation Platform
- `RHEL` → Enterprise Linux
- `RHOAI` → OpenShift AI
- `CNV` → OpenShift Virtualization
- `RHDH` → Developer Hub

Adding a new product is one line in the canonical list. Adding a new acronym is one line in the abbreviation map. Minimal ongoing maintenance.

**Validation behavior:** Accept anything that normalizes to a known product. Reject completely unrecognized products. No suggestions, no corrections — if we recognize it, it passes.

**Error message:**

> "Product 'Cloud Nexus Platform' is not recognized. If this is a valid Red Hat product, add it via the Publishing House dashboard."

#### Dashboard management

Central exposes API endpoints for CRUD operations on all three vocabulary lists. The dashboard provides a simple admin page for adding, removing, and editing entries. This avoids requiring Python file edits to manage vocabulary.

#### Future expansion

The hardcoded starter list is validated against RCARS catalog data during initial coding. Over time, as RCARS data quality improves, the product list can be expanded from RCARS data. But RCARS is not the authority — the curated list is.

### 3. Module Spec Validation

**Where:** `SpecValidator` — new method `validate_module_specs(spec_dir)`

Iterates over `spec/modules/module-*.md` files and checks each against required sections from the module outline template:

- Brief Overview
- Audience and Time
- What You Will See, Learn, and Do (or "See/Learn/Do")
- Lab Structure (with at least one table row)
- Key Takeaways

Same heading-based structural check used for design.md — case-insensitive substring matching. No content quality judgment, just "is the section there and non-empty."

**Additional checks per module:**
- Lab Structure has at least one row in the table
- Duration is specified in Audience and Time
- No template placeholders (reuses existing placeholder regex)

**Does NOT check:**
- Detailed Steps (optional, varies by module complexity)
- Infrastructure Notes (explicitly optional per template)
- Content quality or step accuracy (that's the human approver's job)

**Runs at:** Approval gate — incomplete module specs block approval. Also runs as part of spec drift detection on every sync.

**Error messages are per-file and per-section:**

> "module-02-deploying-vms.md: Missing required section 'Key Takeaways'. Found sections: Brief Overview, Audience and Time, See/Learn/Do, Lab Structure."

### 4. Template Rename

**Where:** `rhdp-publishing-house-template` repo

Rename `publishing-house/spec/SPEC-TEMPLATE.md` to `publishing-house/spec/module-outline-template.md`.

Current name is ambiguous — it's unclear whether it's a template for design.md or for module outlines. Since Central's SpecValidator parses module specs against this template's sections, the name must be unambiguous.

**No backwards compatibility.** The old name is not supported. Any code referencing `SPEC-TEMPLATE.md` is updated to the new name. Existing project repos still have the old file — that's fine, it's a read-only reference document, not something Central parses from project repos.

---

## Part 2: Post-Approval Gate Enforcement

### 5. Spec Contract Snapshot

**Where:** New `SpecContractService` + new `SpecSnapshot` DB model

#### SpecSnapshot model

| Column | Type | Purpose |
|--------|------|---------|
| `id` | UUID, PK | |
| `project_id` | UUID, FK, indexed | |
| `snapshot_data` | JSONB | Extracted contract fields |
| `source_commit` | str(40) | Git commit SHA when snapshot was taken |
| `is_current` | bool | Only one active snapshot per project |
| `superseded_by` | UUID, FK to self, nullable | Links to replacement if re-approved |
| `created_at` | datetime | |

#### Snapshot data structure

Pure Python extraction from design.md + module specs. No LLM in the extraction chain.

```json
{
  "content_type": "lab",
  "difficulty": "intermediate",
  "products": ["OpenShift", "OpenShift Virtualization"],
  "learning_objectives": ["Deploy a VM on OpenShift...", "Configure live migration..."],
  "module_count": 4,
  "modules": [
    {"title": "Introduction to OCP Virt", "duration": "20 min"},
    {"title": "Deploying VMs", "duration": "25 min"},
    {"title": "Live Migration", "duration": "20 min"},
    {"title": "Troubleshooting VMs", "duration": "25 min"}
  ],
  "total_duration": "2 hours",
  "section_counts": {
    "design_md": 9,
    "module_specs": 4
  }
}
```

Extraction uses Python markdown parsing — heading extraction, table parsing, bullet list parsing. Same techniques SpecValidator already uses. If the parser can't extract a field, that's a validation error — the markdown isn't following the template.

**Error messages must be specific about extraction failures:**

> "design.md: Could not extract learning objectives. Expected a bulleted list under '## Learning Objectives' (line 18), but found a paragraph. Use '- ' bullet syntax."

#### When snapshots are created

- **Approval gate passes** → SpecContractService creates the initial snapshot, marks `is_current = True`
- **Spec re-approved after modification** → New snapshot created, old snapshot gets `is_current = False` with `superseded_by` pointing to the new one

Snapshot history is preserved — trace back through `superseded_by` to see contract evolution. Only the current snapshot is used for downstream gate comparisons.

### 6. Spec Compliance Checks at Downstream Gates

**Where:** `SpecContractService` — methods `check_spec_drift()` and `check_content_compliance()`

Two checks run at the **writing→editing** and **editing→code_review** gates:

#### Check 1 — Spec drift detection

Re-extract contract fields from current design.md + module specs and compare against the current snapshot.

- **All fields match** → Spec is still approved, proceed
- **Contract fields changed** → Flag as modified, gate blocks:

> "Spec has been modified since approval. Changed fields:
> - Module count: 4 → 5 (added: 'Troubleshooting VMs')
> - Learning objective added: 'Diagnose VM boot failures'
> Re-approval required before proceeding."

#### Check 2 — Content compliance (deterministic)

Parse AsciiDoc content and compare structural metadata against the snapshot:

- Module count — count of module page files
- Module titles — from nav.adoc entries or page titles
- Presence of content for each module (non-empty files)

> "Content does not match the approved spec. Expected 4 modules, found 3. Missing: 'Troubleshooting VMs'."

This is the deterministic structural check. Whether the content *quality* matches what the spec promises is handled by the advisory LLM check and ultimately by human reviewers.

#### Two-tier drift model

| Tier | What changes | Detection | Action |
|------|-------------|-----------|--------|
| **Structural integrity** | Sections present, no placeholders, structure valid | Automated on every sync | Auto-pass, spec health stays green, snapshot unchanged |
| **Contract field drift** | Module count/titles, products, learning objectives, difficulty, durations, content type | Automated on every sync + gate | Blocks downstream gates, requires human re-approval via approval gate |

#### Advisory content alignment check (non-deterministic)

At the **writing→editing gate** and **on-demand via MCP**, Central runs a lightweight LLM check comparing AsciiDoc content against the approved spec snapshot.

**Model tier:** Lightweight / open-source preferred (e.g., model running on MaaS). Not a frontier model — this is a basic alignment check, not a deep review.

**Prompt pattern:** "Here's what the spec says each module should cover. Here's the AsciiDoc content. For each module, does the content appear to address the spec? One sentence per module."

**Result:** Advisory only, never blocks the gate.

### 7. Spec Lock Model — Summary

1. **Approval gate passes** → Snapshot created. This is the contract.
2. **Author writes content** → Deterministic checks run on every sync.
3. **Author modifies the spec** → Drift detection catches it. Downstream gates block until re-approved.
4. **Re-approval needed** → Full flow: Python structural checks → LLM quality review → human approver.
5. **Downstream gates** → Always compare against the latest approved snapshot.

### 8. Writing Mode Choice

After the approval gate passes, the orchestrator records writing mode:

```yaml
lifecycle:
  phases:
    writing:
      writing_mode: self_provided | assisted
```

**Same validation either way.** The writing→editing gate runs identical checks regardless of writing mode.

---

## Approval Gate Flow — Complete Picture

1. **Python structural checks (automated, hard gate)** — if ANY fail → gate rejects immediately.
2. **LLM quality review (automated, advisory)** — not a gate blocker on its own.
3. **Human approver (authority)** — must be a different person than the author (for rhdp_published).

---

## Gate Request Flow — All Gates

1. Fresh read from git
2. Parse manifest, design.md, module specs
3. Phase integrity check
4. Structural validation
5. Spec drift check (post-approval gates)
6. Content compliance (post-approval gates)
7. Advisory LLM check (writing→editing gate)
8. Gate decision
9. Record GateRecord

---

## Components Changed

| Component | Changes | Repo |
|-----------|---------|------|
| `PhaseEngine` | Add `validate_phase_profile()` | Central |
| `SpecValidator` | Add vocabulary validation, module spec validation | Central |
| `SpecContractService` | **New.** Snapshot creation, drift detection, content compliance | Central |
| `SpecSnapshot` model | **New.** DB model for contract snapshots | Central |
| `VocabularyList` model | **New.** DB model for managed vocabulary lists | Central |
| `GateService` | Call new validators at appropriate gates | Central |
| `RefreshService` | Call drift detection on every sync | Central |
| `MCP gate tools` | Add on-demand content alignment check endpoint | Central |
| `Dashboard` | Add vocabulary management admin page | Central |
| `SPEC-TEMPLATE.md` | Rename to `module-outline-template.md` | Template repo |
| `Alembic migration` | Add SpecSnapshot + VocabularyList tables | Central |

---

## Out of Scope

- LLM-based quality validation improvements (spec reviewer already exists)
- Automation phase self_provided/assisted mode (future, same pattern as writing)
- RCARS-driven automatic product list expansion (future, depends on RCARS data quality)
- Full editorial review automation (editor skill handles this separately)
- Showroom AsciiDoc content quality checks beyond structural metadata

---

## Part 3: Infrastructure Requirements Intake & Validation

**Added:** 2026-07-14 | **Jira:** RHDPCD-183

### New spec.yaml Fields

```yaml
spec:
  environment:
    ocp_version: "4.18"
    topology: "shared-cluster"
    max_concurrent_users: 25
    aap_version: ""
    ai_requirement: "maas"        # maas | gpu | none
    ai_model_tier: "open-source"  # open-source | frontier
    ai_model_name: ""
    ai_justification: ""          # required if frontier or gpu
    non_ga_products: []
    non_ga_access_plan: ""
    external_services: []
    worker_count: 6
    worker_cpu: 8
    worker_ram_gb: 32
    worker_disk_gb: 100
    gpu_nodes: 0
    gpu_type: ""
    rhel_node_count: 0
    rhel_node_vcpu: 0
    rhel_node_ram_gb: 0
    rhel_node_disk_gb: 0
```

### New Intake Questions (Q14–Q18)

**Q14: Concurrent Users** — ask when topology = per-student or cnv-pool
> "How many students will use this simultaneously at peak?"

**Q15: AI / MaaS Requirement** — ask when AI keywords in products
> "Does this lab use AI or LLMs at runtime? MaaS / Dedicated GPU / None."
> If MaaS: "Which model tier? Open-source (default) or frontier/premium?"
> If frontier: "Why is open-source insufficient? Be specific."

**Q16: AAP Version** — ask when AAP in products
> "Which version of AAP does this require?"

**Q17: External Services / Network Egress**
> "Does this lab call any external services outside the cluster? List each by name."

**Q18: Non-GA Products** — ask when any product is non-GA or tech preview
> "Does this lab use non-GA products, tech previews, or beta features? If yes, how will you provide access during provisioning?"

### Infra Review Gate: Auto-Approve vs Human Escalation

**Auto-approved when ALL of:** ai_requirement=maas OR none, ai_model_tier=open-source, topology=shared-cluster, gpu_nodes=0, external_services empty, non_ga_products empty, sizing within standard bounds, CNV cloud provider.

**Human review when ANY of:** gpu required, frontier model, per-student >50 users, external services, non-GA products, non-CNV provider, oversized cluster.

### Validation Rules

| Condition | Rule | Level |
|---|---|---|
| topology = per-student or cnv-pool | max_concurrent_users required | FAIL |
| AAP in products | aap_version required | FAIL |
| ai_requirement = gpu | ai_justification required | FAIL |
| ai_model_tier = frontier | ai_justification with open-source comparison required | FAIL |
| AI keyword in products AND ai_requirement not set | Q15 must be answered | FAIL |
| external_services vague entries | Named services required | FAIL |
| gpu_nodes > 0 AND gpu_type empty | GPU type required | FAIL |
| non_ga_products non-empty AND non_ga_access_plan empty | Access plan required | FAIL |
| worker sizing fields missing | All four fields required | FAIL |

---

## Part 4: Spec Cross-Validation

**Added:** 2026-07-14 | **Jira:** RHDPCD-183

Deterministic Python checks ensuring design.md, module outline files, and spec.yaml are consistent. Run at intake self-check, ph-check.py, Central intake endpoint, and approval gate.

**CV-1: Module Count** — Module Map table count == number of module-0N-*.md files  
**CV-2: Module Title Alignment** — Each Module Map title slug matches an outline file  
**CV-3: Learning Objectives Coverage** — Each objective traceable to at least one module outline's See/Learn/Do (keyword match, ≥50% threshold → WARN)  
**CV-4: Duration Consistency** — Total duration in design.md ≈ sum of module durations (>20% diff → WARN)  
**CV-5: spec.yaml Module List** — spec.modules titles must match design.md Module Map exactly

---

## Part 5: Persona-Based Approval Packet

**Added:** 2026-07-14 | **Jira:** RHDPCD-183

---

### Overview

Three personas review a spec before it can move to content review and generate a Jira ticket. This part specifies:

1. What each persona needs to see — all derived from reading the spec, design.md, and module outlines directly
2. New intake questions (Q22–Q24) that capture fields the system cannot derive
3. Auto-computed fields the system derives (not authored)
4. A structured `approval_checklist` in spec.yaml — one section per persona with their decision

**Design principle:** The spec is the source of truth. Personas read the spec — they do not receive a synthesized summary. The portal links to the relevant files. Each persona decides by reading, not by filling in a form or receiving a report.

---

### Persona 1: Content Dev Manager

**Role:** Prakhar Srivastava (or equivalent)  
**Decision:** Is the scope right? Is it doable? Is it maintainable? Who can I assign this to?

**Everything is derived from the spec — no new intake questions for this persona.**

The manager opens the spec and reads:

| What they read | Where |
|---|---|
| Module count and total duration | design.md Module Map |
| Module outlines | publishing-house/spec/modules/ (linked from portal) |
| Automation complexity | spec.yaml environment fields (non-GA, GPU, external services) |
| Author GitHub ID | spec.yaml |
| Deployment mode | spec.yaml |
| Target audience + difficulty | design.md |

**What the manager is judging:** Is the number of modules and total duration right for this topic? Are the module outlines detailed enough to assign to a writer? Is the infrastructure scope manageable? Is this the right author or do I need to assign a different one?

The manager reads the spec and module outlines directly to make this judgment. The portal links to the relevant files and shows the structured environment fields from spec.yaml (infra complexity). No summary card, no auto-generated flags — the manager reads the source.

**approval_checklist.manager:** decision + notes only. No authored fields from the author.

---

### Persona 2: Content Dev Lead

**Role:** Nate Stephany (or equivalent)  
**Decision:** Is the spec quality sufficient? Are learning objectives actionable and testable? Is it differentiated from existing content?

**New intake questions for this persona:** Q22, Q23, Q24

The content lead reads the full spec and module outlines, and additionally needs:

| Field | Source |
|---|---|
| Problem statement | design.md |
| Target audience + prerequisites | design.md |
| Learning objectives | design.md |
| Module map with durations | design.md |
| Module outlines | spec/modules/ |
| **Prerequisites verifiable in-lab** | **Q22 (new)** |
| **Assessment strategy per module** | **Q23 (new)** |
| **Author's differentiation narrative** | **Q24 (new)** |
| RCARS overlap % + top 3 matches | **AUTO-COMPUTED** |

---

### Persona 3: Infra Team

**Role:** Infra manager (TBD)  
**Decision:** Can we build this? Are the resources reasonable? Are there blockers?

The infra team reads spec.yaml environment fields (from Part 3) and additionally:

| Field | Source |
|---|---|
| OCP version, topology, sizing | spec.yaml (Part 3) |
| AI/MaaS + model tier + justification | spec.yaml (Part 3) |
| AAP version | spec.yaml (Part 3) |
| External services | spec.yaml (Part 3) |
| Non-GA products + access plan | spec.yaml (Part 3) |
| GPU nodes + type | spec.yaml (Part 3) |
| Peak environments | **AUTO-COMPUTED** — max_concurrent_users × topology factor |
| Cost-per-run estimate | **AUTO-COMPUTED** — sizing × concurrency × standard rates (indicative) |
| Provisioning time estimate | **AUTO-COMPUTED** for standard CNV sizing (lookup table); **infra fills** for non-standard (GPU, non-GA, non-CNV) |
| **AgnosticV base CI mapping** | **Infra fills** — which existing CI type supports this |

---

### New Intake Questions (Q22–Q24)

These three questions are the only new authored fields added by Part 5. They follow Q18 in the canonical intake question list.

#### Q22: Prerequisites Verifiable In-Lab

> **What must the learner know or have done before starting Module 1?**
> And: can the lab automatically validate those prerequisites when the learner starts? For example: a check script that verifies a cluster is already connected, or a pre-flight that confirms credentials exist.

- **design.md:** Answer goes into `## Prerequisites` section
- **spec.yaml field:** `approval_checklist.content_lead.prerequisites_verifiable: true | false`
- **Validation:** Must be answered. If prerequisites exist and are NOT verifiable, content lead is notified (WARN).

#### Q23: Assessment Strategy

> **How will we know the learner successfully completed each module?**
> For each module, describe how success is validated: a verification script, a visible result in the UI, a quiz question, or trust-based (learner self-reports). Be specific per module.

- **spec.yaml field:** `approval_checklist.content_lead.assessment_strategy`
- **Validation:** Required. "Trust-based" is an acceptable answer but must be explicit.

#### Q24: Differentiation from Existing Content

> **In your own words: how does this differ from existing content on similar topics?**
> Reference specific existing labs you're aware of, and explain what this adds.

- **spec.yaml field:** `approval_checklist.content_lead.differentiation`
- RCARS overlap is also computed automatically and placed in `approval_checklist.content_lead.rcars_overlap_pct` and `rcars_top_matches`.
- **Validation:** Required. Must be non-empty.

---

### Auto-Computed Fields

| Field | How computed | Written to |
|---|---|---|
| `rcars_overlap_pct` | Query RCARS by products + audience; compute overlap score | `approval_checklist.content_lead.rcars_overlap_pct` |
| `rcars_top_matches` | Top 3 RCARS matches by overlap score | `approval_checklist.content_lead.rcars_top_matches` |
| `peak_environments` | `max_concurrent_users` × 1 (per-student) or 1 (shared) | `approval_checklist.infra.peak_environments` |
| `cost_per_run_est` | Sizing × concurrency × standard hourly rates (indicative) | `approval_checklist.infra.cost_per_run_est` |
| `provisioning_time_est` | Lookup table: standard CNV sizing → estimated minutes | `approval_checklist.infra.provisioning_time_est` |

**Provisioning time lookup:** Standard CNV clusters have known provisioning times. Central maintains a lookup table (worker count × node type → estimated minutes). For non-standard setups (GPU, non-GA, non-CNV provider), infra fills the field manually after reviewing.

---

### Approval Checklist — spec.yaml Structure

```yaml
approval_checklist:

  # Content Dev Manager — no authored fields; decision + notes only
  manager:
    decision: null                # approved | denied | needs_info
    decision_notes: ""

  # Content Dev Lead — three authored fields + auto-computed RCARS
  content_lead:
    prerequisites_verifiable: null  # true | false — Q22
    assessment_strategy: ""         # Q23
    differentiation: ""             # Q24 — author's narrative
    rcars_overlap_pct: null         # AUTO-COMPUTED
    rcars_top_matches: []           # AUTO-COMPUTED: [{title, url, overlap_pct}]
    decision: null                  # approved | denied | needs_info
    decision_notes: ""

  # Infra Team — auto-computed fields + infra fills base CI and non-standard provisioning time
  infra:
    peak_environments: null         # AUTO-COMPUTED
    cost_per_run_est: ""            # AUTO-COMPUTED (indicative)
    provisioning_time_est: ""       # AUTO-COMPUTED for standard; infra fills for non-standard
    agnosticv_base_ci: ""           # INFRA fills: which base CI supports this
    decision: null                  # approved | denied | needs_info
    decision_notes: ""
    approved_by: ""                 # GitHub ID of infra approver
```

---

### Portal Behavior

When a spec reaches the infra review gate, the portal shows three approver views — one per persona. Each view links directly to the relevant spec files. Personas read the source; the portal does not synthesize or summarize on their behalf.

Each view has an **Approve / Deny / Ask a Question** button. Decisions are recorded in `approval_checklist.<persona>.decision`. All three must approve for the project to advance to Jira creation and content review.

---

### Validation Rules (Part 5)

| Condition | Rule | Level |
|---|---|---|
| `approval_checklist.content_lead.assessment_strategy` empty | Required before intake completes | FAIL |
| `approval_checklist.content_lead.prerequisites_verifiable` null | Must be answered | FAIL |
| `approval_checklist.content_lead.differentiation` empty | Required before intake completes | FAIL |

---

### Components Added (Part 5)

| Component | Changes | Repo |
|---|---|---|
| `intake-questions.md` | Add Q22–Q24 | Skills repo |
| `publishing-house/spec.yaml` template | Add `approval_checklist` section | Template repo |
| `design-template.md` | Add `## Prerequisites` section guidance | Skills repo |
| Central intake endpoint | Auto-compute RCARS overlap, peak environments, cost, provisioning time before Jira creation | Central repo |
| Portal | Render three approver views linking to spec files; capture decisions | Central frontend |
| `ph-check.py` | Add Part 5 required field validation (Q22–Q24) | Template repo |

---

### Out of Scope (Part 5)

- Synthesized summary cards (personas read the spec directly)
- Full RCARS integration build (RCARS query mocked until RCARS API is stable)
- Cost modeling engine (cost-per-run is indicative only)
- Parallel vs sequential persona approval order (all three can review simultaneously)
