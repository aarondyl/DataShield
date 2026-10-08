import { afterEach, expect, it, vi } from 'vitest';
import { invoke } from '@tauri-apps/api/core';
import { getRuntimeHealth } from './local-api';

vi.mock('@tauri-apps/api/core', () => ({ invoke: vi.fn() }));
afterEach(() => { vi.useRealTimers(); vi.resetAllMocks(); });

it('recovers when the first window renders before sidecar readiness', async () => {
  vi.useFakeTimers();
  vi.mocked(invoke).mockRejectedValueOnce(new Error('descriptor not ready'))
    .mockResolvedValueOnce({ ok: false }).mockResolvedValue({ ok: true });
  const health = getRuntimeHealth();
  await vi.advanceTimersByTimeAsync(2000);
  await expect(health).resolves.toEqual({ ok: true });
});

it('returns offline within a bounded wait when sidecar never starts', async () => {
  vi.useFakeTimers();
  vi.mocked(invoke).mockResolvedValue({ ok: false });
  const health = getRuntimeHealth();
  await vi.advanceTimersByTimeAsync(30000);
  await expect(health).resolves.toEqual({ ok: false });
  expect(vi.getTimerCount()).toBe(0);
});
