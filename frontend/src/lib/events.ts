import type { RunEvent } from '../types/api';

export interface RunEventState {
  events: RunEvent[];
  lastEventId?: string;
  status?: string;
  currentNode?: string;
}

export type RunEventAction =
  | { type: 'received'; event: RunEvent }
  | { type: 'reset' };

export function runEventReducer(state: RunEventState, action: RunEventAction): RunEventState {
  if (action.type === 'reset') return { events: [] };
  const event = action.event;
  const status = typeof event.status === 'string' ? event.status : state.status;
  const currentNode = typeof event.node === 'string' ? event.node : state.currentNode;
  const lastEventId = event.id === undefined ? state.lastEventId : String(event.id);
  return {
    events: [...state.events, event].slice(-500),
    lastEventId,
    status,
    currentNode,
  };
}
