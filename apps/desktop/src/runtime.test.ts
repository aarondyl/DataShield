// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { initializeRuntime } from '../../../frontend/src/runtime';

describe('initializeRuntime', () => {
  afterEach(() => {
    delete (globalThis as typeof globalThis & { isTauri?: boolean }).isTauri;
    delete window.datashieldDesktop;
  });

  it('selects the Rust bridge mode inside Tauri before the app renders', () => {
    (globalThis as typeof globalThis & { isTauri?: boolean }).isTauri = true;

    initializeRuntime();

    expect(window.datashieldDesktop).toBe(true);
  });

  it('keeps browser builds on the browser API client', () => {
    (globalThis as typeof globalThis & { isTauri?: boolean }).isTauri = false;

    initializeRuntime();

    expect(window.datashieldDesktop).toBe(false);
  });
});
