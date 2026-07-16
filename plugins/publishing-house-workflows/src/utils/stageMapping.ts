import { WorkflowNode, WorkflowStage } from '../api/types';

export function deriveStage(
  nodes: WorkflowNode[],
  processState: string,
): WorkflowStage {
  if (processState === 'COMPLETED') return 'published';
  if (processState === 'ERROR') return 'error';

  for (const node of nodes) {
    if (node.enter && !node.exit) {
      const name = node.name.toLowerCase();
      if (name === 'developmentreview') return 'development_review';
      if (name === 'contentreview') return 'content_review';
      if (name === 'infrareview') return 'infra_review';
      if (name.includes('createepic')) return 'setup';
      if (name.includes('development') || name.includes('writing'))
        return 'development';
      if (name.includes('ready') || name.includes('final')) return 'ready';
      if (name.includes('publish')) return 'published';
      if (name.includes('intake')) return 'intake';
      if (name.includes('setup')) return 'setup';
      if (name.includes('init')) return 'init';
    }
  }
  return 'intake';
}

export const STAGE_ORDER: WorkflowStage[] = [
  'intake',
  'development_review',
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
  development_review: 'Development Review',
  development: 'Development',
  ready: 'Ready',
  published: 'Published',
  error: 'Error',
};

export function stageIndex(stage: WorkflowStage): number {
  const idx = STAGE_ORDER.indexOf(stage);
  return idx >= 0 ? idx : 0;
}
