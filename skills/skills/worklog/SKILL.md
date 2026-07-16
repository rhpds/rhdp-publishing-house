---
name: rhdp-publishing-house:worklog
description: This skill should be used when the user asks to "leave a note", "what's outstanding", "worklog", "resolve item", "what did we do last session", "add a worklog entry", "squash the worklog", or "session summary". It manages the human-context layer in publishing-house/worklog.yaml.
---

---
context: main
model: claude-sonnet-4-6
---

# RHDP Publishing House — Worklog Manager

You manage `publishing-house/worklog.yaml` — the human-context layer that bridges
sessions, people, and decisions. This is NOT a task tracker (the spec tracks
structured progress). The worklog captures what falls between the cracks: decisions
pending, things to check with people, handoff notes, session summaries.

## Before Starting

1. Read `publishing-house/worklog.yaml` — if it doesn't exist, create it with an empty `entries: []` list
2. Read `catalog-info.yaml` for project name and owner

## Commands

### View Open Items

When the user asks "what's outstanding?" or "worklog":

1. Read `worklog.yaml`
2. Filter entries with `status: open`
3. Present them grouped by type (decisions first, then actions, then notes)

### Add a Note

When the user says "leave a note about X" or "add to worklog":

1. Take the user's terse input
2. Expand it into a readable entry — add enough context for someone else to understand it without follow-up questions
3. Classify the type: `note`, `decision`, `handoff`, or `action`
4. Generate a unique ID: `YYYY-MM-DD-NNN`
5. Write the entry to `worklog.yaml`
6. Commit and push

### Resolve an Item

When the user says "resolve item X" or "that's done":

1. Find the entry by ID or by content match
2. Set `status: resolved`, `resolved_at: <now>`, `resolved_by: <github_username>`
3. Commit and push

### Session Summary

When the user says "session summary" or "I'm done for today":

1. Write a summary entry of what was accomplished this session
2. Note any open items for next session
3. Commit and push

### Squash Old Entries

When the user says "squash the worklog" or automatically when the file exceeds ~30 entries:

1. Find all resolved entries older than 1 week
2. Group them by week
3. Compress each week's resolved entries into a single summary entry
4. Remove the individual resolved entries that were squashed
5. Commit and push

## Worklog File Format

```yaml
# Publishing House Worklog
entries:
  - id: "2026-04-15-001"
    timestamp: "2026-04-15T14:30:00Z"
    author: "sborenst"
    status: open          # open | resolved
    type: decision        # note | decision | handoff | action | summary
    content: "Expanded, readable description of the item."
```

## What You Do NOT Do

- Do not duplicate spec state — if a module is in a certain stage, the Central API tracks that
- Do not create action items for PH phases — those are tracked elsewhere
- Do not store sensitive data (credentials, internal URLs) in worklog entries
