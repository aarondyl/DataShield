import { invoke } from '@tauri-apps/api/core';

export type RuntimeHealth = { ok: boolean; message?: string };

// The renderer only sends an API path and body. Rust validates the path and
// attaches X-Runtime-Token after reading runtime.json; the token never enters JS.
export async function getRuntimeHealth(): Promise<RuntimeHealth> {
  return invoke<RuntimeHealth>('runtime_health');
}

export async function localApiRequest<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  return invoke<T>('local_api_request', { request: { path, method, body } });
}
