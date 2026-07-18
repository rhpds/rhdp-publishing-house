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

export function stageIndex(stage: WorkflowStage): number {
  const idx = STAGE_ORDER.indexOf(stage);
  return idx >= 0 ? idx : 0;
}
