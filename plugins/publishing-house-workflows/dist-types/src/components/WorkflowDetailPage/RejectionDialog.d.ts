import React from 'react';
import { WorkflowStage, RejectionData } from '../../api/types';
interface RejectionDialogProps {
    open: boolean;
    stage: WorkflowStage;
    reviewerName: string;
    submitting: boolean;
    onConfirm: (data: RejectionData) => void;
    onCancel: () => void;
}
export declare function RejectionDialog({ open, stage, reviewerName, submitting, onConfirm, onCancel, }: RejectionDialogProps): React.JSX.Element;
export {};
//# sourceMappingURL=RejectionDialog.d.ts.map