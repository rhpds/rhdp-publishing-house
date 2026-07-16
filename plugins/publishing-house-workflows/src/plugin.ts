import {
  createPlugin,
  createRoutableExtension,
} from '@backstage/core-plugin-api';
import { rootRouteRef } from './routes';

export const phWorkflowsPlugin = createPlugin({
  id: 'ph-workflows',
  routes: {
    root: rootRouteRef,
  },
});

export const PhWorkflowsPage = phWorkflowsPlugin.provide(
  createRoutableExtension({
    name: 'PhWorkflowsPage',
    component: () =>
      import('./components/Router').then(m => m.Router),
    mountPoint: rootRouteRef,
  }),
);
