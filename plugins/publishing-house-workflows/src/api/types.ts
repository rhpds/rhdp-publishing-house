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
    baselineSha?: string;
    hasDrift?: boolean;
    auditTrailSha?: string;
    reviewHistory?: AuditEntry[];
    agnosticvUrls?: string[];
    ciUrls?: string[];
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
  | 'env_setup'
  | 'development'
  | 'testing'
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

export interface RcarsMatch {
  ci_name: string;
  display_name: string;
  url: string;
  title?: string;
  relevance_score?: number;
  why_it_fits?: string;
}

export interface ApprovalChecklist {
  content?: {
    prerequisites_verifiable?: boolean | null;
    assessment_strategy?: string;
    catalog_gap?: string;
    design_overview?: string;
    module_summaries?: Array<{ title: string; overview: string }>;
    rcars_overlap_pct?: number | null;
    rcars_top_matches?: RcarsMatch[];
    rejections?: any[];
  };
  infra?: {
    peak_environments?: number | null;
    cost_per_run_est?: string;
    provisioning_time_est?: string;
    agnosticv_base_ci?: string;
    approved_by?: string;
    rejections?: any[];
  };
}

export interface VmSpec {
  role: string;
  count: number;
  cpu: number;
  ram_gb: number;
  disk_gb: number;
  os: string;
}

export interface SpecEnvironment {
  platform?: string;
  topology?: string;
  ocp_version?: string;
  cloud_provider?: string;
  vms_per_student?: VmSpec[];
  cluster_type?: string;
  control_plane_instance_count?: number;
  control_plane_cpu?: number;
  control_plane_ram_gb?: number;
  worker_count?: number | null;
  worker_cpu?: number | null;
  worker_ram_gb?: number | null;
  worker_disk_gb?: number | null;
  max_concurrent_users?: number | null;
  ai_requirement?: string;
  ai_model_tier?: string;
  ai_model_name?: string;
  ai_justification?: string;
  aap_version?: string;
  external_services?: string[];
  non_ga_products?: string[];
  non_ga_access_plan?: string;
  gpu_nodes?: number;
  gpu_type?: string;
}

export interface ValidationReport {
  passed: boolean;
  results: ValidationCheck[];
  auto_computed?: AutoComputedFields;
  commit_sha?: string;
  approval_checklist?: ApprovalChecklist;
  repo_url?: string;
  spec_environment?: SpecEnvironment;
}

export interface AuditEntry {
  user: string;
  stage: string;
  action: string;
  timestamp: string;
  commitSha?: string;
}

export interface DeleteProjectResult {
  slug: string;
  workflow_aborted: boolean;
  db_cleaned: boolean;
  catalog_cleaned: boolean;
  litellm_keys_deleted: number;
  jira_archived: boolean;
  repo_deleted: boolean;
  errors: string[];
}

export interface DriftChange {
  file: string;
  comparing: string;
  difference: string;
  severity?: 'info' | 'warning' | 'critical';
}

export interface DriftReport {
  has_drift: boolean;
  baseline_sha: string;
  current_sha: string;
  summary: string;
  changes: DriftChange[];
}

export interface ReviewMessage {
  id: string;
  title: string;
  text: string;
  origin: string;
  stage: string;
  timestamp: string;
  read: boolean;
}

export interface TokenInfo {
  email: string;
  groups_bitmask: number;
  group_names: string[];
  issued_at: string;
  expires_at: string;
  source: string;
}

export interface TokenListResponse {
  tokens: TokenInfo[];
  count: number;
}

export interface RevokeResponse {
  revoked: boolean;
  email: string | null;
}

export interface RevokeAllResponse {
  revoked_count: number;
}

export interface TestingComment {
  author: string;
  text: string;
  created: string;
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
  hasDrift?: boolean;
  baselineSha?: string;
  intakeType: string;
}
