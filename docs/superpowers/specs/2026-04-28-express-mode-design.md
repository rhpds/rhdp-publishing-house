# Express Mode Design for Publishing House

**Date:** 2026-04-28
**Status:** Draft
**Scope:** Third deployment mode architecture — lifecycle, state management, orchestrator evolution, RCARS usage, portal integration
**Related:** [RCARS Integration Design (2026-04-27)](2026-04-27-rcars-integration-design.md)

---

## Problem

Not everything needs to be a published catalog item or a self-managed deployment. A field associate who needs a working demo environment for a customer meeting next Thursday shouldn't have to build a multi-module lab with GitOps automation, reviews, and publishing gates. Today, PH only supports two modes — onboarded and self-published — both of which assume durable content and stored automation. There's no fast path for one-off, disposable environments.

## What Express Mode Is

> *"This is the 'I need a working environment by Thursday' path. Someone has a real demo need, PH recognizes there's no exact match in the catalog, and instead of building a full publishable lab (weeks), PH finds the closest infrastructure base, orders it, does some hands-on customization, and hands it over — potentially with a lightweight Showroom guide, but always with honest 'here's what's done, here's what's left' notes. The automation is throwaway. The value is speed."*

**Key characteristics:**

- No git repo. No stored automation. No review gates.
- State lives in the portal DB, not a manifest file.
- The agent customizes the environment live — `oc` commands, operator installs, app deployments, ephemeral artifacts (lightweight apps scaffolded on the fly for the demo).
- Produces a recap document stored in the portal DB — what was done, what's left.
- OpenShift-focused initially.

---

## Three Deployment Modes

This table defines all three PH deployment modes. A standalone deployment modes doc (`docs/deployment-modes.md`) should be written from this as a user-facing reference.

| | Onboarded | Self-Published | Express |
|---|-----------|---------------|---------|
| **Purpose** | Published RHDP catalog item | Self-managed deployment | One-off demo environment |
| **State** | Git manifest | Git manifest | Portal DB |
| **Automation** | GitOps + AgnosticV CI | GitOps + generic CI | Live agent + ephemeral artifacts |
| **Content** | Full Showroom lab | Full Showroom lab | Optional lightweight Showroom |
| **Review** | Code, security, final review | Optional code review | None |
| **Durability** | Permanent catalog item | Permanent, self-managed | Throwaway |
| **Portal registration** | Optional (encouraged) | Optional (encouraged) | Automatic |
| **User identity** | GitHub ID in manifest, Red Hat email in portal | GitHub ID in manifest, Red Hat email in portal | Red Hat email in portal |

---

## Express Lifecycle

Minimal phases. No review gates, no editing passes.

### Phase 1 — Intake

- Conversational: what do you need, for when, for what audience?
- RCARS vetting query: "does something like this already exist?" Same query as all modes — checks for overlap.
- Present RCARS results to the user. If there's a close-enough match (even partial), the user might stop here and just order an existing CI. This is a valid and good outcome — reuse is better than new work.
- PH lists all three deployment modes. The user picks. PH never suggests or steers toward a mode — it presents options, the user decides.
- If the user picks express: second RCARS query — broader, stripped of the unique/new parts. "I need an OpenShift cluster with operator X and Y installed." This finds a base CI to order.
- Intake results written to portal DB via MCP.

### Phase 2 — Environment (gate)

- **Option A:** PH orders via Babylon CLI (`babylon workshop create <catalog-item>`)
- **Option B:** PH tells the user what to order and waits ("order this CI, come back when it's ready with your credentials")
- Either way, this is a gate — PH can't proceed until the environment is provisioned and accessible.
- For local CC users: user runs `oc login` to authenticate to the cluster, agent uses that context.
- For chatbot/portal users: credentials provided through the UI, `oc` is baked into the chatbot container image.
- Implementation of Babylon ordering automation is deferred — the gate works either way.

### Phase 3 — Customize (express skill)

- **This phase is designed and built separately.** The express skill is its own brainstorm and spec — it's the substantial piece of agent engineering.
- Agent assesses the environment (what's installed, what's running).
- Agent customizes based on intake requirements — installs operators, deploys apps, scaffolds ephemeral artifacts (lightweight apps, demo data, configurations).
- Conversational: agent works, asks questions when it hits decisions, reports what it's doing.
- Logs everything as it goes.
- The intake design doc is the source of truth for what needs to be customized. No other input is required.

### Phase 4 — Handoff

- Agent produces a recap document: what was installed/changed, what's left for the user.
- Recap stored in portal DB via MCP (`ph_store_express_artifact`).
- Local CC users also get a copy saved to their current directory.
- Optional: lightweight Showroom guide creation. This comes at the end — it describes what was built, not what to build. The Showroom documents the result, the intake design doc drove the work.
- Project status set to "complete" in portal.

---

## Orchestrator Evolution

The orchestrator changes from "find a manifest" to "find state wherever it lives." This affects all modes, not just express.

### New Startup Flow

1. **Check local:** Is CWD (or immediate subdirectory) a PH project repo with a manifest? → Read manifest, proceed as today (onboarded/self-published).
2. **Check portal:** No local manifest? Query portal via MCP (`ph_list_projects`) for projects associated with this user (by Red Hat email). → If found, present them ("you have these in-progress projects — want to continue one?").
3. **New project:** Nothing found? Start intake.

### Intake Flow (All Modes)

1. Conversational intake captures the need.
2. RCARS vetting query — "does something like this already exist?"
3. Present results to user. Close-enough match? User might stop here.
4. PH lists the three deployment modes. User picks one.
5. Based on mode:
   - **Onboarded / Self-published:** PH tells the user to create/clone the repo (provides the `git clone` or `gh repo create` command — PH does not create repos on the user's behalf). Intake results are written to the portal DB via MCP. When the user returns in the repo directory, the orchestrator pulls intake data from the portal and writes the manifest. Session continuity preserved without restarting Claude Code.
   - **Express:** No repo. Intake results written to portal DB via MCP. Second RCARS query for base infrastructure. Flow continues to the environment gate.

### What Changes About Existing PH

- Orchestrator gains MCP awareness (calls `ph_list_projects`, `ph_get_project`).
- Intake writes to portal DB (via MCP) in addition to or instead of local manifest.
- Repo creation moves from "before intake" to "after intake" for onboarded/self-published — intake captures the need first, repo setup comes second.
- Session continuity: when the user returns in a new repo directory, the orchestrator finds the project in the portal and populates the local manifest from stored intake data. No context lost, no restart needed.

### What Stays the Same

- For onboarded/self-published, once the repo exists, everything works as today — manifest is the source of truth, orchestrator reads it, skills update it.
- Phase gates, skill dispatch, worklog — all the same for non-express modes.

---

## RCARS Usage in Express

Express uses `ph_rcars_query` (from the RCARS integration spec) for two distinct purposes:

### Query 1 — Vetting (same as all modes)

- **Purpose:** Check if something already exists that matches the user's need.
- **Query:** Built from the full description of what the user wants — specific product features, target audience, learning objectives.
- **Outcome:** If there's a match (even partial), present it. The user may decide to just order that existing CI instead of building something new. Reuse is always the best outcome.

### Query 2 — Base-finding (express-specific)

- **Purpose:** Find the closest existing infrastructure to build on.
- **Query:** Broader, stripped of the unique/new parts. Focus on infrastructure requirements: "OpenShift cluster with operator X and Y installed," not "demo of new feature Z."
- **Outcome:** A ranked list of candidate CIs that provide the base infrastructure the user needs. The user picks one to order.
- **RCARS dependency:** RCARS currently analyzes Showroom content (what a lab teaches), not environment infrastructure (what operators, workloads, and cluster config each CI provides). The base-finding query requires **infrastructure-aware catalog metadata** — indexing AgnosticV catalog item definitions for infrastructure details. This is filed as a backlog item in the RCARS repo. Until this is built, the base-finding query will rely on content analysis as a proxy, which is imperfect but functional.

Both queries use the same `ph_rcars_query` MCP tool. The skill controls what query text to send; the tool is the same pipe.

---

## MCP Tools for Express

New tools needed in the PH MCP server (additions to the RCARS integration spec):

### Express Project Management

| Tool | Purpose |
|------|---------|
| `ph_create_express_project(name, intake_data)` | Create an express project record in the portal DB |
| `ph_update_express_status(project_id, phase, status)` | Update express project phase status |
| `ph_store_express_artifact(project_id, artifact_type, content)` | Store recap, intake design, or other artifacts in portal DB |
| `ph_get_express_project(project_id)` | Retrieve express project state (for session continuity) |

### Session Continuity (benefits all modes)

| Tool | Purpose |
|------|---------|
| `ph_store_intake_results(project_id, intake_data)` | Save intake interview results to portal DB |
| `ph_get_intake_results(project_id)` | Retrieve intake results when resuming in a new repo |

These follow the same pattern as existing MCP tools. The portal backend handles storage; skills call MCP tools.

---

## Portal Changes

### Express Project Model

New DB model for express projects — lighter than the full project model:

- `id` (UUID)
- `name` (user-provided)
- `owner_email` (Red Hat email — primary key for user identity)
- `base_ci` (the catalog item ordered as the starting point)
- `phase` (intake / environment / customize / complete)
- `status` (in_progress / complete / abandoned)
- `intake_data` (JSONB — captured requirements, RCARS results)
- `created_at`, `updated_at`

### Express Artifacts

- `id` (UUID)
- `project_id` (FK to express project)
- `artifact_type` (intake_design / recap / showroom)
- `content` (text — the artifact body)
- `created_at`

### Portal UI

The portal needs views for express projects alongside full projects:

- Express projects visible on the kanban (separate column or distinct card style)
- Express project detail view showing: intake data, base CI, current phase, artifacts
- Artifact viewer (recap document, intake design)
- Express projects filter/toggle on the projects list

### User Identity

Red Hat email is the primary key for user ownership across all modes. GitHub ID is tracked in manifests for onboarded/self-published projects but is secondary. The portal identifies and associates users by email.

---

## Dependencies

### Required Before Express Can Work

| Dependency | Source | Status |
|------------|--------|--------|
| PH MCP server deployed with external route + API key auth | RCARS integration spec | Not started |
| `ph_rcars_query` MCP tool | RCARS integration spec | Not started |
| Portal DB model for express projects | This spec | Not started |
| Portal MCP tools for express state management | This spec | Not started |
| Orchestrator MCP awareness | This spec | Not started |

### Required for Full Express Experience (can be gated/deferred)

| Dependency | Source | Status |
|------------|--------|--------|
| Express skill (cluster customization agent) | Separate spec (not started) | Not started |
| Babylon ordering automation | Deferred (manual gate works) | Not started |
| RCARS infrastructure-aware metadata | RCARS backlog | Not started |
| Portal user identity model (email ↔ GitHub mapping) | Portal backlog | Not started |

### What Does NOT Change in RCARS Integration Spec

Express is an additional consumer of the same infrastructure defined in the RCARS integration spec:

- Same MCP server deployment (Route, API key auth)
- Same `ph_rcars_query` tool (different query text, same pipe)
- Same SA token auth to RCARS

No changes needed to the RCARS integration spec. Express adds MCP tools to the portal backend alongside the RCARS tools.

---

## Deliverables

| Deliverable | Repo | Description |
|-------------|------|-------------|
| Orchestrator MCP awareness | `rhdp-publishing-house-skills` | Check local manifest → portal via MCP → new intake |
| Intake mode selection update | `rhdp-publishing-house-skills` | Lists three modes after vetting, user picks, routes accordingly |
| Intake-to-portal persistence | `rhdp-publishing-house-portal` | MCP tools to store/retrieve intake results and express project state |
| Express project DB model + migrations | `rhdp-publishing-house-portal` | Lightweight project model, artifact storage |
| Portal express views | `rhdp-publishing-house-portal` | UI to show express projects and artifacts alongside full projects |
| Deployment modes doc | `rhdp-publishing-house` | Standalone doc describing all three modes for users |
| Session continuity MCP tools | `rhdp-publishing-house-portal` | Store/retrieve intake results for repo-based modes too |

## Separate Work (Not in This Spec)

| Item | Notes |
|------|-------|
| Express skill | Agent that assesses, customizes, and recaps — its own brainstorm, spec, and implementation |
| Babylon ordering integration | Manual gate works for now; automation deferred |
| RCARS infrastructure metadata | Filed in RCARS backlog — indexes AgnosticV for infrastructure details |
| Portal user identity model | Filed in portal backlog — Red Hat email as primary key, GitHub ID mapping |

---

## Verification Checklist

Before declaring the express architecture complete (not the express skill — just the framework):

- [ ] Orchestrator discovers express projects from portal via MCP
- [ ] Intake correctly routes to express flow when user selects express mode
- [ ] Intake results persist to portal DB and survive session restarts
- [ ] Express project record created in portal with correct phase tracking
- [ ] Recap artifact stored and retrievable from portal
- [ ] Portal UI shows express projects alongside full projects
- [ ] Session continuity works for onboarded/self-published: intake in one session, repo clone, resume in new session with context preserved
- [ ] Deployment modes doc published and accurate

---

## Open Questions

1. **Babylon CLI contract** — exact command syntax, response format, credential format for ordered environments. Assumed: `babylon workshop create <catalog-item>` returns API endpoint + credential. Details deferred to implementation.
2. **Express project lifecycle** — when does an express project get marked "abandoned" vs staying "in_progress" indefinitely? Cleanup policy TBD.
3. **Portal registration for onboarded/self-published** — mechanism for encouraging but not requiring registration. Could be a prompt during intake ("want to register this with the portal for tracking?") or automatic-with-opt-out. UX TBD.
4. **RCARS base-finding query quality** — until RCARS has infrastructure-aware metadata, the base-finding query relies on content analysis as a proxy. How well does this work in practice? Needs testing once the pipeline is connected.
5. **`oc` in chatbot container** — the chatbot/portal container needs `oc` CLI baked in for the express skill to customize environments on behalf of portal users. Container image update needed.
