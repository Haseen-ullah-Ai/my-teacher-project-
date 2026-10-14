import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';

export const queryKeys = {
  health: ['health'] as const,
  overview: ['overview'] as const,
  runs: ['runs'] as const,
  run: (id: string) => ['run', id] as const,
  logs: (id: string) => ['logs', id] as const,
  calls: (id: string) => ['tool-calls', id] as const,
  report: (id: string) => ['report', id] as const,
  documents: ['documents'] as const,
  document: (id: string) => ['document', id] as const,
  datasets: ['datasets'] as const,
  dataset: (id: string) => ['dataset', id] as const,
  tools: ['tools'] as const,
};

export function useHealth() {
  return useQuery({ queryKey: queryKeys.health, queryFn: api.health, refetchInterval: 30_000, retry: 1 });
}

export function useOverview() {
  return useQuery({ queryKey: queryKeys.overview, queryFn: api.overview, refetchInterval: 60_000 });
}

export function useRuns(params: { status?: string; q?: string; limit?: number; offset?: number }) {
  return useQuery({ queryKey: [...queryKeys.runs, params], queryFn: () => api.runs(params), placeholderData: (previous) => previous });
}

export function useRun(id: string) {
  return useQuery({
    queryKey: queryKeys.run(id),
    queryFn: () => api.run(id),
    enabled: Boolean(id),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && ['completed', 'completed_with_warnings', 'failed', 'cancelled'].includes(status) ? false : 3_000;
    },
  });
}

export function useRunLogs(id: string, enabled = true) {
  return useQuery({ queryKey: queryKeys.logs(id), queryFn: () => api.logs(id), enabled: Boolean(id) && enabled, refetchInterval: 5_000 });
}

export function useToolCalls(id: string) {
  return useQuery({ queryKey: queryKeys.calls(id), queryFn: () => api.toolCalls(id), enabled: Boolean(id), refetchInterval: 3_000 });
}

export function useReport(id: string, enabled = true) {
  return useQuery({ queryKey: queryKeys.report(id), queryFn: () => api.report(id), enabled: Boolean(id) && enabled });
}

export function useDocuments() {
  return useQuery({ queryKey: queryKeys.documents, queryFn: api.documents });
}

export function useDocument(id: string | undefined) {
  return useQuery({ queryKey: queryKeys.document(id ?? ''), queryFn: () => api.document(id ?? ''), enabled: Boolean(id) });
}

export function useDatasets() {
  return useQuery({ queryKey: queryKeys.datasets, queryFn: api.datasets });
}

export function useDataset(id: string | undefined) {
  return useQuery({ queryKey: queryKeys.dataset(id ?? ''), queryFn: () => api.dataset(id ?? ''), enabled: Boolean(id) });
}

export function useTools() {
  return useQuery({ queryKey: queryKeys.tools, queryFn: api.tools });
}

export function useCreateRun() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { task: string; max_retries: number; max_replans: number; dataset_ids: string[]; document_ids: string[] }) =>
      api.createRun(input.task, input),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: queryKeys.runs });
      void client.invalidateQueries({ queryKey: queryKeys.overview });
    },
  });
}

export function useCancelRun(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api.cancelRun(id),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: queryKeys.run(id) });
      await client.invalidateQueries({ queryKey: queryKeys.runs });
    },
  });
}

export function useRetryRun(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api.retryRun(id),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: queryKeys.runs });
      void client.invalidateQueries({ queryKey: queryKeys.overview });
    },
  });
}

export function useDeleteDocument() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.deleteDocument,
    onSuccess: () => void client.invalidateQueries({ queryKey: queryKeys.documents }),
  });
}

export function useDeleteDataset() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.deleteDataset,
    onSuccess: () => void client.invalidateQueries({ queryKey: queryKeys.datasets }),
  });
}
