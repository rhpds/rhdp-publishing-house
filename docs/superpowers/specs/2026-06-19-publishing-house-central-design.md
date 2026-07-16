# Publishing House Central — Architecture Evolution

**Date:** 2026-06-19
**Status:** Draft
**Depends on:** Phase 1 (RCARS MCP Gateway) — complete, RCARS v2 — deployed

## Problem

PH orchestration today runs as LLM instructions (SKILL.md). The LLM decides what tools to call, in what order, and what to do when something fails. This is unreliable at scale:

- **Tool improvisation:** When `ph_rcars_query` wasn't available, the LLM used `reporting-db-prod` to fabricate vetting results from raw SQL queries. The skill says "skip if unavailable" but the LLM overrode that because it saw an alternative data source.
- **Inconsistent output:** Same vetting query produces different table formats, fabricated statistics ("100+ items"), and inconsistent data fields across runs.
- **Boundary violations:** The LLM accesses every MCP tool in the session. Skills can say "don't use X" but can't enforce it. Each user's session has different tools available, creating different failure modes.
- **No custody chain:** Gate decisions (vetting, approvals) are recorded in the local manifest, which the user controls. There's no independent record of whether a gate was legitimately passed.
- **Scaling risk:** Rolling out to dozens of users means dozens of LLM sessions making different decisions about the same workflow.

## Solution

Evolve the PH portal backend into **Publishing House Central** — a validation engine, gate authority, and tracking service. The LLM retains full control of conversation and creative work. Central handles everything that must be deterministic, auditable, or consistent across users.

**Design principle: trust but verify.** The local LLM and skills have full freedom to work — conversations, spec generation, content writing, code reviews. At defined checkpoints (phase gates), the skill calls Central. Central reads the project's git repo, validates artifacts, enforces prerequisites, records the decision, and returns a structured result. The skill presents the result to the user.

---

## Architecture

### What is Publishing House Central

The renamed and expanded portal backend. Four roles:

1. **Validation engine** — Receives gate requests, reads specs and manifests from git. For artifacts validated locally (content review, automation checks), Central verifies and analyzes the submitted results rather than re-running the validation. For artifacts that have no local validation step (spec completeness, manifest structure), Central runs its own structural and quality checks. Returns structured pass/fail with reasons.
2. **Gate authority** — Owns hard gate decisions (vetting, approvals, phase advancement). Maintains a custody chain showing who did what and when.
3. **Tracking service** — Stores project state for cross-project visibility. Powers the dashboard. Syncs to Jira (when Jira integration ships).
4. **MCP gateway** — Single interface for all AI tool clients (Claude Code, Cursor, future tools).

### What Runs Where

| Local (skill + LLM) | Central (server + code) |
|---|---|
| Intake conversation | Spec validation (structural + quality) |
| Spec generation (design.md, outlines) | Manifest validation |
| Content writing (Showroom skills) | Vetting execution (RCARS) |
| Content review (Showroom skills) | Phase gate enforcement |
| Automation code generation | Phase advancement + custody chain |
| Local file I/O (manifest, content) | Project tracking + dashboard |
| User interaction + presentation | Jira sync (future) |
| Session management + worklog | Validation result storage |
| Git operations (commit, push) | Periodic project sync from git |

### Data Flow

Central primarily reads project state from git. The skill pushes to the remote repo, then calls Central with the repo URL and branch. Central fetches spec files and review outputs via the GitHub API (no full clone needed — specific files by path and ref).

**Hybrid option for small artifacts:** For small, frequently-accessed artifacts like the manifest, the MCP call may include the content directly in the payload to avoid a round-trip to git. This is an optimization, not a requirement — Central can always fall back to reading from git. The decision of which artifacts travel in-payload vs are read from git is per-tool, based on size and frequency.

This means:

- Central validates the committed state for large artifacts (specs, review outputs)
- Small artifacts (manifest) can optionally travel in the MCP payload for speed
- No large payload transfer between client and server
- Content files and automation code stay local — Central only sees structured results summaries submitted by local skills

### Interaction Pattern

```
Local skill does creative work freely
  → User pushes to git (skill offers to help, doesn't force)
    → Skill calls Central: "I'm ready for [gate], check repo_url @ branch"
      → Central fetches from git, validates, records decision
        → Central returns structured result
          → Skill presents result to user conversationally
```

---

## Project Registration and Identity

### Registration

Mandatory and automatic from skills. The first time a skill calls any Central tool, it provides `repo_url` and `branch`. Central either finds an existing project record or creates one. No separate registration step from the skill side.

**Manual registration:** Projects can also be registered manually through the Central dashboard UI. A manager or admin can add a repo URL and branch without using the skills. This supports scenarios where a project exists before anyone runs the PH orchestrator — for example, a legacy lab being brought into the PH pipeline, or a project set up by someone who isn't the day-to-day developer.

### Identity

**Project identity = repo URL + branch.** Different branches of the same repo are different projects. A major overhaul on a feature branch has its own phase progression independent of the main branch project.

### Owner

Read from the manifest (`project.owner_github`, `project.owner_name`), not from the caller. If five people work on a project, the owner is whoever the manifest says it is, regardless of who registered it first.

### Project Discovery

The orchestrator skill combines two sources to present a project list:

1. **Local scan** — Check CWD and immediate subdirectories for `publishing-house/manifest.yaml`
2. **Central query** — Call `ph_get_status` with the user's email to get registered projects

The orchestrator merges these into a clear list:
- Cloned locally AND registered in Central
- Registered in Central but not cloned locally (offer clone instructions)
- Cloned locally but not yet registered (will register on first gate call)

This is a deterministic merge of two lists, not LLM guessing.

### Private Repos

Deferred. All project repos must be public for the initial implementation. Private repo support (encrypted deploy keys or GitHub App installation) is a future addition.

---

## Phase Profiles and Gate Enforcement

### Phases Are Required

No optional phases. If a phase is in the profile, it runs. If a capability isn't ready to support a phase, the phase isn't added to the profile yet. This eliminates skip logic from the LLM entirely.

### Phase Profiles by Deployment Mode

**Onboarded (`rhdp_published`):**

```
Intake → Vetting ⇄ Spec Refinement → Approval → Writing ↔ Automation → Editing → Code & Security Review → Final Review → Ready for Publishing
```

All gates are hard. Approval requires a different person or explicit manager sign-off. Code & Security Review and Final Review are non-negotiable.

**Self-published:**

```
Intake → Vetting ⇄ Spec Refinement → Approval → Writing ↔ Automation → Editing → Code & Security Review → Final Review
```

Same phases. Softer gates — self-approval is allowed on Approval and Final Review. Code & Security Review is recommended, author can self-approve.

**Express:**

```
Intake → Vetting → Base Finding → [future: deployment + customization phases]
```

Abbreviated. Additional phases will be added when the express skill capabilities are built.

### Vetting ⇄ Spec Refinement Loop

Vetting and spec refinement are iterative. After vetting, the user may refine the spec. After refinement, vetting must re-run if the spec changed. Central enforces this by tracking the git commit hash of the spec files at the time of the last vetting pass. If the spec changed since the last vetting, the approval gate rejects with "spec changed since last vetting — run vetting again."

The loop continues until vetting passes on the current version of the spec and nothing changes before approval.

### Vetting Posture

Central's vetting assessment must be **challenging and neutral, bordering on pessimistic.** The purpose of vetting is to prevent redundant content, not to validate someone's enthusiasm.

When RCARS returns overlap findings, the vetting assessment must not soften the message. If there is significant overlap with existing catalog items, the assessment says so plainly: "This overlaps significantly with [existing items]. You should not proceed without a clear differentiator." The assessment evaluates based on objective criteria (topic overlap percentage, audience overlap, product coverage), not sentiment.

**First phase:** The backend LLM call that evaluates vetting results uses a fixed prompt that instructs the model to be critical. The prompt explicitly says: "Do not encourage the user. Do not suggest the idea is good despite overlap. Present the overlap findings factually and recommend against proceeding if overlap is high."

**Future phase:** Replace the LLM sentiment assessment with a formula-based scoring model (e.g., overlap percentage thresholds, weighted by audience similarity and product coverage). This removes LLM judgment from the vetting decision entirely.

### Writing ↔ Automation Concurrency

Writing and automation can be co-active. A developer may draft modules, start automating, realize the content needs to change, go back to writing, then continue automation. These phases are not strictly sequential between each other.

The gate enforcement happens when the developer wants to advance to editing. Central checks: is writing complete AND is automation complete? If content changed after automation was marked done, Central flags the inconsistency. The developer resolves it before advancing.

### How Gates Work

When a skill calls `ph_request_gate(repo_url, branch, target_phase)`:

1. Central fetches the manifest and relevant artifacts from the repo at that branch
2. Central checks prerequisites for the target phase (prior phases completed, required artifacts present)
3. For validation gates: Central runs the appropriate validation
   - **Vetting:** Calls RCARS with the spec content, scores results, stores findings
   - **Spec validation:** Checks structural completeness + runs quality assessment via backend LLM
   - **Pre-editing:** Checks that submitted review results have no unresolved Critical findings
4. For approval gates: Records who requested advancement and whether it's self-approval (allowed on soft gates only)
5. Central returns: `{approved: true/false, reason: "...", findings: [...], gate_id: "..."}`
6. If approved, Central records the gate decision in the custody chain

### Approval Surfaces

Gate approvals work from two surfaces:

- **Local skill** — MCP tool call from Claude Code, Cursor, or any MCP client
- **Central dashboard** — Web UI button for managers and reviewers

Both hit the same backend endpoint. Central doesn't care where the approval originates.

### Late-Stage Rework (Noted, Not Fully Designed)

When E2E testing or late-stage review reveals issues requiring changes to earlier-phase artifacts (content, automation), the affected phases need to reopen. Full re-validation from the beginning would be onerous for a three-line fix.

**Proposed concept: scoped re-validation.** When a late-stage issue requires changes, the affected phase reopens but re-validation is limited to what changed. Central tracks which files were modified, and the re-validation gate checks only the delta. This will be designed in detail when E2E testing is added as a phase.

### Future Phases (Noted)

The phase profiles will grow as capabilities are built:
- E2E testing as a separate phase (currently part of Code & Security Review)
- Code review and security review may split into separate phases
- Express mode deployment + customization phases

The `PhaseEngine` is designed to be extensible — adding a phase means adding it to the profile and defining its prerequisites.

---

## Custody Chain

Central's independent record of gate decisions. The manifest tracks local phase status; the custody chain tracks whether gates were legitimately passed.

### What's Recorded

Each `GateRecord` contains:

| Field | Purpose |
|---|---|
| `project_id` | Which project (repo URL + branch) |
| `phase` | Which gate was evaluated |
| `result` | approved / rejected / overridden |
| `reason` | Why (validation findings summary, prerequisite check result) |
| `findings` | Structured validation output (vetting matches, spec issues, etc.) |
| `requested_by` | Email of the person who called the gate |
| `approved_by` | Email of the approver (may differ from requester on hard gates) |
| `is_self_approval` | Boolean — true if requester == approver |
| `override` | Boolean — true if the gate was passed despite negative validation (e.g., proceeded despite high vetting overlap) |
| `spec_commit` | Git commit hash of the spec at time of gate evaluation |
| `created_at` | Timestamp |

### Visibility

The custody chain is visible on the Central dashboard. A manager can see:
- "This project proceeded despite high overlap with Private MaaS v3 — Nate self-approved"
- "Spec validation failed twice, passed on third attempt after adding missing learning objectives"
- "Code review approved by Jane Smith on 2026-07-15"

### Override Tracking

If a user advances past a gate despite a negative result (e.g., vetting finds high overlap but they proceed anyway), Central records it as an override. The project isn't blocked — but the override is permanently visible in the custody chain. This provides accountability without being a blocker.

---

## MCP Tool Surface

Seven high-level tools exposed to client skills. These are the only tools on the MCP surface.

### `ph_register(repo_url, branch)`

**Central does:** Fetch manifest from git, create or find project record, read owner from manifest.

**Returns:** `{project_id, owner, deployment_mode, current_phase, phase_statuses}`

### `ph_request_gate(repo_url, branch, target_phase)`

**Central does:** Fetch manifest + artifacts from git, check prerequisites, run phase-specific validation (vetting calls RCARS, spec validation checks completeness + quality), record gate decision.

**Returns:** `{approved, reason, findings, gate_id}`

### `ph_get_status(repo_url, branch)`

**Central does:** Fetch manifest for a specific project, compute phase status, check for pending gates.

**Returns:** `{project_id, current_phase, phase_statuses, next_action, pending_gates}`

### `ph_list_projects(owner_email)`

**Central does:** Return all registered projects for that user across all repos and branches.

**Returns:** List of `{project_id, repo_url, branch, name, current_phase, deployment_mode}`

### `ph_approve(project_id, phase, approver_email)`

**Central does:** Record approval in custody chain. Can be called from dashboard UI or skill.

**Returns:** `{approved, gate_id}`

### `ph_submit_results(repo_url, branch, phase, results)`

**Central does:** Store structured results from local skills (verify-content findings, automation status, etc.). These results are considered when evaluating future gates.

**Returns:** `{stored, result_id}`

### `ph_get_history(repo_url, branch)`

**Central does:** Return full custody chain — all gate decisions, validations, approvals, overrides.

**Returns:** Ordered list of gate records.

### Internal Functions (Not Exposed via MCP)

The existing low-level tools become internal Python functions:
- `ph_rcars_query` → `RCARSClient.query()` — called by `GateService` during vetting
- `ph_sync_manifest` → replaced by `GitRepoReader` pulling from git
- `ph_store_intake_results` / `ph_get_intake_results` → intake data lives in manifest in git
- `ph_rcars_catalog_search` / `ph_rcars_catalog_item` → internal to vetting logic

---

## Skill Evolution

### Orchestrator (`rhdp-publishing-house`)

Still the entry point. Still owns the conversation flow. Changes:

- Calls `ph_get_status` (with owner email) to discover registered projects, merges with local scan
- Presents status conversationally, suggests next action
- Routes to other skills based on user intent
- At phase boundaries, prompts user to push, then calls `ph_request_gate`
- Presents gate results conversationally
- **No longer contains:** phase prerequisite logic, manifest validation, vetting execution, status computation

### Intake (`rhdp-publishing-house:intake`)

Still fully conversational. Changes:

- Still gathers requirements through dialogue
- Still generates spec files locally (design.md, module outlines)
- Prompts user to push when spec is ready
- Orchestrator calls `ph_request_gate(target_phase="vetting")` — Central reads the spec from git and runs RCARS vetting
- **No longer:** calls `ph_rcars_query` directly, formats vetting results itself, decides how to handle RCARS being unavailable

### Writer (`rhdp-publishing-house:writer`)

Mostly unchanged:
- Dispatches `showroom:create-lab` or `showroom:create-demo` locally
- Writes content to local files
- When done, orchestrator calls `ph_submit_results` with a writing summary, then `ph_request_gate` to advance

### Editor (`rhdp-publishing-house:editor`)

Mostly unchanged:
- Runs `showroom:verify-content` locally
- Runs spec alignment checks locally
- Calls `ph_submit_results` with structured findings
- Orchestrator uses stored results when requesting the gate past editing

### Automation (`rhdp-publishing-house:automation`)

Mostly unchanged:
- Generates catalog configs, Ansible code locally
- Calls `ph_submit_results` with automation completion status
- Orchestrator uses results for gate enforcement

### Bring Your Own Content

Publishing House is a mandatory pipeline to RHDP publishing, but it must not mandate how content is created. At any phase that produces artifacts (writing, automation, editing), the user can bring their own work instead of using the PH skills.

**Writing example:** When the orchestrator reaches the writing phase, the user can say "I've already written the content, it's in the repo." The orchestrator skips dispatching the writer skill and proceeds to the next gate. Central doesn't care whether `showroom:create-lab` generated the content or the author wrote it by hand — it evaluates the artifacts the same way.

**The pipeline enforces quality gates, not tools.** The spec must pass validation. The content must pass review. The automation must work. How those artifacts were produced is the author's choice.

### Pattern Across All Skills

Do creative/local work freely → push to git when ready → call Central at checkpoints → present results to user. Skills stay rich in user interaction and creative dispatch. They lose the infrastructure decision-making.

---

## Central Backend Changes

### New Services

| Service | Purpose |
|---|---|
| `GitRepoReader` | Fetch files from a git repo by URL + ref via GitHub API. Reads manifests, specs, review files without cloning. |
| `GateService` | Core gate logic — check prerequisites, run validations, record decisions. Composes other services. |
| `SpecValidator` | Structural + quality validation of spec files. Structural checks are deterministic code. Quality checks use a backend LLM call via LiteLLM/MaaS with a fixed prompt for consistency. |
| `PhaseEngine` | Defines phase profiles per deployment mode. Knows prerequisite rules and gate types (hard/soft). Returns what's needed to advance. |

### Evolved Services

| Service | Change |
|---|---|
| `RCARSClient` | No change — already calls RCARS API. Now called by `GateService` during vetting instead of exposed via MCP. |
| `ManifestParser` | Extended to validate manifest structure and cross-reference against gate records. |

### New Database Models

| Model | Fields |
|---|---|
| `ProjectRegistration` | repo_url, branch, owner_email, owner_github, deployment_mode, created_at, last_synced_at |
| `GateRecord` | project_id, phase, result, reason, findings (JSONB), requested_by, approved_by, is_self_approval, override, spec_commit, created_at |
| `SubmittedResult` | project_id, phase, result_type, results (JSONB), submitted_by, submitted_at |

### Backend LLM for Quality Validation

`SpecValidator` makes LLM calls for quality assessment (are objectives measurable, is the spec thorough enough for downstream phases). Uses the LiteLLM/MaaS endpoint — same approach already implemented in RCARS. The prompt is fixed server-side so every spec gets the same evaluation regardless of which client-side model the user runs.

**Dependency:** LiteLLM/MaaS endpoint accessible from the Central namespace. Same configuration pattern as RCARS.

### Periodic Sync

Central runs a background job (APScheduler, already in place for project refresh) that periodically fetches manifests from registered project repos. If someone pushes manifest changes outside of the PH skills — manual edit, CI pipeline, another tool — Central catches up on the next sync cycle. The dashboard is never more than one sync interval behind.

### New MCP Tool Module

`app/mcp/gate_tools.py` — registers the six high-level tools.

### Retired MCP Tools

`rcars_tools.py`, `session_tools.py`, and most of `tools.py` lose their `@mcp.tool()` decorators. The code remains as service functions called internally by `GateService` and other services.

---

## Out of Scope (This Spec)

| Item | Why Deferred |
|---|---|
| Private repo support | Edge case — all initial repos are public. Future: encrypted deploy keys or GitHub App. |
| E2E testing phase | Phase will be added when the capability is built. Late-stage rework scoping depends on this. |
| Jira sync integration | Separate spec exists (2026-05-05). Central is the right home for it, but implementation is blocked on RHDPCD project creation. |
| Express mode deployment phases | Express extends beyond base-finding eventually, but those phases aren't designed yet. |
| DevSpaces / hosted workspace | Separate spec exists (2026-05-15). Central architecture makes it simpler but it's a separate implementation. |
| Dashboard UI updates | Central backend changes first. Dashboard evolves to show custody chain, gate history, and project status from new models. |
| Late-stage scoped re-validation | Noted as a concept (reopen affected phase, validate only the delta). Full design when E2E testing phase is built. |

---

## Implementation Sequence

Each step is independently deployable and testable:

1. **`GitRepoReader` + `ph_register`** — Central can read repos and register projects. Foundation for everything else.
2. **`PhaseEngine` + `ph_get_status`** — Central can compute phase status from manifest. Orchestrator simplified.
3. **`GateService` + `ph_request_gate`** — Central validates and enforces gates. Vetting runs through Central.
4. **`SpecValidator`** — Spec quality validation via backend LLM. Requires LiteLLM/MaaS dependency.
5. **`ph_submit_results` + `ph_approve` + `ph_get_history`** — Full custody chain and result tracking.
6. **Skill simplification** — Remove orchestration logic from skills, replace with Central tool calls.
7. **Retire old MCP tools** — Remove `@mcp.tool()` decorators from low-level tools.
8. **Dashboard updates** — Show custody chain, gate history, new project status model.
