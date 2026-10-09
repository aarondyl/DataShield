import axios, { type AxiosRequestConfig, type AxiosResponse } from 'axios';
import { invoke } from '@tauri-apps/api/core';

const baseURL = '/api';
const webClient = axios.create({
  baseURL,
  timeout: 120000,
  withCredentials: true,
});

type ApiResponse<T> = Pick<AxiosResponse<T>, 'data' | 'status'>;
function desktopRequest<T>(method: string, url: string, body?: unknown, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
  if (body instanceof FormData) return Promise.reject(new Error('桌面安全 Bridge 暂不支持文件直传，请使用本地文件接入流程'));
  const path = new URLSearchParams();
  Object.entries(config?.params ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null) path.set(key, String(value));
  });
  const basePath = `${baseURL}/${url.replace(/^\//, '')}`;
  const query = path.toString();
  return invoke<T>('local_api_request', { request: { path: `${basePath}${query ? `?${query}` : ''}`, method, body } })
    .then(data => ({ data: data as T, status: 200 }))
    .catch((error: unknown) => {
      const detail = error instanceof Error ? error.message : '本地服务请求失败';
      return Promise.reject({ response: { status: 500, data: { detail } }, message: detail });
    });
}

const client = {
  get<T = any>(url: string, config?: AxiosRequestConfig) {
    return window.datashieldDesktop ? desktopRequest<T>('GET', url, undefined, config) : webClient.get<T>(url, config);
  },
  post<T = any>(url: string, data?: unknown, config?: AxiosRequestConfig) {
    return window.datashieldDesktop ? desktopRequest<T>('POST', url, data, config) : webClient.post<T>(url, data, config);
  },
  put<T = any>(url: string, data?: unknown, config?: AxiosRequestConfig) {
    return window.datashieldDesktop ? desktopRequest<T>('PUT', url, data, config) : webClient.put<T>(url, data, config);
  },
  patch<T = any>(url: string, data?: unknown, config?: AxiosRequestConfig) {
    return window.datashieldDesktop ? desktopRequest<T>('PATCH', url, data, config) : webClient.patch<T>(url, data, config);
  },
  delete<T = any>(url: string, config?: AxiosRequestConfig) {
    return window.datashieldDesktop ? desktopRequest<T>('DELETE', url, undefined, config) : webClient.delete<T>(url, config);
  },
};

export default client;
