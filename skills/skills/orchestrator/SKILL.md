---
name: rhdp-publishing-house
description: This skill should be used when the user invokes "/rhdp-publishing-house", asks to "start a publishing house project", "check project status", or "what's next on my lab". Handles auth setup, workflow state, intake dispatch, and stage orientation.
---

---
context: main
model: claude-sonnet-4-6
---

# RHDP Publishing House

You handle everything. The author just talks to you. Never tell the author to run scripts or terminal commands.

## What to do when invoked

**Step 1 — Verify this is a Publishing House project:**

Run silently:
```bash
python3 -c "
from pathlib import Path
ci = Path('catalog-info.yaml')
spec = Path('publishing-house/spec.yaml')
if ci.exists() and spec.exists():
    print('ok')
elif not ci.exists():
    print('no-catalog')
else:
    print('no-spec')
"
```

- `ok` → proceed to Step 2.
- `no-catalog` → this is not a Publishing House project. Show:
  > This doesn't look like a Publishing House project — `catalog-info.yaml` is missing.
  >
  > Projects must be created through the **RHDH Developer Hub** template. Open RHDH, choose the **Publishing House Content Project** template, and fill in the form. That will create the repo, register it in the catalog, and start the workflow.
  >
  > Then open the created repo in DevSpaces and run `/rhdp-publishing-house` again.

  **STOP — do not proceed.**
- `no-spec` → show: "`publishing-house/spec.yaml` is missing. This repo may not have been scaffolded correctly." **STOP.**

**Step 2 — Read project identity:**

Run silently:
```bash
python3 -c "
import yaml
from pathlib import Path
spec = yaml.safe_load(Path('publishing-house/spec.yaml').read_text()) or {}
pid = spec.get('project', {}).get('slug', '')
print(f'project_id:{pid}')
"
```

Extract `project_id` from the output. This is used for all subsequent API calls.

If `project_id` is empty → show error: "`project.slug` is missing in `spec.yaml`." **STOP.**

**Step 3 — Check git identity:**

Run silently:
```bash
git config --global user.name
```

If the output is empty (no user.name configured), ask the author:

> **Git identity is not configured in this workspace.**
>
> What is your Git username? (e.g. `treddy`)

Wait for the author to respond. Once they provide a username, run:
```bash
git config --global user.name "USERNAME_HERE"
```
Replace USERNAME_HERE with the provided username.

Confirm: > Git configured as **USERNAME_HERE**.

If the output is non-empty → proceed silently to Step 4.

**Step 4 — Check auth:**

Run silently:
```bash
python3 -c "
import json, os
f = os.path.expanduser('~/.config/publishing-house/auth.json')
if os.path.exists(f):
    d = json.load(open(f))
    cred = d.get('credential', '')
    central = d.get('central', '')
    print(f'cred:{cred[:8]}' if cred else 'no-cred')
    print(f'central:{central}')
else:
    print('missing')
"
```

Extract `central_url` from the `central:` line. This is used for all subsequent API calls.

- Output has `cred:` and `central:` → auth is configured. Proceed to Step 5 silently.
- Output is `missing` → show error: "Workspace auth is not configured. Restart the DevSpaces workspace to trigger setup." **STOP.**
- Output is `no-cred` → the author needs a portal key.

  **ALWAYS show this message:**

  > **You need a Publishing House API key.**
  >
  > Open this URL in your browser:
  > **`{central_url}`**
  >
  > Log in with your Red Hat SSO, click **Generate New Key**, and **paste the key here** — I'll save it for you.

  Then try to open the browser (works locally, silently fails in DevSpaces):
  ```bash
  python3 -c "import subprocess; subprocess.Popen(['open', 'CENTRAL_URL'])" 2>/dev/null || true
  ```
  Replace CENTRAL_URL with the actual `central_url`.

  Wait for the author to paste the key in the chat. Once received, save it:
  ```bash
  python3 -c "
import json, os
key = 'PASTE_KEY_HERE'
path = os.path.expanduser('~/.config/publishing-house/auth.json')
d = json.load(open(path)) if os.path.exists(path) else {}
d['credential'] = key
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, 'w') as f:
    json.dump(d, f, indent=2)
os.chmod(path, 0o600)
print('saved')
"
  ```
  Replace PASTE_KEY_HERE with the actual key.

  Confirm: > Got it — you're all set.

**Step 5 — Read spec.yaml and check workflow state:**

Read `publishing-house/spec.yaml` using the Read tool. Note:
- `project.deployment_mode` — `rhdp_published` or `self_published`
- `project.jira_ticket` — may be blank
- All other pre-populated fields — the intake sub-skill will skip asking about those

Then run the shared workflow script silently:
```bash
python publishing-house/tools/ph-workflow.py
```

Extract `stage`, `epic_key`, `jira_url`, and `workflow_id` from the output. The stage will be one of: `intake`, `review`, `development`, `ready`, or `published`.

The script handles everything: resolves `workflow_id` (calling `/workflow-data` if missing), syncs `jira_ticket` to spec.yaml for `rhdp_published` projects, and queries `/workflow-state` for the current stage. If spec.yaml was updated, commit silently:
```bash
git add publishing-house/spec.yaml
git diff --cached --quiet || git commit -m "feat: sync workflow data from Central API" 2>/dev/null || true
```

**Step 6 — Stage loop:**

This is a loop. After dispatching a skill and it returns, query the API again for the new stage and continue.

```
Loop:
  If stage is intake → dispatch rhdp-publishing-house:intake, wait for return
                        → query API again (same as Step 5), extract new stage, continue loop
  If stage is development → show development status (see below), stop
  If stage is review → show review status (see below), stop
  If stage is ready → show ready status (see below), stop
  If stage is published → show published status (see below), stop
```

To query the API again after a skill returns, run the same script from Step 5 and extract the new `stage`.

## Intake stage — dispatch rhdp-publishing-house:intake

When stage is `intake`, dispatch the intake sub-skill immediately:

```
Dispatch: rhdp-publishing-house:intake
```

The intake skill handles the full flow: interview → spec writing → author approval →
mkdocs generation → commit → API submission → result display. When it returns, the
orchestrator queries the API again for the new stage and continues the loop.

## Stage responses (non-intake)

**review**
> Spec submitted. Three parallel reviews are in progress:
> - **Content Review** — design spec and module outlines
> - **Infra Review** — environment and automation requirements
> - **Development Review** — development readiness and tooling
>
> All three must complete before advancing to Development. Reviewers approve from the RHDH Publishing House portal.

**development**
> You're building. [show failures if any, otherwise: "All checks look good."]
> What do you need help with?

**ready**
> Final gate. Reviewer needs to sign off.
> [show failures if any]

**published**
> This lab is published. ✅

## Rules

- Never tell the author to run any script except opening the portal URL during first-time key setup
- ALWAYS show the portal URL in the conversation — never rely solely on `open` working (DevSpaces has no browser)
- **`project_id`** comes from `spec.yaml` `project.slug` — this is the canonical identifier
- **`central_url`** comes from `~/.config/publishing-house/auth.json` `central` field — written by DevSpaces setup
- Stage is always read from the Central API — auth.json does not store stage
- No `.ph-state` file — all state comes from catalog-info.yaml, spec.yaml, and the Central API
- The orchestrator dispatches skills but does not own submission or advancement — each skill calls its own API endpoint
