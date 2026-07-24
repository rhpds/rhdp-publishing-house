import { DiscoveryApi, FetchApi } from '@backstage/core-plugin-api';

export interface DeleteProjectResult {
  slug: string;
  workflow_aborted: boolean;
  litellm_keys_deleted: number;
  jira_archived: boolean;
  repo_deleted: boolean;
  errors: string[];
}

export interface WorkflowInfo {
  projectId: string;
  epicKey: string;
  jiraUrl: string;
  startedAt: string;
  owner: string;
}

const GRAPHQL_QUERY = `
  query GetPublishingHouseWorkflows {
    ProcessInstances(where: { processId: { equal: "publishinghouseworkflow" } }) {
      id
      businessKey
      state
      start
      variables
    }
  }
`;

export function createPhMaintenanceClient(options: {
  discoveryApi: DiscoveryApi;
  fetchApi: FetchApi;
}) {
  const { discoveryApi, fetchApi } = options;

  async function deleteProject(
    slug: string,
    deleteRepo: boolean,
  ): Promise<DeleteProjectResult> {
    const proxyUrl = await discoveryApi.getBaseUrl('proxy');
    const response = await fetchApi.fetch(
      `${proxyUrl}/central-api/projects/${slug}?delete_repo=${deleteRepo}`,
      { method: 'DELETE' },
    );

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Delete failed (${response.status}): ${text}`);
    }

    return await response.json();
  }

  async function getWorkflowMap(): Promise<Record<string, WorkflowInfo>> {
    const proxyUrl = await discoveryApi.getBaseUrl('proxy');
    const response = await fetchApi.fetch(
      `${proxyUrl}/sonataflow/graphql`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: GRAPHQL_QUERY }),
      },
    );

    if (!response.ok) return {};

    const json = await response.json();
    const instances = json?.data?.ProcessInstances ?? [];
    const map: Record<string, WorkflowInfo> = {};

    for (const inst of instances) {
      const wd = inst.variables?.workflowdata ?? {};
      const projectId = inst.businessKey || wd.projectId || '';
      if (!projectId) continue;
      const epicKey = wd.epic_key || '';
      map[projectId] = {
        projectId,
        epicKey,
        jiraUrl: wd.jira_url || (epicKey ? `https://redhat.atlassian.net/browse/${epicKey}` : ''),
        startedAt: inst.start || '',
        owner: wd.ssoEmail || wd.ssoUser || '',
      };
    }

    return map;
  }

  return { deleteProject, getWorkflowMap };
}
