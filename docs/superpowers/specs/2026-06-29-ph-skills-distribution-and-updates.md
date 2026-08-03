# PH Skills Distribution and Update Workflow

**Date:** 2026-06-29
**Updated:** 2026-08-03
**Status:** Draft
**Author:** Prakhar Srivastava
**Scope:** How users install the PH plugin package, how they receive updates, and how PH manages plugin versions at runtime.

## What's Included

`rhdp-publishing-house-skills` is a multi-plugin repo containing:

| Plugin | Source | Skills/Agents |
|--------|--------|---------------|
| `rhdp-publishing-house` | Native | orchestrator, intake, development, worklog, gitops-helper, ansible-helper |
| `ftl` | Copied from marketplace | content-reader, solve-writer, validate-writer, env-connector, rhdp-lab-validator |

Additionally, two showroom content agents live at the repo root (not as a plugin):
- `agents/file-generator.md` — called directly by development:writer
- `agents/module-reviewer.md` — called directly by development:editor

**agnosticv stays in `rhdp-skills-marketplace`** — PH automation procedure calls it from there. Users who need agnosticv must still have marketplace installed.

---

## Install: First Time

### User-facing command
```bash
git clone git@github.com:rhpds/rhdp-publishing-house-skills.git ~/rhdp-publishing-house-skills
```

Then add to Claude Code settings (`~/.claude/settings.json`):
```json
{
  "pluginDirectories": ["~/rhdp-publishing-house-skills"]
}
```

Claude Code scans `pluginDirectories` for `.claude-plugin/plugin.json` files — it finds 2:
1. Root `plugin.json` → registers `rhdp-publishing-house` plugin
2. `ftl/.claude-plugin/plugin.json` → registers `ftl` plugin

Both plugins and all agents are immediately available. **No second install needed for PH content work.**

**Note:** Users who work on automation (AgnosticV catalog creation) still need `rhdp-skills-marketplace` installed for `agnosticv:catalog-builder`.

---

## Update: Getting the Latest

### How users update
```bash
cd ~/rhdp-publishing-house-skills
git pull
```

One pull updates all plugins (rhdp-publishing-house + ftl) simultaneously.

### Frequency recommendation
Pull before starting a new PH project. Do not pull during a live session — mid-session skill updates could cause inconsistent behavior if an agent definition changes while a pipeline is running.

---

## Version Gate at Session Start

The PH orchestrator checks plugin versions before doing any work. If a plugin is below the minimum required version, it surfaces a clear error and stops.

```
## Session Start — Version Check

Before any routing, read each plugin's version:
- Read ~/.../rhdp-publishing-house-skills/.claude-plugin/plugin.json → rhdp-publishing-house version
- Read ~/.../rhdp-publishing-house-skills/ftl/.claude-plugin/plugin.json → ftl version

MINIMUM_REQUIRED = {
  "rhdp-publishing-house": "0.3.0",
  "ftl": "TBD"
}

For each plugin:
  if installed_version < minimum_required:
    → Print: "❌ [plugin] v{installed} is below minimum v{required}. Update: cd ~/rhdp-publishing-house-skills && git pull"
    → STOP — do not continue the session

All versions OK → continue to normal session flow.
```

---

## Release Cadence

Since all plugins live in one repo, they release together. A `git push` to main that updates `agents/file-generator.md` also ships the current `ftl` as-is.

### Version bump rules
| Change type | Which plugin bumps? |
|------------|-------------------|
| file-generator or module-reviewer agent fix | rhdp-publishing-house (minor bump) |
| ftl agent fix | ftl (minor bump) |
| PH orchestrator fix | rhdp-publishing-house only |
| New gitops-helper or ansible-helper feature | rhdp-publishing-house (minor bump) |

### Git tagging
Tags are on the repo level (not per-plugin):
```
v1.0.0 — initial release with ftl + content agents
v1.1.0 — gitops-helper improvements
```

---

## What Stays in Marketplace

| Plugin | Status |
|--------|--------|
| agnosticv | Active — all features, no change |
| showroom skills | Active — standalone use outside PH |
| showroom scaffold agents | Active — owned by Andrew Jones (RHDPCD-172) |
| health | Active |
| sandbox-cli | Active |

The marketplace is not frozen or deprecated. It continues to serve users who install it standalone. PH users only need marketplace for agnosticv (automation phase).

---

## Edge Cases

### User has both marketplace AND PH installed
No conflict — `rhdp-publishing-house` and `ftl` are distinct plugin names from marketplace plugins. Agents are not plugins, so no name collision risk.

### User only has marketplace (no PH)
Showroom and agnosticv skills still work as before — marketplace is unchanged.

### agnosticv not installed
PH automation phase (7b catalog creation) will fail when `agnosticv:catalog-builder` is called. The development skill should surface a clear error: "agnosticv plugin required for catalog creation. Install rhdp-skills-marketplace."

### PH auto-updates during a session
Do not pull during an active PH session. Document: "Do not pull during a live session."
