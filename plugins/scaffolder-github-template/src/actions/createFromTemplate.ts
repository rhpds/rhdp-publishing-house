import { createTemplateAction } from '@backstage/plugin-scaffolder-node';
import { ScmIntegrations } from '@backstage/integration';
import { Octokit } from '@octokit/rest';
import git from 'isomorphic-git';
import http from 'isomorphic-git/http/node';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

function copyDirSync(src: string, dest: string) {
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    if (entry.name === '.git') continue;
    const s = path.join(src, entry.name);
    const d = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      fs.mkdirSync(d, { recursive: true });
      copyDirSync(s, d);
    } else {
      fs.copyFileSync(s, d);
    }
  }
}

async function poll(
  fn: () => Promise<boolean>,
  intervalMs: number,
  maxRetries: number,
): Promise<void> {
  for (let i = 0; i < maxRetries; i++) {
    if (await fn()) return;
    await new Promise(r => setTimeout(r, intervalMs));
  }
  throw new Error('Timed out waiting for repository to be ready');
}

export function createGithubRepoFromTemplateAction(options: {
  integrations: ScmIntegrations;
}) {
  const { integrations } = options;

  return createTemplateAction({
    id: 'github:repo:create-from-template',
    description: 'Create a GitHub repo from a template, overlay workspace files, commit and push',
    schema: {
      input: {
        repoUrl: (z: any) => z.string({ description: 'github.com?owner=X&repo=Y' }),
        templateRepo: (z: any) => z.string({ description: 'owner/repo of the template' }),
        description: (z: any) => z.string({ description: 'Repository description' }).optional(),
        defaultBranch: (z: any) => z.string({ description: 'Default branch' }).default('main'),
        repoVisibility: (z: any) => z.enum(['public', 'private']).default('public'),
        gitCommitMessage: (z: any) => z.string({ description: 'Commit message' }).default('Add skeleton artifacts'),
        sourcePath: (z: any) => z.string({ description: 'Source path within workspace' }).optional(),
        gitAuthorName: (z: any) => z.string({ description: 'Git author name' }).default('Scaffolder'),
        gitAuthorEmail: (z: any) => z.string({ description: 'Git author email' }).default('scaffolder@backstage.io'),
        collaborators: (z: any) => z.array(
          z.object({
            user: z.string({ description: 'GitHub username' }),
            access: z.string({ description: 'Permission level' }).default('push'),
          }),
        ).optional(),
      },
      output: {
        remoteUrl: (z: any) => z.string({ description: 'Remote URL' }),
        repoContentsUrl: (z: any) => z.string({ description: 'Repo contents URL' }),
        commitHash: (z: any) => z.string({ description: 'Commit hash' }),
      },
    },
    async handler(ctx) {
      const repoUrl = ctx.input.repoUrl as string;
      const templateRepo = ctx.input.templateRepo as string;
      const description = (ctx.input.description as string) || '';
      const defaultBranch = (ctx.input.defaultBranch as string) || 'main';
      const repoVisibility = (ctx.input.repoVisibility as string) || 'public';
      const gitCommitMessage = (ctx.input.gitCommitMessage as string) || 'Add skeleton artifacts';
      const sourcePath = ctx.input.sourcePath as string | undefined;
      const gitAuthorName = (ctx.input.gitAuthorName as string) || 'Scaffolder';
      const gitAuthorEmail = (ctx.input.gitAuthorEmail as string) || 'scaffolder@backstage.io';
      const collaborators = (ctx.input.collaborators as Array<{ user: string; access: string }>) || [];

      const url = new URL(`https://${repoUrl}`);
      const owner = url.searchParams.get('owner');
      const repo = url.searchParams.get('repo');
      if (!owner || !repo) {
        throw new Error(`Invalid repoUrl: ${repoUrl}`);
      }

      const [templateOwner, templateName] = templateRepo.split('/');
      if (!templateOwner || !templateName) {
        throw new Error(`Invalid templateRepo: ${templateRepo}. Expected owner/repo format.`);
      }

      const integration = integrations.github.byUrl(`https://github.com/${owner}/${repo}`);
      if (!integration) {
        throw new Error('No GitHub integration configured');
      }

      const token = integration.config.token;
      if (!token) {
        throw new Error('No GitHub token available from integration');
      }

      const octokit = new Octokit({ auth: token });

      ctx.logger.info(`Creating repo ${owner}/${repo} from template ${templateRepo}`);
      await octokit.repos.createUsingTemplate({
        template_owner: templateOwner,
        template_repo: templateName,
        owner,
        name: repo,
        description,
        private: repoVisibility === 'private',
        include_all_branches: false,
      });

      for (const collab of collaborators) {
        ctx.logger.info(`Adding collaborator ${collab.user} with ${collab.access || 'push'} access`);
        await octokit.repos.addCollaborator({
          owner,
          repo,
          username: collab.user,
          permission: (collab.access || 'push') as 'pull' | 'push' | 'admin' | 'maintain' | 'triage',
        });
      }

      ctx.logger.info('Waiting for repository to initialize...');
      await poll(
        async () => {
          try {
            await octokit.git.getRef({ owner, repo, ref: `heads/${defaultBranch}` });
            return true;
          } catch {
            return false;
          }
        },
        2000,
        15,
      );

      const cloneDir = fs.mkdtempSync(path.join(os.tmpdir(), 'scaffolder-template-'));
      const remoteUrl = `https://github.com/${owner}/${repo}.git`;

      try {
        ctx.logger.info('Cloning repository...');
        await git.clone({
          fs,
          http,
          dir: cloneDir,
          url: remoteUrl,
          ref: defaultBranch,
          singleBranch: true,
          depth: 1,
          onAuth: () => ({ username: 'x-access-token', password: token }),
        });

        const workspacePath = sourcePath
          ? path.resolve(ctx.workspacePath, sourcePath)
          : ctx.workspacePath;

        ctx.logger.info('Overlaying workspace files...');
        copyDirSync(workspacePath, cloneDir);

        await git.add({ fs, dir: cloneDir, filepath: '.' });

        const commitHash = await git.commit({
          fs,
          dir: cloneDir,
          message: gitCommitMessage,
          author: { name: gitAuthorName, email: gitAuthorEmail },
          committer: { name: gitAuthorName, email: gitAuthorEmail },
        });

        ctx.logger.info('Pushing to remote...');
        await git.push({
          fs,
          http,
          dir: cloneDir,
          remote: 'origin',
          ref: defaultBranch,
          onAuth: () => ({ username: 'x-access-token', password: token }),
        });

        ctx.logger.info(`Push complete. Commit: ${commitHash}`);

        ctx.output('remoteUrl', `https://github.com/${owner}/${repo}`);
        ctx.output('repoContentsUrl', `https://github.com/${owner}/${repo}/tree/${defaultBranch}`);
        ctx.output('commitHash', commitHash);
      } finally {
        fs.rmdirSync(cloneDir, { recursive: true });
      }
    },
  });
}
