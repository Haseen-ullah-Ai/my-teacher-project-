import { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowDown, Search } from 'lucide-react';
import type { ExecutionLog } from '../types/api';

const levels = ['ALL', 'INFO', 'WARNING', 'ERROR', 'DEBUG'];

export function LogViewer({ logs, live = false }: { logs: ExecutionLog[]; live?: boolean }) {
  const [level, setLevel] = useState('ALL');
  const [node, setNode] = useState('ALL');
  const [query, setQuery] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  const rowsRef = useRef<HTMLDivElement>(null);
  const filtered = useMemo(() => logs.filter((log) => {
    const text = `${log.event} ${log.message} ${JSON.stringify(log.data ?? {})}`.toLowerCase();
    return (level === 'ALL' || log.level.toUpperCase() === level)
      && (node === 'ALL' || log.node === node)
      && text.includes(query.toLowerCase());
  }).slice(-500), [level, logs, node, query]);
  const nodes = ['ALL', ...Array.from(new Set(logs.map((log) => log.node)))];

  useEffect(() => {
    if (autoScroll && rowsRef.current) rowsRef.current.scrollTop = rowsRef.current.scrollHeight;
  }, [autoScroll, filtered]);

  return (
    <div className="log-viewer">
      <div className="log-toolbar">
        <div className="filter-chips" aria-label="Filter logs by level">{levels.map((item) => <button key={item} className={`filter-chip ${level === item ? 'filter-chip-active' : ''}`} onClick={() => setLevel(item)}>{item}</button>)}</div>
        <label className="log-search"><Search size={14} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search logs" aria-label="Search logs" /></label>
        <select value={node} onChange={(event) => setNode(event.target.value)} aria-label="Filter logs by node">{nodes.map((item) => <option key={item} value={item}>{item === 'ALL' ? 'All nodes' : item}</option>)}</select>
        <button className={`button button-small ${autoScroll ? 'button-secondary' : 'button-ghost'}`} onClick={() => setAutoScroll((value) => !value)}><ArrowDown size={13} />{autoScroll ? 'Live tail on' : 'Live tail off'}</button>
        {live && <span className="live-indicator"><i /> Live</span>}
      </div>
      <div ref={rowsRef} className="log-rows" role="log" aria-live="polite" aria-label="Execution logs" data-autoscroll={autoScroll}>
        {filtered.map((log) => <div key={log.id} className="log-row">
          <time>{new Date(log.created_at).toLocaleTimeString()}</time>
          <span className={`log-level level-${log.level.toLowerCase()}`}>{log.level}</span>
          <span className="log-node">{log.node}</span>
          <span className="log-message"><strong>{log.event}</strong> {log.message}</span>
        </div>)}
        {!filtered.length && <div className="log-empty">No log entries match these filters.</div>}
      </div>
    </div>
  );
}
