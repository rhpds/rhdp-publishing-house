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
  discoveryApiRef,
  fetchApiRef,
  useApi,
} from '@backstage/core-plugin-api';
import { catalogApiRef } from '@backstage/plugin-catalog-react';
import { Entity } from '@backstage/catalog-model';
import {
  IconButton,
  Tooltip,
  makeStyles,
} from '@material-ui/core';
import RefreshIcon from '@material-ui/icons/Refresh';
import DeleteIcon from '@material-ui/icons/Delete';
import { DeleteDialog } from './DeleteDialog';
import { createPhMaintenanceClient, WorkflowInfo } from '../api/client';

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
}

function toRow(entity: Entity, wfMap: Record<string, WorkflowInfo>): ComponentRow {
  const annotations = entity.metadata?.annotations ?? {};
  const slug = annotations['github.com/project-slug'] ?? '';
  const repoUrl = slug ? `https://github.com/${slug}` : '';
  const name = entity.metadata?.name ?? '';

  const wf = wfMap[name];
  const owner = annotations['ph.rhdp.io/owner'] ?? '';

  // Jira: check annotations first, fall back to workflow data
  const annJiraUrl = Object.values(annotations).find(v => typeof v === 'string' && v.includes('atlassian.net/browse/')) ?? '';
  const jiraUrl = annJiraUrl || wf?.jiraUrl || '';
  const jiraLabel = jiraUrl ? (jiraUrl.split('/').pop() ?? 'Epic') : '';

  return {
    entity,
    name,
    description: entity.metadata?.description ?? '',
    owner,
    repoUrl,
    jiraUrl,
    jiraLabel,
    contentType: annotations['ph.rhdp.io/content-type'] ?? '',
  };
}

export function MaintenancePage() {
  const classes = useStyles();
  const catalogApi = useApi(catalogApiRef);
  const discoveryApi = useApi(discoveryApiRef);
  const fetchApi = useApi(fetchApiRef);
  const [refreshKey, setRefreshKey] = useState(0);
  const [deleteTarget, setDeleteTarget] = useState<Entity | null>(null);

  const client = createPhMaintenanceClient({ discoveryApi, fetchApi });

  const { value, loading, error } = useAsync(async () => {
    const [catalogResult, wfMap] = await Promise.all([
      catalogApi.getEntities({
        filter: { kind: 'Component', 'metadata.tags': 'publishing-house' },
        fields: [
          'metadata.name',
          'metadata.description',
          'metadata.uid',
          'metadata.annotations',
          'metadata.tags',
          'kind',
        ],
      }),
      client.getWorkflowMap(),
    ]);
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
      render: (row: ComponentRow) => (
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

  return (
    <Page themeId="tool">
      <Header title="Publishing House" subtitle="Component maintenance and cleanup">
        <HeaderLabel label="Components" value={String(entities.length)} />
      </Header>
      <Content>
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
      </Content>
    </Page>
  );
}
