import { isTauri } from '@tauri-apps/api/core';

/** Set the environment marker before React chooses routing and API transport. */
export function initializeRuntime(): void {
  window.datashieldDesktop = isTauri();
}
