# Automation Scaffolding Spec

## Purpose

This spec drives scaffolding of an AgnosticD v2 Ansible collection, roles, and workloads
playbook under the `automation/` directory of any RHDP Publishing House project.

To use: copy this repo, update the `## Inputs` section below with your project's values,
and hand the file to the automation scaffolding agent.

All conventions follow AgnosticD v2 style as established in
`agnosticd.cloud_provider_openshift_cnv` and `agnosticd.cloud_vm_workloads`.

---

## Inputs

Replace every `<placeholder>` before running the scaffolding agent.

```yaml
inputs:
  # Galaxy namespace — always "agnosticd" for AgnosticD v2 collections
  collection_namespace: "agnosticd"

  # Collection name — snake_case, describes the workload domain
  # Examples: cloud_vm_workloads, leapp_o_matic, aap_demo_setup
  collection_name: "<your_collection_name>"

  # Semantic version — start at 1.0.0
  collection_version: "1.0.0"

  # Author line for galaxy.yml and role meta files
  # Format: "Full Name <email@example.com>"
  collection_author: "<Full Name <email@redhat.com>>"

  # Company field for role meta/main.yaml
  collection_company: "Red Hat"

  # License — GPL-2.0-or-later matches all AgnosticD v2 collections
  collection_license: "GPL-2.0-or-later"

  # SCM URL of this repo
  collection_repository: "<https://github.com/rhpds/<repo-name>>"

  # Roles to generate.
  # Each entry creates a full role skeleton under automation/roles/.
  # - name:        snake_case role name; will also be the directory name
  # - description: one sentence — what this role does
  # - host_group:  AgnosticD v2 inventory group this role targets
  #                common values: controllers, nodes, bastions, satellites
  roles:
    - name: "<role_name_1>"
      description: "<What this role does>"
      host_group: "<controllers|nodes|bastions|satellites>"

    - name: "<role_name_2>"
      description: "<What this role does>"
      host_group: "<controllers|nodes|bastions|satellites>"

    # Add more roles as needed

  # Playbook style — do not change this value.
  # AgnosticD v2 always uses a single workloads.yml dispatcher.
  playbooks:
    - name: workloads.yml
      style: agnosticd_v2_workloads
```

---

## Output Layout

The scaffolding agent writes this tree under `automation/`.
The collection root lives directly under `automation/` — the directory IS the collection;
no extra `collections/ansible_collections/` nesting is used.

```
automation/
├── galaxy.yml
├── README.adoc
├── meta/
│   └── runtime.yml
├── plugins/
│   └── README.md
└── roles/
    └── <role_name>/               # one directory per entry in inputs.roles
        ├── .yamllint
        ├── defaults/
        │   └── main.yaml
        ├── meta/
        │   └── main.yaml
        ├── tasks/
        │   ├── main.yaml          # ACTION dispatcher — do not modify
        │   ├── workload.yaml      # provision logic
        │   └── remove_workload.yaml
        └── README.adoc

automation/playbooks/
└── workloads.yml
```

---

## Artifact Content Rules

### `galaxy.yml`

Line 1 must be the SPDX header. All optional fields must be present (commented or empty)
to match the AgnosticD v2 template.

```yaml
#SPDX-License-Identifier: MIT-0
### REQUIRED
namespace: agnosticd
name: <collection_name>
version: <collection_version>
readme: README.adoc
authors:
- <collection_author>

### OPTIONAL but strongly recommended
description: <one-line description of what this collection does>
license:
- GPL-2.0-or-later
license_file: ''
tags: []
dependencies: {}
repository: <collection_repository>
documentation: ''
homepage: ''
issues: ''
build_ignore: []
```

### `meta/runtime.yml`

```yaml
---
requires_ansible: ">=2.14.0"
```

### Role `.yamllint`

Identical content for every role — do not vary per role.

```yaml
---
extends: default

rules:
  comments:
    require-starting-space: false
    min-spaces-from-content: 1
  comments-indentation: disable
  indentation:
    indent-sequences: consistent
```

### Role `meta/main.yaml`

`galaxy_info` block only. Do not add a `collections:` block unless the role explicitly
requires a non-builtin collection module.

```yaml
---
galaxy_info:
  author: <collection_author>
  description: |
    <role.description>
  company: Red Hat
  version: 1.0.0
  license: GPL-2.0-or-later
  min_ansible_version: "2.14"
  platforms:
    - name: EL
      versions:
        - 8
        - 9
        - 10
  galaxy_tags: []
dependencies: []
```

### Role `defaults/main.yaml`

All variable names **must** be prefixed with the role name: `<role_name>_<variable>`.
This is a hard AgnosticD v2 rule — no exceptions.

```yaml
---
# Customization variables for the <role_name> role.
#
# All variables are prefixed with the role name: <role_name>_<variable>.
# Override these in AgnosticV common.yaml or dev.yaml.

# <describe variable 1>
<role_name>_variable_1: "<default_value>"

# <describe variable 2>
<role_name>_variable_2: "<default_value>"
```

### Role `tasks/main.yaml` — ACTION dispatcher

This file is the role entry point. It must contain **only** `include_tasks` calls
branching on `ACTION`. Never put real task logic here.

```yaml
---
# --------------------------------------------------
# Do not modify this file
# --------------------------------------------------
- name: Running <role_name> provision tasks
  when: ACTION == "provision"
  ansible.builtin.include_tasks: workload.yaml

- name: Running <role_name> removal tasks
  when: ACTION == "destroy"
  ansible.builtin.include_tasks: remove_workload.yaml
```

### Role `tasks/workload.yaml` — provision logic

```yaml
---
# -------------------------------------------------------------------------
# Implement <role_name> provision tasks here
# -------------------------------------------------------------------------

- name: Placeholder — <role_name> provision not yet implemented
  ansible.builtin.debug:
    msg: "<role_name> provision tasks go here"
```

### Role `tasks/remove_workload.yaml` — destroy logic

```yaml
---
# ------------------------------------------
# Implement <role_name> removal tasks here
# ------------------------------------------

- name: Deprovision <role_name>
  ansible.builtin.debug:
    msg: "Nothing to deprovision for <role_name>."
```

### Role `README.adoc`

```asciidoc
= Role: <role_name>

<role.description>

== Requirements

* Ansible >= 2.14
* Target hosts: <role.host_group>

== Role Variables

Defined in `defaults/main.yaml`. All variables are prefixed with `<role_name>_`.

[cols="1,1,2"]
|===
|Variable |Default |Description

|`<role_name>_variable_1`
|`<default>`
|<Description>
|===

== Example AgnosticV Usage

[source,yaml]
----
_workloads_:
  <role.host_group>:
    - agnosticd.<collection_name>.<role_name>
----
```

---

## Playbook: `playbooks/workloads.yml`

AgnosticD v2 uses a single `workloads.yml` that iterates `_workloads_.<host_group>` lists
and calls `ansible.builtin.include_role` per group. Roles are wired in via AgnosticV
`common.yaml` — not hardcoded in the playbook.

The scaffolding agent generates one play per distinct `host_group` value found across
all entries in `inputs.roles`. The template for each play is:

```yaml
---
- name: Install <collection_name> workloads on <host_group>
  hosts: <host_group>
  gather_facts: false
  become: true
  tasks:
  - name: Deploy <collection_name> workloads on <host_group>
    when: _workloads_.<host_group> | default("") | length > 0
    ansible.builtin.include_role:
      name: "{{ __<host_group> }}"
    vars:
      ACTION: provision
    loop: "{{ _workloads_.<host_group> }}"
    loop_control:
      loop_var: __<host_group>
```

### AgnosticV wiring (in `common.yaml` — not generated, shown for reference)

After scaffolding, wire roles in AgnosticV using their FQCN:

```yaml
_workloads_:
  <host_group_1>:
    - agnosticd.<collection_name>.<role_name_1>
  <host_group_2>:
    - agnosticd.<collection_name>.<role_name_2>
    - agnosticd.<collection_name>.<role_name_3>
```

---

## Conditional Logic

| Condition | Behaviour |
|-----------|-----------|
| `roles` list is empty | Skip role creation; emit a warning and continue |
| `playbooks` list is empty | Skip playbook creation; emit a warning and continue |
| A `host_group` value is not a known AgnosticD v2 group | Emit a warning; scaffold the role; add a comment in `workloads.yml` |
| A role name collides with an existing directory under `automation/roles/` | Skip that role; log a conflict; do not overwrite |
| `collection_namespace` is not `agnosticd` | Emit a warning: "AgnosticD v2 convention requires namespace: agnosticd" |
| `collection_namespace` or `collection_name` contains a `<placeholder>` literal | Abort with: "Inputs not filled in — replace all <placeholder> values before running" |
| `collection_namespace` or `collection_name` is missing | Abort with a clear error |

---

## Validation Checklist (post-scaffold)

The scaffolding agent runs these checks after writing all files:

- [ ] `galaxy.yml` line 1 is `#SPDX-License-Identifier: MIT-0`
- [ ] `galaxy.yml` parses as valid YAML with `namespace: agnosticd`, non-empty `name` and `version`, `license: [GPL-2.0-or-later]`
- [ ] Every role has exactly: `defaults/main.yaml`, `tasks/main.yaml`, `tasks/workload.yaml`, `tasks/remove_workload.yaml`, `meta/main.yaml`, `README.adoc`, `.yamllint`
- [ ] No role has `vars/main.yaml` or `handlers/main.yaml` (omit unless the role explicitly needs them)
- [ ] All variable names in every `defaults/main.yaml` start with `<role_name>_`
- [ ] `tasks/main.yaml` in every role contains only `include_tasks` calls branching on `ACTION` — no real task logic
- [ ] `playbooks/workloads.yml` has one play per distinct `host_group` referenced across all roles
- [ ] All FQCN references use `agnosticd.<collection_name>.<role_name>`
- [ ] All generated YAML files use 2-space indentation and start with `---`
- [ ] No generated file is empty
- [ ] The scaffolding agent does **not** commit anything

---

## AgnosticD v2 Convention Reference

| Topic | Convention |
|-------|-----------|
| Galaxy namespace | always `agnosticd` |
| License | `GPL-2.0-or-later` |
| `galaxy.yml` line 1 | `#SPDX-License-Identifier: MIT-0` |
| File extension | `.yaml` (not `.yml`) |
| Role README format | AsciiDoc (`.adoc`) |
| Role entry point | `tasks/main.yaml` dispatches on `ACTION` only |
| Provision logic | `tasks/workload.yaml` |
| Destroy logic | `tasks/remove_workload.yaml` |
| Variable naming | `<role_name>_<variable>` — prefix is mandatory |
| Role invocation | `ansible.builtin.include_role` inside `tasks:` with `loop` over `_workloads_.<group>` |
| Per-phase playbooks | not used — single `workloads.yml` per config |
| Role wiring | AgnosticV `common.yaml` under `_workloads_`, not in the playbook |
| `vars/`, `handlers/` dirs | omit unless explicitly needed |
| `.yamllint` | one per role, identical content |
