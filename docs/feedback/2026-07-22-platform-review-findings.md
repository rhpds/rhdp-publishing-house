# Publishing House — Platform Review Findings

**Date:** 2026-07-22
**Author:** Nate Stephany
**Context:** Hands-on review of the deployed platform following Part 1 gate enforcement work. These findings are operational issues and UX gaps discovered during testing — not feature requests.

---

## Findings

### 1. Keycloak Session Timeout Too Short

**Observed:** Re-authentication is required every time the RHDH tab is reopened or left idle briefly. The session feels like it expires within minutes.

**Expected:** A reasonable session duration so reviewers can switch between tabs (spec repo, RHDH, Jira) without being logged out each time.

**Action:** Extend the Keycloak session and token lifetimes for the `publishing-house` realm. Check `SSO Session Idle`, `SSO Session Max`, `Access Token Lifespan`, and `Client Session Idle` in the Keycloak admin console or the realm import template (`deployment/roles/keycloak/templates/`).

---

### 2. Test Project Cleanup

**Observed:** 4 items visible in the Backstage catalog, but only 1 active workflow instance. Stale test projects are accumulating across multiple systems — GitHub repos, Jira epics/tasks, DevSpaces workspaces, Backstage catalog entries, and SonataFlow workflow instances.

**Expected:** A way to clean up test projects across all systems when they're no longer needed.

**Action:** Define a cleanup procedure or script that removes a test project from all five systems:
- Delete the GitHub repo (or archive it)
- Close/delete the Jira epic and child tasks
- Delete the DevSpaces workspace
- Unregister the Backstage catalog entity
- Terminate the SonataFlow workflow instance

This doesn't need to be automated yet — a documented manual procedure is fine for now. But it needs to exist so we're not accumulating garbage during testing.

---

### 3. DevSpaces Namespace Resource Limits

**Observed:** Could not start a DevSpaces instance because the user namespace was at capacity — old workspaces were not being reaped.

**Expected:** DevSpaces should clean up idle workspaces automatically, or the namespace resource quotas should be high enough to accommodate active development alongside stale workspaces.

**Action:** Two things:
1. Check the CheCluster `devEnvironments.secondsOfInactivityBeforeIdling` and `secondsOfRunBeforeIdling` settings to ensure idle workspaces are stopped
2. Check whether stopped workspaces are eventually deleted (auto-cleanup) or just remain stopped consuming PVC storage
3. Review the namespace resource quota — if it's too tight for concurrent workspaces, increase it

---

### 4. Content Type Options — Drop "Workshop"

**Observed:** The RHDH template form and intake skill offer three content types: lab, demo, and workshop.

**Expected:** Only two options: **lab** and **demo**. "Workshop" is not a distinct content type in the current Publishing House model.

**Action:** Update in three places:
- RHDH Scaffolder template (`templates/publishing-house-project/template.yaml`) — remove "workshop" from the `content_type` enum
- Validation policy (`central-api/k8s/configmap-validation-policy.yaml` and/or the policy ConfigMap) — remove "workshop" from `valid_content_types`
- Intake skill questions (`skills/intake/references/intake-questions.md`, Q4) — update the wording to "hands-on lab or guided demo"

---

### 5. GitHub Collaborators — Improve Template Form UX

**Observed:** The GitHub collaborators step in the RHDH template form doesn't explain what it's asking for. Users may not realize they need to add their own GitHub ID first, and that additional collaborators are optional.

**Expected:** Clear guidance on the form:
- Prompt: "Enter your GitHub username first. You can also add collaborators who will have write access to the project repo."
- The first entry should be labeled or defaulted as "Your GitHub ID (required)"

**Action:** Update `templates/publishing-house-project/template.yaml` — the GitHub collaborators step needs a `description` or `ui:help` property that explains the expected input.

---

### 6. Project Creation Access Control

**Observed:** Anyone who can access RHDH can use the Publishing House template to create a project. This automatically creates a GitHub repo in the `rhpds` org, triggers a SonataFlow workflow, and (for `rhdp_published` mode) creates a Jira epic.

**Expected:** Only authorized users should be able to create Publishing House projects, since it provisions resources in shared infrastructure.

**Action:** This is an access control decision:
- Who should be allowed to create projects? Content team only, or anyone with RHDH access?
- Enforcement options: Keycloak group/role check in the Scaffolder template, or RHDH catalog permissions, or a Central API check before provisioning
- Related to Part 1 feature #5 (Reviewer Access Control) — the same ACL mechanism could gate both project creation and review approvals

---

### 7. DevSpaces — Claude Code Extension Missing

**Observed:** The DevSpaces workspace does not include the Claude Code VS Code extension. Authors need Claude Code to run the Publishing House skills.

**Action:** Add the Claude Code extension to the DevSpaces workspace configuration. This could be:
- Added to the `.devfile.yaml` in the project template (`templates/publishing-house-project/skeleton/.devfile.yaml`) via a `components[].attributes` extension list
- Or installed via the workspace setup script that already runs during DevSpaces init

---

### 8. DevSpaces — Claude Code Permissions Configuration

**Observed:** When Claude Code starts in DevSpaces, it prompts for permission to run every tool call — scripts, git operations, file writes, etc. This makes the intake flow unusable because the user is constantly clicking "Allow."

**Expected:** Claude Code should be pre-configured to allow the Publishing House tools and common operations without prompting.

**Action:** The DevSpaces workspace setup needs to create or populate `.claude/settings.json` (or `.claude/settings.local.json`) with an allowlist covering:
- `publishing-house/tools/*.py` scripts (ph-intake.py, ph-rcars.py, ph-policy.py, etc.)
- Git operations (add, commit, push, diff, status)
- File read/write in the `publishing-house/` directory
- Any other common operations the skills invoke

The `.devfile.yaml` setup commands already configure auth credentials — the permissions configuration should happen in the same setup phase.

---

### 9. Local Mode — Model Selection

**Observed:** When running the skills locally (outside DevSpaces), the user's Claude Code may be configured to use any model. The intake skill specifies `model: claude-opus-4-6` in its frontmatter, but if the user's harness overrides this or they're on a different default, the experience degrades.

**Expected:** The skill should run on the intended model, or the getting started instructions should clearly tell users to switch to the right model.

**Action:** Two options:
- If the skill frontmatter `model:` field is authoritative (Claude Code respects it regardless of user settings), document this and verify it works
- If not, add a clear step to the getting started / quick start instructions: "Switch to Sonnet before running the intake skill" (or whatever the intended model is for local use)

---

### 10. Local Mode — Python Dependencies Missing

**Observed:** Running locally produces errors like `ModuleNotFoundError: No module named 'yaml'`. The `publishing-house/tools/*.py` scripts require `pyyaml` (and potentially other packages), but there's no setup step to install them. After the error, the skill continues and starts prompting for permission on every subsequent action — compounding the bad experience.

**Expected:** Either the dependencies are installed as part of setup, or the pre-flight check catches the missing module and stops with a clear message before the interview starts.

**Action:**
1. Add a `requirements.txt` to `publishing-house/tools/` (or the project template) listing the Python dependencies the tools need
2. The pre-flight check should verify Python dependencies are available and fail with a clear message ("Missing required Python module: yaml. Run `pip install -r publishing-house/tools/requirements.txt`") instead of letting the skill continue in a broken state
3. The getting started instructions should include the pip install step

---

### 11. Local Mode — API Key Generation and Rotation

**Observed:** When running locally, the skill directs the user to the web portal to generate an API key. It's unclear how often these keys rotate or expire, and whether the user needs to regenerate periodically.

**Expected:** Clear documentation on API key lifecycle — how long keys last, whether they survive pod restarts, and how to regenerate.

**Known issue:** API keys are currently stored in-memory (`keys_db` dict in `central-api/app/routers/projects.py`). This means all keys are lost on every pod restart. Users will need to regenerate keys after any Central API redeployment. This needs to be either fixed (persistent storage) or clearly documented as a known limitation.

---

### 12. Workflow Data 404 — Project Not Found in Central

**Observed:** The workflow data endpoint returned a 404: "not found" when querying Central for a project.

**Expected:** The project should be findable by its slug after creation.

**Action:** Investigate the root cause:
- Was the SonataFlow workflow instance actually created? (Check Data Index via GraphQL)
- Is the business key (project slug) matching between the Scaffolder template output and the workflow query?
- Is the Central API querying the correct SonataFlow GraphQL endpoint?
- Could this be a timing issue — the Scaffolder creates the workflow, but the Data Index hasn't indexed it yet when the skill queries?

This may be a one-off or a systemic issue. Reproduce and check the Central API logs.

---

### 13. Project Creation — Use GitHub Template Repo Instead of Commit-Based Scaffolding

**Observed:** When a new project is created via the RHDH Scaffolder, it creates an empty repo and populates it via a series of commits (fetch:template + publish:github). This means the project repo doesn't use GitHub's "created from template" lineage.

**Expected:** Use `rhdp-publishing-house-template` as a GitHub template repository. New projects should be created with GitHub's "Use this template" / `generate` API, which:
- Preserves the "generated from" link in the GitHub UI
- Lets people create projects from the template **outside** of the Publishing House workflow (same repo structure, same files, same experience)
- Is a single API call instead of fetch + commit + push

**Action:** Evaluate switching the Scaffolder template from `fetch:template` + `publish:github` to using the GitHub template repository API (`POST /repos/{template_owner}/{template_repo}/generate`). This may require a custom Scaffolder action or the `publish:github` action's `templateRepository` option if Backstage supports it.

The template repo (`rhdp-publishing-house-template`, `rearchitecture` branch) would need to be marked as a template repository in GitHub settings.

---

### 14. Test Cleanup — Jira Issues Must Be Archived

**Observed:** Test Jira issues (epics and child tasks) from previous testing sessions are still open or just closed — not archived. They clutter the RHDPCD project board and backlog.

**Expected:** Test issues should be closed AND archived (or deleted if Jira Cloud allows) so they don't appear in queries, boards, or reports.

**Action:** Clean up all test Jira issues from previous sessions. Going forward, the cleanup procedure from finding #2 should include archiving (not just closing) Jira issues as a step.

---

### 15. Cascading Cleanup When a Project is Removed

**Observed:** When a project is deleted or abandoned in Publishing House, its resources remain scattered across systems — GitHub repo, Jira epic, Backstage catalog entry, SonataFlow workflow instance, DevSpaces workspace. Manual cleanup was required across all five systems.

**Expected:** When a project is removed from Publishing House (via RHDH, Central API, or a cleanup tool), all associated resources should be cleaned up automatically or as part of a single coordinated action.

**Action:** Implement cascading cleanup — when a project is deleted/archived in PH, the system should:
- Delete or archive the GitHub repo
- Close and archive the Jira epic and child tasks
- Unregister the Backstage catalog entity
- Terminate the SonataFlow workflow instance
- Delete the DevSpaces workspace (if one exists)

This could be a Central API endpoint, a SonataFlow "cancel" workflow path, or a standalone cleanup script — but it needs to be one action, not five manual steps.

---

### 16. Could Not Register a New Project

**Observed:** Attempted to start over with a new project and could not register it.

**Action:** Investigate the root cause — this could be:
- A name collision with a previously created project (same slug, stale workflow instance still in SonataFlow)
- The Scaffolder template failing silently (check Backstage scaffolder task logs)
- A stale catalog entity blocking re-registration
- Related to finding #12 (workflow data 404) — if the previous project's workflow is in a bad state, it may block creation of a new one with the same name

This reinforces the need for the cleanup procedure (#2) — without it, testing is blocked by leftover state from previous runs.

---

### 17. Validation B-02: max_concurrent_users Required for Per-Student — Deploy Fix

**Observed:** The deployed Central API validation (B-02) requires `max_concurrent_users` for `per-student` and `cnv-pool` topologies. This is wrong — per-student gives each learner their own environment. The number of simultaneous users is an operational/scheduling decision, not something the author knows at intake.

**Status:** Already fixed in `feature/intake-refactor-central` branch (commit `2fa26fe`). B-02 now only requires concurrent users for `shared-cluster` topology. Needs to be merged and deployed.

**Action for Tyrell:** Review and merge `feature/intake-refactor-central`, rebuild and deploy Central API.
