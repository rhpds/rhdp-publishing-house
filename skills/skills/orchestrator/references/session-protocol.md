# Session Protocol

## Session Start

After Step 1 confirms this is a Publishing House project:

1. **Sync the repo:** `git pull --rebase --autostash`
2. Read spec.yaml and catalog-info.yaml
3. Check workflow state via Central API
4. Present status concisely

## Session End

Before ending a session:

1. Ensure spec.yaml reflects current state.
2. Commit and push any remaining changes.
