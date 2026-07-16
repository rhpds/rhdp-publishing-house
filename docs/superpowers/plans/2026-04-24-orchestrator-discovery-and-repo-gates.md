# Orchestrator Discovery and Repo Gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the orchestrator's aggressive directory walk-up with shallow discovery and a three-option flow, and add pre-dispatch repo creation gates before writer and automation dispatch.

**Architecture:** Single-file edit to the orchestrator skill prompt (`SKILL.md`). Two sections change: project discovery (Step 1) gets rewritten, and a new "Pre-Dispatch Gates" section is inserted between Step 3 and Dispatch Context.

**Tech Stack:** Markdown (skill prompt file)

---

### Task 1: Replace Project Discovery (Step 1)

**Files:**
- Modify: `skills-plugin/skills/orchestrator/SKILL.md:48-72`

- [ ] **Step 1: Replace the Step 1 section**

Replace the entire "Step 1: Project Discovery (Silent)" section (lines 48–72) with the following. The old section starts at `## Step 1: Project Discovery (Silent)` and ends just before `## Step 2: Read State and Present Status`.

Old text to remove (lines 48–72):

```markdown
## Step 1: Project Discovery (Silent)

Find the project manifest using this search order — stop as soon as you find a match:

1. **Walk up from CWD** — check each parent directory for `publishing-house/manifest.yaml` until you reach the filesystem root. This handles the common case: user is inside a project subdirectory (e.g. `content/modules/`) or has the project open in an IDE.

2. **Scan one level of subdirectories** — if walking up found nothing, check immediate subdirectories of CWD for `publishing-house/manifest.yaml`. This handles the case where the user is in a workspace root containing multiple projects.

3. **Multiple found** — if step 2 finds more than one manifest, list them by project name and ask:
   > "I found multiple Publishing House projects. Which one do you want to work on?"
   > 1. OCP Getting Started (ex-ocp4-getting-started/)
   > 2. DataSphere Workshop (ex-datasphere/)

4. **None found** — ask the user:
   > "I couldn't find a Publishing House project. Do you have one at a specific path, or are you starting something new?"
   - **Existing project:** User provides path → read manifest there → proceed to Step 2.
   - **New project:** Ask ONE question first:
     > "What are you building? (e.g. 'OpenShift getting started workshop' or 'DataSphere demo')"
     Use the answer to suggest a short repo name (e.g. `ocp-getting-started`, `datasphere-demo`), confirm with the user, then show setup commands:
     ```
     gh repo create <org>/<suggested-name> --template rhpds/rhdp-publishing-house-template --private --clone
     cd <suggested-name>
     ```
     Say: "Run those, then come back and run `/rhdp-publishing-house` to start intake."

Once a manifest is located, **set the project root** (the directory containing `publishing-house/`) as the working context for all subsequent file reads and writes in this session.
```

New text to insert:

```markdown
## Step 1: Project Discovery

Find the project manifest. Check these two locations only — do NOT walk up parent directories or search the filesystem:

1. **Current working directory** — check for `publishing-house/manifest.yaml` in CWD.
2. **Immediate subdirectories** — check one level of subdirectories of CWD for `publishing-house/manifest.yaml`.

**Multiple found:** If step 2 finds more than one manifest, list them by project name and ask:
> "I found multiple Publishing House projects. Which one do you want to work on?"
> 1. OCP Getting Started (ex-ocp4-getting-started/)
> 2. DataSphere Workshop (ex-datasphere/)

**Found:** Set the project root (the directory containing `publishing-house/`) as the working context for all subsequent file reads and writes in this session. Proceed to Step 2.

**Not found:** Present three options:

> I don't see a Publishing House project here. Which of these fits?
>
> 1. **I have a PH project cloned locally** — tell me the path
> 2. **I have a PH project in a remote repo** — give me the git URL and I'll clone it
> 3. **I'm starting a new project** — I'll walk you through setup

**Option 1 — Existing local project:**

User provides a path. Validate that `publishing-house/manifest.yaml` exists at that path. If valid, set it as the project root and proceed to Step 2. If not, tell the user what's missing.

**Option 2 — Existing remote project:**

User provides a git URL (any git host — GitHub, GitLab, Gitea, etc.). Suggest cloning to the current directory, showing the actual absolute path:

> "I'll clone it to `<actual-absolute-cwd-path>/<repo-name>` — does that work?"

Wait for the user to confirm or provide a different location. Clone the repo with `git clone <url>`. Validate that `publishing-house/manifest.yaml` exists in the cloned directory. If valid, set it as the project root and proceed to Step 2. If not, tell the user what's missing.

**Option 3 — New project:**

Provide clear instructions to create a project repo from the template. Manual steps first, `gh` CLI shortcut second:

> **Create your project repo:**
>
> Go to https://github.com/rhpds/rhdp-publishing-house-template and click **Use this template → Create a new repository**. Choose your org, name the repo whatever makes sense to you, and set it to **Private** (recommended — you can change this later). Then clone it:
>
> ```
> git clone git@<your-host>:<org>/<repo-name>.git
> cd <repo-name>
> ```
>
> **Or if you use the `gh` CLI:**
> ```
> gh repo create <org>/<repo-name> --template rhpds/rhdp-publishing-house-template --private --clone
> cd <repo-name>
> ```
>
> Once you've cloned the repo, run the Publishing House skill again from inside it.

Rules for Option 3:
- Private is the default recommendation, but the user decides.
- Name the project repo whatever makes sense — the project ID is defined during intake once you know what you're building. Showroom and automation repos created later will use the project ID for consistent naming (e.g., `<project-id>-showroom`, `<project-id>-automation`).
- Only the project repo is created here — Showroom and automation repos come later.
- Do NOT run these commands — provide them as instructions for the user.
- After the user creates and clones, they re-run the skill. The manifest will be found, and since it's empty, the orchestrator routes to intake.
```

- [ ] **Step 2: Verify the edit**

Read `skills-plugin/skills/orchestrator/SKILL.md` and confirm:
- The old walk-up logic is fully removed (no mention of "walk up from CWD", "filesystem root", or "parent directory")
- The new Step 1 starts with "Find the project manifest. Check these two locations only"
- All three options (local path, remote clone, new project) are present with their full instruction text
- Step 2: Read State and Present Status follows immediately after

- [ ] **Step 3: Commit**

```bash
git add skills-plugin/skills/orchestrator/SKILL.md
git commit -m "orchestrator: Replace walk-up discovery with shallow check and three-option flow"
```

---

### Task 2: Add Pre-Dispatch Repo Gates

**Files:**
- Modify: `skills-plugin/skills/orchestrator/SKILL.md` (insert new section between Step 3 and Dispatch Context)

- [ ] **Step 1: Insert the Pre-Dispatch Gates section**

Insert a new section after the end of Step 3 (Route User Intent) and before "## Dispatch Context". The new section goes right before the line `## Dispatch Context` (which will be around line 198 after Task 1's edit, but find it by heading text, not line number).

New text to insert:

```markdown
## Pre-Dispatch Gates

Before dispatching to an agent, check whether prerequisites are met. If not, walk the user through setup before dispatching.

### Before dispatching to Writer

Check `integrations.showroom_repo` in the manifest. If it is not null, the Showroom repo is already linked — proceed to dispatch.

If null, the user needs to create a Showroom content repo first. Present instructions with manual steps first, `gh` CLI shortcut second. Use the project ID from `project.id` in the manifest for the suggested repo name:

> **Your project needs a Showroom content repo before we can start writing.**
>
> Go to https://github.com/rhpds/showroom_template_nookbag and click **Use this template → Create a new repository**. Name it something like `<project-id>-showroom`, set it to **Public**, and create it.
>
> **Or with `gh`:**
> ```
> gh repo create <org>/<project-id>-showroom --template rhpds/showroom_template_nookbag --public
> ```
>
> Once it's created, give me the SSH URL (e.g., `git@github.com:<org>/<repo-name>.git`).

Once the user provides the SSH URL:

1. Run `git submodule add <url> content` in the project root.
2. Update `integrations.showroom_repo` in the manifest with the SSH URL.
3. Commit and push:
   ```bash
   git add .gitmodules content publishing-house/manifest.yaml
   git commit -m "Add Showroom content repo as submodule"
   git push
   ```
4. Tell the user: "Done — your Showroom content is now linked at `content/`. Everything you write there gets pushed to your Showroom repo."
5. Proceed to dispatch the writer agent.

### Before dispatching to Automation (substep 7c)

Check `integrations.automation_repo` in the manifest. If it is not null, the automation repo is already linked — proceed to dispatch.

If null, the instructions depend on the automation approach in the manifest. Check `lifecycle.phases.automation.substeps` or the automation manifest at `publishing-house/spec/automation-manifest.yaml` for the `approach` field.

**GitOps approach:**

> **Your project needs an automation repo before we can start writing code.**
>
> Go to https://github.com/rhpds/ci-template-gitops and click **Use this template → Create a new repository**. Name it something like `<project-id>-automation`, set it to **Public**, and create it.
>
> **Or with `gh`:**
> ```
> gh repo create <org>/<project-id>-automation --template rhpds/ci-template-gitops --public
> ```
>
> Once it's created, give me the SSH URL.

**Ansible approach:**

> **Your project needs an automation repo before we can start writing code.**
>
> Create a new empty repository named something like `<project-id>-automation`, set it to **Public**.
>
> **With `gh`:**
> ```
> gh repo create <org>/<project-id>-automation --public
> ```
>
> Or create it manually on your git host. Once it's created, give me the SSH URL.

Once the user provides the SSH URL:

1. Run `git submodule add <url> automation` in the project root.
2. Update `integrations.automation_repo` in the manifest with the SSH URL.
3. Commit and push:
   ```bash
   git add .gitmodules automation publishing-house/manifest.yaml
   git commit -m "Add automation repo as submodule"
   git push
   ```
4. Tell the user: "Done — your automation code is now linked at `automation/`. Everything you write there gets pushed to your automation repo."
5. Proceed to dispatch the automation agent.
```

- [ ] **Step 2: Verify the edit**

Read `skills-plugin/skills/orchestrator/SKILL.md` and confirm:
- The "Pre-Dispatch Gates" section appears between Step 3 (Route User Intent) and Dispatch Context
- Both gates are present: "Before dispatching to Writer" and "Before dispatching to Automation (substep 7c)"
- Each gate checks the relevant `integrations.*_repo` field, provides manual + `gh` instructions, and handles the `git submodule add` + manifest update + commit/push flow
- The Dispatch Context section still follows and is unchanged

- [ ] **Step 3: Commit**

```bash
git add skills-plugin/skills/orchestrator/SKILL.md
git commit -m "orchestrator: Add pre-dispatch repo gates for Showroom and automation"
```

---

### Task 3: Final Verification

- [ ] **Step 1: Full file review**

Read the complete `skills-plugin/skills/orchestrator/SKILL.md` and verify:
- Step 1 uses shallow discovery (no walk-up)
- Three options are presented when no manifest is found
- Pre-Dispatch Gates section exists with both writer and automation gates
- No references to the old walk-up behavior remain
- The rest of the file (Step 2, Step 3, Step 4, Dispatch Context, Manifest Update Rules, Session Start/End) is unchanged

- [ ] **Step 2: Commit if any fixes were needed**

If any corrections were made during review:
```bash
git add skills-plugin/skills/orchestrator/SKILL.md
git commit -m "orchestrator: Fix discovery and repo gates after review"
```
