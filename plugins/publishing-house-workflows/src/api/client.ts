import { DiscoveryApi, FetchApi } from '@backstage/core-plugin-api';
import { ProcessInstance, WorkflowSummary, WorkflowStage } from './types';
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
  ): Promise<void> {
    const typeMap: Partial<Record<WorkflowStage, string>> = {
      content_review: 'ph.content-review.complete',
      infra_review: 'ph.infra-review.complete',
      development: 'ph.development.complete',
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
        data: {},
      }),
    });

    if (!response.ok) {
      throw new Error(
        `Approval failed: ${response.status} ${response.statusText}`,
      );
    }
  }

  return { getWorkflows, getWorkflow, getWorkflowById, sendApprovalEvent };
}
