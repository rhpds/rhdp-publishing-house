import React, { useState } from 'react';
import {
  Box,
  Chip,
  TextField,
  Button,
  IconButton,
  makeStyles,
  Typography,
} from '@material-ui/core';
import AddIcon from '@material-ui/icons/Add';
import SaveIcon from '@material-ui/icons/Save';
import CancelIcon from '@material-ui/icons/Cancel';

const useStyles = makeStyles(theme => ({
  container: {
    display: 'flex',
    flexDirection: 'column',
    gap: theme.spacing(1),
  },
  tagsRow: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: theme.spacing(0.5),
    alignItems: 'center',
    minHeight: 32,
  },
  addRow: {
    display: 'flex',
    gap: theme.spacing(1),
    alignItems: 'center',
  },
  actionButtons: {
    display: 'flex',
    gap: theme.spacing(1),
    marginTop: theme.spacing(1),
  },
  errorText: {
    color: theme.palette.error.main,
    fontSize: '0.75rem',
    marginTop: theme.spacing(0.5),
  },
}));

interface TagEditorProps {
  initialTags: string[];
  canEdit: boolean;
  onSave: (tags: string[]) => Promise<void>;
}

export function TagEditor({ initialTags, canEdit, onSave }: TagEditorProps) {
  const classes = useStyles();
  const [tags, setTags] = useState<string[]>(initialTags);
  const [newTag, setNewTag] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');

  const hasChanges = JSON.stringify(tags) !== JSON.stringify(initialTags);

  const validateTag = (tag: string): string | null => {
    if (tag.length > 30) {
      return 'Tag must be 30 characters or less';
    }
    if (tags.includes(tag)) {
      return 'Tag already exists';
    }
    return null;
  };

  const handleAddTag = () => {
    const trimmed = newTag.trim();
    if (!trimmed) return;

    // Validate
    if (tags.length >= 10) {
      setError('Maximum 10 tags allowed');
      return;
    }

    const validationError = validateTag(trimmed);
    if (validationError) {
      setError(validationError);
      return;
    }

    // Add to local state
    setTags([...tags, trimmed]);
    setNewTag('');
    setError('');
  };

  const handleRemoveTag = (tagToRemove: string) => {
    setTags(tags.filter(t => t !== tagToRemove));
    setError('');
  };

  const handleSave = async () => {
    setIsSaving(true);
    setError('');
    try {
      await onSave(tags);
      // No need to update local state - parent will refresh and we'll get new initialTags
    } catch (err: any) {
      setError(err.message || 'Failed to save tags');
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    setTags(initialTags);
    setNewTag('');
    setError('');
  };

  if (!canEdit) {
    // Read-only view
    return (
      <div className={classes.tagsRow}>
        {tags.length > 0 ? (
          tags.map(tag => (
            <Chip key={tag} label={tag} size="small" variant="outlined" />
          ))
        ) : (
          <Typography variant="body2" color="textSecondary">—</Typography>
        )}
      </div>
    );
  }

  return (
    <div className={classes.container}>
      {/* Tags display with delete option */}
      <div className={classes.tagsRow}>
        {tags.length > 0 ? (
          tags.map(tag => (
            <Chip
              key={tag}
              label={tag}
              size="small"
              variant="outlined"
              onDelete={() => handleRemoveTag(tag)}
              disabled={isSaving}
            />
          ))
        ) : (
          <Typography variant="body2" color="textSecondary">No tags</Typography>
        )}
      </div>

      {/* Add new tag */}
      <div className={classes.addRow}>
        <TextField
          size="small"
          placeholder="Add tag..."
          value={newTag}
          onChange={e => setNewTag(e.target.value)}
          onKeyPress={e => {
            if (e.key === 'Enter') {
              e.preventDefault();
              handleAddTag();
            }
          }}
          disabled={isSaving || tags.length >= 10}
          style={{ width: 200 }}
        />
        <IconButton
          size="small"
          onClick={handleAddTag}
          disabled={!newTag.trim() || isSaving || tags.length >= 10}
          color="primary"
        >
          <AddIcon />
        </IconButton>
      </div>

      {/* Error message */}
      {error && <Typography className={classes.errorText}>{error}</Typography>}

      {/* Save/Cancel buttons - only show when changes exist */}
      {hasChanges && (
        <div className={classes.actionButtons}>
          <Button
            size="small"
            variant="contained"
            color="primary"
            startIcon={<SaveIcon />}
            onClick={handleSave}
            disabled={isSaving}
          >
            {isSaving ? 'Saving...' : 'Save Tags'}
          </Button>
          <Button
            size="small"
            variant="outlined"
            startIcon={<CancelIcon />}
            onClick={handleCancel}
            disabled={isSaving}
          >
            Cancel
          </Button>
        </div>
      )}
    </div>
  );
}
