import { isTauri } from '@tauri-apps/api/core';

/** Set the environment marker before React chooses routing and API transport. */
export function initializeRuntime(): void {
  window.datashieldDesktop = isTauri();
}

/** Desktop users enter the local app directly; browsers retain the website. */
export function desktopEntryPath(isDesktop: boolean, hasWorkspace: boolean): string | null {
  if (!isDesktop) return null;
  return hasWorkspace ? '/app/today' : '/choose';
}
