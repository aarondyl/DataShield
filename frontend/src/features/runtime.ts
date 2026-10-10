import { isTauri } from '@tauri-apps/api/core';

/** Set the shared UI runtime flag before React renders. */
export function initializeRuntime(): boolean {
  const desktop = isTauri();
  window.datashieldDesktop = desktop;
  return desktop;
}
