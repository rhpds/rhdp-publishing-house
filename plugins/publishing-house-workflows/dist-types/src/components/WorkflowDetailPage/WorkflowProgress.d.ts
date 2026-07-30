import React from 'react';
import { WorkflowStage } from '../../api/types';
interface WorkflowProgressProps {
    stage: WorkflowStage;
    rejectedFrom?: WorkflowStage | null;
    hasDrift?: boolean;
}
export declare function WorkflowProgress({ stage, hasDrift }: WorkflowProgressProps): React.JSX.Element;
export {};
//# sourceMappingURL=WorkflowProgress.d.ts.map