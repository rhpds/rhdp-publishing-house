# Spec Update Rules

- **spec.yaml is the structured data file** — it contains project metadata and spec fields.
- **design.md is the narrative spec** — it contains the full design document.
- **Never delete completed phase data** — it's the project's audit trail.
- **Preserve user-entered data** — don't overwrite fields unless the agent explicitly updated them.
- **Never modify `system.central`** — this is set by the RHDH template and should not be changed.
- **`project.jira_ticket` is set from workflow data** — the Jira epic is created at workflow start. The orchestrator syncs it to spec.yaml, and ph-intake.py updates it if missing. Do not set it manually.
- **Stage comes from Central API** — do not store or manage stage locally.
