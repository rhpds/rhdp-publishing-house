# Phase 3: Automation Agent — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Automation agent that handles lifecycle phase 7 — AgnosticV catalog creation (7a) and automation development (7b). Wraps `agnosticv:catalog-builder`, `agnosticv:validator`, and `code-review:code-review`. Grading/health checks (7c) are deferred.

**Architecture:** The Automation agent is a single spoke that manages two sub-phases sequentially: first it creates the AgnosticV catalog configuration by wrapping the catalog-builder and validator skills, then it develops the environment automation (Ansible roles/playbooks or Argo+Helm manifests) and runs its own code review cycle. The agent reads infrastructure requirements from the design spec and module outlines, determines the base infrastructure type (OCP vs RHEL/VMs vs Sandbox), and feeds that context into the wrapped skills. It runs only when `needs_automation: true` in the manifest.

**Tech Stack:** Claude Code plugin (SKILL.md markdown files), YAML (manifest), Markdown (references, docs)

---

## File Structure

### New files

```
rhdp-publishing-house/
├── skills/
│   └── automation/
│       ├── SKILL.md                             # Automation agent (wraps agnosticv + code-review skills)
│       └── references/
│           └── automation-patterns.md           # PH-specific automation guidance and infra routing
```

### Modified files

```
├── skills/
│   └── orchestrator/
│       └── SKILL.md                             # Update dispatch table — automation now available
├── README.md                                    # Remove "Phase 3" marker from automation entry
```

---

### Task 1: Automation Agent Reference Document

**Files:**
- Create: `skills/automation/references/automation-patterns.md`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p skills/automation/references
```

- [ ] **Step 2: Write automation-patterns.md**

Create `skills/automation/references/automation-patterns.md`:

```markdown
# Publishing House Automation Patterns

Guidance for the automation agent when creating AgnosticV catalogs and developing
environment automation. These supplement the agnosticv skill rules — do not duplicate them.

## When Automation Runs

The automation agent only runs when `lifecycle.phases.automation.needs_automation` is `true`
in the manifest. This is set during intake based on the user's answer about environment
automation needs.

If `needs_automation` is `false` or `null`, the orchestrator skips automation entirely
and marks the phase as `skipped`.

## Sub-Phase Ordering

Automation has three sub-phases tracked in the manifest:

| Sub-Phase | Manifest Key | Status | Description |
|-----------|-------------|--------|-------------|
| 7a: Catalog Item | `substeps.catalog_item` | pending → completed | AgnosticV catalog configuration |
| 7b: Automation Requirements | `substeps.requirements` | pending → completed | Reviewable scope document |
| 7c: Automation Code | `substeps.automation_code` | pending → completed | Ansible collection or GitOps repo |
| 7d: E2E Checks | `substeps.e2e_checks` | deferred | End-to-end validation (future) |

Sub-phases run in order: catalog first (provides infrastructure context), then environment
automation (builds on catalog decisions).

## Infrastructure Type Routing

The automation agent determines infrastructure type from two sources:

1. **Design spec** (`publishing-house/spec/design.md`) — infrastructure requirements section
2. **User confirmation** — the catalog-builder skill asks detailed infrastructure questions

| Infrastructure | AgnosticV Config | Automation Pattern |
|---------------|-----------------|-------------------|
| OCP cluster (CNV) | `config: openshift-workloads`, `cloud_provider: cnv` | OCP workloads via Ansible roles |
| OCP cluster (AWS) | `config: openshift-workloads`, `cloud_provider: ec2` | OCP workloads via Ansible roles |
| RHEL/AAP VMs | `config: cloud-vms-base` | Cloud VM provisioning + Ansible roles |
| Sandbox (Cluster) | `config: openshift-cluster` | Namespace-scoped workloads |
| Sandbox (Tenant) | `config: namespace` | Tenant-scoped workloads |

## Catalog Creation (7a) — Wrapping agnosticv:catalog-builder

### Input Mapping from PH Context

The catalog-builder skill asks its own questions interactively. Pre-fill answers from
the PH spec where possible:

| Catalog-Builder Question | PH Source |
|--------------------------|-----------|
| Catalog type (lab/demo/sandbox) | `project.type` in manifest |
| Event context | Ask user (not in PH spec) |
| Technologies | Products from design.md |
| Display name | `project.name` from manifest |
| Short name | `project.id` from manifest |
| Description | Problem statement from design.md |
| Maintainer | `project.owner` from manifest |
| Infrastructure type | Infrastructure requirements from design.md |

Let the catalog-builder skill handle infrastructure-specific questions — it has
detailed reference docs for OCP, VMs, and Sandbox configurations.

### Post-Catalog Validation

After catalog-builder generates files, immediately invoke `agnosticv:validator`
at scope level 2 (Standard) to catch issues before moving to environment automation.

If validation fails:
- Present errors to user
- Offer to fix and re-validate
- Do not proceed to 7b until catalog validates cleanly

### Catalog Output Tracking

Record the AgnosticV catalog path in the manifest:

```yaml
automation:
  substeps:
    catalog_item: completed
  catalog_path: "summit-2026/lb1234-short-name-cnv"  # AgV relative path
  agv_repo: "/path/to/agnosticv"                      # Local AgV repo path
```

## Automation Requirements (7b) and Automation Code (7c)

### Scope

This sub-phase creates the automation that configures the lab/demo environment.
The type of automation depends on the infrastructure:

| Infrastructure | Automation Type | Output Location |
|---------------|----------------|-----------------|
| OCP (any) | Ansible roles as OCP workloads | `automation/roles/` |
| RHEL/AAP VMs | Ansible roles for VM config | `automation/roles/` |
| Sandbox | Minimal — namespace setup only | `automation/roles/` |

### What Gets Automated

Read the design spec and module outlines to determine what needs to be set up:

- **Operators to install** — from infrastructure requirements
- **Applications to deploy** — from module detailed steps
- **User accounts and RBAC** — from multi-user configuration
- **Sample data and repos** — from module prerequisites
- **Network configuration** — from infrastructure notes

### Automation Code Standards

- Use Ansible roles following `agnosticd` patterns
- Role naming: `ocp4_workload_<short-name>` for OCP workloads
- Include `tasks/workload.yml` (install), `tasks/remove_workload.yml` (cleanup)
- Use `become: false` unless root access is explicitly required
- Parameterize everything — no hardcoded values
- Sensitive values use `lookup('password', ...)` pattern, never static strings
- Container images must use pinned tags, never `:latest`

### Helm/Argo Patterns (GitOps)

When the automation uses GitOps (Argo CD + Helm):

- Helm charts go in `automation/helm/`
- ArgoCD Application manifests go in `automation/argocd/`
- Values files parameterized for multi-environment support
- Use Helm, not Kustomize (per RHDP patterns)

### Code Review Cycle

After writing automation code, the automation agent runs its own review cycle:

1. **Self-review** — check against automation standards above
2. **Invoke `code-review:code-review`** — automated PR-based review
3. **Fix issues** — address review findings
4. **Re-validate catalog** — run `agnosticv:validator` again to ensure workload
   references in common.yaml match the roles that were created

This review cycle is separate from the content security review (Phase 8).

## Human Modifications

Automation files may be modified by a human at any time — the same principle from
PH-COMMON-RULES applies here. A human may:

- Edit common.yaml to add workloads or change configuration
- Modify Ansible roles based on hands-on testing
- Restructure Helm charts based on deployment experience

Always read automation files fresh. Respect human edits. Flag divergence from the
spec as informational, not errors.

## What the Automation Agent Does NOT Do

- Does not write Showroom content — that is the writer agent's job
- Does not review content quality — that is the editor agent's job
- Does not implement ZT grading or health checks — that is deferred (7c)
- Does not manage the AgnosticV repository — it writes files, the user manages git
- Does not deploy or test the catalog — deployment is outside Publishing House scope
- Does not advance the lifecycle phase — only updates substep status
```

- [ ] **Step 3: Commit**

```bash
git add skills/automation/references/automation-patterns.md
git commit -m "Add automation agent reference — patterns, infra routing, code review cycle"
```

---

### Task 2: Automation Agent SKILL.md

**Files:**
- Create: `skills/automation/SKILL.md`

- [ ] **Step 1: Write automation SKILL.md**

Create `skills/automation/SKILL.md`:

```markdown
---
name: rhdp-publishing-house:automation
description: This skill should be used when the user asks to "create the catalog", "build automation", "write the AgnosticV config", "set up the lab environment", "create ansible roles", "automate the deployment", or "write the environment automation". It wraps agnosticv:catalog-builder, agnosticv:validator, and code-review:code-review for RHDP Publishing House projects.
---

---
context: main
model: claude-opus-4-6
---

# RHDP Publishing House — Automation Agent

You handle lifecycle phase 7: creating AgnosticV catalog configuration (7a) and developing
environment automation (7b). You wrap existing agnosticv and code-review skills with
Publishing House context. Grading/health checks (7c) are deferred to a future phase.

See @rhdp-publishing-house/docs/PH-COMMON-RULES.md for shared rules.
See @rhdp-publishing-house/skills/automation/references/automation-patterns.md for automation patterns.

## Before Starting

1. Read `publishing-house/manifest.yaml` to understand project state
2. Confirm `lifecycle.phases.automation.needs_automation` is `true`
   - If `false` or `null`: "Automation was marked as not needed during intake. Would you
     like to change this and proceed, or skip automation?"
3. Check `project.autonomy` for behavior mode
4. Read `publishing-house/spec/design.md` for infrastructure requirements

## Step 1: Determine Sub-Phase

Check the manifest's `lifecycle.phases.automation.substeps`:

- If `catalog` is `pending` → start with 7a (catalog creation)
- If `catalog` is `completed` and `environment` is `pending` → start with 7b (automation)
- If both are `completed` → inform user automation is done
- If user requests a specific sub-phase, route to it (but warn if out of order)

Check what the user requested:

- **"create catalog" / "AgnosticV config"** → 7a
- **"write automation" / "create roles" / "set up environment"** → 7b
- **"automate" / "start automation"** → next pending sub-phase

## Phase 7a: AgnosticV Catalog Creation

### Step 7a-1: Gather Context from PH Spec

Read `publishing-house/spec/design.md` and extract:
- **Project name** → catalog display name
- **Project ID** → catalog short name
- **Content type** (workshop/demo) → catalog type
- **Products & technologies** → technology tags
- **Infrastructure requirements** → infrastructure type routing
- **Owner** → maintainer

Also read module outlines from `publishing-house/spec/modules/` to understand:
- What operators/applications need to be pre-installed
- What user accounts or RBAC is needed
- Multi-user requirements

### Step 7a-2: Invoke agnosticv:catalog-builder

Inform the user:
> "Using `agnosticv:catalog-builder` to create the AgnosticV catalog for this project."

Invoke `agnosticv:catalog-builder` in Mode 1 (Full Catalog Creation).

The catalog-builder skill will ask its own questions interactively. Pre-fill answers
from the PH context where possible:

- **Catalog type:** Map from `project.type` — workshop → `lab_multi` or `lab_single`,
  demo → `demo`. Ask user to confirm.
- **Event context:** Ask the user — this is not in the PH spec.
- **Technologies:** From design.md products & technologies list.
- **Infrastructure type:** Infer from design.md infrastructure requirements.
  Ask user to confirm before proceeding.
- **Display name:** `project.name` from manifest.
- **Short name:** `project.id` from manifest.
- **Maintainer:** `project.owner` from manifest. Ask for email.

For questions the catalog-builder asks that aren't covered by the PH spec, let
the user answer directly. Do not guess infrastructure-specific configuration.

### Step 7a-3: Validate the Catalog

After the catalog-builder generates files, immediately invoke validation:

Inform the user:
> "Running `agnosticv:validator` to check the catalog configuration."

Invoke `agnosticv:validator` at scope level 2 (Standard).

**If validation passes:**
- Update manifest: `substeps.catalog_item: completed`
- Record the catalog path and AgV repo path in the manifest
- Proceed to autonomy-appropriate next step

**If validation fails:**

- **Supervised:** Present errors. Ask: "Would you like to fix these issues now?"
  Walk through fixes one at a time. Re-validate after fixes.
- **Semi:** Attempt to fix errors automatically. Present warnings for user decision.
  Re-validate.
- **Full:** Fix all fixable issues. Re-validate. Present any remaining blockers.

Do not proceed to 7b until the catalog validates at least at Level 2 with no errors.

### Step 7a-4: Update Manifest

```yaml
automation:
  status: in_progress
  substeps:
    catalog_item: completed
    requirements: pending
    automation_code: pending
    e2e_checks: deferred
  catalog_path: "<agv-relative-path>"
  agv_repo: "<local-agv-repo-path>"
```

### Autonomy Behavior (7a)

- **Supervised:** Present the catalog-builder's output for review. Present validation
  results. Ask before committing to the AgV repo.
- **Semi:** Let catalog-builder and validator run. Present summary of what was created
  and validation status. Pause only if validation errors need user input.
- **Full:** Run catalog-builder and validator end-to-end. Present completed catalog
  summary with validation status.

## Phase 7b: Environment Automation

### Step 7b-1: Read Context

Read the completed catalog configuration to understand:
- Infrastructure type (OCP, VMs, Sandbox)
- Workloads already referenced in common.yaml
- Multi-user configuration
- Operators and applications listed

Read module outlines and design spec to understand:
- What the lab/demo environment needs pre-configured
- What applications, data, or services learners will interact with
- Any custom operators or CRDs needed

Read any existing automation files in `automation/` — a human may have started
writing automation code manually.

### Step 7b-2: Determine Automation Scope

Present the automation scope to the user:

> "Based on the spec and catalog configuration, the environment needs:
>
> **Operators to install:** [list]
> **Applications to deploy:** [list]
> **User/RBAC setup:** [details]
> **Sample data/repos:** [list]
> **Network configuration:** [if any]
>
> I'll create Ansible roles for these. Confirm or adjust?"

Wait for user confirmation before proceeding.

### Step 7b-3: Write Automation Code

Based on the infrastructure type, create automation code:

**For OCP workloads (most common):**
- Create Ansible role: `automation/roles/ocp4_workload_<project-id>/`
  - `tasks/workload.yml` — install/configure
  - `tasks/remove_workload.yml` — cleanup
  - `defaults/main.yml` — parameterized defaults
  - `meta/main.yml` — role metadata
- Follow `agnosticd` role patterns
- Reference workloads in the AgnosticV common.yaml

**For RHEL/AAP VMs:**
- Create Ansible roles for VM configuration
- Include package installation, service setup, user configuration

**For GitOps (Argo CD + Helm):**
- Create Helm charts in `automation/helm/<chart-name>/`
- Create ArgoCD Application manifests in `automation/argocd/`
- Use Helm, not Kustomize

### Autonomy Behavior (7b Code Writing)

- **Supervised:** Present each role/chart before writing. Walk through the code.
  Ask for approval before writing files.
- **Semi:** Write the code, present a summary of what was created. Pause for
  review before the code review cycle.
- **Full:** Write all automation code. Run the code review cycle automatically.
  Present final results.

### Step 7b-4: Code Review Cycle

After writing automation code, run a self-contained review cycle:

**1. Self-Review:**
- Check against automation standards in references/automation-patterns.md
- Verify no hardcoded credentials or passwords
- Verify container images use pinned tags
- Check that common.yaml workload references match created roles

**2. Code Review (if automation is in a PR-ready state):**

If the automation code is committed to a branch with an open PR:
> "Using `code-review:code-review` to review the automation code."

Invoke `code-review:code-review` against the PR.

If there is no PR yet (code is local only), skip the automated PR review and rely
on the self-review + validation below.

**3. Re-Validate Catalog:**
> "Re-running `agnosticv:validator` to verify workload references are consistent."

Run `agnosticv:validator` again to ensure:
- Workloads referenced in common.yaml exist as roles
- Collection dependencies are satisfied
- No new issues were introduced

**4. Fix Issues:**
- Address code review findings
- Fix validation errors
- Re-run validation until clean

### Step 7b-5: Update Manifest

After automation is complete and review cycle passes:

```yaml
automation:
  status: in_progress  # Orchestrator sets to completed
  substeps:
    catalog_item: completed
    requirements: completed
    automation_code: completed
    e2e_checks: deferred
  catalog_path: "<agv-relative-path>"
  agv_repo: "<local-agv-repo-path>"
  automation_files:
    - automation/roles/ocp4_workload_<project-id>/
    - automation/helm/<chart-name>/  # if GitOps
```

**Do not change `lifecycle.phases.automation.status` or `lifecycle.current_phase`.**
Phase-level transitions are managed by the orchestrator.

## Step 8: Report Back

After completing either sub-phase, inform the user:

**After 7a (catalog):**
> "AgnosticV catalog created and validated.
> Catalog path: `<agv-relative-path>`
> Validation: [PASSED / PASSED WITH WARNINGS]
>
> Next: Write environment automation (7b), or 'skip automation' if environment
> setup is handled externally."

**After 7b (environment):**
> "Environment automation complete.
> Files: [list of roles/charts created]
> Code review: [PASSED / findings addressed]
> Catalog re-validation: [PASSED]
>
> Automation phase complete. Next: security review."

## Skipping Sub-Phases

Users can skip individual sub-phases:

- **"skip catalog item"** — Set `substeps.catalog_item: skipped`. User manages AgV config
  outside Publishing House.
- **"skip requirements"** — Set `substeps.requirements: skipped`. User provides
  automation code directly without a manifest.
- **"skip automation code"** — Set `substeps.automation_code: skipped`. Automation
  handled externally.
- **"skip all automation"** — Set entire automation phase to `skipped`.

Always confirm skip decisions: "Are you sure? This means [consequence]."

## What You Do NOT Do

- Do not write Showroom content — that is the writer agent's job
- Do not review content quality — that is the editor agent's job
- Do not implement ZT grading or health checks — deferred (7c)
- Do not deploy or test the environment — deployment is outside PH scope
- Do not manage the AgnosticV git repository beyond writing files — the user owns git workflow
- Do not advance the lifecycle phase — only update substep status
- Do not guess infrastructure configuration — let the catalog-builder skill ask its
  detailed questions, or ask the user directly
```

- [ ] **Step 2: Validate SKILL.md frontmatter**

Run: `python3 -c "
content = open('skills/automation/SKILL.md').read()
blocks = content.split('---')
# Simple validation without yaml module
assert 'name: rhdp-publishing-house:automation' in blocks[1], 'Bad name'
assert 'description:' in blocks[1], 'Missing description'
assert 'context: main' in blocks[3], 'Bad context'
assert 'model: claude-opus-4-6' in blocks[3], 'Bad model'
print('Automation SKILL.md frontmatter: VALID')
"`
Expected: `Automation SKILL.md frontmatter: VALID`

- [ ] **Step 3: Commit**

```bash
git add skills/automation/SKILL.md
git commit -m "Add automation agent skill — wraps agnosticv and code-review skills"
```

---

### Task 3: Update Orchestrator for Automation Dispatch

**Files:**
- Modify: `skills/orchestrator/SKILL.md`

- [ ] **Step 1: Read current orchestrator SKILL.md**

Read `skills/orchestrator/SKILL.md` to find the automation dispatch row and guard rails.

- [ ] **Step 2: Update the dispatch table**

In the routing table under "## Step 3: Route User Intent", find the automation row:

```
| "build automation", "create catalog"           | Dispatch `rhdp-publishing-house:automation` (Phase 3, not yet implemented) |
```

Replace with:

```
| "build automation", "create catalog", "write ansible" | Dispatch `rhdp-publishing-house:automation` with sub-phase context |
```

- [ ] **Step 3: Update the guard rails section**

Update the guard rails to only mention security and review agents as unavailable:

Find:
```
- If user requests an agent that hasn't been implemented yet (automation, security, review agents), inform them: "The [agent name] agent is not yet available. It will be built in a future phase of the Publishing House plugin. For now, you can complete [phase] manually and update the manifest when done."
```

Replace with:
```
- If user requests an agent that hasn't been implemented yet (security, review agents), inform them: "The [agent name] agent is not yet available. It will be built in a future phase of the Publishing House plugin. For now, you can complete [phase] manually and update the manifest when done."
```

- [ ] **Step 4: Update the Dispatch Context section**

Find the automation agent dispatch context:
```
- **Automation agent:** Provide path to the design spec and AgnosticV config if it exists
```

Replace with:
```
- **Automation agent:** Provide the sub-phase to work on (catalog or environment). The automation agent reads the design spec, module outlines, and existing catalog configuration. It invokes agnosticv:catalog-builder for 7a and writes Ansible/Helm code for 7b, running agnosticv:validator and code-review:code-review as part of its own review cycle.
```

- [ ] **Step 5: Add automation-specific routing logic**

In the orchestrator, before dispatching the automation agent, add a check:

After the routing table, in the guard rails section, add:

```
- **Automation gate:** Before dispatching the automation agent, check `lifecycle.phases.automation.needs_automation` in the manifest. If `false` or `null`, ask: "Automation was marked as not needed. Would you like to enable it and proceed, or skip the automation phase?" If the user skips, set the automation phase status to `skipped` and move to security review.
```

- [ ] **Step 6: Validate updated frontmatter**

Run: `python3 -c "
content = open('skills/orchestrator/SKILL.md').read()
blocks = content.split('---')
assert 'name: rhdp-publishing-house' in blocks[1]
assert 'model: claude-opus-4-6' in blocks[3]
print('Orchestrator SKILL.md frontmatter: VALID (post-update)')
"`
Expected: `Orchestrator SKILL.md frontmatter: VALID (post-update)`

- [ ] **Step 7: Commit**

```bash
git add skills/orchestrator/SKILL.md
git commit -m "Update orchestrator — enable automation agent dispatch"
```

---

### Task 4: Update README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Read current README.md**

Read `README.md` to find the Phase 3 marker.

- [ ] **Step 2: Update automation entry**

Find:
```
### /rhdp-publishing-house:automation *(Phase 3)*
```

Replace with:
```
### /rhdp-publishing-house:automation

Automation agent. Two sub-phases:
- **7a: Catalog** — Wraps `agnosticv:catalog-builder` and `agnosticv:validator` to create
  and validate AgnosticV catalog configuration from the project spec.
- **7b: Environment** — Writes Ansible roles/playbooks or Argo+Helm manifests for environment
  setup, then runs its own code review cycle via `code-review:code-review`.

Only runs when `needs_automation: true` in the manifest. Uses Opus 4.6.
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "Update README — automation agent now available"
```

---

### Task 5: Smoke Test — Phase 3 Structure Validation

**Files:**
- None created — validation only

- [ ] **Step 1: Validate complete plugin structure**

Run: `find . -not -path './.git/*' -not -path './.superpowers/*' -not -name '.DS_Store' | sort`

Expected output should include all Phase 1-2 files plus:
```
./skills/automation/SKILL.md
./skills/automation/references/automation-patterns.md
```

- [ ] **Step 2: Validate all SKILL.md frontmatters**

Run: `for f in skills/*/SKILL.md; do
  name=$(head -5 "$f" | grep "^name:" | sed 's/name: //')
  model=$(head -12 "$f" | grep "^model:" | sed 's/model: //')
  echo "$f: name=$name, model=$model"
done`

Expected:
```
skills/automation/SKILL.md: name=rhdp-publishing-house:automation, model=claude-opus-4-6
skills/editor/SKILL.md: name=rhdp-publishing-house:editor, model=claude-sonnet-4-6
skills/intake/SKILL.md: name=rhdp-publishing-house:intake, model=claude-opus-4-6
skills/orchestrator/SKILL.md: name=rhdp-publishing-house, model=claude-opus-4-6
skills/writer/SKILL.md: name=rhdp-publishing-house:writer, model=claude-sonnet-4-6
```

- [ ] **Step 3: Verify orchestrator no longer blocks automation**

Run: `python3 -c "
content = open('skills/orchestrator/SKILL.md').read()
assert 'Phase 3, not yet implemented' not in content, 'Orchestrator still has Phase 3 block for automation'
assert 'security' in content.lower() or 'Phase 4' in content, 'Orchestrator should still gate Phase 4 agents'
print('Orchestrator dispatch: automation enabled, security/review still gated')
"`
Expected: `Orchestrator dispatch: automation enabled, security/review still gated`

- [ ] **Step 4: Verify git history is clean**

Run: `git status && git log --oneline -10`
Expected: Clean working tree with Phase 3 commits.

- [ ] **Step 5: Tag Phase 3 complete**

```bash
git tag v0.3.0-phase3 -m "Phase 3: Automation agent"
```

---

## Phase 3 Deliverables Summary

| Deliverable | Task | Notes |
|------------|------|-------|
| Automation reference doc (automation-patterns.md) | Task 1 | Infra routing, sub-phase ordering, code review cycle, automation standards |
| Automation agent SKILL.md | Task 2 | Wraps `agnosticv:catalog-builder`, `agnosticv:validator`, `code-review:code-review`, Opus 4.6 |
| Orchestrator update | Task 3 | Automation dispatch enabled, automation gate check, Phase 4 agents still gated |
| README update | Task 4 | Automation description added, Phase 3 marker removed |
| Structure validation | Task 5 | All files valid, frontmatter verified, dispatch table correct |

## Design Decisions

### Why Opus 4.6 for Automation

The design spec specifies Opus for the automation agent. Rationale: Ansible/Helm generation
requires complex reasoning about infrastructure dependencies, workload ordering, variable
scoping, and security patterns. The catalog-builder skill itself uses Opus. The code review
cycle adds another layer of judgment. Sonnet would struggle with the infrastructure
decision-making.

### Why No Separate Ansible/Helm Skill

The design spec lists "Automation writing (Ansible)" and "Automation writing (Argo + Helm)"
as new capabilities. Rather than creating separate skills, the automation agent handles
code generation directly — it has the full PH context (spec, catalog config, module outlines)
needed to make infrastructure decisions. Extracting a generic Ansible-writing skill would
lose this context. If automation writing patterns stabilize, they could be extracted into
a reusable skill later.

### Code Review Scope

The automation agent's code review cycle (via `code-review:code-review`) covers automation
code only — not Showroom content. Content security review is handled separately in Phase 8
by the security agent. This separation ensures automation code gets reviewed by someone who
understands infrastructure, while content gets reviewed for data sensitivity.

## What's Next (Phase 4)

- Security agent SKILL.md — content-level security audit (credentials, URLs, sensitive data)
- Review agent SKILL.md — holistic final review (spec alignment, completeness, cross-module consistency)
- End-to-end test: full lifecycle from intake through automation on a real project
