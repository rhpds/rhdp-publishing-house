import React, { useState, useCallback } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  CircularProgress,
  makeStyles,
} from '@material-ui/core';
import { Alert } from '@material-ui/lab';
import {
  configApiRef,
  discoveryApiRef,
  fetchApiRef,
  identityApiRef,
  useApi,
} from '@backstage/core-plugin-api';
import { createPhWorkflowsClient } from '../../api/client';

const useStyles = makeStyles(theme => ({
  warning: {
    marginBottom: theme.spacing(2),
  },
  emailList: {
    maxHeight: 200,
    overflow: 'auto',
    marginTop: theme.spacing(1),
    marginBottom: theme.spacing(1),
    padding: theme.spacing(1),
    backgroundColor: theme.palette.background.default,
    borderRadius: 4,
    fontFamily: 'monospace',
    fontSize: '0.85rem',
  },
}));

interface RevokeDialogProps {
  open: boolean;
  emails: string[];
  isRevokeAll: boolean;
  onClose: () => void;
  onRevoked: () => void;
}

export function RevokeDialog({ open, emails, isRevokeAll, onClose, onRevoked }: RevokeDialogProps) {
  const classes = useStyles();
  const configApi = useApi(configApiRef);
  const discoveryApi = useApi(discoveryApiRef);
  const fetchApi = useApi(fetchApiRef);
  const identityApi = useApi(identityApiRef);
  const centralApiUrl = configApi.getString('phWorkflows.centralApiUrl');

  const [revoking, setRevoking] = useState(false);
  const [result, setResult] = useState<{ revoked: number; failed: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleClose = useCallback(() => {
    setRevoking(false);
    setResult(null);
    setError(null);
    onClose();
  }, [onClose]);

  const handleRevoke = useCallback(async () => {
    setRevoking(true);
    setError(null);
    setResult(null);

    try {
      const client = createPhWorkflowsClient({ centralApiUrl, discoveryApi, fetchApi, identityApi });

      if (isRevokeAll) {
        const res = await client.revokeAllTokens();
        setResult({ revoked: res.revoked_count, failed: 0 });
      } else {
        let revoked = 0;
        let failed = 0;
        for (const email of emails) {
          try {
            const res = await client.revokeToken(email);
            if (res.revoked) revoked++;
            else failed++;
          } catch {
            failed++;
          }
        }
        setResult({ revoked, failed });
      }
    } catch (e: any) {
      setError(e.message || 'Revocation failed');
    } finally {
      setRevoking(false);
    }
  }, [emails, isRevokeAll, centralApiUrl, discoveryApi, fetchApi, identityApi]);

  const count = isRevokeAll ? 'all' : String(emails.length);

  return (
    <Dialog open={open} onClose={revoking || result ? undefined : handleClose} maxWidth="sm" fullWidth disableEscapeKeyDown={!!result || revoking}>
      <DialogTitle>Revoke Tokens</DialogTitle>
      <DialogContent>
        {!result && !error && (
          <>
            <Alert severity="warning" className={classes.warning}>
              {isRevokeAll
                ? 'This will revoke ALL active tokens. Every user will need to re-authenticate.'
                : `This will revoke ${count} token(s). Affected users will need to re-authenticate.`}
            </Alert>
            {!isRevokeAll && emails.length > 0 && (
              <div className={classes.emailList}>
                {emails.map(e => (
                  <div key={e}>{e}</div>
                ))}
              </div>
            )}
          </>
        )}

        {result && (
          <Alert severity={result.failed > 0 ? 'warning' : 'success'}>
            <Typography variant="body2">
              Revoked: {result.revoked}
              {result.failed > 0 && ` | Failed: ${result.failed}`}
            </Typography>
          </Alert>
        )}

        {error && <Alert severity="error">{error}</Alert>}
      </DialogContent>
      <DialogActions>
        {!result ? (
          <>
            <Button onClick={handleClose} disabled={revoking}>Cancel</Button>
            <Button
              onClick={handleRevoke}
              color="secondary"
              variant="contained"
              disabled={revoking}
              startIcon={revoking ? <CircularProgress size={16} /> : undefined}
            >
              {revoking ? 'Revoking...' : 'Revoke'}
            </Button>
          </>
        ) : (
          <Button onClick={() => { handleClose(); onRevoked(); }} color="primary">
            Close
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}
