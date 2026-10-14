import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { NewResearchPage, validateResearchTask } from './NewResearchPage';

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="current-path">{location.pathname}</output>;
}

function renderResearchForm() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/runs/new']}>
        <Routes>
          <Route path="/runs/new" element={<NewResearchPage />} />
          <Route path="/runs/:runId" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('New research task validation', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('requires 10-4,000 non-whitespace characters', () => {
    expect(validateResearchTask('   ')).toMatch(/at least 10/);
    expect(validateResearchTask('Analyze sales')).toBeUndefined();
    expect(validateResearchTask('a'.repeat(4001))).toMatch(/4,000/);
  });

  it('keeps submit disabled until a valid task is provided, then navigates after creation', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/datasets') || url.endsWith('/documents')) return new Response('[]', { status: 200 });
      if (url.endsWith('/runs') && init?.method === 'POST') return new Response(JSON.stringify({ run_id: 'run-test-123' }), { status: 202 });
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();
    renderResearchForm();

    const taskInput = screen.getByLabelText('What would you like to research?');
    const submit = screen.getByRole('button', { name: 'Start research' });
    expect(submit).toBeDisabled();
    await user.type(taskInput, 'Short');
    expect(screen.getByText(/at least 10 characters/)).toBeInTheDocument();
    expect(submit).toBeDisabled();
    await user.click(screen.getByRole('button', { name: /Analyze Q3 sales by region/ }));
    expect(submit).toBeEnabled();
    fireEvent.click(submit);
    await waitFor(() => expect(screen.getByTestId('current-path')).toHaveTextContent('/runs/run-test-123'));
    const post = fetchMock.mock.calls.find((call) => call[1]?.method === 'POST');
    expect(post).toBeDefined();
    expect(JSON.parse(String(post?.[1]?.body))).toMatchObject({ task: expect.stringContaining('Analyze Q3 sales') });
  });
});
