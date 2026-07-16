# PH Skills Distribution and Update Workflow

**Date:** 2026-06-29  
**Status:** Draft  
**Author:** Prakhar Srivastava  
**Scope:** How users install the combined PH plugin, how they receive updates, and how PH manages plugin versions at runtime.

## Background: Why This Consolidation

This spec reflects decisions made after:
- **Graphify analysis** of 1,643-node PH knowledge graph confirming 8 EXTRACTED call edges: writer→showroom (×2), editor→showroom (×1), orchestrator→agnosticv (×2), automation→agnosticv (×3)
- **Council review** (4 voices: Architect, Skeptic, Pragmatist, Critic) — Pragmatist verdict: "8 EXTRACTED cross-boundary edges = the boundary is already fiction. Users who install PH without marketplace get silent failures today."
- **FTL graph finding:** zero direct PH→FTL call edges exist today; FTL is included forward-looking for future integration
- **Shared interface confirmed:** PH and marketplace skills share state via manifest.yaml + MCP tools, NOT via ph_payload. ph_payload is the headless invocation interface (PH automation → marketplace skills), not a state-sharing mechanism.

---

## The Core Problem: Skill Updates

Skills are Markdown files in a git repo. "Getting the latest" is a `git pull`. But:
- Users may not know when to pull
- PH may depend on a minimum version of a skill that changed
- Multiple plugin dirs in one repo means all plugins update together (no independent cadence)
- PH must detect version skew and tell users what to do

This spec defines the full lifecycle: install → use → update → version gate.

---

## Install: First Time

### User-facing command (unchanged)
```bash
git clone git@github.com:rhpds/rhdp-publishing-house-skills.git ~/rhdp-publishing-house-skills
```

Then add to Claude Code settings (`~/.claude/settings.json`):
```json
{
  "pluginDirectories": ["~/rhdp-publishing-house-skills"]
}
```

Claude Code scans `pluginDirectories` for `.claude-plugin/plugin.json` files — it finds 4:
1. Root `plugin.json` → registers `rhdp-publishing-house` plugin
2. `showroom/.claude-plugin/plugin.json` → registers `showroom` plugin  
3. `agnosticv/.claude-plugin/plugin.json` → registers `agnosticv` plugin
4. `ftl/.claude-plugin/plugin.json` → registers `ftl` plugin

All skills from all 4 plugins are immediately available. **No second install.**

---

## Update: Getting the Latest

### How users update
```bash
cd ~/rhdp-publishing-house-skills
git pull
```

One pull updates all 4 plugins simultaneously. This is the primary update mechanism — it is intentionally simple.

### PH self-update prompt (at session start)
When the PH orchestrator starts, it can optionally check for updates:

```bash
# Orchestrator runs this at session start
cd $(dirname $(cat ~/rhdp-publishing-house-skills/.git/HEAD))
git fetch --quiet origin main
BEHIND=$(git rev-list HEAD..origin/main --count 2>/dev/null || echo "0")
if [ "$BEHIND" -gt "0" ]; then
  echo "⚠️  PH skills are $BEHIND commits behind. Run: cd ~/rhdp-publishing-house-skills && git pull"
fi
```

This check is **opt-in** in the orchestrator — it runs only if the user has PLUGIN_AUTO_CHECK_UPDATES=true in their env or config. Default: off (don't slow session start).

### Frequency recommendation
Pull before starting a new PH project. Pull whenever the orchestrator warns you. Do not auto-pull during a live session — mid-session skill updates could cause inconsistent behavior if an agent definition changes while a pipeline is running.

---

## Version Gate at Session Start

The PH orchestrator checks plugin versions before doing any work. If a plugin is below the minimum required version, it surfaces a clear error and stops.

### Version check implementation (in orchestrator SKILL.md)
```
## Session Start — Version Check

Before any routing, read each plugin's version:
- Read ~/.../rhdp-publishing-house-skills/.claude-plugin/plugin.json → rhdp-publishing-house version
- Read ~/.../rhdp-publishing-house-skills/showroom/.claude-plugin/plugin.json → showroom version
- Read ~/.../rhdp-publishing-house-skills/agnosticv/.claude-plugin/plugin.json → agnosticv version
- Read ~/.../rhdp-publishing-house-skills/ftl/.claude-plugin/plugin.json → ftl version

MINIMUM_REQUIRED = {
  "rhdp-publishing-house": "0.2.0",
  "showroom": "2.14.0",     # ph_payload headless mode
  "agnosticv": "2.15.0",    # ph_payload + agent decomposition
  "ftl": "TBD"
}

For each plugin:
  if installed_version < minimum_required:
    → Print: "❌ [plugin] v{installed} is below minimum v{required}. Update: cd ~/rhdp-publishing-house-skills && git pull"
    → STOP — do not continue the session

All versions OK → continue to normal session flow.
```

### Plugin version location
Each plugin's version lives in its `.claude-plugin/plugin.json`:
```json
{
  "name": "agnosticv",
  "version": "2.15.0",
  ...
}
```

The orchestrator finds the plugin dir by searching the pluginDirectories configured in Claude Code settings, or by reading a well-known path (e.g., `~/rhdp-publishing-house-skills/agnosticv/.claude-plugin/plugin.json`).

---

## Release Cadence: All Plugins Together

Since all 4 plugins live in one repo, they release together. A `git push` to main that updates `showroom/skills/create-lab/SKILL.md` also ships the current `agnosticv` and `ftl` as-is.

**Implication:** Version numbers in each plugin.json only bump when that plugin's files change. But the release (git tag) covers all plugins simultaneously.

### Version bump rules
| Change type | Which plugin bumps? | Example |
|------------|-------------------|---------|
| showroom skill fix | showroom only (minor bump) | showroom: 2.14.1 |
| agnosticv new agent | agnosticv only (minor bump) | agnosticv: 2.15.1 |
| PH orchestrator fix | rhdp-publishing-house only | rhdp-publishing-house: 0.2.1 |
| Breaking change to ph_payload | All affected plugins | showroom: 2.15.0, agnosticv: 2.16.0 |

### Git tagging
Tags are on the repo level (not per-plugin):
```
v1.0.0 — initial consolidated release
v1.1.0 — showroom create-lab improvements
v1.2.0 — agnosticv ocp-infra-checker update
```

Users on `main` always get latest. Users who need stability can pin to a tag.

---

## What Happens to rhdp-skills-marketplace

After consolidation, `rhdp-skills-marketplace` is frozen for the 3 migrated plugins:

| Plugin | Status after migration |
|--------|----------------------|
| showroom | Frozen at v2.14.x — no new features. README points to PH. |
| agnosticv | Frozen at v2.15.x — no new features. README points to PH. |
| ftl | Frozen at current version. README points to PH. |
| health | Active — continues to evolve in marketplace |
| sandbox-cli | Active — continues to evolve in marketplace |

Marketplace README updated:
```markdown
## showroom, agnosticv, ftl skills have moved

These plugins are now part of Publishing House:
  git clone git@github.com:rhpds/rhdp-publishing-house-skills.git

The marketplace continues to serve: health, sandbox-cli.
```

---

## Dependency Discovery: How Does PH Know Where the Plugins Are?

When the orchestrator needs to read a plugin's version file, it needs to know where the skills are installed. Two approaches:

### Option A: Well-known path (recommended)
Convention: users always clone to `~/rhdp-publishing-house-skills`. Orchestrator reads from there directly.
- Pros: Simple, no configuration needed
- Cons: Breaks if user clones to a different path

### Option B: Claude Code plugin context
Claude Code injects the plugin dir path into the skill execution context. The orchestrator can use this to derive the path of sibling plugins.
- Pros: Works regardless of install path
- Cons: Requires understanding Claude Code plugin context injection (not yet documented)

### Option C: Config file
User creates `~/.config/rhdp/config.yaml`:
```yaml
skills_dir: ~/rhdp-publishing-house-skills
```
Orchestrator reads this to find plugin dirs.
- Pros: Flexible, user-controlled
- Cons: Extra config step for users

**Recommendation:** Start with Option A (well-known path). Document it clearly. Revisit if users report path issues.

---

## Edge Cases

### If plugins are renamed during consolidation (Option B)

See architecture spec for full rename steps. From a distribution perspective:
- CHANGELOG entry must document the breaking name change
- Users on old marketplace who upgrade to new PH-consolidated package must update any personal scripts or workflows that call old skill names
- The version gate should surface a message when old names are not found (rather than silently failing)

### User has both marketplace AND PH installed
Both `showroom` plugins are installed (one from each repo). Claude Code loads the LAST plugin.json it finds if names clash. This is **undefined behavior** — the wrong showroom plugin could be active.

**Resolution:** When PH is installed, users MUST remove the marketplace `--plugin-dir` from their Claude Code settings. Orchestrator warns if both are detected:
```
⚠️  Multiple 'showroom' plugins detected. 
    Remove rhdp-skills-marketplace from your Claude Code pluginDirectories.
```

### User only has marketplace (no PH)
Showroom and agnosticv skills still work as before — marketplace is not removed, just frozen. 

### PH auto-updates during a session
If a user runs `git pull` while a PH session is in progress, the skill files on disk change mid-session. Claude Code reads skill files at invocation time (not cached), so the next skill invocation uses the new version. This is generally safe but could cause subtle issues during automation phase 7b if the agnosticv API changes.

**Recommendation:** Document: "Do not pull during an active PH session."
