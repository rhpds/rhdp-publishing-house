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
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  IconButton,
  makeStyles,
  Tooltip,
  Typography,
} from '@material-ui/core';
import { Alert } from '@material-ui/lab';
import RefreshIcon from '@material-ui/icons/Refresh';
import CheckCircleIcon from '@material-ui/icons/CheckCircle';
import { createPhWorkflowsClient } from '../../api/client';
import { WorkflowSummary, DriftReport } from '../../api/types';
import { STAGE_LABELS } from '../../utils/stageMapping';

const useStyles = makeStyles(theme => ({
  chip: {
    fontWeight: 600,
    fontSize: '0.75rem',
  },
  driftDetails: {
    padding: theme.spacing(2),
    backgroundColor: theme.palette.background.default,
    borderRadius: theme.shape.borderRadius,
    marginTop: theme.spacing(1),
  },
  changesTable: {
    width: '100%',
    borderCollapse: 'collapse' as const,
    marginTop: theme.spacing(1),
    '& th, & td': {
      padding: theme.spacing(1),
      textAlign: 'left' as const,
      borderBottom: `1px solid ${theme.palette.divider}`,
      fontSize: '0.85rem',
    },
    '& th': {
      fontWeight: 600,
      backgroundColor: theme.palette.background.paper,
    },
  },
  approveButton: {
    marginTop: theme.spacing(1),
  },
  resolvedBanner: {
    marginTop: theme.spacing(1),
  },
}));

interface DriftRowState {
  loading: boolean;
  report?: DriftReport;
  error?: string;
  approving?: boolean;
  approved?: boolean;
}

export function DriftDashboardPage() {
  const classes = useStyles();
  const discoveryApi = useApi(discoveryApiRef);
  const fetchApi = useApi(fetchApiRef);
  const [refreshKey, setRefreshKey] = useState(0);
  const [expandedSlug, setExpandedSlug] = useState<string | null>(null);
  const [rowStates, setRowStates] = useState<Record<string, DriftRowState>>({});

  const client = createPhWorkflowsClient({ discoveryApi, fetchApi });

  const { value: workflows, loading, error } = useAsync(async () => {
    const all = await client.getWorkflows();
    return all.filter(w => w.hasDrift === true);
  }, [refreshKey]);

  const handleRefresh = useCallback(() => {
    setRefreshKey(k => k + 1);
    setExpandedSlug(null);
    setRowStates({});
  }, []);

  const handleExpand = useCallback(async (slug: string) => {
    if (expandedSlug === slug) {
      setExpandedSlug(null);
      return;
    }

    setExpandedSlug(slug);

    if (rowStates[slug]?.report || rowStates[slug]?.loading) return;

    setRowStates(prev => ({ ...prev, [slug]: { loading: true } }));

    try {
      const report = await client.fetchDriftReport(slug, 'semantic');
      setRowStates(prev => ({ ...prev, [slug]: { loading: false, report } }));
    } catch (e: any) {
      setRowStates(prev => ({
        ...prev,
        [slug]: { loading: false, error: e.message || 'Failed to load drift report' },
      }));
    }
  }, [expandedSlug, rowStates, client]);

  const handleApprove = useCallback(async (slug: string) => {
    setRowStates(prev => ({
      ...prev,
      [slug]: { ...prev[slug], approving: true },
    }));

    try {
      await client.approveDrift(slug);
      setRowStates(prev => ({
        ...prev,
        [slug]: { ...prev[slug], approving: false, approved: true },
      }));
      setTimeout(() => handleRefresh(), 1500);
    } catch (e: any) {
      setRowStates(prev => ({
        ...prev,
        [slug]: { ...prev[slug], approving: false, error: e.message },
      }));
    }
  }, [client, handleRefresh]);

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
      render: (row: WorkflowSummary) => (
        <Chip
          label={STAGE_LABELS[row.stage] || row.stage}
          size="small"
          className={classes.chip}
        />
      ),
    },
    {
      title: 'Baseline SHA',
      field: 'baselineSha',
      render: (row: WorkflowSummary) =>
        row.baselineSha ? row.baselineSha.substring(0, 8) : '—',
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
      defaultSort: 'desc' as const,
    },
    {
      title: 'Actions',
      field: 'id',
      sorting: false,
      render: (row: WorkflowSummary) => {
        const state = rowStates[row.projectId];
        if (state?.approved) {
          return (
            <Chip
              icon={<CheckCircleIcon />}
              label="Approved"
              size="small"
              style={{ backgroundColor: '#4caf50', color: '#fff' }}
            />
          );
        }
        return (
          <Button
            variant="outlined"
            size="small"
            color="primary"
            disabled={state?.approving}
            onClick={e => {
              e.stopPropagation();
              handleApprove(row.projectId);
            }}
          >
            {state?.approving ? <CircularProgress size={16} /> : 'Approve'}
          </Button>
        );
      },
    },
  ];

  return (
    <Page themeId="tool">
      <Header title="Spec Drift" subtitle="Review and approve spec drift across workflows">
        <HeaderLabel label="Drifted" value={String(workflows?.length ?? 0)} />
      </Header>
      <Content>
        <ContentHeader title="Drifted Workflows">
          <Tooltip title="Refresh">
            <IconButton onClick={handleRefresh} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </ContentHeader>
        <Table<WorkflowSummary>
          title="Workflows with Spec Drift"
          options={{
            search: true,
            paging: true,
            pageSize: 20,
            padding: 'dense',
          }}
          columns={columns}
          data={workflows ?? []}
          isLoading={loading}
          emptyContent={
            error ? (
              <Box p={2}>
                <Alert severity="error">Failed to load workflows: {error.message}</Alert>
              </Box>
            ) : (
              <Box p={4} textAlign="center">
                <Typography variant="h6" color="textSecondary">
                  No drifted workflows found
                </Typography>
                <Typography variant="body2" color="textSecondary">
                  All active workflows are in sync with their baseline.
                </Typography>
              </Box>
            )
          }
          onRowClick={(_event, rowData) => {
            if (rowData) {
              handleExpand(rowData.projectId);
            }
          }}
          detailPanel={[
            {
              tooltip: 'Show drift details',
              render: ({ rowData }) => {
                const slug = rowData.projectId;
                const state = rowStates[slug];

                return (
                  <Box className={classes.driftDetails}>
                    {!state || state.loading ? (
                      <Box display="flex" alignItems="center" style={{ gap: 8 }}>
                        <CircularProgress size={20} />
                        <Typography variant="body2">Loading drift report...</Typography>
                      </Box>
                    ) : state.error ? (
                      <Alert severity="error">{state.error}</Alert>
                    ) : state.report && !state.report.has_drift ? (
                      <Alert severity="success" className={classes.resolvedBanner}>
                        Drift has been resolved. The current HEAD matches the baseline.
                      </Alert>
                    ) : state.report ? (
                      <>
                        <Typography variant="subtitle2" gutterBottom>
                          {state.report.summary}
                        </Typography>
                        <Typography variant="caption" color="textSecondary">
                          Baseline: {state.report.baseline_sha.substring(0, 8)} &rarr; Current: {state.report.current_sha.substring(0, 8)}
                        </Typography>
                        {state.report.changes.length > 0 && (
                          <table className={classes.changesTable}>
                            <thead>
                              <tr>
                                <th>File</th>
                                <th>Section</th>
                                <th>Difference</th>
                              </tr>
                            </thead>
                            <tbody>
                              {state.report.changes.map((c, i) => (
                                <tr key={i}>
                                  <td>{c.file}</td>
                                  <td>{c.comparing}</td>
                                  <td>{c.difference}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )}
                      </>
                    ) : null}
                  </Box>
                );
              },
            },
          ]}
        />
      </Content>
    </Page>
  );
}
