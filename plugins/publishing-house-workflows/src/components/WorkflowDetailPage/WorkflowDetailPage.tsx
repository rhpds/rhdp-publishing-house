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
  Snackbar,
} from '@material-ui/core';
import { Alert } from '@material-ui/lab';
import GitHubIcon from '@material-ui/icons/GitHub';
import BugReportIcon from '@material-ui/icons/BugReport';
import { createPhWorkflowsClient } from '../../api/client';
import { WorkflowStage } from '../../api/types';
import { STAGE_LABELS } from '../../utils/stageMapping';
import { WorkflowProgress } from './WorkflowProgress';

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
  const { projectId } = useParams<{ projectId: string }>();
  const discoveryApi = useApi(discoveryApiRef);
  const fetchApi = useApi(fetchApiRef);

  const client = createPhWorkflowsClient({ discoveryApi, fetchApi });

  const [refreshKey, setRefreshKey] = useState(0);
  const {
    value: result,
    loading,
    error,
  } = useAsync(() => client.getWorkflow(projectId!), [projectId, refreshKey]);

  const [approvingStage, setApprovingStage] = useState<string | null>(null);
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    severity: 'success' | 'error';
    message: string;
  }>({ open: false, severity: 'success', message: '' });

  const handleApprove = async (stage: WorkflowStage) => {
    if (!result) return;
    setApprovingStage(stage);
    try {
      await client.sendApprovalEvent(result.summary.projectId, stage);
      setSnackbar({
        open: true,
        severity: 'success',
        message: `${STAGE_LABELS[stage]} approved`,
      });
      setTimeout(() => setRefreshKey(k => k + 1), 1500);
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
              : `No workflow found for project "${projectId}"`}
          </Typography>
        </Content>
      </Page>
    );
  }

  const { summary } = result;
  const stageLabel = STAGE_LABELS[summary.stage] || summary.stage;

  return (
    <Page themeId="tool">
      <Header
        title={summary.projectId}
        subtitle={`${summary.projectType} — ${summary.deploymentMode}`}
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
        </div>

        <InfoCard title="Workflow Progress">
          <WorkflowProgress
            stage={summary.stage}
            approvingStage={approvingStage}
            onApprove={handleApprove}
          />
        </InfoCard>

        <Grid container spacing={3} className={classes.detailGrid}>
          <Grid item xs={12} md={6}>
            <InfoCard title="Project Details">
              <DetailField label="Project ID" value={summary.projectId} />
              <DetailField label="Owner" value={summary.owner} />
              <DetailField label="SSO User" value={summary.ssoUser} />
              <DetailField label="Type" value={summary.projectType} />
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
            </InfoCard>
          </Grid>
        </Grid>

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
