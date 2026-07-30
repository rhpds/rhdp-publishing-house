import { DiscoveryApi, FetchApi } from '@backstage/core-plugin-api';
import { ProcessInstance, WorkflowSummary, WorkflowStage, RejectionData, ValidationReport, DriftReport } from './types';
export declare function createPhWorkflowsClient(options: {
    discoveryApi: DiscoveryApi;
    fetchApi: FetchApi;
}): {
    getWorkflows: () => Promise<WorkflowSummary[]>;
    getWorkflow: (projectId: string) => Promise<{
        summary: WorkflowSummary;
        instance: ProcessInstance;
    } | undefined>;
    getWorkflowById: (workflowId: string) => Promise<{
        summary: WorkflowSummary;
        instance: ProcessInstance;
    } | undefined>;
    sendApprovalEvent: (workflowId: string, stage: WorkflowStage, projectId?: string, auditData?: {
        user: string;
        commitSha?: string;
    }) => Promise<void>;
    sendRejectionEvent: (workflowId: string, stage: WorkflowStage, rejectionData: RejectionData, projectId?: string, commitSha?: string) => Promise<void>;
    fetchValidationReport: (slug: string, repoUrl: string, branch?: string, baselineSha?: string) => Promise<ValidationReport>;
    fetchDriftReport: (slug: string, mode?: 'structural' | 'semantic') => Promise<DriftReport>;
    approveDrift: (slug: string) => Promise<{
        slug: string;
        baselineSha: string;
        cleared: boolean;
    }>;
    fetchHeadCommitSha: (repoUrl: string, branch?: string) => Promise<string | undefined>;
};
//# sourceMappingURL=client.d.ts.map