# Backstage Plugins

## publishing-house-workflows

**Version:** 1.20.5
**Plugin ID:** `ph-workflows`
**Location:** `plugins/publishing-house-workflows/`

### Pages

| Export | Component | Route | Purpose |
|---|---|---|---|
| `PhWorkflowsPage` | WorkflowListPage / WorkflowDetailPage | `/` (list), `/:workflowId` (detail) | Main workflow management UI |
| `PhDriftDashboardPage` | DriftDashboardPage | drift route ref | Drift detection across all workflows |
| `PhMaintenancePage` | MaintenancePage | maintenance route ref | Admin: delete projects, manage tokens |
| `PhHomeCard` | PhHomeCard | (card widget) | Homepage card showing workflow summary |

### WorkflowListPage

Displays all active workflows with:
- Business key, stage, owner, created date
- Drift status indicator
- Link to detail page

### WorkflowDetailPage

| Section | Component | What It Shows |
|---|---|---|
| Header | — | Project name, repo link, Jira link, owner |
| Progress | WorkflowProgress.tsx | Stage stepper with current stage highlighted |
| Environment | — | spec.environment card (platform, sizing, topology) |
| Approval Checklist | — | Content and infra review checklists |
| Actions | — | Stage-appropriate actions (approve, reject, message) |
| Drift | — | Drift status and approve button |

#### WorkflowProgress behavior

- Renders stages from `STAGE_ORDER`: intake, content_review, infra_review, env_setup, development, testing, published
- `env_setup` shown as "skipped" when `showroomType === 'zero_touch'` (line 80: `if (s === 'env_setup' && envSetupSkipped) return 'skipped'`)
- Stage derivation uses `deriveStage()` from `stageMapping.ts` which maps SonataFlow process node names to stage names

#### Stage Mapping (`stageMapping.ts`)

| SonataFlow Node | Derived Stage |
|---|---|
| IntakeCompleteEvent | intake |
| ContentReview | content_review |
| InfraReview | infra_review |
| EnvSetup | env_setup |
| Development | development |
| Testing | testing |
| Published | published |

### Dialogs

| Dialog | Triggered By | Purpose |
|---|---|---|
| RejectionDialog | Reject button (content/infra review) | Collects rejection reasons, calls reject endpoint |
| MessageDialog | Message button (review stages) | Posts messages between reviewer and author |
| DeleteDialog | Delete button (maintenance) | Confirms project deletion |
| RevokeDialog | Revoke button (maintenance) | Confirms token revocation |

### Hooks

| Hook | Purpose |
|---|---|
| `useUserGroups` | Resolves RBAC groups from signed token, controls action visibility |

### RBAC in UI

Actions are conditionally rendered based on user's group bitmask:
- Content review approve/reject: visible to `rhdp-content-review` (bit 1)
- Infra review approve/reject: visible to `rhdp-infra-review` (bit 2)
- Delete project: visible to `rhdp-administrators` (bit 8)
- Token management: visible to `rhdp-administrators` (bit 8)

---

## scaffolder-backend-module-publishing-house

**Version:** 1.1.5
**Location:** `plugins/scaffolder-backend-module-publishing-house/`

### Custom Scaffolder Actions

| Action ID | Inputs | What It Does |
|---|---|---|
| `publishing-house:create-github-repo` | repoUrl, templateRepo, description, defaultBranch, repoVisibility, gitCommitMessage, collaborators | Creates GitHub repo from template, overlays workspace files, commits, pushes, invites collaborators |
| `publishing-house:import-github-repo` | repoUrl, sourceRepo, templateRepo, description, defaultBranch, repoVisibility, gitCommitMessage, collaborators | Same as create + imports content/ directory from source Showroom repo |
| `publishing-house:annotate` | labels, annotations, spec | Annotates catalog-info.yaml with additional metadata |
| `publishing-house:timestamp` | (none) | Sets `ph.rhdp.io/created-at` annotation to current ISO timestamp |

---

## readme / readme-backend

**Version:** 0.1.0 each
**Location:** `plugins/readme/`, `plugins/readme-backend/`

Frontend + backend plugin pair for rendering README content in the RHDH catalog entity view. Standard README display functionality.

---

## Plugin Build and Deploy

Plugins are built using `build-dynamic-plugin.sh` and deployed via the RHDH dynamic plugins mechanism:
1. Build produces a tarball
2. Tarball is published (or mounted via PVC)
3. RHDH dynamic plugins ConfigMap references the plugin
4. RHDH pod mounts the `developer-hub-dynamic-plugins-root` PVC (5Gi)
