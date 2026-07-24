import {
  createPlugin,
  createRoutableExtension,
} from '@backstage/core-plugin-api';
import { rootRouteRef } from './routes';

export const phMaintenancePlugin = createPlugin({
  id: 'ph-maintenance',
  routes: {
    root: rootRouteRef,
  },
});

export const PhMaintenancePage = phMaintenancePlugin.provide(
  createRoutableExtension({
    name: 'PhMaintenancePage',
    component: () =>
      import('./components/MaintenancePage').then(m => m.MaintenancePage),
    mountPoint: rootRouteRef,
  }),
);
