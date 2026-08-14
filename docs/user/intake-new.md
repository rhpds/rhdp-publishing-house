# New Project Intake

This guide walks you through intake for a **new** project — from logging in to Publishing House through completing your project spec with Claude.

!!! tip "Migrating an existing Showroom repo?"
    If you already have a working Showroom repo with `content/`, `site.yml`, and `nav.adoc`, use the [Migration Intake](intake-migration.md) path instead. It imports your content and reverse-engineers the spec from it.

---

## 1. Log in to Publishing House

Open the Publishing House dashboard in your browser. Log in with your Red Hat SSO credentials.

After logging in, you'll see the project pipeline board showing any existing projects and their current lifecycle phase.

---

## 2. Create a project from the template

Click **Self Service** in the left navigation bar, then select the **Publishing House Content Project** template.

The template walks you through three pages:

### Page 1 — Project Details

| Field | Description |
|-------|-------------|
| **Project Name** | Lowercase letters, numbers, and hyphens only (e.g., `openshift-ai-workshop`). This becomes your GitHub repo name — it must be unique. |
| **Project Description** | Brief overview of what this project will deliver. A few sentences is enough — the intake skill will flesh this out later. |
| **Content Type** | `Lab` (hands-on workshop) or `Demo` (presenter-led). |
| **Deployment Mode** | `RHDP Published` (full gates, reviewer required) or `Self-Published` (self-approval allowed). |
| **Tags** | Optional. Add identifiers like a Jira ticket number (`LB1234`), product names, or event tags. |

Click **Next**.

### Page 2 — GitHub Collaborators

| Field | Description |
|-------|-------------|
| **GitHub Users** | Enter your GitHub username as the first entry (required). Add collaborators who need write access to the repo. |

Click **Next**.

### Page 3 — Initiative & Content Format

| Field | Description |
|-------|-------------|
| **Initiative** | Which initiative this content is for — `RH1 2027`, `Summit 2027`, or `None`. |
| **Showroom Type** | `Classic` (standard Showroom lab) or `Zero Touch` (embedded runtime and setup automation with solve/validate buttons). |
| **Automation Type** | `Ansible`, `GitOps`, or `Both`. This determines which automation scaffolding is set up in your repo. |

Click **Review**, verify your selections, then click **Create**.

### What the template does

The template runs five steps automatically:

1. Checks that your project name isn't already taken
2. Generates skeleton files (`catalog-info.yaml`, `spec.yaml`, `.devfile.yaml`, Claude Code settings)
3. Creates a GitHub repo under `rhpds/` from the `rhdp-publishing-house-template` and pushes the skeleton
4. Starts the Publishing House workflow in Central (sets the stage to `intake`)
5. Registers the project in the Developer Hub catalog

### Template output

When the template completes, you'll see three links:

- **Open Repository** — your new GitHub repo
- **View in Catalog** — the project's Developer Hub catalog entry
- **Open in DevSpaces** — launches a browser-based workspace (see next step)

The page also shows getting-started instructions for both DevSpaces and local setup.

---

## 3. Open your workspace

### Option A — Dev Spaces (browser-based)

Click the **Open in DevSpaces** link from the template output page (or from the project's catalog entry).

The workspace takes 1–2 minutes to start on first launch. During startup, six setup tasks run automatically:

1. Downloads the Claude Code VS Code extension
2. Installs Python dependencies for PH tools
3. Installs the Claude CLI
4. Provisions your API key and LiteLLM key (authenticates with the Central API using the DevSpaces service account — no manual token needed)
5. Configures Claude Code settings (API endpoint, model, permissions)
6. Clones the PH skills plugin

Once the workspace is ready, you'll see VS Code in your browser with your project repo open. Start Claude in one of two ways:

- **Extension:** Click the **Claude** icon in the left sidebar, then click **New Session**. If the Claude icon isn't visible, open **Extensions** (`Ctrl/Cmd+Shift+X`), find **Claude Code for VS Code** under the DevSpaces section, click it, then click **Enable (Workspace)**.
- **CLI:** Open a terminal (`` Ctrl+` ``) and run `claude`.

### Option B — Local Claude Code (standalone)

If you prefer to work locally:

1. Install the PH skills plugin (one-time setup):

    ```bash
    git clone https://github.com/rhpds/rhdp-publishing-house-skills.git \
      ~/.claude/skills/publishing-house
    ```

2. Clone the project repo that was created in step 2:

    ```bash
    git clone https://github.com/rhpds/my-openshift-workshop.git
    cd my-openshift-workshop
    ```

3. Start Claude Code:

    ```bash
    claude
    ```

---

## 4. Run the skill

Whether you're in Dev Spaces or running Claude Code locally, the next step is the same. In the Claude Code prompt, type:

```
/rhdp-publishing-house
```

The orchestrator discovers your project, reads the current stage (`intake`), and launches the intake skill.

Before starting the conversation, Claude runs a pre-flight sequence automatically:

1. **Verifies this is a PH project** — checks for `catalog-info.yaml` and `spec.yaml`
2. **Reads project identity** — extracts the project slug from `spec.yaml`
3. **Checks authentication** — verifies your API key exists
4. **Syncs with Central** — fetches workflow state, checks for any prior rejections
5. **Loads validation policy** — fetches the latest product names, content types, and validation rules

!!! note "Local Claude Code — API key prompt"
    When running locally (not in Dev Spaces), Claude will detect that you don't have a Publishing House API key yet. It will open the Central API URL in your browser — log in with your **Red Hat SSO**, click **Generate New Key**, and **paste the key back into Claude**. Claude saves it to `~/.config/publishing-house/auth.json` so you won't be prompted again in future sessions.

!!! tip "Resuming a previous session"
    If you paused intake partway through, Claude detects which phases are already complete (design.md populated, RCARS results present, module outlines exist, infrastructure fields filled) and picks up at the next incomplete phase. You won't repeat work.

---

## 5. Walk through the intake phases

The intake skill runs through six phases. You'll have a conversation with Claude — it asks questions, you provide answers, and together you build the project spec. Each phase commits its output to git, so your progress is saved even if the session ends.

### Phase 1 — Discovery

Claude reads the project description you entered in the template and presents three options:

1. **Build on this description** — uses the description from the template as a starting point and asks follow-up questions to flesh out the details.
2. **I have a doc or outline** — share a Google Doc, Jira issue, Confluence page, or rough notes. Claude extracts what it can and only asks about what's missing.
3. **I already filled this out** — if you've already populated `design.md` and `spec.yaml` in the repo, Claude validates what's there, fills any gaps, and skips ahead to later phases.

Claude skips questions for fields already set by the template (content type, showroom type, deployment mode). For everything else, it has a natural conversation — not a rigid questionnaire. You'll cover:

- What is the goal of this lab or demo? (concrete and measurable)
- Who is the target audience?
- Which Red Hat products and technologies are involved? (validated against the official product list)
- How long should it take? How many modules?
- Any existing reference material? (docs, recordings, diagrams)

!!! note "Minimum to proceed"
    You need at least four things to move to the next phase: **goal**, **audience**, **products**, and **content type**. Everything else can be refined later. Claude will ask specifically about anything missing.

At the end of this phase, Claude writes the captured fields to `spec.yaml` and commits.

> "Discovery complete. Next: design doc. **(4 phases remaining)**"

### Phase 2 — Design document

Claude generates `publishing-house/spec/design.md` from your discovery answers. The design doc has 11 required sections: overview, target audience, prerequisites, learning objectives, content type, products and technologies, module map (with duration table), difficulty level, environment, and optionally assessment strategy.

Key details:

- Claude proposes a **module map** with titles and estimated durations, explaining why it structured it that way. You can adjust.
- **Learning objectives** are scaled to duration — roughly 3 per 45 minutes of content.
- **Infrastructure Requirements** is intentionally left as TBD — that's covered in Phase 5.

Claude presents the design for your review:

> "Here's the design doc I've drafted. Review it and let me know if anything needs changing. You can also edit `publishing-house/spec/design.md` directly in your editor."

**You must explicitly approve before Claude moves on.** If you have feedback, Claude updates the design and re-presents it. After approval, Claude runs a quick structure check (all sections present, valid action verbs in objectives, no unfilled placeholders) and shows the results. This check is non-blocking — you can fix issues now or later.

Claude commits `design.md` and `spec.yaml`, then proceeds.

> "Design doc complete and validated. Next: RCARS vetting. **(3 phases remaining)**"

### Phase 3 — RCARS vetting

Claude queries the RCARS content advisor to check your design against the existing RHDP catalog. This takes 10–20 seconds.

If similar content exists, Claude presents the matches with relevance scores and a summary of what your design covers that existing items don't. This is informational — Claude will never ask you to justify your project's existence. You can adjust your scope based on the findings, or proceed as-is.

If no close matches are found:

> "I checked the RHDP catalog — no close matches found. This looks like new territory."

If RCARS is unavailable, this phase is skipped with a note and will run again at submission.

Claude writes the results to `spec.yaml` and commits.

> "RCARS vetting complete. Next: module outlines. **(2 phases remaining)**"

### Phase 4 — Module outlines

If module outlines already exist in `publishing-house/spec/modules/`, Claude asks whether to validate them or treat them as ready.

Claude generates one outline file per module from the design doc (not from conversation context). Each outline follows the project's `module-outline-template.md` and covers:

- Brief overview
- Audience and estimated time
- Learning objectives
- Lab structure (step-by-step table)
- Detailed steps (numbered)
- Key takeaways
- Infrastructure notes

The outlines are saved as `publishing-house/spec/modules/module-01-<title>.md`, `module-02-<title>.md`, etc. Claude also generates narrative summaries for reviewers and initializes all module statuses to `not_started` in `spec.yaml`.

These outlines are what the writer agent uses later to generate AsciiDoc content — the more detail you add, the better the output.

Claude commits the outlines.

> "Module outlines complete. Next: infrastructure confirmation. **(1 phase remaining)**"

### Phase 5 — Infrastructure

Claude determines your platform (OCP or RHEL VMs) from the products discussed earlier, derives sensible defaults, and presents a complete infrastructure profile for you to confirm or adjust. This is a single interaction, not a long questionnaire.

**For OCP labs**, the profile includes: cloud provider, cluster type (SNO or multinode), worker sizing, OCP version, and topology.

**For RHEL-based labs**, the profile includes: per-student VM roles with sizing (e.g., 1 AAP controller, 2 managed nodes, 1 Windows server).

Claude only asks conditional follow-ups if triggered:

- **AI/MaaS** — only if your products include AI keywords
- **AAP version** — only if AAP is in your products
- **Non-GA products** — only if any product is beta or tech preview
- **External services** — always asked explicitly (container registries, package repos, license servers, Git hosts, external APIs needed during provisioning or student sessions)
- **Concurrent users** — only for shared-cluster topology (per-student topologies don't need this)

After you confirm, Claude writes the infrastructure fields to `spec.yaml` and updates the Infrastructure Requirements section of `design.md`, then commits.

### Phase 6 — Finalize and submit

Claude presents a final summary of everything captured, flagging any fields still empty or with placeholder values.

> "Here's what we have before submitting for review..."

**You must explicitly approve before Claude continues.** If anything needs changing, say so.

Once approved, Claude executes the remaining steps without further prompts:

1. **Generates `mkdocs.yml`** — for TechDocs rendering in Developer Hub
2. **Asks for final confirmation** — one last checkpoint before submission
3. **Commits and pushes** all spec artifacts to your repo
4. **Submits to Central** via `ph-intake.py`

After submission:

- **201 (success)** — your project advances to the review stage
- **422 (validation failed)** — Claude shows each failed check, proposes fixes, and asks you to confirm before applying. After fixes, it resubmits. This loops until validation passes.
- **409/404/other** — Claude shows the error and stops

For classic Showroom projects, Claude also cleans up any zero-touch directories (`runtime-automation/`, `setup-automation/`) that don't apply.

---

## 6. What happens after intake

After a successful intake submission:

- **Onboarded projects** enter review — content and infrastructure reviewers evaluate your spec. You'll be notified when reviews are complete.
- **Self-published projects** move directly to the development stage.

Either way, the next time you open your workspace and run `/rhdp-publishing-house`, the orchestrator picks up exactly where you left off.

### Handling rejections

If reviewers reject parts of your spec, run `/rhdp-publishing-house` again. Claude syncs the rejection reasons from Central, shows them to you grouped by review stage, and walks you through addressing each one. After resolving all rejections, Claude resubmits automatically.

---

## Tips

- **Invest time in module outlines.** They're the foundation for everything that follows — content generation, automation, and review all reference them.
- **You can pause and resume.** Say `"I'm done for today"` or just close the session. The orchestrator saves your progress and picks up next time.
- **Human edits are welcome.** Edit `design.md`, module outlines, or any spec file directly between sessions. Claude reads fresh and respects what's on disk.
- **Bring existing material.** If you have a Google Doc, Confluence page, or rough notes, share them during discovery. Claude extracts structured information rather than asking you to repeat it.
