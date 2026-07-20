import React from 'react';
import { Route, Routes } from 'react-router-dom';
import { WorkflowListPage } from './WorkflowListPage/WorkflowListPage';
import { WorkflowDetailPage } from './WorkflowDetailPage/WorkflowDetailPage';

export function Router() {
  return (
    <Routes>
      <Route path="/" element={<WorkflowListPage />} />
      <Route path="/:workflowId" element={<WorkflowDetailPage />} />
    </Routes>
  );
}
