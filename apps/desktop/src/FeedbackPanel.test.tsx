// @vitest-environment jsdom
import React from 'react';
import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { FeedbackPanel } from './FeedbackPanel';
import { zh } from './i18n';
import { localApiRequest } from './local-api';
vi.mock('./local-api', () => ({ localApiRequest: vi.fn() }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });
test('confirmation is separate from apply; written version and failed reanalysis remain retryable', async () => {
  let exists = false; let status = 'PROPOSED'; let attempts = 0;
  const calls: string[] = [];
  vi.mocked(localApiRequest).mockImplementation(async (path, method) => {
    calls.push(path);
    if (method === 'POST') {
      exists = true;
      if (path.endsWith('/confirm')) status = 'CONFIRMED';
      if (path.endsWith('/apply')) { attempts++; if (attempts === 2) status = 'APPLIED'; }
      return {} as never;
    }
    return (exists ? [{ feedback: { id: 1, finding_id: 3, raw_text: '用户事实' }, candidates: [{ id: 2, status, reasoning_summary: '修正解释', proposed_name: 'ai_disclosure', proposed_status: 'PRESENT', applied_twin_version_id: attempts ? 8 : null, reanalysis_run_id: attempts ? 9 : null, last_error: attempts === 1 ? 'FAILED' : '' }] }] : []) as never;
  });
  render(<FeedbackPanel copy={zh} workspace={{ companyId: 2, productId: 4 }} findingId={3} />);
  fireEvent.change(screen.getByLabelText(zh.feedback.input), { target: { value: '用户事实' } });
  fireEvent.click(screen.getByRole('button', { name: zh.feedback.interpret }));
  await screen.findByText('修正解释');
  await waitFor(() => expect(screen.getByRole('button', { name: zh.feedback.confirm }).hasAttribute('disabled')).toBe(false));
  fireEvent.click(screen.getByRole('button', { name: zh.feedback.confirm }));
  await screen.findByText(zh.feedback.confirmed);
  expect(calls.some(p => p.endsWith('/apply'))).toBe(false);
  await waitFor(() => expect(screen.getByRole('button', { name: zh.feedback.apply }).hasAttribute('disabled')).toBe(false));
  fireEvent.click(screen.getByRole('button', { name: zh.feedback.apply }));
  await screen.findByText(zh.feedback.failed);
  expect(screen.queryByText(zh.feedback.applied)).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: zh.feedback.retry }));
  await screen.findByText(zh.feedback.applied);
});
