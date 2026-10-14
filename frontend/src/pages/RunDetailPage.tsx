import { useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import {
  AlertTriangle,
  ArrowDownToLine,
  ArrowLeft,
  CheckCircle2,
  Circle,
  Clock3,
  FileJson,
  LoaderCircle,
  RotateCcw,
  ShieldCheck,
  XCircle,
} from 'lucide-react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { downloadUrl } from '../api/client';
import { useCancelRun, useReport, useRun, useRunLogs, useRetryRun, useToolCalls } from '../api/hooks';
import { useDocument } from '../api/hooks';
import { LogViewer } from '../components/LogViewer';
import { SideDrawer } from '../components/SideDrawer';
import { Button, Card, EmptyState, ErrorState, JsonViewer, Skeleton, StatusBadge, formatDate, formatDuration, notify } from '../components/ui';
import { useRunEvents } from '../hooks/useRunEvents';
import type { EvidenceReference, RunStatus, ValidationAttempt, ValidationCheck } from '../types/api';

const tabs = ['Overview', 'Plan', 'Tool Calls', 'Findings', 'Validation', 'Logs', 'Report'] as const;
type RunTab = typeof tabs[number];
const pipeline = ['Intake', 'Plan', 'Execute', 'Analyze', 'Validate', 'Report'];
const pipelineByStatus: Record<string, number> = {
  pending: 0,
  planning: 1,
  running: 2,
  analyzing: 3,
  validating: 4,
  reporting: 5,
};
const pipelineByNode: Record<string, number> = {
  intake: 0,
  planner: 1,
  select_tool: 2,
  execute_tool: 2,
  collect: 2,
  executor: 2,
  retry_or_fallback: 2,
  analyzer: 3,
  validator: 4,
  reporter: 5,
};
const activeStatuses = new Set(['pending', 'planning', 'running', 'analyzing', 'validating', 'reporting']);

function PipelineProgress({ status, currentNode, replans }: { status: string; currentNode?: string; replans: number }) {
  const completed = ['completed', 'completed_with_warnings'].includes(status);
  const pipelineIndex = completed ? pipeline.length - 1 : pipelineByStatus[status] ?? pipelineByNode[currentNode ?? ''] ?? 0;
  return (
    <div className="pipeline-card">
      <div className="pipeline-track">{pipeline.map((step, index) => {
        const isComplete = completed || index < pipelineIndex;
        const isCurrent = !completed && index === pipelineIndex;
        return (
          <div className={`pipeline-stage ${isComplete ? 'pipeline-complete' : ''} ${isCurrent ? 'pipeline-current' : ''}`} key={step}>
            <div className="pipeline-node">{isComplete ? <CheckCircle2 size={17} /> : isCurrent ? <LoaderCircle size={16} className="spin" /> : <Circle size={16} />}</div>
            <span>{step}</span>
            {index < pipeline.length - 1 && <i className={`pipeline-connector ${isComplete ? 'connector-complete' : ''}`} />}
          </div>
        );
      })}</div>
      {replans > 0 && <span className="replanned-marker"><RotateCcw size={13} /> Replanned {replans}×</span>}
    </div>
  );
}

function MarkdownReport({ markdown }: { markdown: string }) {
  const lines = markdown.split(/\r?\n/);
  const sections: Array<{ title: string; content: string[] }> = [];
  let current: { title: string; content: string[] } = { title: '', content: [] };
  for (const line of lines) {
    const heading = line.match(/^#{1,3}\s+(.+)$/);
    if (heading) {
      if (current.title || current.content.length) sections.push(current);
      current = { title: heading[1], content: [] };
    } else if (line.trim() || current.content.length) current.content.push(line);
  }
  if (current.title || current.content.length) sections.push(current);
  const headings = sections.filter((section) => section.title).map((section) => section.title);
  return (
    <div className="report-layout">
      {headings.length > 1 && <nav className="report-toc" aria-label="Report contents"><strong>On this page</strong>{headings.map((heading, index) => <a key={`${heading}-${index}`} href={`#report-section-${index}`}>{heading}</a>)}</nav>}
      <article className="markdown-content">
        {sections.map((section, index) => <section key={`${section.title}-${index}`} id={section.title ? `report-section-${headings.indexOf(section.title)}` : undefined}>
          {section.title && <h2>{section.title}</h2>}
          <MarkdownBlocks lines={section.content} />
        </section>)}
      </article>
    </div>
  );
}

function MarkdownBlocks({ lines }: { lines: string[] }) {
  const result: ReactNode[] = [];
  let list: string[] = [];
  let table: string[] = [];
  const flushList = () => {
    if (list.length) result.push(<ul key={`list-${result.length}`}>{list.map((item, index) => <li key={index}>{item}</li>)}</ul>);
    list = [];
  };
  const flushTable = () => {
    const rows = table
      .filter((line) => !/^\s*\|?[-: |]+\|?\s*$/.test(line))
      .map((line) => line.split('|').map((cell) => cell.trim()).filter((cell) => cell.length > 0));
    if (rows.length) result.push(<div key={`table-${result.length}`} className="markdown-table-wrap"><table><thead><tr>{rows[0].map((cell, index) => <th key={index}>{cell}</th>)}</tr></thead><tbody>{rows.slice(1).map((row, ri) => <tr key={ri}>{row.map((cell, ci) => <td key={ci}>{cell}</td>)}</tr>)}</tbody></table></div>);
    table = [];
  };
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    if (line.trim().startsWith('|')) { flushList(); table.push(line); continue; }
    flushTable();
    const listItem = line.match(/^\s*[-*]\s+(.+)$/);
    if (listItem) { list.push(listItem[1]); continue; }
    flushList();
    if (!line.trim()) continue;
    if (line.startsWith('```')) {
      const code: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].startsWith('```')) code.push(lines[index++]);
      result.push(<pre key={`code-${index}`}>{code.join('\n')}</pre>);
      continue;
    }
    result.push(<p key={`para-${index}`}>{line.replace(/\*\*(.*?)\*\*/g, '$1')}</p>);
  }
  flushTable();
  flushList();
  return <>{result}</>;
}

function EvidenceDetails({ reference, sourceOutput, onClose }: { reference: EvidenceReference; sourceOutput?: unknown; onClose: () => void }) {
  const sourceId = reference.source_id ?? reference.chunk_id ?? reference.tool_call_id ?? '';
  const documentId = reference.document_id;
  const document = useDocument(documentId);
  const [showSource, setShowSource] = useState(false);
  const citation = reference.citation ?? reference.reference ?? reference.evidence_id ?? 'Evidence reference';
  return (
    <SideDrawer title="Evidence source" onClose={onClose}>
      <div className="evidence-drawer-content">
        <span className="evidence-type">{reference.source_type ?? 'source'}</span>
        <h3>{citation}</h3>
        <div className="drawer-meta"><span>Evidence ID</span><code>{reference.evidence_id ?? '—'}</code></div>
        <div className="drawer-meta"><span>Source ID</span><code>{sourceId || '—'}</code></div>
        {document.isLoading && <Skeleton lines={3} />}
        {document.isError && <ErrorState error={document.error} retry={() => void document.refetch()} />}
        {document.data?.chunks?.length ? <div className="source-snippet"><strong>Document source</strong>{document.data.chunks.map((chunk) => <p key={chunk.id}>{chunk.content}</p>)}</div> : null}
        {!document.isLoading && !document.data?.chunks?.length && reference.citation && <div className="source-snippet"><strong>Provenance</strong><p>{reference.citation}</p></div>}
        <button className="button button-small button-secondary" onClick={() => setShowSource((value) => !value)}>{showSource ? 'Hide reference data' : 'Show reference data'}</button>
        {showSource && <pre className="evidence-json">{JSON.stringify(reference, null, 2)}</pre>}
        {sourceOutput !== undefined && <JsonViewer value={sourceOutput} label="Source tool output" />}
      </div>
    </SideDrawer>
  );
}

function EvidenceChips({ evidence, onSelect }: { evidence: EvidenceReference[]; onSelect: (value: EvidenceReference) => void }) {
  return <div className="evidence-chips">{evidence.map((item, index) => <button key={`${item.evidence_id ?? item.source_id ?? index}`} className="evidence-chip" onClick={() => onSelect(item)}><ShieldCheck size={12} />{item.citation ?? item.evidence_id ?? item.source_id ?? `Evidence ${index + 1}`}</button>)}</div>;
}

function PlanTab({ run }: { run: NonNullable<ReturnType<typeof useRun>['data']> }) {
  if (!run.plan.length) return <EmptyState title="Plan not available yet" description="The planner will populate execution steps as this run progresses." />;
  return (
    <div className="plan-list">
      {run.plan.map((step) => (
        <article key={step.id ?? step.step_index} className={`plan-step step-${step.status}`}>
          <div className="plan-step-icon"><FileJson size={17} /></div>
          <div className="plan-step-main">
            <div className="plan-step-title"><span>Step {step.step_index + 1}</span><StatusBadge status={step.status} /></div>
            <p>{step.description}</p>
            <div className="plan-step-meta">
              <span className="tool-name">{step.tool_name}</span>
              {step.retries ? <span className="retry-tag"><RotateCcw size={12} /> {step.retries} retries</span> : null}
              {step.depends_on?.map((dependency) => <span className="dependency-chip" key={dependency}>Depends on {dependency + 1}</span>)}
            </div>
            <JsonViewer value={step.tool_args ?? {}} label="Arguments" />
          </div>
        </article>
      ))}
    </div>
  );
}

function ToolCallsTab({ calls }: { calls: NonNullable<ReturnType<typeof useToolCalls>['data']> }) {
  if (!calls.length) return <EmptyState title="No tool calls yet" description="Tool calls will appear here as the executor gathers local evidence." />;
  return (
    <div className="tool-call-timeline">
      {calls.map((call, index) => (
        <details className={`tool-call-card tool-call-${call.status}`} key={call.id}>
          <summary>
            <span className="timeline-index">{index + 1}</span>
            <div className="tool-call-summary"><strong>{call.tool_name}</strong><span className="mono">{call.id}</span></div>
            <StatusBadge status={call.status} />
            {call.attempt > 1 && <span className="retry-tag"><RotateCcw size={12} /> Attempt {call.attempt}</span>}
            <span className="tool-call-duration">{formatDuration(call.duration_ms)}</span>
          </summary>
          <div className="tool-call-expanded">
            <JsonViewer value={call.input} label="Input" />
            <JsonViewer value={call.output} label="Output" />
            {call.error_message && <div className="call-error"><strong>{call.error_type ?? 'Tool error'}</strong><p>{call.error_message}</p></div>}
          </div>
        </details>
      ))}
    </div>
  );
}

function ValidationTab({ attempts }: { attempts: ValidationAttempt[] }) {
  if (!attempts.length) return <EmptyState title="Validation pending" description="Checks will appear here after the analyzer has prepared evidence-backed findings." />;
  return (
    <div className="validation-attempts">
      {attempts.map((attempt) => (
        <Card key={attempt.attempt} title={`Validation attempt ${attempt.attempt}`} action={<StatusBadge status={attempt.passed ? 'completed' : 'failed'} />}>
          <div className="validation-checks">{attempt.checks.map((check: ValidationCheck, index) => {
            const warning = check.warning || (check.name === 'source_agreement' && check.passed);
            const failed = !check.passed && !warning;
            const Icon = warning ? AlertTriangle : failed ? XCircle : CheckCircle2;
            return (
              <div className={`validation-check ${warning ? 'validation-warning' : failed ? 'validation-failed' : ''}`} key={`${check.name}-${index}`}>
                <Icon size={17} />
                <div><strong>{check.name.replace(/_/g, ' ')}</strong><p>{check.detail ?? (check.passed ? 'Check passed.' : 'Check failed.')}</p></div>
                <span>{warning ? 'Warning' : check.passed ? 'Pass' : 'Fail'}</span>
              </div>
            );
          })}</div>
        </Card>
      ))}
    </div>
  );
}

function ReportTab({ runId, report, isLoading, isError, error, refetch }: {
  runId: string; report?: ReturnType<typeof useReport>['data']; isLoading: boolean; isError: boolean; error: unknown; refetch: () => void;
}) {
  const markdown = report?.content_markdown ?? (typeof report?.content_json?.content_markdown === 'string' ? report.content_json.content_markdown : '');
  if (isLoading) return <div className="report-loading"><Skeleton lines={9} /></div>;
  if (isError) return <ErrorState error={error} retry={refetch} />;
  if (!markdown && !report) return <EmptyState title="Report is being prepared" description="The final report and downloads will be ready after validation completes." />;
  return (
    <div className="report-panel">
      <div className="report-downloads"><span>Download report</span>{(['pdf', 'md', 'json'] as const).map((format) => <a key={format} className="button button-small button-secondary" href={downloadUrl(runId, format)} target="_blank" rel="noreferrer"><ArrowDownToLine size={14} /> {format.toUpperCase()}</a>)}</div>
      {markdown ? <MarkdownReport markdown={markdown} /> : <pre className="evidence-json">{JSON.stringify(report?.content_json ?? report, null, 2)}</pre>}
      {report?.content_json && <AppendixVisuals content={report.content_json} />}
    </div>
  );
}

interface AppendixTableData {
  title: string;
  columns: string[];
  rows: unknown[][];
}

function AppendixVisuals({ content }: { content: Record<string, unknown> }) {
  const source = content.appendix_tables;
  if (!Array.isArray(source)) return null;
  const tables = source.flatMap((value): AppendixTableData[] => {
    if (typeof value !== 'object' || value === null) return [];
    const item = value as { title?: unknown; columns?: unknown; rows?: unknown };
    if (!Array.isArray(item.columns) || !item.columns.every((column) => typeof column === 'string') || !Array.isArray(item.rows)) return [];
    return [{
      title: typeof item.title === 'string' ? item.title : 'Appendix data',
      columns: item.columns,
      rows: item.rows.filter((row): row is unknown[] => Array.isArray(row)),
    }];
  });
  if (!tables.length) return null;
  return <section className="appendix-visuals"><h2>Appendix tables</h2>{tables.map((table, index) => <AppendixTable key={`${table.title}-${index}`} table={table} />)}</section>;
}

function AppendixTable({ table }: { table: AppendixTableData }) {
  const data = table.rows.map((row) => Object.fromEntries(table.columns.map((column, index) => [column, row[index] ?? ''])));
  const numericColumn = table.columns.find((column) => data.length > 0 && data.every((row) => {
    const value = row[column];
    return value !== '' && value !== null && Number.isFinite(Number(value));
  }));
  const categoryColumn = table.columns.find((column) => column !== numericColumn);
  return (
    <div className="appendix-table-card">
      <h3>{table.title}</h3>
      {numericColumn && categoryColumn && data.length > 1 && <div className="appendix-chart"><ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 5, right: 10, left: -15, bottom: 0 }}>
          <CartesianGrid stroke="var(--border-subtle)" vertical={false} />
          <XAxis dataKey={categoryColumn} tickLine={false} axisLine={false} />
          <YAxis tickLine={false} axisLine={false} />
          <Tooltip contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-primary)' }} />
          <Bar dataKey={numericColumn} fill="#6068dd" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer></div>}
      <div className="markdown-table-wrap"><table><thead><tr>{table.columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{table.rows.map((row, ri) => <tr key={ri}>{table.columns.map((_, ci) => <td key={ci}>{String(row[ci] ?? '—')}</td>)}</tr>)}</tbody></table></div>
    </div>
  );
}

export function RunDetailPage() {
  const { runId = '' } = useParams();
  const navigate = useNavigate();
  const [tab, setTab] = useState<RunTab>('Overview');
  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceReference>();
  const run = useRun(runId);
  const current = run.data;
  const events = useRunEvents(runId, !current || activeStatuses.has(current.status));
  const logs = useRunLogs(runId, tab === 'Logs' || tab === 'Overview');
  const calls = useToolCalls(runId);
  const report = useReport(runId, tab === 'Report' || run.data?.status === 'completed' || run.data?.status === 'completed_with_warnings');
  const cancel = useCancelRun(runId);
  const retry = useRetryRun(runId);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!current?.started_at || current.finished_at || !activeStatuses.has(current.status)) return;
    const started = new Date(current.started_at).getTime();
    const update = () => setElapsed(Math.max(0, Date.now() - started));
    update();
    const timer = window.setInterval(update, 1000);
    return () => window.clearInterval(timer);
  }, [current?.finished_at, current?.started_at, current?.status]);

  const duration = useMemo(() => current?.total_duration_ms ?? current?.duration_ms ?? elapsed, [current?.duration_ms, current?.total_duration_ms, elapsed]);
  const canCancel = current ? activeStatuses.has(current.status) : false;
  const doCancel = async () => {
    if (!window.confirm('Cancel this research run?')) return;
    try { await cancel.mutateAsync(); notify('Cancellation requested.'); }
    catch (error) { notify(error instanceof Error ? error.message : 'Unable to cancel run.', 'error'); }
  };
  const doRetry = async () => {
    try { const result = await retry.mutateAsync(); notify('Retry run created.'); navigate(`/runs/${result.run_id}`); }
    catch (error) { notify(error instanceof Error ? error.message : 'Unable to retry run.', 'error'); }
  };
  const validations = current?.validation_results ?? [];
  const latestValidation = validations[validations.length - 1];

  if (run.isLoading) return <div className="page-stack"><Skeleton lines={9} /></div>;
  if (run.isError || !current) return <div className="page-stack"><ErrorState error={run.error ?? new Error('Run not found.')} retry={() => void run.refetch()} /><Link to="/runs" className="text-link"><ArrowLeft size={14} /> Back to runs</Link></div>;

  return (
    <div className="page-stack run-detail-page">
      <div className="run-detail-heading">
        <div><Link to="/runs" className="back-link"><ArrowLeft size={14} /> All runs</Link><h1>{current.task}</h1><div className="run-subtitle"><StatusBadge status={current.status as RunStatus} /><code>{current.run_id}</code><span><Clock3 size={14} /> {formatDuration(duration)}</span><span>Started {formatDate(current.created_at)}</span></div></div>
        <div className="run-heading-actions">{canCancel && <Button variant="secondary" disabled={cancel.isPending} onClick={() => void doCancel()}><XCircle size={15} /> Cancel</Button>}{!canCancel && <Button variant="secondary" disabled={retry.isPending} onClick={() => void doRetry()}><RotateCcw size={15} /> Retry</Button>}{current.report && <a className="button button-secondary" href={downloadUrl(runId, 'pdf')} target="_blank" rel="noreferrer"><ArrowDownToLine size={15} /> Download</a>}</div>
      </div>
      {current.error && <div className="call-error run-error"><strong>Run failed</strong><p>{current.error}</p></div>}
      <PipelineProgress status={activeStatuses.has(current.status) ? events.status ?? current.status : current.status} currentNode={events.currentNode} replans={current.replan_count ?? current.summary?.replan_count ?? 0} />
      <div className="run-tabbar" role="tablist" aria-label="Run details sections">{tabs.map((item) => <button key={item} role="tab" aria-selected={tab === item} className={`run-tab ${tab === item ? 'run-tab-active' : ''}`} onClick={() => setTab(item)}>{item}{item === 'Logs' && logs.data?.length ? <span className="tab-count">{logs.data.length}</span> : null}</button>)}</div>
      <div className="run-tab-content">
        {tab === 'Overview' && <div className="overview-grid">
          <div className="overview-main"><Card title="Run summary"><p className="overview-task">{current.task}</p><div className="summary-metrics"><div><span>Tool calls</span><strong>{current.tool_call_count ?? current.summary?.tool_call_count ?? calls.data?.length ?? '—'}</strong></div><div><span>Retries</span><strong>{current.retry_count ?? current.summary?.retry_count ?? '—'}</strong></div><div><span>Replans</span><strong>{current.replan_count ?? current.summary?.replan_count ?? 0}</strong></div><div><span>Validation</span><strong>{latestValidation ? latestValidation.passed ? 'Passed' : 'Needs review' : 'Pending'}</strong></div></div></Card>
            <Card title="Key findings">{current.findings.length ? <div className="finding-list">{current.findings.slice(0, 3).map((finding, index) => <article className="finding-card" key={finding.id ?? index}><p>{finding.statement}</p><div className="finding-footer"><span className="confidence-label">Confidence <strong>{Math.round(finding.confidence * 100)}%</strong></span><div className="confidence-track"><i style={{ width: `${Math.max(0, Math.min(100, finding.confidence * 100))}%` }} /></div><EvidenceChips evidence={finding.evidence} onSelect={setSelectedEvidence} /></div></article>)}</div> : <EmptyState title="Findings in progress" description="Evidence-backed findings will appear as the analyzer completes." />}</Card>
          </div>
          <div className="overview-side"><Card title="Latest validation">{latestValidation ? <div className="mini-check-list">{latestValidation.checks.slice(0, 5).map((check: ValidationCheck, index: number) => <div key={`${check.name}-${index}`} className={check.passed ? '' : 'mini-check-fail'}>{check.passed ? <CheckCircle2 size={15} /> : <XCircle size={15} />}<span>{check.name.replace(/_/g, ' ')}</span></div>)}</div> : <p className="muted-copy">Validation results will show here.</p>}</Card><Card title="Recent execution logs" action={<button className="text-link" onClick={() => setTab('Logs')}>View all</button>}>{logs.isLoading ? <Skeleton lines={4} /> : logs.isError ? <ErrorState error={logs.error} retry={() => void logs.refetch()} /> : logs.data?.length ? <div className="mini-logs">{logs.data.slice(-5).reverse().map((log) => <div key={log.id}><span className={`log-level level-${log.level.toLowerCase()}`}>{log.level}</span><p><strong>{log.event}</strong><small>{log.message}</small></p></div>)}</div> : <p className="muted-copy">No log events yet.</p>}</Card></div>
        </div>}
        {tab === 'Plan' && <PlanTab run={current} />}
        {tab === 'Tool Calls' && (calls.isLoading ? <Skeleton lines={6} /> : calls.isError ? <ErrorState error={calls.error} retry={() => void calls.refetch()} /> : <ToolCallsTab calls={calls.data ?? []} />)}
        {tab === 'Findings' && (current.findings.length ? <div className="finding-list findings-tab">{current.findings.map((finding, index) => <Card key={finding.id ?? index}><div className="finding-header"><h3>{finding.statement}</h3><span className="confidence-pill">{Math.round(finding.confidence * 100)}% confidence</span></div><div className="confidence-track"><i style={{ width: `${Math.max(0, Math.min(100, finding.confidence * 100))}%` }} /></div><EvidenceChips evidence={finding.evidence} onSelect={setSelectedEvidence} /></Card>)}</div> : <EmptyState title="No findings yet" description="Analysis findings will be shown here with evidence links." />)}
        {tab === 'Validation' && <ValidationTab attempts={current.validation_results ?? []} />}
        {tab === 'Logs' && (logs.isLoading ? <Skeleton lines={6} /> : logs.isError ? <ErrorState error={logs.error} retry={() => void logs.refetch()} /> : <Card className="logs-card"><LogViewer logs={logs.data ?? []} live={activeStatuses.has(current.status)} /></Card>)}
        {tab === 'Report' && <Card><ReportTab runId={runId} report={report.data} isLoading={report.isLoading} isError={report.isError} error={report.error} refetch={() => void report.refetch()} /></Card>}
      </div>
      {selectedEvidence && <EvidenceDetails
        reference={selectedEvidence}
        sourceOutput={calls.data?.find((call) => {
          const citedCallId = selectedEvidence.tool_call_id ?? selectedEvidence.evidence_id?.replace(/^tc:/, '');
          return Boolean(citedCallId && call.id === citedCallId);
        })?.output}
        onClose={() => setSelectedEvidence(undefined)}
      />}
    </div>
  );
}
