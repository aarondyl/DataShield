import { expect, test } from 'vitest';
import { en, zh } from './i18n';
const paths = (value: unknown, prefix = ''): string[] => Array.isArray(value) ? value.flatMap((v, i) => paths(v, `${prefix}.${i}`)) : value && typeof value === 'object' ? Object.entries(value).flatMap(([k, v]) => paths(v, `${prefix}.${k}`)) : [prefix];
test('Chinese and English have identical leaf keys and nonempty translations', () => {
  expect(paths(zh)).toEqual(paths(en));
  const leaves = (v: unknown): unknown[] => v && typeof v === 'object' ? Object.values(v).flatMap(leaves) : [v];
  for (const leaf of [...leaves(zh), ...leaves(en)]) expect(typeof leaf === 'string' && leaf.trim().length > 0).toBe(true);
});
