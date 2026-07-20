import { createRouteRef, createSubRouteRef } from '@backstage/core-plugin-api';

export const rootRouteRef = createRouteRef({
  id: 'ph-workflows',
});

export const detailRouteRef = createSubRouteRef({
  id: 'ph-workflows-detail',
  parent: rootRouteRef,
  path: '/:workflowId',
});
