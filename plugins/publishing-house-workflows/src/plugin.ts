import {
  createPlugin,
  createRoutableExtension,
} from '@backstage/core-plugin-api';
import { rootRouteRef, driftRouteRef, maintenanceRouteRef } from './routes';

export const phWorkflowsPlugin = createPlugin({
  id: 'ph-workflows',
  routes: {
    root: rootRouteRef,
    drift: driftRouteRef,
    maintenance: maintenanceRouteRef,
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

export const PhDriftDashboardPage = phWorkflowsPlugin.provide(
  createRoutableExtension({
    name: 'PhDriftDashboardPage',
    component: () =>
      import('./components/DriftDashboardPage/DriftDashboardPage').then(
        m => m.DriftDashboardPage,
      ),
    mountPoint: driftRouteRef,
  }),
);

export const PhMaintenancePage = phWorkflowsPlugin.provide(
  createRoutableExtension({
    name: 'PhMaintenancePage',
    component: () =>
      import('./components/MaintenancePage/MaintenancePage').then(
        m => m.MaintenancePage,
      ),
    mountPoint: maintenanceRouteRef,
  }),
);
