import React, { useState, useCallback, useMemo } from 'react';
import { useAsync } from 'react-use';
import {
  Table,
  TableColumn,
} from '@backstage/core-components';
import {
  configApiRef,
  discoveryApiRef,
  fetchApiRef,
  identityApiRef,
  useApi,
} from '@backstage/core-plugin-api';
import {
  Checkbox,
  IconButton,
  TextField,
  Tooltip,
  Typography,
  makeStyles,
} from '@material-ui/core';
import RefreshIcon from '@material-ui/icons/Refresh';
import { createPhWorkflowsClient } from '../../api/client';
import { TokenInfo } from '../../api/types';
import { RevokeDialog } from './RevokeDialog';

const useStyles = makeStyles(theme => ({
  toolbar: {
    display: 'flex',
    alignItems: 'center',
    gap: theme.spacing(2),
    marginBottom: theme.spacing(2),
  },
  searchField: {
    minWidth: 280,
  },
  revokeBtn: {
    color: theme.palette.error.main,
    fontWeight: 600,
    cursor: 'pointer',
    border: `1px solid ${theme.palette.error.main}`,
    borderRadius: 4,
    padding: '4px 12px',
    background: 'none',
    fontSize: '0.8125rem',
    '&:hover': {
      backgroundColor: theme.palette.error.main,
      color: '#fff',
    },
    '&:disabled': {
      opacity: 0.4,
      cursor: 'default',
      '&:hover': {
        backgroundColor: 'transparent',
        color: theme.palette.error.main,
      },
    },
  },
  spacer: {
    flex: 1,
  },
}));

type TokenRow = TokenInfo;

export function TokenManagementTab() {
  const classes = useStyles();
  const configApi = useApi(configApiRef);
  const discoveryApi = useApi(discoveryApiRef);
  const fetchApi = useApi(fetchApiRef);
  const identityApi = useApi(identityApiRef);
  const centralApiUrl = configApi.getString('phWorkflows.centralApiUrl');

  const client = useMemo(
    () => createPhWorkflowsClient({ centralApiUrl, discoveryApi, fetchApi, identityApi }),
    [centralApiUrl, discoveryApi, fetchApi, identityApi],
  );

  const [refreshKey, setRefreshKey] = useState(0);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [revokeDialogOpen, setRevokeDialogOpen] = useState(false);
  const [revokeAll, setRevokeAll] = useState(false);

  const searchTimer = React.useRef<ReturnType<typeof setTimeout>>();
  const handleSearchChange = useCallback((val: string) => {
    setSearch(val);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => {
      setDebouncedSearch(val);
      setSelected(new Set());
    }, 400);
  }, []);

  const { value, loading, error } = useAsync(async () => {
    if (debouncedSearch.trim()) {
      return client.searchTokens(debouncedSearch.trim());
    }
    return client.getTokens();
  }, [refreshKey, debouncedSearch]);

  const tokens: TokenRow[] = value?.tokens ?? [];

  const handleRefresh = useCallback(() => {
    setRefreshKey(k => k + 1);
    setSelected(new Set());
  }, []);

  const handleSelectToggle = useCallback((email: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(email)) next.delete(email);
      else next.add(email);
      return next;
    });
  }, []);

  const handleSelectAll = useCallback(() => {
    if (selected.size === tokens.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(tokens.map(t => t.email)));
    }
  }, [tokens, selected.size]);

  const handleRevokeSelected = useCallback(() => {
    setRevokeAll(false);
    setRevokeDialogOpen(true);
  }, []);

  const handleRevokeAll = useCallback(() => {
    setRevokeAll(true);
    setRevokeDialogOpen(true);
  }, []);

  const handleRevoked = useCallback(() => {
    setSelected(new Set());
    setRefreshKey(k => k + 1);
  }, []);

  const formatDate = (iso: string) => {
    try {
      return new Date(iso).toLocaleString();
    } catch {
      return iso;
    }
  };

  const columns: TableColumn<TokenRow>[] = [
    {
      title: '',
      field: 'email',
      sorting: false,
      width: '40px',
      headerStyle: { paddingLeft: 8, paddingRight: 0 },
      cellStyle: { paddingLeft: 8, paddingRight: 0 },
      render: (row: TokenRow) => (
        <Checkbox
          size="small"
          checked={selected.has(row.email)}
          onChange={() => handleSelectToggle(row.email)}
          onClick={e => e.stopPropagation()}
        />
      ),
      customFilterAndSearch: () => true,
    },
    {
      title: 'Email',
      field: 'email',
      highlight: true,
    },
    {
      title: 'Groups',
      field: 'group_names',
      render: (row: TokenRow) => row.group_names?.join(', ') || '—',
    },
    {
      title: 'Source',
      field: 'source',
    },
    {
      title: 'Issued',
      field: 'issued_at',
      render: (row: TokenRow) => formatDate(row.issued_at),
    },
    {
      title: 'Expires',
      field: 'expires_at',
      render: (row: TokenRow) => formatDate(row.expires_at),
    },
  ];

  return (
    <>
      <div className={classes.toolbar}>
        <TextField
          className={classes.searchField}
          label="Search by email"
          variant="outlined"
          size="small"
          value={search}
          onChange={e => handleSearchChange(e.target.value)}
        />
        <Tooltip title="Refresh">
          <IconButton onClick={handleRefresh} disabled={loading} size="small">
            <RefreshIcon />
          </IconButton>
        </Tooltip>
        <div className={classes.spacer} />
        <button
          className={classes.revokeBtn}
          disabled={selected.size === 0}
          onClick={handleRevokeSelected}
        >
          Revoke Selected ({selected.size})
        </button>
        <button
          className={classes.revokeBtn}
          disabled={tokens.length === 0}
          onClick={handleRevokeAll}
        >
          Revoke All
        </button>
      </div>

      <Table<TokenRow>
        title={
          <Typography variant="subtitle2">
            Active Tokens ({tokens.length})
            {tokens.length > 0 && (
              <span
                style={{ marginLeft: 12, cursor: 'pointer', textDecoration: 'underline', fontSize: '0.8rem' }}
                onClick={handleSelectAll}
              >
                {selected.size === tokens.length ? 'Deselect All' : 'Select All'}
              </span>
            )}
          </Typography>
        }
        options={{
          search: false,
          paging: true,
          pageSize: 20,
          padding: 'dense',
        }}
        columns={columns}
        data={tokens}
        isLoading={loading}
        emptyContent={
          error ? (
            <div style={{ padding: 16 }}>
              Failed to load tokens: {error.message}
            </div>
          ) : undefined
        }
      />

      <RevokeDialog
        open={revokeDialogOpen}
        emails={Array.from(selected)}
        isRevokeAll={revokeAll}
        onClose={() => setRevokeDialogOpen(false)}
        onRevoked={handleRevoked}
      />
    </>
  );
}
