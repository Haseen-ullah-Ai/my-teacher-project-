import { useEffect, useState } from 'react';
import {
  AlertCircle,
  Check,
  ChevronDown,
  ChevronRight,
  Copy,
  LoaderCircle,
  RefreshCw,
  X,
} from 'lucide-react';
import type { ReactNode } from 'react';
import type { RunStatus } from '../types/api';

const statusLabels: Record<string, string> = {
  completed_with_warnings: 'Warnings',
  running: 'Running',
  pending: 'Queued',
};

export function StatusBadge({ status }: { status: RunStatus | string }) {
  return (
    <span className={`status-badge status-${status.replace(/_/g, '-')}`}>
      {status === 'running' && <span className="status-pulse" />}
      {statusLabels[status] ?? status.replace(/_/g, ' ')}
    </span>
  );
}

export function StatCard({ label, value, detail, icon, tone = 'indigo' }: {
  label: string;
  value: string | number;
  detail?: string;
  icon: ReactNode;
  tone?: 'indigo' | 'green' | 'amber' | 'blue';
}) {
  return (
    <article className="stat-card">
      <div className={`stat-icon stat-${tone}`}>{icon}</div>
      <div className="stat-copy">
        <span className="muted-label">{label}</span>
        <strong>{value}</strong>
        {detail && <small>{detail}</small>}
      </div>
    </article>
  );
}

export function Card({ children, className = '', title, action }: {
  children: ReactNode;
  className?: string;
  title?: string;
  action?: ReactNode;
}) {
  return (
    <section className={`card ${className}`}>
      {(title || action) && <header className="card-header">{title && <h2>{title}</h2>}{action}</header>}
      {children}
    </section>
  );
}

export function PageHeader({ title, description, actions }: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="page-header">
      <div><h1>{title}</h1>{description && <p>{description}</p>}</div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  );
}

export function EmptyState({ title, description, action, icon }: {
  title: string;
  description: string;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon">{icon ?? <AlertCircle size={22} />}</div>
      <strong>{title}</strong><p>{description}</p>{action}
    </div>
  );
}

export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  const message = error instanceof Error ? error.message : 'Something went wrong.';
  return (
    <div className="error-state" role="alert">
      <AlertCircle size={18} />
      <span>{message}</span>
      {retry && <button className="button button-small button-secondary" onClick={retry}><RefreshCw size={14} /> Retry</button>}
    </div>
  );
}

export function Skeleton({ lines = 3, className = '' }: { lines?: number; className?: string }) {
  return (
    <div className={`skeleton-stack ${className}`} aria-label="Loading">
      {Array.from({ length: lines }, (_, index) => <span key={index} className="skeleton-line" />)}
    </div>
  );
}

export function Button({ children, className = '', variant = 'primary', ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
}) {
  return <button className={`button button-${variant} ${className}`} {...props}>{children}</button>;
}

export function JsonViewer({ value, label }: { value: unknown; label?: string }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const text = JSON.stringify(value ?? {}, null, 2);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1400);
    } catch {
      notify('Clipboard access is unavailable in this browser.', 'error');
    }
  };
  return (
    <div className="json-viewer">
      <button className="json-toggle" onClick={() => setOpen((value) => !value)} aria-expanded={open}>
        {open ? <ChevronDown size={15} /> : <ChevronRight size={15} />}<span>{label ?? 'JSON'}</span>
      </button>
      {open && <div className="json-content"><button className="icon-button copy-button" onClick={() => void copy()} aria-label="Copy JSON">{copied ? <Check size={14} /> : <Copy size={14} />}</button><pre>{text}</pre></div>}
    </div>
  );
}

export function LoadingSpinner({ label = 'Loading' }: { label?: string }) {
  return <span className="spinner-wrap"><LoaderCircle className="spin" size={16} />{label}</span>;
}

export function ToastViewport() {
  const [items, setItems] = useState<Array<{ id: number; message: string; kind: string }>>([]);
  useEffect(() => {
    const listener = (event: Event) => {
      const detail = (event as CustomEvent<{ message: string; kind?: string }>).detail;
      const id = Date.now() + Math.random();
      setItems((current) => [...current, { id, message: detail.message, kind: detail.kind ?? 'success' }]);
      window.setTimeout(() => setItems((current) => current.filter((item) => item.id !== id)), 3600);
    };
    window.addEventListener('rp-toast', listener);
    return () => window.removeEventListener('rp-toast', listener);
  }, []);
  return (
    <div className="toast-viewport" aria-live="polite">
      {items.map((item) => <div key={item.id} className={`toast toast-${item.kind}`}><span>{item.message}</span><button aria-label="Dismiss notification" onClick={() => setItems((current) => current.filter((toast) => toast.id !== item.id))}><X size={14} /></button></div>)}
    </div>
  );
}

export function notify(message: string, kind: 'success' | 'error' | 'info' = 'success') {
  window.dispatchEvent(new CustomEvent('rp-toast', { detail: { message, kind } }));
}

export function formatDuration(ms?: number | null): string {
  if (ms === undefined || ms === null || !Number.isFinite(ms)) return '—';
  if (ms < 1_000) return `${ms} ms`;
  const seconds = Math.floor(ms / 1_000);
  return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

export function formatDate(value?: string): string {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date);
}
