# SonataFlow Workflow

**Name:** `publishinghouseworkflow`
**Profile:** preview
**Persistence:** PostgreSQL (database: `sonataflow`, schema: `publishing-house-workflow`)
**Defined in:** `deployment/roles/sonataflow/templates/sonataflow-workflow.yaml.j2` (Jinja2 template, no standalone .sw.json)

## State Machine

```
Start
  │
  ▼
Init (inject)
  │  Sets: projectId, repoUrl, projectName, ssoUser, ssoEmail,
  │        deploymentMode, contentType, tags, showroomType, intakeType
  ▼
Setup (inject)
  │  Sets: createdAt, reviews={content:false,infra:false},
  │        rejection={isRejected:false}, reviewHistory=[{stage:intake,
  │        action:started}], baselineSha="", hasDrift=false
  ▼
CreateEpic (operation) ─── conditional: only if deploymentMode == rhdp_published
  │  Calls: createjiraepic → Central API
  │  Sets: epic_key, jira_url
  ▼
┌─────────────────────────────────────────────────────────┐
│ Intake (event wait)                                      │
│   Waits for: ph.intake.complete                          │
│   Timeout: PT168H (7 days)                               │
│   Correlation: projectid                                 │
│   On receive: merges auditTrailSha + reviewHistory entry │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│ ContentReview (event wait)                               │
│   Waits for: ph.content-review.complete                  │
│          OR: ph.content-review.rejected                  │
│   Timeout: PT168H                                        │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
ContentReviewDecision (switch)
  ├── rejection.isRejected == true ──► Intake (loop back)
  └── else ──► InfraReview
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│ InfraReview (event wait)                                 │
│   Waits for: ph.infra-review.complete                    │
│          OR: ph.infra-review.rejected                    │
│   Timeout: PT168H                                        │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
InfraReviewDecision (switch)
  ├── rejection.isRejected == true ──► ContentReview (loop back)
  └── else ──► JiraSyncIntake
                      │
                      ▼
JiraSyncIntake (operation) ─── conditional: rhdp_published
  │  Calls: syncjiratasks
  ▼
EnvSetupOrDev (switch)
  ├── showroomType == zero_touch ──► Development (skip env setup)
  └── else ──► EnvSetup
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│ EnvSetup (event wait)                                    │
│   Waits for: ph.env-setup.complete                       │
│   Timeout: PT168H                                        │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
JiraSyncEnvSetup (operation) ─── conditional
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│ Development (event wait)                                 │
│   Waits for: ph.development.complete                     │
│   Timeout: PT168H                                        │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
JiraSyncDev (operation) ─── conditional
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│ Testing (event wait)                                     │
│   Waits for: ph.testing.complete                         │
│   Timeout: PT168H                                        │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
JiraSyncFinal (operation) ─── conditional
                      │
                      ▼
Published (inject: terminate)
  │  Sets: completedAt
  ▼
End
```

## Events

All events use CloudEvents format, correlated by `projectid`.

| Event Name | Type String | Consumed At | Sent By |
|---|---|---|---|
| IntakeCompleteEvent | `ph.intake.complete` | Intake | Central API (on intake submit) |
| ContentReviewCompleteEvent | `ph.content-review.complete` | ContentReview | Central API (on content approve) |
| ContentReviewRejectedEvent | `ph.content-review.rejected` | ContentReview | Central API (on content reject) |
| InfraReviewCompleteEvent | `ph.infra-review.complete` | InfraReview | Central API (on infra approve) |
| InfraReviewRejectedEvent | `ph.infra-review.rejected` | InfraReview | Central API (on infra reject) |
| EnvSetupCompleteEvent | `ph.env-setup.complete` | EnvSetup | Central API (on env-setup submit) |
| DevelopmentCompleteEvent | `ph.development.complete` | Development | Central API (on dev submit) |
| TestingCompleteEvent | `ph.testing.complete` | Testing | Central API (on testing submit) |

## REST Functions

| Function | Target | OpenAPI Operation |
|---|---|---|
| `createjiraepic` | Central API | `central-api.yaml#createJiraEpic` |
| `syncjiratasks` | Central API | `central-api.yaml#syncJiraTasks` |
| `printMessage` | sysout (logging) | N/A |

## Rejection Loops

**Content review rejection:**
- ContentReviewDecision checks `rejection.isRejected`
- If true: returns to **Intake** state
- Author addresses rejections via rejection handler, resubmits intake
- Flow re-enters ContentReview after intake re-submission

**Infra review rejection:**
- InfraReviewDecision checks `rejection.isRejected`
- If true: returns to **ContentReview** state
- Requires content re-review before infra re-review

## Workflow Data Model

### workflowdata (runtime state)

| Field | Type | Set By | Purpose |
|---|---|---|---|
| `projectId` | string | Init | Business key, matches repo name |
| `projectid` | string | Init | Lowercase copy for CloudEvent correlation |
| `repoUrl` | string | Init | GitHub repo URL |
| `projectName` | string | Init | Display name |
| `ssoUser` | string | Init | Owner's SSO username |
| `ssoEmail` | string | Init | Owner's email |
| `deploymentMode` | string | Init | `rhdp_published` or `self_published` |
| `contentType` | string | Init | `lab` or `demo` |
| `tags` | string[] | Init | Project tags |
| `showroomType` | string | Init | `classic` or `zero_touch` |
| `intakeType` | string | Init | `new` or `migration` |
| `projectDescription` | string | Init | Project description |
| `auditTrailSha` | string | Events | Latest validated commit SHA |
| `baselineSha` | string | Drift approve | SHA against which drift is measured |
| `hasDrift` | boolean | CronJob | Whether structural drift detected |
| `createdAt` | number | Setup | Unix timestamp |
| `reviews.content` | boolean | ContentReview | Content review completed |
| `reviews.infra` | boolean | InfraReview | Infra review completed |
| `rejection.isRejected` | boolean | Review events | Currently in rejected state |
| `rejection.reviewerName` | string | Review events | Who rejected |
| `rejection.reviewerStage` | string | Review events | Which review stage |
| `rejection.timestamp` | string | Review events | When rejected |
| `rejection.reasons` | object[] | Review events | Rejection reasons |
| `reviewHistory` | object[] | Events | Audit trail of stage transitions |
| `epic_key` | string | CreateEpic | Jira epic key (e.g. RHDPCD-1166) |
| `jira_url` | string | CreateEpic | Jira epic URL |
| `latestAudit` | object | Validation | Latest validation result |
| `agnosticvUrls` | object | EnvSetup | AgnosticV URLs from env setup |
| `ciUrls` | object | EnvSetup | CI URLs from env setup |

### workflowdatainput (immutable copy)

Subset of workflowdata fields set at Init time. Updated via PATCH to runtime endpoint (propagates to both workflowdata and workflowdatainput in data index).

### reviewHistory entry

```json
{
  "user": "user@redhat.com",
  "stage": "intake",
  "action": "started",
  "commitSha": "abc123...",
  "timestamp": "1.787273510395e+9"
}
```

## Timeouts

Every event-wait state has `PT168H` (7 days) timeout. On timeout the workflow stays in the current state (no auto-transition).

## Jira Sync Points

Jira task sync runs at 4 points, all conditional on `deploymentMode == rhdp_published`:
1. After intake approval (JiraSyncIntake)
2. After env setup completion (JiraSyncEnvSetup)
3. After development completion (JiraSyncDev)
4. After testing completion (JiraSyncFinal)

## Deployment

- **SonataFlowPlatform CR** manages data-index and jobs-service
- **Build:** in-cluster using Serverless Logic operator, resources: 4 CPU / 4Gi memory
- **Data Index:** PostgreSQL-backed, CORS enabled for management console
- **Jobs Service:** PostgreSQL-backed
