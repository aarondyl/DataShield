// @vitest-environment jsdom
import React from 'react';
import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { TodayPage } from './TodayPage';
import { zh } from './i18n';
import { localApiRequest } from './local-api';
vi.mock('./local-api', () => ({ localApiRequest: vi.fn() }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });
test('empty findings without sync or analysis never imply all clear', async () => {
  vi.mocked(localApiRequest).mockImplementation(async path => (path.includes('/today?') ? { needs_review: [], waiting_for_you: [], recently_completed: [], latest_run: null } : path.includes('/status') ? { last_success_at: '', using_local_cache: true } : []) as never);
  render(<TodayPage copy={zh} workspace={{ companyId: 2, productId: 4 }} onNavigate={vi.fn()} />);
  await screen.findByText(zh.today.noRun);
  expect(screen.getByText(zh.monitor.offline)).toBeTruthy();
  expect(screen.queryByText(zh.today.clear)).toBeNull();
});
