import React from 'react';
import {
  makeStyles,
  Button,
  CircularProgress,
  Typography,
} from '@material-ui/core';
import CheckCircleIcon from '@material-ui/icons/CheckCircle';
import RadioButtonUncheckedIcon from '@material-ui/icons/RadioButtonUnchecked';
import FiberManualRecordIcon from '@material-ui/icons/FiberManualRecord';
import ErrorIcon from '@material-ui/icons/Error';
import { WorkflowStage } from '../../api/types';
import { STAGE_ORDER, STAGE_LABELS, stageIndex } from '../../utils/stageMapping';

const APPROVE_STAGES: WorkflowStage[] = ['content_review', 'infra_review'];

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
          return (
            <React.Fragment key={s}>
              <div className={classes.node}>
                <NodeIcon state={st} />
                <Typography className={classes.nodeLabel}>{STAGE_LABELS[s]}</Typography>
              </div>
              {i < STAGE_ORDER.length - 1 && <div className={lineCls(st)} />}
            </React.Fragment>
          );
        })}
      </div>

      {APPROVE_STAGES.includes(stage) && onApprove && (
        <div style={{ marginTop: 24, paddingBottom: 8, display: 'flex', gap: 12 }}>
          <Button
            variant="contained"
            style={{ backgroundColor: '#4caf50', color: '#fff', fontWeight: 600 }}
            size="large"
            startIcon={
              approvingStage === stage ? (
                <CircularProgress size={16} color="inherit" />
              ) : undefined
            }
            onClick={() => onApprove(stage)}
            disabled={approvingStage !== null}
          >
            {approvingStage === stage ? 'Approving...' : 'Approve'}
          </Button>
          <Button
            variant="contained"
            style={{ backgroundColor: '#e57373', color: '#fff', fontWeight: 600 }}
            size="large"
            disabled={approvingStage !== null}
          >
            Reject
          </Button>
        </div>
      )}
    </div>
  );
}
