# Development

Development is the main working stage of the Publishing House lifecycle — where you write content, build automation, create tests, and configure your Showroom environment. It starts after your project clears the three review gates (Content Review, Infra Review, Staging) and ends when you submit all completed workstreams back to Central.

---

## How it works

Every time you run `/rhdp-publishing-house` during the development stage, Claude presents a **dashboard** showing your outstanding workstreams. You pick one, work on it (with or without AI helpers), and mark it complete when you're done. The dashboard updates each session to reflect your progress.

The development skill tracks five workstream categories:

| Workstream | What it covers | Required? |
|---|---|---|
| **Modules** | AsciiDoc content for each lab module | Yes |
| **GitOps Automation** | Helm charts and ArgoCD manifests in `automation/gitops/` | Yes (if automation type includes GitOps) |
| **Ansible Automation** | Ansible roles in `automation/ansible/` | Yes (if automation type includes Ansible) |
| **E2E Tests** | End-to-end test playbooks in `qa-automation/` | Yes |
| **Health Check** | Health check playbook in `qa-automation/` | Yes |
| **Showroom Config** | `site.yml`, `ui-config.yml`, navigation, tabs | Always available |

Completed workstreams disappear from the dashboard. When all required workstreams are complete, Claude offers to submit development to Central.

---

## 1. Enter development

Open your workspace (Dev Spaces or local Claude Code) and run:

```
/rhdp-publishing-house
```

The orchestrator detects that your project is in the `development` stage and launches the development skill. On every invocation, Claude:

1. **Runs pre-flight** — verifies the project, reads identity, checks auth
2. **Syncs with Central** — fetches the latest workflow state, checks for rejections
3. **Checks the scaffold** — validates that `site.yml`, `ui-config.yml`, `antora.yml`, and `nav.adoc` are properly configured. If there are issues, Claude offers to fix them before proceeding.
4. **Checks in-progress work** — if any workstreams were left `in_progress` from a previous session, Claude asks whether you've finished them

After these checks, the dashboard appears.

### Handling rejections

If reviewers rejected parts of your spec during the review gates, Claude shows the rejection reasons when you enter development. It walks you through addressing each one, then continues to the dashboard.

---

## 2. The development dashboard

The dashboard is the central hub. It shows only incomplete workstreams — once something is done, it's hidden.

```
Development Dashboard

| # | Workstream         | Status          |
|---|--------------------|-----------------|
| 1 | Modules            | 2 of 5 complete |
| 2 | GitOps Automation  | not_started     |
| 3 | Ansible Automation | in_progress     |
| 4 | E2E Tests          | not_started     |
| 5 | Health Check       | not_started     |
| 6 | Showroom Config    | —               |

Type a number to work on that item.
```

Type a number to select a workstream. Each one has its own flow described below.

---

## 3. Modules

Selecting **Modules** from the dashboard shows a list of incomplete modules with their statuses. Select a module to work on it.

### Starting a module

When you select a `not_started` module, Claude:

1. Sets its status to `in_progress` in `spec.yaml`
2. Creates an empty `.adoc` stub at `content/modules/ROOT/pages/[filename].adoc` if one doesn't exist
3. Commits the changes

Then shows three options:

| # | Option |
|---|--------|
| 1 | Write it myself |
| 2 | Use AI writer helper |
| 3 | Back to dashboard |

### Option 1 — Write it myself

Claude points you to the file path and waits. Write your content in your editor, then come back and tell Claude you're done to mark the module complete. If you're not finished yet, go back to the dashboard — the module stays `in_progress` and Claude will ask about it next session.

### Option 2 — AI writer helper

Claude dispatches to the `writer-helper` skill, which generates AsciiDoc content from the module outline you created during intake. The writer uses the design doc, module outline, and any reference material to produce a draft. When it finishes, Claude marks the module complete.

!!! tip "Invest in your module outlines"
    The writer helper generates content directly from your module outlines in `publishing-house/spec/modules/`. The more detail you put in those outlines during intake, the better the generated content.

### Marking modules complete

When a module is marked complete, Claude:

1. Verifies the `.adoc` file exists (warns if missing, but lets you proceed if you confirm)
2. Updates `spec.yaml`
3. Commits and pushes
4. Closes the corresponding Jira ticket

---

## 4. Automation

Automation workstreams depend on the `automation_type` you selected during intake:

| automation_type | Workstreams shown |
|---|---|
| `gitops` | GitOps Automation |
| `ansible` | Ansible Automation |
| `both` | GitOps Automation + Ansible Automation |

### GitOps Automation

If the `automation/gitops/` directory doesn't exist yet, Claude offers to scaffold it using the config-helper (creates Helm chart structure with `bootstrap-infra/` and optionally `bootstrap-tenant/`).

Once the directory exists:

| # | Option |
|---|--------|
| 1 | Use GitOps helper (populates Helm charts with workloads) |
| 2 | Do it myself |
| 3 | Back to dashboard |

**GitOps helper** — dispatches to the `gitops-helper` skill, which clones the `rhdp-gitops-patterns` reference repo, gathers your requirements (from the spec and clarifying questions), classifies resources as infra vs tenant, and generates Helm templates with proper sync-wave annotations. When it finishes, it asks if automation is complete or if you need to do more work.

**Do it myself** — Claude sets the status to `in_progress` and tells you where to work. Come back when you're done.

See [GitOps Automation](gitops.md) for the full guide on chart structure, sync-wave conventions, and AgnosticV integration.

### Ansible Automation

Same flow as GitOps. If `automation/ansible/` doesn't exist, Claude offers to scaffold it.

| # | Option |
|---|--------|
| 1 | Use Ansible helper |
| 2 | Do it myself |
| 3 | Back to dashboard |

**Ansible helper** — dispatches to the `ansible-helper` skill, which lets you create new roles from scratch or import existing roles from a Git repository. When it finishes, it asks if automation is complete or if you need to do more work.

See [Ansible Automation](ansible.md) for the full guide on collection structure, role conventions, and importing from Git.

### Automation ticket closure

There is a single Jira ticket (`write-automation`) covering all automation work. When `automation_type` is `both`, the ticket is only closed when **both** GitOps and Ansible are marked complete — completing one alone does not close it.

---

## 5. E2E Tests

Selecting **E2E Tests** sets the status to `in_progress` (if `not_started`) and shows:

| # | Option |
|---|--------|
| 1 | Mark E2E tests complete |
| 2 | Back to dashboard |

Write your E2E tests in `qa-automation/`. When you're satisfied, come back and mark them complete.

---

## 6. Health Check

Same flow as E2E Tests. Write your health check playbook in `qa-automation/`, then mark it complete.

---

## 7. Showroom Config

Showroom Config is always available on the dashboard regardless of completion status. It gives you two options:

| # | Option |
|---|--------|
| 1 | Set up showroom (config-helper) |
| 2 | Review showroom config (config-reviewer) |
| 3 | Back to dashboard |

### Config helper

The config-helper handles initial scaffolding and configuration:

- Detects your content pattern (classic Showroom or Zero Touch)
- Generates `site.yml`, `ui-config.yml`, `antora.yml`
- Configures tabs (terminal, IDE, console, custom)
- Creates automation directory skeletons if needed

### Config reviewer

The config-reviewer validates your Showroom configuration:

- Checks all config files against known rules
- Detects cross-file mismatches (e.g., tab referenced in `ui-config.yml` but missing from `site.yml`)
- Produces a severity-rated report with fix suggestions

The scaffold check also runs automatically at the start of every development session — if it finds issues, Claude asks whether you want help fixing them before showing the dashboard.

---

## 8. Submission

When all required workstreams are complete (all modules, all applicable automation children, E2E tests, and health check), Claude offers to submit:

> "All workstreams are complete. Would you like to submit development?"

If you confirm, Claude runs the submission script. On success:

> "Development submitted to Central — workflow advanced to review stage."

If you're not ready, select **No** to return to the dashboard.

---

## Pausing and resuming

You can pause at any time — close the session or say you're done for the day. Everything is tracked in `spec.yaml` and committed to git.

Next time you run `/rhdp-publishing-house`:

- Modules left `in_progress` will be flagged — Claude asks if you've finished them
- Automation, E2E, and health check statuses are preserved
- The dashboard shows exactly where you left off

You can also edit files directly between sessions. Claude reads fresh from disk and respects what's there.

---

## Working without AI helpers

Every workstream has a "do it myself" option. The AI helpers (writer, GitOps helper, Ansible helper) are available but never mandatory. You can:

- Write all AsciiDoc content by hand
- Build Helm charts and ArgoCD manifests yourself
- Create Ansible roles without the scaffold helper
- Write E2E tests and health checks manually

Claude tracks status and handles submission regardless of how you produce the work.

---

## Tips

- **Modules and automation can be worked in parallel.** There's no enforced ordering between workstreams — work on whatever makes sense.
- **Use the config reviewer periodically.** It catches mismatches early (e.g., a tab configured in `ui-config.yml` that references a missing service).
- **Human edits are first-class.** Edit `spec.yaml`, module files, or automation templates directly in your editor. Claude reads the current state from disk, not from memory.
- **Completed workstreams can be reopened.** If you need to revisit a completed module or automation workstream, Claude offers to set it back to `in_progress`.
