export interface WorkflowNode {
  name: string;
  enter: string | null;
  exit: string | null;
  type: string;
}

export interface WorkflowVariables {
  workflowdata: {
    projectId: string;
    projectid: string;
    githubUser: string;
    ssoUser?: string;
    ssoEmail?: string;
    repoUrl: string;
    deploymentMode: string;
    projectType: string;
    createdAt: number;
    epic_key?: string;
    jira_url?: string;
    tags?: string[];
  };
}

export interface ProcessInstance {
  id: string;
  businessKey: string;
  processId: string;
  state: string;
  start: string;
  lastUpdate: string;
  nodes: WorkflowNode[];
  variables: WorkflowVariables;
}

export type WorkflowStage =
  | 'init'
  | 'setup'
  | 'intake'
  | 'review'
  | 'content_review'
  | 'infra_review'
  | 'jira_sync'
  | 'development'
  | 'ready'
  | 'published'
  | 'error';

export interface WorkflowSummary {
  id: string;
  projectId: string;
  owner: string;
  ssoUser: string;
  ssoEmail: string;
  projectType: string;
  deploymentMode: string;
  stage: WorkflowStage;
  state: string;
  epicKey: string;
  jiraUrl: string;
  repoUrl: string;
  tags: string[];
  startedAt: string;
  lastUpdate: string;
}
