import { expect, test } from '@playwright/test';

test('starts research, follows the run, and opens its downloadable report', async ({ page }) => {
  const runId = 'run-stage12-demo';
  await page.route('**/health', (route) => route.fulfill({ json: { status: 'ok', version: '0.1.0', db: 'ok' } }));
  await page.route('**/api/v1/stats/overview', (route) => route.fulfill({
    json: { total_runs: 1, success_rate: 1, average_duration_ms: 1200, total_tool_calls: 2, runs_by_status: { completed: 1 }, runs_by_day: [], tool_usage: [], recent_runs: [] },
  }));
  await page.route('**/api/v1/documents', (route) => route.fulfill({ json: [] }));
  await page.route('**/api/v1/datasets', (route) => route.fulfill({ json: [] }));
  await page.route('**/api/v1/runs', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({ status: 202, json: { run_id: runId } });
    } else {
      await route.fulfill({ json: { items: [], total: 0, limit: 10, offset: 0 } });
    }
  });
  await page.route(`**/api/v1/runs/${runId}`, (route) => route.fulfill({
    json: {
      run_id: runId,
      task: 'Analyze Q3 sales by region and recommend actions.',
      status: 'completed',
      created_at: new Date().toISOString(),
      finished_at: new Date().toISOString(),
      total_duration_ms: 1200,
      plan: [],
      findings: [],
      validation_results: [],
      tool_call_count: 2,
      retry_count: 0,
      failure_count: 0,
      token_count: 0,
      replan_count: 0,
    },
  }));
  await page.route(`**/api/v1/runs/${runId}/events`, (route) => route.fulfill({
    status: 200,
    contentType: 'text/event-stream',
    body: `id: 1\nevent: run_completed\ndata: {"status":"completed","node":"reporter"}\n\n`,
  }));
  await page.route(`**/api/v1/runs/${runId}/logs*`, (route) => route.fulfill({ json: [] }));
  await page.route(`**/api/v1/runs/${runId}/tool-calls`, (route) => route.fulfill({ json: [] }));
  await page.route(`**/api/v1/runs/${runId}/report`, (route) => route.fulfill({
    json: { title: 'Q3 sales review', content_markdown: '# Q3 sales review\n## Executive summary\nSales performance was reviewed across regions.' },
  }));
  await page.route(`**/api/v1/runs/${runId}/report/download*`, (route) => route.fulfill({ status: 200, contentType: 'application/pdf', body: 'PDF' }));

  await page.goto('/runs/new');
  await page.getByLabel('What would you like to research?').fill('Analyze Q3 sales by region and recommend actions.');
  await page.getByRole('button', { name: 'Start research' }).click();
  await expect(page).toHaveURL(new RegExp(`/runs/${runId}$`));
  await expect(page.getByText('completed', { exact: true })).toBeVisible();
  await page.getByRole('tab', { name: 'Report' }).click();
  await expect(page.getByRole('heading', { name: 'Executive summary' })).toBeVisible();
  await expect(page.getByRole('link', { name: /PDF/i })).toHaveAttribute('href', new RegExp(`${runId}/report/download\\?format=pdf`));
});

test('supports theme switching and mobile navigation without horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.addInitScript(() => localStorage.removeItem('researchpilot-theme'));
  await page.goto('/settings');
  await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();

  const initialTheme = await page.locator('html').getAttribute('data-theme');
  await page.getByRole('button', { name: `Switch to ${initialTheme === 'dark' ? 'light' : 'dark'} theme` }).click();
  await expect.poll(() => page.locator('html').getAttribute('data-theme')).not.toBe(initialTheme);

  await page.getByRole('button', { name: 'Open navigation' }).click();
  await expect(page.locator('.sidebar')).toHaveClass(/sidebar-mobile-open/);
  const widths = await page.evaluate(() => ({ viewport: window.innerWidth, document: document.documentElement.scrollWidth }));
  expect(widths.document).toBeLessThanOrEqual(widths.viewport);
});
