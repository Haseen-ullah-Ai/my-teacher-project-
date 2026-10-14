import { useMemo } from 'react';
import { Activity, ArrowRight, Clock3, FileSearch, Plus, Wrench } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { useOverview } from '../api/hooks';
import { DataTable } from '../components/DataTable';
import { Button, Card, EmptyState, ErrorState, PageHeader, Skeleton, StatCard, StatusBadge, formatDate, formatDuration } from '../components/ui';
import type { RunItem } from '../types/api';

const chartColors = ['#6068dd', '#1e9e76', '#d89927', '#467bb5', '#8c5ce1', '#d55d69'];

export function DashboardPage() {
  const overview = useOverview();
  const navigate = useNavigate();
  const trend = useMemo(() => overview.data?.runs_by_day ?? [], [overview.data]);
  const statusData = useMemo(() => Object.entries(overview.data?.runs_by_status ?? {}).map(([name, value]) => ({ name, value })), [overview.data]);
  const tools = useMemo(() => overview.data?.tool_usage ?? [], [overview.data]);
  const recent = overview.data?.recent_runs ?? [];

  return (
    <div className="page-stack">
      <PageHeader
        title="Research overview"
        description="A clear view of your controlled research activity."
        actions={<Button onClick={() => navigate('/runs/new')}><Plus size={16} /> New research</Button>}
      />
      {overview.isError && <ErrorState error={overview.error} retry={() => void overview.refetch()} />}
      {overview.isLoading ? <div className="stats-grid">{Array.from({ length: 4 }, (_, index) => <div key={index} className="card stat-skeleton"><Skeleton lines={3} /></div>)}</div> : overview.data && (
        <>
          <div className="stats-grid">
            <StatCard label="Total runs" value={overview.data.total_runs.toLocaleString()} detail="Research tasks submitted" icon={<Activity size={18} />} />
            <StatCard label="Success rate" value={`${Math.round(overview.data.success_rate * (overview.data.success_rate <= 1 ? 100 : 1))}%`} detail="Runs completed successfully" icon={<FileSearch size={18} />} tone="green" />
            <StatCard label="Average duration" value={formatDuration(overview.data.average_duration_ms)} detail="Across completed runs" icon={<Clock3 size={18} />} tone="blue" />
            <StatCard label="Tool calls" value={overview.data.total_tool_calls.toLocaleString()} detail="Controlled local execution" icon={<Wrench size={18} />} tone="amber" />
          </div>
          <div className="dashboard-chart-grid">
            <Card title="Run activity" className="chart-card chart-card-wide">
              {trend.length ? <div className="chart-frame"><ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trend} margin={{ top: 8, right: 12, left: -16, bottom: 0 }}>
                  <defs><linearGradient id="runFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#6068dd" stopOpacity={0.25} /><stop offset="100%" stopColor="#6068dd" stopOpacity={0.01} /></linearGradient></defs>
                  <CartesianGrid stroke="var(--border-subtle)" vertical={false} />
                  <XAxis dataKey="date" tickFormatter={(value: string) => new Date(value).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })} tickLine={false} axisLine={false} />
                  <YAxis allowDecimals={false} tickLine={false} axisLine={false} />
                  <Tooltip contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 10, color: 'var(--text-primary)' }} />
                  <Area type="monotone" dataKey="count" stroke="#6068dd" strokeWidth={2} fill="url(#runFill)" />
                </AreaChart>
              </ResponsiveContainer></div> : <EmptyState title="No activity yet" description="Your run activity for the last 14 days will appear here." />}
            </Card>
            <Card title="Runs by status" className="chart-card">
              {statusData.length ? <div className="donut-wrap">
                <div className="donut"><ResponsiveContainer width="100%" height="100%">
                  <PieChart><Pie data={statusData} dataKey="value" nameKey="name" innerRadius={62} outerRadius={84} paddingAngle={3} stroke="none">{statusData.map((entry, index) => <Cell key={entry.name} fill={chartColors[index % chartColors.length]} />)}</Pie><Tooltip /></PieChart>
                </ResponsiveContainer></div>
                <ul className="chart-legend">{statusData.map((item, index) => <li key={item.name}><i style={{ background: chartColors[index % chartColors.length] }} /><span>{item.name.replace(/_/g, ' ')}</span><strong>{item.value}</strong></li>)}</ul>
              </div> : <EmptyState title="No statuses to show" description="Run status breakdown appears after your first task." />}
            </Card>
            <Card title="Tool usage" className="chart-card chart-card-wide">
              {tools.length ? <div className="chart-frame chart-frame-short"><ResponsiveContainer width="100%" height="100%">
                <BarChart data={tools} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
                  <CartesianGrid stroke="var(--border-subtle)" vertical={false} />
                  <XAxis dataKey="tool_name" tickLine={false} axisLine={false} />
                  <YAxis allowDecimals={false} tickLine={false} axisLine={false} />
                  <Tooltip contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 10, color: 'var(--text-primary)' }} />
                  <Bar dataKey="count" name="Calls" fill="#6068dd" radius={[5, 5, 0, 0]} />
                  <Bar dataKey="failures" name="Failures" fill="#d55d69" radius={[5, 5, 0, 0]} />
                </BarChart>
              </ResponsiveContainer></div> : <EmptyState title="No tool activity yet" description="Tool usage and failures will be summarized here." />}
            </Card>
            <Card title="How ResearchPilot works" className="chart-card how-card">
              <div className="how-content"><div className="how-icon"><Activity size={20} /></div><strong>Research that stays under control</strong><p>Your runs use local documents and datasets. Every result is logged and evidence-linked.</p><Link to="/tools" className="text-link">Explore available tools <ArrowRight size={14} /></Link></div>
            </Card>
          </div>
          <Card title="Recent runs" action={<Link className="text-link" to="/runs">All runs <ArrowRight size={14} /></Link>}>
            <DataTable<RunItem>
              rows={recent.slice(0, 6)}
              rowKey={(run) => run.run_id}
              onRowClick={(run) => navigate(`/runs/${run.run_id}`)}
              emptyTitle="Your research starts here"
              emptyDescription="Create a run to search local evidence and generate a cited report."
              columns={[
                { key: 'task', label: 'Research task', render: (run) => <span className="task-cell">{run.task}</span>, sortValue: (run) => run.task },
                { key: 'status', label: 'Status', render: (run) => <StatusBadge status={run.status} />, sortValue: (run) => run.status },
                { key: 'duration', label: 'Duration', render: (run) => formatDuration(run.duration_ms ?? run.total_duration_ms), sortValue: (run) => run.duration_ms ?? run.total_duration_ms ?? 0 },
                { key: 'tools', label: 'Tools', render: (run) => run.tool_call_count ?? 0, sortValue: (run) => run.tool_call_count ?? 0 },
                { key: 'created', label: 'Created', render: (run) => formatDate(run.created_at), sortValue: (run) => run.created_at },
              ]}
            />
          </Card>
        </>
      )}
    </div>
  );
}
