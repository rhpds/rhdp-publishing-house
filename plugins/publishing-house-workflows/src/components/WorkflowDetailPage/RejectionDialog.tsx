import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Typography,
  CircularProgress,
  makeStyles,
} from '@material-ui/core';
import DeleteIcon from '@material-ui/icons/Delete';
import AddIcon from '@material-ui/icons/Add';
import { WorkflowStage, RejectionData, RejectionReason } from '../../api/types';
import { STAGE_LABELS } from '../../utils/stageMapping';

const useStyles = makeStyles(theme => ({
  reasonInput: {
    display: 'flex',
    gap: theme.spacing(1),
    alignItems: 'flex-start',
    marginBottom: theme.spacing(2),
  },
  reasonList: {
    border: `1px solid ${theme.palette.divider}`,
    borderRadius: 4,
    maxHeight: 240,
    overflow: 'auto',
    marginBottom: theme.spacing(1),
  },
  reasonNumber: {
    fontWeight: 600,
    marginRight: theme.spacing(1),
    color: theme.palette.text.secondary,
    minWidth: 24,
  },
  emptyState: {
    padding: theme.spacing(3),
    textAlign: 'center' as const,
    color: theme.palette.text.secondary,
  },
  confirmButton: {
    backgroundColor: '#e57373',
    color: '#fff',
    fontWeight: 600,
    '&:hover': { backgroundColor: '#d32f2f' },
    '&:disabled': { backgroundColor: '#ccc' },
  },
}));

function generateRejectionId(): string {
  return Math.random().toString(36).substring(2, 7);
}

interface RejectionDialogProps {
  open: boolean;
  stage: WorkflowStage;
  reviewerName: string;
  submitting: boolean;
  onConfirm: (data: RejectionData) => void;
  onCancel: () => void;
}

export function RejectionDialog({
  open,
  stage,
  reviewerName,
  submitting,
  onConfirm,
  onCancel,
}: RejectionDialogProps) {
  const classes = useStyles();
  const [reasons, setReasons] = useState<RejectionReason[]>([]);
  const [currentText, setCurrentText] = useState('');
  const [rejectionId, setRejectionId] = useState('');

  useEffect(() => {
    if (open) {
      setReasons([]);
      setCurrentText('');
      setRejectionId(generateRejectionId());
    }
  }, [open]);

  const handleAdd = () => {
    const trimmed = currentText.trim();
    if (!trimmed) return;
    setReasons(prev => [...prev, { id: prev.length + 1, text: trimmed }]);
    setCurrentText('');
  };

  const handleRemove = (id: number) => {
    setReasons(prev =>
      prev.filter(r => r.id !== id).map((r, i) => ({ ...r, id: i + 1 })),
    );
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleAdd();
    }
  };

  const handleConfirm = () => {
    onConfirm({
      rejectionId,
      reviewerName,
      reviewerStage: stage,
      timestamp: new Date().toISOString(),
      reasons,
    });
  };

  return (
    <Dialog open={open} onClose={onCancel} maxWidth="sm" fullWidth>
      <DialogTitle>
        Reject {STAGE_LABELS[stage] || stage}
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="textSecondary" gutterBottom>
          Rejection ID: <strong>{rejectionId}</strong> | Reviewer: <strong>{reviewerName}</strong>
        </Typography>

        <div className={classes.reasonInput}>
          <TextField
            label="Rejection reason"
            variant="outlined"
            size="small"
            fullWidth
            multiline
            maxRows={3}
            value={currentText}
            onChange={e => setCurrentText(e.target.value)}
            onKeyPress={handleKeyPress}
            disabled={submitting}
            placeholder="Describe the issue..."
          />
          <Button
            variant="contained"
            color="primary"
            size="small"
            startIcon={<AddIcon />}
            onClick={handleAdd}
            disabled={!currentText.trim() || submitting}
            style={{ minWidth: 80, height: 40 }}
          >
            Add
          </Button>
        </div>

        {reasons.length === 0 ? (
          <div className={classes.emptyState}>
            <Typography variant="body2">
              Add at least one reason to reject.
            </Typography>
          </div>
        ) : (
          <div className={classes.reasonList}>
            <List dense>
              {reasons.map(reason => (
                <ListItem key={reason.id}>
                  <span className={classes.reasonNumber}>{reason.id}.</span>
                  <ListItemText primary={reason.text} />
                  <ListItemSecondaryAction>
                    <IconButton
                      edge="end"
                      size="small"
                      onClick={() => handleRemove(reason.id)}
                      disabled={submitting}
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </ListItemSecondaryAction>
                </ListItem>
              ))}
            </List>
          </div>
        )}

        <Typography variant="caption" color="textSecondary">
          {reasons.length} reason{reasons.length !== 1 ? 's' : ''} added
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={onCancel} disabled={submitting}>
          Cancel
        </Button>
        <Button
          className={classes.confirmButton}
          onClick={handleConfirm}
          disabled={reasons.length === 0 || submitting}
          startIcon={submitting ? <CircularProgress size={16} color="inherit" /> : undefined}
        >
          {submitting ? 'Rejecting...' : 'Confirm Rejection'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
