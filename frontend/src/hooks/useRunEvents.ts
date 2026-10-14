import { useEffect, useReducer, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { api, readRunEventStream } from '../api/client';
import { queryKeys } from '../api/hooks';
import { runEventReducer } from '../lib/events';

const terminalStates = new Set(['completed', 'completed_with_warnings', 'failed', 'cancelled']);

export function useRunEvents(runId: string, enabled = true) {
  const [state, dispatch] = useReducer(runEventReducer, { events: [] });
  const queryClient = useQueryClient();
  const lastEventId = useRef<string>();

  useEffect(() => {
    lastEventId.current = undefined;
    dispatch({ type: 'reset' });
  }, [runId]);

  useEffect(() => {
    if (!runId || !enabled) return;
    let stopped = false;
    let retryDelay = 500;
    let activeController: AbortController | undefined;

    const connect = async () => {
      while (!stopped) {
        activeController = new AbortController();
        try {
          const id = await readRunEventStream(
            api.eventsUrl(runId),
            activeController.signal,
            lastEventId.current,
            (event) => {
              if (event.id !== undefined) lastEventId.current = String(event.id);
              dispatch({ type: 'received', event });
              void queryClient.invalidateQueries({ queryKey: queryKeys.run(runId) });
              void queryClient.invalidateQueries({ queryKey: queryKeys.logs(runId) });
              void queryClient.invalidateQueries({ queryKey: queryKeys.calls(runId) });
              if (typeof event.status === 'string' && terminalStates.has(event.status)) stopped = true;
            },
          );
          if (id) lastEventId.current = id;
          retryDelay = 500;
          if (!stopped) await new Promise((resolve) => window.setTimeout(resolve, retryDelay));
        } catch {
          if (stopped || activeController.signal.aborted) return;
          await new Promise((resolve) => window.setTimeout(resolve, retryDelay));
          retryDelay = Math.min(retryDelay * 2, 10_000);
        }
      }
    };
    void connect();
    return () => {
      stopped = true;
      activeController?.abort();
    };
  }, [enabled, queryClient, runId]);

  return state;
}
