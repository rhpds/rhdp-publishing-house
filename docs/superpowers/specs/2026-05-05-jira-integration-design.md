# Jira Integration Design Spec

**Date:** 2026-05-05 (updated 2026-06-25)
**Status:** Active — core implemented, polish items in RHDPCD-77
**Phase:** 3 (Milestone 2 Roadmap)
**Depends on:** Phase 1 (RCARS MCP Gateway) — complete, Publishing House Central architecture — complete (2026-06-19 spec)
**Tracking:** [RHDPCD-77](https://redhat.atlassian.net/browse/RHDPCD-77) — remaining polish items

## Problem

Management needs visibility into content development progress across the team. Today there is no structured way for a senior director to answer "how much Summit content is done" or "which projects are behind" without asking individual developers. During Summit 2026 lab development, checkpoints existed but there was no data to assess whether projects should be cut. PH tracks everything in git manifests — useful for developers, invisible to leadership.

## Audience

Three tiers with different needs and tool preferences:

| Tier | Primary Tool | What They Need |
|------|-------------|----------------|
| Content developers | PH (80%) / Jira (20%) | Don't want to think about Jira. It should just work. |
| Direct managers | Jira (50%) / Central (50%) | Area-level status, verify Jira is current, generate reports |
| Senior director + PM | Jira (80%) / Central (20%) | Portfolio view, effort-level rollups, points, checkpoints, cut decisions |

## Design Principles

1. **Manifest is the source of truth.** Jira is a one-directional sync target. PH → Jira always. Jira → PH never (v1).
2. **Onboarded projects only.** Jira integration applies to `rhdp_published` (onboarded) projects. Self-published and express projects are not tracked in Jira — self-published work is done by others on their own schedule, and express is transient.
3. **Only the Central backend talks to Jira.** No LLM creates or modifies Jira tickets. No Jira credentials leave Central.
4. **Developers never need to touch Jira.** PH automates all Jira ticket creation and status updates.
5. **Humans own the strategic layer.** Outcomes and Initiatives are created manually in Jira. PH owns everything below that (Epics and Tasks).
6. **Points are defaults, not mandates.** PH sets fixed point values at creation. Humans adjust in Jira. PH never overwrites point values.

---

## Jira Project

**Key:** RHDPCD (RHDP Content Development)
**Template:** Template 2 — Basic Project (non-PGE)
**Site:** redhat.atlassian.net (Jira Cloud)

**Post-creation scheme change:** Template 2 defaults to OJA-ITS-001 (Bare Bones: Story, Sub-Task only). After project creation, use Delegated Project Admin to switch to **OJA-ITS-003 (Standard)** which provides Initiative, Epic, Task — the three-level hierarchy PH needs. This is a self-service change, no PME ticket required. See [How do Project Admins align with Red Hat Standards in Jira?](https://redhat.atlassian.net/wiki/spaces/HUB/pages/190190555) and [Adopting Approved Work Types](https://redhat.atlassian.net/wiki/spaces/HUB/pages/190190124).

**Scheme reference:** [OJA: Jira Configuration Taxonomy](https://redhat.atlassian.net/wiki/spaces/HUB/pages/190189089) and [Requesting a new Jira project](https://redhat.atlassian.net/servicedesk/customer/portal/67/article/421568311).

### Why a Dedicated Project

GPTEINFRA (the existing RHDP Jira project) has 70+ issue types and shared schemes across all of RHDP. Adding custom workflows, fields, or automation rules for content tracking would affect unrelated work. A dedicated project provides:

- Custom workflow matching PH lifecycle phases without affecting GPTEINFRA
- Story points enabled on the right issue types by default
- Automation rules scoped to content work only
- Clean JQL: `project = RHDPCD` = all PH content work, no filtering needed

**Cross-project reporting still works.** Jira Cloud dashboards use JQL that spans projects. Issue links connect RHDPCD Epics to GPTEINFRA Initiatives. A single dashboard can show both infra and content work side by side.

### Issue Types Required

| Type | Hierarchy Level | ID | Purpose |
|------|----------------|-----|---------|
| Outcome | 3 | 10130 | Organizational grouping ("All Events", "Non-Event Content") |
| Initiative | 2 | 10103 | One per event or program (Summit 2027, RH1, BAU) |
| Epic | 1 | 10000 | One per PH project (lab, demo, workshop) |
| Task | 0 | 10014 | One per deliverable (with story points) |

OJA-ITS-003 also includes Story, Bug, Vulnerability, Weakness, and Sub-task. PH uses only the four types above.

### Workflow

**Workflow scheme: OJA-WF-AG** (six states). Scheme change from the original four-state OJA-WF-J requested 2026-06-27; pending IT approval. All transitions are global (any state can reach any other state).

| Status | ID | Category | PH Maps To |
|--------|----|----------|------------|
| New | 10142 | To Do | `pending` — initial task creation |
| Refinement | 10143 | To Do | `pending` — task being scoped or discussed |
| Backlog | 10013 | To Do | `pending` — ready to start, not yet pulled in |
| In Progress | 3 | In Progress | `in_progress` — active work on content/automation deliverables |
| Review | 10145 | In Progress | `in_progress` — used for review-type deliverables only |
| Closed | 6 | Done | `completed` / `skipped` |

PH uses all 6 states. The Closed transition requires a resolution field (e.g., "Done").

**JiraSyncService transition logic (manifest status → Jira status):**

| Manifest status | Deliverable type | Jira status |
|----------------|-----------------|-------------|
| `pending` | any | New |
| `in_progress` | `design_doc`, `module_outline`, `module_content`, `module_automation`, `module_verified` | In Progress |
| `in_progress` | `code_review`, `security_review`, `e2e_test`, `final_review` | Review |
| `completed` or `skipped` | any | Closed |

**⚠ Transition ID update required after scheme switch:** The JiraSyncService hardcodes transition IDs from the old four-state scheme (e.g., `TRANSITION_CLOSED = 41`, `TRANSITION_IN_PROGRESS = 31`). After OJA-WF-AG is applied, these IDs will change. Before any implementation work against the new scheme, re-query:

```
GET /rest/api/3/issue/{any-RHDPCD-issue}/transitions
```

Update the transition ID constants in `app/services/jira_sync.py` accordingly. Also add `TRANSITION_REVIEW` and `TRANSITION_BACKLOG` constants for the two new states.

### Key Fields

#### Standard and Custom Fields Used by PH

| Field | Type | ID | Available On | Purpose |
|-------|------|----|-------------|---------|
| Story Points | Custom (float) | customfield_10028 | Task, Epic, Initiative | Effort estimation |
| Epic Link | Custom | customfield_10014 | Task | Parent Epic linking |
| Epic Name | Custom | customfield_10011 | Epic | Display name |
| Assignee | Standard (user picker) | — | All | The person who owns this issue |
| Flagged | Standard (flag) | — | All | Impediment flag for escalation |

**Assignee = owner.** The person assigned to an issue in Jira is the owner of that deliverable. At the Epic level, this is the RHDP team member accountable for the project. At the Task level, it's whoever is doing the work — which may be the same person or someone else. PH sets the Assignee on Epics and Tasks at creation time from `manifest.project.owner_email`. Managers reassign in Jira as needed; PH never overwrites Assignee on existing issues.

#### Dependency and Blocker Tracking

Content projects frequently depend on people outside the RHDP team — product engineers building automation, partners providing content, or other teams delivering prerequisites. When those dependencies stall, the project is blocked, and leadership needs to see it.

**The problem:** today, a blocked Epic just shows "In Progress" with no indication of why or who is holding it up. A senior director sees the project is behind but can't tell if it's a staffing issue, a technical blocker, or an external dependency waiting on someone outside the team.

**Assumption:** All contributors (internal and external) have Jira accounts on redhat.atlassian.net. This is a prerequisite for proper tracking.

**Proposed custom fields:**

| Field | Jira Field Type | Available On | Purpose |
|-------|----------------|-------------|---------|
| Waiting On | User picker (multi) | Task, Epic | People this issue is waiting on. Structured, queryable, supports multiple users. |
| Dependency Note | Text (multi-line) | Task, Epic | Context about the dependency — what they're doing, expected timeline. Visible on the issue for humans reading it. |

**Why these types:**

- **User picker (multi) for "Waiting On"** gives structured, JQL-queryable data: `"Waiting On" in (Bob)` finds all issues waiting on Bob across the entire project. Multi-user supports the common case where a Task is waiting on more than one person. Since all contributors have Jira accounts, there's no reason to fall back to free text.
- **Text (multi-line) for "Dependency Note"** provides context that a user picker can't: what the people are doing, what the expected timeline is, and any relevant details. "Bob is building the operator controller. Alice is handling CRDs. Expected completion: July 15."
- **Flagged (standard)** is the escalation signal. When a dependency stalls, the manager flags the issue as an impediment. Built-in Jira field — no custom field creation needed.

**How it looks in practice:**

```
Epic: "OCP Getting Started"
  Assignee: Tyrell (RHDP — owns the project)

  Task: "Module 3: Automation"
    Assignee: Tyrell (he's accountable)
    Waiting On: [Bob, Alice]
    Dependency Note: "Bob is building the operator controller. Alice is handling
                      CRDs. Expected mid-July."
    Status: In Progress
    Flagged: Yes (impediment — Bob missed two check-ins)

  Task: "Module 3: Verified"
    Assignee: Tyrell
    Waiting On: [Bob]   ← same dependency, different task
    Status: In Progress
```

Key point: Tyrell stays the **Assignee** because he owns and is accountable for the deliverable. "Waiting On" shows who is actually doing the work or blocking progress. When a manager looks at this, the picture is clear: Tyrell owns it, Bob and Alice are the dependency, and it's flagged because Bob is late.

**Dashboard queries this enables:**

| Query | JQL | Who Uses It |
|-------|-----|-------------|
| My projects | `issuetype = Epic AND assignee = currentUser()` | Developer |
| Everything waiting on someone | `"Waiting On" is not EMPTY AND status != Closed` | Manager |
| What is Bob holding up? | `"Waiting On" in (Bob) AND status != Closed` | Manager |
| Flagged/blocked items | `flagged = impediment AND project = RHDPCD` | Manager, PM |
| At-risk projects | `issuetype = Epic AND flagged = impediment` | Senior director |
| All of Tyrell's work | `assignee = Tyrell AND project = RHDPCD` | Manager |

**Who sets these fields — PH or Jira direct?**

| Field | Set By | Why |
|-------|--------|-----|
| Assignee | **PH** at creation, then Jira direct | PH sets from `manifest.project.owner_email` when creating Epics and Tasks. Managers reassign in Jira as needed. PH never overwrites existing Assignee values. |
| Waiting On | **Jira direct** only | This is a management judgment call — "we're waiting on Bob." The information lives in the manager's head (conversations, check-ins, team knowledge), not in the manifest or git. PH has no way to know who Bob is or that he's late. |
| Dependency Note | **Jira direct** only | Same reasoning — context about what external people are doing and when they're expected to deliver is human knowledge, not derivable from code. |
| Flagged | **Jira direct** only | Flagging an impediment is a human decision based on missed deadlines, unanswered messages, or gut feel. Not something PH can determine from manifest state. |

PH's role is limited to what it can derive from the manifest: issue creation and status transitions. Everything related to dependencies, blockers, and escalation is managed by humans directly in Jira because the underlying information doesn't exist in PH's world.

**Future consideration — stale detection (v2):** The one scenario where PH *could* assist is detecting stalled work: if a Task has been "In Progress" for N days with no corresponding manifest change, PH could auto-flag it and notify the manager to investigate. This would be an automated nudge, not a field-setting mechanism — the manager still decides what to do about it. Not v1, but worth designing the fields to support it.

**Open questions for discussion:**

1. **Custom field creation:** Can project admins create "Waiting On" (multi-user picker) and "Dependency Note" (multi-line text) in RHDPCD via Delegated Project Admin, or does this require a PME request? If custom fields must be org-wide, we may need to check whether equivalent fields already exist.
2. **Stale detection threshold:** What's the right N for "Task in progress with no manifest change"? 7 days? 14? Should it vary by deliverable type (automation tasks legitimately take longer)?
3. **Epic creation timing and outline/design doc tasks (2026-06-25):** Epic+Tasks are now created at the vetting gate (moved from approval gate) so managers can see outline tasks in progress during development. However, with PH tooling, developers complete intake → outlines → vetting quickly, so outline and design doc tasks may still appear "born closed." The real question: are outline and design doc tasks worth tracking in Jira at all, or does the meaningful work start at writing? During events, managers do need outline visibility ("where's Tyrell's outline?"), but with AI-assisted intake the spec phase is fast. This needs a rethink — possibly: (a) keep all tasks but accept some are born-closed, (b) only create content/automation/review tasks and summarize earlier work in the Epic description, or (c) make it configurable per Initiative (event-driven work creates outline tasks, BAU skips them).

---

## Ticket Hierarchy

```
Outcome (grouping)             → "All Events", "Non-Event Content"  [manually created]
  └── Initiative (event)       → "Summit 2027 Labs"                 [manually created]
        └── Epic (project)     → "OCP Getting Started"              [PH auto-created]
              ├── Design Doc          → 3 pts                       [PH auto-created]
              ├── Module 1: Outline   → 5 pts                       [PH auto-created]
              ├── Module 1: Content   → 5 pts                       [PH auto-created]
              ├── Module 1: Automation → 8 pts                      [PH auto-created]
              ├── Module 1: Verified  → 5 pts                       [PH auto-created]
              ├── Module 2: Outline   → 5 pts                       [PH auto-created]
              ├── Module 2: Content   → 5 pts                       [PH auto-created]
              ├── Module 2: Automation → 8 pts                      [PH auto-created]
              ├── Module 2: Verified  → 5 pts                       [PH auto-created]
              ├── ...
              ├── Code Review         → 3 pts                       [PH auto-created]
              ├── Security Review     → 3 pts                       [PH auto-created]
              ├── E2E Test            → 8 pts                       [PH auto-created]
              └── Final Review        → 1 pt                        [PH auto-created]
```

Each PH project = one Epic. One parent Initiative (the event or effort). One effort label.

**Project identity = repo URL + branch** (per Central architecture). A feature branch of the same repo gets its own Epic and independent phase progression. The Jira task mapping table uses `project_id` (which encodes repo URL + branch) as the foreign key, not repo URL alone.

Outcomes and Initiatives are created manually in Jira. PH does not create or sync them — they're organizational constructs managed by the team.

---

## Points Model

Points represent relative effort. Fixed defaults set by PH at task creation. Managers adjust in Jira if needed — PH never overwrites point values on existing tasks.

### Deliverable Types and Default Points

| Deliverable | Points | Manifest Source | Count |
|---|---|---|---|
| Design Doc | 3 | `lifecycle.phases.intake.status` + `lifecycle.phases.vetting.status` | 1 per project |
| Module X: Outline | 5 | `lifecycle.phases.spec_refinement.modules[id=X].status` | per module |
| Module X: Content | 5 | `lifecycle.phases.writing.modules[id=X].status` | per module |
| Module X: Automation | 8 | `lifecycle.phases.automation.modules[id=X].status` | per module |
| Module X: Verified | 5 | `lifecycle.phases.writing.modules[id=X].verified` | per module |
| Code Review | 3 | `lifecycle.phases.code_review.status` | 1 per project |
| Security Review | 3 | `lifecycle.phases.security_review.status` | 1 per project |
| E2E Test | 8 | `lifecycle.phases.e2e_testing.status` | 1 per project |
| Final Review | 1 | `lifecycle.phases.final_review.status` | 1 per project |

**Manifest evolution notes:**
- **Design Doc** combines intake + vetting. Vetting is not its own Jira task — it's part of getting the spec right. Design Doc task moves to Done when intake is complete and vetting is either complete or skipped.
- **Module Outline** requires per-module status tracking under `spec_refinement`. Manifest needs a `modules` array mirroring the writing phase structure.
- **Module Automation** requires per-module status tracking under `automation`. Manifest needs a `modules` array here too. This aligns with the direction of per-module self-contained automation.
- **Code Review and Security Review** are separate deliverables and separate manifest phases (`code_review` and `security_review`). They run in parallel — either can complete first. Both use the same point value (3 pts each).

### Example Project Sizes

| Project Type | Calculation | Total Points |
|---|---|---|
| 5-module workshop | 3 + 5×(5+5+8+5) + 3 + 3 + 8 + 1 | 133 |
| 3-module workshop | 3 + 3×(5+5+8+5) + 3 + 3 + 8 + 1 | 87 |
| 2-module quick lab | 3 + 2×(5+5+8+5) + 3 + 3 + 8 + 1 | 64 |

### Phase Profiles and Task Creation

Central's `PhaseEngine` defines which phases exist per deployment mode (onboarded, self-published, express). Tasks are created based on the project's phase profile, not a universal hardcoded list. Different deployment modes may produce different task sets.

If a phase profile is extended later (e.g., E2E test added as a separate phase), new tasks are created for existing projects on next sync.

In rare cases where a manager decides to bypass a task in Jira (e.g., marking a task Done without the work being completed), the task transitions to Done with 0 points. The project total shrinks accordingly, and percentage calculations stay accurate. This is an exception path managed in Jira, not a PH workflow.

### Module Content + Automation Relationship

Content and Automation for a module are separate tasks with independent status, but the module is not truly complete until both are done AND the Verified task passes. The Verified task represents walking through the module end-to-end — testing content against live automation, finding problems, fixing both, re-testing until it works.

If automation is structured lab-wide (not per-module), each module's Automation task stays open until the relevant automation for that module is working. They may all complete together — that's fine. Jira reflects "is the automation for this module's exercises working," not "is there a per-module Ansible role."

### Regression Handling

If a change to automation or content affects a previously verified module, the Verified task should be reopened. This is a future PH feature (backlogged): PH detects that a commit touches files affecting completed modules and reopens the Verified tasks so they can be re-tested. For v1, manual reopening by the developer or manager.

---

## Effort Categories & Initiative Management

### Four-Level Hierarchy

The hierarchy maps to standard Jira issue types and their built-in hierarchy levels:

**Outcomes** (level 3) are organizational groupings — broad categories that organize the team's work. Examples: "All Events", "Non-Event Content", "Architecture & Infrastructure". Manually created in Jira. PH does not create or sync Outcomes.

**Initiatives** (level 2) are events or efforts — each event, program, or work stream gets one Initiative under its parent Outcome. Examples: "Summit 2027 Labs", "RH1 FY27 Content", "BAU Content Development", "Arcade Development". Manually created in Jira. PH does not create Initiatives.

**Epics** (level 1) are projects — each content project (lab, workshop, demo) gets one Epic under its parent Initiative. PH auto-created when the approval gate passes.

**Tasks** (level 0) are deliverables — each piece of work within a project gets a Task with story points under its parent Epic. PH auto-created alongside the Epic.

### What an Initiative Represents

A business-level grouping of content work under one event or effort. Answers: "What are we working toward and by when?"

Examples:
- "Summit 2027 Labs"
- "RH1 FY27 Content"
- "BAU Content Development"
- "Summit Connect 2027"
- "Blog Series: AI on OpenShift"
- "Architecture Development"
- "Arcade Development"

### Initiative Lifecycle

**Created by:** Manually in Jira. PH never creates Initiatives.

**Key fields:**

| Field | Purpose | Example |
|---|---|---|
| Summary | Effort name | "Summit 2027 Labs" |
| Description | Scope, goals, deadline context | "All labs for Summit 2027. Content freeze: 2027-04-15." |
| Due date | Hard deadline (event-driven) or empty (BAU) | 2027-04-15 |
| Labels | Broad effort type for cross-cutting queries | `event`, `bau`, `blog`, `architecture`, `arcade` |
| Parent | Outcome this Initiative belongs to | "All Events" |

### Project-to-Initiative Assignment

During intake, PH queries Central for open Initiatives in RHDPCD. Developer selects one or "None — unassigned." The Epic is created as a child of the selected Initiative with a matching label.

Unassigned Epics can be moved under an Initiative later by a manager in Jira. Single parent per Epic — no multi-effort linking needed. If a project changes efforts (rare), someone drags the Epic in Jira.

### Senior Director's View

| Level | What They See | Jira Action |
|---|---|---|
| Organization | All Outcomes with total/completed points, % done | Dashboard |
| Effort | All Initiatives under one Outcome with per-effort points | Click Outcome |
| Project | All Epics under one Initiative with per-project status | Click Initiative |
| Deliverables | All Tasks under one Epic with per-deliverable status | Click Epic |
| Cross-cutting | All work by effort type (all events, all BAU) | Label-based JQL filter |

---

## Integration Architecture

### Auth

| Component | Value |
|---|---|
| Auth method | Jira API token (Basic auth: `email:token`) |
| Account | Dedicated Jira service account (not personal) |
| Secret storage | K8s Secret `ph-jira-credentials` in `publishing-house-dev` |
| Secret management | Ansible deployer |
| API version | Jira Cloud REST API v3 |

**Initial development uses a personal Jira account** (nstephan@redhat.com) with an API token stored in the Ansible vars (gitignored). This unblocks implementation while the service account is provisioned. The token and email are swappable — replace `jira_email` and `jira_api_token` in the env-specific vars file when the service account is ready.

**TODO for production:** Provision a dedicated Jira Cloud service account on redhat.atlassian.net. If not possible, evaluate alternatives (shared team token, OAuth 2.0 app). This remains a dependency for production deployment.

### Central Backend: JiraSyncService

Single integration class in `rhdp-publishing-house-central`. Pure Python, deterministic, no LLM in the loop.

```
app/services/jira_sync.py

JiraSyncService
  ├── create_project(manifest, initiative_key, phase_profile) → epic_key + task_keys
  ├── sync_project(manifest, task_mapping) → list of changes made
  ├── get_open_initiatives() → list of initiatives (cached, 15min TTL)
  └── _diff_state(manifest, jira_state) → list of transitions needed
```

**`create_project`:** Uses `PhaseEngine.get_profile(deployment_mode)` to determine which deliverable tasks to create for this project's deployment mode. Reads manifest, counts modules, creates Epic + all Tasks in one Jira API batch. Returns Jira keys stored in Central DB. Different deployment modes may produce different task sets.

**`sync_project`:** Compares manifest phase statuses against Jira task statuses via the task mapping table. Transitions tasks that are out of sync. Adds a comment to the Epic summarizing changes and linking to the custody chain gate decision that triggered the sync. Idempotent — same manifest state produces no changes.

**`get_open_initiatives`:** Queries Jira for open Initiatives in RHDPCD. Cached in Central DB, refreshed every 15 minutes or on-demand.

**`_diff_state`:** Compares manifest state against Jira state, returns list of transitions needed. Uses the task mapping table to know which Jira issue corresponds to which manifest path.

### Task Mapping Table (Central DB)

```
jira_task_mappings
  ├── id (PK)
  ├── project_id (FK → projects)
  ├── jira_epic_key (e.g., "RHDPCD-42")
  ├── deliverable_type (enum: design_doc, module_outline, module_content,
  │                     module_automation, module_verified, code_review,
  │                     security_review, e2e_test, final_review)
  ├── module_id (nullable — null for project-level tasks)
  ├── jira_issue_key (e.g., "RHDPCD-87")
  ├── manifest_path (e.g., "lifecycle.phases.writing.modules[id=module-03].status")
  ├── default_points (int)
  ├── created_at
  └── updated_at
```

Every row maps one manifest path to one Jira issue. The sync service reads this table to know what to diff and what to transition.

This table lives alongside Central's existing models: `Project` (with cached JSONB phase statuses), `GateRecord` (custody chain), and `SubmittedResult` (local skill outputs). The `project_id` FK references the `Project` model, which identifies projects by `repo_url + branch`.

### Sync Triggers

Three paths, all converging on the Central backend. Central reads project state from git via `GitRepoReader` (GitHub API, no full clone) — there is no `ph_sync_manifest` push model.

**1. Gate-driven (real-time, during active CC work)**

```
Skill completes phase work → pushes to git
  → calls ph_request_gate(repo_url, branch, target_phase)
    → Central reads manifest from git via GitRepoReader
      → Gate evaluates, records decision in custody chain
        → If state changed, JiraSyncService.sync_project() → Jira updated
```

For new projects (no Jira mapping exists), Central calls `create_project()` when the **approval gate** passes — the point where the spec is frozen and the module list is stable. Earlier gates (vetting, spec refinement) don't trigger Jira creation because modules may still change during the vetting ⇄ spec refinement loop. The Epic is created under the selected Initiative (event/effort), with Tasks as children of the Epic.

Subsequent gate passes sync task statuses to Jira. This ensures Jira reflects validated progress, not work-in-progress.

**2. Periodic sync (near-real-time, catches drift)**

Central's existing APScheduler periodic sync already reads manifests from git via `GitRepoReader` to update cached phase statuses. The Jira sync hooks into this: after updating cached statuses, compare against Jira state via the task mapping table. If out of sync, run `JiraSyncService.sync_project()`.

This catches changes made outside gate calls: manual git edits, CI pipeline updates, and any state drift between Central and Jira.

**3. Dashboard-triggered (on-demand)**

Central dashboard: "Sync to Jira" button on project detail page. Calls `JiraSyncService.sync_project()` directly. No separate MCP tool needed — this is a dashboard-only action, consistent with Central's minimal MCP tool surface.

### Error Handling

| Scenario | Behavior |
|---|---|
| Jira API down | Log error, skip sync, reconciliation job catches it on next run |
| Jira task deleted manually | Log warning, recreate task, update mapping table |
| Manifest has module with no Jira task | Create missing task, add to mapping table |
| Module removed from manifest | Transition task to Done with 0 points, comment "Module removed" |
| API rate limit | Exponential backoff, reconciliation catches remainder |
| Service account token expired | Health endpoint reports Jira unhealthy, alert via monitoring |

### Assignee from owner_email

When PH creates Epics and Tasks at the approval gate, it sets the Assignee field from `manifest.project.owner_email`. This gives instant visibility into who owns what — managers don't need to manually assign every task.

**User lookup flow:**

```
manifest.project.owner_email = "tyrell@redhat.com"
  → JiraClient.search_users("tyrell@redhat.com")
    → Jira REST API GET /rest/api/3/user/search?query=tyrell@redhat.com
      → Returns [{accountId: "70121:abc123", displayName: "Tyrell Dev", ...}]
  → Use accountId in assignee field when creating Epic and Tasks
```

**JiraClient.search_users method:**

```python
def search_users(self, query: str, max_results: int = 10) -> list[dict]:
    """Search for Jira users by email or display name."""
    params = {"query": query, "maxResults": max_results}
    resp = self._client.get(
        self._url("/user/search"),
        headers=self._headers,
        params=params,
    )
    resp.raise_for_status()
    return resp.json()
```

**Rules:**
- PH sets Assignee **at creation time only** — never overwrites existing Assignee values on subsequent syncs.
- If the email lookup fails (user not found, API error), the Epic/Task is created without an Assignee. Log a warning, don't fail.
- The Assignee is set on both the Epic and all Tasks from the same `owner_email`. A manager can reassign individual Tasks in Jira later.
- Cache the account ID lookup per sync call — no need to look up the same email multiple times within one `create_project` call.

**Implementation in JiraSyncService.create_project:**

```python
# Look up Jira account ID from owner email
owner_email = manifest.get("project", {}).get("owner_email")
assignee_account_id = None
if owner_email:
    try:
        users = self._jira.search_users(owner_email)
        if users:
            assignee_account_id = users[0].get("accountId")
            logger.info("Resolved %s to Jira accountId %s", owner_email, assignee_account_id)
        else:
            logger.warning("No Jira user found for email %s", owner_email)
    except JiraError as e:
        logger.warning("Jira user lookup failed for %s: %s", owner_email, e.message)

# Set on Epic and Task creation:
if assignee_account_id:
    epic_fields["assignee"] = {"accountId": assignee_account_id}
    task_fields["assignee"] = {"accountId": assignee_account_id}
```

### Dashboard Sync Button

The Central dashboard project detail page needs a "Sync to Jira" button that forces Central to reconcile a project's Jira state on demand. Currently the only sync triggers are gate-driven (during active CC work) and periodic (APScheduler). There's no way for a manager or developer to force a sync without either.

**REST API endpoint:**

```
POST /api/v1/projects/{project_id}/sync-jira

Response 200:
{
  "synced": true,
  "changes": [
    {"issue_key": "RHDPCD-101", "deliverable": "module_content", "from": "pending", "to": "in_progress"}
  ],
  "epic_key": "RHDPCD-100"
}

Response 200 (Jira not configured):
{"synced": false, "reason": "jira_not_configured"}

Response 200 (no mappings):
{"synced": false, "reason": "no_mappings"}

Response 404: Project not found
```

**Backend implementation** (in `app/api/projects.py`):

```python
@router.post("/{project_id}/sync-jira")
def sync_project_jira(project_id: uuid.UUID, db: Session = Depends(get_db)):
    """Manually trigger Jira sync for a project."""
    project = db.query(Project).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    jira_svc = create_jira_sync_service()
    if not jira_svc:
        return {"synced": False, "reason": "jira_not_configured"}

    if not project.cached_manifest_data:
        return {"synced": False, "reason": "no_manifest_data"}

    result = jira_svc.sync_project(db, project.id, project.cached_manifest_data)
    return result
```

**Frontend** (in project detail page, kebab dropdown):

Add "Sync to Jira" as a dropdown item after "Refresh from GitHub." Only shown for `rhdp_published` projects. Calls `api.syncProjectJira(projectId)`, shows a brief toast with the number of changes made.

```typescript
// api.ts
syncProjectJira: (id: string) =>
  request<{synced: boolean; changes?: unknown[]; reason?: string}>(`/projects/${id}/sync-jira`, { method: "POST" }),
```

The button re-reads the manifest from the cached data (not a fresh GitHub fetch) and reconciles against Jira. If the user wants a fresh manifest first, they should "Refresh from GitHub" then "Sync to Jira."

### Error Edge Cases — Manifest as Truth

The sync service must handle three divergence scenarios where Jira state has drifted from the manifest. These ensure the git manifest remains the source of truth. The reconciliation runs during `sync_project` (all three sync paths: gate-driven, periodic, dashboard button).

**Scenario 1: Jira task deleted manually**

Someone deletes a Jira task (or it gets cleaned up by automation). The mapping table still has a row for it, but the issue no longer exists in Jira.

Detection: During `_diff_and_transition`, after querying Jira for child issues of the Epic, check whether any mapped issue keys are missing from the Jira response.

Behavior:
1. Log warning: "Jira task {key} not found — recreating"
2. Create a new Jira Task with the same summary, points, and parent Epic
3. Update the mapping table row with the new Jira issue key
4. Transition the new task to match the current manifest status

```python
# In _diff_and_transition, after building jira_status_map:
for mapping in mappings:
    if mapping.jira_issue_key not in jira_status_map:
        logger.warning("Jira task %s deleted externally — recreating", mapping.jira_issue_key)
        d = DELIVERABLE_DEFAULTS.get(DeliverableType(mapping.deliverable_type))
        if not d:
            continue
        task_fields = {
            "project": {"key": self._project_key},
            "issuetype": {"id": ISSUE_TYPE_TASK},
            "summary": d["summary"],  # rebuild from deliverable type + module
            "parent": {"key": epic_key},
            FIELD_STORY_POINTS: float(mapping.default_points),
        }
        try:
            new_task = self._jira.create_issue(task_fields)
            old_key = mapping.jira_issue_key
            mapping.jira_issue_key = new_task["key"]
            db.commit()
            jira_status_map[new_task["key"]] = "pending"
            changes.append({"issue_key": new_task["key"], "action": "recreated", "old_key": old_key})
        except JiraError as e:
            logger.warning("Failed to recreate task: %s", e.message)
```

**Scenario 2: Manifest has module with no Jira task**

A module was added to the manifest after the initial Epic creation (e.g., the developer added Module 6 to a 5-module workshop). The mapping table has no rows for this module's deliverables.

Detection: During `sync_project`, compare `build_deliverable_list(manifest)` against existing mappings. Any deliverable in the manifest list that has no corresponding mapping is a new task to create.

Behavior:
1. Log info: "New module {id} found in manifest — creating Jira tasks"
2. Create Tasks for all missing deliverables under the existing Epic
3. Add new rows to the mapping table
4. Transition new tasks to match current manifest status

```python
# In sync_project, after fetching mappings:
manifest_deliverables = build_deliverable_list(manifest, "rhdp_published")
existing_keys = {(m.deliverable_type, m.module_id) for m in mappings}
missing = [d for d in manifest_deliverables
           if (d["deliverable_type"], d["module_id"]) not in existing_keys]

if missing:
    for d in missing:
        task_fields = {
            "project": {"key": self._project_key},
            "issuetype": {"id": ISSUE_TYPE_TASK},
            "summary": d["summary"],
            "parent": {"key": epic_key},
            FIELD_STORY_POINTS: float(d["points"]),
        }
        task = self._jira.create_issue(task_fields)
        new_mapping = JiraTaskMapping(
            project_id=project_id,
            jira_epic_key=epic_key,
            deliverable_type=d["deliverable_type"],
            module_id=d["module_id"],
            jira_issue_key=task["key"],
            manifest_path=d["manifest_path"],
            default_points=d["points"],
        )
        db.add(new_mapping)
    db.commit()
    # Re-fetch mappings to include new ones
    mappings = db.query(JiraTaskMapping).filter_by(project_id=project_id).all()
```

**Scenario 3: Module removed from manifest**

A module was removed from the manifest (e.g., the workshop was scoped down from 5 to 3 modules). The mapping table has rows for deliverables that no longer exist in the manifest.

Detection: During `sync_project`, compare existing mappings against `build_deliverable_list(manifest)`. Any mapping whose `(deliverable_type, module_id)` is not in the manifest deliverable list is orphaned.

Behavior:
1. Log info: "Module {id} removed from manifest — closing Jira tasks"
2. Transition each orphaned task to Done with resolution "Done"
3. Set story points to 0 on the Jira task (to avoid inflating totals)
4. Add a comment: "Module removed from manifest"
5. Update the mapping table: set `default_points = 0` (keep the row for audit trail)

```python
# After the missing-module check:
manifest_keys = {(d["deliverable_type"], d["module_id"]) for d in manifest_deliverables}
orphaned = [m for m in mappings
            if (m.deliverable_type, m.module_id) not in manifest_keys]

for mapping in orphaned:
    try:
        self._jira.transition_issue(mapping.jira_issue_key, TRANSITION_CLOSED,
                                     fields={"resolution": {"name": "Done"}})
        self._jira.add_comment(mapping.jira_issue_key, "Module removed from manifest")
        # Zero out points so totals stay accurate
        self._jira.update_issue(mapping.jira_issue_key,
                                 fields={FIELD_STORY_POINTS: 0.0})
        mapping.default_points = 0
        changes.append({"issue_key": mapping.jira_issue_key, "action": "removed",
                         "module_id": mapping.module_id})
    except JiraError as e:
        logger.warning("Failed to close orphaned task %s: %s", mapping.jira_issue_key, e.message)

db.commit()
```

**JiraClient.update_issue method** (needed for zeroing story points):

```python
def update_issue(self, issue_key: str, fields: dict) -> None:
    """Update fields on an existing Jira issue."""
    self._enforce_issue_prefix(issue_key)
    try:
        resp = self._client.put(
            self._url(f"/issue/{issue_key}"),
            headers=self._headers,
            json={"fields": fields},
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        self._handle_error(e)
```

**Summary of edge case handling:**

| Scenario | Detection | Action | Mapping Table |
|---|---|---|---|
| Jira task deleted | Mapped key not in JQL results | Recreate task, transition to current status | Update key |
| New module in manifest | Deliverable has no mapping row | Create tasks under existing Epic | Add rows |
| Module removed from manifest | Mapping has no corresponding deliverable | Close with 0 pts, add comment | Set points=0, keep row |

### Jira Data in MCP Responses

No separate Jira MCP tools. Jira metadata is folded into the existing `ph_get_status` response, consistent with Central's minimal MCP tool surface (7 high-level tools):

```json
{
  "...existing ph_get_status fields...",
  "jira": {
    "epic_key": "RHDPCD-42",
    "epic_url": "https://redhat.atlassian.net/browse/RHDPCD-42",
    "initiative_key": "RHDPCD-10",
    "points_completed": 45,
    "points_total": 130,
    "synced_at": "2026-07-15T14:30:00Z"
  }
}
```

The `jira` block is `null` for projects not yet linked to Jira (e.g., express mode projects). Skills present this data conversationally — one fewer MCP tool call per status check.

### Custody Chain Integration

When a gate passes and triggers a Jira sync, `JiraSyncService` adds a comment to the project's Jira Epic summarizing the gate decision:

- Phase name, result (approved/rejected/overridden), who requested, who approved
- Override decisions are flagged: "Proceeded despite high overlap — override recorded in custody chain"
- Comments are human-readable, not machine-cross-references — managers get a partial audit trail in Jira without needing to check the Central dashboard for every decision
- Gate IDs from the custody chain are not exposed in Jira

This ensures that the Epic comment history tells the story of how the project progressed, including any exceptions.

### Atlassian MCP Server Relationship

The Atlassian MCP server configured in Claude Code is for interactive human use (querying Jira, browsing issues). Central's `JiraSyncService` calls the Jira REST API directly via `httpx`. These are independent integration paths that coexist without conflict.

---

## Manifest Changes

### New fields in `integrations`:

```yaml
integrations:
  jira:
    epic_key: "RHDPCD-42"
    initiative_key: "RHDPCD-10"
    effort_label: "summit-2027"
    synced_at: "2026-05-05T14:30:00Z"
```

### Developer option: disabling Jira sync

Not included in the manifest template. Developers who need to test the PH pipeline repeatedly without creating Jira issues can add this to their project manifest:

```yaml
integrations:
  jira:
    enabled: false
```

When `enabled` is `false`, Central skips all Jira operations (creation, sync, comments) for that project. Defaults to `true` when omitted. This is a per-project setting — it doesn't affect other projects or the Central configuration.

### Per-module outline tracking (new structure under spec_refinement):

```yaml
spec_refinement:
  status: completed
  completed_at: "2026-04-10"
  modules:                          # NEW — per-module outline status
    - id: "module-01"
      title: "Your First Application"
      status: completed             # pending / in_progress / completed
    - id: "module-02"
      title: "Expanding Your Deployment"
      status: completed
```

### Per-module automation tracking (new structure under automation):

```yaml
automation:
  status: in_progress
  needs_automation: true
  substeps:                          # existing — kept for backward compat
    requirements: completed
    catalog_item: completed
    automation_code: in_progress
    testing: pending
  modules:                           # NEW — per-module automation status
    - id: "module-01"
      status: completed
    - id: "module-02"
      status: in_progress
```

### New per-module verification fields (under writing):

```yaml
writing:
  modules:
    - id: "module-01"
      title: "Your First Application"
      status: drafted
      content_path: "..."
      verified: false                # NEW — has this module passed testing?
      verified_at: null              # NEW — when was it verified?
```

### New phase:

```yaml
e2e_test:
  status: pending                    # pending / in_progress / completed / failed
  completed_at: null
  results: null                      # summary of test results
```

### Template update

Manifest template (`template/publishing-house/manifest.yaml`) updated with all new fields. Existing pre-Jira projects work without changes — sync service treats missing fields as "not yet started" and creates Jira tasks in To Do status.

### Backward compatibility

The sync service handles manifests with and without the new fields:
- Missing `integrations.jira` → project has no Jira mapping yet, eligible for creation
- Missing `spec_refinement.modules` → outline status derived from phase-level `spec_refinement.status` (all outlines share one status)
- Missing `automation.modules` → automation status derived from phase-level `automation.status`
- Missing `writing.modules[].verified` → treated as `false`
- Missing `e2e_test` → treated as `pending`

---

## Out of Scope (v1)

| Feature | Why Deferred |
|---|---|
| Jira → PH write-back | Conflict resolution is complex. One-directional sync first. v2 feature. |
| Manager reopens task in Jira → PH respects it | Requires bidirectional awareness. v2. |
| Automated regression detection (reopen Verified tasks) | PH feature, not Jira feature. Backlogged. |
| Jira webhooks to Central | Per-repo webhook setup doesn't scale. Gate-driven sync + periodic reconciliation sufficient. |
| Express project tracking in Jira | Express is transient — no Jira presence by design. |
| Self-published project tracking in Jira | Self-published work is done by others on their own schedule. Not useful for portfolio tracking in v1. Can add later if needed. |
| Self-service API key onboarding for CC users | Important but separate from Jira integration. Backlogged. |

---

## Prerequisites

| Prerequisite | Status | Blocker? |
|---|---|---|
| RHDPCD Jira project created | **Complete** (2026-06-18) | No |
| Issue type scheme: OJA-ITS-003 (Standard) | **Complete** (2026-06-22, verified via API) — provides Initiative, Epic, Task hierarchy | No |
| Workflow scheme: OJA-WF-AG (six states) | **Requested 2026-06-27** (pending IT approval). Replaces four-state OJA-WF-J. Adds Backlog and Review states. JiraSyncService constants need re-query after scheme is applied — see Workflow section. | No — current scheme functional; WF-AG unlocks Review + Backlog |
| Jira service account provisioned | Not started (personal account used for dev) | Yes — gating dependency for **production** deployment |
| Phase 1 (MCP Gateway) | Complete | No |
| Publishing House Central architecture | **Complete** (2026-06-19 spec, implemented) | No |
| JiraClient + JiraSyncService | **Complete** (2026-06-22, deployed to central-dev) | No |
| Gate hooks + ph_get_status jira block | **Complete** (2026-06-22) | No |
| Periodic reconciliation hook | **Complete** (2026-06-22, wired to APScheduler) | No |
| Ansible templates for Jira credentials | **Complete** (2026-06-22) | No |
| Custom fields (Waiting On, Dependency Note) | Not started — needs Delegated Admin or PME | No (v1 works without them) |

---

## Implementation Status

| Component | Status | Notes |
|---|---|---|
| JiraClient (HTTP client) | **Complete** | Basic auth, project key guardrail, create/transition/comment/search/get |
| JiraClient.search_users | **Not started** | Needed for assignee from owner_email |
| JiraClient.update_issue | **Not started** | Needed for zeroing story points on removed modules |
| JiraTaskMapping model | **Complete** | SQLAlchemy model + Alembic migration |
| JiraSyncService.create_project | **Complete** | Creates Epic + Tasks at approval gate |
| JiraSyncService.sync_project | **Partial** | Status transitions work; error edge cases (deleted/missing/removed) not implemented |
| JiraSyncService.get_open_initiatives | **Complete** | JQL query, exposed via `ph_get_open_initiatives` MCP tool |
| JiraSyncService.get_jira_summary | **Complete** | Points total + epic URL, folded into `ph_get_status` response |
| Gate hooks | **Complete** | `ph_request_gate` triggers Jira sync after approved gates |
| `ph_get_status` jira block | **Complete** | Returns `jira: {epic_key, epic_url, task_count, points_total}` or null |
| Periodic reconciliation | **Complete** | `_reconcile_jira` hooked into APScheduler `_scheduled_refresh` |
| Dashboard sync button | **Not started** | REST endpoint + frontend button (RHDPCD-77) |
| Assignee from owner_email | **Not started** | User lookup + set at Epic/Task creation (RHDPCD-77) |
| Error edge cases | **Not started** | Deleted tasks, missing modules, removed modules (RHDPCD-77) |
| Ansible templates | **Complete** | Jira credentials Secret + env vars |
| Jira service account | **Not started** | Using personal account for dev; service account needed for prod |

## Backlog Items Identified During Design

| Item | Description | Where |
|---|---|---|
| Regression detection | PH detects changes affecting completed modules, reopens Verified tasks | PH backlog |
| CC user onboarding flow | Self-service or scripted API key generation and distribution | PH backlog |
| Chatbot supports all modes | Chatbot is for onboarded, self-published, AND express — not just express | Chatbot phase (Phase 4) |
| Jira → PH write-back (v2) | Manager annotations flowing from Jira to PH, scoped to specific fields | JIRA-F-01 in REQUIREMENTS.md |
