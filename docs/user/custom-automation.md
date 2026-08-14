# Custom Ansible Automation

The template ships a starter Ansible collection at `.scaffolds/automation/ansible/`
in [rhdp-publishing-house-template](https://github.com/rhpds/rhdp-publishing-house-template)
— a valid, installable collection with a single no-op `example` role. It's the base
you build your own roles on top of, not real automation itself.

This is optional. Skip it entirely if your project doesn't need custom Ansible
automation beyond the base infrastructure.

## Copy it out before scaffolding

`scaffold.py` deletes the entire `.scaffolds/` directory when it runs — including
`.scaffolds/automation/`. If you want the starter collection:

- Copy `.scaffolds/automation/ansible/` to `automation/ansible/` (or wherever you
  keep your automation code) **before** running `python scaffold.py`, or
- If you've already scaffolded, fetch that directory from the
  `rhdp-publishing-house-template` repository directly and add it to your project.

## Fill in the placeholders

`galaxy.yml` and the role's `meta/main.yml` use literal `<placeholder>` values —
the collection won't install cleanly until you replace them:

```yaml
---
namespace: "<your_namespace>"
name: "<your_collection_name>"
version: "1.0.0"
readme: README.md
authors:
  - "<Your Name> <you@example.com>"
description: "Starter collection for this project's custom Ansible automation."
license: []
repository: "<https://github.com/rhpds/your-project-repo>"
```

`namespace` and `name` become the prefix for every role's fully qualified name —
`<namespace>.<name>.<role_name>`. Once you're happy with the content, commit it
and tag a release:

```bash
git tag v1.0.0
git push --tags
```

## Wire it into AgnosticV

This collection is never published to Ansible Galaxy — it's referenced straight
from your project's git repository using AgnosticV's `requirements_content`:

```yaml
requirements_content:
  collections:
  - name: https://github.com/rhpds/<your-project-repo>.git#/automation/ansible
    type: git
    version: "v1.0.0"
```

- The `#/automation/ansible` fragment is **required**, not optional, here. Ansible
  only auto-discovers a collection's `galaxy.yml` at the top level of a repository
  or one level deep — `automation/ansible/` is two levels deep, so the exact
  subdirectory has to be spelled out in the URI. See the
  [Ansible collections install docs](https://docs.ansible.com/projects/ansible/latest/collections_guide/collections_installing.html)
  for the full rules.
- `version` accepts any git ref — branch, tag, or commit SHA. Point at a branch
  (e.g. `main`) while you're iterating, then pin to a tag once the collection is
  stable so automation runs don't shift under you.

Once installed, reference roles by their fully qualified name:

```yaml
- name: Run my custom role
  ansible.builtin.include_role:
    name: <your_namespace>.<your_collection_name>.example
```

## Adding roles

```bash
ansible-galaxy role init --init-path roles/ my_role_name
```

Replace or delete the placeholder `example` role once you've added real ones.
