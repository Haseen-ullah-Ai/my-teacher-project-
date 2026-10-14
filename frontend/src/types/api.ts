export type RunStatus =
  | 'pending'
  | 'planning'
  | 'running'
  | 'analyzing'
  | 'validating'
  | 'reporting'
  | 'completed'
  | 'completed_with_warnings'
  | 'failed'
  | 'cancelled';

export type CheckState = 'pass' | 'fail' | 'warn';

export interface RunMetrics {
  total_duration_ms?: number | null;
  tool_call_count?: number;
  retry_count?: number;
  failure_count?: number;
  token_count?: number;
  replan_count?: number;
}

export interface RunItem extends RunMetrics {
  run_id: string;
  task: string;
  status: RunStatus;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  duration_ms?: number | null;
}

export interface PlanStep {
  id?: string;
  step_index: number;
  description: string;
  tool_name: string;
  tool_args?: Record<string, unknown>;
  status: 'pending' | 'running' | 'succeeded' | 'failed' | 'skipped';
  retries?: number;
  depends_on?: number[] | null;
}

export interface EvidenceReference {
  evidence_id?: string;
  source_type?: string;
  source_id?: string;
  citation?: string;
  reference?: string;
  chunk_id?: string;
  document_id?: string;
  tool_call_id?: string;
}

export interface Finding {
  id?: string;
  statement: string;
  confidence: number;
  evidence: EvidenceReference[];
}

export interface ValidationCheck {
  name: string;
  passed: boolean;
  detail?: string;
  warning?: boolean;
}

export interface ValidationAttempt {
  attempt: number;
  passed: boolean;
  checks: ValidationCheck[];
  created_at?: string;
}

export interface ToolCall {
  id: string;
  tool_name: string;
  status: string;
  input?: Record<string, unknown> | null;
  output?: unknown;
  error_type?: string | null;
  error_message?: string | null;
  attempt: number;
  duration_ms?: number | null;
  started_at?: string;
  step_id?: string | null;
  step_index?: number | null;
}

export interface ExecutionLog {
  id: number;
  run_id?: string;
  node: string;
  level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | string;
  event: string;
  message: string;
  data?: Record<string, unknown>;
  created_at: string;
}

export interface ReportDocument {
  id?: string;
  title: string;
  summary?: string;
  content_json?: Record<string, unknown>;
  content_markdown?: string;
  file_paths?: string[] | Record<string, string>;
  created_at?: string;
}

export interface RunDetail extends RunItem {
  plan: PlanStep[];
  findings: Finding[];
  validation_results: ValidationAttempt[];
  summary?: RunMetrics;
  final_report_id?: string | null;
  error?: string | null;
  report?: ReportDocument | null;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface OverviewStats {
  total_runs: number;
  success_rate: number;
  average_duration_ms: number;
  total_tool_calls: number;
  runs_by_status: Record<string, number>;
  runs_by_day: Array<{ date: string; count: number }>;
  tool_usage: Array<{ tool_name: string; count: number; failures?: number }>;
  recent_runs: RunItem[];
  failures_by_tool?: Array<{ tool_name: string; count: number }>;
}

export interface DocumentItem {
  id: string;
  filename: string;
  title: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
  chunk_count?: number;
}

export interface DocumentPreview extends DocumentItem {
  chunks: Array<{ id: string; chunk_index: number; content: string }>;
}

export interface DatasetItem {
  id: string;
  filename: string;
  checksum?: string;
  row_count: number;
  columns: Array<{ name: string; dtype: string }>;
  created_at: string;
}

export interface DatasetPreview extends DatasetItem {
  rows: Array<Record<string, unknown>>;
}

export interface ToolDescription {
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
  output_schema?: Record<string, unknown>;
  timeout_seconds?: number;
}

export interface RunEvent {
  id?: string | number;
  type?: string;
  event?: string;
  node?: string;
  status?: string;
  message?: string;
  created_at?: string;
  data?: Record<string, unknown>;
  [key: string]: unknown;
}
