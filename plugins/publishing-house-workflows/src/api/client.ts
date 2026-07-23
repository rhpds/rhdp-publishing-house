import { DiscoveryApi, FetchApi } from '@backstage/core-plugin-api';
import { ProcessInstance, WorkflowSummary, WorkflowStage, RejectionData, ValidationReport, DriftReport } from './types';
import { deriveStage } from '../utils/stageMapping';

const GRAPHQL_QUERY = `
  query GetPublishingHouseWorkflows {
    ProcessInstances(where: { processId: { equal: "publishinghouseworkflow" } }) {
      id
      businessKey
      processId
      state
      start
      lastUpdate
      nodes { name enter exit type }
      variables
    }
  }
`;

function toSummary(inst: ProcessInstance): WorkflowSummary {
  const wd = inst.variables?.workflowdata ?? ({} as any);
  return {
    id: inst.id,
    projectId: inst.businessKey || wd.projectId || '',
    owner: wd.ssoEmail || wd.githubUser || '',
    ssoUser: wd.ssoUser || '',
    ssoEmail: wd.ssoEmail || '',
    contentType: wd.contentType || '',
    deploymentMode: wd.deploymentMode || '',
    stage: deriveStage(inst.nodes || [], inst.state),
    state: inst.state,
    epicKey: wd.epic_key || '',
    jiraUrl: wd.jira_url || (wd.epic_key ? `https://redhat.atlassian.net/browse/${wd.epic_key}` : ''),
    repoUrl: wd.repoUrl || '',
    tags: Array.isArray(wd.tags) ? wd.tags : [],
    projectDescription: wd.projectDescription || '',
    startedAt: inst.start,
    lastUpdate: inst.lastUpdate,
  };
}

export function createPhWorkflowsClient(options: {
  discoveryApi: DiscoveryApi;
  fetchApi: FetchApi;
}) {
  const { discoveryApi, fetchApi } = options;

  async function getWorkflows(): Promise<WorkflowSummary[]> {
    const proxyUrl = await discoveryApi.getBaseUrl('proxy');
    const response = await fetchApi.fetch(
      `${proxyUrl}/sonataflow/graphql`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: GRAPHQL_QUERY }),
      },
    );

    if (!response.ok) {
      throw new Error(
        `Workflow query failed: ${response.status} ${response.statusText}`,
      );
    }

    const json = await response.json();
    const instances: ProcessInstance[] =
      json?.data?.ProcessInstances ?? [];

    return instances.map(inst => toSummary(inst));
  }

  async function getWorkflow(projectId: string): Promise<{
    summary: WorkflowSummary;
    instance: ProcessInstance;
  } | undefined> {
    const proxyUrl = await discoveryApi.getBaseUrl('proxy');
    const query = `
      query GetWorkflowByProject($bk: String!) {
        ProcessInstances(where: { businessKey: { equal: $bk } }) {
          id
          businessKey
          processId
          state
          start
          lastUpdate
          nodes { name enter exit type }
          variables
        }
      }
    `;
    const response = await fetchApi.fetch(
      `${proxyUrl}/sonataflow/graphql`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, variables: { bk: projectId } }),
      },
    );

    if (!response.ok) {
      throw new Error(
        `Workflow query failed: ${response.status} ${response.statusText}`,
      );
    }

    const json = await response.json();
    const instances: ProcessInstance[] =
      json?.data?.ProcessInstances ?? [];

    if (instances.length === 0) return undefined;

    const inst = instances[0];
    return { summary: toSummary(inst), instance: inst };
  }

  async function getWorkflowById(workflowId: string): Promise<{
    summary: WorkflowSummary;
    instance: ProcessInstance;
  } | undefined> {
    const proxyUrl = await discoveryApi.getBaseUrl('proxy');
    const query = `
      query GetWorkflowById($id: String!) {
        ProcessInstances(where: { id: { equal: $id } }) {
          id
          businessKey
          processId
          state
          start
          lastUpdate
          nodes { name enter exit type }
          variables
        }
      }
    `;
    const response = await fetchApi.fetch(
      `${proxyUrl}/sonataflow/graphql`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, variables: { id: workflowId } }),
      },
    );

    if (!response.ok) {
      throw new Error(
        `Workflow query failed: ${response.status} ${response.statusText}`,
      );
    }

    const json = await response.json();
    const instances: ProcessInstance[] =
      json?.data?.ProcessInstances ?? [];

    if (instances.length === 0) return undefined;

    const inst = instances[0];
    return { summary: toSummary(inst), instance: inst };
  }

  async function sendApprovalEvent(
    workflowId: string,
    stage: WorkflowStage,
    projectId?: string,
    auditData?: { user: string; commitSha?: string },
  ): Promise<void> {
    const typeMap: Partial<Record<WorkflowStage, string>> = {
      content_review: 'ph.content-review.complete',
      infra_review: 'ph.infra-review.complete',
      development: 'ph.development.complete',
      drift_review: 'ph.drift-review.approved',
      testing: 'ph.testing.complete',
    };
    const eventType = typeMap[stage];
    if (!eventType) {
      throw new Error(`Cannot approve stage: ${stage}`);
    }

    const proxyUrl = await discoveryApi.getBaseUrl('proxy');
    const response = await fetchApi.fetch(`${proxyUrl}/sonataflow/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/cloudevents+json' },
      body: JSON.stringify({
        specversion: '1.0',
        type: eventType,
        source: 'publishing-house',
        id: crypto.randomUUID(),
        kogitobusinesskey: projectId ?? workflowId,
        projectid: projectId ?? workflowId,
        datacontenttype: 'application/json',
        data: {
          user: auditData?.user ?? '',
          stage,
          action: stage === 'development' || stage === 'testing' ? 'completed' : 'approved',
          timestamp: new Date().toISOString(),
          commitSha: auditData?.commitSha ?? '',
        },
      }),
    });

    if (!response.ok) {
      throw new Error(
        `Approval failed: ${response.status} ${response.statusText}`,
      );
    }
  }

  async function sendRejectionEvent(
    workflowId: string,
    stage: WorkflowStage,
    rejectionData: RejectionData,
    projectId?: string,
    commitSha?: string,
  ): Promise<void> {
    const typeMap: Partial<Record<WorkflowStage, string>> = {
      content_review: 'ph.content-review.rejected',
      infra_review: 'ph.infra-review.rejected',
      drift_review: 'ph.drift-review.rejected',
    };
    const eventType = typeMap[stage];
    if (!eventType) {
      throw new Error(`Cannot reject stage: ${stage}`);
    }

    const proxyUrl = await discoveryApi.getBaseUrl('proxy');
    const response = await fetchApi.fetch(`${proxyUrl}/sonataflow/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/cloudevents+json' },
      body: JSON.stringify({
        specversion: '1.0',
        type: eventType,
        source: 'publishing-house',
        id: crypto.randomUUID(),
        kogitobusinesskey: projectId ?? workflowId,
        projectid: projectId ?? workflowId,
        datacontenttype: 'application/json',
        data: {
          user: rejectionData.reviewerName,
          stage,
          action: 'rejected',
          timestamp: rejectionData.timestamp,
          commitSha: commitSha ?? '',
          rejectionId: rejectionData.rejectionId,
          reasons: rejectionData.reasons,
        },
      }),
    });

    if (!response.ok) {
      throw new Error(
        `Rejection failed: ${response.status} ${response.statusText}`,
      );
    }
  }

  async function fetchValidationReport(
    slug: string,
    repoUrl: string,
    branch: string = 'main',
    approvedSha?: string,
  ): Promise<ValidationReport> {
    const proxyUrl = await discoveryApi.getBaseUrl('proxy');
    const params = new URLSearchParams({ stage: 'review' });
    if (approvedSha) {
      params.set('approved_sha', approvedSha);
    }
    const response = await fetchApi.fetch(
      `${proxyUrl}/central-api/spec/validation/${slug}?${params}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_url: repoUrl, branch }),
      },
    );

    const json = await response.json();
    return json as ValidationReport;
  }

  async function fetchDriftReport(
    slug: string,
    repoUrl: string,
    branch: string = 'main',
    approvedSha: string,
  ): Promise<DriftReport> {
    const proxyUrl = await discoveryApi.getBaseUrl('proxy');
    const response = await fetchApi.fetch(
      `${proxyUrl}/central-api/spec/drift/${slug}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_url: repoUrl, branch, approved_sha: approvedSha }),
      },
    );

    if (!response.ok) {
      throw new Error(`Drift check failed: ${response.status} ${response.statusText}`);
    }

    return await response.json() as DriftReport;
  }

  async function fetchHeadCommitSha(
    repoUrl: string,
    branch: string = 'main',
  ): Promise<string | undefined> {
    const match = repoUrl.replace(/\.git$/, '').match(/github\.com\/([^/]+)\/([^/]+)/);
    if (!match) return undefined;
    const [, owner, repo] = match;

    const proxyUrl = await discoveryApi.getBaseUrl('proxy');
    const response = await fetchApi.fetch(
      `${proxyUrl}/github-api/repos/${owner}/${repo}/commits/${branch}`,
      { headers: { Accept: 'application/vnd.github.sha' } },
    );

    if (!response.ok) return undefined;
    return (await response.text()).trim();
  }

  return {
    getWorkflows,
    getWorkflow,
    getWorkflowById,
    sendApprovalEvent,
    sendRejectionEvent,
    fetchValidationReport,
    fetchDriftReport,
    fetchHeadCommitSha,
  };
}
