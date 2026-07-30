import { WorkflowNode, WorkflowStage } from '../api/types';
export declare function deriveStage(nodes: WorkflowNode[], processState: string): WorkflowStage;
export declare const STAGE_ORDER: WorkflowStage[];
export declare const STAGE_LABELS: Record<WorkflowStage, string>;
export declare const STAGE_DESCRIPTIONS: Record<string, string>;
export declare function stageIndex(stage: WorkflowStage): number;
//# sourceMappingURL=stageMapping.d.ts.map