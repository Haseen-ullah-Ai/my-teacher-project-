import { lazy, Suspense } from 'react';
import { Navigate, Outlet, Route, Routes } from 'react-router-dom';
import { AppShell } from './components/AppShell';
import { Skeleton } from './components/ui';

const DashboardPage = lazy(() => import('./pages/DashboardPage').then((module) => ({ default: module.DashboardPage })));
const NewResearchPage = lazy(() => import('./pages/NewResearchPage').then((module) => ({ default: module.NewResearchPage })));
const RunsPage = lazy(() => import('./pages/RunsPage').then((module) => ({ default: module.RunsPage })));
const RunDetailPage = lazy(() => import('./pages/RunDetailPage').then((module) => ({ default: module.RunDetailPage })));
const AssetsPage = lazy(() => import('./pages/AssetsPage').then((module) => ({ default: module.AssetsPage })));
const ToolsPage = lazy(() => import('./pages/ToolsPage').then((module) => ({ default: module.ToolsPage })));
const SettingsPage = lazy(() => import('./pages/SettingsPage').then((module) => ({ default: module.SettingsPage })));

function PageLoading() {
  return <div className="page-stack" aria-label="Loading page"><Skeleton lines={7} /></div>;
}

function SuspendedPages() {
  return <Suspense fallback={<PageLoading />}><Outlet /></Suspense>;
}

function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route element={<SuspendedPages />}>
          <Route index element={<DashboardPage />} />
          <Route path="runs" element={<RunsPage />} />
          <Route path="runs/new" element={<NewResearchPage />} />
          <Route path="runs/:runId" element={<RunDetailPage />} />
          <Route path="documents" element={<AssetsPage kind="documents" />} />
          <Route path="datasets" element={<AssetsPage kind="datasets" />} />
          <Route path="tools" element={<ToolsPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Route>
    </Routes>
  );
}

export default App;
