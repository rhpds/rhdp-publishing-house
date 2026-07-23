import React, { useState, useCallback, useMemo } from 'react';
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
  CircularProgress,
  IconButton,
  Snackbar,
  Tabs,
  Tab,
} from '@material-ui/core';
import { Alert } from '@material-ui/lab';
import GitHubIcon from '@material-ui/icons/GitHub';
import BugReportIcon from '@material-ui/icons/BugReport';
import RefreshIcon from '@material-ui/icons/Refresh';
import ReplayIcon from '@material-ui/icons/Replay';
import { createPhWorkflowsClient } from '../../api/client';
import { WorkflowStage, RejectionData, ValidationReport, CheckStatus, DriftReport } from '../../api/types';
import { STAGE_LABELS, STAGE_DESCRIPTIONS } from '../../utils/stageMapping';

const REVIEW_STAGES: WorkflowStage[] = ['content_review', 'infra_review', 'drift_review'];

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

  const client = useMemo(() => createPhWorkflowsClient({ discoveryApi, fetchApi }), [discoveryApi, fetchApi]);

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
    if (!REVIEW_STAGES.includes(stage)) return;

    const repoUrl = result.summary.repoUrl;
    const wd = result.instance?.variables?.workflowdata as any;
    const approvedSha = wd?.approvedSha;
    if (!repoUrl) return;

    const slug = result.summary.projectId;

    const isDriftReview = stage === 'drift_review';

    if (!isDriftReview) setValidationLoading(true);
    if (approvedSha) setDriftLoading(true);

    const validationPromise = isDriftReview
      ? Promise.resolve()
      : client.fetchValidationReport(slug, repoUrl, 'main', approvedSha)
          .then(report => setValidationReport(report))
          .catch((err: any) => setSnackbar({ open: true, severity: 'error', message: `Validation report failed: ${err.message}` }))
          .finally(() => setValidationLoading(false));

    const driftPromise = approvedSha
      ? client.fetchDriftReport(slug, repoUrl, 'main', approvedSha)
          .then(report => setDriftReport(report))
          .catch((err: any) => setSnackbar({ open: true, severity: 'error', message: `Drift check failed: ${err.message}` }))
          .finally(() => setDriftLoading(false))
      : Promise.resolve().then(() => { setDriftReport(null); setDriftLoading(false); });

    await Promise.all([validationPromise, driftPromise]);
  }, [result, client]);

  React.useEffect(() => {
    if (result && REVIEW_STAGES.includes(result.summary.stage)) {
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
      await client.sendRejectionEvent(result.summary.id, rejectingStage, data, result.summary.projectId, validationReport?.commit_sha);
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
  const wd = instance?.variables?.workflowdata as any;
  const reviewHistory: Array<{ user: string; stage: string; action: string; timestamp: string; commitSha?: string }> = wd?.reviewHistory ?? [];

  const isReviewStage = REVIEW_STAGES.includes(summary.stage);

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
            rejectedFrom={rejectedFrom}
            hasDrift={wd?.hasDrift}
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
          {isReviewStage && <Tab label="Review" />}
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

        {isReviewStage && activeTab === 1 && (
          <>
            {/* Spec File Links */}
            {summary.repoUrl && (
              <InfoCard title="Spec Files">
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {[
                    { label: 'spec.yaml', path: 'publishing-house/spec.yaml' },
                    { label: 'design.md', path: 'publishing-house/spec/design.md' },
                    { label: 'Module Outlines', path: 'publishing-house/spec/modules' },
                    { label: 'automation-manifest.yaml', path: 'publishing-house/spec/automation-manifest.yaml' },
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

            {(driftLoading || driftReport) && (
              <InfoCard title="Changes Since Last Approval">
                {driftLoading ? (
                  <Progress />
                ) : driftReport ? (
                  <div>
                    <div style={{
                      padding: '8px 16px',
                      marginBottom: 16,
                      borderRadius: 4,
                      backgroundColor: driftReport.has_drift ? '#fff3e0' : '#e8f5e9',
                      color: driftReport.has_drift ? '#e65100' : '#2e7d32',
                      fontWeight: 600,
                    }}>
                      {driftReport.has_drift ? 'Design changes detected since last approval' : 'No design changes since last approval'}
                    </div>
                    <Typography variant="body2" style={{ marginBottom: 8, color: '#757575' }}>
                      Approved: <code>{driftReport.approved_sha.substring(0, 7)}</code>
                      {' → Current: '}
                      <code>{driftReport.current_sha.substring(0, 7)}</code>
                    </Typography>
                    <Typography variant="body2" style={{ marginBottom: 12 }}>
                      {driftReport.summary}
                    </Typography>
                    {driftReport.has_drift && driftReport.changes.map((fileChange, fi) => (
                      <div key={fi} style={{ marginBottom: 16 }}>
                        <Typography variant="subtitle2" style={{ marginBottom: 8, fontFamily: 'monospace' }}>
                          {fileChange.file}
                        </Typography>
                        {fileChange.sections.map((sec, si) => (
                          <div key={si} style={{ marginBottom: 8, marginLeft: 8 }}>
                            <Typography variant="body2" style={{ fontWeight: 600, marginBottom: 4 }}>
                              {sec.section}
                            </Typography>
                            <ul style={{ margin: 0, paddingLeft: 20 }}>
                              {sec.changes.map((c, ci) => (
                                <li key={ci} style={{ marginBottom: 2 }}>{c}</li>
                              ))}
                            </ul>
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                ) : null}
              </InfoCard>
            )}

            {summary.stage !== 'drift_review' && (
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
            )}

            {summary.stage !== 'drift_review' && (
            <>
            {/* Approval Checklist Answers */}
            {validationReport?.approval_checklist?.content && (
              <InfoCard title="Content Review — Approval Checklist">
                <Grid container spacing={2}>
                  <Grid item xs={12}>
                    <DetailField
                      label="Prerequisites Verifiable (Q22)"
                      value={validationReport.approval_checklist.content.prerequisites_verifiable === null ? 'Not set' : String(validationReport.approval_checklist.content.prerequisites_verifiable)}
                    />
                  </Grid>
                  <Grid item xs={12}>
                    <Typography className={classes.label}>Assessment Strategy (Q23)</Typography>
                    <Typography variant="body2" style={{ whiteSpace: 'pre-wrap', backgroundColor: 'rgba(255,255,255,0.08)', padding: 12, borderRadius: 4 }}>
                      {validationReport.approval_checklist.content.assessment_strategy || '— not set —'}
                    </Typography>
                  </Grid>
                  <Grid item xs={12}>
                    <Typography className={classes.label}>Differentiation (Q24)</Typography>
                    <Typography variant="body2" style={{ whiteSpace: 'pre-wrap', backgroundColor: 'rgba(255,255,255,0.08)', padding: 12, borderRadius: 4 }}>
                      {validationReport.approval_checklist.content.differentiation || '— not set —'}
                    </Typography>
                  </Grid>
                  {validationReport.approval_checklist.content.rcars_overlap_pct != null && (
                    <Grid item xs={12}>
                      <Typography className={classes.label}>RCARS Overlap</Typography>
                      <Typography variant="body2" style={{ fontWeight: 600, color: (validationReport.approval_checklist.content.rcars_overlap_pct ?? 0) > 60 ? '#ef5350' : '#66bb6a' }}>
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
                  </Grid>
                </InfoCard>
              );
            })()}
            </>
            )}

            {/* Approve / Reject buttons */}
            {(validationReport || driftReport) && (
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

        {activeTab === (isReviewStage ? 2 : 1) && (
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
                {wd?.approvedSha && (
                  <DetailField label="Approved Commit" value={wd.approvedSha.substring(0, 7)} />
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
                          <Chip
                            label={entry.action}
                            size="small"
                            style={{
                              backgroundColor: entry.action === 'approved' ? '#e8f5e9' : entry.action === 'rejected' ? '#ffebee' : '#e3f2fd',
                              color: entry.action === 'approved' ? '#2e7d32' : entry.action === 'rejected' ? '#c62828' : '#1565c0',
                            }}
                          />
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
