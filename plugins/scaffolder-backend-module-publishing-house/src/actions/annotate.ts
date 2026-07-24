import { createTemplateAction } from '@backstage/plugin-scaffolder-node';
import * as fs from 'fs-extra';
import * as path from 'path';
import { parse, stringify } from 'yaml';

export function createAnnotateAction() {
  return createTemplateAction({
    id: 'publishing-house:annotate',
    description: 'Annotate an entity YAML file with labels, annotations, and spec properties',
    schema: {
      input: {
        annotations: (z: any) => z.record(z.string()).optional().describe('Annotations to merge'),
        labels: (z: any) => z.record(z.string()).optional().describe('Labels to merge'),
        spec: (z: any) => z.record(z.any()).optional().describe('Spec properties to merge'),
        entityFilePath: (z: any) => z.string().optional().default('./catalog-info.yaml').describe('Path to entity YAML'),
      },
      output: {
        annotatedObject: (z: any) => z.string().describe('The annotated YAML string'),
      },
    },
    async handler(ctx) {
      const filePath = ctx.input.entityFilePath as string || './catalog-info.yaml';
      const annotations = (ctx.input.annotations as Record<string, string>) || {};
      const labels = (ctx.input.labels as Record<string, string>) || {};
      const spec = (ctx.input.spec as Record<string, any>) || {};

      const fullPath = path.resolve(ctx.workspacePath, filePath);
      const content = await fs.readFile(fullPath, 'utf8');
      const entity = parse(content);

      if (!entity.metadata) {
        entity.metadata = {};
      }

      if (Object.keys(annotations).length > 0) {
        entity.metadata.annotations = {
          ...(entity.metadata.annotations || {}),
          ...annotations,
        };
      }

      if (Object.keys(labels).length > 0) {
        entity.metadata.labels = {
          ...(entity.metadata.labels || {}),
          ...labels,
        };
      }

      if (Object.keys(spec).length > 0) {
        entity.spec = {
          ...(entity.spec || {}),
          ...spec,
        };
      }

      const result = stringify(entity);
      await fs.writeFile(fullPath, result, 'utf8');

      ctx.logger.info(`Annotated ${filePath}`);
      ctx.output('annotatedObject', result);
    },
  });
}
