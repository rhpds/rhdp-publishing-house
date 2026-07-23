import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
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
import {
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Chip,
  makeStyles,
  TextField,
  IconButton,
  Tooltip,
} from '@material-ui/core';
import RefreshIcon from '@material-ui/icons/Refresh';
import { createPhWorkflowsClient } from '../../api/client';
import { WorkflowSummary, WorkflowStage } from '../../api/types';
import { STAGE_LABELS, STAGE_ORDER } from '../../utils/stageMapping';

const useStyles = makeStyles(theme => ({
  filters: {
    display: 'flex',
    gap: theme.spacing(2),
    marginBottom: theme.spacing(2),
    flexWrap: 'wrap' as const,
    alignItems: 'center',
  },
  filterControl: {
    minWidth: 160,
  },
  searchField: {
    minWidth: 220,
  },
  chip: {
    fontWeight: 600,
    fontSize: '0.75rem',
  },
}));

function StageChip({ stage }: { stage: WorkflowStage }) {
  const classes = useStyles();
  const label = STAGE_LABELS[stage] || stage;
  const chipStyle: React.CSSProperties =
    stage === 'published'
      ? { backgroundColor: '#4caf50', color: '#fff' }
      : stage === 'error'
        ? { backgroundColor: '#f44336', color: '#fff' }
        : {};

  return (
    <Chip
      label={label}
      size="small"
      color={stage === 'review' || stage === 'ready' ? 'primary' : stage === 'development' ? 'secondary' : 'default'}
      className={classes.chip}
      style={chipStyle}
    />
  );
}

const columns: TableColumn<WorkflowSummary>[] = [
  {
    title: 'Project ID',
    field: 'projectId',
    highlight: true,
  },
  {
    title: 'Owner',
    field: 'owner',
  },
  {
    title: 'Type',
    field: 'contentType',
  },
  {
    title: 'Stage',
    field: 'stage',
    render: (row: WorkflowSummary) => <StageChip stage={row.stage} />,
  },
  {
    title: 'Tags',
    field: 'tags',
    render: (row: WorkflowSummary) =>
      row.tags.length > 0 ? (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
          {row.tags.map(tag => (
            <Chip key={tag} label={tag} size="small" variant="outlined" style={{ margin: 2, height: 22, fontSize: '0.7rem' }} />
          ))}
        </div>
      ) : (
        '—'
      ),
  },
  {
    title: 'Jira',
    field: 'epicKey',
    render: (row: WorkflowSummary) =>
      row.epicKey ? (
        <a href={row.jiraUrl} target="_blank" rel="noopener noreferrer">
          {row.epicKey}
        </a>
      ) : (
        '—'
      ),
  },
  {
    title: 'Started',
    field: 'startedAt',
    render: (row: WorkflowSummary) =>
      row.startedAt
        ? new Date(row.startedAt).toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
          })
        : '—',
    defaultSort: 'desc' as const,
  },
  {
    title: 'Last Updated',
    field: 'lastUpdate',
    render: (row: WorkflowSummary) =>
      row.lastUpdate
        ? new Date(row.lastUpdate).toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
          })
        : '—',
  },
];

export function WorkflowListPage() {
  const classes = useStyles();
  const navigate = useNavigate();
  const discoveryApi = useApi(discoveryApiRef);
  const fetchApi = useApi(fetchApiRef);
  const [stageFilter, setStageFilter] = useState<string>('ALL');
  const [searchText, setSearchText] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);

  const client = createPhWorkflowsClient({ discoveryApi, fetchApi });

  const { value: workflows, loading, error } = useAsync(
    () => client.getWorkflows(),
    [refreshKey],
  );

  const handleRefresh = useCallback(() => {
    setRefreshKey(k => k + 1);
  }, []);

  const filtered = (workflows ?? []).filter(w => {
    if (stageFilter !== 'ALL' && w.stage !== stageFilter) return false;
    if (searchText) {
      const term = searchText.toLowerCase();
      const match =
        w.projectId.toLowerCase().includes(term) ||
        w.owner.toLowerCase().includes(term) ||
        w.ssoUser.toLowerCase().includes(term) ||
        w.epicKey.toLowerCase().includes(term) ||
        w.tags.some(t => t.toLowerCase().includes(term));
      if (!match) return false;
    }
    return true;
  });

  return (
    <Page themeId="tool">
      <Header title="Publishing House" subtitle="Content lifecycle workflows">
        <HeaderLabel label="Workflows" value={String(workflows?.length ?? 0)} />
      </Header>
      <Content>
        <ContentHeader title="Projects">
          <Tooltip title="Refresh">
            <IconButton onClick={handleRefresh} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </ContentHeader>
        <div className={classes.filters}>
          <TextField
            variant="outlined"
            size="small"
            label="Search"
            placeholder="Project ID, owner, Jira..."
            className={classes.searchField}
            value={searchText}
            onChange={e => setSearchText(e.target.value)}
          />
          <FormControl variant="outlined" size="small" className={classes.filterControl}>
            <InputLabel>Stage</InputLabel>
            <Select
              value={stageFilter}
              onChange={e => setStageFilter(e.target.value as string)}
              label="Stage"
            >
              <MenuItem value="ALL">All Stages</MenuItem>
              {STAGE_ORDER.map(s => (
                <MenuItem key={s} value={s}>
                  {STAGE_LABELS[s]}
                </MenuItem>
              ))}
              <MenuItem value="error">Error</MenuItem>
            </Select>
          </FormControl>
        </div>
        <Table<WorkflowSummary>
          title="Workflow Instances"
          options={{
            search: false,
            paging: true,
            pageSize: 20,
            padding: 'dense',
          }}
          columns={columns}
          data={filtered}
          isLoading={loading}
          emptyContent={
            error ? (
              <div style={{ padding: 16 }}>
                Failed to load workflows: {error.message}
              </div>
            ) : undefined
          }
          onRowClick={(_event, rowData) => {
            if (rowData) {
              navigate(`/publishing-house-workflows/${rowData.id}`);
            }
          }}
        />
      </Content>
    </Page>
  );
}
