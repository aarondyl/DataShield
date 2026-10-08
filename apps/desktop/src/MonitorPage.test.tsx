// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MonitorPage } from './MonitorPage';
import { zh } from './i18n';
import { localApiRequest } from './local-api';
vi.mock('./local-api', () => ({ localApiRequest: vi.fn() }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });
it('retains genuine cached events with explicit offline status after sync fails', async () => {
  let offline = false;
  vi.mocked(localApiRequest).mockImplementation(async (path, method) => {
    if (method === 'POST') { offline = true; throw new Error('Cloud unavailable'); }
    return (path.endsWith('/status') ? { scope: 'all:jurisdiction=*', last_success_at: '2026-10-08T00:00:00Z', using_local_cache: offline } : [{ event: { event_id: 'e1', payload: { materiality: 'HIGH' } }, regulation: { name: '缓存法规', source_url: 'https://example.org/official' } }]) as never;
  });
  render(<MonitorPage copy={zh} />);
  await screen.findByText('缓存法规');
  fireEvent.click(screen.getByRole('button', { name: '手动同步法规' }));
  await screen.findByRole('alert');
  expect(screen.getByText('缓存法规')).toBeTruthy();
  expect(screen.getByRole('status').textContent).toContain('本地缓存');
  expect(screen.getByRole('link').getAttribute('href')).toBe('https://example.org/official');
});
