import React, { useState, useCallback, useEffect, useRef, useMemo } from 'react';
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
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  makeStyles,
  TextField,
  Tooltip,
  Typography,
} from '@material-ui/core';
import { Alert } from '@material-ui/lab';
import RefreshIcon from '@material-ui/icons/Refresh';
import CheckCircleIcon from '@material-ui/icons/CheckCircle';
import AddIcon from '@material-ui/icons/Add';
import DeleteIcon from '@material-ui/icons/Delete';
import { createPhWorkflowsClient } from '../../api/client';
import { WorkflowSummary, DriftReport } from '../../api/types';
import { STAGE_LABELS } from '../../utils/stageMapping';
import { useUserGroups } from '../../hooks/useUserGroups';

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
}

function DriftDetailPanel({
  slug,
  state,
  onFetch,
  onApprove,
  canApprove,
  approvingSlug,
  approvedSlugs,
  classes,
}: {
  slug: string;
  state: DriftRowState | undefined;
  onFetch: (slug: string) => void;
  onApprove: (slug: string) => void;
  canApprove: boolean;
  approvingSlug: string | null;
  approvedSlugs: Set<string>;
  classes: ReturnType<typeof useStyles>;
}) {
  const fetchedRef = useRef(false);

  useEffect(() => {
    if (!state && !fetchedRef.current) {
      fetchedRef.current = true;
      onFetch(slug);
    }
  }, [slug, state, onFetch]);

  const reportLoaded = state && !state.loading && !state.error && state.report;
  const isApproving = approvingSlug === slug;
  const isApproved = approvedSlugs.has(slug);

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
          Drift appears to have been resolved by the developer. You can approve to clear the drift flag.
        </Alert>
      ) : state.report ? (
        <>
          <div style={{
            padding: '8px 16px',
            marginBottom: 16,
            borderRadius: 4,
            backgroundColor: '#fff3e0',
            color: '#e65100',
            fontWeight: 600,
          }}>
            Project drift detected
          </div>
          <Typography variant="body2" style={{ marginBottom: 8, color: '#757575' }}>
            Baseline: <code>{state.report.baseline_sha.substring(0, 7)}</code>
            {' → HEAD: '}
            <code>{state.report.current_sha.substring(0, 7)}</code>
          </Typography>
          {state.report.changes.length > 0 && (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid rgba(255,255,255,0.12)', textAlign: 'left' }}>
                  <th style={{ padding: '6px 8px' }}>Severity</th>
                  <th style={{ padding: '6px 8px' }}>File</th>
                  <th style={{ padding: '6px 8px' }}>Field / Section</th>
                  <th style={{ padding: '6px 8px' }}>Difference</th>
                </tr>
              </thead>
              <tbody>
                {state.report.changes.map((c, i) => {
                  const sevColor = c.severity === 'critical' ? '#f44336'
                    : c.severity === 'warning' ? '#ff9800'
                    : '#2196f3';
                  return (
                    <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                      <td style={{ padding: '6px 8px' }}>
                        <Chip
                          label={c.severity || 'info'}
                          size="small"
                          style={{
                            backgroundColor: sevColor,
                            color: '#fff',
                            fontWeight: 600,
                            fontSize: '0.7rem',
                          }}
                        />
                      </td>
                      <td style={{ padding: '6px 8px', fontFamily: 'monospace' }}>{c.file}</td>
                      <td style={{ padding: '6px 8px' }}>{c.comparing}</td>
                      <td style={{ padding: '6px 8px' }}>{c.difference}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </>
      ) : null}
      {reportLoaded && !isApproved && canApprove && (
        <Box className={classes.approveButton}>
          <Typography variant="caption" color="textSecondary" style={{ display: 'block', marginBottom: 4 }}>
            Approving updates the baseline SHA to the latest commit.
          </Typography>
          <Button
            variant="contained"
            size="small"
            disabled={isApproving}
            style={{ backgroundColor: '#4caf50', color: '#fff', fontWeight: 600 }}
            onClick={() => onApprove(slug)}
          >
            {isApproving ? <CircularProgress size={16} color="inherit" /> : 'Approve'}
          </Button>
        </Box>
      )}
      {isApproved && (
        <Alert severity="success" className={classes.approveButton}>
          Baseline updated to latest commit.
        </Alert>
      )}
    </Box>
  );
}

export function DriftDashboardPage() {
  const classes = useStyles();
  const configApi = useApi(configApiRef);
  const discoveryApi = useApi(discoveryApiRef);
  const fetchApi = useApi(fetchApiRef);
  const identityApi = useApi(identityApiRef);
  const centralApiUrl = configApi.getString('phWorkflows.centralApiUrl');
  const { isContentReviewer, isAdmin } = useUserGroups();
  const [refreshKey, setRefreshKey] = useState(0);
  const [rowStates, setRowStates] = useState<Record<string, DriftRowState>>({});
  const [approvalNotesDialogOpen, setApprovalNotesDialogOpen] = useState(false);
  const [approvalNotes, setApprovalNotes] = useState<Array<{ text: string }>>([]);
  const [pendingApprovalSlug, setPendingApprovalSlug] = useState<string | null>(null);
  const [approvingSlug, setApprovingSlug] = useState<string | null>(null);
  const [approvedSlugs, setApprovedSlugs] = useState<Set<string>>(new Set());

  const client = useMemo(() => createPhWorkflowsClient({ centralApiUrl, discoveryApi, fetchApi, identityApi }), [centralApiUrl, discoveryApi, fetchApi, identityApi]);

  const { value: workflows, loading, error } = useAsync(async () => {
    const all = await client.getWorkflows();
    return all.filter(w => w.hasDrift === true);
  }, [refreshKey]);

  const handleRefresh = useCallback(() => {
    setRefreshKey(k => k + 1);
    setRowStates({});
    setApprovingSlug(null);
    setApprovedSlugs(new Set());
  }, []);

  const fetchDrift = useCallback(async (slug: string) => {
    setRowStates(prev => {
      if (prev[slug]?.report || prev[slug]?.loading) return prev;
      return { ...prev, [slug]: { loading: true } };
    });

    try {
      const report = await client.fetchDriftReport(slug, 'semantic');
      setRowStates(prev => ({ ...prev, [slug]: { loading: false, report } }));
    } catch (e: any) {
      setRowStates(prev => ({
        ...prev,
        [slug]: { loading: false, error: e.message || 'Failed to load drift report' },
      }));
    }
  }, [client]);

  const handleApprove = useCallback((slug: string) => {
    setPendingApprovalSlug(slug);
    setApprovalNotes([]);
    setApprovalNotesDialogOpen(true);
  }, []);

  const handleApproveConfirm = useCallback(async () => {
    if (!pendingApprovalSlug) return;

    const slug = pendingApprovalSlug;
    setApprovalNotesDialogOpen(false);
    setPendingApprovalSlug(null);
    setApprovingSlug(slug);

    try {
      const notes = approvalNotes.length > 0 ? approvalNotes.map(n => n.text).filter(t => t.trim()) : undefined;
      await client.approveDrift(slug, notes);
      setApprovingSlug(null);
      // Remove from drift queue after a brief delay
      setTimeout(() => {
        setApprovedSlugs(prev => new Set(prev).add(slug));
      }, 1500);
    } catch (e: any) {
      setApprovingSlug(null);
      setRowStates(prev => ({
        ...prev,
        [slug]: { ...prev[slug], error: e.message },
      }));
    }
  }, [pendingApprovalSlug, approvalNotes, client]);

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
          data={(workflows ?? []).filter(w => !approvedSlugs.has(w.projectId))}
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
              fetchDrift(rowData.projectId);
            }
          }}
          detailPanel={[
            {
              tooltip: 'Show drift details',
              render: ({ rowData }) => (
                <DriftDetailPanel
                  slug={rowData.projectId}
                  state={rowStates[rowData.projectId]}
                  onFetch={fetchDrift}
                  onApprove={handleApprove}
                  canApprove={isContentReviewer || isAdmin}
                  approvingSlug={approvingSlug}
                  approvedSlugs={approvedSlugs}
                  classes={classes}
                />
              ),
            },
          ]}
        />
      </Content>

      <Dialog open={approvalNotesDialogOpen} onClose={() => setApprovalNotesDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Approve Drift with Notes</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="textSecondary" gutterBottom style={{ marginBottom: 16 }}>
            Add notes about this drift approval (optional). These will be visible in the Notes tab.
          </Typography>
          {approvalNotes.map((note, i) => (
            <div key={i} style={{ display: 'flex', gap: 8, marginBottom: 8, alignItems: 'center' }}>
              <TextField
                fullWidth
                variant="outlined"
                size="small"
                value={note.text}
                onChange={(e) => {
                  const next = [...approvalNotes];
                  next[i] = { text: e.target.value };
                  setApprovalNotes(next);
                }}
                placeholder="Note text..."
              />
              <IconButton
                size="small"
                onClick={() => setApprovalNotes(approvalNotes.filter((_, j) => j !== i))}
              >
                <DeleteIcon fontSize="small" />
              </IconButton>
            </div>
          ))}
          <Button
            size="small"
            startIcon={<AddIcon />}
            onClick={() => setApprovalNotes([...approvalNotes, { text: '' }])}
            style={{ marginTop: 8 }}
          >
            Add Note
          </Button>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setApprovalNotesDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            style={{ backgroundColor: '#4caf50', color: '#fff', fontWeight: 600 }}
            onClick={handleApproveConfirm}
          >
            Approve
          </Button>
        </DialogActions>
      </Dialog>
    </Page>
  );
}
