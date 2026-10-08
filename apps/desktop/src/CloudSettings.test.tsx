// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { CloudSettings } from './CloudSettings';
import { zh, useLocale } from './i18n';
import { localApiRequest } from './local-api';
import { act, renderHook } from '@testing-library/react';
vi.mock('./local-api', () => ({ localApiRequest: vi.fn() }));
afterEach(() => { cleanup(); vi.resetAllMocks(); localStorage.clear(); });
it('saves a public HTTPS endpoint through Rust without credentials', async () => {
  vi.mocked(localApiRequest).mockResolvedValue({ base_url: '' });
  render(<CloudSettings copy={zh} />);
  await waitFor(() => expect(localApiRequest).toHaveBeenCalled());
  fireEvent.change(screen.getByRole('textbox'), { target: { value: 'https://regintel.example.org' } });
  fireEvent.click(screen.getByRole('button', { name: '保存同步配置' }));
  await screen.findByText('配置已保存，可前往法规动态同步。');
  expect(localApiRequest).toHaveBeenCalledWith('/api/v1/local-regulations/configuration', 'PUT', { base_url: 'https://regintel.example.org' });
});
it('defaults to Chinese and persists instant English switching', () => {
  const { result, unmount } = renderHook(useLocale);
  expect(result.current.locale).toBe('zh-CN');
  act(() => result.current.setLocale('en-US'));
  expect(result.current.copy.actions.create).toBe('Generate recommendation');
  expect(document.documentElement.lang).toBe('en-US');
  unmount();
  const next = renderHook(useLocale);
  expect(next.result.current.locale).toBe('en-US');
});
