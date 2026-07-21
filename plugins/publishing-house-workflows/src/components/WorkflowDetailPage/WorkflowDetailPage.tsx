import React, { useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { useAsync } from 'react-use';
import {
  Content,
  Header,
  HeaderLabel,
  InfoCard,
  Page,
  Progress,
} from '@backstage/core-components';
import {
  discoveryApiRef,
  fetchApiRef,
  useApi,
} from '@backstage/core-plugin-api';
import {
  Grid,
  Typography,
  makeStyles,
  Button,
  Chip,
  IconButton,
  Snackbar,
} from '@material-ui/core';
import { Alert } from '@material-ui/lab';
import GitHubIcon from '@material-ui/icons/GitHub';
import BugReportIcon from '@material-ui/icons/BugReport';
import RefreshIcon from '@material-ui/icons/Refresh';
import ReplayIcon from '@material-ui/icons/Replay';
import { createPhWorkflowsClient } from '../../api/client';
import { WorkflowStage, RejectionData } from '../../api/types';
import { STAGE_LABELS, STAGE_DESCRIPTIONS } from '../../utils/stageMapping';
import { WorkflowProgress } from './WorkflowProgress';
import { RejectionDialog } from './RejectionDialog';

const useStyles = makeStyles(theme => ({
  linkButtons: {
    display: 'flex',
    gap: theme.spacing(1),
    marginBottom: theme.spacing(2),
  },
  detailGrid: {
    marginTop: theme.spacing(1),
  },
  label: {
    color: theme.palette.text.secondary,
    fontSize: '0.75rem',
    textTransform: 'uppercase' as const,
    fontWeight: 600,
    marginBottom: theme.spacing(0.5),
  },
  value: {
    fontSize: '0.95rem',
    marginBottom: theme.spacing(2),
  },
}));

function DetailField({ label, value }: { label: string; value: string }) {
  const classes = useStyles();
  return (
    <div>
      <Typography className={classes.label}>{label}</Typography>
      <Typography className={classes.value}>{value || '—'}</Typography>
    </div>
  );
}

export function WorkflowDetailPage() {
  const classes = useStyles();
  const { workflowId } = useParams<{ workflowId: string }>();
  const discoveryApi = useApi(discoveryApiRef);
  const fetchApi = useApi(fetchApiRef);

  const client = createPhWorkflowsClient({ discoveryApi, fetchApi });

  const [refreshKey, setRefreshKey] = useState(0);
  const {
    value: result,
    loading,
    error,
  } = useAsync(() => client.getWorkflowById(workflowId!), [workflowId, refreshKey]);

  const [approvingStage, setApprovingStage] = useState<string | null>(null);
  const [rejectionDialogOpen, setRejectionDialogOpen] = useState(false);
  const [rejectingStage, setRejectingStage] = useState<WorkflowStage | null>(null);
  const [submittingRejection, setSubmittingRejection] = useState(false);
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    severity: 'success' | 'error';
    message: string;
  }>({ open: false, severity: 'success', message: '' });

  const handleApprove = async (stage: WorkflowStage) => {
    if (!result) return;
    setApprovingStage(stage);
    try {
      await client.sendApprovalEvent(result.summary.id, stage, result.summary.projectId);
      setSnackbar({
        open: true,
        severity: 'success',
        message: `${STAGE_LABELS[stage]} approved — refreshing...`,
      });
      await new Promise(resolve => setTimeout(resolve, 5000));
      setRefreshKey(k => k + 1);
    } catch (err: any) {
      setSnackbar({
        open: true,
        severity: 'error',
        message: `Approval failed: ${err.message}`,
      });
    } finally {
      setApprovingStage(null);
    }
  };

  const handleReject = (stage: WorkflowStage) => {
    setRejectingStage(stage);
    setRejectionDialogOpen(true);
  };

  const handleRejectionConfirm = async (data: RejectionData) => {
    if (!result || !rejectingStage) return;
    setSubmittingRejection(true);
    try {
      await client.sendRejectionEvent(result.summary.id, rejectingStage, data, result.summary.projectId);
      setRejectionDialogOpen(false);
      setSnackbar({
        open: true,
        severity: 'success',
        message: `${STAGE_LABELS[rejectingStage]} rejected — workflow returning to Intake...`,
      });
      await new Promise(resolve => setTimeout(resolve, 5000));
      setRefreshKey(k => k + 1);
    } catch (err: any) {
      setSnackbar({
        open: true,
        severity: 'error',
        message: `Rejection failed: ${err.message}`,
      });
    } finally {
      setSubmittingRejection(false);
    }
  };

  const handleRejectionCancel = () => {
    setRejectionDialogOpen(false);
    setRejectingStage(null);
  };

  if (loading) {
    return (
      <Page themeId="tool">
        <Header title="Loading..." />
        <Content>
          <Progress />
        </Content>
      </Page>
    );
  }

  if (error || !result) {
    return (
      <Page themeId="tool">
        <Header title="Workflow Not Found" />
        <Content>
          <Typography>
            {error
              ? `Error: ${error.message}`
              : `No workflow found for ID "${workflowId}"`}
          </Typography>
        </Content>
      </Page>
    );
  }

  const { summary, instance } = result;
  const stageLabel = STAGE_LABELS[summary.stage] || summary.stage;
  const rejection = instance?.variables?.workflowdata
    ? (instance.variables as any).workflowdata?.rejection ?? (instance.variables as any).rejection
    : null;
  const rejectedFrom = rejection?.reviewerStage as WorkflowStage | null;
  const rejectionReasons = rejection?.reasons ?? [];

  return (
    <Page themeId="tool">
      <Header
        title={summary.projectId}
        subtitle={`${summary.contentType} — ${summary.deploymentMode}`}
      >
        <HeaderLabel label="Stage" value={stageLabel} />
        <HeaderLabel label="Owner" value={summary.owner} />
      </Header>
      <Content>
        <div className={classes.linkButtons}>
          {summary.repoUrl && (
            <Button
              variant="outlined"
              size="small"
              startIcon={<GitHubIcon />}
              href={summary.repoUrl}
              target="_blank"
              rel="noopener noreferrer"
            >
              GitHub Repo
            </Button>
          )}
          {summary.epicKey && (
            <Button
              variant="outlined"
              size="small"
              startIcon={<BugReportIcon />}
              href={summary.jiraUrl}
              target="_blank"
              rel="noopener noreferrer"
            >
              {summary.epicKey}
            </Button>
          )}
          <IconButton
            size="small"
            onClick={() => setRefreshKey(k => k + 1)}
            disabled={loading}
          >
            <RefreshIcon />
          </IconButton>
        </div>

        <InfoCard title="Workflow Progress">
          <WorkflowProgress
            stage={summary.stage}
            approvingStage={approvingStage}
            onApprove={handleApprove}
            onReject={handleReject}
            rejectedFrom={rejectedFrom}
          />
        </InfoCard>

        {rejectionReasons.length > 0 && (
          <InfoCard title={`Rejected at ${STAGE_LABELS[rejectedFrom!] || 'Review'}`}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
              <ReplayIcon style={{ fontSize: '1rem', color: '#e57373' }} />
              <Typography variant="body2" style={{ color: '#e57373', fontWeight: 600 }}>
                Reviewer: {rejection?.reviewerName || '—'}
                {rejection?.timestamp ? ` — ${new Date(rejection.timestamp).toLocaleString()}` : ''}
              </Typography>
            </div>
            <ul style={{ margin: 0, paddingLeft: 24 }}>
              {rejectionReasons.map((r: any) => (
                <li key={r.id}>
                  <Typography variant="body2">{r.text}</Typography>
                </li>
              ))}
            </ul>
          </InfoCard>
        )}

        <Grid container spacing={3} className={classes.detailGrid}>
          <Grid item xs={12} md={6}>
            <InfoCard title="Project Details">
              <DetailField label="Project ID" value={summary.projectId} />
              <DetailField label="Description" value={summary.projectDescription} />
              <DetailField label="Owner" value={summary.owner} />
              <DetailField label="SSO User" value={summary.ssoUser} />
              <DetailField label="Type" value={summary.contentType} />
              <DetailField label="Deployment Mode" value={summary.deploymentMode} />
              <DetailField label="State" value={summary.state} />
              <div>
                <Typography className={classes.label}>Tags</Typography>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 16 }}>
                  {summary.tags.length > 0
                    ? summary.tags.map(tag => (
                        <Chip key={tag} label={tag} size="small" variant="outlined" />
                      ))
                    : <Typography className={classes.value}>—</Typography>}
                </div>
              </div>
            </InfoCard>
          </Grid>
          <Grid item xs={12} md={6}>
            <InfoCard title="Timeline">
              <DetailField
                label="Started"
                value={
                  summary.startedAt
                    ? new Date(summary.startedAt).toLocaleString()
                    : ''
                }
              />
              <DetailField
                label="Last Updated"
                value={
                  summary.lastUpdate
                    ? new Date(summary.lastUpdate).toLocaleString()
                    : ''
                }
              />
              <DetailField label="Jira Ticket" value={summary.epicKey} />
              <DetailField label="Current Stage" value={stageLabel} />
              {STAGE_DESCRIPTIONS[summary.stage] && (
                <DetailField label="What's Happening" value={STAGE_DESCRIPTIONS[summary.stage]} />
              )}
            </InfoCard>
          </Grid>
        </Grid>

        <RejectionDialog
          open={rejectionDialogOpen}
          stage={rejectingStage || 'content_review'}
          reviewerName={summary.ssoEmail || summary.owner}
          submitting={submittingRejection}
          onConfirm={handleRejectionConfirm}
          onCancel={handleRejectionCancel}
        />

        <Snackbar
          open={snackbar.open}
          autoHideDuration={5000}
          onClose={() => setSnackbar(s => ({ ...s, open: false }))}
        >
          <Alert
            onClose={() => setSnackbar(s => ({ ...s, open: false }))}
            severity={snackbar.severity}
          >
            {snackbar.message}
          </Alert>
        </Snackbar>
      </Content>
    </Page>
  );
}
