import React, { useState, useCallback, useEffect, useMemo } from 'react';
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
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Checkbox,
  FormControlLabel,
} from '@material-ui/core';
import { Alert } from '@material-ui/lab';
import GitHubIcon from '@material-ui/icons/GitHub';
import BugReportIcon from '@material-ui/icons/BugReport';
import RefreshIcon from '@material-ui/icons/Refresh';
import ReplayIcon from '@material-ui/icons/Replay';
import InfoOutlinedIcon from '@material-ui/icons/InfoOutlined';
import MenuBookIcon from '@material-ui/icons/MenuBook';
import ExpandMoreIcon from '@material-ui/icons/ExpandMore';
import ExpandLessIcon from '@material-ui/icons/ExpandLess';
import ErrorIcon from '@material-ui/icons/Error';
import AddIcon from '@material-ui/icons/Add';
import DeleteIcon from '@material-ui/icons/Delete';
import { createPhWorkflowsClient } from '../../api/client';
import { WorkflowStage, RejectionData, ValidationReport, CheckStatus, DriftReport, RcarsMatch } from '../../api/types';
import { STAGE_LABELS, STAGE_DESCRIPTIONS, stageIndex } from '../../utils/stageMapping';
import { useUserGroups } from '../../hooks/useUserGroups';

const REVIEW_STAGES: WorkflowStage[] = ['pre_intake_review', 'content_review', 'infra_review'];
const STAGES_WITH_REVIEW_TAB: WorkflowStage[] = [
  'content_review', 'infra_review', 'env_setup', 'development', 'testing', 'published',
];
const PRE_INTAKE_STAGES: WorkflowStage[] = ['pre_intake_review'];
const STAGES_WITH_DEVELOPMENT_TAB: WorkflowStage[] = ['development', 'testing', 'published'];

// Expected next stages after approval/completion (matches workflow transitions)
// Some stages can transition to multiple targets depending on decision
const EXPECTED_NEXT_STAGES: Record<string, WorkflowStage[]> = {
  pre_intake_review: ['intake'],                // Approved → Intake (no reject)
  intake: ['content_review'],                   // Intake → ContentReview
  content_review: ['intake', 'infra_review'],   // Rejected → Intake, Approved → InfraReview
  infra_review: ['intake', 'env_setup', 'development'], // Rejected → Intake, Approved → EnvSetup or Development
  env_setup: ['development'],                   // EnvSetup → Development
  development: ['testing'],                     // Development → Testing
  testing: ['published'],                       // Testing → Published
};

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
import { TagEditor } from './TagEditor';

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

  const [currentUserEmail, setCurrentUserEmail] = useState<string>('');
  const [validationReport, setValidationReport] = useState<ValidationReport | null>(null);
  const [validationLoading, setValidationLoading] = useState(false);
  const [driftReport, setDriftReport] = useState<DriftReport | null>(null);
  const [driftLoading, setDriftLoading] = useState(false);

  useEffect(() => {
    identityApi.getProfileInfo().then(profile => {
      if (profile.email) setCurrentUserEmail(profile.email);
    }).catch(() => {});
  }, [identityApi]);

  const fetchReport = useCallback(async () => {
    if (!result) return;
    const stage = result.summary.stage;
    if (!STAGES_WITH_REVIEW_TAB.includes(stage)) return;

    const repoUrl = result.summary.repoUrl;
    const wd = result.instance?.variables?.workflowdata as any;
    const baselineSha = wd?.baselineSha;
    if (!repoUrl) return;

    const slug = result.summary.id; // Use workflow_id for all API calls
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

  // Fetch module statuses from spec data
  useEffect(() => {
    if (!result || !STAGES_WITH_DEVELOPMENT_TAB.includes(result.summary.stage)) return;

    const fetchModules = async () => {
      try {
        const specData = await client.getSpecData(result.summary.id);
        const fetchedModules = specData?.spec?.modules || [];
        setModules(fetchedModules);
        const statuses: Record<string, string> = {};
        fetchedModules.forEach((mod: any) => {
          if (mod.id && mod.status) {
            statuses[mod.id] = mod.status;
          }
        });
        setModuleStatuses(statuses);
        setInitialModuleStatuses(statuses);

        // Fetch automation status
        const autoStatus = specData?.spec?.development?.automation?.status || 'not_started';
        setAutomationStatus(autoStatus);
        setInitialAutomationStatus(autoStatus);
      } catch (error) {
        console.error('Failed to fetch module data:', error);
      }
    };

    fetchModules();
  }, [result, client]);

  const handleModuleStatusChange = (moduleId: string, newStatus: string) => {
    setModuleStatuses(prev => ({ ...prev, [moduleId]: newStatus }));
  };

  const handleAutomationStatusChange = (newStatus: string) => {
    setAutomationStatus(newStatus);
  };

  const handleUpdateAllStatuses = async () => {
    if (!result) return;

    setUpdatingStatuses(true);
    const errors: string[] = [];

    try {
      // Update changed module statuses
      const moduleUpdates = Object.entries(moduleStatuses).filter(
        ([moduleId, status]) => initialModuleStatuses[moduleId] !== status
      );

      for (const [moduleId, status] of moduleUpdates) {
        try {
          await client.updateModuleStatus(result.summary.id, moduleId, status);
        } catch (error) {
          errors.push(`Failed to update ${moduleId}: ${error}`);
        }
      }

      // Update automation status if changed
      if (automationStatus !== initialAutomationStatus) {
        try {
          await client.updateAutomationStatus(result.summary.id, automationStatus);
        } catch (error) {
          errors.push(`Failed to update automation status: ${error}`);
        }
      }

      if (errors.length > 0) {
        setSnackbar({
          open: true,
          severity: 'error',
          message: `Some updates failed: ${errors.join('; ')}`,
        });
      } else {
        // Refresh to get latest state
        setInitialModuleStatuses(moduleStatuses);
        setInitialAutomationStatus(automationStatus);

        setSnackbar({
          open: true,
          severity: 'success',
          message: 'Development statuses updated successfully',
        });
      }
    } catch (error) {
      setSnackbar({
        open: true,
        severity: 'error',
        message: `Failed to update statuses: ${error}`,
      });
    } finally {
      setUpdatingStatuses(false);
    }
  };

  const hasStatusChanges = () => {
    const moduleChanged = Object.entries(moduleStatuses).some(
      ([moduleId, status]) => initialModuleStatuses[moduleId] !== status
    );
    const automationChanged = automationStatus !== initialAutomationStatus;
    return moduleChanged || automationChanged;
  };

  // Initialize pre-intake review fields from workflow data
  useEffect(() => {
    if (!result) return;
    const wd = result.instance?.variables?.workflowdata as any;
    if (!wd) return;

    // Reinitialize fields when in pre_intake_review stage (includes refresh)
    if (result.summary.stage === 'pre_intake_review') {
      setPreIntakeReviewFields({
        assetTitle: wd.assetTitle || '',
        projectDescription: wd.projectDescription || '',
        contentOutline: wd.contentOutline || '',
        learningObjectives: wd.learningObjectives || '',
        contentType: wd.contentType || 'lab',
        associatedOpportunities: wd.associatedOpportunities || '',
        salesPlayTdp: wd.salesPlayTdp || '',
        aiRelated: wd.aiRelated || false,
        canUseMaas: wd.canUseMaas != null ? wd.canUseMaas : true,
        maasModels: wd.maasModels || '',
        gpuJustification: wd.gpuJustification || '',
        partnersAccess: wd.partnersAccess || false,
        cloudProvider: wd.cloudProvider || 'cnv',
        clusterType: wd.clusterType || 'sno',
        ocpVersion: wd.ocpVersion || '4.21',
        showroomType: wd.showroomType || '',
        initiativeKey: wd.initiativeKey || 'rhdp_catalog',
        tags: wd.tags || [],
      });
    }
  }, [result]);

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
  const [approvalNotes, setApprovalNotes] = useState<Array<{ text: string }>>([]);
  const [approvalNotesDialogOpen, setApprovalNotesDialogOpen] = useState(false);
  const [stagingAgnosticvUrls, setStagingAgnosticvUrls] = useState<string[]>(['']);
  const [stagingCiUrls, setStagingCiUrls] = useState<string[]>(['']);
  const [submittingStaging, setSubmittingStaging] = useState(false);
  const [testingNoteText, setTestingNoteText] = useState('');
  const [submittingTestingNote, setSubmittingTestingNote] = useState(false);
  const [completingTesting, setCompletingTesting] = useState(false);
  const [expandedRcarsRows, setExpandedRcarsRows] = useState<Set<number>>(new Set());
  const [addNoteText, setAddNoteText] = useState('');
  const [submittingNote, setSubmittingNote] = useState(false);
  const [cancelConfirmDialogOpen, setCancelConfirmDialogOpen] = useState(false);
  const [moduleStatuses, setModuleStatuses] = useState<Record<string, string>>({});
  const [modules, setModules] = useState<any[]>([]);
  const [automationStatus, setAutomationStatus] = useState<string>('not_started');
  const [initialModuleStatuses, setInitialModuleStatuses] = useState<Record<string, string>>({});
  const [initialAutomationStatus, setInitialAutomationStatus] = useState<string>('not_started');
  const [updatingStatuses, setUpdatingStatuses] = useState(false);

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
      const notes = approvalNotes.length > 0 ? approvalNotes.map(n => n.text).filter(t => t.trim()) : undefined;
      await client.sendApprovalEvent(result.summary.id, stage, result.summary.id, { user, commitSha, notes });
      setApprovalNotes([]);
      setApprovalNotesDialogOpen(false);
      setSnackbar({
        open: true,
        severity: 'success',
        message: `${STAGE_LABELS[stage]} approved — waiting for workflow to advance...`,
      });
      const currentStage = result.summary.stage;
      const expectedStages = EXPECTED_NEXT_STAGES[currentStage] || [];
      for (let i = 0; i < 12; i++) {
        await new Promise(resolve => setTimeout(resolve, 5000));
        const updated = await client.getWorkflowById(result.summary.id);
        if (updated && expectedStages.includes(updated.summary.stage)) break;
        if (updated && updated.summary.stage !== currentStage) break; // Fallback: any stage change
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
      await client.sendRejectionEvent(result.summary.id, rejectingStage, data, result.summary.id, validationReport?.commit_sha);
      setRejectionDialogOpen(false);
      setSnackbar({
        open: true,
        severity: 'success',
        message: `${STAGE_LABELS[rejectingStage]} rejected — waiting for workflow to transition...`,
      });
      const currentStage = result.summary.stage;
      const expectedStages = EXPECTED_NEXT_STAGES[currentStage] || [];
      for (let i = 0; i < 12; i++) {
        await new Promise(resolve => setTimeout(resolve, 5000));
        const updated = await client.getWorkflowById(result.summary.id);
        if (updated && expectedStages.includes(updated.summary.stage)) break;
        if (updated && updated.summary.stage !== currentStage) break; // Fallback: any stage change
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

  const [preIntakeReviewAction, setPreIntakeReviewAction] = useState<'approved' | 'cancelled' | null>(null);
  const [preIntakeReviewFields, setPreIntakeReviewFields] = useState<Record<string, any>>({});

  const handlePreIntakeReviewAction = async (action: 'approved' | 'cancelled') => {
    if (!result) return;

    // Validate required fields for approval
    if (action === 'approved' && !preIntakeReviewFields.showroomType) {
      setSnackbar({
        open: true,
        severity: 'error',
        message: 'Showroom Type is required. Please select Classic or Zero Touch.',
      });
      return;
    }

    // Validate GPU justification when AI-related and cannot use MaaS
    const aiRelated = preIntakeReviewFields.aiRelated !== undefined ? preIntakeReviewFields.aiRelated : wd?.aiRelated;
    const canUseMaas = preIntakeReviewFields.canUseMaas !== undefined ? preIntakeReviewFields.canUseMaas : wd?.canUseMaas;
    const gpuJustification = preIntakeReviewFields.gpuJustification ?? wd?.gpuJustification ?? '';

    if (action === 'approved' && aiRelated && !canUseMaas && !gpuJustification.trim()) {
      setSnackbar({
        open: true,
        severity: 'error',
        message: 'GPU Justification is required when MaaS cannot be used.',
      });
      return;
    }

    setPreIntakeReviewAction(action);
    try {
      if (action === 'cancelled') {
        // Delete project and all artifacts
        await client.deleteProject(result.summary.id, true);
        setSnackbar({
          open: true,
          severity: 'success',
          message: 'Pre-Intake Review cancelled. Workflow and artifacts deleted.',
        });
        // Navigate back to workflows list after deletion
        setTimeout(() => navigate('/publishing-house-workflows'), 2000);
      } else {
        const notes = approvalNotes.length > 0 ? approvalNotes.map(n => n.text).filter(t => t.trim()).join('\n\n') : '';
        await client.sendPreIntakeReviewAction(result.summary.id, action, preIntakeReviewFields, notes);
        setApprovalNotes([]);
        setSnackbar({
          open: true,
          severity: 'success',
          message: `Pre-Intake Review ${action} — waiting for workflow to advance...`,
        });
        const currentStage = result.summary.stage;
        const expectedStages = EXPECTED_NEXT_STAGES[currentStage] || [];
        for (let i = 0; i < 12; i++) {
          await new Promise(resolve => setTimeout(resolve, 5000));
          const updated = await client.getWorkflowById(result.summary.id);
          if (updated && expectedStages.includes(updated.summary.stage)) break;
          if (updated && updated.summary.stage !== currentStage) break; // Fallback: any stage change
        }
        setRefreshKey(k => k + 1);
      }
    } catch (err: any) {
      setSnackbar({
        open: true,
        severity: 'error',
        message: `Pre-Intake Review ${action} failed: ${err.message}`,
      });
    } finally {
      setPreIntakeReviewAction(null);
    }
  };

  const handleStagingSubmit = async () => {
    const filteredAgv = stagingAgnosticvUrls.map(u => u.trim()).filter(Boolean);
    const filteredCi = stagingCiUrls.map(u => u.trim()).filter(Boolean);
    if (!result || !filteredAgv.length || !filteredCi.length) return;
    setSubmittingStaging(true);
    try {
      await client.submitEnvSetup(result.summary.id, filteredAgv, filteredCi);
      setSnackbar({ open: true, severity: 'success', message: 'Env setup info submitted — waiting for workflow to advance...' });
      const currentStage = result.summary.stage;
      const expectedStages = EXPECTED_NEXT_STAGES[currentStage] || [];
      for (let i = 0; i < 12; i++) {
        await new Promise(resolve => setTimeout(resolve, 5000));
        const updated = await client.getWorkflowById(result.summary.id);
        if (updated && expectedStages.includes(updated.summary.stage)) break;
        if (updated && updated.summary.stage !== currentStage) break; // Fallback: any stage change
      }
      setRefreshKey(k => k + 1);
    } catch (err: any) {
      setSnackbar({ open: true, severity: 'error', message: `Env setup submit failed: ${err.message}` });
    } finally {
      setSubmittingStaging(false);
    }
  };

  const handlePostTestingNote = async () => {
    if (!result?.summary.id || !testingNoteText.trim()) return;
    setSubmittingTestingNote(true);
    try {
      await client.addNote(result.summary.id, testingNoteText.trim());
      setTestingNoteText('');
      setSnackbar({ open: true, severity: 'success', message: 'Note added.' });
      setRefreshKey(k => k + 1);
    } catch (err: any) {
      setSnackbar({ open: true, severity: 'error', message: `Add note failed: ${err.message}` });
    } finally {
      setSubmittingTestingNote(false);
    }
  };

  const handleCompleteTesting = async () => {
    if (!result?.summary.repoUrl) return;
    setCompletingTesting(true);
    try {
      await client.submitTesting(result.summary.id, result.summary.repoUrl);
      setSnackbar({ open: true, severity: 'success', message: 'Testing complete. Workflow advanced.' });
      setTimeout(() => window.location.reload(), 1500);
    } catch (err: any) {
      setSnackbar({ open: true, severity: 'error', message: `Testing submit failed: ${err.message}` });
    } finally {
      setCompletingTesting(false);
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
  const isPreIntakeReviewStage = PRE_INTAKE_STAGES.includes(summary.stage);
  const hasStagingTab = summary.stage === 'env_setup' || Boolean(wd?.agnosticvUrls?.length) || Boolean(wd?.ciUrls?.length);
  const hasDevTab = STAGES_WITH_DEVELOPMENT_TAB.includes(summary.stage);
  const canPreIntakeReview = summary.stage === 'pre_intake_review' && (isContentReviewer || isInfraReviewer || isAdmin);
  const canReview = (summary.stage === 'content_review' && (isContentReviewer || isAdmin))
    || (summary.stage === 'infra_review' && (isInfraReviewer || isAdmin));
  const canStaging = summary.stage === 'env_setup' && (isContentDeveloper || isAdmin);
  const canEditModules = summary.stage === 'development' && (isContentDeveloper || isAdmin);
  const testingStages: WorkflowStage[] = ['testing', 'published'];
  const hasTestingTab = testingStages.includes(summary.stage);
  const canPostTestingComment = isOperations && summary.stage === 'testing';
  const canCompleteTesting = isOperations || isAdmin;
  const stagingTabIndex = hasReviewTab ? 2 : 1;
  const devTabIndex = 1 + (hasReviewTab ? 1 : 0) + (hasStagingTab ? 1 : 0);
  const testingTabIndex = 1 + (hasReviewTab ? 1 : 0) + (hasStagingTab ? 1 : 0) + (hasDevTab ? 1 : 0);
  const timelineTabIndex = 1 + (hasReviewTab ? 1 : 0) + (hasStagingTab ? 1 : 0) + (hasDevTab ? 1 : 0) + (hasTestingTab ? 1 : 0);
  const notesTabIndex = 1 + (hasReviewTab ? 1 : 0) + (hasStagingTab ? 1 : 0) + (hasDevTab ? 1 : 0) + (hasTestingTab ? 1 : 0) + 1;

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
            preIntakeUpdateSkipped={!wd?.preIntakeSentBack}
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
          <Tab label="Intake" />
          {hasReviewTab && <Tab label="Review" />}
          {hasStagingTab && <Tab label="Env Setup" />}
          {hasDevTab && <Tab label="Development" />}
          {hasTestingTab && <Tab label="Testing" />}
          <Tab label="Timeline" />
          <Tab label="Notes" />
        </Tabs>

        {/* Unified Intake Tab - Same fields for all stages */}
        {activeTab === 0 && (
          <>
            {/* RHDP Published Content */}
            {wd?.deploymentMode === 'rhdp-published' && (
              <InfoCard title="Pre-Intake Request">
                <Grid container spacing={2}>
                <Grid item xs={12} md={6}>
                  <DetailField label="Project ID" value={summary.projectId} />
                </Grid>
                <Grid item xs={12} md={6}>
                  <DetailField label="Owner" value={summary.owner} />
                </Grid>
                <Grid item xs={12} md={6}>
                  <DetailField label="SSO User" value={summary.ssoUser} />
                </Grid>
                <Grid item xs={12} md={6}>
                  <DetailField label="Deployment Mode" value={summary.deploymentMode} />
                </Grid>
                <Grid item xs={12} md={6}>
                  <DetailField label="Intake Type" value={summary.intakeType === 'migration' ? 'Migration' : 'New'} />
                </Grid>
                <Grid item xs={12} md={6}>
                  <DetailField label="Current Stage" value={stageLabel} />
                </Grid>
                <Grid item xs={12}>
                  {summary.stage === 'pre_intake_review' ? (
                    <>
                      <Typography className={classes.label}>Asset Title *</Typography>
                      <TextField
                        fullWidth
                        variant="outlined"
                        size="small"
                        value={preIntakeReviewFields.assetTitle || ''}
                        onChange={(e) => setPreIntakeReviewFields({ ...preIntakeReviewFields, assetTitle: e.target.value })}
                      />
                    </>
                  ) : (
                    <DetailField label="Asset Title" value={wd?.assetTitle || '—'} />
                  )}
                </Grid>
                <Grid item xs={12}>
                  <Typography className={classes.label}>Description *</Typography>
                  {summary.stage === 'pre_intake_review' ? (
                    <TextField
                      fullWidth
                      multiline
                      rows={3}
                      variant="outlined"
                      value={preIntakeReviewFields.projectDescription || ''}
                      onChange={(e) => setPreIntakeReviewFields({ ...preIntakeReviewFields, projectDescription: e.target.value })}
                    />
                  ) : (
                    <Typography className={classes.value} style={{ whiteSpace: 'pre-wrap' }}>{wd?.projectDescription || '—'}</Typography>
                  )}
                </Grid>
                <Grid item xs={12}>
                  <Typography className={classes.label}>Content Outline *</Typography>
                  {summary.stage === 'pre_intake_review' ? (
                    <TextField
                      fullWidth
                      multiline
                      rows={4}
                      variant="outlined"
                      value={preIntakeReviewFields.contentOutline || ''}
                      onChange={(e) => setPreIntakeReviewFields({ ...preIntakeReviewFields, contentOutline: e.target.value })}
                    />
                  ) : (
                    <Typography className={classes.value} style={{ whiteSpace: 'pre-wrap' }}>{wd?.contentOutline || '—'}</Typography>
                  )}
                </Grid>
                <Grid item xs={12}>
                  <Typography className={classes.label}>Learning Objectives *</Typography>
                  {summary.stage === 'pre_intake_review' ? (
                    <TextField
                      fullWidth
                      multiline
                      rows={3}
                      variant="outlined"
                      value={preIntakeReviewFields.learningObjectives || ''}
                      onChange={(e) => setPreIntakeReviewFields({ ...preIntakeReviewFields, learningObjectives: e.target.value })}
                    />
                  ) : (
                    <Typography className={classes.value} style={{ whiteSpace: 'pre-wrap' }}>{wd?.learningObjectives || '—'}</Typography>
                  )}
                </Grid>
                <Grid item xs={12} md={6}>
                  {summary.stage === 'pre_intake_review' ? (
                    <>
                      <Typography className={classes.label}>Content Type *</Typography>
                      <FormControl fullWidth variant="outlined" size="small">
                        <Select
                          value={preIntakeReviewFields.contentType || wd?.contentType || 'lab'}
                          onChange={(e) => setPreIntakeReviewFields({ ...preIntakeReviewFields, contentType: e.target.value as string })}
                        >
                          <MenuItem value="lab">Lab</MenuItem>
                          <MenuItem value="demo">Demo</MenuItem>
                        </Select>
                      </FormControl>
                    </>
                  ) : (
                    <DetailField label="Content Type" value={wd?.contentType || '—'} />
                  )}
                </Grid>
                <Grid item xs={12} md={6}>
                  {summary.stage === 'pre_intake_review' ? (
                    <>
                      <Typography className={classes.label}>Showroom Type *</Typography>
                      <FormControl fullWidth variant="outlined" size="small">
                        <Select
                          value={preIntakeReviewFields.showroomType || wd?.showroomType || ''}
                          onChange={(e) => setPreIntakeReviewFields({ ...preIntakeReviewFields, showroomType: e.target.value as string })}
                          displayEmpty
                        >
                          <MenuItem value="" disabled>Select showroom type</MenuItem>
                          <MenuItem value="classic">Classic</MenuItem>
                          <MenuItem value="zero_touch">Zero Touch</MenuItem>
                        </Select>
                      </FormControl>
                    </>
                  ) : (
                    <DetailField label="Showroom Type" value={wd?.showroomType === 'zero_touch' ? 'Zero Touch' : (wd?.showroomType === 'classic' ? 'Classic' : '—')} />
                  )}
                </Grid>
                <Grid item xs={12} md={6}>
                  {summary.stage === 'pre_intake_review' ? (
                    <>
                      <Typography className={classes.label}>Cloud Provider</Typography>
                      <FormControl fullWidth variant="outlined" size="small">
                        <Select
                          value={preIntakeReviewFields.cloudProvider || wd?.cloudProvider || 'cnv'}
                          onChange={(e) => setPreIntakeReviewFields({ ...preIntakeReviewFields, cloudProvider: e.target.value as string })}
                        >
                          <MenuItem value="cnv">CNV</MenuItem>
                          <MenuItem value="aws">AWS</MenuItem>
                          <MenuItem value="rosa">ROSA</MenuItem>
                          <MenuItem value="aro">ARO</MenuItem>
                        </Select>
                      </FormControl>
                    </>
                  ) : (
                    <DetailField label="Cloud Provider" value={wd?.cloudProvider || '—'} />
                  )}
                </Grid>
                <Grid item xs={12} md={6}>
                  {summary.stage === 'pre_intake_review' ? (
                    <>
                      <Typography className={classes.label}>Cluster Type</Typography>
                      <FormControl fullWidth variant="outlined" size="small">
                        <Select
                          value={preIntakeReviewFields.clusterType || wd?.clusterType || 'sno'}
                          onChange={(e) => setPreIntakeReviewFields({ ...preIntakeReviewFields, clusterType: e.target.value as string })}
                        >
                          <MenuItem value="sno">SNO</MenuItem>
                          <MenuItem value="multinode">Multinode</MenuItem>
                        </Select>
                      </FormControl>
                    </>
                  ) : (
                    <DetailField label="Cluster Type" value={wd?.clusterType || '—'} />
                  )}
                </Grid>
                <Grid item xs={12} md={6}>
                  {summary.stage === 'pre_intake_review' ? (
                    <>
                      <Typography className={classes.label}>OCP Version</Typography>
                      <FormControl fullWidth variant="outlined" size="small">
                        <Select
                          value={preIntakeReviewFields.ocpVersion || wd?.ocpVersion || '4.21'}
                          onChange={(e) => setPreIntakeReviewFields({ ...preIntakeReviewFields, ocpVersion: e.target.value as string })}
                        >
                          <MenuItem value="4.20">4.20</MenuItem>
                          <MenuItem value="4.21">4.21</MenuItem>
                          <MenuItem value="4.22">4.22</MenuItem>
                        </Select>
                      </FormControl>
                    </>
                  ) : (
                    <DetailField label="OCP Version" value={wd?.ocpVersion || '—'} />
                  )}
                </Grid>
                <Grid item xs={12} md={6}>
                  {summary.stage === 'pre_intake_review' ? (
                    <>
                      <Typography className={classes.label}>Initiative</Typography>
                      <FormControl fullWidth variant="outlined" size="small">
                        <Select
                          value={preIntakeReviewFields.initiativeKey || wd?.initiativeKey || 'rhdp_catalog'}
                          onChange={(e) => setPreIntakeReviewFields({ ...preIntakeReviewFields, initiativeKey: e.target.value as string })}
                        >
                          <MenuItem value="rhdp_catalog">RHDP Catalog</MenuItem>
                          <MenuItem value="rh1_2027">RH1 2027</MenuItem>
                          <MenuItem value="summit_2027">Summit 2027</MenuItem>
                        </Select>
                      </FormControl>
                    </>
                  ) : (
                    <DetailField label="Initiative" value={wd?.initiativeKey || '—'} />
                  )}
                </Grid>
                <Grid item xs={12}>
                  <Grid container spacing={2}>
                    <Grid item xs={12} md={3}>
                      {summary.stage === 'pre_intake_review' ? (
                        <FormControlLabel
                          control={
                            <Checkbox
                              checked={preIntakeReviewFields.aiRelated !== undefined ? Boolean(preIntakeReviewFields.aiRelated) : (wd?.aiRelated !== undefined ? Boolean(wd.aiRelated) : false)}
                              onChange={(e) => setPreIntakeReviewFields({
                                ...preIntakeReviewFields,
                                aiRelated: e.target.checked,
                                canUseMaas: e.target.checked ? (preIntakeReviewFields.canUseMaas !== undefined ? preIntakeReviewFields.canUseMaas : true) : false,
                                maasModels: e.target.checked ? preIntakeReviewFields.maasModels : '',
                                gpuJustification: e.target.checked ? preIntakeReviewFields.gpuJustification : ''
                              })}
                            />
                          }
                          label="AI Related"
                        />
                      ) : (
                        Boolean(wd?.aiRelated) && <DetailField label="AI Related" value="Yes" />
                      )}
                    </Grid>
                    {(preIntakeReviewFields.aiRelated !== undefined ? Boolean(preIntakeReviewFields.aiRelated) : Boolean(wd?.aiRelated)) && (
                      <>
                        <Grid item xs={12} md={3}>
                          {summary.stage === 'pre_intake_review' ? (
                            <FormControlLabel
                              control={
                                <Checkbox
                                  checked={preIntakeReviewFields.canUseMaas !== undefined ? Boolean(preIntakeReviewFields.canUseMaas) : (wd?.canUseMaas !== undefined ? Boolean(wd.canUseMaas) : true)}
                                  onChange={(e) => setPreIntakeReviewFields({
                                    ...preIntakeReviewFields,
                                    canUseMaas: e.target.checked,
                                    maasModels: e.target.checked ? preIntakeReviewFields.maasModels : '',
                                    gpuJustification: !e.target.checked ? preIntakeReviewFields.gpuJustification : ''
                                  })}
                                />
                              }
                              label="Can Use MaaS"
                            />
                          ) : (
                            (wd?.canUseMaas !== undefined ? Boolean(wd.canUseMaas) : true) && <DetailField label="Can Use MaaS" value="Yes" />
                          )}
                        </Grid>
                        {(preIntakeReviewFields.canUseMaas !== undefined ? Boolean(preIntakeReviewFields.canUseMaas) : (wd?.canUseMaas !== undefined ? Boolean(wd.canUseMaas) : true)) ? (
                          <Grid item xs={12} md={6}>
                            {summary.stage === 'pre_intake_review' ? (
                              <TextField
                                fullWidth
                                label="MaaS Models Needed"
                                placeholder="e.g., gpt-4o, claude-3-5-sonnet"
                                value={preIntakeReviewFields.maasModels ?? wd?.maasModels ?? ''}
                                onChange={(e) => setPreIntakeReviewFields({ ...preIntakeReviewFields, maasModels: e.target.value })}
                                size="small"
                                multiline
                                rows={2}
                              />
                            ) : (
                              wd?.maasModels && <DetailField label="MaaS Models" value={wd.maasModels} />
                            )}
                          </Grid>
                        ) : (
                          <Grid item xs={12} md={6}>
                            {summary.stage === 'pre_intake_review' ? (
                              <TextField
                                fullWidth
                                label="GPU Justification"
                                placeholder="Explain why MaaS cannot meet your needs and specify GPU requirements"
                                value={preIntakeReviewFields.gpuJustification ?? wd?.gpuJustification ?? ''}
                                onChange={(e) => setPreIntakeReviewFields({ ...preIntakeReviewFields, gpuJustification: e.target.value })}
                                size="small"
                                multiline
                                rows={2}
                              />
                            ) : (
                              wd?.gpuJustification && <DetailField label="GPU Justification" value={wd.gpuJustification} />
                            )}
                          </Grid>
                        )}
                      </>
                    )}
                    <Grid item xs={12} md={3}>
                      {summary.stage === 'pre_intake_review' ? (
                        <FormControlLabel
                          control={
                            <Checkbox
                              checked={preIntakeReviewFields.partnersAccess ?? wd?.partnersAccess ?? false}
                              onChange={(e) => setPreIntakeReviewFields({ ...preIntakeReviewFields, partnersAccess: e.target.checked })}
                            />
                          }
                          label="Partners Access"
                        />
                      ) : (
                        wd?.partnersAccess && <DetailField label="Partners Access" value="Yes" />
                      )}
                    </Grid>
                  </Grid>
                </Grid>
                <Grid item xs={12}>
                  <Typography className={classes.label}>Associated Opportunities</Typography>
                  {summary.stage === 'pre_intake_review' ? (
                    <TextField
                      fullWidth
                      multiline
                      rows={2}
                      variant="outlined"
                      value={preIntakeReviewFields.associatedOpportunities || ''}
                      onChange={(e) => setPreIntakeReviewFields({ ...preIntakeReviewFields, associatedOpportunities: e.target.value })}
                    />
                  ) : (
                    <Typography className={classes.value} style={{ whiteSpace: 'pre-wrap' }}>{wd?.associatedOpportunities || '—'}</Typography>
                  )}
                </Grid>
                <Grid item xs={12}>
                  <Typography className={classes.label}>Sales Play / TDP</Typography>
                  {summary.stage === 'pre_intake_review' ? (
                    <TextField
                      fullWidth
                      multiline
                      rows={2}
                      variant="outlined"
                      value={preIntakeReviewFields.salesPlayTdp || ''}
                      onChange={(e) => setPreIntakeReviewFields({ ...preIntakeReviewFields, salesPlayTdp: e.target.value })}
                    />
                  ) : (
                    <Typography className={classes.value} style={{ whiteSpace: 'pre-wrap' }}>{wd?.salesPlayTdp || '—'}</Typography>
                  )}
                </Grid>
                <Grid item xs={4}>
                  <DetailField label="Initiative" value={wd?.initiativeKey || '—'} />
                </Grid>
                <Grid item xs={12}>
                  <Typography className={classes.label}>Tags</Typography>
                  <TagEditor
                    initialTags={summary.tags}
                    canEdit={isContentDeveloper || isContentReviewer || isAdmin}
                    onSave={async (tags) => {
                      await client.updateTags(summary.id, tags);
                      setRefreshKey(k => k + 1);
                    }}
                  />
                </Grid>
              </Grid>
            </InfoCard>
            )}

            {/* Field Source Content - Placeholder */}
            {wd?.deploymentMode === 'field-source' && (
              <InfoCard title={summary.stage === 'pre_intake_review' ? 'Update Field Source Request' : 'Field Source Request'}>
                <Grid container spacing={2}>
                  <Grid item xs={12} md={6}>
                    <DetailField label="Project ID" value={summary.projectId} />
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <DetailField label="Owner" value={summary.owner} />
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <DetailField label="SSO User" value={summary.ssoUser} />
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <DetailField label="Deployment Mode" value={summary.deploymentMode} />
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <DetailField label="Intake Type" value={summary.intakeType === 'migration' ? 'Migration' : 'New'} />
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <DetailField label="Current Stage" value={stageLabel} />
                  </Grid>
                  <Grid item xs={12}>
                    <Typography variant="body2" color="textSecondary">
                      Field source pre-intake review fields will be implemented here.
                    </Typography>
                  </Grid>
                  <Grid item xs={12}>
                    <Typography className={classes.label}>Asset Title</Typography>
                    {summary.stage === 'pre_intake_review' ? (
                      <TextField
                        fullWidth
                        variant="outlined"
                        size="small"
                        value={preIntakeReviewFields.assetTitle || ''}
                        onChange={(e) => setPreIntakeReviewFields({ ...preIntakeReviewFields, assetTitle: e.target.value })}
                      />
                    ) : (
                      <DetailField label="" value={wd?.assetTitle || '—'} />
                    )}
                  </Grid>
                  <Grid item xs={12}>
                    <Typography className={classes.label}>Description</Typography>
                    {summary.stage === 'pre_intake_review' ? (
                      <TextField
                        fullWidth
                        multiline
                        rows={3}
                        variant="outlined"
                        value={preIntakeReviewFields.projectDescription || ''}
                        onChange={(e) => setPreIntakeReviewFields({ ...preIntakeReviewFields, projectDescription: e.target.value })}
                      />
                    ) : (
                      <Typography className={classes.value} style={{ whiteSpace: 'pre-wrap' }}>{wd?.projectDescription || '—'}</Typography>
                    )}
                  </Grid>
                  <Grid item xs={12}>
                    <Typography className={classes.label}>Tags</Typography>
                    <TagEditor
                      initialTags={summary.tags}
                      canEdit={isContentDeveloper || isContentReviewer || isAdmin}
                      onSave={async (tags) => {
                        await client.updateTags(summary.id, tags);
                        setRefreshKey(k => k + 1);
                      }}
                    />
                  </Grid>
                </Grid>
              </InfoCard>
            )}

            {/* Action Buttons */}
            <InfoCard>
              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                {/* Review action buttons for pre_intake_review */}
                {canPreIntakeReview && (
                  <>
                    <Button
                      variant="contained"
                      style={{ backgroundColor: '#4caf50', color: '#fff', fontWeight: 600 }}
                      size="large"
                      startIcon={
                        preIntakeReviewAction === 'approved' ? (
                          <CircularProgress size={16} color="inherit" />
                        ) : undefined
                      }
                      onClick={() => {
                        setApprovalNotes([]);
                        setApprovalNotesDialogOpen(true);
                      }}
                      disabled={preIntakeReviewAction !== null}
                    >
                      {preIntakeReviewAction === 'approved' ? 'Approving...' : 'Approve'}
                    </Button>
                    <Button
                      variant="contained"
                      style={{ backgroundColor: '#ffc107', color: '#000', fontWeight: 600 }}
                      size="large"
                      startIcon={
                        preIntakeReviewAction === 'cancelled' ? (
                          <CircularProgress size={16} color="inherit" />
                        ) : undefined
                      }
                      onClick={() => setCancelConfirmDialogOpen(true)}
                      disabled={preIntakeReviewAction !== null}
                    >
                      {preIntakeReviewAction === 'cancelled' ? 'Cancelling...' : 'Cancel'}
                    </Button>
                  </>
                )}
              </div>
            </InfoCard>
          </>
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
                  {driftReport.has_drift ? 'Project drift detected' : driftReport.summary}
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
                            <th style={{ padding: '6px 8px', width: 24 }} />
                            <th style={{ padding: '6px 8px' }}>Catalog Item</th>
                            <th style={{ padding: '6px 8px' }}>Display Name</th>
                            <th style={{ padding: '6px 8px' }}>Relevance</th>
                            <th style={{ padding: '6px 8px' }}>Why It Fits</th>
                            <th style={{ padding: '6px 8px' }}>Link</th>
                          </tr>
                        </thead>
                        <tbody>
                          {validationReport.approval_checklist.content.rcars_top_matches!.map((m, i) => {
                            const hasWorkloads = (m.workloads ?? []).length > 0;
                            const isExpanded = expandedRcarsRows.has(i);
                            return (
                              <React.Fragment key={i}>
                                <tr style={{ borderBottom: hasWorkloads && isExpanded ? 'none' : '1px solid rgba(255,255,255,0.06)' }}>
                                  <td style={{ padding: '6px 4px', textAlign: 'center' }}>
                                    {hasWorkloads && (
                                      <IconButton
                                        size="small"
                                        onClick={() => {
                                          const next = new Set(expandedRcarsRows);
                                          if (next.has(i)) next.delete(i); else next.add(i);
                                          setExpandedRcarsRows(next);
                                        }}
                                        style={{ padding: 2 }}
                                      >
                                        {isExpanded ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
                                      </IconButton>
                                    )}
                                  </td>
                                  <td style={{ padding: '6px 8px', fontFamily: 'monospace' }}>{m.ci_name}</td>
                                  <td style={{ padding: '6px 8px' }}>{m.display_name || m.title || '—'}</td>
                                  <td style={{ padding: '6px 8px' }}>{m.relevance_score != null ? `${m.relevance_score}%` : '—'}</td>
                                  <td style={{ padding: '6px 8px', maxWidth: 300 }}>{m.why_it_fits || '—'}</td>
                                  <td style={{ padding: '6px 8px' }}>
                                    {m.url ? <a href={m.url} target="_blank" rel="noopener noreferrer">View</a> : '—'}
                                  </td>
                                </tr>
                                {hasWorkloads && isExpanded && (
                                  <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                                    <td colSpan={6} style={{ padding: '4px 8px 12px 40px' }}>
                                      <Typography variant="caption" style={{ fontWeight: 600, color: '#90caf9' }}>
                                        Reusable Workloads ({m.workloads!.length})
                                      </Typography>
                                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem', marginTop: 4 }}>
                                        <thead>
                                          <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)', textAlign: 'left' }}>
                                            <th style={{ padding: '4px 8px' }}>Role</th>
                                            <th style={{ padding: '4px 8px' }}>Collection</th>
                                          </tr>
                                        </thead>
                                        <tbody>
                                          {m.workloads!.map((w, wi) => (
                                            <tr key={wi} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                                              <td style={{ padding: '3px 8px', fontFamily: 'monospace' }}>{w.role}</td>
                                              <td style={{ padding: '3px 8px', fontFamily: 'monospace' }}>{w.collection}</td>
                                            </tr>
                                          ))}
                                        </tbody>
                                      </table>
                                    </td>
                                  </tr>
                                )}
                              </React.Fragment>
                            );
                          })}
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
                    onClick={() => {
                      setApprovalNotes([]);
                      setApprovalNotesDialogOpen(true);
                    }}
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

        {hasDevTab && activeTab === devTabIndex && (
          <InfoCard title="Development Progress">
            <Typography variant="body2" style={{ marginBottom: 16, color: '#757575' }}>
              Track the development status. Make your changes, then click Update to commit to the repository.
            </Typography>

            {/* Automation Section */}
            <div style={{ marginBottom: 32 }}>
              <Typography variant="h6" style={{ marginBottom: 12, fontSize: '1rem', fontWeight: 600 }}>
                Automation
              </Typography>
              <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                <Typography variant="body2" style={{ minWidth: 100 }}>Status:</Typography>
                <FormControl variant="outlined" size="small" style={{ minWidth: 150 }} disabled={!canEditModules}>
                  <Select
                    value={automationStatus}
                    onChange={(e) => handleAutomationStatusChange(e.target.value as string)}
                  >
                    <MenuItem value="not_started">Not Started</MenuItem>
                    <MenuItem value="in_progress">In Progress</MenuItem>
                    <MenuItem value="complete">Complete</MenuItem>
                  </Select>
                </FormControl>
              </div>
            </div>

            {/* Modules Section */}
            <Typography variant="h6" style={{ marginBottom: 12, fontSize: '1rem', fontWeight: 600 }}>
              Modules
            </Typography>
            {(() => {
              if (modules.length === 0) {
                return (
                  <Typography variant="body2" style={{ color: '#757575', fontStyle: 'italic' }}>
                    No modules defined in spec.yaml yet.
                  </Typography>
                );
              }

              return (
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid rgba(255,255,255,0.12)', textAlign: 'left' }}>
                      <th style={{ padding: '8px 12px' }}>Module ID</th>
                      <th style={{ padding: '8px 12px' }}>Title</th>
                      <th style={{ padding: '8px 12px' }}>Duration (min)</th>
                      <th style={{ padding: '8px 12px' }}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {modules.map((module: any, i: number) => {
                      const currentStatus = moduleStatuses[module.id] || module.status || 'not_started';

                      return (
                        <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                          <td style={{ padding: '8px 12px', fontFamily: 'monospace' }}>{module.id}</td>
                          <td style={{ padding: '8px 12px' }}>{module.title || '—'}</td>
                          <td style={{ padding: '8px 12px' }}>{module.duration_min || '—'}</td>
                          <td style={{ padding: '8px 12px' }}>
                            <FormControl variant="outlined" size="small" fullWidth disabled={!canEditModules}>
                              <Select
                                value={currentStatus}
                                onChange={(e) => handleModuleStatusChange(module.id, e.target.value as string)}
                                style={{ minWidth: 150 }}
                              >
                                <MenuItem value="not_started">Not Started</MenuItem>
                                <MenuItem value="in_progress">In Progress</MenuItem>
                                <MenuItem value="complete">Complete</MenuItem>
                              </Select>
                            </FormControl>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              );
            })()}

            {/* Update Button */}
            {canEditModules && (
              <div style={{ marginTop: 24, display: 'flex', alignItems: 'center', gap: 16 }}>
                <Button
                  variant="contained"
                  color="primary"
                  onClick={handleUpdateAllStatuses}
                  disabled={!hasStatusChanges() || updatingStatuses}
                  startIcon={updatingStatuses ? <CircularProgress size={16} color="inherit" /> : undefined}
                >
                  {updatingStatuses ? 'Updating...' : 'Update'}
                </Button>
                {hasStatusChanges() && (
                  <Typography variant="caption" style={{ color: '#757575' }}>
                    You have unsaved changes
                  </Typography>
                )}
              </div>
            )}
          </InfoCard>
        )}

        {hasTestingTab && activeTab === testingTabIndex && (
          <InfoCard title="Testing Notes">
            {canPostTestingComment && (
              <div style={{ marginBottom: 24 }}>
                <TextField
                  label="Add a note"
                  placeholder="Enter your testing feedback..."
                  fullWidth
                  multiline
                  minRows={3}
                  variant="outlined"
                  value={testingNoteText}
                  onChange={e => setTestingNoteText(e.target.value)}
                  disabled={submittingTestingNote}
                  style={{ marginBottom: 8 }}
                />
                <div style={{ display: 'flex', gap: 8 }}>
                  <Button
                    variant="contained"
                    color="primary"
                    size="small"
                    style={{ fontWeight: 600 }}
                    onClick={handlePostTestingNote}
                    disabled={submittingTestingNote || !testingNoteText.trim()}
                    startIcon={submittingTestingNote ? <CircularProgress size={16} color="inherit" /> : undefined}
                  >
                    {submittingTestingNote ? 'Adding...' : 'Add Note'}
                  </Button>
                </div>
              </div>
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

        {activeTab === notesTabIndex && (
          <InfoCard title="Notes">
            <div style={{ marginBottom: 24 }}>
              <TextField
                label="Add a note"
                placeholder="Enter your note..."
                fullWidth
                multiline
                minRows={3}
                variant="outlined"
                value={addNoteText}
                onChange={e => setAddNoteText(e.target.value)}
                disabled={submittingNote}
                style={{ marginBottom: 8 }}
              />
              <div style={{ display: 'flex', gap: 8 }}>
                <Button
                  variant="contained"
                  color="primary"
                  size="small"
                  style={{ fontWeight: 600 }}
                  onClick={async () => {
                    if (!addNoteText.trim()) return;
                    setSubmittingNote(true);
                    try {
                      await client.addNote(result.summary.id, addNoteText.trim());
                      setAddNoteText('');
                      setSnackbar({ open: true, severity: 'success', message: 'Note added successfully' });
                      setRefreshKey(k => k + 1);
                    } catch (err: any) {
                      setSnackbar({ open: true, severity: 'error', message: `Failed to add note: ${err.message}` });
                    } finally {
                      setSubmittingNote(false);
                    }
                  }}
                  disabled={submittingNote || !addNoteText.trim()}
                  startIcon={submittingNote ? <CircularProgress size={16} color="inherit" /> : undefined}
                >
                  {submittingNote ? 'Adding...' : 'Add Note'}
                </Button>
              </div>
            </div>
            {(() => {
              const notes = (wd?.notes ?? []) as Array<{ user: string; text: string; type: 'rejection' | 'info'; timestamp: string; stage: string }>;
              if (notes.length === 0) {
                return (
                  <Typography variant="body2" style={{ color: '#757575', fontStyle: 'italic' }}>
                    No notes have been added yet.
                  </Typography>
                );
              }
              return (
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid rgba(255,255,255,0.12)', textAlign: 'left' }}>
                      <th style={{ padding: '6px 8px', width: 40 }}>Type</th>
                      <th style={{ padding: '6px 8px' }}>User</th>
                      <th style={{ padding: '6px 8px' }}>Note</th>
                      <th style={{ padding: '6px 8px' }}>Stage</th>
                      <th style={{ padding: '6px 8px' }}>When</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...notes].reverse().map((note, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                        <td style={{ padding: '6px 8px', textAlign: 'center' }}>
                          {note.type === 'rejection' ? (
                            <ErrorIcon style={{ fontSize: 20, color: '#f44336', verticalAlign: 'middle' }} />
                          ) : (
                            <InfoOutlinedIcon style={{ fontSize: 20, color: '#2196f3', verticalAlign: 'middle' }} />
                          )}
                        </td>
                        <td style={{ padding: '6px 8px' }}>{note.user || '—'}</td>
                        <td style={{ padding: '6px 8px' }}>{note.text}</td>
                        <td style={{ padding: '6px 8px' }}>{STAGE_LABELS[note.stage as WorkflowStage] || note.stage}</td>
                        <td style={{ padding: '6px 8px' }}>
                          {(() => {
                            if (!note.timestamp) return '—';
                            const n = Number(note.timestamp);
                            if (!isNaN(n) && n > 1_000_000_000 && n < 10_000_000_000_000) {
                              return new Date(n < 10_000_000_000 ? n * 1000 : n).toLocaleString();
                            }
                            return new Date(note.timestamp).toLocaleString();
                          })()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              );
            })()}
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
          reviewerName={currentUserEmail}
          submitting={submittingRejection}
          onConfirm={handleRejectionConfirm}
          onCancel={handleRejectionCancel}
        />

        <Dialog open={approvalNotesDialogOpen} onClose={() => setApprovalNotesDialogOpen(false)} maxWidth="sm" fullWidth>
          <DialogTitle>Approve with Notes</DialogTitle>
          <DialogContent>
            <Typography variant="body2" color="textSecondary" gutterBottom style={{ marginBottom: 16 }}>
              Add notes about your approval (optional). These will be visible in the Notes tab.
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
              onClick={() => {
                setApprovalNotesDialogOpen(false);
                if (summary.stage === 'pre_intake_review') {
                  handlePreIntakeReviewAction('approved');
                } else {
                  handleApprove(summary.stage);
                }
              }}
              disabled={approvingStage !== null || preIntakeReviewAction !== null}
            >
              Submit
            </Button>
          </DialogActions>
        </Dialog>

        <Dialog open={cancelConfirmDialogOpen} onClose={() => setCancelConfirmDialogOpen(false)} maxWidth="sm" fullWidth>
          <DialogTitle>Confirm Cancellation</DialogTitle>
          <DialogContent>
            <Alert severity="warning" style={{ marginBottom: 16 }}>
              <Typography variant="body2">
                <strong>Warning:</strong> This is a destructive action.
              </Typography>
            </Alert>
            <Typography variant="body2">
              Cancelling this pre-intake review request will permanently delete the workflow and all associated artifacts. This action cannot be undone.
            </Typography>
            <Typography variant="body2" style={{ marginTop: 16 }}>
              Are you sure you want to proceed?
            </Typography>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setCancelConfirmDialogOpen(false)}>
              No, Go Back
            </Button>
            <Button
              variant="contained"
              style={{ backgroundColor: '#f44336', color: '#fff', fontWeight: 600 }}
              onClick={() => {
                setCancelConfirmDialogOpen(false);
                handlePreIntakeReviewAction('cancelled');
              }}
              disabled={preIntakeReviewAction !== null}
            >
              Yes, Cancel Pre-Intake
            </Button>
          </DialogActions>
        </Dialog>

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
