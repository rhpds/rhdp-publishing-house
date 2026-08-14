# GitOps

> **Note:** Publishing House provides a `gitops-helper` skill that automates
> the GitOps setup for you. If you prefer to set it up manually,
> follow the structure below.

## Overview

This guide covers how to structure and write GitOps workloads (Helm + ArgoCD) for RHDP labs.

<!-- Juliano to document the following sections:

1. Repo structure - what a GitOps lab repo looks like (Helm chart layout, ArgoCD manifests)
2. ArgoCD Application - how to define the Application manifest and pin to a version
3. Helm chart versioning - extracting shared charts into a dedicated repo with version tags
4. Required variables - what PH passes in, what the workload must define
5. Local testing - how to validate the Helm chart and ArgoCD sync before submitting
6. CI integration - how the GitOps workload gets picked up by the platform

-->
