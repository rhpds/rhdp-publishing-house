# Getting Started

## Prerequisites

### 1. Install Claude Code

[Install Claude Code](https://docs.anthropic.com/en/docs/claude-code) if you haven't already.

### 2. Install the Publishing House plugin

Clone the skills repo. You only do this once.

```bash
git clone git@github.com:rhpds/rhdp-publishing-house-skills.git ~/rhdp-publishing-house-skills
```

Add the plugin to your Claude Code settings, or pass it at launch with `--plugin-dir ~/rhdp-publishing-house-skills`.

### 3. Connect to the Publishing House MCP server

The MCP server gives Claude Code access to RCARS content advisory, project tracking, and session tools. You need an API key from a PH admin.

The easiest way to add it is the `claude mcp add` command:

```bash
claude mcp add --transport http publishing-house \
  "https://ph-mcp.apps.<cluster-domain>/mcp/" \
  --header "Authorization: Bearer <your-api-key>"
```

Replace `<cluster-domain>` with the OpenShift cluster apps domain (ask your admin) and `<your-api-key>` with the raw API key they provide.

Alternatively, add it manually to `~/.claude.json`:

```json
{
  "mcpServers": {
    "publishing-house": {
      "type": "http",
      "url": "https://ph-mcp.apps.<cluster-domain>/mcp/",
      "headers": {
        "Authorization": "Bearer <your-api-key>"
      }
    }
  }
}
```

Restart Claude Code after adding the server.

!!! tip "Verify the connection"
    After restarting, ask Claude: "List PH projects." If the connection is working, you'll see a list of projects (or an empty list if none exist yet).

!!! warning "Troubleshooting"
    - **Connection refused** — verify the URL, check VPN connectivity, confirm the backend is deployed
    - **401 "Authentication required"** — verify the `Authorization` header is set and the key is current
    - **Tool not found** — restart Claude Code and check that `publishing-house` appears in the MCP server list

### 4. Create your project repo from the template

**Option A — GitHub web UI:**

1. Go to `https://github.com/rhpds/rhdp-publishing-house-template`
2. Click **Use this template → Create a new repository**
3. Give it a name and create it
4. Clone it:
   ```bash
   git clone git@github.com:your-org/your-repo.git
   ```

**Option B — `gh` CLI:**

```bash
gh repo create my-new-lab \
  --template rhpds/rhdp-publishing-house-template \
  --clone
cd my-new-lab
```

---

## Quick Start

Start Claude Code from your project directory (or one level above it — the orchestrator will find PH projects in subdirectories). Then run:

```
/rhdp-publishing-house
```

!!! note "Where to start Claude Code"
    The orchestrator looks for a `publishing-house/manifest.yaml` in the current directory and its immediate subdirectories. If it doesn't find a project, it checks Central for your registered projects and offers to help you locate or clone one.

Here's what happens through the first session:

### 1. Intake

The intake agent asks what you're building. If you have a design doc, Google Doc, or rough outline, provide it and the agent extracts answers instead of asking every question.

You'll cover:

- What are you building? (name, type, audience)
- Deployment mode (see [Deployment Modes](deployment-modes.md))
- Modules — how many, rough titles, estimated duration
- Whether the lab needs infrastructure pre-configured

The intake agent produces:

- `publishing-house/spec/design.md` — the master spec
- `publishing-house/spec/modules/module-NN-title.md` — one outline per module

### 2. Vetting

The orchestrator submits the spec to RCARS to check for overlap with existing RHDP content. If similar content exists, you'll be guided through differentiation — adjusting scope or angle to complement what's already there.

### 3. Spec refinement and approval

Refine the spec if needed based on vetting findings, then approve it. This is the checkpoint before content production begins.

### 4. Write, automate, edit

From here, the orchestrator guides you through the remaining phases. Say what you want to do:

- `"write module 1"` — writer agent generates AsciiDoc from the module outline
- `"build automation"` — automation agent captures requirements, creates the catalog, writes code
- `"edit all"` — editor agent reviews content against Red Hat standards and your spec
- `"what's next"` — lightweight status check

### 5. End the session

Say `"I'm done for today"` or `"session summary"`. The orchestrator writes a worklog entry, commits, and pushes. Next session, the pull happens automatically.

!!! tip "Resuming later"
    Run `/rhdp-publishing-house` from your project directory or one level above. The orchestrator finds your project, pulls the latest changes, and presents where things stand. If it can't find the project, it offers to help locate or clone it.

---

## Deployment Modes

Set during intake. Determines the review rigor and publishing target. See [Deployment Modes](deployment-modes.md) for the full comparison.

| Mode | Description | Published to RHDP? |
|------|-------------|-------------------|
| **Onboarded** | Full pipeline with review gates and Jira tracking | Yes |
| **Self-Published** | Same tools, softer gates, you manage deployment | No |
| **Express** | One-off demo environment, no git repo | No |

---

## Autonomy Levels

Control how much confirmation you want at each step:

```
/rhdp-publishing-house              # guided (default) — confirm everything
/rhdp-publishing-house assisted     # auto-fix low-risk, confirm structural changes
/rhdp-publishing-house autonomous   # auto-fix everything clear, stop only for ambiguity
```

Switch mid-session: `"switch to assisted"`

---

## Required vs. Optional Phases

**Required** (cannot be skipped):

- **Intake** — shortcuttable with a pre-existing spec, but always runs
- **Approval** — you review and sign off on the spec; never auto-advanced
- **Technical Editing** — runs regardless of how content was produced
- **Code & Security Review** — required for onboarded; recommended for self-published
- **Final Review** — holistic check before marking ready

**Optional** (skip if handled another way):

- **Vetting** — check against existing RHDP content via RCARS
- **Spec Refinement** — clean up spec before writing starts
- **Writing** — skip if you wrote content manually
- **Automation** — skip if environment setup is handled externally

Say `"skip writing"`, `"I already have content"`, or `"skip automation"` to jump ahead.

---

## Collaborating on a Project

The manifest is the source of truth. Push your repo; a colleague runs `/rhdp-publishing-house` and picks up exactly where you left off.

The orchestrator pulls at session start and pushes at session end — you don't need to manage this manually.

For async handoffs, use the worklog:

```
"leave a note: check with Prakhar on pool sizing before creating the catalog"
"what's outstanding"
"resolve item 2026-04-14-001"
```

---

## Tips

- **Invest in module outlines.** The writer generates content from `publishing-house/spec/modules/` — the more detailed the outline, the better the output.
- **Human edits are expected.** Edit content, specs, and automation files freely between sessions. All agents read fresh and respect what's there.
- **The worklog is for notes, not tasks.** The manifest tracks phases; the worklog tracks decisions, handoffs, and context.
- **Automation testing gate.** After the automation agent writes code, you deploy and test it yourself, then confirm with `"testing done"`.
