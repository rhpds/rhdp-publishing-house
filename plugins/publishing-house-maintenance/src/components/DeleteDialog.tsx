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
  useApi,
} from '@backstage/core-plugin-api';
import { catalogApiRef } from '@backstage/plugin-catalog-react';
import { Entity } from '@backstage/catalog-model';
import { createPhMaintenanceClient, DeleteProjectResult } from '../api/client';

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
  const catalogApi = useApi(catalogApiRef);

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
      const client = createPhMaintenanceClient({ discoveryApi, fetchApi });
      const res = await client.deleteProject(slug, deleteRepo);
      setResult(res);

      const uid = entity.metadata?.uid;
      if (uid) {
        try {
          const fullEntity = await catalogApi.getEntityByRef({kind: entity.kind, namespace: entity.metadata?.namespace ?? 'default', name: entity.metadata?.name ?? ''});
          const locationRef = fullEntity?.metadata?.annotations?.['backstage.io/managed-by-location'] ?? '';
          const match = locationRef.match(/url:(.+)/);
          if (match) {
            const proxyUrl = await discoveryApi.getBaseUrl('catalog');
            const locResponse = await fetchApi.fetch(`${proxyUrl}/locations`);
            if (locResponse.ok) {
              const locations = await locResponse.json();
              const loc = (locations as any[]).find((l: any) => (l.data?.target ?? l.target) === match[1]);
              if (loc) {
                await fetchApi.fetch(`${proxyUrl}/locations/${loc.id}`, { method: 'DELETE' });
              }
            }
          }
          await catalogApi.removeEntityByUid(uid);
        } catch (e: any) {
          res.errors.push(`Catalog unregister: ${e.message}`);
        }
      }

    } catch (e: any) {
      setError(e.message || 'Unknown error');
    } finally {
      setDeleting(false);
    }
  }, [entity, slug, deleteRepo, discoveryApi, fetchApi, catalogApi]);

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
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
                <ListItemText primary="Archive the Jira epic" />
              </ListItem>
              <ListItem>
                <ListItemIcon><WarningIcon fontSize="small" /></ListItemIcon>
                <ListItemText primary="Unregister entity from the catalog" />
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
              <ResultItem label={`LiteLLM keys deleted: ${result.litellm_keys_deleted}`} success={result.litellm_keys_deleted > 0} />
              <ResultItem label="Jira epic archived" success={result.jira_archived} />
              {deleteRepo && <ResultItem label="GitHub repo deleted" success={result.repo_deleted} />}
              <ResultItem label="Catalog entity unregistered" success />
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
