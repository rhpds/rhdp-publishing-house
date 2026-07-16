# Jira Integration

Publishing House automatically creates and updates Jira tickets as onboarded projects progress through the lifecycle. Developers never touch Jira — tickets update as a side effect of doing the work. Jira sync only runs for onboarded (`rhdp_published`) projects.

## Hierarchy

PH maps to standard Jira issue types:

- **Outcomes** — broad organizational groupings (e.g., "All Events", "Non-Event Content"). Manually created.
- **Initiatives** — events or work streams (e.g., Summit 2027, RH1, BAU Content Dev). Each can have a due date for content freeze deadlines. Manually created.
- **Epics** — one per content project. Auto-created by PH at registration.
- **Tasks** — one per deliverable within a project. Auto-created progressively as the project advances.

```
Outcome: "All Events"
  └── Initiative: "Summit 2027 Labs"
        └── Epic: "OCP Getting Started Workshop"
              ├── Intake & Spec                    [13 pts] ✓ Done
              ├── Module 1: Content                [5 pts]  ✓ Done
              ├── Module 1: Automation             [8 pts]  ● In Progress
              ├── Module 1: Verified               [5 pts]  ○ To Do
              ├── Module 2: Content                [5 pts]  ● In Progress
              ├── Module 2: Automation             [8 pts]  ○ To Do
              ├── Module 2: Verified               [5 pts]  ○ To Do
              ├── Code Review                      [3 pts]  ○ To Do
              ├── Security Review                  [3 pts]  ○ To Do
              ├── E2E Test                         [8 pts]  ○ To Do
              └── Final Review                     [1 pt]   ○ To Do
```

---

## Progressive Task Creation

Jira tickets are created in two phases, matching the points where PH has enough information to define them.

### Phase 1 — At Registration

When a project registers with Central (`ph_register`), PH creates:

- A **Jira Epic** for the project, parented under the Initiative if one is set
- An **Intake & Spec** task (13 story points) covering spec development, vetting, and approval
- **Assignee** resolved from the manifest's `owner_email`

At this point the module list isn't finalized, so per-module tasks aren't created yet.

### Phase 2 — At Approval Gate

When the approval gate passes and the spec is locked, PH creates the full task set:

- **Epic summary** updated to the finalized project name
- **Per-module tasks** for each content module:
    - `Content` (5 pts) — the instructional AsciiDoc content
    - `Automation` (8 pts) — infrastructure and deployment code
    - `Verified` (5 pts) — confirmation that content and automation work together for this module
- **Cross-cutting review tasks:**
    - `Code Review` (3 pts)
    - `Security Review` (3 pts)
    - `E2E Test` (8 pts) — full end-to-end validation of the complete lab
    - `Final Review` (1 pt)

---

## Points

Points represent relative effort — not hours or days. They're fixed defaults based on deliverable type.

| Deliverable | Points |
|---|---|
| Intake & Spec | 13 |
| Module Content (each) | 5 |
| Module Automation (each) | 8 |
| Module Verified (each) | 5 |
| Code Review | 3 |
| Security Review | 3 |
| E2E Test | 8 |
| Final Review | 1 |

A 5-module workshop totals **118 points**. A 2-module quick lab totals **64 points**. The module count drives project size naturally.

Points are defaults — a manager can adjust them in Jira for unusually complex or simple modules. PH won't overwrite manually adjusted values.

---

## Automatic Status Sync

PH updates Jira as work progresses. Three paths keep things current:

- **Real-time** — during active development, gate transitions immediately sync to Jira
- **Background polling** — Central checks repos every 30 minutes for manifest changes made outside PH
- **Manual** — "Sync now" in the Central dashboard

### Sync Behavior

Sync is designed to be self-correcting:

- **Creates missing tasks** — new modules added to the manifest after approval get their tasks created
- **Closes orphaned tasks** — removed modules get their tasks zeroed out and closed (not deleted)
- **Transitions status in both directions** — if a task is closed in Jira but the manifest shows that phase is still open, sync will reopen it to match the manifest
- **Recreates deleted tasks** — if someone deletes a PH-created task in Jira, sync detects the gap and recreates it

The manifest is always the source of truth. Jira is brought into alignment with whatever the manifest says.

---

## Example: What a Developer Sees vs. What Jira Shows

```
Developer runs:  /rhdp-publishing-house
Orchestrator:    Registering project with Central...
                 ✓ Jira Epic created: RHDPCD-200 "OCP Getting Started Workshop"
                 ✓ Jira Task created: RHDPCD-201 "Intake & Spec" [13 pts]
                 Starting intake...

[Developer completes intake, vetting, spec refinement]

Orchestrator:    Requesting approval gate...
                 ✓ Gate passed
                 ✓ Jira tasks created:
                   - RHDPCD-202 "Module 1: Content" [5 pts]
                   - RHDPCD-203 "Module 1: Automation" [8 pts]
                   - RHDPCD-204 "Module 1: Verified" [5 pts]
                   - RHDPCD-205 "Module 2: Content" [5 pts]
                   - ... (remaining module + review tasks)
                 ✓ RHDPCD-201 "Intake & Spec" → Done

[Developer writes Module 1 content]

Orchestrator:    Module 1 content drafted.
                 ✓ RHDPCD-202 "Module 1: Content" → Done
```

In Jira, a manager sees the Epic with all tasks, point totals, and real-time status — without anyone having to update a ticket manually.

---

## What Jira Does NOT Track

- **How developers work.** PH session logs, worklog entries, and internal decisions stay in PH. Jira shows what's done, not how it got done.
- **Express mode projects.** Express environments are transient — no Jira tracking.
- **Self-published projects.** No automatic Jira sync unless the author opts in.
