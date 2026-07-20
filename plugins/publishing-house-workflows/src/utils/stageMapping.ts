import { WorkflowNode, WorkflowStage } from '../api/types';

export function deriveStage(
  nodes: WorkflowNode[],
  processState: string,
): WorkflowStage {
  if (processState === 'COMPLETED') return 'published';
  if (processState === 'ERROR') return 'error';

  let best: WorkflowStage = 'intake';
  let bestIdx = -1;

  for (const node of nodes) {
    if (node.enter && !node.exit) {
      const name = node.name.toLowerCase();
      let candidate: WorkflowStage | undefined;
      if (name === 'contentreview') candidate = 'content_review';
      else if (name === 'infrareview') candidate = 'infra_review';
      else if (name === 'jirasync') candidate = 'jira_sync';
      else if (name.includes('createepic')) candidate = 'setup';
      else if (name.includes('development') || name.includes('writing'))
        candidate = 'development';
      else if (name.includes('ready') || name.includes('final'))
        candidate = 'ready';
      else if (name.includes('publish')) candidate = 'published';

      if (candidate) {
        const idx = STAGE_ORDER.indexOf(candidate);
        if (idx > bestIdx) {
          best = candidate;
          bestIdx = idx;
        }
      }
    }
  }
  return best;
}

export const STAGE_ORDER: WorkflowStage[] = [
  'intake',
  'content_review',
  'infra_review',
  'development',
  'ready',
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
  ready: 'Ready',
  published: 'Published',
  error: 'Error',
};

export const STAGE_DESCRIPTIONS: Record<string, string> = {
  intake: 'The project spec, design document, and module outlines are being authored via the intake skill.',
  content_review: 'The design spec and module outlines are being reviewed for completeness and accuracy. A reviewer must approve or reject before proceeding.',
  infra_review: 'Infrastructure requirements (cluster type, sizing, workloads) are being reviewed. A reviewer must approve or reject before proceeding.',
  development: 'Lab content is being developed. The author is writing the actual lab modules and showroom content.',
  ready: 'Development is complete. The project is ready to be published to the RHDP catalog.',
  published: 'The project has been published to the RHDP catalog and is available to users.',
  error: 'The workflow encountered an error. Check the Orchestrator logs for details.',
};

export function stageIndex(stage: WorkflowStage): number {
  const idx = STAGE_ORDER.indexOf(stage);
  return idx >= 0 ? idx : 0;
}
