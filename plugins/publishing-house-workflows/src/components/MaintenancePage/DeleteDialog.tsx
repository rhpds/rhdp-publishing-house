import React, { useState, useCallback } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Checkbox,
  FormControlLabel,
  Typography,
  CircularProgress,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  makeStyles,
} from '@material-ui/core';
import { Alert } from '@material-ui/lab';
import WarningIcon from '@material-ui/icons/Warning';
import CheckCircleIcon from '@material-ui/icons/CheckCircle';
import ErrorIcon from '@material-ui/icons/Error';
import {
  discoveryApiRef,
  fetchApiRef,
  identityApiRef,
  useApi,
} from '@backstage/core-plugin-api';
import { Entity } from '@backstage/catalog-model';
import { createPhWorkflowsClient } from '../../api/client';
import { DeleteProjectResult } from '../../api/types';

const useStyles = makeStyles(theme => ({
  warning: {
    marginBottom: theme.spacing(2),
  },
  resultList: {
    marginTop: theme.spacing(1),
  },
  successIcon: {
    color: '#4caf50',
  },
  errorIcon: {
    color: '#f44336',
  },
}));

interface DeleteDialogProps {
  open: boolean;
  entity: Entity | null;
  onClose: () => void;
  onDeleted: () => void;
}

export function DeleteDialog({ open, entity, onClose, onDeleted }: DeleteDialogProps) {
  const classes = useStyles();
  const discoveryApi = useApi(discoveryApiRef);
  const fetchApi = useApi(fetchApiRef);
  const identityApi = useApi(identityApiRef);

  const [deleteRepo, setDeleteRepo] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [result, setResult] = useState<DeleteProjectResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const slug = entity?.metadata?.name ?? '';

  const handleClose = useCallback(() => {
    setDeleteRepo(false);
    setDeleting(false);
    setResult(null);
    setError(null);
    onClose();
  }, [onClose]);

  const handleDelete = useCallback(async () => {
    if (!entity) return;
    setDeleting(true);
    setError(null);
    setResult(null);

    try {
      const client = createPhWorkflowsClient({ discoveryApi, fetchApi, identityApi });
      const res = await client.deleteProject(slug, deleteRepo);
      setResult(res);
    } catch (e: any) {
      setError(e.message || 'Unknown error');
    } finally {
      setDeleting(false);
    }
  }, [entity, slug, deleteRepo, discoveryApi, fetchApi, identityApi]);

  return (
    <Dialog open={open} onClose={deleting || result ? undefined : handleClose} maxWidth="sm" fullWidth disableEscapeKeyDown={!!result || deleting}>
      <DialogTitle>Delete Component: {slug}</DialogTitle>
      <DialogContent>
        {!result && !error && (
          <>
            <Alert severity="warning" className={classes.warning}>
              This will permanently delete the component and all associated resources.
            </Alert>
            <Typography variant="body2" gutterBottom>
              The following cleanup will be performed:
            </Typography>
            <List dense>
              <ListItem>
                <ListItemIcon><WarningIcon fontSize="small" /></ListItemIcon>
                <ListItemText primary="Abort any running SonataFlow workflow" />
              </ListItem>
              <ListItem>
                <ListItemIcon><WarningIcon fontSize="small" /></ListItemIcon>
                <ListItemText primary="Delete LiteLLM virtual keys for this project" />
              </ListItem>
              <ListItem>
                <ListItemIcon><WarningIcon fontSize="small" /></ListItemIcon>
                <ListItemText primary="Remove catalog location and entity" />
              </ListItem>
              <ListItem>
                <ListItemIcon><WarningIcon fontSize="small" /></ListItemIcon>
                <ListItemText primary="Archive the Jira epic" />
              </ListItem>
            </List>
            <FormControlLabel
              control={
                <Checkbox
                  checked={deleteRepo}
                  onChange={e => setDeleteRepo(e.target.checked)}
                  color="secondary"
                />
              }
              label="Also delete the GitHub repository"
            />
          </>
        )}

        {result && (
          <div className={classes.resultList}>
            <Typography variant="subtitle2" gutterBottom>
              Cleanup Results:
            </Typography>
            <List dense>
              <ResultItem label="Workflow aborted" success={result.workflow_aborted} />
              <ResultItem label="Catalog location removed" success={result.catalog_cleaned} />
              <ResultItem label={`LiteLLM keys deleted: ${result.litellm_keys_deleted}`} success={result.litellm_keys_deleted > 0} />
              <ResultItem label="Jira epic archived" success={result.jira_archived} />
              {deleteRepo && <ResultItem label="GitHub repo deleted" success={result.repo_deleted} />}
            </List>
            {result.errors.length > 0 && (
              <Alert severity="warning" style={{ marginTop: 8 }}>
                {result.errors.map((err, i) => (
                  <div key={i}>{err}</div>
                ))}
              </Alert>
            )}
          </div>
        )}

        {error && (
          <Alert severity="error">
            {error}
          </Alert>
        )}
      </DialogContent>
      <DialogActions>
        {!result ? (
          <>
            <Button onClick={handleClose} disabled={deleting}>Cancel</Button>
            <Button
              onClick={handleDelete}
              color="secondary"
              variant="contained"
              disabled={deleting}
              startIcon={deleting ? <CircularProgress size={16} /> : undefined}
            >
              {deleting ? 'Deleting...' : 'Delete'}
            </Button>
          </>
        ) : (
          <Button onClick={() => { handleClose(); onDeleted(); }} color="primary">
            Close
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}

function ResultItem({ label, success }: { label: string; success: boolean }) {
  const classes = useStyles();
  return (
    <ListItem>
      <ListItemIcon>
        {success ? (
          <CheckCircleIcon fontSize="small" className={classes.successIcon} />
        ) : (
          <ErrorIcon fontSize="small" className={classes.errorIcon} />
        )}
      </ListItemIcon>
      <ListItemText primary={label} />
    </ListItem>
  );
}
