import React from 'react';
import { InfoCard } from '@backstage/core-components';
import {
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Typography,
} from '@material-ui/core';
import AddCircleOutlineIcon from '@material-ui/icons/AddCircleOutline';
import AccountTreeIcon from '@material-ui/icons/AccountTree';
import CompareArrowsIcon from '@material-ui/icons/CompareArrows';
import { useNavigate } from 'react-router-dom';

export const PhHomeCard = () => {
  const navigate = useNavigate();

  const links = [
    {
      label: 'Create New Project',
      path: '/create',
      icon: <AddCircleOutlineIcon />,
    },
    {
      label: 'Active Workflows',
      path: '/publishing-house-workflows',
      icon: <AccountTreeIcon />,
    },
    {
      label: 'Spec Drift Dashboard',
      path: '/publishing-house-drift',
      icon: <CompareArrowsIcon />,
    },
  ];

  return (
    <InfoCard title="Demo Platform Publishing House">
      <Typography variant="body2" paragraph>
        Create, review, and publish RHDP lab and demo content through automated
        workflows.
      </Typography>
      <List dense>
        {links.map(link => (
          <ListItem
            key={link.path}
            button
            onClick={() => navigate(link.path)}
          >
            <ListItemIcon>{link.icon}</ListItemIcon>
            <ListItemText primary={link.label} />
          </ListItem>
        ))}
      </List>
    </InfoCard>
  );
};
