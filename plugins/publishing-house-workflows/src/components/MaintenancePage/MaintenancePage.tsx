import React, { useState, useCallback } from 'react';
import { useAsync } from 'react-use';
import {
  Content,
  ContentHeader,
  Header,
  HeaderLabel,
  Page,
  Table,
  TableColumn,
} from '@backstage/core-components';
import {
  configApiRef,
  discoveryApiRef,
  fetchApiRef,
  identityApiRef,
  useApi,
} from '@backstage/core-plugin-api';
import { catalogApiRef } from '@backstage/plugin-catalog-react';
import { Entity } from '@backstage/catalog-model';
import {
  IconButton,
  Tab,
  Tabs,
  Tooltip,
  Typography,
  makeStyles,
} from '@material-ui/core';
import RefreshIcon from '@material-ui/icons/Refresh';
import DeleteIcon from '@material-ui/icons/Delete';
import LockIcon from '@material-ui/icons/Lock';
import { DeleteDialog } from './DeleteDialog';
import { TokenManagementTab } from './TokenManagementTab';
import { createPhWorkflowsClient } from '../../api/client';
import { WorkflowSummary } from '../../api/types';
import { useUserGroups } from '../../hooks/useUserGroups';

const useStyles = makeStyles(theme => ({
  deleteButton: {
    color: theme.palette.error.main,
  },
}));

interface ComponentRow {
  entity: Entity;
  name: string;
  description: string;
  owner: string;
  repoUrl: string;
  jiraUrl: string;
  jiraLabel: string;
  contentType: string;
  createdAt: string;
  workflowState: string;
}

function toRow(entity: Entity, wfMap: Record<string, WorkflowSummary>): ComponentRow {
  const annotations = entity.metadata?.annotations ?? {};
  const slug = annotations['github.com/project-slug'] ?? '';
  const repoUrl = slug ? `https://github.com/${slug}` : '';
  const name = entity.metadata?.name ?? '';

  const wf = wfMap[name];
  const owner = annotations['ph.rhdp.io/owner'] ?? '';

  const links = (entity.metadata as any)?.links ?? [];
  const jiraLink = links.find((l: any) => l.title === 'Jira Epic' || (l.url && l.url.includes('atlassian.net/browse/')));
  const jiraUrl = jiraLink?.url || wf?.jiraUrl || '';
  const jiraLabel = jiraUrl ? (jiraUrl.split('/').pop() ?? 'Epic') : '';

  const rawTs = annotations['ph.rhdp.io/created-at'] ?? '';
  let createdAt = '';
  if (rawTs) {
    try { createdAt = new Date(rawTs).toLocaleDateString(); } catch { createdAt = rawTs; }
  }

  return {
    entity,
    name,
    description: entity.metadata?.description ?? '',
    owner,
    repoUrl,
    jiraUrl,
    jiraLabel,
    contentType: annotations['ph.rhdp.io/content-type'] ?? '',
    createdAt,
    workflowState: wf?.state ?? '',
  };
}

export function MaintenancePage() {
  const classes = useStyles();
  const catalogApi = useApi(catalogApiRef);
  const configApi = useApi(configApiRef);
  const discoveryApi = useApi(discoveryApiRef);
  const fetchApi = useApi(fetchApiRef);
  const identityApi = useApi(identityApiRef);
  const centralApiUrl = configApi.getString('phWorkflows.centralApiUrl');
  const { isAdmin, loading: groupsLoading } = useUserGroups();
  const [activeTab, setActiveTab] = useState(0);
  const [refreshKey, setRefreshKey] = useState(0);
  const [deleteTarget, setDeleteTarget] = useState<Entity | null>(null);

  const client = createPhWorkflowsClient({ centralApiUrl, discoveryApi, fetchApi, identityApi });

  const { value, loading, error } = useAsync(async () => {
    const [catalogResult, workflows] = await Promise.all([
      catalogApi.getEntities({
        filter: { kind: 'Component', 'metadata.tags': 'publishing-house' },
        fields: [
          'metadata.name',
          'metadata.description',
          'metadata.uid',
          'metadata.annotations',
          'metadata.links',
          'metadata.tags',
          'kind',
        ],
      }),
      client.getWorkflows(),
    ]);
    const wfMap: Record<string, WorkflowSummary> = {};
    for (const w of workflows) {
      if (w.projectId) wfMap[w.projectId] = w;
    }
    const projects = catalogResult.items.filter(e => {
      const ann = e.metadata?.annotations ?? {};
      return ann['ph.rhdp.io/owner'] || ann['ph.rhdp.io/content-type'];
    });
    return { entities: projects, wfMap };
  }, [refreshKey]);

  const handleRefresh = useCallback(() => {
    setRefreshKey(k => k + 1);
  }, []);

  const entities = value?.entities ?? [];
  const wfMap = value?.wfMap ?? {};
  const rows = entities.map(e => toRow(e, wfMap));

  const columns: TableColumn<ComponentRow>[] = [
    {
      title: 'Name',
      field: 'name',
      highlight: true,
    },
    {
      title: 'Owner',
      field: 'owner',
      render: (row: ComponentRow) => row.owner || '—',
    },
    {
      title: 'Description',
      field: 'description',
      render: (row: ComponentRow) =>
        row.description.length > 80
          ? `${row.description.slice(0, 80)}...`
          : row.description || '—',
    },
    {
      title: 'Type',
      field: 'contentType',
    },
    {
      title: 'Created',
      field: 'createdAt',
      render: (row: ComponentRow) => row.createdAt || '—',
    },
    {
      title: 'Repo',
      field: 'repoUrl',
      render: (row: ComponentRow) =>
        row.repoUrl ? (
          <a href={row.repoUrl} target="_blank" rel="noopener noreferrer">
            {row.repoUrl}
          </a>
        ) : (
          '—'
        ),
    },
    {
      title: 'Jira',
      field: 'jiraLabel',
      render: (row: ComponentRow) =>
        row.jiraUrl ? (
          <a href={row.jiraUrl} target="_blank" rel="noopener noreferrer">
            {row.jiraLabel}
          </a>
        ) : (
          '—'
        ),
    },
    {
      title: 'Actions',
      field: 'name',
      sorting: false,
      render: (row: ComponentRow) =>
        row.workflowState === 'COMPLETED' ? (
          <Typography variant="caption" color="textSecondary">Completed</Typography>
        ) : (
          <Tooltip title="Delete component and resources">
            <IconButton
              size="small"
              className={classes.deleteButton}
              onClick={e => {
                e.stopPropagation();
                setDeleteTarget(row.entity);
              }}
            >
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        ),
    },
  ];

  if (!groupsLoading && !isAdmin) {
    return (
      <Page themeId="tool">
        <Header title="Publishing House" subtitle="Component maintenance and cleanup" />
        <Content>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: 64, gap: 16 }}>
            <LockIcon style={{ fontSize: 48, color: '#757575' }} />
            <Typography variant="h6" color="textSecondary">Access Restricted</Typography>
            <Typography variant="body2" color="textSecondary">
              This page is only available to members of rhdp-administrators.
            </Typography>
          </div>
        </Content>
      </Page>
    );
  }

  return (
    <Page themeId="tool">
      <Header title="Publishing House" subtitle="Maintenance and administration">
        <HeaderLabel label="Components" value={String(entities.length)} />
      </Header>
      <Content>
        <Tabs
          value={activeTab}
          onChange={(_e, v) => setActiveTab(v)}
          indicatorColor="primary"
          textColor="primary"
          style={{ marginBottom: 16 }}
        >
          <Tab label="Components" />
          <Tab label="Token Management" />
        </Tabs>

        {activeTab === 0 && (
          <>
            <ContentHeader title="Registered Components">
              <Tooltip title="Refresh">
                <IconButton onClick={handleRefresh} disabled={loading}>
                  <RefreshIcon />
                </IconButton>
              </Tooltip>
            </ContentHeader>
            <Table<ComponentRow>
              title="Publishing House Components"
              options={{
                search: true,
                paging: true,
                pageSize: 20,
                padding: 'dense',
              }}
              columns={columns}
              data={rows}
              isLoading={loading}
              emptyContent={
                error ? (
                  <div style={{ padding: 16 }}>
                    Failed to load components: {error.message}
                  </div>
                ) : undefined
              }
            />
            <DeleteDialog
              open={!!deleteTarget}
              entity={deleteTarget}
              onClose={() => setDeleteTarget(null)}
              onDeleted={() => {
                setDeleteTarget(null);
                handleRefresh();
              }}
            />
          </>
        )}

        {activeTab === 1 && <TokenManagementTab />}
      </Content>
    </Page>
  );
}
