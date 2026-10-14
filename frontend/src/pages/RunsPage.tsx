import { useEffect, useState } from 'react';
import { MoreHorizontal, RotateCcw, Search, XCircle } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useCancelRun, useRetryRun, useRuns } from '../api/hooks';
import { DataTable } from '../components/DataTable';
import { Button, ErrorState, PageHeader, Skeleton, StatusBadge, formatDate, formatDuration, notify } from '../components/ui';
import type { RunItem, RunStatus } from '../types/api';

const filters = ['all', 'running', 'completed', 'completed_with_warnings', 'failed', 'cancelled'] as const;
const pageSize = 10;

function RunActions({ run }: { run: RunItem }) {
  const navigate = useNavigate();
  const cancel = useCancelRun(run.run_id);
  const retry = useRetryRun(run.run_id);
  const canCancel = ['pending', 'planning', 'running', 'analyzing', 'validating', 'reporting'].includes(run.status);
  const performCancel = async (event: React.MouseEvent) => {
    event.stopPropagation();
    try { await cancel.mutateAsync(); notify('Run cancellation requested.'); }
    catch (error) { notify(error instanceof Error ? error.message : 'Could not cancel run.', 'error'); }
  };
  const performRetry = async (event: React.MouseEvent) => {
    event.stopPropagation();
    try { const result = await retry.mutateAsync(); notify('Retry run created.'); navigate(`/runs/${result.run_id}`); }
    catch (error) { notify(error instanceof Error ? error.message : 'Could not retry run.', 'error'); }
  };
  return (
    <details className="row-menu" onClick={(event) => event.stopPropagation()}>
      <summary aria-label={`Actions for ${run.task}`}><MoreHorizontal size={17} /></summary>
      <div className="row-menu-popover">
        {canCancel && <button disabled={cancel.isPending} onClick={(event) => void performCancel(event)}><XCircle size={14} /> Cancel run</button>}
        <button disabled={retry.isPending} onClick={(event) => void performRetry(event)}><RotateCcw size={14} /> Retry run</button>
      </div>
    </details>
  );
}

export function RunsPage() {
  const [filter, setFilter] = useState<string>('all');
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [offset, setOffset] = useState(0);
  const navigate = useNavigate();

  useEffect(() => {
    const timer = window.setTimeout(() => { setSearch(searchInput); setOffset(0); }, 250);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  const runs = useRuns({ status: filter === 'all' ? undefined : filter, q: search || undefined, limit: pageSize, offset });
  const data = runs.data;
  const rows = data?.items ?? [];

  return (
    <div className="page-stack">
      <PageHeader title="Research runs" description="Track, review, and manage every research execution." actions={<Button onClick={() => navigate('/runs/new')}>New research</Button>} />
      <div className="runs-toolbar">
        <label className="search-field"><Search size={16} /><input value={searchInput} onChange={(event) => setSearchInput(event.target.value)} placeholder="Search tasks…" aria-label="Search runs" /></label>
        <div className="filter-chips" role="tablist" aria-label="Filter runs by status">{filters.map((item) => <button key={item} role="tab" aria-selected={filter === item} className={`filter-chip ${filter === item ? 'filter-chip-active' : ''}`} onClick={() => { setFilter(item); setOffset(0); }}>{item === 'all' ? 'All runs' : item.replace(/_/g, ' ')}</button>)}</div>
      </div>
      {runs.isError && <ErrorState error={runs.error} retry={() => void runs.refetch()} />}
      {runs.isLoading ? <div className="card table-loading"><Skeleton lines={7} /></div> : (
        <div className="card runs-table-card">
          <DataTable<RunItem>
            rows={rows}
            rowKey={(run) => run.run_id}
            onRowClick={(run) => navigate(`/runs/${run.run_id}`)}
            emptyTitle={search || filter !== 'all' ? 'No runs match these filters' : 'No research runs yet'}
            emptyDescription={search || filter !== 'all' ? 'Try a different search or clear the status filter.' : 'Start your first research run to see plans, evidence, and reports here.'}
            columns={[
              { key: 'task', label: 'Research task', render: (run) => <div className="run-task-cell"><span className="run-task-title">{run.task}</span><span className="run-id">{run.run_id}</span></div>, sortValue: (run) => run.task },
              { key: 'status', label: 'Status', render: (run) => <StatusBadge status={run.status as RunStatus} />, sortValue: (run) => run.status },
              { key: 'duration', label: 'Duration', render: (run) => formatDuration(run.duration_ms ?? run.total_duration_ms), sortValue: (run) => run.duration_ms ?? run.total_duration_ms ?? 0 },
              { key: 'tools', label: 'Tools used', render: (run) => run.tool_call_count ?? 0, sortValue: (run) => run.tool_call_count ?? 0 },
              { key: 'created', label: 'Created', render: (run) => formatDate(run.created_at), sortValue: (run) => run.created_at },
              { key: 'actions', label: '', className: 'table-actions-cell', render: (run) => <RunActions run={run} /> },
            ]}
          />
          <div className="pagination">
            <span>{data ? `${data.total ? offset + 1 : 0}–${Math.min(offset + rows.length, data.total)} of ${data.total}` : '—'}</span>
            <div><button className="button button-small button-secondary" disabled={offset === 0 || runs.isFetching} onClick={() => setOffset(Math.max(0, offset - pageSize))}>Previous</button><button className="button button-small button-secondary" disabled={!data || offset + pageSize >= data.total || runs.isFetching} onClick={() => setOffset(offset + pageSize)}>Next</button></div>
          </div>
        </div>
      )}
    </div>
  );
}
