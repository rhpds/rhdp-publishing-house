import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Typography,
  CircularProgress,
  makeStyles,
} from '@material-ui/core';
import SendIcon from '@material-ui/icons/Send';
import { WorkflowStage } from '../../api/types';
import { STAGE_LABELS } from '../../utils/stageMapping';

const useStyles = makeStyles(() => ({
  sendButton: {
    backgroundColor: '#1976d2',
    color: '#fff',
    fontWeight: 600,
    '&:hover': { backgroundColor: '#1565c0' },
    '&:disabled': { backgroundColor: '#ccc' },
  },
}));

interface MessageDialogProps {
  open: boolean;
  stage: WorkflowStage;
  senderName: string;
  submitting: boolean;
  onConfirm: (text: string) => void;
  onCancel: () => void;
}

export function MessageDialog({
  open,
  stage,
  senderName,
  submitting,
  onConfirm,
  onCancel,
}: MessageDialogProps) {
  const classes = useStyles();
  const [text, setText] = useState('');

  useEffect(() => {
    if (open) setText('');
  }, [open]);

  return (
    <Dialog open={open} onClose={onCancel} maxWidth="sm" fullWidth>
      <DialogTitle>Message Author</DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="textSecondary" gutterBottom>
          Stage: <strong>{STAGE_LABELS[stage] || stage}</strong> | From: <strong>{senderName}</strong>
        </Typography>

        <TextField
          label="Message"
          variant="outlined"
          fullWidth
          multiline
          minRows={3}
          maxRows={8}
          value={text}
          onChange={e => setText(e.target.value)}
          disabled={submitting}
          placeholder="Write a message to the project author..."
          style={{ marginTop: 8 }}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onCancel} disabled={submitting}>
          Cancel
        </Button>
        <Button
          className={classes.sendButton}
          onClick={() => onConfirm(text.trim())}
          disabled={!text.trim() || submitting}
          startIcon={submitting ? <CircularProgress size={16} color="inherit" /> : <SendIcon />}
        >
          {submitting ? 'Sending...' : 'Send'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
