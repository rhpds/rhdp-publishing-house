import {
  coreServices,
  createBackendModule,
} from '@backstage/backend-plugin-api';
import { scaffolderActionsExtensionPoint } from '@backstage/plugin-scaffolder-node';
import { ScmIntegrations } from '@backstage/integration';
import { createGithubRepoFromTemplateAction } from './actions/createFromTemplate';

export default createBackendModule({
  pluginId: 'scaffolder',
  moduleId: 'github-template',
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
        );
      },
    });
  },
});
