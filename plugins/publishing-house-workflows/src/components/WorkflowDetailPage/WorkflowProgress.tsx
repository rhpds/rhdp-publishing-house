import React, { useState } from 'react';
import {
  makeStyles,
  Button,
  CircularProgress,
  Collapse,
  Paper,
  Typography,
} from '@material-ui/core';
import CheckCircleIcon from '@material-ui/icons/CheckCircle';
import RadioButtonUncheckedIcon from '@material-ui/icons/RadioButtonUnchecked';
import FiberManualRecordIcon from '@material-ui/icons/FiberManualRecord';
import ErrorIcon from '@material-ui/icons/Error';
import { WorkflowStage } from '../../api/types';
import { STAGE_ORDER, STAGE_LABELS, stageIndex } from '../../utils/stageMapping';

const APPROVE_STAGES: WorkflowStage[] = ['content_review', 'infra_review'];

const STAGE_DESCRIPTIONS: Record<string, string> = {
  intake: 'The project intake questionnaire is being completed to gather requirements.',
  content_review: 'Review the design spec and module outlines for completeness and accuracy.',
  infra_review: 'Review the environment and automation requirements for feasibility.',
  development: 'The project is in active development.',
  ready: 'Development is complete. The project is being prepared for publication.',
  published: 'The project has been published and is available in the catalog.',
};

const useStyles = makeStyles(theme => ({
  root: {
    padding: theme.spacing(3, 2),
    overflowX: 'auto',
  },
  pipeline: {
    display: 'flex',
    alignItems: 'center',
    minWidth: 700,
  },
  node: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    minWidth: 80,
  },
  nodeClickable: {
    cursor: 'pointer',
    '&:hover': { opacity: 0.7 },
  },
  nodeLabel: {
    marginTop: 6,
    fontSize: '0.75rem',
    textAlign: 'center' as const,
    whiteSpace: 'nowrap' as const,
  },
  line: {
    flex: 1,
    height: 2,
    minWidth: 30,
    backgroundColor: theme.palette.divider,
  },
  lineCompleted: { backgroundColor: '#4caf50' },
  lineActive: { backgroundColor: theme.palette.primary.main },
  panel: {
    padding: theme.spacing(2, 3),
    marginTop: theme.spacing(2),
    backgroundColor: theme.palette.background.default,
    border: `1px solid ${theme.palette.divider}`,
  },
  panelTitle: {
    fontWeight: 600,
    marginBottom: theme.spacing(0.5),
  },
  panelDesc: {
    color: theme.palette.text.secondary,
    fontSize: '0.875rem',
    marginBottom: theme.spacing(2),
  },
  completed: { color: '#4caf50' },
  active: { color: theme.palette.primary.main },
  error: { color: '#f44336' },
  iconLarge: { fontSize: '1.3rem' },
}));

type NodeState = 'completed' | 'active' | 'pending' | 'error';

function NodeIcon({ state }: { state: NodeState }) {
  const classes = useStyles();
  const cls = classes.iconLarge;
  switch (state) {
    case 'completed':
      return <CheckCircleIcon className={`${classes.completed} ${cls}`} />;
    case 'active':
      return <FiberManualRecordIcon className={`${classes.active} ${cls}`} />;
    case 'error':
      return <ErrorIcon className={`${classes.error} ${cls}`} />;
    default:
      return <RadioButtonUncheckedIcon className={cls} />;
  }
}

function getNodeState(s: WorkflowStage, currentStage: WorkflowStage): NodeState {
  if (currentStage === 'error') return 'error';
  if (currentStage === 'published') return 'completed';
  const cur = stageIndex(currentStage);
  const idx = stageIndex(s);
  if (idx < cur) return 'completed';
  if (idx === cur) return 'active';
  return 'pending';
}

interface WorkflowProgressProps {
  stage: WorkflowStage;
  approvingStage?: string | null;
  onApprove?: (stage: WorkflowStage) => void;
}

export function WorkflowProgress({ stage, approvingStage, onApprove }: WorkflowProgressProps) {
  const classes = useStyles();
  const [selectedStep, setSelectedStep] = useState<WorkflowStage | null>(null);

  const handleClick = (s: WorkflowStage) => {
    if (getNodeState(s, stage) !== 'active') return;
    setSelectedStep(prev => (prev === s ? null : s));
  };

  const lineCls = (state: NodeState) => {
    if (state === 'completed') return `${classes.line} ${classes.lineCompleted}`;
    if (state === 'active') return `${classes.line} ${classes.lineActive}`;
    return classes.line;
  };

  return (
    <div className={classes.root}>
      <div className={classes.pipeline}>
        {STAGE_ORDER.map((s, i) => {
          const st = getNodeState(s, stage);
          const isActive = st === 'active';
          return (
            <React.Fragment key={s}>
              <div
                className={`${classes.node} ${isActive ? classes.nodeClickable : ''}`}
                onClick={() => handleClick(s)}
              >
                <NodeIcon state={st} />
                <Typography className={classes.nodeLabel}>{STAGE_LABELS[s]}</Typography>
              </div>
              {i < STAGE_ORDER.length - 1 && <div className={lineCls(st)} />}
            </React.Fragment>
          );
        })}
      </div>

      <Collapse in={selectedStep !== null}>
        {selectedStep && (
          <Paper className={classes.panel} elevation={0}>
            <Typography className={classes.panelTitle}>
              {STAGE_LABELS[selectedStep]}
            </Typography>
            <Typography className={classes.panelDesc}>
              {STAGE_DESCRIPTIONS[selectedStep] || ''}
            </Typography>
            {APPROVE_STAGES.includes(selectedStep) &&
              getNodeState(selectedStep, stage) === 'active' &&
              onApprove && (
              <Button
                variant="contained"
                color="primary"
                size="small"
                startIcon={
                  approvingStage === selectedStep ? (
                    <CircularProgress size={16} color="inherit" />
                  ) : undefined
                }
                onClick={() => onApprove(selectedStep)}
                disabled={approvingStage !== null}
              >
                {approvingStage === selectedStep
                  ? 'Approving...'
                  : 'Approve'}
              </Button>
            )}
          </Paper>
        )}
      </Collapse>
    </div>
  );
}
