import {
  coreServices,
  createBackendModule,
} from '@backstage/backend-plugin-api';
import { scaffolderActionsExtensionPoint } from '@backstage/plugin-scaffolder-node';
import { ScmIntegrations } from '@backstage/integration';
import { createGithubRepoFromTemplateAction } from './actions/createFromTemplate';
import { createAnnotateAction } from './actions/annotate';
import { createTimestampAction } from './actions/timestamp';

export default createBackendModule({
  pluginId: 'scaffolder',
  moduleId: 'publishing-house',
  register({ registerInit }) {
    registerInit({
      deps: {
        scaffolder: scaffolderActionsExtensionPoint,
        config: coreServices.rootConfig,
      },
      async init({ scaffolder, config }) {
        const integrations = ScmIntegrations.fromConfig(config);
        scaffolder.addActions(
          createGithubRepoFromTemplateAction({ integrations }),
          createAnnotateAction(),
          createTimestampAction(),
        );
      },
    });
  },
});
