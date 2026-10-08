// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { TwinPage } from './TwinPage';
import { zh } from './i18n';
import { localApiRequest } from './local-api';
vi.mock('./local-api', () => ({ localApiRequest: vi.fn() }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });
it('confirms a fact through the bridge and shows the new version while retaining history', async () => {
  let version = 1;
  vi.mocked(localApiRequest).mockImplementation(async (path, method) => {
    if (method === 'POST') { version = 2; return {} as never; }
    if (path.includes('/versions?')) return [{ version: 2, created_at: '2026-10-08T00:00:00Z' }, { version: 1, created_at: '2026-10-07T00:00:00Z' }] as never;
    return { version, facts: [{ id: 7, name: 'ai_features', group: 'features', status: 'UNKNOWN', confirmation_status: version === 1 ? 'UNREVIEWED' : 'CONFIRMED' }] } as never;
  });
  render(<TwinPage copy={zh} workspace={{ companyId: 1, productId: 2 }} onIntake={vi.fn()} />);
  fireEvent.click(await screen.findByRole('button', { name: '确认此事实' }));
  await waitFor(() => expect(screen.getByText('当前画像版本: v2')).toBeTruthy());
  expect(localApiRequest).toHaveBeenCalledWith('/api/v1/ui/understanding/products/2/twin/facts/7/confirm', 'POST', { company_id: 1, note: '', actor_label: 'local-workspace-user' });
  expect(screen.getByText(/v1 ·/)).toBeTruthy();
  expect(screen.getByText(/未知 · 已确认/)).toBeTruthy();
});
