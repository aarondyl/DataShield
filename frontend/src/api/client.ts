import axios from 'axios';

const client = axios.create({
  baseURL: window.datashieldDesktop?.apiBase ?? '/api',
  timeout: 120000,
  withCredentials: true,
});

// 桌面（Electron）模式下，每个请求携带主进程下发的运行时 token，
// 后端据此拒绝本机其他进程对 127.0.0.1 内嵌后端的盗用。
client.interceptors.request.use(async (config) => {
  const desktop = window.datashieldDesktop;
  if (desktop?.getToken) {
    const token = await desktop.getToken();
    config.headers.set('X-Runtime-Token', token);
  }
  return config;
});

export default client;
