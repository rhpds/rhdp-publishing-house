# Intake Guide

This guide walks you through the entire intake process — from logging in to Publishing House through completing your project spec with Claude.

---

## 1. Log in to Publishing House

Open the Publishing House dashboard in your browser. Log in with your Red Hat SSO credentials.

After logging in, you'll see the project pipeline board showing any existing projects and their current lifecycle phase.

---

## 2. Create a project from the template

Click **Self Service** in the navigation bar. This opens the project creation form.

1. Give your project a name (e.g., `my-openshift-workshop`)
2. Select a deployment mode:
    - **Onboarded** — full RHDP catalog pipeline with review gates and Jira tracking
    - **Self-Published** — same tools, softer gates, you manage deployment
3. Click **Create Project**

Publishing House creates a git repository from the `rhdp-publishing-house-template`, registers the project in Central, and sets the initial lifecycle stage to `intake`.

Once the template finishes, you'll see your new project on the dashboard with a **Launch Workspace** button.

---

## 3. Open your workspace

You have two options for working on your project:

### Option A — Dev Spaces (browser-based)

Click **Launch Workspace** (or **Open in Dev Spaces**) on your project page. Publishing House provisions a Dev Spaces workspace with:

- VS Code in the browser with your project repo cloned
- Claude Code pre-installed and configured
- MaaS API key provisioned automatically
- PH skills plugin pre-loaded

The workspace takes 1–2 minutes to start on first launch. Subsequent launches are faster.

Once the workspace is ready, you'll be redirected to VS Code in your browser. Open the terminal (`` Ctrl+` ``) or use the Claude Code chat panel in the sidebar.

### Option B — Local Claude Code (standalone)

If you prefer to work locally:

1. Clone the project repo that was created in step 2:

    ```bash
    git clone git@github.com:your-org/my-openshift-workshop.git
    cd my-openshift-workshop
    ```

2. Make sure the PH skills plugin is installed. If you haven't set it up yet, follow the [Getting Started](getting-started.md) prerequisites (install Claude Code, clone the skills repo, connect the MCP server).

3. Start Claude Code from your project directory:

    ```bash
    claude
    ```

---

## 4. Start the intake skill

Whether you're in Dev Spaces or running Claude Code locally, the next step is the same. In the Claude Code prompt, type:

```
/rhdp-publishing-house
```

The orchestrator discovers your project, reads the current stage (`intake`), and launches the intake skill.

!!! tip "First run"
    On the very first invocation, the orchestrator may sync project state from Central and set up local configuration. This is automatic — just follow the prompts.

!!! note "Local Claude Code — API key prompt"
    When running locally (not in Dev Spaces), Claude will detect that you don't have a Publishing House API key yet. It will open the Central API URL in your browser — log in with your **Red Hat SSO**, click **Generate New Key**, and **paste the key back into Claude**. Claude saves it to `~/.config/publishing-house/auth.json` so you won't be prompted again in future sessions.

---

## 5. Walk through the intake conversation

The intake skill runs through six phases. You'll have a conversation with Claude — it asks questions, you provide answers, and together you build the project spec.

### Phase 1 — Discovery

Claude asks what you're building. You can provide as much or as little detail as you have:

- **Start from an idea:** Describe your workshop or demo concept and Claude will ask follow-up questions to fill in the details.
- **Start from a document:** Paste or reference a Google Doc, Jira issue, or design notes. Claude extracts what it can and only asks about what's missing.

You'll cover:

- What is the goal of this lab or demo?
- Who is the target audience?
- Which Red Hat products and technologies are involved?
- Is this a workshop (hands-on) or a demo (presenter-led)?
- How long should it take? How many modules?

!!! note
    You don't need all the answers right now. Claude works with what you have and helps you figure out the rest. The only hard requirements to move forward are: goal, audience, products, and content type.

### Phase 2 — Design document

Claude generates a `design.md` file from your discovery answers. This is the narrative spec for your project — it covers overview, audience, prerequisites, learning objectives, module map, and difficulty level.

Claude presents the design for your review. Read through it and suggest any changes. Once you approve, it's written to `publishing-house/spec/design.md`.

### Phase 3 — RCARS vetting

Claude checks your design against the existing RHDP catalog to identify overlapping content. If similar labs or demos already exist, Claude presents them as context — not as a challenge to justify your project. You can adjust your scope or angle if needed, or proceed as-is.

If RCARS is unavailable, this phase is skipped with a note.

### Phase 4 — Module outlines

For each module in your design, Claude generates a detailed outline covering:

- Learning objectives
- Lab structure (step-by-step breakdown)
- Estimated duration
- Key takeaways
- Infrastructure notes

The outlines are saved to `publishing-house/spec/modules/`. These are what the writer agent will use later to generate the actual AsciiDoc content, so the more detail you add here, the better the output will be.

### Phase 5 — Infrastructure

Claude presents an infrastructure profile based on your products and module requirements:

- Platform (OpenShift, RHEL VMs, or Zero Touch)
- Cluster type and sizing
- Multi-user topology
- AI/MaaS requirements (if applicable)
- External services

Review the profile and confirm or adjust. This is a single confirm-or-adjust interaction, not a long questionnaire.

### Phase 6 — Finalize and submit

Claude presents a final summary of everything captured. Review it and approve.

Once approved, Claude:

1. Generates supporting files (automation manifest, TechDocs config)
2. Commits all spec artifacts to your repo
3. Pushes to the remote
4. Submits the spec to Central via `ph-intake.py`

If validation passes, your project advances to the next stage. If there are validation issues, Claude shows you what needs fixing and helps you address them before resubmitting.

---

## 6. What happens after intake

After a successful intake submission:

- **Onboarded projects** enter review — content and infrastructure reviewers evaluate your spec. You'll be notified when reviews are complete. If there are rejections, run `/rhdp-publishing-house` again and Claude will walk you through addressing each one.
- **Self-published projects** move directly to the development stage. Run `/rhdp-publishing-house` to start writing content, building automation, or configuring Showroom.

Either way, the next time you open your workspace and run `/rhdp-publishing-house`, the orchestrator picks up exactly where you left off.

---

## Tips

- **Invest time in module outlines.** They're the foundation for everything that follows — content generation, automation, and review all reference them.
- **You can pause and resume.** Say `"I'm done for today"` or just close the session. The orchestrator saves your progress and picks up next time.
- **Human edits are welcome.** Edit `design.md`, module outlines, or any spec file directly between sessions. Claude reads fresh and respects what's on disk.
- **Bring existing material.** If you have a Google Doc, Confluence page, or rough notes, share them during discovery. Claude extracts structured information rather than asking you to repeat it.
