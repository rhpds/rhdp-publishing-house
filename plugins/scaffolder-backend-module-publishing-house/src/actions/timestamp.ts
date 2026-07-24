import { createTemplateAction } from '@backstage/plugin-scaffolder-node';
import * as fs from 'fs-extra';
import * as path from 'path';
import { parse, stringify } from 'yaml';

export function createTimestampAction() {
  return createTemplateAction({
    id: 'publishing-house:timestamp',
    description: 'Set ph.rhdp.io/created-at annotation to the current ISO timestamp',
    schema: {
      input: {
        entityFilePath: (z: any) => z.string().optional().default('./catalog-info.yaml').describe('Path to entity YAML'),
      },
      output: {
        timestamp: (z: any) => z.string().describe('The ISO timestamp that was set'),
      },
    },
    async handler(ctx) {
      const filePath = ctx.input.entityFilePath as string || './catalog-info.yaml';
      const fullPath = path.resolve(ctx.workspacePath, filePath);
      const content = await fs.readFile(fullPath, 'utf8');
      const entity = parse(content);

      if (!entity.metadata) {
        entity.metadata = {};
      }
      if (!entity.metadata.annotations) {
        entity.metadata.annotations = {};
      }

      const timestamp = new Date().toISOString();
      entity.metadata.annotations['ph.rhdp.io/created-at'] = timestamp;

      await fs.writeFile(fullPath, stringify(entity), 'utf8');

      ctx.logger.info(`Set ph.rhdp.io/created-at to ${timestamp}`);
      ctx.output('timestamp', timestamp);
    },
  });
}
