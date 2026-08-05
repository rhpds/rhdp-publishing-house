import { DiscoveryApi, FetchApi, IdentityApi } from '@backstage/core-plugin-api';
import { ProcessInstance, WorkflowSummary, WorkflowStage, RejectionData, ValidationReport, DriftReport, DeleteProjectResult, ReviewMessage, TokenListResponse, RevokeResponse, RevokeAllResponse } from './types';
import { deriveStage } from '../utils/stageMapping';

const TOKEN_STORAGE_KEY = 'ph-central-token';
const EXPIRY_STORAGE_KEY = 'ph-central-token-expiry';

const GRAPHQL_QUERY = `
  query GetPublishingHouseWorkflows {
    ProcessInstances(where: { processId: { equal: "publishinghouseworkflow" }, state: { in: [ACTIVE, ERROR, SUSPENDED] } }) {
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
    hasDrift: wd.hasDrift ?? false,
    baselineSha: wd.baselineSha || '',
  };
}

export function createPhWorkflowsClient(options: {
  centralApiUrl: string;
  discoveryApi: DiscoveryApi;
  fetchApi: FetchApi;
  identityApi?: IdentityApi;
}) {
  const { centralApiUrl, discoveryApi, fetchApi, identityApi } = options;

  async function getUserToken(): Promise<string | undefined> {
    const cached = sessionStorage.getItem(TOKEN_STORAGE_KEY);
    const expiry = Number(sessionStorage.getItem(EXPIRY_STORAGE_KEY) || '0');
    if (cached && Date.now() / 1000 < expiry - 60) {
      return cached;
    }

    if (!identityApi) return undefined;

    let backstageToken: string | undefined;
    try {
      const creds = await identityApi.getCredentials();
      backstageToken = creds.token;
    } catch {
      return undefined;
    }
    if (!backstageToken) return undefined;

    const proxyUrl = await discoveryApi.getBaseUrl('proxy');
    const resp = await fetchApi.fetch(
      `${proxyUrl}/central-api/auth/keys/exchange`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ backstage_token: backstageToken }),
      },
    );

    if (!resp.ok) return undefined;

    const data = await resp.json();
    sessionStorage.setItem(TOKEN_STORAGE_KEY, data.token);
    sessionStorage.setItem(EXPIRY_STORAGE_KEY, String(new Date(data.expires_at).getTime() / 1000));
    return data.token;
  }

  async function centralFetch(path: string, init?: RequestInit): Promise<Response> {
    const token = await getUserToken();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers as Record<string, string> | undefined),
    };
    const resp = await globalThis.fetch(`${centralApiUrl}/api/v1${path}`, {
      ...init,
      headers,
    });
    if (resp.status === 401 && token) {
      sessionStorage.removeItem(TOKEN_STORAGE_KEY);
      sessionStorage.removeItem(EXPIRY_STORAGE_KEY);
    }
    return resp;
  }

  async function getWorkflows(): Promise<WorkflowSummary[]> {
    const proxyUrl = await discoveryApi.getBaseUrl('proxy');
    const response = await fetchApi.fetch(
      `${proxyUrl}/sonataflow`,
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
      `${proxyUrl}/sonataflow`,
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
      `${proxyUrl}/sonataflow`,
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
    const stagePathMap: Partial<Record<WorkflowStage, string>> = {
      content_review: 'content-review',
      infra_review: 'infra-review',
    };
    const stagePath = stagePathMap[stage];
    if (!stagePath) {
      throw new Error(`Cannot approve stage: ${stage}`);
    }

    const slug = projectId ?? workflowId;
    const response = await centralFetch(
      `/projects/${slug}/${stagePath}/approve`,
      {
        method: 'POST',
        body: JSON.stringify({
          commit_sha: auditData?.commitSha ?? '',
        }),
      },
    );

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
    const stagePathMap: Partial<Record<WorkflowStage, string>> = {
      content_review: 'content-review',
      infra_review: 'infra-review',
    };
    const stagePath = stagePathMap[stage];
    if (!stagePath) {
      throw new Error(`Cannot reject stage: ${stage}`);
    }

    const slug = projectId ?? workflowId;
    const response = await centralFetch(
      `/projects/${slug}/${stagePath}/reject`,
      {
        method: 'POST',
        body: JSON.stringify({
          reasons: rejectionData.reasons,
          reviewer_name: rejectionData.reviewerName,
          commit_sha: commitSha ?? '',
        }),
      },
    );

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
    baselineSha?: string,
  ): Promise<ValidationReport> {
    const params = new URLSearchParams({ stage: 'review' });
    if (baselineSha) {
      params.set('baseline_sha', baselineSha);
    }
    const response = await centralFetch(
      `/spec/validation/${slug}?${params}`,
      {
        method: 'POST',
        body: JSON.stringify({ repo_url: repoUrl, branch }),
      },
    );

    const json = await response.json();
    return json as ValidationReport;
  }

  async function fetchDriftReport(
    slug: string,
    mode: 'structural' | 'semantic' = 'semantic',
  ): Promise<DriftReport> {
    const response = await centralFetch(
      `/spec/drift/${slug}?mode=${mode}`,
      { method: 'POST' },
    );

    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || `Drift check failed: ${response.status}`);
    }

    return await response.json() as DriftReport;
  }

  async function approveDrift(
    slug: string,
  ): Promise<{ slug: string; baselineSha: string; cleared: boolean }> {
    const response = await centralFetch(
      `/projects/${slug}/drift/approve`,
      { method: 'POST' },
    );

    if (!response.ok) {
      throw new Error(`Drift approval failed: ${response.status} ${response.statusText}`);
    }

    return await response.json();
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

  async function deleteProject(
    slug: string,
    deleteRepo: boolean,
  ): Promise<DeleteProjectResult> {
    const response = await centralFetch(
      `/projects/${slug}?delete_repo=${deleteRepo}`,
      { method: 'DELETE' },
    );

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Delete failed (${response.status}): ${text}`);
    }

    return await response.json();
  }

  async function sendMessage(
    slug: string,
    text: string,
    stage: string,
  ): Promise<{ sent: boolean; recipients: string[] }> {
    const response = await centralFetch(
      `/projects/${slug}/messages`,
      {
        method: 'POST',
        body: JSON.stringify({ text, stage }),
      },
    );

    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || `Send message failed: ${response.status}`);
    }

    return await response.json();
  }

  async function getMessages(
    slug: string,
    unreadOnly?: boolean,
  ): Promise<ReviewMessage[]> {
    const params = unreadOnly !== undefined ? `?read=${!unreadOnly}` : '';
    const response = await centralFetch(
      `/projects/${slug}/messages${params}`,
    );

    if (!response.ok) return [];

    const data = await response.json();
    return data.messages ?? [];
  }

  async function markMessagesRead(
    slug: string,
    ids: string[],
  ): Promise<{ marked: number }> {
    const response = await centralFetch(
      `/projects/${slug}/messages/read`,
      {
        method: 'POST',
        body: JSON.stringify({ ids }),
      },
    );

    if (!response.ok) return { marked: 0 };
    return await response.json();
  }

  async function submitStaging(
    slug: string,
    agnosticvUrl: string,
    ciUrl: string,
  ): Promise<void> {
    const response = await centralFetch(
      `/projects/${slug}/staging/submit`,
      {
        method: 'POST',
        body: JSON.stringify({ agnosticv_url: agnosticvUrl, ci_url: ciUrl }),
      },
    );

    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || `Staging submit failed: ${response.status}`);
    }
  }

  async function getTokens(): Promise<TokenListResponse> {
    const response = await centralFetch('/auth/tokens');
    if (!response.ok) throw new Error(`Failed to list tokens: ${response.status}`);
    return await response.json();
  }

  async function searchTokens(query: string): Promise<TokenListResponse> {
    const response = await centralFetch(`/auth/tokens/search?q=${encodeURIComponent(query)}`);
    if (!response.ok) throw new Error(`Token search failed: ${response.status}`);
    return await response.json();
  }

  async function revokeToken(email: string): Promise<RevokeResponse> {
    const response = await centralFetch(`/auth/tokens/${encodeURIComponent(email)}`, { method: 'DELETE' });
    if (!response.ok) throw new Error(`Revoke failed: ${response.status}`);
    return await response.json();
  }

  async function revokeAllTokens(): Promise<RevokeAllResponse> {
    const response = await centralFetch('/auth/tokens', { method: 'DELETE' });
    if (!response.ok) throw new Error(`Revoke all failed: ${response.status}`);
    return await response.json();
  }

  return {
    getWorkflows,
    getWorkflow,
    getWorkflowById,
    sendApprovalEvent,
    sendRejectionEvent,
    fetchValidationReport,
    fetchDriftReport,
    approveDrift,
    fetchHeadCommitSha,
    deleteProject,
    submitStaging,
    sendMessage,
    getMessages,
    markMessagesRead,
    getTokens,
    searchTokens,
    revokeToken,
    revokeAllTokens,
  };
}
