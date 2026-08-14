# Intake

Intake is the first stage of the Publishing House lifecycle — where you scope out what you're building and produce the spec artifacts (`design.md`, `spec.yaml`, module outlines) that everything else in the lifecycle builds on. There are two paths, depending on whether you're starting fresh or bringing in an existing repo.

| | New Project | Migration |
|---|---|---|
| **Use when** | You're starting from an idea, doc, or Jira ticket | You already have a working Showroom repo |
| **Template** | Publishing House Content Project | Publishing House Migration |
| **Discovery** | Conversational — Claude asks questions and builds the spec with you | Automated — Claude reads your existing `content/`, `site.yml`, and `nav.adoc` and reverse-engineers the spec |
| **Design doc & module outlines** | Drafted from your discovery answers | Derived from your existing content |

- [New Project Intake](intake-new.md) — walks through logging in, creating a project from the template, and the conversational discovery.
- [Migration Intake](intake-migration.md) — walks through importing an existing Showroom repo and generating the spec from its content.

Both paths converge after intake: RCARS vetting, infrastructure confirmation, and submission for review work the same way regardless of which one you took.

---

## Choosing a Path

1. **Do you have a working Showroom repo already?** → [Migration Intake](intake-migration.md)
2. **Are you starting from scratch — an idea, a doc, or a Jira ticket?** → [New Project Intake](intake-new.md)
