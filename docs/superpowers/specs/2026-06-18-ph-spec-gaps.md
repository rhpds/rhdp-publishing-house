# PH Spec Review — Gaps & Recommendations
**Date:** 2026-06-18  
**Reviewer:** Prakhar Srivastava  
**Scope:** Hosted Workspace spec (2026-05-15) + Marketplace (v2.14.0)  
**Status:** Draft — for Nate's review

---

## Action Required Before Implementation Starts

Two decisions that block writing any workspace code:

**1. Portal MCP auth architecture (resolves Gaps 1 and 2)**

The current auth mechanism (`auth.py`) reads API keys from a volume-mounted
file at pod startup only. Adding a key per workspace requires a pod restart.
For self-service workspace provisioning, this breaks every new user silently.

Two paths — choose one before writing `workspace_manager.py`:

- **Portal-managed keys:** Requires dynamic secret reload without pod restart
  (secrets-reload sidecar or volume watch loop). This touches OpenShift
  infrastructure outside the portal. Scope is larger than it appears.
- **User-owned keys (recommended):** User provides their LiteMaaS virtual key
  once via a portal form. Portal stores it encrypted per user, injects into
  every workspace at creation. Gap 1 dissolves — no runtime key provisioning,
  no pod restarts, no lifecycle loop to break.

**2. Marketplace version gate (Gap 5)**

The orchestrator needs a version check before any headless mode integration
is built. Write it before writing workspace code. It is independent of
everything else — see Gap 5 below.

---

## Part 1: Hosted Workspace Spec Gaps

---

### Gap 1: Portal MCP auth not addressed in workspace pods [CRITICAL]

**What's missing:** The spec injects `MAAS_API_KEY` and `MCP_ENDPOINT` into
workspace pods. It says nothing about the portal MCP API key. The portal MCP
endpoint requires Bearer auth (see `app/mcp/auth.py`). Without a valid portal
key, every `ph_` tool call from the workspace returns 401. The user has model
access but no PH portal access — the workspace is half-broken on day one.

**The deeper problem:** `auth.py` loads keys from a YAML file at startup only
(`D-01` design decision). Adding a key per new workspace requires a pod restart.
For self-service provisioning at any scale, this is not viable. The fix requires
either dynamic secret reloading (infrastructure work) or a different auth model.

**Fix:** Resolve via the auth architecture decision above. If user-owned keys
are chosen, the portal stores the user's key and injects `PH_PORTAL_API_KEY`
into the workspace devfile alongside `MAAS_API_KEY`. The startup script
configures the CC MCP server block:

```bash
cat > ~/.claude/mcp-servers.json <<EOF
{
  "mcpServers": {
    "publishing-house": {
      "type": "streamable-http",
      "url": "${MCP_ENDPOINT}",
      "headers": {"Authorization": "Bearer ${PH_PORTAL_API_KEY}"}
    }
  }
}
EOF
```

---

### Gap 2: Key recovery — "users never touch keys" = no self-service [HIGH]

**What's missing:** When the portal's LiteLLM key lifecycle loop fails (network
partition, quota exhaustion, API change), users get a workspace with a broken AI
assistant and no recovery path. The spec's guarantee — "users never touch keys"
— also means users cannot rescue themselves.

**This is the same root problem as Gap 1.** User-owned keys resolve both:
the portal never manages MAAS_API_KEY injection, users regenerate their own key
via the LiteMaaS UI if it breaks, and the `LiteLLMClient` service is no longer
needed.

**If portal-managed keys are kept instead:** Add a "Regenerate key" button on
the project workspace detail page. Portal re-provisions and updates workspace
env without workspace recreation.

---

### Gap 3: No degradation path when Dev Spaces is unavailable [MEDIUM]

**What's missing:** No behavior defined when `ocpv-infra01` is in maintenance
or the Dev Spaces operator is unhealthy. The portal button fails with an opaque error.

**Fix:** When `DevSpacesClient` returns an error, portal shows:
> "Workspace temporarily unavailable. Use local Claude Code instead. [Setup guide →]"

Add `CLUSTER_MAINTENANCE_MODE` env var to portal deployment. When true, disable
the workspace button with a banner before the user clicks.

---

### Gap 4: WorkspaceManager abstraction needs an interface contract [HIGH]

**What's missing:** The spec claims `WorkspaceManager` is an abstraction that
allows swapping backends. Without a written protocol, the first Dev Spaces-specific
API response field will leak into `WorkspaceManager` within two iterations,
making the backend swap impossible.

**Fix:** Define the protocol on day one of workspace implementation — not after:

```python
class WorkspaceBackend(Protocol):
    def create(self, project_id: str, user_id: str,
               env_vars: dict[str, str]) -> WorkspaceRecord: ...
    def start(self, workspace_id: str) -> None: ...
    def stop(self, workspace_id: str) -> None: ...
    def delete(self, workspace_id: str) -> None: ...
    def get_status(self, workspace_id: str) -> WorkspaceStatus: ...
    def get_url(self, workspace_id: str) -> str: ...
```

`DevSpacesClient` implements this protocol. `WorkspaceManager` only calls
protocol methods — never Dev Spaces API directly.

---

## Part 2: Marketplace Gaps (rhdp-skills-marketplace v2.14.0)

---

### Gap 5: No marketplace version contract in any PH spec [CRITICAL]

**What's missing:** PH skills reference `showroom:create-lab`,
`showroom:verify-content`, `agnosticv:catalog-builder`, `agnosticv:validator`
by name with no version pinning. If marketplace ships a breaking change to the
`ph_payload` schema, PH breaks silently — not with an error, but with
plausible-looking wrong output.

**Why this compounds with Gap 6 (AgnosticV):** Wrong marketplace version
produces structurally valid but semantically wrong catalog output. The 97KB
monolithic validator has no version awareness. Malformed catalog items land
in AgnosticV with no seam to catch them.

**What already exists:**
- `showroom/.claude-plugin/plugin.json` → `"version": "2.14.0"`
- `agnosticv/.claude-plugin/plugin.json` → `"version": "2.14.0"`
- Root `VERSION` file → `v2.14.0` (monorepo — all plugins version together)
- `ph_payload` headless mode ships in 2.14.0

**Fix:** Add Section 5d to `2026-04-20-skills-redesign.md`:

```markdown
#### 5d. Marketplace version gate

PH requires rhdp-skills-marketplace ≥ 2.14.0.

Reason: 2.14.0 introduced ph_payload headless mode for showroom:create-lab
and showroom:verify-content. Earlier versions have no ph_payload support.

On session start, orchestrator:
1. Reads root VERSION file from marketplace install directory
2. Compares against MARKETPLACE_MIN_VERSION = "2.14.0"
3. Compatible → log version to manifest.integrations.marketplace.version, proceed silently
4. Older → warn user with update command, ask to continue
5. Missing → warn that writer and editor agents will not work

MARKETPLACE_MIN_VERSION is hardcoded in the orchestrator skill and updated
with each PH release that requires a new marketplace capability.
```

Must be implemented before headless mode is integrated into PH writer/editor agents.

---

### Gap 6: AgnosticV skills need agent-based refactor + ph_payload [CRITICAL]

**What's missing:** Showroom became agent-based in v2.14.0. AgnosticV did not.
`catalog-builder` (41KB SKILL.md) and `validator` (97KB SKILL.md) are monolithic
sequential skills with no `ph_payload` interface. PH automation agent calls them
conversationally today — context bleeding, not an interface.

**Why this is Critical:** Silent corruption. The automation agent produces
plausible-looking output that fails downstream (wrong variable names, missing
fields, bad workload references) with no error message and no rollback.
Debugging traces back weeks after the fact. This compounds with Gap 5 —
wrong marketplace version feeds into a monolithic validator with no version
awareness.

**Why agnosticV agents are different from showroom agents:**
Showroom agents are parallel file processors — same logic, different modules.
AgnosticV agents must be domain-knowledge specialists:

```
agnosticv:catalog-builder (orchestrator)
  ├── agnosticv:ocp-infra-agent
  │     OCP pools, workload chains, CNV vs AWS sizing, autoscale, LiteMaaS
  ├── agnosticv:vm-infra-agent
  │     cloud-vms-base, RHEL images, AAP runner patterns, VM sizing
  ├── agnosticv:sandbox-api-agent
  │     cluster/tenant split, namespace CI, sandbox_api destroy policy
  ├── agnosticv:metadata-agent
  │     __meta__ rules, UUIDs, BU taxonomy, keyword limits, label conventions
  └── agnosticv:workflow-reviewer  ← already exists (Step 11.5)

agnosticv:validator (orchestrator)
  ├── agnosticv:yaml-check-agent
  ├── agnosticv:workload-check-agent
  ├── agnosticv:security-check-agent
  └── agnosticv:metadata-check-agent
```

**ph_payload interface for catalog-builder (proposed):**

```yaml
ph_payload:
  mode: full_catalog
  infra_type: ocp
  agv_path: ~/work/code/agnosticv
  spec:
    display_name: "OpenShift GitOps Workshop"
    short_name: ocp-gitops-workshop
    event: summit-2027
    lab_id: lb2345
    technologies: [gitops, argocd]
    workloads:
      - agnosticd.core_workloads.ocp4_workload_openshift_gitops
      - agnosticd.showroom.ocp4_workload_showroom
    multiuser: true
    maintainer: {name: "Jane Dev", email: "jdev@redhat.com"}
```

Returns:
```json
{
  "files_written": ["common.yaml", "dev.yaml", "description.adoc"],
  "catalog_path": "summit-2027/lb2345-ocp-gitops-workshop-none",
  "warnings": ["ocp4_workload_openshift_gitops version not pinned"],
  "errors": []
}
```

**Implementation constraint:** The first AgnosticV call from the PH automation
agent goes through a `ph_payload` interface — not a conversational call. This
is a constraint on how the automation agent is built, not a separate refactor
sprint to be scheduled later.

**Action:** Add to `BACKLOG.md` Near-Term. Update marketplace minimum version
when `ph_payload` ships for agnosticv.

---

### Gap 7: Feature Request — RCARS Automation Discovery [MEDIUM]

**Origin:** Prakhar Srivastava (2026-06-17). Identified before this spec review
began — not a net-new suggestion from this session.

**Problem:** RCARS is wired into PH for content vetting only (intake Phase 2).
The automation agent (Phase 7a–7d) has no RCARS connection. Developers building
automation cannot query what workloads already exist or what patterns existing
labs use. Every new lab reinvents workloads that already exist across 500+
catalog items.

**What this enables:** Before writing any automation code, the automation agent
can ask RCARS "what already exists for DevSpaces tenant provisioning, Keycloak
multi-user setup, or Gitea user creation?" and get back real workload names,
source repos, and which labs use them. Developers reuse proven patterns instead
of writing from scratch.

**Proposed new MCP tool: `ph_rcars_workload_search`**

Add to `app/mcp/rcars_tools.py` alongside existing RCARS tools:

```python
async def ph_rcars_workload_search(
    query: str,
    workload_type: str = "all"   # ansible_role | agnosticv_config | all
) -> dict:
    """
    Search for existing workloads matching a query.
    Returns workload names, source repos, which labs use them, and AgV snippets.
    Called by the automation agent during Phase 7a before writing any new code.
    """
```

Returns:
```json
{
  "matching_workloads": [
    {
      "workload_name": "ocp4_workload_tenant_devspaces",
      "source_repo": "agnosticd/core_workloads",
      "used_by": ["lb2010-rhads-ols-modernize"],
      "agnosticv_snippet": "- agnosticd.core_workloads.ocp4_workload_tenant_devspaces",
      "notes": "Provisions per-user DevSpaces workspace in a namespace"
    }
  ]
}
```

**Proposed flow:**

```
Phase 7a: Automation Requirements
  → Automation agent calls ph_rcars_workload_search before writing anything
  → RCARS returns matching workloads with source repo and AgV snippet
  → Agent presents reuse plan: "Found X — recommend reusing Y, writing Z from scratch"
  → Developer confirms
  → automation-manifest.yaml records reuse decisions

Phase 7c: Automation Code
  → Agent uses RCARS hits as reference implementations
  → Writes only what doesn't already exist
```

**Dependency:** Requires RCARS to index workload-level data (Ansible role names,
AgV config snippets) in addition to catalog metadata. Coordinate with the RCARS
team before committing — the indexing side may not be trivial.

**Action:** Add to `BACKLOG.md` Near-Term. Flag as requiring RCARS team input
before implementation begins.

---

## Summary

| # | Gap | Priority | Team | Blocks |
|---|---|---|---|---|
| 1 | Portal MCP auth in workspace pods | **Critical** | Portal | workspace_manager.py |
| 2 | Key recovery — user-owned keys | High | Portal + UX | workspace launch |
| 3 | Dev Spaces degradation path | Medium | Portal | nothing |
| 4 | WorkspaceManager interface contract | High | Portal | backend swap |
| 5 | Marketplace version gate | **Critical** | Marketplace | headless mode |
| 6 | AgnosticV agent refactor + ph_payload | **Critical** | Marketplace | automation agent |
| 7 | RCARS automation discovery (feature request) | Medium | Marketplace + RCARS | nothing yet |
