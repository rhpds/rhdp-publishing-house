# Infrastructure — infra02 As-Deployed

Snapshot of the `publishing-house` namespace on `ocpv-infra02.wdc07.infra.demo.redhat.com` as of 2026-08-21.

## Deployments

| Deployment | Image | Tag | Replicas | CPU Limit | Memory Limit | CPU Request | Memory Request |
|---|---|---|---|---|---|---|---|
| central-api | quay.io/rhpds/central-api | 1.21.9 | 1 | 500m | 1Gi | 100m | 512Mi |
| publishinghouseworkflow | quay.io/rhpds/publishing-house-workflow | 1.5 | 1 | — | — | — | — |
| backstage-developer-hub | registry.redhat.io/rhdh/rhdh-hub-rhel9 | sha256:24be57... | 1 | 4 | 2560Mi | 250m | 256Mi |
| sonataflow-platform-data-index-service | registry.redhat.io/openshift-serverless-1/logic-data-index-postgresql-rhel9 | sha256:fad663... | 1 | 200m | 1Gi | 100m | 1Gi |
| sonataflow-platform-jobs-service | registry.redhat.io/openshift-serverless-1/logic-jobs-service-postgresql-rhel9 | sha256:892b94... | 1 | 500m | 1Gi | 250m | 64Mi |
| sonataflow-management-console | docker.io/apache/incubator-kie-sonataflow-management-console | main | 1 | 500m | 512Mi | 100m | 256Mi |
| sonataflow-management-console (sidecar) | quay.io/oauth2-proxy/oauth2-proxy | v7.7.1 | — | 100m | 128Mi | 50m | 64Mi |

## StatefulSets

| StatefulSet | Image | Replicas | CPU Limit | Memory Limit |
|---|---|---|---|---|
| backstage-psql-developer-hub | registry.redhat.io/rhel9/postgresql-15 | 1 | 250m | 1Gi |
| sonataflow-postgresql | registry.redhat.io/rhel9/postgresql-15:latest | 1 | 1 | 1Gi |

## CronJobs

| CronJob | Schedule | Image |
|---|---|---|
| drift-checker | `0 6 * * *` (daily 06:00 UTC) | python:3.11-slim |
| inactivity-checker | `0 7 * * *` (daily 07:00 UTC) | python:3.11-slim |
| workflow-cleanup | `0 5 * * *` (daily 05:00 UTC) | python:3.11-slim |

## Services

| Service | Type | Port(s) |
|---|---|---|
| central-api | ClusterIP | 8000 |
| publishinghouseworkflow | ClusterIP | 80 |
| backstage-developer-hub | ClusterIP | 80, 9464 |
| backstage-psql-developer-hub | ClusterIP (headless) | 5432 |
| sonataflow-platform-data-index-service | ClusterIP | 80 |
| sonataflow-platform-jobs-service | ClusterIP | 80 |
| sonataflow-management-console | ClusterIP | 8080 |

## Routes

| Route | Host | Service | TLS |
|---|---|---|---|
| central-api | central-api-publishing-house.apps.ocpv-infra02.wdc07.infra.demo.redhat.com | central-api | edge/Redirect |
| central-publishing-house | central-publishing-house-publishing-house.apps.ocpv-infra02.wdc07.infra.demo.redhat.com | backstage-developer-hub | edge/Redirect |
| sonataflow-management-console | sonataflow-management-console-publishing-house.apps.ocpv-infra02.wdc07.infra.demo.redhat.com | sonataflow-management-console | edge |

## Persistent Volume Claims

| PVC | Capacity | Access | Storage Class | Used By |
|---|---|---|---|---|
| central-api-data | 1Gi | RWO | ocs-storagecluster-ceph-rbd | Central API (token cache) |
| data-backstage-psql-developer-hub-0 | 1Gi | RWO | ocs-storagecluster-ceph-rbd | RHDH PostgreSQL |
| data-sonataflow-postgresql-0 | 5Gi | RWO | ocs-storagecluster-ceph-rbd | SonataFlow PostgreSQL |
| developer-hub-dynamic-plugins-root | 5Gi | RWO | ocs-storagecluster-ceph-rbd | RHDH dynamic plugins |

## ConfigMaps (18)

| ConfigMap | Purpose |
|---|---|
| central-api-config | Central API env vars (15 keys) |
| central-api-spec | OpenAPI spec for SonataFlow |
| ph-validation-policy | Validation policy (products, verbs, content types) |
| ph-developer-hub-app-config | RHDH app-config |
| ph-developer-hub-dynamic-plugins | RHDH plugin config |
| ph-rbac-policy | RHDH RBAC policy |
| publishinghouseworkflow-managed-props | SonataFlow managed properties |
| publishinghouseworkflow-props | SonataFlow user properties |
| sonataflow-platform-data-index-service-props | Data index properties |
| sonataflow-platform-jobs-service-props | Jobs service properties |
| workflow-input-schema | Workflow input JSON schema |
| drift-checker-script | Drift checker CronJob script |
| inactivity-checker-script | Inactivity checker CronJob script |
| workflow-cleanup-script | Workflow cleanup CronJob script |
| backstage-appconfig-developer-hub-default-appconfig | RHDH default appconfig |
| backstage-dynamic-plugins-developer-hub | RHDH dynamic plugins (operator-managed) |
| kube-root-ca.crt | Cluster root CA |
| openshift-service-ca.crt | Service CA |

## Secrets (11)

| Secret | Purpose |
|---|---|
| publishing-house-credentials | All API keys/tokens (from Vault via ESO) |
| backstage-psql-secret-developer-hub | RHDH PostgreSQL credentials |
| ph-developer-hub-env | RHDH environment variables |
| rhdh-k8s-integration | Kubernetes plugin SA token |
| sonataflow-postgresql-svcbind | SonataFlow DB connection |
| sonataflow-console-oauth-proxy | Management console OAuth config |
| *-dockercfg-* | Container registry pull secrets (4) |

## External Secrets

| Name | Store | Refresh | Status |
|---|---|---|---|
| publishing-house-credentials | vault-secret-store (ClusterSecretStore) | 1h | SecretSynced / Ready |

## SonataFlow Platform

- Build strategy: platform, MAVEN_ARGS=-DskipTests
- Monitoring: enabled
- Data Index: PostgreSQL-backed, CORS enabled
- Jobs Service: PostgreSQL-backed
- REST endpoint: Central API route, auth via publishing-house-credentials

## Workflow Instance Counts

| State | Count |
|---|---|
| ACTIVE | 26 |
| COMPLETED | 0 |
| ERROR | 0 |

## Network

- No NetworkPolicies in publishing-house namespace
- No Ingress resources (OpenShift Routes used instead)
- No DevWorkspaceTemplates in namespace
- SonataFlow operator subscription location not confirmed (may be cluster-scoped)
