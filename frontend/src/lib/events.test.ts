import { describe, expect, it } from 'vitest';
import { runEventReducer } from './events';
import type { RunEventState } from './events';

describe('runEventReducer', () => {
  it('tracks status, node, and Last-Event-ID from a stream event', () => {
    const state = runEventReducer({ events: [] }, { type: 'received', event: { id: '9', status: 'running', node: 'executor' } });
    expect(state).toMatchObject({ lastEventId: '9', status: 'running', currentNode: 'executor' });
    expect(state.events).toHaveLength(1);
  });

  it('keeps the most recent 500 events and supports reset', () => {
    let state: RunEventState = { events: [] };
    for (let id = 0; id < 520; id += 1) {
      state = runEventReducer(state, { type: 'received', event: { id } });
    }
    expect(state.events).toHaveLength(500);
    expect(state.events[0].id).toBe(20);
    expect(state.events[499].id).toBe(519);
    expect(runEventReducer(state, { type: 'reset' })).toEqual({ events: [] });
  });
});
