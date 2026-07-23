import React from 'react';
import {
  makeStyles,
  Typography,
} from '@material-ui/core';
import CheckCircleIcon from '@material-ui/icons/CheckCircle';
import RadioButtonUncheckedIcon from '@material-ui/icons/RadioButtonUnchecked';
import FiberManualRecordIcon from '@material-ui/icons/FiberManualRecord';
import ErrorIcon from '@material-ui/icons/Error';
import RemoveCircleOutlineIcon from '@material-ui/icons/RemoveCircleOutline';
import { WorkflowStage } from '../../api/types';
import { STAGE_ORDER, STAGE_LABELS, stageIndex } from '../../utils/stageMapping';

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
    position: 'relative' as const,
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
  completed: { color: '#4caf50' },
  active: { color: '#4caf50' },
  error: { color: '#f44336' },
  skipped: { color: theme.palette.text.disabled },
  iconLarge: { fontSize: '1.3rem' },
}));

type NodeState = 'completed' | 'active' | 'pending' | 'error' | 'skipped';

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
    case 'skipped':
      return <RemoveCircleOutlineIcon className={`${classes.skipped} ${cls}`} />;
    default:
      return <RadioButtonUncheckedIcon className={cls} />;
  }
}

function getNodeState(
  s: WorkflowStage,
  currentStage: WorkflowStage,
  driftSkipped?: boolean,
): NodeState {
  if (currentStage === 'error') return 'error';
  if (currentStage === 'published') {
    if (s === 'drift_review' && driftSkipped) return 'skipped';
    return 'completed';
  }
  const cur = stageIndex(currentStage);
  const idx = stageIndex(s);
  if (idx < cur) {
    if (s === 'drift_review' && driftSkipped) return 'skipped';
    return 'completed';
  }
  if (idx === cur) return 'active';
  return 'pending';
}

interface WorkflowProgressProps {
  stage: WorkflowStage;
  rejectedFrom?: WorkflowStage | null;
  hasDrift?: boolean;
}

export function WorkflowProgress({ stage, hasDrift }: WorkflowProgressProps) {
  const classes = useStyles();
  const pastDrift = stageIndex(stage) > stageIndex('drift_review');
  const driftSkipped = pastDrift && hasDrift === false;

  const lineCls = () => classes.line;

  return (
    <div className={classes.root}>
      <div className={classes.pipeline}>
        {STAGE_ORDER.map((s, i) => {
          const st = getNodeState(s, stage, driftSkipped);
          return (
            <React.Fragment key={s}>
              <div className={classes.node}>
                <NodeIcon state={st} />
                <Typography className={classes.nodeLabel}>{STAGE_LABELS[s]}</Typography>
              </div>
              {i < STAGE_ORDER.length - 1 && <div className={lineCls()} />}
            </React.Fragment>
          );
        })}
      </div>

    </div>
  );
}
