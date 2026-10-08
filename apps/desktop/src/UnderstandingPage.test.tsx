// @vitest-environment jsdom
import React from 'react';
import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { UnderstandingPage } from './UnderstandingPage';
import { zh } from './i18n';
import { localApiRequest, selectRepository } from './local-api';
vi.mock('./local-api', () => ({ localApiRequest: vi.fn(), selectRepository: vi.fn() }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });
test('repository path comes from native picker and analysis requires a separate import confirmation', async () => {
  vi.mocked(selectRepository).mockResolvedValue('C:\\Projects\\MyProduct');
  vi.mocked(localApiRequest).mockResolvedValue({ analysis_id: 'scan-1', kind: 'repository', status: 'COMPLETED', repository_analysis: { features: [{ name: 'file_upload', status: 'NOT_DETECTED' }], evidence: [{ evidence_id: 'e1', type: 'CODE', file: 'src/main.ts', reason: 'Static scan' }], limitations: [] } });
  const done = vi.fn();
  render(<UnderstandingPage copy={zh} workspace={{ companyId: 2, productId: 4 }} onDone={done} />);
  fireEvent.click(screen.getByRole('button', { name: zh.understanding.select }));
  await screen.findByText('C:\\Projects\\MyProduct');
  fireEvent.click(screen.getByRole('button', { name: zh.understanding.repository }));
  await screen.findByText('file_upload · 未检测到');
  expect(localApiRequest).toHaveBeenCalledWith('/api/v1/ui/understanding/repository', 'POST', { company_id: 2, product_id: 4, product_description: '', repository_path: 'C:\\Projects\\MyProduct', analysis_mode: 'FULL' });
  expect(done).not.toHaveBeenCalled();
  await waitFor(() => expect(screen.getByRole('button', { name: zh.understanding.attach }).hasAttribute('disabled')).toBe(false));
  fireEvent.click(screen.getByRole('button', { name: zh.understanding.attach }));
  await waitFor(() => expect(done).toHaveBeenCalled());
  expect(localApiRequest).toHaveBeenCalledWith('/api/v1/ui/understanding/products/4/twin/analyses', 'POST', { company_id: 2, analysis_id: 'scan-1', kind: 'repository' });
});
