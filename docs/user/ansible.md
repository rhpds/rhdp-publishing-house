# Ansible Automation

Publishing House provides an `ansible-helper` skill that creates and imports Ansible roles into your project's collection. You can also build roles manually — the skill is optional.

See [Development](development.md) for how Ansible Automation fits into the overall development workflow.

---

## Overview

Ansible automation in RHDP uses an **Ansible Collection** structure inside `automation/ansible/`. Each role in the collection handles a specific piece of lab provisioning — deploying an application, configuring a service, creating user environments, etc. The roles are called by AgnosticD v2 workloads during lab deployment.

---

## Directory structure

The automation scaffolding (created by the development skill's config-helper) produces this layout:

```
automation/ansible/
├── galaxy.yml
├── README.md
├── meta/
│   └── runtime.yml
└── roles/
    └── <role_name>/
        ├── tasks/main.yml
        ├── defaults/main.yml
        ├── meta/main.yml
        └── README.md
```

Optional directories can be added per role as needed:

- `vars/main.yml` — role-internal variables not exposed to callers
- `handlers/main.yml` — notification handlers

---

## Using the Ansible helper skill

### From the development dashboard

Select **Ansible Automation** from the development dashboard, then choose **Use Ansible helper**. Claude dispatches to the `ansible-helper` skill, which offers two paths:

| # | Path | What it does |
|---|------|-------------|
| 1 | **New role** | Creates a fresh Ansible role skeleton from scratch |
| 2 | **Import from Git** | Pulls existing roles from a Git repository into your collection |

### Path 1 — New role

Claude walks you through:

1. **Role name** — provide a snake_case name (e.g., `configure_aap`, `deploy_nginx`)
2. **Role purpose** — describe what the role should configure, deploy, or manage
3. **Duplicate check** — if a role with that name already exists, Claude asks whether to continue or pick a different name
4. **Scaffold** — creates the role skeleton with `tasks/main.yml`, `defaults/main.yml`, `meta/main.yml`, and `README.md`
5. **Write tasks** — optionally, Claude writes the actual task logic based on your description. Give as much detail as possible for better results. You can also decline and write tasks yourself.
6. **Report** — prints a summary of files created

You can repeat this to add multiple roles in one session.

### Path 2 — Import from Git

Claude handles three repo layouts automatically:

| Repo type | Detection | How roles are found |
|---|---|---|
| **Ansible Collection** | `galaxy.yml` at repo root | Subdirectories of `roles/` |
| **Single role** | `tasks/main.yml` at repo root | The entire repo is one role |
| **Multi-role monorepo** | Neither of the above | Directories containing `tasks/main.yml` |

The flow:

1. **Provide a Git URL** — Claude clones the repo
2. **Select roles** — Claude lists all discovered roles; type `all` or specific numbers to import
3. **Duplicate check** — for any role that already exists, choose overwrite, skip, or rename
4. **Copy and update** — roles are copied into `automation/ansible/roles/`, and `meta/main.yml` is updated with your author email
5. **Report** — prints a summary of imported roles

You can import from multiple repositories in one session.

### Standalone mode

The skill also works outside of Publishing House projects:

```
/rhdp-publishing-house:ansible-helper
```

In standalone mode, the pre-flight and workflow checks are skipped. The skill verifies that `automation/ansible/` exists and proceeds directly.

---

## Collection conventions

### galaxy.yml

The collection identity file at `automation/ansible/galaxy.yml`:

```yaml
namespace: <project_slug_underscored>
name: ansible
version: 1.0.0
authors:
- owner@redhat.com
description: Ansible collection for <project-slug> lab automation
license:
- GPL-2.0-or-later
```

The namespace is derived from your project slug with hyphens converted to underscores.

### Role naming

- Use **snake_case** for role names (e.g., `configure_aap`, `deploy_gitea`, `setup_users`)
- Hyphens and spaces are automatically converted to underscores
- Prefix with a verb that describes the action: `configure_`, `deploy_`, `setup_`, `install_`

### Role metadata

Every role should have a `meta/main.yml` with author and description:

```yaml
galaxy_info:
  author: owner@redhat.com
  description: Configures AAP controller for the lab environment
  license: GPL-2.0-or-later
  min_ansible_version: 2.9
  galaxy_tags: []
dependencies: []
```

### Role variables

Expose configurable values in `defaults/main.yml`. Document them in the role's `README.md`:

```markdown
## Role Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `aap_admin_password` | `redhat` | Admin password for the AAP controller |
| `aap_version` | `2.6` | AAP version to install |
```

---

## Manual setup

If you prefer to build Ansible automation without the skill:

1. Select **Ansible Automation** from the development dashboard, choose **Do it myself**
2. Create roles in `automation/ansible/roles/` following the structure above
3. Ensure each role has `tasks/main.yml`, `defaults/main.yml`, and `meta/main.yml`
4. Come back to the dashboard and mark Ansible automation complete when done

You can also use `ansible-galaxy` directly:

```bash
# Initialize a new role
cd automation/ansible/roles
ansible-galaxy role init my_new_role
```

---

## AgnosticV integration

Once your collection and roles are ready, include the collection in your AgnosticV catalog item's `common.yaml` using `requirements_content`. Since the collection lives in a subdirectory of your project repo, use the `#/path` fragment syntax to point to it:

```yaml
requirements_content:
  collections:
  - name: https://github.com/rhpds/<your-repo>.git#/automation/ansible
    type: git
    version: main
```

The `#/automation/ansible` fragment tells `ansible-galaxy` to install from that subdirectory rather than the repo root. The `version` field is the git ref (branch, tag, or commit SHA).

You can then reference your roles as workloads in your AgnosticV catalog item alongside core workloads:

```yaml
workloads:
  - agnosticd.core_workloads.ocp4_workload_authorino
  - <namespace>.ansible.<role_name>
```

Where `<namespace>` is the namespace from your `galaxy.yml` (your project slug with hyphens converted to underscores).

---

## Tips

- **One role per concern.** Each role should do one thing well — deploy an operator, configure a service, set up user environments. This makes roles reusable across projects.
- **Use defaults liberally.** Put all configurable values in `defaults/main.yml` so callers can override them without modifying the role.
- **Import before writing.** If you have existing roles in another repo, import them first, then customize. It's faster than starting from scratch.
- **Test locally.** Use `ansible-playbook --check` or a sandbox environment to validate your roles before marking automation complete.
