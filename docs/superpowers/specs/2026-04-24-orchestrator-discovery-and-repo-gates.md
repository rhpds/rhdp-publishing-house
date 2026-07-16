# Orchestrator: Project Discovery and Phase-Gate Repo Creation

**Date:** 2026-04-24
**Scope:** Modifications to the orchestrator skill only — no changes to writer, automation, or other skills.

## Problem

The orchestrator's current project discovery aggressively walks up the directory tree looking for `publishing-house/manifest.yaml`. This wastes time searching through the user's filesystem and provides a poor experience when no project exists. Additionally, Showroom and automation repos are expected to exist from project creation, but they aren't needed until their respective phases begin.

## Design

### 1. Project Discovery

When the orchestrator starts, it checks for `publishing-house/manifest.yaml` in the current working directory only. No subdirectory scanning, no walking up.

If found, read the manifest and proceed as normal.

If NOT found, present three options:

> I don't see a Publishing House project here. Which of these fits?
>
> 1. **I have a PH project cloned locally** — tell me the path
> 2. **I have a PH project in a remote repo** — give me the git URL and I'll clone it
> 3. **I'm starting a new project** — I'll walk you through setup

#### Option 1: Existing local project

User provides a path. Orchestrator validates `publishing-house/manifest.yaml` exists at that path. If valid, proceed. If not, tell the user what's missing.

#### Option 2: Existing remote project

User provides a git URL (any git host — GitHub, GitLab, Gitea, etc.). Orchestrator suggests cloning to the current directory, showing the actual absolute path:

> "I'll clone it to `/Users/you/devel/my-project` — does that work?"

User confirms or provides a different location. Orchestrator clones, validates the manifest exists, and proceeds.

#### Option 3: New project

Give the user clear instructions to create a project repo from the template. Manual steps first, `gh` CLI shortcut second.

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

Key rules:
- Private is the default recommendation, but the user decides
- Name the project repo whatever makes sense — the project ID is defined during intake once you know what you're building. Showroom and automation repos created later will use the project ID for consistent naming (e.g., `<project-id>-showroom`, `<project-id>-automation`).
- Only the project repo is created here — Showroom and automation repos come later
- The orchestrator does NOT run these commands itself — it provides instructions
- After the user creates and clones, they re-run the skill and hit the "manifest found" path, which sees an empty manifest and routes to intake

### 2. Phase-Gate Repo Creation

The orchestrator checks for required repos before dispatching to skills. Skills never deal with repo setup.

#### Before dispatching to Writer

Check `integrations.showroom_repo` in the manifest. If null, walk the user through creating the Showroom repo:

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

Once the user provides the URL, the orchestrator:

1. Runs `git submodule add <url> content` in the project repo
2. Updates `integrations.showroom_repo` in the manifest
3. Commits and pushes
4. Tells the user: "Done — your Showroom content is now linked at `content/`. Everything you write there gets pushed to your Showroom repo."
5. Dispatches to the writer skill

#### Before dispatching to Automation (substep 7c)

Check `integrations.automation_repo` in the manifest. If null, the instructions depend on the automation approach already captured in the manifest:

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

No template exists yet. Orchestrator tells the user to create an empty repo — the automation skill will scaffold content.

Once the user provides the URL, the orchestrator:

1. Runs `git submodule add <url> automation` in the project repo
2. Updates `integrations.automation_repo` in the manifest
3. Commits and pushes
4. Tells the user: "Done — your automation code is now linked at `automation/`. Everything you write there gets pushed to your automation repo."
5. Dispatches to the automation skill

### 3. What Does NOT Change

- **Manifest schema** — `integrations.showroom_repo` and `integrations.automation_repo` already exist and default to null. No schema changes needed.
- **Template repo** — No structural changes. `content/` and `automation/` are already gitignored with `.gitkeep` placeholders.
- **Writer skill** — Receives a ready-to-use `content/` directory. No repo awareness.
- **Automation skill** — Receives a ready-to-use `automation/` directory. No repo awareness.
- **Other skills** — Intake, editor, worklog — no changes.

## Key Principles

- **Orchestrator owns all repo setup.** Skills write into directories that already exist.
- **Instructions over automation.** The orchestrator tells the user what to do, not does it for them. Repo creation involves decisions (name, org, visibility) that belong to the user.
- **Manual steps are first-class.** `gh` CLI is a convenience shortcut, not the primary path. Not everyone uses GitHub.
- **Discovery is CWD only.** Check the current directory. If not found, ask — don't search subdirectories or the filesystem.
- **Confirm before cloning.** Show the actual absolute path and get confirmation.
