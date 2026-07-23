import { WorkflowNode, WorkflowStage } from '../api/types';

const STATE_MAP: Record<string, WorkflowStage> = {
  createepic: 'intake',
  intake: 'intake',
  contentreview: 'content_review',
  contentreviewdecision: 'content_review',
  infrareview: 'infra_review',
  infrareviewdecision: 'infra_review',
  jirasync: 'jira_sync',
  development: 'development',
  driftcheck: 'development',
  driftdecision: 'development',
  driftreview: 'drift_review',
  driftreviewdecision: 'drift_review',
  testing: 'testing',
  published: 'published',
};

export function deriveStage(
  nodes: WorkflowNode[],
  processState: string,
): WorkflowStage {
  if (processState === 'COMPLETED') return 'published';
  if (processState === 'ERROR') return 'error';

  let best: WorkflowStage = 'intake';
  let latestEnter = '';

  for (const node of nodes) {
    if (node.type !== 'CompositeContextNode') continue;
    if (!node.enter || node.exit) continue;
    const candidate = STATE_MAP[node.name.toLowerCase()];
    if (candidate && node.enter > latestEnter) {
      best = candidate;
      latestEnter = node.enter;
    }
  }
  return best;
}

export const STAGE_ORDER: WorkflowStage[] = [
  'intake',
  'content_review',
  'infra_review',
  'development',
  'drift_review',
  'testing',
  'published',
];

export const STAGE_LABELS: Record<WorkflowStage, string> = {
  init: 'Init',
  setup: 'Setup',
  intake: 'Intake',
  review: 'Reviews',
  content_review: 'Content Review',
  infra_review: 'Infra Review',
  jira_sync: 'Jira Sync',
  development: 'Development',
  drift_review: 'Drift Review',
  testing: 'Testing',
  published: 'Published',
  error: 'Error',
};

export const STAGE_DESCRIPTIONS: Record<string, string> = {
  intake: 'The project spec, design document, and module outlines are being authored via the intake skill.',
  content_review: 'The design spec and module outlines are being reviewed for completeness and accuracy. A reviewer must approve or reject before proceeding.',
  infra_review: 'Infrastructure requirements (cluster type, sizing, workloads) are being reviewed. A reviewer must approve or reject before proceeding.',
  development: 'Lab content is being developed. The author is writing the actual lab modules and showroom content.',
  drift_review: 'Design changes were detected since the last approval. A reviewer must approve or reject the drift before proceeding to testing.',
  testing: 'Development is complete. The project is undergoing testing before release.',
  published: 'The project has been published to the RHDP catalog and is available to users.',
  error: 'The workflow encountered an error. Check the Orchestrator logs for details.',
};

export function stageIndex(stage: WorkflowStage): number {
  const idx = STAGE_ORDER.indexOf(stage);
  return idx >= 0 ? idx : 0;
}
