# Scaffolder Templates

## Publishing House Content Project

**Location:** `templates/publishing-house-project/template.yaml`
**Template name:** `publishing-house-project`
**Title:** Publishing House Content Project

### Parameters

#### Page 1: Project Details

| Parameter | Type | Default | Constraints | Required |
|---|---|---|---|---|
| `project_name` | string | — | `^[a-z0-9-]+$` | yes |
| `project_description` | string (textarea) | — | — | yes |
| `content_type` | string | `lab` | enum: `lab`, `demo` | yes |
| `deployment_mode` | string | `rhdp_published` | enum: `rhdp_published`, `self_published` | yes |
| `tags` | array of string | — | per item: `^[a-zA-Z0-9_-]+$` | no |

#### Page 2: GitHub Collaborators

| Parameter | Type | Default | Constraints | Required |
|---|---|---|---|---|
| `github_users` | array of {user, access} | — | minItems: 1, access default: `write` | yes |

#### Page 3: Initiative & Content Format

| Parameter | Type | Default | Constraints | Required |
|---|---|---|---|---|
| `initiative_key` | string | `rh1_2027` | enum: `rh1_2027`, `summit_2027`, `none` | yes |
| `showroom_type` | string | `classic` | enum: `classic`, `zero_touch` | yes |
| `automation_type` | string | `ansible` | enum: `ansible`, `gitops`, `both` | yes |

### Steps

| # | ID | Action | What It Does |
|---|---|---|---|
| 1 | `check-catalog` | `catalog:fetch` | Check if project name already exists in catalog |
| 2 | `generate-skeleton` | `fetch:template` | Render skeleton directory with template values |
| 3 | `timestamp` | `publishing-house:timestamp` | Set `ph.rhdp.io/created-at` annotation |
| 4 | `create-and-push` | `publishing-house:create-github-repo` | Create repo from template repo, overlay skeleton, commit+push, invite collaborators |
| 5 | `trigger-workflow` | `http:backstage:request` | POST to Central API `/projects/{name}` to start SonataFlow workflow |
| 6 | `register` | `catalog:register` | Register in RHDH catalog |

Steps 2-6 are conditional: only run if step 1 finds no existing entity.

### Skeleton Files

| File | Purpose |
|---|---|
| `.claude/settings.json` | Claude Code permissions (python, git, read/edit PH dirs) |
| `.devfile.yaml` | DevSpaces workspace config (4Gi mem, 2 CPU, postStart: install Claude CLI/ext + skills + auth) |
| `catalog-info.yaml` | Backstage Component (type: content, system: publishing-house, ph.rhdp.io/* annotations) |
| `publishing-house/spec.yaml` | Full spec template with all fields (project, spec, development, compliance, tracking, approval_checklist) |
| `README.md` | Basic project readme |

### Output Links

- Open Repository (GitHub)
- View in Catalog (RHDH)
- Open in DevSpaces

---

## Publishing House Migration

**Location:** `templates/publishing-house-migration/template.yaml`
**Template name:** `publishing-house-migration`

### Differences from Project Template

| Aspect | Project | Migration |
|---|---|---|
| Extra parameter | — | `source_repo` (string, pattern `^https://github\.com/.+/.+$`) |
| `intake_type` | `new` | `migration` |
| Repo creation action | `publishing-house:create-github-repo` | `publishing-house:import-github-repo` (copies content/ from source) |
| catalog-info.yaml | Standard annotations | Adds `ph.rhdp.io/migrated-repo` annotation + `migration` tag |

---

## Template Repo (`rhdp-publishing-house-template`)

The GitHub template repository that the scaffolder clones from. Contains the full project structure that gets overlaid with skeleton values.

### Key Files

| File | Purpose |
|---|---|
| `scaffold.py` | Lab pattern selector (3 patterns) |
| `CLAUDE.md` | Project-level Claude instructions |
| `hooks/pre-tool-use.sh` | Blocks specific tools from PH context |
| `setup-claude-hooks.sh` | Copies settings template |
| `publishing-house/worklog.yaml` | Empty worklog template |
| `publishing-house/spec/design.md` | Design doc template (11 sections with placeholders) |
| `publishing-house/spec/module-outline-template.md` | Per-module outline template |
| `publishing-house/spec/automation-manifest.yaml` | Automation config template |
| `publishing-house/spec/modules/.gitkeep` | Empty modules directory |
| `publishing-house/decisions/.gitkeep` | Decisions directory |
| `publishing-house/reviews/.gitkeep` | Reviews directory |
| `publishing-house/tools/requirements.txt` | `pyyaml>=6.0` |

### Scaffold Patterns

| Pattern | showroom_type | UI Bundle | Extras |
|---|---|---|---|
| `agd-open` | classic | rhdp_showroom_theme v2.0.3 | podman-compose.yaml |
| `agd-guided` | guided | nookbag-bundle v0.0.3 | runtime-automation (solve/validate per module) |
| `zt-guided` | guided (zero_touch) | nookbag-bundle v0.0.3 | runtime-automation, setup-automation, config (instances/networks/firewall) |

### Automation Scaffolds (optional `--automation` flag)

| Type | What It Creates |
|---|---|
| `ansible/` | Starter Ansible collection with galaxy.yml, example role |
| `gitops/bootstrap-infra/` | Helm chart with test namespace |
| `gitops/bootstrap-tenant/` | Per-user namespace + RBAC (only if `--topology shared-cluster`) |

---

## Catalog Entities

| File | Kind | Name | Purpose |
|---|---|---|---|
| `org-entities.yaml` | System | publishing-house | System grouping |
| `org-entities.yaml` | Group | rhdp-team | Owner group |
| `all-locations.yaml` | Location | publishing-house-entities | Top-level pointer |
| `template-locations.yaml` | Location | publishing-house-templates | Points to template.yaml files |
| `component-locations.yaml` | Location | publishing-house-components | Dynamic (empty targets) |

---

## spec.yaml Schema

The spec.yaml template defines the full project specification schema:

```yaml
project:
  slug: ""                    # repo name, set by scaffolder
  owner_email: ""             # SSO email, set by scaffolder
  content_type: ""            # lab | demo
  deployment_mode: ""         # rhdp_published | self_published
  initiative_key: ""          # rh1_2027 | summit_2027 | none
  showroom_type: ""           # classic | zero_touch
  intake_type: ""             # new | migration
  automation_type: ""         # ansible | gitops | both
  description: ""             # project description
  jira_ticket: ""             # set by workflow
  workflow_id: ""             # set by workflow

spec:
  title: ""
  learning_objectives: []
  modules: []                 # [{id, title, duration_min, status}]
  environment:
    platform: ""              # ocp | rhel-vms
    topology: ""              # shared-cluster | per-student | cnv-pool
    cloud_provider: cnv       # cnv | aws
    max_concurrent_users: null
    ocp_version: ""           # e.g. 4.20 (ocp only)
    cluster_type: ""          # sno | multinode (ocp only)
    control_plane_instance_count: null
    control_plane_cpu: null
    control_plane_ram_gb: null
    worker_count: null        # optional
    worker_cpu: null          # optional (required if worker_count > 0)
    worker_ram_gb: null       # optional (required if worker_count > 0)
    worker_disk_gb: null      # optional (required if worker_count > 0)
    vms_per_student: []       # rhel-vms only: [{role, count, cpu, ram_gb, disk_gb, os}]
    aap_version: ""           # required if AAP in products
    ai_requirement: ""        # maas | gpu | none
    ai_model_tier: ""         # open-source | frontier
    ai_model_name: ""
    ai_justification: ""      # required if frontier or gpu
    non_ga_products: []
    non_ga_access_plan: ""
    external_services: []
    gpu_nodes: 0
    gpu_type: ""              # required if gpu_nodes > 0
  duration_hours: null
  audience: ""                # beginner | intermediate | advanced

development:
  automation:
    ansible:
      status: not_started     # if automation_type includes ansible
    gitops:
      status: not_started     # if automation_type includes gitops
  e2e:
    status: not_started
  healthCheck:
    status: not_started

compliance:
  last_hard_check: null
  hard_result: null

tracking:
  paused: false
  pause_reason: null

approval_checklist:
  content:
    prerequisites_verifiable: null
    assessment_strategy: ""
    catalog_gap: ""
    design_overview: ""
    module_summaries: []
    rcars_overlap_pct: null
    rcars_top_matches: []
    rejections: []
  infra:
    peak_environments: null
    cost_per_run_est: ""
    provisioning_time_est: ""
    agnosticv_base_ci: ""
    approved_by: ""
    rejections: []
```
