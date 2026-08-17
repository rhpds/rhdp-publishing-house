import React, { useState, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
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
  configApiRef,
  discoveryApiRef,
  fetchApiRef,
  identityApiRef,
  useApi,
} from '@backstage/core-plugin-api';
import {
  Grid,
  Typography,
  makeStyles,
  Button,
  Chip,
  CircularProgress,
  IconButton,
  Snackbar,
  Tabs,
  Tab,
  Popover,
  TextField,
} from '@material-ui/core';
import { Alert } from '@material-ui/lab';
import GitHubIcon from '@material-ui/icons/GitHub';
import BugReportIcon from '@material-ui/icons/BugReport';
import RefreshIcon from '@material-ui/icons/Refresh';
import ReplayIcon from '@material-ui/icons/Replay';
import InfoOutlinedIcon from '@material-ui/icons/InfoOutlined';
import MenuBookIcon from '@material-ui/icons/MenuBook';
import { createPhWorkflowsClient } from '../../api/client';
import { WorkflowStage, RejectionData, ValidationReport, CheckStatus, DriftReport, TestingComment } from '../../api/types';
import { STAGE_LABELS, STAGE_DESCRIPTIONS } from '../../utils/stageMapping';
import { useUserGroups } from '../../hooks/useUserGroups';

const REVIEW_STAGES: WorkflowStage[] = ['content_review', 'infra_review'];
const STAGES_WITH_REVIEW_TAB: WorkflowStage[] = [
  'content_review', 'infra_review', 'env_setup', 'development', 'testing', 'published',
];

const CHECK_GROUP_LABELS: Record<string, string> = {
  A: 'Spec Fields',
  B: 'Conditional Fields',
  C: 'Approval Checklist',
  D: 'Design Structure',
  E: 'Module Outlines',
  F: 'Cross-Validation',
  G: 'Automation Manifest',
  H: 'Vocabulary',
  I: 'Auto-Computed',
  J: 'Content Writing',
  SYS: 'System',
};

const STATUS_COLORS: Record<CheckStatus, string> = {
  pass: '#4caf50',
  fail: '#f44336',
  warn: '#ff9800',
  skip: '#9e9e9e',
};

const STATUS_ICONS: Record<CheckStatus, string> = {
  pass: '✓',
  fail: '✗',
  warn: '⚠',
  skip: '—',
};
import { WorkflowProgress } from './WorkflowProgress';
import { RejectionDialog } from './RejectionDialog';
import { MessageDialog } from './MessageDialog';

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
  const navigate = useNavigate();
  const configApi = useApi(configApiRef);
  const discoveryApi = useApi(discoveryApiRef);
  const fetchApi = useApi(fetchApiRef);
  const identityApi = useApi(identityApiRef);
  const centralApiUrl = configApi.getString('phWorkflows.centralApiUrl');

  const client = useMemo(() => createPhWorkflowsClient({ centralApiUrl, discoveryApi, fetchApi, identityApi }), [centralApiUrl, discoveryApi, fetchApi, identityApi]);
  const { isContentReviewer, isInfraReviewer, isContentDeveloper, isAdmin, isOperations, isDeveloper } = useUserGroups();

  const [refreshKey, setRefreshKey] = useState(0);
  const [activeTab, setActiveTab] = useState(0);
  const {
    value: result,
    loading,
    error,
  } = useAsync(() => client.getWorkflowById(workflowId!), [workflowId, refreshKey]);

  const [validationReport, setValidationReport] = useState<ValidationReport | null>(null);
  const [validationLoading, setValidationLoading] = useState(false);
  const [driftReport, setDriftReport] = useState<DriftReport | null>(null);
  const [driftLoading, setDriftLoading] = useState(false);

  const fetchReport = useCallback(async () => {
    if (!result) return;
    const stage = result.summary.stage;
    if (!STAGES_WITH_REVIEW_TAB.includes(stage)) return;

    const repoUrl = result.summary.repoUrl;
    const wd = result.instance?.variables?.workflowdata as any;
    const baselineSha = wd?.baselineSha;
    if (!repoUrl) return;

    const slug = result.summary.projectId;
    const isReview = REVIEW_STAGES.includes(stage);

    setValidationLoading(true);
    if (baselineSha) setDriftLoading(true);

    const validationPromise = client.fetchValidationReport(slug, repoUrl, 'main', baselineSha, stage)
        .then(report => setValidationReport(report))
        .catch((err: any) => setSnackbar({ open: true, severity: 'error', message: `Validation report failed: ${err.message}` }))
        .finally(() => setValidationLoading(false));

    const driftMode = isReview || stage === 'env_setup' ? 'structural' : 'semantic';
    const skipDrift = stage === 'published';
    const runInfra = !isReview && stage !== 'env_setup' && !skipDrift;
    const driftPromise = baselineSha && !skipDrift
      ? (async () => {
          try {
            const report = await client.fetchDriftReport(slug, driftMode);
            if (runInfra) {
              try {
                const infraReport = await client.fetchDriftReport(slug, 'infra');
                report.changes = [...report.changes, ...infraReport.changes];
                if (!report.summary && infraReport.summary) report.summary = infraReport.summary;
              } catch { /* infra check is best-effort */ }
            }
            setDriftReport(report);
          } catch (err: any) {
            setSnackbar({ open: true, severity: 'error', message: `Drift check failed: ${err.message}` });
          } finally {
            setDriftLoading(false);
          }
        })()
      : Promise.resolve().then(() => { setDriftReport(null); setDriftLoading(false); });

    await Promise.all([validationPromise, driftPromise]);
  }, [result, client]);

  React.useEffect(() => {
    if (result && STAGES_WITH_REVIEW_TAB.includes(result.summary.stage)) {
      fetchReport();
    }
  }, [result, fetchReport]);

  const [approvingStage, setApprovingStage] = useState<string | null>(null);
  const [rejectionDialogOpen, setRejectionDialogOpen] = useState(false);
  const [rejectingStage, setRejectingStage] = useState<WorkflowStage | null>(null);
  const [submittingRejection, setSubmittingRejection] = useState(false);
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    severity: 'success' | 'error';
    message: string;
  }>({ open: false, severity: 'success', message: '' });
  const [reasonsPopover, setReasonsPopover] = useState<{ anchorEl: HTMLElement | null; reasons: { id: number; text: string }[] }>({ anchorEl: null, reasons: [] });
  const [messageDialogOpen, setMessageDialogOpen] = useState(false);
  const [sendingMessage, setSendingMessage] = useState(false);
  const [stagingAgnosticvUrls, setStagingAgnosticvUrls] = useState<string[]>(['']);
  const [stagingCiUrls, setStagingCiUrls] = useState<string[]>(['']);
  const [submittingStaging, setSubmittingStaging] = useState(false);
  const [testingComments, setTestingComments] = useState<TestingComment[]>([]);
  const [testingCommentText, setTestingCommentText] = useState('');
  const [submittingTestingComment, setSubmittingTestingComment] = useState(false);
  const [loadingTestingComments, setLoadingTestingComments] = useState(false);
  const [completingTesting, setCompletingTesting] = useState(false);

  const handleApprove = async (stage: WorkflowStage) => {
    if (!result) return;
    setApprovingStage(stage);
    try {
      if (REVIEW_STAGES.includes(stage) && result.summary.repoUrl) {
        const latestSha = await client.fetchHeadCommitSha(result.summary.repoUrl);
        if (!latestSha) {
          setSnackbar({
            open: true,
            severity: 'error',
            message: 'Could not verify repo state — approval blocked. Try again.',
          });
          setApprovingStage(null);
          return;
        }
        if (validationReport?.commit_sha && latestSha !== validationReport.commit_sha) {
          setSnackbar({
            open: true,
            severity: 'error',
            message: 'The repo has been updated since the last check. Refreshing validation report...',
          });
          await fetchReport();
          setApprovingStage(null);
          return;
        }
      }

      const user = result.summary.ssoEmail || result.summary.owner;
      const commitSha = validationReport?.commit_sha;
      await client.sendApprovalEvent(result.summary.id, stage, result.summary.projectId, { user, commitSha });
      setSnackbar({
        open: true,
        severity: 'success',
        message: `${STAGE_LABELS[stage]} approved — waiting for workflow to advance...`,
      });
      const prevStage = result.summary.stage;
      for (let i = 0; i < 6; i++) {
        await new Promise(resolve => setTimeout(resolve, 5000));
        const updated = await client.getWorkflow(result.summary.projectId);
        if (updated && updated.summary.stage !== prevStage) break;
      }
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
      await client.sendRejectionEvent(result.summary.id, rejectingStage, data, result.summary.projectId, validationReport?.commit_sha);
      setRejectionDialogOpen(false);
      setSnackbar({
        open: true,
        severity: 'success',
        message: `${STAGE_LABELS[rejectingStage]} rejected — returning to ${rejectingStage === 'infra_review' ? 'Content Review' : 'Intake'}...`,
      });
      const prevStage = result.summary.stage;
      for (let i = 0; i < 6; i++) {
        await new Promise(resolve => setTimeout(resolve, 5000));
        const updated = await client.getWorkflow(result.summary.projectId);
        if (updated && updated.summary.stage !== prevStage) break;
      }
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

  const handleSendMessage = async (text: string) => {
    if (!result) return;
    setSendingMessage(true);
    try {
      await client.sendMessage(result.summary.projectId, text, result.summary.stage);
      setMessageDialogOpen(false);
      setSnackbar({ open: true, severity: 'success', message: 'Message sent to author.' });
    } catch (err: any) {
      setSnackbar({ open: true, severity: 'error', message: `Send failed: ${err.message}` });
    } finally {
      setSendingMessage(false);
    }
  };

  const handleStagingSubmit = async () => {
    const filteredAgv = stagingAgnosticvUrls.map(u => u.trim()).filter(Boolean);
    const filteredCi = stagingCiUrls.map(u => u.trim()).filter(Boolean);
    if (!result || !filteredAgv.length || !filteredCi.length) return;
    setSubmittingStaging(true);
    try {
      await client.submitEnvSetup(result.summary.projectId, filteredAgv, filteredCi);
      setSnackbar({ open: true, severity: 'success', message: 'Env setup info submitted — waiting for workflow to advance...' });
      const prevStage = result.summary.stage;
      for (let i = 0; i < 6; i++) {
        await new Promise(resolve => setTimeout(resolve, 5000));
        const updated = await client.getWorkflow(result.summary.projectId);
        if (updated && updated.summary.stage !== prevStage) break;
      }
      setRefreshKey(k => k + 1);
    } catch (err: any) {
      setSnackbar({ open: true, severity: 'error', message: `Env setup submit failed: ${err.message}` });
    } finally {
      setSubmittingStaging(false);
    }
  };

  const loadTestingComments = useCallback(async () => {
    if (!result?.summary.epicKey) return;
    setLoadingTestingComments(true);
    try {
      const data = await client.getTestingComments(result.summary.epicKey);
      setTestingComments(data.comments);
    } catch {
      setTestingComments([]);
    } finally {
      setLoadingTestingComments(false);
    }
  }, [result, client]);

  const handlePostTestingComment = async () => {
    if (!result?.summary.epicKey || !testingCommentText.trim()) return;
    setSubmittingTestingComment(true);
    try {
      await client.postTestingComment(result.summary.epicKey, testingCommentText.trim());
      setTestingCommentText('');
      setSnackbar({ open: true, severity: 'success', message: 'Comment posted to Jira.' });
      await loadTestingComments();
    } catch (err: any) {
      setSnackbar({ open: true, severity: 'error', message: `Comment failed: ${err.message}` });
    } finally {
      setSubmittingTestingComment(false);
    }
  };

  const handleCompleteTesting = async () => {
    if (!result?.summary.repoUrl) return;
    setCompletingTesting(true);
    try {
      await client.submitTesting(result.summary.projectId, result.summary.repoUrl);
      setSnackbar({ open: true, severity: 'success', message: 'Testing complete. Workflow advanced.' });
      setTimeout(() => window.location.reload(), 1500);
    } catch (err: any) {
      setSnackbar({ open: true, severity: 'error', message: `Testing submit failed: ${err.message}` });
    } finally {
      setCompletingTesting(false);
    }
  };

  React.useEffect(() => {
    if (result && ['testing', 'published'].includes(result.summary.stage) && result.summary.epicKey) {
      loadTestingComments();
    }
  }, [result, loadTestingComments]);

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
  const rejectionReasons = (rejection?.reasons ?? []).filter((r: any) => !r.resolved);
  const wd = instance?.variables?.workflowdata as any;
  const reviewHistory: Array<{ user: string; stage: string; action: string; timestamp: string; commitSha?: string }> = wd?.reviewHistory ?? [];

  const isReviewStage = REVIEW_STAGES.includes(summary.stage);
  const hasReviewTab = STAGES_WITH_REVIEW_TAB.includes(summary.stage);
  const hasStagingTab = summary.stage === 'env_setup' || Boolean(wd?.agnosticvUrls?.length) || Boolean(wd?.ciUrls?.length);
  const canReview = (summary.stage === 'content_review' && (isContentReviewer || isAdmin))
    || (summary.stage === 'infra_review' && (isInfraReviewer || isAdmin));
  const canStaging = summary.stage === 'env_setup' && (isContentDeveloper || isAdmin);
  const canMessage = isContentReviewer || isInfraReviewer;
  const testingStages: WorkflowStage[] = ['testing', 'published'];
  const hasTestingTab = testingStages.includes(summary.stage);
  const canPostTestingComment = isOperations && summary.stage === 'testing';
  const canCompleteTesting = isOperations || isAdmin;
  const stagingTabIndex = hasReviewTab ? 2 : 1;
  const testingTabIndex = 1 + (hasReviewTab ? 1 : 0) + (hasStagingTab ? 1 : 0);
  const timelineTabIndex = 1 + (hasReviewTab ? 1 : 0) + (hasStagingTab ? 1 : 0) + (hasTestingTab ? 1 : 0);

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
          <Button
            variant="outlined"
            size="small"
            startIcon={<MenuBookIcon />}
            onClick={() => navigate(`/catalog/default/component/${summary.projectId}`)}
          >
            Catalog
          </Button>
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
            rejectedFrom={rejectedFrom}
            hasDrift={wd?.hasDrift}
            envSetupSkipped={wd?.showroomType === 'zero_touch'}
          />
        </InfoCard>

        {rejection?.isRejected && rejectionReasons.length > 0 && (
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

        <Tabs
          value={activeTab}
          onChange={(_e, v) => setActiveTab(v)}
          indicatorColor="primary"
          textColor="primary"
          style={{ marginBottom: 16, marginTop: 16 }}
        >
          <Tab label="Overview" />
          {hasReviewTab && <Tab label="Review" />}
          {hasStagingTab && <Tab label="Env Setup" />}
          {hasTestingTab && <Tab label="Testing" />}
          <Tab label="Timeline" />
        </Tabs>

        {activeTab === 0 && (
          <InfoCard title="Project Details">
            <Grid container spacing={3}>
              <Grid item xs={12} md={6}>
                <DetailField label="Project ID" value={summary.projectId} />
                <DetailField label="Description" value={summary.projectDescription} />
                <DetailField label="Owner" value={summary.owner} />
                <DetailField label="SSO User" value={summary.ssoUser} />
              </Grid>
              <Grid item xs={12} md={6}>
                <DetailField label="Type" value={summary.contentType} />
                <DetailField label="Deployment Mode" value={summary.deploymentMode} />
                <DetailField label="Showroom Type" value={wd?.showroomType === 'zero_touch' ? 'Zero Touch' : 'Classic'} />
                <DetailField label="Intake Type" value={summary.intakeType === 'migration' ? 'Migration' : 'New'} />
                <DetailField label="State" value={summary.state} />
                <DetailField label="Current Stage" value={stageLabel} />
              </Grid>
              <Grid item xs={12}>
                <Typography className={classes.label}>Tags</Typography>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 16 }}>
                  {summary.tags.length > 0
                    ? summary.tags.map(tag => (
                        <Chip key={tag} label={tag} size="small" variant="outlined" />
                      ))
                    : <Typography className={classes.value}>—</Typography>}
                </div>
              </Grid>
            </Grid>
          </InfoCard>
        )}

        {activeTab === 0 && canMessage && (
          <InfoCard>
            <Button
              variant="contained"
              style={{ backgroundColor: '#0099FF', color: '#fff', fontWeight: 600 }}
              size="large"
              onClick={() => setMessageDialogOpen(true)}
            >
              Message
            </Button>
          </InfoCard>
        )}


        {hasReviewTab && activeTab === 1 && (
          <>
            {/* Spec File Links */}
            {summary.repoUrl && (
              <InfoCard title="Spec Files">
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {[
                    { label: 'spec.yaml', path: 'publishing-house/spec.yaml' },
                    { label: 'design.md', path: 'publishing-house/spec/design.md' },
                    { label: 'Module Outlines', path: 'publishing-house/spec/modules' },
                  ].map(f => (
                    <Button
                      key={f.path}
                      variant="outlined"
                      size="small"
                      startIcon={<GitHubIcon />}
                      href={`${summary.repoUrl.replace(/\.git$/, '')}/blob/main/${f.path}`}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {f.label}
                    </Button>
                  ))}
                </div>
              </InfoCard>
            )}

            {driftLoading && (
              <InfoCard title="Drift Check">
                <Progress />
              </InfoCard>
            )}
            {!driftLoading && driftReport && driftReport.changes.length > 0 && (
              <InfoCard title={driftReport.has_drift ? 'Changes Since Last Approval' : 'Drift Check'}>
                <div style={{
                  padding: '8px 16px',
                  marginBottom: 16,
                  borderRadius: 4,
                  backgroundColor: driftReport.has_drift ? '#fff3e0' : '#e3f2fd',
                  color: driftReport.has_drift ? '#e65100' : '#1565c0',
                  fontWeight: 600,
                }}>
                  {driftReport.has_drift ? 'Changes detected since last approval' : driftReport.summary}
                </div>
                {driftReport.baseline_sha && (
                  <Typography variant="body2" style={{ marginBottom: 8, color: '#757575' }}>
                    Baseline: <code>{driftReport.baseline_sha.substring(0, 7)}</code>
                    {' → HEAD: '}
                    <code>{driftReport.current_sha.substring(0, 7)}</code>
                  </Typography>
                )}
                {driftReport.has_drift && (
                  <Typography variant="body2" style={{ marginBottom: 12 }}>
                    {driftReport.summary}
                  </Typography>
                )}
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
                    {driftReport.changes.map((change, ci) => {
                      const sevColor = change.severity === 'critical' ? '#f44336'
                        : change.severity === 'warning' ? '#ff9800'
                        : '#2196f3';
                      return (
                        <tr key={ci} style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                          <td style={{ padding: '6px 8px' }}>
                            <Chip
                              label={change.severity || 'info'}
                              size="small"
                              style={{
                                backgroundColor: sevColor,
                                color: '#fff',
                                fontWeight: 600,
                                fontSize: '0.7rem',
                              }}
                            />
                          </td>
                          <td style={{ padding: '6px 8px', fontFamily: 'monospace' }}>{change.file}</td>
                          <td style={{ padding: '6px 8px' }}>{change.comparing}</td>
                          <td style={{ padding: '6px 8px' }}>{change.difference}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </InfoCard>
            )}

            <InfoCard title="Validation Report">
              {validationLoading ? (
                <Progress />
              ) : validationReport ? (
                <div>
                  <div style={{
                    padding: '8px 16px',
                    marginBottom: 16,
                    borderRadius: 4,
                    backgroundColor: validationReport.passed ? '#e8f5e9' : '#ffebee',
                    color: validationReport.passed ? '#2e7d32' : '#c62828',
                    fontWeight: 600,
                  }}>
                    {validationReport.passed ? 'All checks passed' : 'Some checks failed'}
                  </div>
                  {validationReport.commit_sha && (
                    <Typography variant="body2" style={{ marginBottom: 16, color: '#757575' }}>
                      Validated against commit <code>{validationReport.commit_sha.substring(0, 7)}</code>
                    </Typography>
                  )}
                  {Object.entries(
                    (validationReport.results || []).reduce((acc, check) => {
                      (acc[check.group] = acc[check.group] || []).push(check);
                      return acc;
                    }, {} as Record<string, typeof validationReport.results>),
                  ).map(([group, checks]) => (
                    <div key={group} style={{ marginBottom: 12 }}>
                      <Typography variant="subtitle2" style={{ fontWeight: 600, marginBottom: 4 }}>
                        Group {group}: {CHECK_GROUP_LABELS[group] || group}
                      </Typography>
                      {checks.map(check => (
                        <div key={check.check_id} style={{ display: 'flex', gap: 8, alignItems: 'baseline', paddingLeft: 16, marginBottom: 2 }}>
                          <span style={{ color: STATUS_COLORS[check.status], fontWeight: 700, fontFamily: 'monospace', width: 16 }}>
                            {STATUS_ICONS[check.status]}
                          </span>
                          <Typography variant="body2">
                            {check.message}
                          </Typography>
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              ) : (
                <Typography variant="body2">No validation report available</Typography>
              )}
            </InfoCard>

            {/* Approval Checklist Answers */}
            {validationReport?.approval_checklist?.content && (
              <InfoCard title="Content Review — Approval Checklist">
                <Grid container spacing={2}>
                  <Grid item xs={6}>
                    <Typography className={classes.label}>Prerequisites Verifiable</Typography>
                    <Typography variant="body2" style={{ backgroundColor: 'rgba(255,255,255,0.08)', padding: 12, borderRadius: 4 }}>
                      {validationReport.approval_checklist.content.prerequisites_verifiable == null
                        ? '— not set —'
                        : validationReport.approval_checklist.content.prerequisites_verifiable ? 'Yes' : 'No'}
                    </Typography>
                  </Grid>
                  <Grid item xs={6}>
                    <Typography className={classes.label}>Assessment Strategy</Typography>
                    <Typography variant="body2" style={{ whiteSpace: 'pre-wrap', backgroundColor: 'rgba(255,255,255,0.08)', padding: 12, borderRadius: 4 }}>
                      {validationReport.approval_checklist.content.assessment_strategy || '— not set (optional for classic) —'}
                    </Typography>
                  </Grid>
                  {validationReport.approval_checklist.content.catalog_gap && (
                    <Grid item xs={12}>
                      <Typography className={classes.label}>Catalog Gap</Typography>
                      <Typography variant="body2" style={{ whiteSpace: 'pre-wrap', backgroundColor: 'rgba(255,255,255,0.08)', padding: 12, borderRadius: 4 }}>
                        {validationReport.approval_checklist.content.catalog_gap}
                      </Typography>
                    </Grid>
                  )}
                  {validationReport.approval_checklist.content.design_overview && (
                    <Grid item xs={12}>
                      <Typography className={classes.label}>Design Overview</Typography>
                      <Typography variant="body2" style={{ whiteSpace: 'pre-wrap', backgroundColor: 'rgba(255,255,255,0.08)', padding: 12, borderRadius: 4, lineHeight: 1.6 }}>
                        {validationReport.approval_checklist.content.design_overview}
                      </Typography>
                    </Grid>
                  )}
                  {(validationReport.approval_checklist.content.module_summaries ?? []).length > 0 && (
                    <Grid item xs={12}>
                      <Typography className={classes.label}>Module Summaries</Typography>
                      <div style={{ backgroundColor: 'rgba(255,255,255,0.08)', padding: 12, borderRadius: 4 }}>
                        {validationReport.approval_checklist.content.module_summaries!.map((m, i) => (
                          <div key={i} style={{ marginBottom: i < validationReport.approval_checklist!.content!.module_summaries!.length - 1 ? 12 : 0 }}>
                            <Typography variant="subtitle2" style={{ fontWeight: 600 }}>{m.title}</Typography>
                            <Typography variant="body2" style={{ marginTop: 4 }}>{m.overview}</Typography>
                          </div>
                        ))}
                      </div>
                    </Grid>
                  )}
                  {validationReport.approval_checklist.content.rcars_overlap_pct != null && (
                    <Grid item xs={12}>
                      <Typography className={classes.label}>RCARS Overlap</Typography>
                      <Typography variant="body2" style={{ fontWeight: 600 }}>
                        {validationReport.approval_checklist.content.rcars_overlap_pct}%
                      </Typography>
                    </Grid>
                  )}
                  {(validationReport.approval_checklist.content.rcars_top_matches ?? []).length > 0 && (
                    <Grid item xs={12}>
                      <Typography className={classes.label}>RCARS Top Matches</Typography>
                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem', marginTop: 4 }}>
                        <thead>
                          <tr style={{ borderBottom: '2px solid rgba(255,255,255,0.12)', textAlign: 'left' }}>
                            <th style={{ padding: '6px 8px' }}>Catalog Item</th>
                            <th style={{ padding: '6px 8px' }}>Display Name</th>
                            <th style={{ padding: '6px 8px' }}>Relevance</th>
                            <th style={{ padding: '6px 8px' }}>Why It Fits</th>
                            <th style={{ padding: '6px 8px' }}>Link</th>
                          </tr>
                        </thead>
                        <tbody>
                          {validationReport.approval_checklist.content.rcars_top_matches!.map((m, i) => (
                            <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                              <td style={{ padding: '6px 8px', fontFamily: 'monospace' }}>{m.ci_name}</td>
                              <td style={{ padding: '6px 8px' }}>{m.display_name || m.title || '—'}</td>
                              <td style={{ padding: '6px 8px' }}>{m.relevance_score != null ? `${m.relevance_score}%` : '—'}</td>
                              <td style={{ padding: '6px 8px', maxWidth: 300 }}>{m.why_it_fits || '—'}</td>
                              <td style={{ padding: '6px 8px' }}>
                                {m.url ? <a href={m.url} target="_blank" rel="noopener noreferrer">View</a> : '—'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </Grid>
                  )}
                </Grid>
              </InfoCard>
            )}

            {validationReport?.spec_environment && (() => {
              const env = validationReport.spec_environment!;
              const has = (v: any) => v != null && v !== '' && v !== 0;
              const hasArr = (v: any[] | undefined) => v && v.length > 0;
              return (
                <InfoCard title="Infra Review — Environment Spec">
                  <Grid container spacing={2}>
                    {has(env.platform) && (
                      <Grid item xs={4}><DetailField label="Platform" value={env.platform!} /></Grid>
                    )}
                    {has(env.topology) && (
                      <Grid item xs={4}><DetailField label="Topology" value={env.topology!} /></Grid>
                    )}
                    {has(env.ocp_version) && (
                      <Grid item xs={4}><DetailField label="OCP Version" value={env.ocp_version!} /></Grid>
                    )}
                    {has(env.cloud_provider) && (
                      <Grid item xs={4}><DetailField label="Cloud Provider" value={env.cloud_provider!} /></Grid>
                    )}
                    {has(env.cluster_type) && (
                      <Grid item xs={4}><DetailField label="Cluster Type" value={env.cluster_type!} /></Grid>
                    )}
                    {has(env.control_plane_instance_count) && (
                      <Grid item xs={4}><DetailField label="Control Plane Nodes" value={String(env.control_plane_instance_count)} /></Grid>
                    )}
                    {has(env.control_plane_cpu) && (
                      <Grid item xs={4}><DetailField label="Control Plane CPU / RAM" value={`${env.control_plane_cpu} vCPU / ${env.control_plane_ram_gb ?? '?'} GB`} /></Grid>
                    )}
                    {has(env.worker_count) && (
                      <Grid item xs={4}><DetailField label="Worker Nodes" value={String(env.worker_count)} /></Grid>
                    )}
                    {has(env.worker_cpu) && (
                      <Grid item xs={4}><DetailField label="Worker CPU / RAM" value={`${env.worker_cpu} vCPU / ${env.worker_ram_gb ?? '?'} GB`} /></Grid>
                    )}
                    {has(env.worker_disk_gb) && (
                      <Grid item xs={4}><DetailField label="Worker Disk" value={`${env.worker_disk_gb} GB`} /></Grid>
                    )}
                    {has(env.max_concurrent_users) && (
                      <Grid item xs={4}><DetailField label="Max Concurrent Users" value={String(env.max_concurrent_users)} /></Grid>
                    )}
                    {has(env.ai_requirement) && env.ai_requirement !== 'none' && (
                      <Grid item xs={4}><DetailField label="AI Requirement" value={env.ai_requirement!} /></Grid>
                    )}
                    {has(env.ai_model_tier) && (
                      <Grid item xs={4}><DetailField label="AI Model" value={`${env.ai_model_tier}${env.ai_model_name ? ` — ${env.ai_model_name}` : ''}`} /></Grid>
                    )}
                    {has(env.ai_justification) && (
                      <Grid item xs={12}><DetailField label="AI Justification" value={env.ai_justification!} /></Grid>
                    )}
                    {has(env.gpu_nodes) && (
                      <Grid item xs={4}><DetailField label="GPU" value={`${env.gpu_nodes}x ${env.gpu_type || '?'}`} /></Grid>
                    )}
                    {has(env.aap_version) && (
                      <Grid item xs={4}><DetailField label="AAP Version" value={env.aap_version!} /></Grid>
                    )}
                    {hasArr(env.external_services) && (
                      <Grid item xs={6}><DetailField label="External Services" value={env.external_services!.join(', ')} /></Grid>
                    )}
                    {hasArr(env.non_ga_products) && (
                      <Grid item xs={6}><DetailField label="Non-GA Products" value={env.non_ga_products!.join(', ')} /></Grid>
                    )}
                    {has(env.non_ga_access_plan) && (
                      <Grid item xs={12}><DetailField label="Non-GA Access Plan" value={env.non_ga_access_plan!} /></Grid>
                    )}
                    {(env.vms_per_student ?? []).length > 0 && (
                      <Grid item xs={12}>
                        <Typography className={classes.label}>VMs per Student</Typography>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem', marginTop: 4 }}>
                          <thead>
                            <tr style={{ borderBottom: '2px solid rgba(255,255,255,0.12)', textAlign: 'left' }}>
                              <th style={{ padding: '6px 8px' }}>Role</th>
                              <th style={{ padding: '6px 8px' }}>Count</th>
                              <th style={{ padding: '6px 8px' }}>CPU</th>
                              <th style={{ padding: '6px 8px' }}>RAM</th>
                              <th style={{ padding: '6px 8px' }}>Disk</th>
                              <th style={{ padding: '6px 8px' }}>OS</th>
                            </tr>
                          </thead>
                          <tbody>
                            {env.vms_per_student!.map((vm, i) => (
                              <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                                <td style={{ padding: '6px 8px', fontFamily: 'monospace' }}>{vm.role}</td>
                                <td style={{ padding: '6px 8px' }}>{vm.count}</td>
                                <td style={{ padding: '6px 8px' }}>{vm.cpu} vCPU</td>
                                <td style={{ padding: '6px 8px' }}>{vm.ram_gb} GB</td>
                                <td style={{ padding: '6px 8px' }}>{vm.disk_gb} GB</td>
                                <td style={{ padding: '6px 8px' }}>{vm.os}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </Grid>
                    )}
                  </Grid>
                </InfoCard>
              );
            })()}

            {/* Approve / Reject / Message buttons */}
            {canReview && (validationReport || driftReport) && (
              <InfoCard>
                <div style={{ display: 'flex', gap: 12 }}>
                  <Button
                    variant="contained"
                    style={{ backgroundColor: '#4caf50', color: '#fff', fontWeight: 600 }}
                    size="large"
                    startIcon={
                      approvingStage === summary.stage ? (
                        <CircularProgress size={16} color="inherit" />
                      ) : undefined
                    }
                    onClick={() => handleApprove(summary.stage)}
                    disabled={approvingStage !== null}
                  >
                    {approvingStage === summary.stage ? 'Approving...' : 'Approve'}
                  </Button>
                  <Button
                    variant="contained"
                    style={{ backgroundColor: '#e57373', color: '#fff', fontWeight: 600 }}
                    size="large"
                    disabled={approvingStage !== null}
                    onClick={() => handleReject(summary.stage)}
                  >
                    Reject
                  </Button>
                </div>
              </InfoCard>
            )}
          </>
        )}

        {hasStagingTab && activeTab === stagingTabIndex && (
          <InfoCard title="Catalog Item Env Setup">
            <Typography variant="body2" style={{ marginBottom: 16, color: '#757575' }}>
              Provide the AgnosticV catalog item URL and demo.redhat.com CI link for this project.
            </Typography>
            {wd?.agnosticvUrls?.length && !canStaging ? (
              <Grid container spacing={2}>
                <Grid item xs={12}>
                  <Typography variant="body2" style={{ color: '#757575', marginBottom: 4 }}>AgnosticV Catalog Item URLs</Typography>
                  {(wd.agnosticvUrls || []).map((url: string, i: number) => (
                    <div key={i}><a href={url} target="_blank" rel="noopener noreferrer" style={{ wordBreak: 'break-all' }}>{url}</a></div>
                  ))}
                </Grid>
                <Grid item xs={12}>
                  <Typography variant="body2" style={{ color: '#757575', marginBottom: 4 }}>demo.redhat.com CI Links</Typography>
                  {(wd.ciUrls || []).length ? (wd.ciUrls || []).map((url: string, i: number) => (
                    <div key={i}><a href={url} target="_blank" rel="noopener noreferrer" style={{ wordBreak: 'break-all' }}>{url}</a></div>
                  )) : (
                    <Typography variant="body1">—</Typography>
                  )}
                </Grid>
              </Grid>
            ) : (
              <>
                <Typography variant="body2" style={{ color: '#757575', marginBottom: 8 }}>AgnosticV Catalog Item URLs</Typography>
                {stagingAgnosticvUrls.map((url, i) => (
                  <div key={i} style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                    <TextField
                      placeholder="https://github.com/rhpds/agnosticv/tree/master/agd_v2/..."
                      fullWidth
                      variant="outlined"
                      size="small"
                      value={url}
                      onChange={e => {
                        const next = [...stagingAgnosticvUrls];
                        next[i] = e.target.value;
                        setStagingAgnosticvUrls(next);
                      }}
                      disabled={!canStaging || submittingStaging}
                    />
                    {stagingAgnosticvUrls.length > 1 && (
                      <Button size="small" onClick={() => setStagingAgnosticvUrls(stagingAgnosticvUrls.filter((_, j) => j !== i))} disabled={!canStaging || submittingStaging}>Remove</Button>
                    )}
                  </div>
                ))}
                {canStaging && (
                  <Button size="small" onClick={() => setStagingAgnosticvUrls([...stagingAgnosticvUrls, ''])} disabled={submittingStaging} style={{ marginBottom: 16 }}>+ Add URL</Button>
                )}

                <Typography variant="body2" style={{ color: '#757575', marginBottom: 8, marginTop: 8 }}>demo.redhat.com CI Links</Typography>
                {stagingCiUrls.map((url, i) => (
                  <div key={i} style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                    <TextField
                      placeholder="https://catalog.demo.redhat.com/catalog/..."
                      fullWidth
                      variant="outlined"
                      size="small"
                      value={url}
                      onChange={e => {
                        const next = [...stagingCiUrls];
                        next[i] = e.target.value;
                        setStagingCiUrls(next);
                      }}
                      disabled={!canStaging || submittingStaging}
                    />
                    {stagingCiUrls.length > 1 && (
                      <Button size="small" onClick={() => setStagingCiUrls(stagingCiUrls.filter((_, j) => j !== i))} disabled={!canStaging || submittingStaging}>Remove</Button>
                    )}
                  </div>
                ))}
                {canStaging && (
                  <Button size="small" onClick={() => setStagingCiUrls([...stagingCiUrls, ''])} disabled={submittingStaging} style={{ marginBottom: 16 }}>+ Add URL</Button>
                )}

                {canStaging && (
                  <div style={{ marginTop: 16 }}>
                    <Button
                      variant="contained"
                      color="primary"
                      size="large"
                      style={{ fontWeight: 600 }}
                      onClick={handleStagingSubmit}
                      disabled={submittingStaging || !stagingAgnosticvUrls.some(u => u.trim()) || !stagingCiUrls.some(u => u.trim())}
                      startIcon={submittingStaging ? <CircularProgress size={16} color="inherit" /> : undefined}
                    >
                      {submittingStaging ? 'Submitting...' : 'Submit'}
                    </Button>
                  </div>
                )}
              </>
            )}
          </InfoCard>
        )}

        {hasTestingTab && activeTab === testingTabIndex && (
          <InfoCard title="Testing Comments">
            <Typography variant="body2" style={{ marginBottom: 16, color: '#757575' }}>
              Comments posted here are forwarded to the Testing Jira ticket.
            </Typography>
            {canPostTestingComment && (
              <div style={{ marginBottom: 24 }}>
                <TextField
                  label="Add a comment"
                  placeholder="Enter your testing feedback..."
                  fullWidth
                  multiline
                  minRows={3}
                  variant="outlined"
                  value={testingCommentText}
                  onChange={e => setTestingCommentText(e.target.value)}
                  disabled={submittingTestingComment}
                  style={{ marginBottom: 8 }}
                />
                <div style={{ display: 'flex', gap: 8 }}>
                  <Button
                    variant="contained"
                    color="primary"
                    size="small"
                    style={{ fontWeight: 600 }}
                    onClick={handlePostTestingComment}
                    disabled={submittingTestingComment || !testingCommentText.trim()}
                    startIcon={submittingTestingComment ? <CircularProgress size={16} color="inherit" /> : undefined}
                  >
                    {submittingTestingComment ? 'Posting...' : 'Post Comment'}
                  </Button>
                  <IconButton size="small" onClick={loadTestingComments} disabled={loadingTestingComments}>
                    <RefreshIcon fontSize="small" />
                  </IconButton>
                </div>
              </div>
            )}
            {loadingTestingComments ? (
              <Progress />
            ) : testingComments.length > 0 ? (
              <div>
                {testingComments.map((c, i) => (
                  <div key={i} style={{
                    padding: '12px 16px',
                    marginBottom: 8,
                    borderRadius: 4,
                    backgroundColor: 'rgba(255,255,255,0.06)',
                    borderLeft: '3px solid #1976d2',
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <Typography variant="subtitle2" style={{ fontWeight: 600 }}>{c.author}</Typography>
                      <Typography variant="caption" style={{ color: '#757575' }}>
                        {new Date(c.created).toLocaleString()}
                      </Typography>
                    </div>
                    <Typography variant="body2" style={{ whiteSpace: 'pre-wrap' }}>{c.text}</Typography>
                  </div>
                ))}
              </div>
            ) : (
              <Typography variant="body2" style={{ color: '#757575' }}>No comments yet.</Typography>
            )}
            {canCompleteTesting && summary.stage === 'testing' && (
              <div style={{ marginTop: 16 }}>
                <Button
                  variant="contained"
                  size="small"
                  style={{ fontWeight: 600, backgroundColor: '#4caf50' }}
                  onClick={handleCompleteTesting}
                  disabled={completingTesting}
                  startIcon={completingTesting ? <CircularProgress size={16} color="inherit" /> : undefined}
                >
                  {completingTesting ? 'Completing...' : 'Complete Testing'}
                </Button>
              </div>
            )}
          </InfoCard>
        )}

        {activeTab === timelineTabIndex && (
          <InfoCard title="Timeline">
            <Grid container spacing={3}>
              <Grid item xs={12} md={6}>
                <DetailField
                  label="Started"
                  value={summary.startedAt ? new Date(summary.startedAt).toLocaleString() : ''}
                />
                <DetailField
                  label="Last Updated"
                  value={summary.lastUpdate ? new Date(summary.lastUpdate).toLocaleString() : ''}
                />
                <DetailField label="Jira Ticket" value={summary.epicKey} />
                {STAGE_DESCRIPTIONS[summary.stage] && (
                  <DetailField label="What's Happening" value={STAGE_DESCRIPTIONS[summary.stage]} />
                )}
              </Grid>
              <Grid item xs={12} md={6}>
                {wd?.baselineSha && (
                  <DetailField label="Baseline Commit" value={wd.baselineSha.substring(0, 7)} />
                )}
                {wd?.auditTrailSha && (
                  <DetailField label="Last Known Commit" value={wd.auditTrailSha.substring(0, 7)} />
                )}
              </Grid>
            </Grid>
            {reviewHistory.length > 0 && (
              <div style={{ marginTop: 16 }}>
                <Typography variant="subtitle2" style={{ fontWeight: 600, marginBottom: 8 }}>
                  Audit History
                </Typography>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid #e0e0e0', textAlign: 'left' }}>
                      <th style={{ padding: '6px 8px' }}>When</th>
                      <th style={{ padding: '6px 8px' }}>Who</th>
                      <th style={{ padding: '6px 8px' }}>Stage</th>
                      <th style={{ padding: '6px 8px' }}>Action</th>
                      <th style={{ padding: '6px 8px' }}>Commit</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...reviewHistory].reverse().map((entry, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid #f0f0f0' }}>
                        <td style={{ padding: '6px 8px' }}>
                          {(() => {
                            if (!entry.timestamp) return '—';
                            const n = Number(entry.timestamp);
                            if (!isNaN(n) && n > 1_000_000_000 && n < 10_000_000_000_000) {
                              return new Date(n < 10_000_000_000 ? n * 1000 : n).toLocaleString();
                            }
                            return new Date(entry.timestamp).toLocaleString();
                          })()}
                        </td>
                        <td style={{ padding: '6px 8px' }}>{entry.user || '—'}</td>
                        <td style={{ padding: '6px 8px' }}>{STAGE_LABELS[entry.stage as WorkflowStage] || entry.stage}</td>
                        <td style={{ padding: '6px 8px' }}>
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                            <Chip
                              label={entry.action}
                              size="small"
                              style={{
                                backgroundColor: entry.action === 'approved' ? '#e8f5e9' : entry.action === 'rejected' ? '#ffebee' : '#e3f2fd',
                                color: entry.action === 'approved' ? '#2e7d32' : entry.action === 'rejected' ? '#c62828' : '#1565c0',
                              }}
                            />
                            {entry.action === 'rejected' && (entry as any).reasons?.length > 0 && (
                              <InfoOutlinedIcon
                                style={{ fontSize: 16, color: '#c62828', cursor: 'pointer' }}
                                onClick={(e) => setReasonsPopover({ anchorEl: e.currentTarget as unknown as HTMLElement, reasons: (entry as any).reasons })}
                              />
                            )}
                          </span>
                        </td>
                        <td style={{ padding: '6px 8px', fontFamily: 'monospace' }}>
                          {entry.commitSha ? entry.commitSha.substring(0, 7) : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </InfoCard>
        )}

        <Popover
          open={Boolean(reasonsPopover.anchorEl)}
          anchorEl={reasonsPopover.anchorEl}
          onClose={() => setReasonsPopover({ anchorEl: null, reasons: [] })}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
          transformOrigin={{ vertical: 'top', horizontal: 'left' }}
        >
          <div style={{ padding: '12px 16px', maxWidth: 320 }}>
            <Typography variant="subtitle2" style={{ marginBottom: 8, color: '#c62828' }}>Rejection Reasons</Typography>
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              {reasonsPopover.reasons.map((r) => (
                <li key={r.id} style={{ marginBottom: 4 }}>
                  <Typography variant="body2">{r.text}</Typography>
                </li>
              ))}
            </ul>
          </div>
        </Popover>

        <RejectionDialog
          open={rejectionDialogOpen}
          stage={rejectingStage || 'content_review'}
          reviewerName={summary.ssoEmail || summary.owner}
          submitting={submittingRejection}
          onConfirm={handleRejectionConfirm}
          onCancel={handleRejectionCancel}
        />

        <MessageDialog
          open={messageDialogOpen}
          stage={summary.stage}
          senderName={summary.ssoEmail || summary.owner}
          submitting={sendingMessage}
          onConfirm={handleSendMessage}
          onCancel={() => setMessageDialogOpen(false)}
        />

        <Snackbar
          open={snackbar.open}
          autoHideDuration={snackbar.severity === 'error' ? null : 6000}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
          onClose={() => setSnackbar(s => ({ ...s, open: false }))}
        >
          <Alert
            onClose={() => setSnackbar(s => ({ ...s, open: false }))}
            severity={snackbar.severity}
            variant="filled"
          >
            {snackbar.message}
          </Alert>
        </Snackbar>
      </Content>
    </Page>
  );
}
