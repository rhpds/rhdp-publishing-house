# Migration Intake

This guide walks you through intake for an **existing Showroom repo** — importing your content into the Publishing House workflow and generating the spec artifacts from it.

!!! tip "Starting from scratch?"
    If you don't have an existing Showroom repo, use the [New Project Intake](intake-new.md) path instead. It walks you through a conversational discovery to build the spec from your idea.

---

## 1. Log in to Publishing House

Open the Publishing House dashboard in your browser. Log in with your Red Hat SSO credentials.

After logging in, you'll see the project pipeline board showing any existing projects and their current lifecycle phase.

---

## 2. Create a project from the migration template

Click **Self Service** in the left navigation bar, then select the **Publishing House Migration** template.

The template walks you through three pages:

### Page 1 — Project Details

| Field | Description |
|-------|-------------|
| **Project Name** | Lowercase letters, numbers, and hyphens only. This becomes your new GitHub repo name — it must be unique. |
| **Project Description** | Brief overview (max 1500 characters). |
| **Source Repository** | Public GitHub URL of the existing Showroom repo to import (e.g., `https://github.com/rhpds/my-existing-lab`). The `content/`, `site.yml`, and `ui-config.yml` will be copied from this repo. |
| **Content Type** | `Lab` (hands-on workshop) or `Demo` (presenter-led). |
| **Deployment Mode** | `RHDP Published` (full gates, reviewer required) or `Self-Published` (self-approval allowed). |
| **Tags** | Optional identifiers. |

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
3. Creates a GitHub repo under `rhpds/` and **imports content from your source repo** — the `content/` folder, `site.yml`, and `ui-config.yml` are copied in
4. Starts the Publishing House workflow with `intake_type: migration`
5. Registers the project in the Developer Hub catalog

### Template output

When the template completes, you'll see three links:

- **Open Repository** — your new GitHub repo (with your imported content)
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

The orchestrator discovers your project, reads the intake type (`migration`), and launches the **migrate skill**.

Before starting, Claude runs a pre-flight sequence automatically:

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

## 5. Walk through the migration phases

Instead of a conversational discovery, the migrate skill reads your existing content and reverse-engineers the intake artifacts from it. You'll review and approve each step before Claude moves on.

### Phase 1 — Content analysis

Claude spawns a content reader agent that scans your imported repo:

- `site.yml` — project title and metadata
- `nav.adoc` — module ordering and titles
- All `.adoc` pages in `content/modules/ROOT/pages/` — the actual lab content
- `spec.yaml` — any fields pre-populated by the template

For each module page, the reader extracts titles, section structure, code blocks, products mentioned, commands used, and estimated duration. It also identifies infrastructure signals (operators, VMs, AI/GPU references, external services) and audience indicators (prerequisite knowledge, task complexity).

### Phase 2 — Review the analysis

Claude presents a summary of what it found:

> "I've analyzed the imported content. Here's what I found:
>
> **Title:** OpenShift AI Workshop
> **Modules:** 5 modules: Introduction, Model Training, Model Serving, Pipeline Setup, Monitoring
> **Products:** RHOAI, OpenShift, Pipelines
> **Estimated duration:** 3 hours
>
> Does this look right? Anything I should adjust before I generate the spec?"

**You must confirm before Claude proceeds.** Adjust anything that looks off.

### Phase 3 — Design doc and spec generation

Claude spawns a migration writer agent that generates the intake artifacts from the content analysis:

- **`design.md`** — all 11 sections populated from the existing content (overview, audience, prerequisites, learning objectives, module map with durations, difficulty level, environment description). Infrastructure is left as TBD — that's covered in Phase 5.
- **`spec.yaml`** — fields populated where the content provides clear signals (title, audience, duration, products, modules). Fields left empty when the content doesn't provide enough information.
- **Module outlines** — one per module in `publishing-house/spec/modules/`, derived from the actual content pages rather than from scratch.

Claude presents the design doc for your review. **You must explicitly approve before it moves on.** After approval, it runs a structure check (all sections present, valid action verbs in objectives, no unfilled placeholders).

These outlines are what the writer agent uses later to generate AsciiDoc content — the more detail you add, the better the output.

Claude commits `design.md`, `spec.yaml`, and the module outlines.

### Phase 4 — RCARS vetting

Claude queries the RCARS content advisor to check your design against the existing RHDP catalog. This takes 10–20 seconds.

The source repo you're migrating from is automatically filtered out of the results — your existing lab won't be flagged as a duplicate of itself.

If similar content exists, Claude presents the matches with relevance scores and a summary of what your design covers that existing items don't. This is informational — Claude will never ask you to justify your project's existence. You can adjust your scope based on the findings, or proceed as-is.

If no close matches are found:

> "I checked the RHDP catalog — no close matches found. This looks like new territory."

If RCARS is unavailable, this phase is skipped with a note and will run again at submission.

Claude writes the results to `spec.yaml` and commits.

### Phase 5 — Infrastructure

Claude determines your platform (OCP or RHEL VMs) from the products detected in your content, derives sensible defaults, and presents a complete infrastructure profile for you to confirm or adjust. This is a single interaction, not a long questionnaire.

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

1. **Generates a draft automation manifest** (`automation-manifest.yaml`) — derived from your spec, covering operators, infrastructure, RBAC, and external services
2. **Generates `mkdocs.yml`** — for TechDocs rendering in Developer Hub
3. **Asks for final confirmation** — one last checkpoint before submission
4. **Commits and pushes** all spec artifacts to your repo
5. **Submits to Central** via `ph-intake.py`

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

- **Invest time in module outlines.** Even though they're auto-generated from your content, review and refine them. They're the foundation for everything that follows — content generation, automation, and review all reference them.
- **You can pause and resume.** Say `"I'm done for today"` or just close the session. The orchestrator saves your progress and picks up next time.
- **Human edits are welcome.** Edit `design.md`, module outlines, or any spec file directly between sessions. Claude reads fresh and respects what's on disk.
- **Content is preserved.** Your original Showroom content in `content/` is untouched during migration intake. The spec artifacts are generated alongside it, not as replacements.
