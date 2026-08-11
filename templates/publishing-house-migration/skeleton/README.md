# ${{ values.project_name }}

${{ values.project_description }}

**Owner:** ${{ values.github_user }}
**Migrated from:** ${{ values.migrated_repo }}

---

## What was set up

1. Repository created (migrated from existing Showroom repo)
2. `catalog-info.yaml` added to repository
3. Registered in Developer Hub catalog
4. Orchestrator workflow started — your AI-guided content pipeline is running!

## What happens next

Claude will walk you through the entire content lifecycle — from intake and spec creation, through Jira tracking and reviews, all the way to a published lab on RHDP. Just follow the prompts!

## Getting started

### DevSpaces (recommended)

1. Open in DevSpaces: `https://${{ values.devspaces_url | replace('https://', '') }}#${{ values.repo_url }}`
2. Use Claude via the **extension** or the **CLI**:
   - **Extension:** Click the **Claude** icon in the sidebar, click **New Session**. If the Claude icon is not visible, open **Extensions** (`Ctrl/Cmd+Shift+X`), find **Claude Code for VS Code** under the DevSpaces section, click it, then click **Enable (Workspace)**.
   - **CLI:** Open a terminal and run `claude`
3. Run `/rhdp-publishing-house` — and you're off!

### Local machine

1. Install the skills:
   ```
   git clone -b ${{ values.ph_git_ref }} https://github.com/rhpds/rhdp-publishing-house-skills.git ~/.claude/skills/publishing-house
   ```
2. Clone the repo:
   ```
   git clone ${{ values.repo_url }}
   ```
3. `cd ${{ values.project_name }}`
4. Start Claude CLI: `claude`
5. Run `/rhdp-publishing-house` — and you're off!
