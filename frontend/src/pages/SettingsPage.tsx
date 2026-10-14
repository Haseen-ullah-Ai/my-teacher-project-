import { useHealth } from '../api/hooks';
import { API_BASE_URL } from '../api/client';
import { useThemePreference } from '../components/AppShell';
import { Card, ErrorState, PageHeader, Skeleton } from '../components/ui';

export function SettingsPage() {
  const health = useHealth();
  const { preference, setPreference } = useThemePreference();
  return <div className="page-stack page-narrow">
    <PageHeader title="Settings" description="Workspace preferences and application information." />
    <Card title="Appearance" className="settings-card"><div className="settings-row"><div><strong>Theme</strong><p>Choose an appearance or follow your operating system preference.</p></div><div className="segmented-control" role="group" aria-label="Theme preference">{(['system', 'light', 'dark'] as const).map((theme) => <button key={theme} className={preference === theme ? 'segment-active' : ''} aria-pressed={preference === theme} onClick={() => setPreference(theme)}>{theme[0].toUpperCase() + theme.slice(1)}</button>)}</div></div></Card>
    <Card title="Connection" className="settings-card"><div className="settings-row"><div><strong>API base URL</strong><p>Requests are sent to the configured ResearchPilot backend.</p></div><code className="api-url">{API_BASE_URL}</code></div><div className="settings-row"><div><strong>LLM provider</strong><p>Provider selection is managed by the backend environment.</p></div><span className="settings-readonly">{import.meta.env.VITE_LLM_PROVIDER ?? 'Backend managed'}</span></div><div className="settings-row"><div><strong>Database</strong><p>PostgreSQL connectivity reported by the health endpoint.</p></div>{health.isLoading ? <Skeleton lines={1} /> : health.isError ? <ErrorState error={health.error} retry={() => void health.refetch()} /> : <span className={`status-badge ${health.data?.db === 'ok' ? 'status-completed' : 'status-failed'}`}>{health.data?.db ?? 'unknown'}</span>}</div></Card>
    <Card title="About ResearchPilot" className="settings-card"><div className="about-brand"><span className="brand-mark">RP</span><div><strong>ResearchPilot</strong><p>Controlled, evidence-first research for your workspace.</p></div></div><div className="settings-row"><span>Version</span><code>{health.data?.version ?? (health.isLoading ? 'Loading…' : 'Unavailable')}</code></div><div className="settings-row"><span>Data boundary</span><strong>Local tools only</strong></div><div className="settings-row"><span>Report provenance</span><strong>Evidence references included</strong></div></Card>
  </div>;
}
