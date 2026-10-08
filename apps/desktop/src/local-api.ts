import { invoke } from '@tauri-apps/api/core';

export type RuntimeHealth = { ok: boolean; message?: string };
export const selectRepository = () => invoke<string | null>('select_repository');

// The renderer only sends an API path and body. Rust validates the path and
// attaches X-Runtime-Token after reading runtime.json; the token never enters JS.
export async function getRuntimeHealth(): Promise<RuntimeHealth> {
  // 首次窗口渲染可能早于 sidecar 的 descriptor / HTTP readiness。
  // 保持“正在连接”，在有限时间内重试，避免健康的冷启动永久显示离线。
  let last: RuntimeHealth = { ok: false };
  for (let attempt = 0; attempt < 40; attempt++) {
    try {
      last = await invoke<RuntimeHealth>('runtime_health');
      if (last.ok) return last;
    } catch { last = { ok: false }; }
    if (attempt < 39) await new Promise(resolve => setTimeout(resolve, 500));
  }
  return last;
}

export async function localApiRequest<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  return invoke<T>('local_api_request', { request: { path, method, body } });
}
