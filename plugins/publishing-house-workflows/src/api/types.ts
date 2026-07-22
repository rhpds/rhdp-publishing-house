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
    contentType: string;
    createdAt: number;
    epic_key?: string;
    jira_url?: string;
    tags?: string[];
    projectDescription?: string;
    activeCommitSha?: string;
    reviewHistory?: AuditEntry[];
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

export interface RejectionReason {
  id: number;
  text: string;
}

export interface RejectionData {
  rejectionId: string;
  reviewerName: string;
  reviewerStage: WorkflowStage;
  timestamp: string;
  reasons: RejectionReason[];
}

export type CheckStatus = 'pass' | 'fail' | 'skip' | 'warn';

export interface ValidationCheck {
  check_id: string;
  group: string;
  status: CheckStatus;
  message: string;
  field?: string;
}

export interface AutoComputedFields {
  peak_environments?: number;
  cost_per_run_est?: number;
  provisioning_time_min?: number;
}

export interface ValidationReport {
  passed: boolean;
  results: ValidationCheck[];
  auto_computed?: AutoComputedFields;
  commit_sha?: string;
}

export interface AuditEntry {
  user: string;
  stage: string;
  action: string;
  timestamp: string;
  commitSha?: string;
}

export interface WorkflowSummary {
  id: string;
  projectId: string;
  owner: string;
  ssoUser: string;
  ssoEmail: string;
  contentType: string;
  deploymentMode: string;
  stage: WorkflowStage;
  state: string;
  epicKey: string;
  jiraUrl: string;
  repoUrl: string;
  tags: string[];
  projectDescription: string;
  startedAt: string;
  lastUpdate: string;
}
