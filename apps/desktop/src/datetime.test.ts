import { expect, it } from 'vitest';
import { apiDate } from './datetime';

it('interprets backend naive timestamps as UTC rather than Windows local time', () => {
  expect(apiDate('2026-10-08T18:54:27').getTime()).toBe(Date.UTC(2026, 9, 8, 18, 54, 27));
});

it('preserves explicit offsets and invalid timestamps', () => {
  expect(apiDate('2026-10-09T02:54:27+08:00').getTime()).toBe(apiDate('2026-10-08T18:54:27Z').getTime());
  expect(Number.isNaN(apiDate('not-a-timestamp').getTime())).toBe(true);
});
