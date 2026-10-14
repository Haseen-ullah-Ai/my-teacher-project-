import type {
  DatasetItem,
  DatasetPreview,
  DocumentItem,
  DocumentPreview,
  ExecutionLog,
  OverviewStats,
  Paginated,
  ReportDocument,
  RunDetail,
  RunEvent,
  RunItem,
  ToolCall,
  ToolDescription,
} from '../types/api';

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/$/, '');
const API = `${API_BASE_URL}/api/v1`;

export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API}${path}`, {
      ...init,
      headers: { Accept: 'application/json', ...init?.headers },
    });
  } catch (error) {
    throw new ApiError(error instanceof Error ? error.message : 'Unable to reach ResearchPilot API', 0);
  }
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    let code: string | undefined;
    try {
      const body = (await response.json()) as { detail?: string; error?: { message?: string; code?: string } };
      message = body.error?.message ?? body.detail ?? message;
      code = body.error?.code;
    } catch {
      // The server may return an empty body for an error response.
    }
    throw new ApiError(message, response.status, code);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function upload<T>(path: string, file: File, onProgress?: (progress: number) => void): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${API}${path}`);
    xhr.responseType = 'json';
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress?.(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onerror = () => reject(new ApiError('Upload failed. Check your connection and retry.', 0));
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve(xhr.response as T);
      else {
        const body = xhr.response as { detail?: string; error?: { message?: string; code?: string } } | null;
        reject(new ApiError(body?.error?.message ?? body?.detail ?? `Upload failed (${xhr.status})`, xhr.status, body?.error?.code));
      }
    };
    const form = new FormData();
    form.append('file', file);
    xhr.send(form);
  });
}

export const api = {
  health: () => requestAt<{ status: string; version?: string; db?: string }>(`${API_BASE_URL}/health`),
  overview: () => request<OverviewStats>('/stats/overview'),
  runs: (params: { status?: string; q?: string; limit?: number; offset?: number } = {}) => {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== '') query.set(key, String(value));
    });
    return request<Paginated<RunItem>>(`/runs${query.size ? `?${query}` : ''}`);
  },
  createRun: (task: string, options?: { max_retries?: number; max_replans?: number; dataset_ids?: string[]; document_ids?: string[] }) =>
    request<{ run_id: string }>('/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task, ...options }),
    }),
  run: (id: string) => request<RunDetail>(`/runs/${encodeURIComponent(id)}`),
  logs: (id: string, params: { level?: string; node?: string; after_id?: number } = {}) => {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== '') query.set(key, String(value));
    });
    return request<ExecutionLog[]>(`/runs/${encodeURIComponent(id)}/logs${query.size ? `?${query}` : ''}`);
  },
  toolCalls: (id: string) => request<ToolCall[]>(`/runs/${encodeURIComponent(id)}/tool-calls`),
  report: (id: string) => request<ReportDocument>(`/runs/${encodeURIComponent(id)}/report`),
  cancelRun: (id: string) => request<void>(`/runs/${encodeURIComponent(id)}/cancel`, { method: 'POST' }),
  retryRun: (id: string) => request<{ run_id: string }>(`/runs/${encodeURIComponent(id)}/retry`, { method: 'POST' }),
  documents: () => request<DocumentItem[]>('/documents'),
  uploadDocument: (file: File, onProgress?: (progress: number) => void) => upload<DocumentItem>('/documents', file, onProgress),
  document: (id: string) => request<DocumentPreview>(`/documents/${encodeURIComponent(id)}`),
  deleteDocument: (id: string) => request<void>(`/documents/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  datasets: () => request<DatasetItem[]>('/datasets'),
  uploadDataset: (file: File, onProgress?: (progress: number) => void) => upload<DatasetItem>('/datasets', file, onProgress),
  dataset: (id: string) => request<DatasetPreview>(`/datasets/${encodeURIComponent(id)}/preview`),
  deleteDataset: (id: string) => request<void>(`/datasets/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  tools: () => request<ToolDescription[]>('/tools'),
  eventsUrl: (id: string) => `${API}/runs/${encodeURIComponent(id)}/events`,
};

async function requestAt<T>(url: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, { headers: { Accept: 'application/json' } });
  } catch (error) {
    throw new ApiError(error instanceof Error ? error.message : 'Unable to reach ResearchPilot API', 0);
  }
  if (!response.ok) throw new ApiError(`Health check failed (${response.status})`, response.status);
  return (await response.json()) as T;
}

export function downloadUrl(runId: string, format: 'pdf' | 'md' | 'json'): string {
  return `${API}/runs/${encodeURIComponent(runId)}/report/download?format=${format}`;
}

export function eventStreamUrl(runId: string): string {
  return api.eventsUrl(runId);
}

export async function readRunEventStream(
  url: string,
  signal: AbortSignal,
  lastEventId?: string,
  onEvent?: (event: RunEvent) => void,
): Promise<string | undefined> {
  const headers = new Headers({ Accept: 'text/event-stream' });
  if (lastEventId) headers.set('Last-Event-ID', lastEventId);
  const response = await fetch(url, { headers, signal });
  if (!response.ok || !response.body) throw new ApiError(`Event stream failed (${response.status})`, response.status);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let currentId = lastEventId;
  const dispatch = (block: string) => {
    let id: string | undefined;
    let name = '';
    const dataLines: string[] = [];
    for (const line of block.split(/\r?\n/)) {
      if (line.startsWith('id:')) id = line.slice(3).trim();
      else if (line.startsWith('event:')) name = line.slice(6).trim();
      else if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart());
    }
    if (!dataLines.length) return;
    currentId = id ?? currentId;
    const payload = dataLines.join('\n');
    try {
      const parsed = JSON.parse(payload) as RunEvent;
      onEvent?.({ ...parsed, id: parsed.id ?? id, type: parsed.type ?? name });
    } catch {
      onEvent?.({ id, type: name, message: payload });
    }
  };
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const blocks = buffer.split(/\r?\n\r?\n/);
    buffer = blocks.pop() ?? '';
    blocks.forEach(dispatch);
    if (done) break;
  }
  return currentId;
}
