# Automation Manifest Format

The automation manifest is a structured YAML file that describes what needs to be
automated for a lab or demo environment. It is the contract between content (what
the learner experiences) and automation (what the environment needs pre-configured).

## Location

`publishing-house/spec/automation-manifest.yaml`

## Format

```yaml
# Automation Manifest
approach: ansible | gitops | both

infrastructure:
  type: ocp-cnv | ocp-aws | rhel-vms | sandbox-cluster | sandbox-tenant | field-per-user-cluster | field-shared-cluster
  topology: per-user-cluster | shared-cluster  # self_published only
  ocp_version: "4.17"
  multi_user: true
  users_per_deployment: 25

operators:
  - name: Red Hat OpenShift Pipelines
    channel: latest
    namespace: openshift-operators
    reason: "Module 2 uses Tekton pipelines"
    source_module: module-02-pipelines

applications:
  - name: sample-app
    description: "Application the learner configures"
    namespace: "{{ user_namespace }}"
    image: quay.io/org/sample-app:v1.0
    resources:
      - kind: Deployment
      - kind: Service
      - kind: Route
    reason: "Module 1 starts with 'open the application'"
    source_module: module-01-overview

rbac:
  - type: namespace
    name: "{{ user_namespace }}"
    reason: "Per-user namespace for lab resources"

seed_data:
  - type: git-repo
    name: sample-app-source
    url: https://github.com/rhpds/sample-app.git
    target: gitea
    reason: "Module 2 uses Tekton pipeline from this repo"
    source_module: module-02-pipelines

broken_resources:
  - name: broken-pod
    namespace: "{{ user_namespace }}"
    description: "Pod with typo in nodeSelector"
    what_is_broken: "nodeSelector uses 'wrker' instead of 'worker'"
    resources:
      - kind: Pod
    reason: "Module 4 troubleshooting exercise"
    source_module: module-04-troubleshooting

provision_data:
  - key: app_url
    value: "https://sample-app-{{ user_namespace }}.{{ deployer.domain }}"
    description: "URL to the sample application"

notes: |
  Any additional notes for the automation developer.
```

## Reviewing the Manifest

1. Every operator/app has a `reason` and `source_module`
2. Nothing the learner should do themselves is listed
3. Provision data covers everything the learner needs to connect
4. Multi-user is correct
5. Approach matches the lab's needs
