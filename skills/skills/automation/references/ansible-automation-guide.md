# Ansible Automation Guide

How to create Ansible collections that automate RHDP lab/demo environments.

## Collection Structure

```
rhpds.<collection_name>/
├── galaxy.yml
└── roles/
    └── <role_name>/
        ├── defaults/main.yml
        ├── meta/main.yml
        ├── tasks/
        │   ├── main.yml
        │   ├── workload.yml
        │   └── remove_workload.yml
        ├── templates/*.yaml.j2
        └── README.md
```

## Role Entry Point (tasks/main.yml)

```yaml
- name: Run workload
  when: ACTION == "create" or ACTION == "provision"
  ansible.builtin.include_tasks: workload.yml

- name: Remove workload
  when: ACTION == "destroy" or ACTION == "remove"
  ansible.builtin.include_tasks: remove_workload.yml
```

## Variable Conventions

All variables use a prefix matching the role name:

```yaml
# Role: ocp4_workload_my_lab
ocp4_workload_my_lab_namespace: my-lab
ocp4_workload_my_lab_app_name: my-application
ocp4_workload_my_lab_image: quay.io/org/app:v1.2.3  # Always pin tags
```

## Return User Information

```yaml
- name: Set user info for the lab
  agnosticd.core.agnosticd_user_info:
    data:
      app_url: "https://my-app-{{ my_role_namespace }}.{{ deployer.domain }}"
      app_user: "{{ my_role_user }}"
      app_password: "{{ my_role_password }}"
```

## AgnosticV Integration

```yaml
requirements_content:
  collections:
    - name: https://github.com/rhpds/<collection-repo>.git
      type: git
      version: main

workloads:
  - agnosticd.core_workloads.ocp4_workload_authentication_htpasswd
  - rhpds.<collection_name>.<role_name>
  - agnosticd.core_workloads.ocp4_workload_showroom  # always last
```

## What to Automate vs What the Learner Does

- **Automate:** Operators the learner will USE, apps the learner will CONFIGURE, sample data, RBAC setup
- **Do NOT automate:** Steps where the learner runs commands, resources the learner creates/modifies
