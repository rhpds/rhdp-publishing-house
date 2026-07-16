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

**Step 2 — Read project identity and Central API URL:**

Run silently:
```bash
python3 -c "
import yaml
from pathlib import Path
ci = yaml.safe_load(Path('catalog-info.yaml').read_text())
spec = yaml.safe_load(Path('publishing-house/spec.yaml').read_text()) or {}
pid = ci.get('metadata', {}).get('name', '')
central = spec.get('system', {}).get('central', '')
print(f'project_id:{pid}')
print(f'central:{central}')
"
```

Extract `project_id` and `central_url` from the output. These are used for all subsequent API calls.

If `project_id` is empty → show error: "`metadata.name` is missing in `catalog-info.yaml`." **STOP.**
If `central_url` is empty → show error: "`system.central` is not set in `spec.yaml`. Re-scaffold from the RHDH template." **STOP.**

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
    print('found:' + cred[:8] if cred else 'empty')
else:
    print('missing')
"
```

- Output starts with `found:` → credential exists. Proceed to Step 4 silently.
- Output is `missing` or `empty` → the author needs a portal key.

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
central = 'CENTRAL_URL_HERE'
path = os.path.expanduser('~/.config/publishing-house/auth.json')
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, 'w') as f:
    json.dump({'credential': key, 'portal': central}, f, indent=2)
os.chmod(path, 0o600)
print('saved')
"
  ```
  Replace PASTE_KEY_HERE with the actual key and CENTRAL_URL_HERE with `central_url`.

  Confirm: > Got it — you're all set.

  Proceed to Step 4 immediately.

**Step 5 — Read spec.yaml and check workflow state:**

Read `publishing-house/spec.yaml` using the Read tool. Note:
- `project.deployment_mode` — `rhdp_published` or `self_published`
- `project.jira_ticket` — may be blank
- All other pre-populated fields — the intake sub-skill will skip asking about those

Then query the workflow stage silently:
```bash
python3 -c "
import json, os, ssl, urllib.request
creds = json.load(open(os.path.expanduser('~/.config/publishing-house/auth.json')))
key = creds.get('credential', '')
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
req = urllib.request.Request(
    'CENTRAL_URL/api/v1/projects/PROJECT_ID/workflow-data',
    headers={'Authorization': f'Bearer {key}'}
)
try:
    result = json.loads(urllib.request.urlopen(req, context=ctx, timeout=10).read().decode())
    stage = result.get('stage', 'intake')
    epic_key = result.get('epic_key', '')
    jira_url = result.get('jira_url', '')
    print(f'stage:{stage}')
    print(f'epic_key:{epic_key}')
    print(f'jira_url:{jira_url}')
except Exception as e:
    print('stage:intake')
    print('epic_key:')
    print('jira_url:')
"
```
Replace CENTRAL_URL with `central_url` and PROJECT_ID with `project_id`.

Extract `stage`, `epic_key`, and `jira_url` from the output. The stage will be one of: `intake`, `review`, `development`, `ready`, or `published`.

**Sync Jira ticket (rhdp_published only):**

If `project.deployment_mode` is `rhdp_published` AND `project.jira_ticket` in spec.yaml is blank AND `epic_key` from the workflow-data response is non-empty — update spec.yaml:
```bash
python3 -c "
import yaml
from pathlib import Path
spec_path = Path('publishing-house/spec.yaml')
spec = yaml.safe_load(spec_path.read_text()) or {}
spec.setdefault('project', {})['jira_ticket'] = 'EPIC_KEY_HERE'
with open(spec_path, 'w') as f:
    yaml.dump(spec, f, default_flow_style=False, sort_keys=False)
print('updated')
"
```
Replace EPIC_KEY_HERE with the actual `epic_key`. Commit silently:
```bash
git add publishing-house/spec.yaml
git commit -m "feat: sync Jira ticket from workflow" 2>/dev/null || true
```

If `project.deployment_mode` is `self_published`, skip the Jira ticket sync entirely — self-published projects don't use Jira.

**Step 6 — Orient by stage:**

- **intake** → dispatch the intake sub-skill (see below)
- **review** → present reviews status (see Stage responses)
- **development** → present development status (see Stage responses)
- **ready** → present ready status (see Stage responses)
- **published** → present published status (see Stage responses)

## Intake stage — dispatch rhdp-publishing-house:intake

When stage is `intake`, dispatch the intake sub-skill immediately:

```
Dispatch: rhdp-publishing-house:intake
```

The intake sub-skill will:
1. Read spec.yaml and skip fields that are already populated
2. Conduct the requirements interview (one question at a time)
3. Write `publishing-house/spec/design.md` from the interview answers
4. Write `publishing-house/spec/modules/module-0N-*.md` outlines (one per module)
5. Update spec.yaml with structured data from the interview
6. Present the completed design to the author for review

**When the intake sub-skill signals it has finished writing the spec, the orchestrator MUST:**

Ask the author explicitly — do NOT proceed without this confirmation:

> Here's what was designed for your lab. Take a moment to review `publishing-house/spec/design.md` and the module outlines in `publishing-house/spec/modules/`.
>
> **Are you happy with the design and ready to submit for review?**
> - Type **yes** (or "looks good", "proceed") to submit
> - Or give feedback and I'll update the spec

**Wait for the author's response. Do NOT auto-proceed.**

- **If feedback** → send the feedback back to the intake sub-skill and wait again
- **If yes/looks good/proceed** → immediately execute the following steps WITHOUT asking again:

**Step A0 — Generate mkdocs.yml and add TechDocs annotation:**

Generate `mkdocs.yml` at the repo root so RHDH TechDocs can render the spec as documentation.
Run silently:
```bash
python3 -c "
import yaml, glob, os
from pathlib import Path

# Read spec for project title
spec = yaml.safe_load(Path('publishing-house/spec.yaml').read_text()) or {}
title = spec.get('spec', {}).get('title', spec.get('project', {}).get('slug', 'Publishing House Project'))

# Generate index.md with links to design and modules
modules = sorted(glob.glob('publishing-house/spec/modules/module-*.md'))
index_lines = [f'# {title}', '', 'Welcome to the project spec. Use the navigation to browse the design and module outlines.', '', '- [Design Spec](design.md)']
for m in modules:
    fname = os.path.basename(m)
    parts = fname.replace('.md', '').split('-', 2)
    num = int(parts[1]) if len(parts) > 1 else 0
    label = parts[2].replace('-', ' ').title() if len(parts) > 2 else fname
    index_lines.append(f'- [Module {num} - {label}](modules/{fname})')
Path('publishing-house/spec/index.md').write_text(chr(10).join(index_lines) + chr(10))

# Build nav from spec/modules directory
nav = [{'Home': 'index.md'}, {'Design Spec': 'design.md'}]
if modules:
    mod_nav = []
    for m in modules:
        fname = os.path.basename(m)
        # Convert module-01-some-title.md -> 'Module 1 - Some Title'
        parts = fname.replace('.md', '').split('-', 2)
        num = int(parts[1]) if len(parts) > 1 else 0
        label = parts[2].replace('-', ' ').title() if len(parts) > 2 else fname
        mod_nav.append({f'Module {num} - {label}': f'modules/{fname}'})
    nav.append({'Modules': mod_nav})

# Check for other spec files
if Path('publishing-house/spec/automation-manifest.yaml').exists():
    nav.append({'Automation Manifest': 'automation-manifest.yaml'})
if Path('publishing-house/spec/module-outline-template.md').exists():
    nav.append({'Module Outline Template': 'module-outline-template.md'})

mkdocs = {
    'site_name': title,
    'docs_dir': 'publishing-house/spec',
    'nav': nav,
    'plugins': ['techdocs-core'],
}
with open('mkdocs.yml', 'w') as f:
    yaml.dump(mkdocs, f, default_flow_style=False, sort_keys=False)
print('mkdocs.yml created')
"
```

Then add the `backstage.io/techdocs-ref` annotation to `catalog-info.yaml`:
```bash
python3 -c "
import yaml
from pathlib import Path

ci_path = Path('catalog-info.yaml')
ci = yaml.safe_load(ci_path.read_text()) or {}
annotations = ci.setdefault('metadata', {}).setdefault('annotations', {})
if 'backstage.io/techdocs-ref' not in annotations:
    annotations['backstage.io/techdocs-ref'] = 'dir:.'
    with open(ci_path, 'w') as f:
        yaml.dump(ci, f, default_flow_style=False, sort_keys=False)
    print('techdocs annotation added')
else:
    print('techdocs annotation already present')
"
```

**Step A — Commit and push:**
```bash
git add publishing-house/ mkdocs.yml catalog-info.yaml
git commit -m "feat: intake complete — design spec and module outlines"
git push
```

**Step B — Submit intake to Central API:**
```bash
python publishing-house/tools/ph-intake.py 2>&1
```

**Run this immediately. Do NOT ask the author. Do NOT wait for confirmation. Just run it.**

`ph-intake.py` reads `project_id` from `catalog-info.yaml`, reads spec data from `spec.yaml`,
calls `POST {central_url}/api/v1/projects/{project_id}/intake`, and updates `spec.yaml`
with the returned Jira ticket.

Parse the JSON output from ph-intake.py.

**Step C — Commit and push the updated spec.yaml (with Jira ticket):**
```bash
git add publishing-house/spec.yaml
git commit -m "feat: add Jira ticket from intake submission"
git push
```

**Run this immediately. Do NOT ask the author.**

**Step D — Tell the author what happened:**
> ✅ Spec submitted.
> [For rhdp_published: "Jira ticket: **{epic_key}** — {jira_url}". For self_published: "No Jira — self-published mode."]
> Stage is now **{stage}**. [Explain what happens next in one sentence.]

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
- **`project_id`** comes from `catalog-info.yaml` `metadata.name` — this is the canonical identifier
- **`central_url`** comes from `spec.yaml` `system.central` — used for ALL API calls
- Stage is read from the Central API, never from local files
- After intake approval: run git commit, ph-intake.py, and update IMMEDIATELY. No confirmation. No asking.
- No `.ph-state` file — all state comes from catalog-info.yaml, spec.yaml, and the Central API

## Post-Intake: Project Structure Cleanup

When returning from intake, check `project.showroom_type` in spec.yaml.

- **If `classic`** (or empty/unset): Remove Zero-Touch directories silently:
  ```bash
  rm -rf runtime-automation/ setup-automation/
  git add -A runtime-automation/ setup-automation/ 2>/dev/null || true
  ```
- **If `zero_touch`**: Keep `runtime-automation/` and `setup-automation/` in place.
